# Deployment Guide - Cultural Heritage Chatbot

Simple 4-step deployment process using AWS CloudShell and automated scripts.

## Prerequisites

- AWS Account with appropriate permissions
- Access to AWS Management Console

## Deployment Steps

### Step 1: Open AWS CloudShell

1. Log in to the [AWS Management Console](https://console.aws.amazon.com)
2. Click the **CloudShell** icon (terminal icon) in the top navigation bar
3. Wait for the CloudShell environment to initialize

### Step 2: Clone the Repository

```bash
git clone https://github.com/ASUCICREPO/Loc_Project.git
cd Loc_Project/backend
```

### Step 3: Make Deploy Script Executable

```bash
chmod +x ./deploy.sh
```

### Step 4: Run Deployment

```bash
./deploy.sh
```

The deployment script will automatically:
- Install all required dependencies
- Bootstrap AWS CDK (if needed)
- Create Bedrock Agent memory
- Deploy backend infrastructure
- Set up API Gateway, Lambda functions, Neptune, and OpenSearch
- Configure the frontend build

## Monitor Deployment Progress

The CodeBuild project will start automatically and you can monitor the build progress:

1. Go to **AWS CodeBuild** in the AWS Console
2. Find your build project: `cultural-heritage-chatbot-build`
3. Click on the running build to view logs

## Get Your Application URL

**At the end of the CodeBuild process, you will receive an AWS Amplify link.**

The Amplify link will be displayed in the CodeBuild output logs:
```
✅ Deployment complete!
🌐 Your application is available at: https://xxxxx.amplifyapp.com
```

## Post-Deployment

### Verify Deployment

```bash
# Check CloudFormation stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# Test API endpoint (URL from deployment output)
curl https://your-api-gateway-url.amazonaws.com/health
```

### Access Your Application

1. Open the Amplify URL provided in the CodeBuild output
2. The Cultural Heritage Chatbot interface will load
3. Select a persona from the dropdown or buttons
4. Start asking questions about US history

## Example Queries to Test

- "What is the First Amendment?"
- "Explain the significance of the Constitutional Convention"
- "What were the main debates in early Congress?"
- "Tell me about the Federalist Papers"

## Troubleshooting

### If Deployment Fails

**Check CloudFormation Events:**
```bash
aws cloudformation describe-stack-events --stack-name LocProjectStack
```

**View CodeBuild Logs:**
1. Go to AWS CodeBuild Console
2. Select your build project
3. Click on the failed build
4. Review the error messages in the logs

**Common Issues:**

1. **Bedrock Not Available**
   - Ensure you're deploying in a region that supports AWS Bedrock (us-east-1, us-west-2)

2. **Permission Denied**
   - Verify your AWS account has the necessary IAM permissions
   - Required: CloudFormation, Lambda, API Gateway, Bedrock, Neptune, S3, OpenSearch

3. **CDK Bootstrap Error**
   - Run manually: `cdk bootstrap aws://ACCOUNT-ID/REGION`

4. **Timeout Errors**
   - Neptune and OpenSearch can take 10-15 minutes to provision
   - Wait for the deployment to complete (typically 15-20 minutes total)

### View Detailed Logs

```bash
# Lambda function logs
aws logs tail /aws/lambda/cultural-heritage-chatbot-handler --follow

# CodeBuild logs
aws codebuild batch-get-builds --ids <build-id>
```

## Clean Up / Delete Resources

To remove all deployed resources:

```bash
cd backend
./cleanup.sh
```

Or manually:

```bash
# Delete all CDK stacks
cdk destroy --all

# Or use CloudFormation
aws cloudformation delete-stack --stack-name LocProjectStack
```

**Note:** Make sure to empty and delete S3 buckets before deleting stacks.

## What Gets Deployed

The `deploy.sh` script deploys:

### Backend Infrastructure
- **API Gateway**: REST API endpoints for chat functionality
- **Lambda Functions**: Handler for processing chat requests
- **Amazon Bedrock Agent**: AI-powered response generation
- **Neptune Database**: Graph database for historical relationships
- **OpenSearch**: Vector search for document retrieval
- **S3 Buckets**: Document and asset storage
- **CloudWatch**: Logging and monitoring

### Frontend Application
- **AWS Amplify**: Hosting for the Next.js frontend
- **CloudFront CDN**: Global content delivery
- **Environment Configuration**: Automatic API endpoint setup

## Architecture Overview

```
User Request
    ↓
Amplify Frontend (Next.js)
    ↓
API Gateway
    ↓
Lambda Function
    ↓
Bedrock Agent (Claude AI)
    ↓
Knowledge Base (OpenSearch + Neptune)
    ↓
Response to User
```

## Configuration

The deployment uses default settings from:
- `backend/cdk.json` - CDK stack configuration
- `backend/buildspec.yml` - CodeBuild build specification
- `backend/deploy.sh` - Deployment automation script

To customize:
1. Edit these files before running `./deploy.sh`
2. Update region, instance types, or other parameters as needed

## Support

### Documentation
- [Main README](README.md) - Project overview and features
- [Frontend README](frontend/README.md) - Frontend-specific documentation
- [Backend README](backend/README.md) - Backend infrastructure details

### Get Help
- **GitHub Issues**: [Report issues](https://github.com/ASUCICREPO/Loc_Project/issues)
- **AWS Support**: Check AWS console for service-specific errors
- **CloudFormation Events**: Review stack events for detailed error messages

## Deployment Time

Expected deployment time: **15-20 minutes**

- CDK Bootstrap: 2-3 minutes (first time only)
- Backend Stack: 10-15 minutes
- Frontend Build: 3-5 minutes
- Total: ~20 minutes for first deployment

## Security Notes

- All API calls are encrypted (HTTPS)
- IAM roles follow least-privilege principle
- Bedrock Agent uses AWS-managed encryption
- CloudWatch logs are retained for 30 days by default

## Next Steps After Deployment

1. ✅ Test the application with sample queries
2. ✅ Review CloudWatch logs to ensure everything is working
3. ✅ Load historical data (if not included in initial deployment)
4. ✅ Configure custom domain (optional)
5. ✅ Set up monitoring alerts
6. ✅ Review and optimize costs

---

**Last Updated**: February 2026
**Version**: 1.0.0

**Quick Start**: Just run `./deploy.sh` in CloudShell and get your Amplify link at the end! 🚀
