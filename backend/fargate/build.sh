#!/bin/bash

# Build and push Docker image to ECR
# Uses AWS Public ECR for base images to avoid Docker Hub rate limits

set -e

# Configuration
AWS_REGION=${AWS_REGION:-us-west-2}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "========================================="
echo "Building Congress Bills Collector"
echo "========================================="
echo "Using AWS Public ECR base image to avoid Docker Hub rate limits"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo ""

# Auto-detect repository name from CDK stack
# Try LOCstack first, then fall back to old names
for STACK_NAME in "LOCstack" "ChroniclingAmericaStackV2" "ChroniclingAmericaStack"; do
  ECR_REPOSITORY=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text 2>/dev/null | cut -d'/' -f2)
  
  if [ -n "$ECR_REPOSITORY" ] && [ "$ECR_REPOSITORY" != "None" ] && [ "$ECR_REPOSITORY" != "null" ]; then
    echo "✓ Found repository from stack: $STACK_NAME"
    break
  else
    ECR_REPOSITORY=""
  fi
done

# Fallback to default if not found
if [ -z "$ECR_REPOSITORY" ]; then
  # Use project name from environment (should match CDK context)
  PROJECT_NAME=${PROJECT_NAME:-loc}
  ECR_REPOSITORY="${PROJECT_NAME}-collector"
  echo "⚠ Could not auto-detect repository name, using default: $ECR_REPOSITORY"
  echo "   PROJECT_NAME: $PROJECT_NAME"
  echo "   Expected CDK repository name: ${PROJECT_NAME}-collector"
fi

# Validate repository name meets ECR requirements
if [[ ! "$ECR_REPOSITORY" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]]; then
  echo "❌ ERROR: Repository name '$ECR_REPOSITORY' doesn't meet ECR naming requirements"
  echo "   ECR repository names must:"
  echo "   - Be lowercase"
  echo "   - Contain only letters, numbers, hyphens, underscores, and periods"
  echo "   - Not start or end with special characters"
  echo ""
  # Fix the repository name
  ECR_REPOSITORY=$(echo "$ECR_REPOSITORY" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]//g' | sed 's/^[._-]*//g' | sed 's/[._-]*$//g')
  echo "   Fixed repository name: $ECR_REPOSITORY"
fi

IMAGE_TAG=${IMAGE_TAG:-latest}

echo "Repository: $ECR_REPOSITORY"
echo "Tag: $IMAGE_TAG"
echo ""

# Create ECR repository if it doesn't exist
echo "Step 1: Creating ECR repository (if not exists)..."
aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPOSITORY --region $AWS_REGION

# Login to ECR
echo "Step 2: Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Docker image
echo "Step 3: Building Docker image (using AWS Public ECR base)..."
echo "  Base image: public.ecr.aws/docker/library/python:3.11-slim"
echo "  This avoids Docker Hub rate limits"
docker build -t $ECR_REPOSITORY:$IMAGE_TAG .

# Tag image for ECR
echo "Step 4: Tagging image for ECR..."
docker tag $ECR_REPOSITORY:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG

# Push to ECR
echo "Step 5: Pushing image to ECR..."
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG

echo ""
echo "🎉 Docker image build complete!"
echo "✓ Image URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG"
echo "✓ Ready for Fargate deployment"
