import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as neptune from "aws-cdk-lib/aws-neptune";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as stepfunctions from "aws-cdk-lib/aws-stepfunctions";
import * as tasks from "aws-cdk-lib/aws-stepfunctions-tasks";
import * as logs from "aws-cdk-lib/aws-logs";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecr from "aws-cdk-lib/aws-ecr";
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
    const bedrockModelId =
      props.bedrockModelId || "anthropic.claude-3-5-sonnet-20241022-v2:0";

    // ========================================
    // S3 Bucket for Data Storage
    // ========================================
    const dataBucket = new s3.Bucket(this, "DataBucket", {
      bucketName:
        props.dataBucketName ||
        `${projectName}-data-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: "DeleteOldExtractions",
          expiration: cdk.Duration.days(90),
          prefix: "extracted/",
        },
      ],
    });

    // Grant Bedrock Data Automation service access to S3 bucket
    dataBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("bedrock.amazonaws.com")],
        actions: ["s3:GetObject", "s3:PutObject"],
        resources: [`${dataBucket.bucketArn}/*`],
        conditions: {
          StringEquals: {
            "aws:SourceAccount": this.account,
          },
        },
      })
    );

    dataBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("bedrock.amazonaws.com")],
        actions: ["s3:ListBucket"],
        resources: [dataBucket.bucketArn],
        conditions: {
          StringEquals: {
            "aws:SourceAccount": this.account,
          },
        },
      })
    );

    // ========================================
    // VPC for Neptune
    // ========================================
    const vpc = new ec2.Vpc(this, "NeptuneVPC", {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
        {
          cidrMask: 28,
          name: "Isolated",
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    // Security Group for Neptune
    const neptuneSecurityGroup = new ec2.SecurityGroup(
      this,
      "NeptuneSecurityGroup",
      {
        vpc,
        description: "Security group for Neptune cluster",
        allowAllOutbound: true,
      }
    );

    neptuneSecurityGroup.addIngressRule(
      neptuneSecurityGroup,
      ec2.Port.tcp(8182),
      "Allow Neptune access from within security group"
    );

    // ========================================
    // ECS Cluster for Fargate Tasks
    // ========================================
    const ecsCluster = new ecs.Cluster(this, "ECSCluster", {
      clusterName: `${projectName}-cluster`,
      vpc,
      containerInsights: true,
    });

    // ECR Repository for Fargate task image
    const collectorRepository = new ecr.Repository(this, "CollectorRepository", {
      repositoryName: `${projectName}-collector`,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          maxImageCount: 5,
          description: "Keep only 5 most recent images",
        },
      ],
    });

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
      image: ecs.ContainerImage.fromEcrRepository(collectorRepository, "latest"),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: "collector",
        logGroup: collectorLogGroup,
      }),
      environment: {
        BUCKET_NAME: dataBucket.bucketName,
        START_CONGRESS: "1",
        END_CONGRESS: "16",
        BILL_TYPES: "hr,s",
        CONGRESS_API_KEY: "MThtRT5WkFu8I8CHOfiLLebG4nsnKcX3JnNv2N8A",
      },
    });

    // ========================================
    // Neptune Cluster
    // ========================================
    const neptuneSubnetGroup = new neptune.CfnDBSubnetGroup(
      this,
      "NeptuneSubnetGroup",
      {
        dbSubnetGroupDescription: "Subnet group for Neptune cluster",
        subnetIds: vpc.isolatedSubnets.map((subnet) => subnet.subnetId),
        dbSubnetGroupName: `${projectName}-neptune-subnet-group`,
      }
    );

    const neptuneCluster = new neptune.CfnDBCluster(this, "NeptuneCluster", {
      dbClusterIdentifier: `${projectName}-neptune-cluster`,
      dbSubnetGroupName: neptuneSubnetGroup.dbSubnetGroupName,
      vpcSecurityGroupIds: [neptuneSecurityGroup.securityGroupId],
      iamAuthEnabled: false,
      storageEncrypted: true,
    });

    neptuneCluster.addDependency(neptuneSubnetGroup);

    const neptuneInstance = new neptune.CfnDBInstance(this, "NeptuneInstance", {
      dbInstanceClass: "db.t3.medium",
      dbClusterIdentifier: neptuneCluster.dbClusterIdentifier,
      dbInstanceIdentifier: `${projectName}-neptune-instance`,
    });

    neptuneInstance.addDependency(neptuneCluster);

    // ========================================
    // Bedrock Knowledge Base - SEMI-AUTOMATED
    // ========================================
    // Note: OpenSearch Serverless setup via CDK has validation issues.
    // The pipeline will automatically export documents to S3 in KB-ready format.
    // You can create the Knowledge Base manually in AWS Console (5 minutes).
    // See README.md for instructions.

    // Placeholder values for KB (will be set after manual creation or via env vars)
    const knowledgeBaseId = process.env.KNOWLEDGE_BASE_ID || "";
    const dataSourceId = process.env.DATA_SOURCE_ID || "";

    // ========================================
    // Lambda Execution Role
    // ========================================
    const lambdaRole = new iam.Role(this, "LambdaExecutionRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaVPCAccessExecutionRole"
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    // Grant S3 permissions
    dataBucket.grantReadWrite(lambdaRole);

    // Grant IAM PassRole permission for Bedrock Data Automation
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: [lambdaRole.roleArn],
        conditions: {
          StringEquals: {
            "iam:PassedToService": "bedrock.amazonaws.com",
          },
        },
      })
    );

    // Grant Bedrock permissions
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/*`,
          `arn:aws:bedrock:*::foundation-model/*`,
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      })
    );

    // Grant AWS Marketplace permissions for Bedrock Marketplace models
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe",
        ],
        resources: ["*"],
      })
    );

    // Grant Neptune permissions
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["neptune-db:*"],
        resources: ["*"],
      })
    );

    // ========================================
    // Lambda Functions (Docker-based)
    // ========================================

    // 0. Fargate Trigger Lambda (triggers Fargate task for bill collection)
    const fargateTriggerLogGroup = new logs.LogGroup(
      this,
      "FargateTriggerLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-fargate-trigger`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const fargateTriggerFunction = new lambda.DockerImageFunction(
      this,
      "FargateTriggerFunction",
      {
        functionName: `${projectName}-fargate-trigger`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/fargate-trigger")
        ),
        timeout: cdk.Duration.seconds(30),
        memorySize: 256,
        role: lambdaRole,
        environment: {
          ECS_CLUSTER_NAME: ecsCluster.clusterName,
          TASK_DEFINITION_ARN: collectorTaskDefinition.taskDefinitionArn,
          SUBNET_IDS: vpc.publicSubnets.map((s) => s.subnetId).join(","),
          SECURITY_GROUP_ID: neptuneSecurityGroup.securityGroupId,
          BUCKET_NAME: dataBucket.bucketName,
          START_CONGRESS: "1",
          END_CONGRESS: "16",
          BILL_TYPES: "hr,s",
        },
        logGroup: fargateTriggerLogGroup,
      }
    );

    // Grant ECS permissions to Lambda
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "ecs:RunTask",
          "ecs:DescribeTasks",
          "ecs:StopTask",
        ],
        resources: ["*"],
      })
    );

    // Grant PassRole for ECS task execution
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: [
          fargateExecutionRole.roleArn,
          fargateTaskRole.roleArn,
        ],
      })
    );

    // 1. Image Collector Lambda
    const imageCollectorLogGroup = new logs.LogGroup(
      this,
      "ImageCollectorLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-image-collector`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const imageCollectorFunction = new lambda.DockerImageFunction(
      this,
      "ImageCollectorFunction",
      {
        functionName: `${projectName}-image-collector`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/image-collector")
        ),
        timeout: cdk.Duration.minutes(15),
        memorySize: 1024,
        role: lambdaRole,
        environment: {
          DATA_BUCKET: dataBucket.bucketName,
          CONGRESS_API_KEY: "MThtRT5WkFu8I8CHOfiLLebG4nsnKcX3JnNv2N8A",
        },
        logGroup: imageCollectorLogGroup,
      }
    );

    // 2. Image to PDF Lambda
    const imageToPdfLogGroup = new logs.LogGroup(this, "ImageToPdfLogGroup", {
      logGroupName: `/aws/lambda/${projectName}-image-to-pdf`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const imageToPdfFunction = new lambda.DockerImageFunction(
      this,
      "ImageToPdfFunction",
      {
        functionName: `${projectName}-image-to-pdf`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/image-to-pdf")
        ),
        timeout: cdk.Duration.minutes(15),
        memorySize: 3008,
        role: lambdaRole,
        environment: {
          DATA_BUCKET: dataBucket.bucketName,
        },
        logGroup: imageToPdfLogGroup,
      }
    );

    // 3. Bedrock Data Automation Lambda
    const bedrockDataAutomationLogGroup = new logs.LogGroup(
      this,
      "BedrockDataAutomationLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-bedrock-data-automation`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const bedrockDataAutomationFunction = new lambda.DockerImageFunction(
      this,
      "BedrockDataAutomationFunction",
      {
        functionName: `${projectName}-bedrock-data-automation`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/bedrock-data-automation")
        ),
        timeout: cdk.Duration.minutes(15),
        memorySize: 2048,
        role: lambdaRole,
        environment: {
          DATA_BUCKET: dataBucket.bucketName,
          AWS_ACCOUNT_ID: this.account,
          BEDROCK_REGION: this.region,
          LOG_LEVEL: "INFO",
          BEDROCK_PROJECT_NAME: `${projectName}-extraction`,
          BEDROCK_PROFILE_ARN: `arn:aws:bedrock:${this.region}:${this.account}:data-automation-profile/us.data-automation-v1`,
        },
        logGroup: bedrockDataAutomationLogGroup,
      }
    );

    // Grant Bedrock Data Automation permissions
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:ListDataAutomationProjects",
          "bedrock:CreateDataAutomationProject",
          "bedrock:GetDataAutomationProject",
          "bedrock:UpdateDataAutomationProject",
          "bedrock:DeleteDataAutomationProject",
          "bedrock:CreateBlueprint",
          "bedrock:GetBlueprint",
          "bedrock:ListBlueprints",
        ],
        resources: ["*"],
      })
    );

    // Grant Bedrock Data Automation Runtime permissions
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock-data-automation-runtime:*"],
        resources: ["*"],
      })
    );

    // Grant permission to use Bedrock Data Automation Profiles and Projects
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeDataAutomationAsync",
          "bedrock:GetDataAutomationStatus",
          "bedrock:GetDataAutomationProfile",
          "bedrock:ListDataAutomationProfiles",
        ],
        resources: ["*"],
      })
    );

    // Grant Bedrock model invocation permissions (required by Data Automation)
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/*`,
          `arn:aws:bedrock:*::foundation-model/*`,
        ],
      })
    );

    // 4. Data Extractor Lambda (kept for compatibility)
    const dataExtractorLogGroup = new logs.LogGroup(
      this,
      "DataExtractorLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-data-extractor`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const dataExtractorFunction = new lambda.DockerImageFunction(
      this,
      "DataExtractorFunction",
      {
        functionName: `${projectName}-data-extractor`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/data-extractor")
        ),
        timeout: cdk.Duration.minutes(15),
        memorySize: 2048,
        role: lambdaRole,
        environment: {
          DATA_BUCKET: dataBucket.bucketName,
          BEDROCK_MODEL_ID: bedrockModelId,
        },
        logGroup: dataExtractorLogGroup,
      }
    );

    // Entity Extractor Lambda - REMOVED
    // Bedrock Knowledge Base will automatically extract entities from documents in Neptune
    // No need for separate entity extraction Lambda

    // 4. Neptune Loader Lambda
    const neptuneLoaderLogGroup = new logs.LogGroup(
      this,
      "NeptuneLoaderLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-neptune-loader`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const neptuneLoaderFunction = new lambda.DockerImageFunction(
      this,
      "NeptuneLoaderFunction",
      {
        functionName: `${projectName}-neptune-loader`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/neptune-loader")
        ),
        timeout: cdk.Duration.minutes(15),
        memorySize: 1024,
        role: lambdaRole,
        vpc,
        vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        securityGroups: [neptuneSecurityGroup],
        environment: {
          DATA_BUCKET: dataBucket.bucketName,
          NEPTUNE_ENDPOINT: neptuneCluster.attrEndpoint,
          NEPTUNE_PORT: "8182",
        },
        logGroup: neptuneLoaderLogGroup,
      }
    );

    // 5. Chat Handler Lambda
    const chatHandlerLogGroup = new logs.LogGroup(this, "ChatHandlerLogGroup", {
      logGroupName: `/aws/lambda/${projectName}-chat-handler`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const chatHandlerFunction = new lambda.DockerImageFunction(
      this,
      "ChatHandlerFunction",
      {
        functionName: `${projectName}-chat-handler`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/chat-handler")
        ),
        timeout: cdk.Duration.seconds(30),
        memorySize: 1024,
        role: lambdaRole,
        vpc,
        vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        securityGroups: [neptuneSecurityGroup],
        environment: {
          NEPTUNE_ENDPOINT: neptuneCluster.attrEndpoint,
          NEPTUNE_PORT: "8182",
          BEDROCK_MODEL_ID: bedrockModelId,
          KNOWLEDGE_BASE_ID: knowledgeBaseId, // Now uses actual KB ID
        },
        logGroup: chatHandlerLogGroup,
      }
    );

    // Grant Bedrock Agent Runtime permissions for Knowledge Base
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:Retrieve", "bedrock:RetrieveAndGenerate"],
        resources: ["*"],
      })
    );

    // ========================================
    // Neptune Exporter Lambda
    // ========================================
    const neptuneExporterLogGroup = new logs.LogGroup(
      this,
      "NeptuneExporterLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-neptune-exporter`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const neptuneExporterFunction = new lambda.DockerImageFunction(
      this,
      "NeptuneExporterFunction",
      {
        functionName: `${projectName}-neptune-exporter`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/neptune-exporter")
        ),
        timeout: cdk.Duration.minutes(15),
        memorySize: 1024,
        role: lambdaRole,
        vpc,
        vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        securityGroups: [neptuneSecurityGroup],
        environment: {
          DATA_BUCKET: dataBucket.bucketName,
          NEPTUNE_ENDPOINT: neptuneCluster.attrEndpoint,
          NEPTUNE_PORT: "8182",
        },
        logGroup: neptuneExporterLogGroup,
      }
    );

    // ========================================
    // KB Sync Trigger Lambda
    // ========================================
    const kbSyncTriggerLogGroup = new logs.LogGroup(
      this,
      "KBSyncTriggerLogGroup",
      {
        logGroupName: `/aws/lambda/${projectName}-kb-sync-trigger`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }
    );

    const kbSyncTriggerFunction = new lambda.DockerImageFunction(
      this,
      "KBSyncTriggerFunction",
      {
        functionName: `${projectName}-kb-sync-trigger`,
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "../lambda/kb-sync-trigger")
        ),
        timeout: cdk.Duration.minutes(2),
        memorySize: 256,
        role: lambdaRole,
        environment: {
          KNOWLEDGE_BASE_ID: knowledgeBaseId, // Now uses actual KB ID
          DATA_SOURCE_ID: dataSourceId, // Now uses actual Data Source ID
        },
        logGroup: kbSyncTriggerLogGroup,
      }
    );

    // Grant permissions to start ingestion jobs (for any KB)
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

    // ========================================
    // Step Functions State Machine
    // ========================================

    // Define tasks
    // Use Fargate task for data collection (no timeout limit)
    const collectBillsTask = new tasks.EcsRunTask(this, "CollectBills", {
      integrationPattern: stepfunctions.IntegrationPattern.RUN_JOB,
      cluster: ecsCluster,
      taskDefinition: collectorTaskDefinition,
      launchTarget: new tasks.EcsFargateLaunchTarget({
        platformVersion: ecs.FargatePlatformVersion.LATEST,
      }),
      containerOverrides: [
        {
          containerDefinition: collectorTaskDefinition.defaultContainer!,
          environment: [
            {
              name: "BUCKET_NAME",
              value: dataBucket.bucketName,
            },
          ],
        },
      ],
      assignPublicIp: true,
      subnets: { subnetType: ec2.SubnetType.PUBLIC },
      resultPath: "$.fargateResult",
    });

    const imageToPdfTask = new tasks.LambdaInvoke(this, "ImageToPdf", {
      lambdaFunction: imageToPdfFunction,
      outputPath: "$.Payload",
    });

    const bedrockDataAutomationTask = new tasks.LambdaInvoke(
      this,
      "BedrockDataAutomation",
      {
        lambdaFunction: bedrockDataAutomationFunction,
        outputPath: "$.Payload",
        retryOnServiceExceptions: true,
      }
    ).addCatch(
      new stepfunctions.Fail(this, "ExtractionFailed", {
        cause: "Text extraction failed",
        error: "ExtractionError",
      }),
      {
        errors: ["States.ALL"],
        resultPath: "$.error",
      }
    );

    const dataExtractorTask = new tasks.LambdaInvoke(this, "DataExtractor", {
      lambdaFunction: dataExtractorFunction,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    }).addCatch(
      new stepfunctions.Fail(this, "DataExtractionFailed", {
        cause: "Data extraction failed",
        error: "DataExtractionError",
      }),
      {
        errors: ["States.ALL"],
        resultPath: "$.error",
      }
    );

    const loadToNeptuneTask = new tasks.LambdaInvoke(this, "LoadToNeptune", {
      lambdaFunction: neptuneLoaderFunction,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    }).addCatch(
      new stepfunctions.Fail(this, "NeptuneLoadFailed", {
        cause: "Failed to load documents to Neptune",
        error: "NeptuneLoadError",
      }),
      {
        errors: ["States.ALL"],
        resultPath: "$.error",
      }
    );

    const exportToS3Task = new tasks.LambdaInvoke(this, "ExportToS3", {
      lambdaFunction: neptuneExporterFunction,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    }).addCatch(
      new stepfunctions.Fail(this, "ExportFailed", {
        cause: "Failed to export documents to S3",
        error: "ExportError",
      }),
      {
        errors: ["States.ALL"],
        resultPath: "$.error",
      }
    );

    const syncKBTask = new tasks.LambdaInvoke(this, "SyncKnowledgeBase", {
      lambdaFunction: kbSyncTriggerFunction,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    }).addCatch(
      // Don't fail the whole pipeline if KB sync fails (KB might not be set up yet)
      new stepfunctions.Succeed(this, "KBSyncSkipped", {
        comment: "KB sync failed - KB may not be configured yet",
      }),
      {
        errors: ["States.ALL"],
        resultPath: "$.error",
      }
    );

    // Simplified Pipeline: Fargate collects & extracts → KB Sync
    // Fargate task handles: API calls, text extraction, S3 storage
    // Bedrock KB handles: Entity extraction, Neptune storage (automatic)
    const definition = collectBillsTask.next(syncKBTask);

    const stateMachine = new stepfunctions.StateMachine(
      this,
      "PipelineStateMachine",
      {
        stateMachineName: `${projectName}-pipeline`,
        definitionBody: stepfunctions.DefinitionBody.fromChainable(definition),
        timeout: cdk.Duration.hours(2),
        logs: {
          destination: new logs.LogGroup(this, "StateMachineLogGroup", {
            logGroupName: `/aws/stepfunctions/${projectName}-pipeline`,
            retention: logs.RetentionDays.ONE_WEEK,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
          }),
          level: stepfunctions.LogLevel.ALL,
        },
      }
    );

    // ========================================
    // API Gateway for Chat UI
    // ========================================
    const api = new apigateway.RestApi(this, "ChatAPI", {
      restApiName: `${projectName}-chat-api`,
      description: "API for historical newspaper chat interface",
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ["Content-Type", "Authorization"],
      },
    });

    const chatIntegration = new apigateway.LambdaIntegration(
      chatHandlerFunction
    );
    const chatResource = api.root.addResource("chat");
    chatResource.addMethod("POST", chatIntegration);

    const healthResource = api.root.addResource("health");
    healthResource.addMethod("GET", chatIntegration);

    // Fargate trigger endpoint
    const collectIntegration = new apigateway.LambdaIntegration(
      fargateTriggerFunction
    );
    const collectResource = api.root.addResource("collect");
    collectResource.addMethod("POST", collectIntegration);

    // ========================================
    // Outputs
    // ========================================
    new cdk.CfnOutput(this, "DataBucketName", {
      value: dataBucket.bucketName,
      description: "S3 bucket for pipeline data",
      exportName: `${projectName}-data-bucket`,
    });

    new cdk.CfnOutput(this, "StateMachineArn", {
      value: stateMachine.stateMachineArn,
      description: "Step Functions state machine ARN",
      exportName: `${projectName}-state-machine-arn`,
    });

    new cdk.CfnOutput(this, "NeptuneEndpoint", {
      value: neptuneCluster.attrEndpoint,
      description: "Neptune cluster endpoint",
      exportName: `${projectName}-neptune-endpoint`,
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

    new cdk.CfnOutput(this, "KBDocumentsPrefix", {
      value: `s3://${dataBucket.bucketName}/kb-documents/`,
      description:
        "S3 prefix where KB documents are exported (ready for manual KB setup)",
    });

    new cdk.CfnOutput(this, "KnowledgeBaseSetup", {
      value: "MANUAL_SETUP_REQUIRED",
      description:
        "Create KB in AWS Console, then set KNOWLEDGE_BASE_ID and DATA_SOURCE_ID env vars",
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

    // ========================================
    // Auto-Start Pipeline After Deployment (Optional)
    // ========================================
    // Uncomment to automatically trigger pipeline after each deployment

    //   const autoStartPipeline = new cr.AwsCustomResource(
    //     this,
    //     "AutoStartPipeline",
    //     {
    //       onCreate: {
    //         service: "StepFunctions",
    //         action: "startExecution",
    //         parameters: {
    //           stateMachineArn: stateMachine.stateMachineArn,
    //           input: JSON.stringify({
    //             start_date: "1815-08-01",
    //             end_date: "1820-08-31",
    //             max_pages: 30,
    //           }),
    //         },
    //         physicalResourceId: cr.PhysicalResourceId.of(Date.now().toString()),
    //       },
    //       policy: cr.AwsCustomResourcePolicy.fromStatements([
    //         new iam.PolicyStatement({
    //           actions: ["states:StartExecution"],
    //           resources: [stateMachine.stateMachineArn],
    //         }),
    //       ]),
    //     }
    //   );
  }
}
