# Fargate Trigger Lambda

This Lambda function triggers Fargate tasks to collect bills from the Congress API.

## Architecture

```
API Gateway → Lambda (trigger) → Fargate Task (collector)
     ↓
  Returns immediately with task ARN
                                    ↓
                            Fargate runs collection job
                                    ↓
                            Saves bills to S3
```

## Why Lambda + Fargate?

**Lambda Advantages:**
- Fast response to API requests (< 1 second)
- No timeout issues (just triggers and returns)
- Simple to deploy (no Docker build needed)

**Fargate Advantages:**
- Can run for hours (no 15-minute Lambda limit)
- More memory and CPU for heavy processing
- Better for long-running data collection jobs

## Usage

### Via API Gateway:
```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/collect \
  -H "Content-Type: application/json" \
  -d '{
    "start_congress": 1,
    "end_congress": 16,
    "bill_types": "hr,s"
  }'
```

### Via Python test script:
```bash
python test_backend.py --source congress --congress 7
```

### Response:
```json
{
  "message": "Fargate task started successfully",
  "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/...",
  "parameters": {
    "start_congress": 1,
    "end_congress": 16,
    "bill_types": "hr,s"
  }
}
```

## Monitoring

Check Fargate task logs in CloudWatch:
```bash
aws logs tail /ecs/chronicling-america-pipeline-collector --follow
```

## Deployment

No Docker build needed! Just deploy CDK:
```bash
cd backend
cdk deploy
```

The Lambda function is automatically built and deployed by CDK.
