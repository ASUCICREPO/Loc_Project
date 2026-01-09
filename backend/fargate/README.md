# Fargate Task: Congress Bills Collector

This Fargate task collects historical bills from the Congress API (Congress 1-16, 1789-1821) and extracts text to S3.

## Why Fargate Instead of Lambda?

- **No timeout limit**: Lambda has 15-minute max, but collecting all bills takes 30+ minutes
- **Long-running**: Can run for hours without issues
- **Cost-effective**: Only pay for actual runtime
- **Scalable**: Can handle large data collection tasks

## How It Works

```
1. Fargate Task Starts
   ↓
2. Calls Congress API for each Congress (1-16)
   ↓
3. For each bill:
   - Fetches bill metadata
   - Gets text versions (txt, html, pdf)
   - Extracts text (priority: txt > html > pdf)
   - Saves to S3 as plain text
   ↓
4. Saves collection summary
   ↓
5. Triggers Bedrock KB sync (via Step Functions)
   ↓
6. Bedrock automatically:
   - Reads text files from S3
   - Extracts entities & relationships
   - Stores in Neptune (GraphRAG)
```

## Build and Deploy

### 1. Build Docker Image

```bash
cd backend/fargate
chmod +x build.sh
./build.sh
```

This will:
- Create ECR repository
- Build Docker image
- Push to ECR

### 2. Deploy CDK Stack

```bash
cd backend
npm run deploy
```

### 3. Run Fargate Task

#### Option A: Via Step Functions (Recommended)

```bash
aws stepfunctions start-execution \
  --state-machine-arn <STATE_MACHINE_ARN> \
  --input '{}'
```

#### Option B: Directly via ECS

```bash
aws ecs run-task \
  --cluster chronicling-america-cluster \
  --task-definition chronicling-america-collector \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],assignPublicIp=ENABLED}"
```

## Configuration

Environment variables (set in CDK stack):

- `BUCKET_NAME`: S3 bucket for extracted text
- `START_CONGRESS`: Starting Congress number (default: 1)
- `END_CONGRESS`: Ending Congress number (default: 16)
- `BILL_TYPES`: Comma-separated bill types (default: "hr,s")
- `CONGRESS_API_KEY`: Congress.gov API key

## Text Extraction Priority

The task tries formats in this order:

1. **Plain Text (.txt)** - Best, no extraction needed
2. **HTML (.htm)** - Good, uses BeautifulSoup
3. **PDF** - Last resort, uses PyPDF2

## Output Structure

```
s3://bucket/
├── extracted/
│   ├── congress_1/
│   │   ├── hr_1.txt
│   │   ├── hr_2.txt
│   │   └── s_1.txt
│   ├── congress_2/
│   │   └── ...
│   └── congress_16/
│       └── ...
└── collection_summary.json
```

## Monitoring

### View Logs

```bash
# CloudWatch Logs
aws logs tail /ecs/chronicling-america-collector --follow

# Or in AWS Console
# CloudWatch → Log Groups → /ecs/chronicling-america-collector
```

### Check Task Status

```bash
aws ecs list-tasks --cluster chronicling-america-cluster
aws ecs describe-tasks --cluster chronicling-america-cluster --tasks <task-id>
```

### View Summary

```bash
aws s3 cp s3://<bucket>/collection_summary.json -
```

## Troubleshooting

### Task Fails to Start

- Check ECR image exists: `aws ecr describe-images --repository-name chronicling-america-collector`
- Check task role permissions
- Check VPC/subnet configuration

### API Rate Limiting

The task includes 0.5s delay between API calls. If you hit rate limits:
- Increase delay in `collect_bills.py`
- Process fewer Congresses at a time

### Out of Memory

If task runs out of memory:
- Increase memory in CDK stack (currently 4GB)
- Process fewer bills per run

## Cost Estimate

Fargate pricing (us-east-1):
- 2 vCPU: $0.04048/hour
- 4 GB memory: $0.004445/GB/hour

Estimated cost for full collection (1-2 hours):
- **~$0.10 - $0.20** per run

Much cheaper than keeping Lambda running!

## Next Steps

After Fargate completes:

1. **Check S3**: Verify text files in `extracted/` folder
2. **Sync Bedrock KB**: Trigger KB sync (automatic in Step Functions)
3. **Wait for entity extraction**: 5-10 minutes
4. **Query via Chat API**: Test with historical questions

## Local Testing

Test the collector locally:

```bash
cd backend/fargate

# Build image
docker build -t collector-test .

# Run locally
docker run -e BUCKET_NAME=test-bucket \
  -e START_CONGRESS=1 \
  -e END_CONGRESS=2 \
  -e BILL_TYPES=hr \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=xxx \
  collector-test
```
