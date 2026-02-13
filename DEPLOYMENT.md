# Deployment Guide - Cultural Heritage Chatbot

This guide provides step-by-step instructions for deploying the Cultural Heritage Chatbot to AWS using CloudShell, CodeBuild, and the deploy.sh script.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Deployment Methods](#deployment-methods)
- [Method 1: AWS CloudShell Deployment](#method-1-aws-cloudshell-deployment)
- [Method 2: Local Deployment with deploy.sh](#method-2-local-deployment-with-deploysh)
- [Method 3: AWS CodeBuild Deployment](#method-3-aws-codebuild-deployment)
- [Post-Deployment Steps](#post-deployment-steps)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### AWS Account Requirements
- AWS Account with appropriate permissions
- AWS CLI configured with credentials
- Required IAM permissions:
  - CloudFormation
  - Lambda
  - API Gateway
  - Bedrock
  - Neptune
  - S3
  - OpenSearch
  - IAM role creation

### Software Requirements
- **Node.js** 18+ and npm
- **Python** 3.9+
- **AWS CDK** 2.x (`npm install -g aws-cdk`)
- **Git**

### AWS Services to Enable
1. AWS Bedrock (ensure your region supports Bedrock)
2. Amazon Neptune
3. Amazon OpenSearch Service

---

## Deployment Methods

There are three primary methods to deploy the Cultural Heritage Chatbot:

1. **AWS CloudShell** - Easiest, no local setup required
2. **Local Deployment** - Using deploy.sh script
3. **AWS CodeBuild** - Automated CI/CD pipeline

---

## Method 1: AWS CloudShell Deployment

AWS CloudShell provides a browser-based shell with AWS CLI pre-installed.

### Step 1: Open AWS CloudShell

1. Log in to the AWS Management Console
2. Click the CloudShell icon (terminal icon) in the top navigation bar
3. Wait for the CloudShell environment to initialize

### Step 2: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/ASUCICREPO/Loc_Project.git
cd Loc_Project
```

### Step 3: Set Up Backend

```bash
# Navigate to backend directory
cd backend

# Install Node.js dependencies
npm install

# Bootstrap CDK (first-time setup only)
cdk bootstrap

# Create Bedrock Agent Memory
npm run setup-memory
```

### Step 4: Configure Environment

Edit the `backend/cdk.json` file to set your configuration:

```bash
# Use CloudShell's built-in text editor
nano cdk.json
```

Update the following values:
- AWS Account ID
- AWS Region
- Bedrock Agent configuration
- Neptune cluster settings

### Step 5: Deploy Backend Infrastructure

```bash
# Deploy all CDK stacks
npm run deploy

# Or deploy specific stacks
cdk deploy --all
```

**Note**: The deployment process will:
- Create S3 buckets for document storage
- Set up Neptune graph database
- Deploy Lambda functions
- Configure API Gateway
- Set up Bedrock Agent with Knowledge Base
- Create OpenSearch domain

### Step 6: Note the API Endpoint

After deployment completes, note the API Gateway endpoint URL from the output:
```
Outputs:
LocProjectStack.ApiEndpoint = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
```

### Step 7: Deploy Frontend

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Create environment file
cat > .env.local << EOF
NEXT_PUBLIC_API_BASE_URL=https://your-api-gateway-url.amazonaws.com
NEXT_PUBLIC_CHAT_ENDPOINT=https://your-api-gateway-url.amazonaws.com/chat
EOF

# Build the frontend
npm run build

# Export static files (if deploying to S3)
npm run export
```

### Step 8: Deploy Frontend to S3 (Optional)

```bash
# Create S3 bucket for frontend hosting
aws s3 mb s3://cultural-heritage-chatbot-frontend

# Enable static website hosting
aws s3 website s3://cultural-heritage-chatbot-frontend --index-document index.html

# Upload build files
aws s3 sync out/ s3://cultural-heritage-chatbot-frontend --acl public-read

# Set bucket policy for public access
aws s3api put-bucket-policy --bucket cultural-heritage-chatbot-frontend --policy file://bucket-policy.json
```

---

## Method 2: Local Deployment with deploy.sh

The `deploy.sh` script automates the deployment process.

### Step 1: Prepare Your Environment

```bash
# Clone the repository
git clone https://github.com/ASUCICREPO/Loc_Project.git
cd Loc_Project

# Ensure AWS CLI is configured
aws configure
```

### Step 2: Make deploy.sh Executable

```bash
cd backend
chmod +x deploy.sh
```

### Step 3: Review and Update Configuration

Open `deploy.sh` and verify the configuration:

```bash
#!/bin/bash

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="123456789012"
STACK_NAME="LocProjectStack"

# Your deployment logic here
```

### Step 4: Run the Deployment Script

```bash
# Run with default settings
./deploy.sh

# Or with custom parameters
./deploy.sh --region us-west-2 --environment production
```

### Step 5: Monitor Deployment Progress

The script will:
1. Install dependencies
2. Bootstrap CDK (if needed)
3. Create Bedrock Agent memory
4. Deploy CDK stacks
5. Output deployment information

### Step 6: Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name LocProjectStack

# Test API endpoint
curl https://your-api-gateway-url.amazonaws.com/health
```

---

## Method 3: AWS CodeBuild Deployment

Use CodeBuild for automated CI/CD deployments.

### Step 1: Set Up CodeBuild Project

1. Go to AWS CodeBuild in the AWS Console
2. Click **Create build project**
3. Configure the project:
   - **Project name**: `cultural-heritage-chatbot-build`
   - **Source**: GitHub (connect your repository)
   - **Environment**:
     - **Operating system**: Ubuntu
     - **Runtime**: Standard
     - **Image**: `aws/codebuild/standard:7.0`
   - **Buildspec**: Use `buildspec.yml` from the repository

### Step 2: Review buildspec.yml

The `backend/buildspec.yml` file contains the build instructions:

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 18
      python: 3.9
    commands:
      - npm install -g aws-cdk
      - cd backend && npm install
      - pip install -r requirements.txt

  pre_build:
    commands:
      - echo "Setting up Bedrock Agent Memory..."
      - npm run setup-memory

  build:
    commands:
      - echo "Deploying CDK stacks..."
      - cdk deploy --all --require-approval never

  post_build:
    commands:
      - echo "Deployment completed"
      - aws cloudformation describe-stacks --stack-name LocProjectStack

artifacts:
  files:
    - '**/*'
```

### Step 3: Configure Environment Variables

In CodeBuild project settings, add environment variables:
- `AWS_DEFAULT_REGION`: Your AWS region
- `AWS_ACCOUNT_ID`: Your AWS account ID

### Step 4: Set Up Service Role

Ensure the CodeBuild service role has permissions for:
- CloudFormation
- Lambda
- API Gateway
- Bedrock
- Neptune
- S3
- OpenSearch
- IAM

### Step 5: Start Build

```bash
# Using AWS CLI
aws codebuild start-build --project-name cultural-heritage-chatbot-build

# Or click "Start build" in the AWS Console
```

### Step 6: Monitor Build Progress

View build logs in real-time:
1. Go to CodeBuild console
2. Select your build project
3. Click on the running build
4. View the **Build logs** tab

---

## Post-Deployment Steps

### 1. Verify Backend Deployment

```bash
# Check all stacks are deployed
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# Test API Gateway endpoint
curl https://your-api-gateway-url.amazonaws.com/health
```

### 2. Load Historical Data

```bash
# Navigate to backend scripts
cd backend/scripts

# Run data ingestion script
python ingest_historical_data.py
```

### 3. Configure Bedrock Agent

1. Go to Amazon Bedrock console
2. Navigate to **Agents**
3. Verify your agent is created
4. Test the agent with sample queries

### 4. Set Up Monitoring

```bash
# Enable CloudWatch logs
aws logs create-log-group --log-group-name /aws/lambda/cultural-heritage-chatbot

# Set up alarms
aws cloudwatch put-metric-alarm \
  --alarm-name high-error-rate \
  --alarm-description "Alert when error rate is high" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

### 5. Update Frontend Environment

Update frontend `.env.local` with the deployed API endpoint:

```bash
NEXT_PUBLIC_API_BASE_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
NEXT_PUBLIC_CHAT_ENDPOINT=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/chat
```

### 6. Test the Application

1. Navigate to your frontend URL
2. Select a persona
3. Ask a test question: "What is the First Amendment?"
4. Verify the response includes source citations

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: CDK Bootstrap Failed

**Error**: "CDK needs to be bootstrapped"

**Solution**:
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

#### Issue 2: Bedrock Not Available

**Error**: "Bedrock service not available in region"

**Solution**:
- Bedrock is only available in certain regions (us-east-1, us-west-2)
- Update your region in `cdk.json`
- Redeploy with supported region

#### Issue 3: Neptune Cluster Creation Failed

**Error**: "Neptune cluster creation timeout"

**Solution**:
- Neptune can take 10-15 minutes to create
- Check CloudFormation events for specific errors
- Ensure your VPC has proper subnet configuration

#### Issue 4: Lambda Function Timeout

**Error**: "Task timed out after 3.00 seconds"

**Solution**:
```bash
# Increase Lambda timeout in CDK stack
timeout: Duration.seconds(30)
```

#### Issue 5: API Gateway CORS Errors

**Error**: "No 'Access-Control-Allow-Origin' header"

**Solution**:
- Update Lambda response to include CORS headers
- Check API Gateway CORS configuration

#### Issue 6: Out of Memory Error

**Error**: "JavaScript heap out of memory"

**Solution**:
```bash
# Increase Node.js memory
export NODE_OPTIONS="--max-old-space-size=4096"
npm run deploy
```

### Rollback Deployment

If deployment fails or you need to rollback:

```bash
# Delete all stacks
cdk destroy --all

# Or delete specific stack
aws cloudformation delete-stack --stack-name LocProjectStack

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete --stack-name LocProjectStack
```

### Check CloudFormation Events

```bash
# View stack events
aws cloudformation describe-stack-events --stack-name LocProjectStack

# Filter for failed events
aws cloudformation describe-stack-events --stack-name LocProjectStack \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

### View Lambda Logs

```bash
# Get latest log stream
aws logs tail /aws/lambda/cultural-heritage-chatbot-handler --follow

# View specific log group
aws logs describe-log-streams --log-group-name /aws/lambda/cultural-heritage-chatbot-handler
```

---

## Clean Up Resources

To remove all deployed resources:

```bash
# Method 1: Using CDK
cd backend
cdk destroy --all

# Method 2: Using CloudFormation
aws cloudformation delete-stack --stack-name LocProjectStack

# Method 3: Manual cleanup
# Delete S3 buckets (empty them first)
aws s3 rm s3://your-bucket-name --recursive
aws s3 rb s3://your-bucket-name

# Delete CloudWatch log groups
aws logs delete-log-group --log-group-name /aws/lambda/cultural-heritage-chatbot
```

---

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS CloudShell User Guide](https://docs.aws.amazon.com/cloudshell/)
- [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)

---

## Support

For deployment issues:
1. Check CloudFormation events for detailed error messages
2. Review CloudWatch logs for Lambda functions
3. Consult the project README for configuration details
4. Open an issue on GitHub: [https://github.com/ASUCICREPO/Loc_Project/issues](https://github.com/ASUCICREPO/Loc_Project/issues)

---

**Last Updated**: February 2026
**Version**: 1.0.0
