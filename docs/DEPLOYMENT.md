# Deployment Guide

Complete step-by-step guide to deploy the Cultural Heritage Chatbot using AWS CloudShell.

## Table of Contents

1. [Overview](#overview)
2. [Deployment Steps](#deployment-steps)
3. [Parameter Reference](#parameter-reference)
4. [Monitoring Deployment](#monitoring-deployment)
5. [Accessing Your Application](#accessing-your-application)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Troubleshooting](#troubleshooting)
8. [Cleanup / Destroy](#cleanup--destroy)

---

## Overview

### What Gets Deployed

The deployment script automatically provisions:

- **Frontend**: Next.js application on AWS Amplify
- **Backend**: Lambda functions, API Gateway, ECS Fargate
- **AI/ML**: Bedrock Knowledge Base with Neptune Analytics (GraphRAG)
- **Storage**: S3 buckets for documents and builds
- **Networking**: VPC with public subnets

### Deployment Time

- **Total time**: 10-15 minutes
- **CDK deployment**: 5-10 minutes
- **Frontend build**: 1-2 minutes
- **Data collection**: Starts automatically after deployment

---

## Deployment Steps

### Step 1: Open AWS CloudShell

1. Log in to the [AWS Management Console](https://console.aws.amazon.com)

2. Click the **CloudShell** icon in the top navigation bar (terminal icon)

3. Wait for the CloudShell environment to initialize

4. You should see a terminal prompt like:
   ```
   [cloudshell-user@ip-10-0-0-1 ~]$
   ```

### Step 2: Clone the Repository

Copy and paste the following commands:

```bash
# Clone the repository
git clone https://github.com/ASUCICREPO/Loc_Project.git

# Navigate to the backend directory
cd Loc_Project/backend
```

**Expected output:**
```
Cloning into 'Loc_Project'...
remote: Enumerating objects: 500, done.
remote: Counting objects: 100% (500/500), done.
...
```

### Step 3: Make Deploy Script Executable

```bash
chmod +x ./deploy.sh
```

### Step 4: Run the Deployment Script

```bash
./deploy.sh
```

### Step 5: Enter Deployment Parameters

The script will prompt you for the following parameters:

#### 5.1 GitHub Repository URL

```
Enter GitHub repository URL:
```

Enter the URL of your repository (or the original):
```
https://github.com/ASUCICREPO/Loc_Project.git
```

#### 5.2 Project Name

```
Enter project name [default: loc]:
```
Press **Enter** to use default `loc`, or enter a custom name:

**Note**: Project name is used as a prefix for all AWS resources.

#### 5.3 AWS Region

**Recommended regions**: `us-west-2` or `us-east-1` (best Bedrock support)

#### 5.4 Data Bucket Name

```
Enter data bucket name [default: loc-data-123456789012-us-west-2]:
```

Press **Enter** to use the auto-generated default name.

#### 5.5 Bedrock Model ID

```
Enter Bedrock model ID [default: global.anthropic.claude-sonnet-4-5-20250929-v1:0]:
```

Press **Enter** to use Claude 4.5 Sonnet (recommended).

#### 5.6 Congress.gov API Key

```
Enter Congress.gov API key (get one at https://api.congress.gov/sign-up):
```

**Important**: This is required. See [Prerequisites Guide](PREREQUISITES.md) for how to obtain one.

#### 5.7 Action

```
Enter action [deploy/destroy]:
```

Enter:
```
deploy
```

### Step 6: Wait for Deployment

After entering all parameters, the script will:

1. ✅ Create IAM role for CodeBuild
2. ✅ Create CodeBuild project
3. ✅ Start the build

You'll see output like:
```
=========================================
loc Pipeline Deployment
=========================================

Checking for IAM role: loc-codebuild-role
✓ IAM role exists
Creating CodeBuild project: loc-deploy
✓ CodeBuild project created
Starting deployment...
✓ Build started with ID: loc-deploy:abc123

Monitor build progress:
https://console.aws.amazon.com/codesuite/codebuild/projects/loc-deploy/build/loc-deploy:abc123
```

---

## Parameter Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| GitHub URL | (required) | Repository URL to clone |
| Project Name | `loc` | Prefix for all AWS resources |
| AWS Region | `us-west-2` | Deployment region |
| Data Bucket | `{project}-data-{account}-{region}` | S3 bucket for documents |
| Bedrock Model | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` | LLM for chat |
| Congress API Key | (required) | For data collection |
| Action | (required) | `deploy` or `destroy` |

---

## Monitoring Deployment

### Option 1: AWS Console (Recommended)

1. Click the CodeBuild URL shown in the terminal output

2. Or navigate manually:
   - Go to **AWS Console** → **CodeBuild**
   - Find project: `{project-name}-deploy`
   - Click on the running build

3. View the **Build logs** tab for real-time progress

### Option 2: CloudShell Commands

```bash
# List recent builds
aws codebuild list-builds-for-project --project-name loc-deploy

# Get build details
aws codebuild batch-get-builds --ids loc-deploy:abc123
```

### Build Phases

The CodeBuild process goes through these phases:

| Phase | Duration | Description |
|-------|----------|-------------|
| INSTALL | 2-3 min | Install Node.js, CDK, dependencies |
| PRE_BUILD | 3-5 min | Build TypeScript, create AgentCore Memory |
| BUILD | 5-10 min | CDK deploy, Docker build, Amplify deploy |
| POST_BUILD | 1 min | Output summary |

**Key outputs to note:**
```
Frontend URL: https://main.d25i518d1urtex.amplifyapp.com
API URL: https://abc123.execute-api.us-west-2.amazonaws.com/prod/
Knowledge Base ID: LUA1WTHEIU
```

---

## Accessing Your Application

### Frontend URL

After deployment completes, your application is available at:

```
https://main.{app-id}.amplifyapp.com
```

The exact URL is shown in the CodeBuild output.

## Post-Deployment Verification

### 1. Check CloudFormation Stack

```bash
aws cloudformation describe-stacks --stack-name LOCstack --query 'Stacks[0].StackStatus'
```

Expected: `"CREATE_COMPLETE"`

### 2. Check Data Collection

Data collection starts automatically. Monitor progress:

```bash
# View Fargate task logs
aws logs tail /ecs/{ProjectName}-collector --follow
```

### 3. Check S3 Data

```bash
# List collected bills
aws s3 ls s3://{ProjectName}-data-{account}-{region}/bills/ --recursive | head -20

# List collected newspapers
aws s3 ls s3://{ProjectName}-data-{account}-{region}/newspapers/ --recursive | head -20
```

### 4. Check Knowledge Base

```bash
# Get KB status
aws bedrock-agent get-knowledge-base --knowledge-base-id {kb-id}
```
---

## Troubleshooting

### Build Fails in INSTALL Phase

**Symptom**: Error installing dependencies

**Solution**:
```bash
# Check if npm/node are available
node --version
npm --version

# Clear CloudShell cache and retry
rm -rf ~/Loc_Project
# Re-clone and deploy
```

### Build Fails in PRE_BUILD Phase

**Symptom**: TypeScript compilation errors

**Solution**:
```bash
# Check for syntax errors in CDK code
cd backend
npm run build
```

### Build Fails in BUILD Phase

**Symptom**: CDK deployment fails

**Common causes**:
1. **Bedrock access not enabled**: Enable model access in Bedrock console
2. **Region not supported**: Use us-west-2 or us-east-1
3. **Permission denied**: Ensure IAM has required permissions

**Check CloudFormation events**:
```bash
aws cloudformation describe-stack-events --stack-name LOCstack --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

### Fargate Task Fails

**Symptom**: Data collection doesn't complete

**Check logs**:
```bash
aws logs tail /ecs/loc-collector --follow
```

**Common causes**:
1. **Invalid Congress API key**: Verify key at api.congress.gov
2. **Rate limiting**: Wait and retry
3. **Network issues**: Check VPC/subnet configuration

### Frontend Not Loading

**Symptom**: Amplify URL shows error

**Check Amplify status**:
```bash
aws amplify list-apps
aws amplify get-branch --app-id {app-id} --branch-name main
```

**Solution**: Trigger manual deployment
```bash
aws amplify start-deployment --app-id {app-id} --branch-name main
```

### Chat API Returns Errors

**Symptom**: 500 errors from /chat endpoint

**Check Lambda logs**:
```bash
aws logs tail /aws/lambda/loc-chat-handler --follow
```

**Common causes**:
1. **KB not synced**: Wait for data collection to complete
2. **Memory not created**: Check AgentCore Memory ID in Lambda env vars

---

## Cleanup / Destroy

### Option 1: Using Deploy Script

```bash
cd Loc_Project/backend
./deploy.sh
# Enter same parameters as deployment
# Choose "destroy" for action
```

### Option 2: Manual Cleanup

```bash
# Delete CDK stack
cdk destroy LOCstack --force

# Delete CodeBuild project
aws codebuild delete-project --name loc-deploy

# Delete IAM role
aws iam detach-role-policy --role-name loc-codebuild-role --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam delete-role --role-name loc-codebuild-role
```

### What Gets Deleted

- ✅ All Lambda functions
- ✅ API Gateway
- ✅ S3 buckets (with contents)
- ✅ VPC and networking
- ✅ ECS cluster and ECR repository
- ✅ Knowledge Base and Neptune
- ✅ Amplify app
- ✅ CloudWatch log groups

**Note**: AgentCore Memory is NOT automatically deleted. Delete manually if needed:
```bash
# List memories
aws bedrock-agentcore list-memories

# Delete memory
aws bedrock-agentcore delete-memory --memory-id {memory-id}
```

---

## Next Steps

After successful deployment:

1. **Wait for data collection** (30-60 minutes for full collection)
2. **Test the chat interface** at your Amplify URL
3. **Monitor costs** in AWS Cost Explorer
4. **Review logs** in CloudWatch for any issues

For architecture details, see [Architecture Deep Dive](ARCHITECTURE.md).
