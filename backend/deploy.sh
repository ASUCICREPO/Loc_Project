#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "Chronicling America Pipeline Deployment"
echo "========================================="
echo ""

# Get GitHub URL
if [ -z "${GITHUB_URL:-}" ]; then
  read -rp "Enter GitHub repository URL: " GITHUB_URL
fi

clean_url=${GITHUB_URL%.git}
clean_url=${clean_url%/}

# Get project name
if [ -z "${PROJECT_NAME:-}" ]; then
  read -rp "Enter project name [default: chronicling-america-pipeline]: " PROJECT_NAME
  PROJECT_NAME=${PROJECT_NAME:-chronicling-america-pipeline}
fi

# Get AWS region
if [ -z "${AWS_REGION:-}" ]; then
  read -rp "Enter AWS region [default: us-west-2]: " AWS_REGION
  AWS_REGION=${AWS_REGION:-us-west-2}
fi

# Get AWS account
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# Get data bucket name
if [ -z "${DATA_BUCKET_NAME:-}" ]; then
  read -rp "Enter data bucket name [default: ${PROJECT_NAME}-data-${AWS_ACCOUNT}-${AWS_REGION}]: " DATA_BUCKET_NAME
  DATA_BUCKET_NAME=${DATA_BUCKET_NAME:-${PROJECT_NAME}-data-${AWS_ACCOUNT}-${AWS_REGION}}
fi

# Get Bedrock model ID
if [ -z "${BEDROCK_MODEL_ID:-}" ]; then
  read -rp "Enter Bedrock model ID [default: anthropic.claude-3-5-sonnet-20241022-v2:0]: " BEDROCK_MODEL_ID
  BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID:-anthropic.claude-3-5-sonnet-20241022-v2:0}
fi

# Get action
if [ -z "${ACTION:-}" ]; then
  read -rp "Enter action [deploy/destroy]: " ACTION
  ACTION=$(printf '%s' "$ACTION" | tr '[:upper:]' '[:lower:]')
fi

if [[ "$ACTION" != "deploy" && "$ACTION" != "destroy" ]]; then
  echo "Invalid action: '$ACTION'. Choose 'deploy' or 'destroy'."
  exit 1
fi

# Create IAM role for CodeBuild
ROLE_NAME="${PROJECT_NAME}-codebuild-role"
echo ""
echo "Checking for IAM role: $ROLE_NAME"

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "✓ IAM role exists"
  ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
else
  echo "Creating IAM role: $ROLE_NAME"
  TRUST_DOC='{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"codebuild.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'

  ROLE_ARN=$(aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_DOC" \
    --query 'Role.Arn' --output text)

  echo "Attaching policies..."
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

  echo "Waiting for IAM role to propagate..."
  sleep 10
fi

# Create CodeBuild project
CODEBUILD_PROJECT_NAME="${PROJECT_NAME}-deploy"
echo ""
echo "Creating CodeBuild project: $CODEBUILD_PROJECT_NAME"

ENV_VARS=$(cat <<EOF
[
  {"name": "PROJECT_NAME", "value": "$PROJECT_NAME", "type": "PLAINTEXT"},
  {"name": "ACTION", "value": "$ACTION", "type": "PLAINTEXT"},
  {"name": "CDK_DEFAULT_REGION", "value": "$AWS_REGION", "type": "PLAINTEXT"},
  {"name": "DATA_BUCKET_NAME", "value": "$DATA_BUCKET_NAME", "type": "PLAINTEXT"},
  {"name": "BEDROCK_MODEL_ID", "value": "$BEDROCK_MODEL_ID", "type": "PLAINTEXT"}
]
EOF
)

ENVIRONMENT=$(cat <<EOF
{
  "type": "LINUX_CONTAINER",
  "image": "aws/codebuild/standard:7.0",
  "computeType": "BUILD_GENERAL1_MEDIUM",
  "privilegedMode": true,
  "environmentVariables": $ENV_VARS
}
EOF
)

ARTIFACTS='{"type":"NO_ARTIFACTS"}'
SOURCE=$(cat <<EOF
{
  "type":"GITHUB",
  "location":"$GITHUB_URL",
  "buildspec":"backend/buildspec.yml"
}
EOF
)

# Delete existing project if exists
if aws codebuild batch-get-projects --names "$CODEBUILD_PROJECT_NAME" --query 'projects[0].name' --output text 2>/dev/null | grep -q "$CODEBUILD_PROJECT_NAME"; then
  echo "Deleting existing CodeBuild project..."
  aws codebuild delete-project --name "$CODEBUILD_PROJECT_NAME"
  sleep 5
fi

aws codebuild create-project \
  --name "$CODEBUILD_PROJECT_NAME" \
  --source "$SOURCE" \
  --artifacts "$ARTIFACTS" \
  --environment "$ENVIRONMENT" \
  --service-role "$ROLE_ARN" \
  --output json \
  --no-cli-pager

if [ $? -eq 0 ]; then
  echo "✓ CodeBuild project created"
else
  echo "✗ Failed to create CodeBuild project"
  exit 1
fi

# Start build
echo ""
echo "Starting deployment..."
BUILD_ID=$(aws codebuild start-build \
  --project-name "$CODEBUILD_PROJECT_NAME" \
  --query 'build.id' \
  --output text)

if [ $? -eq 0 ]; then
  echo "✓ Build started with ID: $BUILD_ID"
  echo ""
  echo "Monitor build progress:"
  echo "https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT_NAME/build/$BUILD_ID"
else
  echo "✗ Failed to start build"
  exit 1
fi

echo ""
echo "========================================="
echo "Deployment Information"
echo "========================================="
echo "Project Name: $PROJECT_NAME"
echo "GitHub URL: $GITHUB_URL"
echo "AWS Region: $AWS_REGION"
echo "Data Bucket: $DATA_BUCKET_NAME"
echo "Bedrock Model: $BEDROCK_MODEL_ID"
echo "Action: $ACTION"
echo "Build ID: $BUILD_ID"
echo ""
echo "⏱️  Estimated deployment time: 20-30 minutes"
echo "📊 Monitor progress in CodeBuild console"
echo ""

exit 0
