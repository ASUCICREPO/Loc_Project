# Prerequisites Guide

This guide covers all the requirements and setup steps needed before deploying the Cultural Heritage Chatbot.

## Table of Contents

1. [AWS Account Requirements](#aws-account-requirements)
2. [AWS Services Used](#aws-services-used)
3. [Congress.gov API Key](#congressgov-api-key)
4. [AWS Bedrock Model Access](#aws-bedrock-model-access)

---

## AWS Account Requirements

### Basic Requirements

- **AWS Account**: Active AWS account with billing enabled
- **IAM Permissions**: Administrator access or specific permissions
- **Region**: Deploy in a region that supports Amazon Bedrock (recommended: `us-west-2` or `us-east-1`)
---

## AWS Services Used

The following AWS services will be provisioned during deployment:

### Compute & Networking

| Service | Purpose |
|---------|---------|
| **Amazon VPC** | Network isolation for resources |
| **AWS Lambda** | Serverless functions for chat API and triggers |
| **Amazon ECS Fargate** | Containerized data collection tasks |
| **Amazon ECR** | Docker image repository |

### AI/ML Services

| Service | Purpose |
|---------|---------|
| **Amazon Bedrock** | Claude 4.5 Sonnet for chat responses |
| **Bedrock Knowledge Base** | GraphRAG with semantic search |
| **Bedrock AgentCore Memory** | Conversation history storage |
| **Amazon Neptune Analytics** | Graph database for relationships |

### Storage

| Service | Purpose |
|---------|---------|
| **Amazon S3** | Document storage (bills, newspapers) |

### API & Hosting

| Service | Purpose |
|---------|---------|
| **Amazon API Gateway** | REST API endpoints |
| **AWS Amplify** | Frontend hosting |
| **Amazon CloudFront** | CDN (via Amplify) |

### DevOps & Monitoring

| Service | Purpose |
|---------|---------|
| **AWS CodeBuild** | Build and deployment automation |
| **AWS CloudFormation** | Infrastructure as Code (via CDK) |
| **Amazon CloudWatch** | Logging and monitoring |
| **AWS IAM** | Identity and access management |

---

## Congress.gov API Key

The Congress.gov API key is **required** for collecting Congressional bill data. This is a free API provided by the Library of Congress.

### Step 1: Navigate to API Signup Page

1. Open your web browser
2. Go to: **https://api.congress.gov/sign-up/**

### Step 2: Fill Out the Registration Form

Complete the registration form with the following information:

| Field | Description | Example |
|-------|-------------|---------|
| **First Name** | Your first name | John |
| **Last Name** | Your last name | Doe |
| **Email** | Valid email address | john.doe@example.com |
| **description (optional)** | Brief description | Historical research chatbot |

### Step 3: Submit and Verify Email

1. Click **"Sign Up"** button
2. Check your email inbox for a verification email from `api.data.gov`
3. Click the verification link in the email
4. Your API key will be displayed on the confirmation page

### Step 4: Save Your API Key

**Important**: Save your API key securely. You will need it during deployment.


### API Key Usage Notes

- **Rate Limits**: 1,000 requests per hour (sufficient for data collection)
- **No Cost**: The API is free to use
- **Terms of Service**: Review at https://api.congress.gov/terms-of-service/
- **Documentation**: https://api.congress.gov/

### Troubleshooting API Key Issues

| Issue | Solution |
|-------|----------|
| Didn't receive email | Check spam folder, try again with different email |
| API key not working | Ensure no extra spaces when copying |
| Rate limit exceeded | Wait 1 hour, or contact api.data.gov support |

---

## AWS Bedrock Model Access

Amazon Bedrock models require explicit access enablement before use.

### Step 1: Open Bedrock Console

1. Log in to AWS Console
2. Navigate to **Amazon Bedrock**

To get started, simply select a model from the Model catalog and open it in the playground or invoke the model using the InvokeModel  or Converse API  operations. Review  documentation  for the complete list of available models.

## Next Steps

Once all prerequisites are complete, proceed to the [Deployment Guide](DEPLOYMENT.md).
