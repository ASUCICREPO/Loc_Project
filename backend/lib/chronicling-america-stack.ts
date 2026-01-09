import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3n from "aws-cdk-lib/aws-s3-notifications";
import * as iam from "aws-cdk-lib/aws-iam";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as logs from "aws-cdk-lib/aws-logs";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as bedrock from "aws-cdk-lib/aws-bedrock";
import * as codebuild from "aws-cdk-lib/aws-codebuild";
import * as amplify from "aws-cdk-lib/aws-amplify";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import { Construct } from "constructs";
import * as path from "path";

export interface ChroniclingAmericaStackProps extends cdk.StackProps {
  projectName: string;
  dataBucketName?: string;
  bedrockModelId?: string;
}

export class ChroniclingAmericaStack extends cdk.Stack {
  constructor(
    scope: Construct,
    id: string,
    props: ChroniclingAmericaStackProps
  ) {
    super(scope, id, props);

    const projectName = props.projectName;
    // Use inference profile for cross-region routing, or foundation model for single region
    // Inference profile: "us.anthropic.claude-sonnet-4-0-v1:0"
    // Foundation model: "anthropic.claude-3-5-sonnet-20241022-v2:0"
    const bedrockModelId =
      props.bedrockModelId || "anthropic.claude-3-5-sonnet-20241022-v2:0";

    // ========================================
    // S3 Buckets for Data Storage
    // ========================================
    const dataBucket = new s3.Bucket(this, "DataBucket", {
      bucketName:
        props.dataBucketName ||
        `${projectName}-data-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      eventBridgeEnabled: true, // Enable EventBridge for S3 events
    });

    // Transformation bucket for Knowledge Base intermediate storage
    const transformationBucket = new s3.Bucket(this, "TransformationBucket", {
      bucketName: `loc-transformation-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Can be destroyed since it's just temp storage
      lifecycleRules: [
        {
          id: "DeleteTempFiles",
          enabled: true,
          expiration: cdk.Duration.days(7), // Auto-delete temp files after 7 days
        },
      ],
    });

    // Grant Bedrock service access to both S3 buckets
    dataBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("bedrock.amazonaws.com")],
        actions: ["s3:GetObject", "s3:ListBucket"],
        resources: [dataBucket.bucketArn, `${dataBucket.bucketArn}/*`],
        conditions: {
          StringEquals: {
            "aws:SourceAccount": this.account,
          },
        },
      })
    );

    // Grant Bedrock service access to transformation bucket (read/write for intermediate storage)
    transformationBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("bedrock.amazonaws.com")],
        actions: [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ],
        resources: [
          transformationBucket.bucketArn,
          `${transformationBucket.bucketArn}/*`,
        ],
        conditions: {
          StringEquals: {
            "aws:SourceAccount": this.account,
          },
        },
      })
    );



    // ========================================
    // VPC for Fargate (minimal setup)
    // ========================================
    const vpc = new ec2.Vpc(this, "VPC", {
      maxAzs: 2,
      natGateways: 0, // Use public subnets only for cost savings
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
      ],
      restrictDefaultSecurityGroup: false, // Disable to avoid IAM permission issues
    });

    // ========================================
    // ECS Cluster for Fargate Tasks
    // ========================================
    const ecsCluster = new ecs.Cluster(this, "ECSCluster", {
      clusterName: `${projectName}-cluster`,
      vpc,
      containerInsights: true,
    });

    // ECR Repository for Fargate task image
    const collectorRepository = new ecr.Repository(
      this,
      "CollectorRepository",
      {
        repositoryName: `${projectName}-collector`,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
        lifecycleRules: [
          {
            maxImageCount: 5,
            description: "Keep only 5 most recent images",
          },
        ],
      }
    );

    // Fargate Task Execution Role
    const fargateExecutionRole = new iam.Role(this, "FargateExecutionRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AmazonECSTaskExecutionRolePolicy"
        ),
      ],
    });

    // Fargate Task Role (for application permissions)
    const fargateTaskRole = new iam.Role(this, "FargateTaskRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    });

    // Grant S3 permissions to Fargate task
    dataBucket.grantReadWrite(fargateTaskRole);

    // Grant Bedrock permissions to Fargate task (for triggering KB sync)
    fargateTaskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs",
        ],
        resources: ["*"],
      })
    );

    // Grant Amazon Textract permissions to Fargate task
    fargateTaskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "textract:DetectDocumentText",
          "textract:StartDocumentTextDetection",
          "textract:GetDocumentTextDetection",
        ],
        resources: ["*"],
      })
    );

    // Fargate Task Definition
    const collectorTaskDefinition = new ecs.FargateTaskDefinition(
      this,
      "CollectorTaskDefinition",
      {
        family: `${projectName}-collector`,
        cpu: 2048, // 2 vCPU
        memoryLimitMiB: 4096, // 4 GB
        executionRole: fargateExecutionRole,
        taskRole: fargateTaskRole,
      }
    );

    // Log Group for Fargate task
    const collectorLogGroup = new logs.LogGroup(this, "CollectorLogGroup", {
      logGroupName: `/ecs/${projectName}-collector`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Container Definition
    collectorTaskDefinition.addContainer("CollectorContainer", {
      containerName: "collector",
      image: ecs.ContainerImage.fromEcrRepository(
        collectorRepository,
        "latest"
      ),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: "collector",
        logGroup: collectorLogGroup,
      }),
      environment: {
        BUCKET_NAME: dataBucket.bucketName,
        BEDROCK_MODEL_ID: bedrockModelId,
        // Congress Bills Configuration
        START_CONGRESS: "1",
        END_CONGRESS: "16",
        BILL_TYPES: "hr,s,hjres,sjres,hconres,sconres,hres,sres",
        CONGRESS_API_KEY: "MThtRT5WkFu8I8CHOfiLLebG4nsnKcX3JnNv2N8A",
        // Chronicling America Newspapers Configuration
        START_YEAR: "1760",
        END_YEAR: "1820",
        MAX_NEWSPAPER_PAGES: "10",
      },
    });

    // ========================================
    // IAM Role for Bedrock Knowledge Base
    // ========================================
    const knowledgeBaseRole = new iam.Role(this, "KnowledgeBaseRole", {
      assumedBy: new iam.ServicePrincipal("bedrock.amazonaws.com"),
      description: "Role for Bedrock Knowledge Base to access S3 and Neptune",
    });

    // Grant S3 permissions to Knowledge Base role
    dataBucket.grantRead(knowledgeBaseRole);
    transformationBucket.grantReadWrite(knowledgeBaseRole);

    // Grant Neptune Analytics permissions
    knowledgeBaseRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["neptune-graph:*", "neptune-db:*"],
        resources: ["*"],
      })
    );

    // Grant Bedrock model access (for embeddings and entity extraction)
    knowledgeBaseRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
          `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0`,
        ],
      })
    );

    // Grant Lambda invoke permission to Knowledge Base role (for transformation lambda)
    // Include all versions to handle $LATEST and versioned invocations
    knowledgeBaseRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["lambda:InvokeFunction"],
        resources: [
          `arn:aws:lambda:${this.region}:${this.account}:function:${projectName}-kb-transformation`,
          `arn:aws:lambda:${this.region}:${this.account}:function:${projectName}-kb-transformation:$LATEST`,
          `arn:aws:lambda:${this.region}:${this.account}:function:${projectName}-kb-transformation:*`,
        ],
      })
    );

    // ========================================
    // Knowledge Base will be created via CLI in buildspec.yml
    // ========================================

    // Placeholder values - will be updated by CLI after KB creation
    const knowledgeBaseId = "PLACEHOLDER_KB_ID";
    const dataSourceId = "PLACEHOLDER_DS_ID";

    // ========================================
    // CodeBuild Role for Neptune Analytics (for buildspec.yml)
    // ========================================
    const codeBuildRole = new iam.Role(this, "CodeBuildNeptuneRole", {
      assumedBy: new iam.ServicePrincipal("codebuild.amazonaws.com"),
      description: "Role for CodeBuild to create Neptune Analytics resources",
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("AWSCodeBuildDeveloperAccess"),
      ],
    });

    // Grant Neptune Analytics permissions to CodeBuild
    codeBuildRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "neptune-graph:CreateGraph",
          "neptune-graph:DeleteGraph",
          "neptune-graph:GetGraph",
          "neptune-graph:ListGraphs",
          "neptune-graph:UpdateGraph",
          "neptune-graph:CreateGraphSnapshot",
          "neptune-graph:DeleteGraphSnapshot",
          "neptune-graph:ListGraphSnapshots",
          "neptune-graph:RestoreGraphFromSnapshot",
          "neptune-graph:TagResource",
          "neptune-graph:UntagResource"
        ],
        resources: ["*"],
      })
    );

    // Grant Bedrock Agent permissions for Knowledge Base creation
    codeBuildRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:CreateKnowledgeBase",
          "bedrock:DeleteKnowledgeBase",
          "bedrock:GetKnowledgeBase",
          "bedrock:ListKnowledgeBases",
          "bedrock:UpdateKnowledgeBase",
          "bedrock-agent:CreateDataSource",
          "bedrock-agent:DeleteDataSource",
          "bedrock-agent:GetDataSource",
          "bedrock-agent:ListDataSources",
          "bedrock-agent:UpdateDataSource"
        ],
        resources: ["*"],
      })
    );

    // Grant IAM PassRole for Knowledge Base role
    codeBuildRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: [knowledgeBaseRole.roleArn],
      })
    );

    // ========================================
    // Lambda Execution Role
    // ========================================
    const lambdaRole = new iam.Role(this, "LambdaExecutionRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    // Grant ECS permissions to Lambda (for Fargate trigger)
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["ecs:RunTask", "ecs:DescribeTasks", "ecs:StopTask"],
        resources: ["*"],
      })
    );

    // Grant PassRole for ECS task execution
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: [fargateExecutionRole.roleArn, fargateTaskRole.roleArn],
      })
    );

    // Grant Bedrock Agent permissions (for KB sync)
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs",
        ],
        resources: ["*"],
      })
    );

    // Grant Bedrock model invocation permissions (for chat)
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate",
          "bedrock:GetInferenceProfile",
          "bedrock:ListInferenceProfiles",
          "bedrock:Rerank",  // For reranker model
        ],
        resources: ["*"],
      })
    );

    // Grant STS permissions to get account ID (for inference profile ARNs)
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["sts:GetCallerIdentity"],
        resources: ["*"],
      })
    );

    // Grant S3 read permissions to Lambda for direct bill lookup
    dataBucket.grantRead(lambdaRole);
    
    // Grant transformation lambda access to transformation bucket
    transformationBucket.grantReadWrite(lambdaRole);

    // ========================================
    // Lambda Functions (Only 3 needed!)
    // ========================================

    // 1. Fargate Trigger Lambda
    const fargateTriggerLogGroup = new logs.LogGroup(
      this,
      "FargateTriggerLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-fargate-trigger`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    // Create security group for Fargate tasks
    const fargateSecurityGroup = new ec2.SecurityGroup(
      this,
      "FargateSecurityGroup",
      {
        vpc,
        description: "Security group for Fargate collector tasks",
        allowAllOutbound: true,
      }
    );

    const fargateTriggerFunction = new lambda.Function(
      this,
      "FargateTriggerFunction",
      {
        functionName: `${projectName}-fargate-trigger`,
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: "lambda_function.lambda_handler",
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/fargate-trigger")
        ),
        timeout: cdk.Duration.seconds(30),
        memorySize: 256,
        role: lambdaRole,
        environment: {
          ECS_CLUSTER_NAME: ecsCluster.clusterName,
          TASK_DEFINITION_ARN: collectorTaskDefinition.taskDefinitionArn,
          SUBNET_IDS: vpc.publicSubnets.map((s) => s.subnetId).join(","),
          SECURITY_GROUP_ID: fargateSecurityGroup.securityGroupId,
          BUCKET_NAME: dataBucket.bucketName,
          START_CONGRESS: "1",
          END_CONGRESS: "16",
          BILL_TYPES: "hr,s,hjres,sjres,hconres,sconres,hres,sres",
          KNOWLEDGE_BASE_ID: knowledgeBaseId,
          DATA_SOURCE_ID: dataSourceId,
        },
        logGroup: fargateTriggerLogGroup,
      }
    );

    // 2. KB Sync Trigger Lambda
    const kbSyncTriggerLogGroup = new logs.LogGroup(
      this,
      "KBSyncTriggerLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-kb-sync-trigger`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const kbSyncTriggerFunction = new lambda.Function(
      this,
      "KBSyncTriggerFunction",
      {
        functionName: `${projectName}-kb-sync-trigger`,
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: "lambda_function.lambda_handler",
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/kb-sync-trigger")
        ),
        timeout: cdk.Duration.minutes(2),
        memorySize: 256,
        role: lambdaRole,
        environment: {
          KNOWLEDGE_BASE_ID: knowledgeBaseId,
          DATA_SOURCE_ID: dataSourceId,
        },
        logGroup: kbSyncTriggerLogGroup,
      }
    );

    // Note: S3 event notification removed to avoid triggering KB sync for each file
    // KB sync should be triggered manually after all files are collected
    // Or triggered by the Fargate task when collection is complete

    // Uncomment below to enable auto-sync (will trigger for EACH file):
    // dataBucket.addEventNotification(
    //   s3.EventType.OBJECT_CREATED,
    //   new s3n.LambdaDestination(kbSyncTriggerFunction),
    //   { prefix: "extracted/", suffix: ".txt" }
    // );

    // 3. KB Transformation Lambda (for GraphRAG structure)
    const kbTransformationLogGroup = new logs.LogGroup(
      this,
      "KBTransformationLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-kb-transformation`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const kbTransformationFunction = new lambda.Function(
      this,
      "KBTransformationFunction",
      {
        functionName: `${projectName}-kb-transformation`,
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: "lambda_function.lambda_handler",
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/kb-transformation")
        ),
        timeout: cdk.Duration.seconds(60),
        memorySize: 512,
        role: lambdaRole,
        logGroup: kbTransformationLogGroup,
      }
    );

    // Grant Knowledge Base permission to invoke transformation Lambda
    kbTransformationFunction.grantInvoke(
      new iam.ServicePrincipal("bedrock.amazonaws.com")
    );

    // Additional permission for Knowledge Base to invoke Lambda with specific conditions
    kbTransformationFunction.addPermission("BedrockKnowledgeBaseInvoke", {
      principal: new iam.ServicePrincipal("bedrock.amazonaws.com"),
      action: "lambda:InvokeFunction",
      sourceAccount: this.account,
    });

    // 4. Chat Handler Lambda
    const chatHandlerLogGroup = new logs.LogGroup(this, "ChatHandlerLogGroup", {
      logGroupName: `/aws/lambda/${projectName}-chat-handler`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const chatHandlerFunction = new lambda.Function(
      this,
      "ChatHandlerFunction",
      {
        functionName: `${projectName}-chat-handler`,
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: "lambda_function.lambda_handler",
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/chat-handler")
        ),
        timeout: cdk.Duration.seconds(30),
        memorySize: 1024,
        role: lambdaRole,
        environment: {
          KNOWLEDGE_BASE_ID: knowledgeBaseId, // Will be updated by CLI
          MODEL_ID: bedrockModelId,
          DATA_BUCKET_NAME: dataBucket.bucketName, // For direct S3 access
        },
        logGroup: chatHandlerLogGroup,
      }
    );

    // ========================================
    // API Gateway for Chat UI
    // ========================================
    const api = new apigateway.RestApi(this, "ChatAPI", {
      restApiName: `${projectName}-chat-api`,
      description: "API for historical Congress bills chat interface",
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ["Content-Type", "Authorization"],
      },
    });

    // Chat endpoint
    const chatIntegration = new apigateway.LambdaIntegration(
      chatHandlerFunction
    );
    const chatResource = api.root.addResource("chat");
    chatResource.addMethod("POST", chatIntegration);

    // Health endpoint
    const healthResource = api.root.addResource("health");
    healthResource.addMethod("GET", chatIntegration);

    // Fargate trigger endpoint
    const collectIntegration = new apigateway.LambdaIntegration(
      fargateTriggerFunction
    );
    const collectResource = api.root.addResource("collect");
    collectResource.addMethod("POST", collectIntegration);

    // ========================================
    // S3 Bucket for Frontend Builds (Amplify)
    // ========================================
    const buildsBucket = new s3.Bucket(this, "BuildsBucket", {
      bucketName: `${projectName}-builds-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      versioned: false,
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // Grant Amplify service access to builds bucket (critical for deployment)
    buildsBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: "AllowAmplifyServiceAccess",
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("amplify.amazonaws.com")],
        actions: [
          "s3:GetObject",
          "s3:GetObjectAcl",
          "s3:GetObjectVersion",
          "s3:GetObjectVersionAcl",
          "s3:PutObjectAcl",
          "s3:PutObjectVersionAcl",
          "s3:ListBucket",
          "s3:GetBucketAcl",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:GetBucketPolicy",
          "s3:GetBucketPolicyStatus",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetEncryptionConfiguration",
        ],
        resources: [buildsBucket.bucketArn, `${buildsBucket.bucketArn}/*`],
        conditions: {
          StringEquals: {
            "aws:SourceAccount": this.account,
          },
        },
      })
    );

    // ========================================
    // AWS Amplify App for Frontend Deployment
    // ========================================
    const amplifyApp = new amplify.CfnApp(this, "AmplifyApp", {
      name: `${projectName}-frontend`,
      description: "Chronicling America Frontend - Historical Congressional Bills Chat Interface",
      platform: "WEB",
      environmentVariables: [
        {
          name: "REACT_APP_API_BASE_URL",
          value: api.url,
        },
        {
          name: "REACT_APP_CHAT_ENDPOINT", 
          value: api.url,
        },
        {
          name: "REACT_APP_HEALTH_ENDPOINT",
          value: api.url,
        },
        {
          name: "REACT_APP_AWS_REGION",
          value: this.region,
        },
        {
          name: "AMPLIFY_DIFF_DEPLOY",
          value: "false",
        },
        {
          name: "AMPLIFY_MONOREPO_APP_ROOT",
          value: "frontend",
        },
        {
          name: "_LIVE_UPDATES",
          value: JSON.stringify([
            {
              name: "Node.js version",
              pkg: "node",
              type: "nvm",
              version: "18",
            },
          ]),
        },
      ],
      customRules: [
        {
          source: "/<*>",
          target: "/index.html",
          status: "404-200", // SPA routing support
        },
      ],
    });

    // Create Amplify branch for main deployment
    const amplifyBranch = new amplify.CfnBranch(this, "AmplifyBranch", {
      appId: amplifyApp.attrAppId,
      branchName: "main",
      description: "Main branch for production deployment",
      enableAutoBuild: false, // We'll trigger builds via CodeBuild
      environmentVariables: [
        {
          name: "REACT_APP_API_BASE_URL",
          value: api.url,
        },
        {
          name: "REACT_APP_CHAT_ENDPOINT",
          value: api.url,
        },
        {
          name: "REACT_APP_HEALTH_ENDPOINT", 
          value: api.url,
        },
        {
          name: "REACT_APP_AWS_REGION",
          value: this.region,
        },
      ],
    });

    // ========================================
    // Outputs
    // ========================================
    new cdk.CfnOutput(this, "DataBucketName", {
      value: dataBucket.bucketName,
      description: "S3 bucket for pipeline data",
      exportName: `${projectName}-data-bucket`,
    });

    new cdk.CfnOutput(this, "TransformationBucketName", {
      value: transformationBucket.bucketName,
      description: "S3 bucket for Knowledge Base transformation intermediate storage",
      exportName: `${projectName}-transformation-bucket`,
    });



    new cdk.CfnOutput(this, "KnowledgeBaseRoleArn", {
      value: knowledgeBaseRole.roleArn,
      description: "IAM role ARN for Bedrock Knowledge Base",
      exportName: `${projectName}-kb-role`,
    });

    new cdk.CfnOutput(this, "APIGatewayURL", {
      value: api.url,
      description: "API Gateway URL for chat interface",
      exportName: `${projectName}-api-url`,
    });

    new cdk.CfnOutput(this, "ChatEndpoint", {
      value: `${api.url}chat`,
      description: "Chat endpoint URL",
    });

    new cdk.CfnOutput(this, "CollectEndpoint", {
      value: `${api.url}collect`,
      description: "Fargate collection trigger endpoint",
    });

    new cdk.CfnOutput(this, "ECRRepositoryUri", {
      value: collectorRepository.repositoryUri,
      description: "ECR repository URI for Fargate collector image",
      exportName: `${projectName}-ecr-repository`,
    });

    new cdk.CfnOutput(this, "FargateTaskDefinitionArn", {
      value: collectorTaskDefinition.taskDefinitionArn,
      description: "Fargate task definition ARN",
      exportName: `${projectName}-fargate-task`,
    });

    new cdk.CfnOutput(this, "ExtractedDataPrefix", {
      value: `s3://${dataBucket.bucketName}/extracted/`,
      description: "S3 prefix where Fargate saves extracted bill text",
    });

    new cdk.CfnOutput(this, "BedrockModelId", {
      value: bedrockModelId,
      description: "Bedrock model ID used for chat responses",
    });

    new cdk.CfnOutput(this, "KBTransformationFunctionArn", {
      value: kbTransformationFunction.functionArn,
      description: "Transformation Lambda ARN for Knowledge Base GraphRAG",
      exportName: `${projectName}-kb-transformation-arn`,
    });

    new cdk.CfnOutput(this, "CodeBuildNeptuneRoleArn", {
      value: codeBuildRole.roleArn,
      description: "CodeBuild role ARN with Neptune Analytics permissions",
      exportName: `${projectName}-codebuild-neptune-role`,
    });

    // ========================================
    // IAM Policy for Existing CodeBuild Role
    // ========================================
    // Create a managed policy that can be attached to your existing CodeBuild role
    const neptuneBedrockPolicy = new iam.ManagedPolicy(this, "NeptuneBedrockPolicy", {
      managedPolicyName: `${projectName}-neptune-bedrock-policy`,
      description: "Policy for CodeBuild to create Neptune Analytics and Bedrock resources",
      statements: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "neptune-graph:CreateGraph",
            "neptune-graph:DeleteGraph",
            "neptune-graph:GetGraph",
            "neptune-graph:ListGraphs",
            "neptune-graph:UpdateGraph",
            "neptune-graph:TagResource",
            "neptune-graph:UntagResource"
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "bedrock:CreateKnowledgeBase",
            "bedrock:DeleteKnowledgeBase",
            "bedrock:GetKnowledgeBase",
            "bedrock:ListKnowledgeBases",
            "bedrock:UpdateKnowledgeBase",
            "bedrock-agent:CreateDataSource",
            "bedrock-agent:DeleteDataSource",
            "bedrock-agent:GetDataSource",
            "bedrock-agent:ListDataSources",
            "bedrock-agent:UpdateDataSource"
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["iam:PassRole"],
          resources: [knowledgeBaseRole.roleArn],
        }),
      ],
    });

    new cdk.CfnOutput(this, "NeptuneBedrockPolicyArn", {
      value: neptuneBedrockPolicy.managedPolicyArn,
      description: "Managed policy ARN to attach to your existing CodeBuild role",
    });

    // ========================================
    // Frontend Deployment Outputs
    // ========================================
    new cdk.CfnOutput(this, "AmplifyAppId", {
      value: amplifyApp.attrAppId,
      description: "Amplify App ID for frontend deployment",
      exportName: `${projectName}-amplify-app-id`,
    });

    new cdk.CfnOutput(this, "AmplifyAppUrl", {
      value: `https://${amplifyBranch.branchName}.${amplifyApp.attrAppId}.amplifyapp.com`,
      description: "Amplify App URL for frontend access",
    });

    new cdk.CfnOutput(this, "BuildsBucketName", {
      value: buildsBucket.bucketName,
      description: "S3 bucket for frontend builds",
      exportName: `${projectName}-builds-bucket`,
    });
  }
}
