# Chronicling America Historical Newspaper Pipeline - Backend

Complete AWS CDK infrastructure for automated historical newspaper and congressional bill data extraction with **GraphRAG using Amazon Bedrock Knowledge Bases**.

## 🎯 What's New: GraphRAG with Bedrock Knowledge Bases

This pipeline implements **GraphRAG** (Graph Retrieval-Augmented Generation) using Amazon Bedrock Knowledge Bases for automatic entity extraction and relationship discovery.

### Key Innovation

Instead of manual entity extraction, we use:

1. **Neptune** - Stores raw document text as graph vertices
2. **S3 Export** - Automatically exports documents to S3
3. **Bedrock Knowledge Base** - Automatically extracts entities, relationships, and creates embeddings
4. **Semantic Search** - Query using natural language with context-aware answers

### Why This Approach?

- ✅ **Automatic Entity Extraction**: No manual NLP pipelines needed
- ✅ **Better Accuracy**: Bedrock uses advanced foundation models
- ✅ **Semantic Search**: Vector embeddings for intelligent retrieval
- ✅ **Scalable**: Handles thousands of documents efficiently
- ✅ **Cost Effective**: Pay only for what you use

## 🚀 Quick Start

### One-Command Deployment

```bash
cd backend
./deploy.sh
```

**What gets deployed:**

1. ✅ VPC & Neptune cluster
2. ✅ 7 Lambda functions (Docker-based)
3. ✅ S3 bucket with automatic document export
4. ✅ Step Functions pipeline
5. ✅ API Gateway for chat interface
6. ⚠️ Knowledge Base setup (5-minute manual step)

**Deployment time**: ~20-30 minutes

### Post-Deployment Setup (5 minutes)

After deployment, follow **[SIMPLE_SETUP_GUIDE.md](../SIMPLE_SETUP_GUIDE.md)** to:

1. Create Bedrock Knowledge Base in AWS Console
2. Point it to the auto-exported S3 documents
3. Update Lambda environment variables

## 📋 What Gets Deployed

### Infrastructure Components

- **7 Lambda Functions** (Docker-based, fully automated)

  - Image Collector - Fetches from LOC/Congress APIs
  - Image to PDF - Converts images to PDF format
  - Bedrock Data Automation - Extracts text using Bedrock
  - Neptune Loader - Stores documents in graph database
  - **Neptune Exporter** ← NEW! Exports docs to S3 for KB
  - **KB Sync Trigger** ← NEW! Triggers Knowledge Base ingestion
  - Chat Handler - Queries KB for intelligent answers

- **Step Functions** - Fully automated pipeline orchestration
- **Neptune Cluster** - Graph database for document storage
- **VPC** - Network isolation with private subnets
- **S3 Bucket** - Data storage with `kb-documents/` prefix
- **API Gateway** - REST API for chat interface

### GraphRAG Architecture Flow

```
Data Sources (LOC API / Congress.gov)
    ↓
1. Image Collector Lambda
   ↓ Fetches newspaper images or congressional bills
   ↓ Saves to S3: images/ or congress-bills/

2. Image to PDF Lambda (newspapers only)
   ↓ Converts images to PDF format
   ↓ Saves to S3: pdfs/

3. Bedrock Data Automation Lambda
   ↓ Extracts text using Bedrock
   ↓ Saves to S3: extractions/

4. Neptune Loader Lambda
   ↓ Loads documents as vertices with full text
   ↓ Stores in Neptune with document_text property

5. Neptune Exporter Lambda ← NEW!
   ↓ Exports Neptune documents to S3
   ↓ Saves to S3: kb-documents/ (KB-ready format)

6. KB Sync Trigger Lambda ← NEW!
   ↓ Triggers Bedrock Knowledge Base ingestion
   ↓ KB extracts entities & relationships automatically

7. Bedrock Knowledge Base (Manual Setup)
   ↓ Reads from S3: kb-documents/
   ↓ Extracts entities (people, places, organizations)
   ↓ Creates relationships automatically
   ↓ Generates vector embeddings
   ↓ Stores in vector database

8. Chat Handler Lambda (API Gateway)
   ↓ Receives natural language questions
   ↓ Queries Bedrock KB (semantic search)
   ↓ Returns answers with citations
```

## 🎯 Key Features

### ✅ GraphRAG with Bedrock Knowledge Bases

- **Automatic Entity Extraction**: No manual NLP pipelines
- **Semantic Search**: Vector embeddings for intelligent retrieval
- **Relationship Discovery**: Automatically finds connections
- **Context-Aware Answers**: LLM-powered responses with citations
- **Scalable**: Handles thousands of documents

### ✅ Dual Data Sources

- **Historical Newspapers**: Chronicling America (1789-1963)
- **Congressional Bills**: Congress.gov API (current legislation)
- Unified pipeline for both sources
- Consistent document format

### ✅ Docker-Based Lambda Functions

- **No manual layer creation required**
- Dependencies automatically managed
- Consistent runtime environment
- Easy to update and maintain
- All 7 functions containerized

### ✅ Automated Deployment

- One-command deployment via CodeBuild
- No local Docker required
- Builds in AWS environment
- Consistent across teams
- IAM roles auto-created

### ✅ Complete Pipeline Automation

- Step Functions orchestration
- Automatic S3 export for KB
- Automatic KB sync triggering
- Error handling and retries
- CloudWatch logging
- S3 data persistence

### ✅ Intelligent Chat API

- Natural language queries
- Bedrock Knowledge Base integration
- Semantic search with embeddings
- Entity and relationship traversal
- Source citations included
- CORS enabled
- Health check endpoint

## 📖 Documentation

### Setup Guides

- **[SIMPLE_SETUP_GUIDE.md](../SIMPLE_SETUP_GUIDE.md)** - Step-by-step setup (RECOMMENDED)
- **[QUICK_START.md](../QUICK_START.md)** - Quick reference commands
- **[DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md)** - What gets created

### Technical Documentation

- **[AUTOMATED_SETUP.md](../AUTOMATED_SETUP.md)** - Complete automation architecture
- **[DEPLOYMENT_STATUS.md](../DEPLOYMENT_STATUS.md)** - Current deployment approach
- **[GRAPHRAG_IMPLEMENTATION.md](../GRAPHRAG_IMPLEMENTATION.md)** - GraphRAG details
- **[BEDROCK_KB_MANUAL_SETUP.md](../BEDROCK_KB_MANUAL_SETUP.md)** - Manual KB setup (if needed)

### Integration Guides

- **[CONGRESS_BILLS_INTEGRATION.md](../CONGRESS_BILLS_INTEGRATION.md)** - Congress.gov API integration
- **[FULLY_AUTOMATED_PIPELINE.md](../FULLY_AUTOMATED_PIPELINE.md)** - Pipeline automation details

### Testing

- **[test_automated_pipeline.py](../test_automated_pipeline.py)** - End-to-end test script
- **[test_backend.py](test_backend.py)** - Backend test utilities

## 🔧 Prerequisites

### Required

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Node.js 18+ and npm
- Bedrock model access (Claude 3.5 Sonnet)

### Optional

- Docker (for local development)
- Git (for version control)

### Quick Setup

```bash
# Install AWS CLI
# https://aws.amazon.com/cli/

# Configure AWS credentials
aws configure

# Install Node.js
# https://nodejs.org/

# Install AWS CDK
npm install -g aws-cdk@2.161.1

# Verify setup
./quick-start.sh
```

## 🚀 Deployment Options

### Option 1: Automated (Recommended)

```bash
./deploy.sh
```

**Best for**: Production, CI/CD, teams

### Option 2: Manual CDK

```bash
npm install
npm run build
cdk deploy --all
```

**Best for**: Development, customization

### Option 3: AWS CloudShell

```bash
# Open CloudShell in AWS Console
git clone YOUR-REPO-URL
cd YOUR-REPO/backend
./deploy.sh
```

**Best for**: No local setup required

## 📊 Usage Examples

### Start Pipeline - Newspapers

```bash
# Get State Machine ARN
STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name LOCstack \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# Process historical newspapers
aws stepfunctions start-execution \
  --state-machine-arn $STATE_MACHINE_ARN \
  --input '{
    "source": "newspapers",
    "start_date": "1815-08-01",
    "end_date": "1815-08-31",
    "max_pages": 10
  }'
```

### Start Pipeline - Congressional Bills

```bash
# Process congressional bills
aws stepfunctions start-execution \
  --state-machine-arn $STATE_MACHINE_ARN \
  --input '{
    "source": "congress",
    "congress": 118,
    "bill_type": "hr",
    "limit": 10
  }'
```

### Monitor Pipeline Execution

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn $STATE_MACHINE_ARN \
  --max-results 5

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn <EXECUTION_ARN>
```

### Check Knowledge Base Sync Status

```bash
# Get KB IDs from outputs (after manual setup)
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name LOCstack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text)

DS_ID=$(aws cloudformation describe-stacks \
  --stack-name LOCstack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseDataSourceId`].OutputValue' \
  --output text)

# Check sync status
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID
```

## 📁 Project Structure

```
backend/
├── bin/
│   └── chronicling-america-cdk.ts           # CDK app entry point
├── lib/
│   └── chronicling-america-stack.ts         # Main infrastructure stack
├── lambda/
│   ├── image-collector/                     # Fetch from LOC/Congress APIs
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── image-to-pdf/                        # Convert images to PDF
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── bedrock-data-automation/             # Extract text with Bedrock
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── data-extractor/                      # Legacy extractor (kept for compatibility)
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── neptune-loader/                      # Load documents to Neptune
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── neptune-exporter/                    # ← NEW! Export to S3 for KB
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── kb-sync-trigger/                     # ← NEW! Trigger KB ingestion
│   │   ├── lambda_function.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── chat-handler/                        # Chat API with KB integration
│       ├── lambda_function.py
│       ├── Dockerfile
│       └── requirements.txt
├── deploy.sh                                # Automated deployment script
├── buildspec.yml                            # CodeBuild configuration
├── cdk.json                                 # CDK configuration
├── package.json                             # Node.js dependencies
├── tsconfig.json                            # TypeScript configuration
└── README.md                                # This file
```

## 🔧 Lambda Functions (Docker-Based)

All Lambda functions use Docker containers for automatic dependency management:

### Data Collection

1. **image-collector**: Fetches newspaper images from LOC API or congressional bills from Congress.gov API

### Data Processing

2. **image-to-pdf**: Converts newspaper images to PDF format for text extraction
3. **bedrock-data-automation**: Extracts text from PDFs using Amazon Bedrock Data Automation
4. **data-extractor**: Legacy extractor using Claude Vision (kept for compatibility)

### Graph Database

5. **neptune-loader**: Loads documents to Neptune as vertices with full text content

### GraphRAG (NEW!)

6. **neptune-exporter**: Exports Neptune documents to S3 in Bedrock KB-compatible format
7. **kb-sync-trigger**: Automatically triggers Bedrock Knowledge Base ingestion after export

### Query Interface

8. **chat-handler**: Provides chat API that queries Bedrock Knowledge Base for intelligent answers

## Environment Variables

Set in CDK stack:

- `DATA_BUCKET`: S3 bucket for pipeline data
- `BEDROCK_MODEL_ID`: Bedrock model ID (default: Claude 3.5 Sonnet)
- `NEPTUNE_ENDPOINT`: Neptune cluster endpoint
- `NEPTUNE_PORT`: Neptune port (default: 8182)

## Cost Estimation

- **Lambda**: ~$0.20 per 1000 invocations
- **Bedrock**: ~$0.012 per image (Claude 3.5 Sonnet)
- **Neptune**: ~$0.10/hour (db.t3.medium)
- **S3**: ~$0.023/GB/month
- **Step Functions**: ~$0.025 per 1000 state transitions

**Total for 100 newspapers**: ~$2-5

## Monitoring

- CloudWatch Logs: `/aws/lambda/<function-name>`
- Step Functions: AWS Console → Step Functions
- Neptune: CloudWatch metrics for cluster

## Troubleshooting

### Lambda timeout

- Increase timeout in CDK stack (default: 15 minutes)

### Bedrock access denied

- Enable model access in Bedrock console
- Check IAM permissions

### Neptune connection failed

- Verify VPC configuration
- Check security group rules

## Next Steps

1. Deploy the stack
2. Start a pipeline execution
3. Monitor in Step Functions console
4. Query Neptune via chat UI
5. Customize extraction prompts in Lambda code

## Support

For issues, check CloudWatch logs or create an issue in the repository.

### Query Chat API

```bash
# Get API endpoint
API_URL=$(aws cloudformation describe-stacks \
  --stack-name LOCstack \
  --query 'Stacks[0].Outputs[?OutputKey==`ChatEndpoint`].OutputValue' \
  --output text)

# Query about newspapers
curl -X POST $API_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "Who are the people mentioned in the newspapers from 1815?"
  }'

# Query about congressional bills
curl -X POST $API_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What bills were introduced about taxation?"
  }'

# Query with entity relationships
curl -X POST $API_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "Which committees reviewed healthcare bills?"
  }'
```

### Check Health

```bash
curl $API_URL/health
```

### View Exported Documents in S3

```bash
# Get bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name LOCstack \
  --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue' \
  --output text)

# List exported documents
aws s3 ls s3://$BUCKET_NAME/kb-documents/

# Download a sample document
aws s3 cp s3://$BUCKET_NAME/kb-documents/doc-1.json ./sample-doc.json
cat sample-doc.json
```

## 💰 Cost Estimation

### Monthly Costs (100 documents)

| Service                 | Cost            | Notes                       |
| ----------------------- | --------------- | --------------------------- |
| Lambda (7 functions)    | $0.50           | Includes all pipeline steps |
| Bedrock Data Automation | $2.40           | Text extraction             |
| Bedrock KB (embeddings) | $0.50           | One-time per document       |
| Bedrock KB (queries)    | $0.10           | Per 1000 queries            |
| Neptune (db.t3.medium)  | $73.00          | 24/7 operation              |
| S3 Storage              | $0.10           | Raw + processed + KB docs   |
| Step Functions          | $0.50           | Pipeline orchestration      |
| API Gateway             | $0.01           | Chat API calls              |
| VPC (NAT Gateway)       | $32.00          | Network connectivity        |
| CloudWatch Logs         | $0.50           | Monitoring                  |
| **Total**               | **~$110/month** | **First month: ~$113**      |

### Cost Breakdown by Data Source

**100 Newspapers:**

- Image processing: $1.20
- Text extraction: $2.40
- KB ingestion: $0.50
- **Total processing**: ~$4.10

**100 Congressional Bills:**

- API calls: Free
- Text extraction: $0.50 (simpler format)
- KB ingestion: $0.50
- **Total processing**: ~$1.00

### 💡 Cost Optimization Tips

1. **Stop Neptune when not in use** → Save $73/month

   ```bash
   aws neptune stop-db-cluster --db-cluster-identifier YOUR-CLUSTER
   ```

2. **Use smaller Neptune instance** → Save 50%

   - Change from db.t3.medium to db.t3.small in CDK

3. **Batch processing** → Reduce Lambda invocations

   - Process 100 documents at once instead of 10

4. **S3 Intelligent-Tiering** → Automatic cost optimization

   - Moves old data to cheaper storage tiers

5. **Delete old CloudWatch logs** → Save on storage
   - Set retention to 7 days instead of indefinite

### Cost for Different Scales

| Documents | Processing | Monthly | Notes            |
| --------- | ---------- | ------- | ---------------- |
| 100       | $4         | $110    | Good for testing |
| 1,000     | $40        | $145    | Production ready |
| 10,000    | $400       | $505    | Large scale      |

_Monthly costs include Neptune + infrastructure. Processing is one-time per document._

## 🔍 Monitoring

### CloudWatch Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/chronicling-america-pipeline-image-collector --follow

# View Step Functions logs
aws logs tail /aws/stepfunctions/chronicling-america-pipeline --follow
```

### Step Functions Console

Monitor pipeline execution:

- https://console.aws.amazon.com/states/home

### Neptune Metrics

View in CloudWatch:

- CPU utilization
- Memory usage
- Connection count

## 🐛 Troubleshooting

### Common Issues

#### Lambda Timeout

**Error**: Task timed out after 15 minutes

**Solution**: Reduce `max_pages` or increase timeout in CDK stack

#### Bedrock Access Denied

**Error**: AccessDeniedException

**Solution**: Enable model access in Bedrock console

#### Neptune Connection Failed

**Error**: Cannot connect to Neptune

**Solution**:

- Verify Lambda is in VPC
- Check security group rules
- Wait for Neptune to be available

#### Docker Build Failed

**Error**: Cannot build image

**Solution**:

- Ensure Docker is running (local)
- Enable privileged mode in CodeBuild
- Check Dockerfile syntax

### Debug Commands

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name ChroniclingAmericaStack

# Check Lambda function
aws lambda get-function --function-name chronicling-america-pipeline-image-collector

# Check Neptune cluster
aws neptune describe-db-clusters

# Test API Gateway
curl -X GET https://YOUR-API-ID.execute-api.us-west-2.amazonaws.com/prod/health
```

## 📁 Project Structure

```
backend/
├── bin/
│   └── chronicling-america-cdk.ts          # CDK app entry
├── lib/
│   └── chronicling-america-stack.ts        # Infrastructure stack
├── lambda/
│   ├── image-collector/                    # Fetch images
│   ├── data-extractor/                     # Extract with Bedrock
│   ├── entity-extractor/                   # Extract entities
│   ├── neptune-loader/                     # Load to Neptune
│   └── chat-handler/                       # Chat API
├── deploy.sh                               # Automated deployment
├── buildspec.yml                           # CodeBuild config
├── quick-start.sh                          # Setup verification
├── test-deployment.sh                      # Test script
├── package.json                            # Dependencies
├── tsconfig.json                           # TypeScript config
├── cdk.json                                # CDK config
├── README.md                               # This file
├── DEPLOYMENT_GUIDE.md                     # Detailed guide
└── IMPLEMENTATION_SUMMARY.md               # Technical details
```

## 🔄 GraphRAG Pipeline Steps

### 1. Data Collection

**Lambda**: `image-collector`

- Fetches newspaper images from Chronicling America API
- OR fetches congressional bills from Congress.gov API
- Filters by date range / congress number
- Deduplicates results
- Saves raw data to S3

### 2. Format Conversion (Newspapers Only)

**Lambda**: `image-to-pdf`

- Downloads images from URLs
- Converts to PDF format
- Optimizes for text extraction
- Saves PDFs to S3

### 3. Text Extraction

**Lambda**: `bedrock-data-automation`

- Reads PDFs from S3
- Extracts text using Bedrock Data Automation
- Handles multi-page documents
- Saves extracted text to S3

### 4. Document Storage

**Lambda**: `neptune-loader`

- Reads extracted text from S3
- Creates Document vertices in Neptune
- Stores full text in `document_text` property
- Adds metadata (title, date, source)
- No manual entity extraction needed!

### 5. S3 Export for Knowledge Base ← NEW!

**Lambda**: `neptune-exporter`

- Queries all Document vertices from Neptune
- Exports to S3 in Bedrock KB format
- Creates JSON files in `kb-documents/` prefix
- Each document includes: id, title, content, metadata

### 6. Knowledge Base Sync ← NEW!

**Lambda**: `kb-sync-trigger`

- Automatically triggers after S3 export
- Calls Bedrock Agent API to start ingestion
- Bedrock KB reads from S3 and:
  - Chunks documents (1000 tokens, 20% overlap)
  - Extracts entities automatically
  - Creates relationships automatically
  - Generates vector embeddings
  - Stores in vector database

### 7. Intelligent Query Interface

**Lambda**: `chat-handler`

- Receives natural language questions via API Gateway
- Queries Bedrock Knowledge Base using `retrieve_and_generate`
- KB performs:
  - Semantic search using embeddings
  - Entity and relationship traversal
  - Context-aware answer generation
- Returns answers with source citations

## 🎨 Customization

### Modify Extraction Prompts

Edit `lambda/data-extractor/lambda_function.py`:

```python
extraction_prompt = """
Your custom prompt here...
"""
```

### Add Custom Entity Types

Edit `lambda/entity-extractor/lambda_function.py`:

```python
# Add to entity types
"CUSTOM_TYPE": "Your custom entity type"
```

### Adjust Lambda Settings

Edit `lib/chronicling-america-stack.ts`:

```typescript
timeout: cdk.Duration.minutes(20),  // Increase timeout
memorySize: 3008,                   // Increase memory
```

## 🧹 Cleanup

### Destroy All Resources

```bash
./deploy.sh
# Choose "destroy" when prompted
```

### Manual Cleanup

```bash
cdk destroy LOCstack --force

# Delete S3 bucket (retained by default)
aws s3 rb s3://YOUR-BUCKET-NAME --force
```

## 📚 Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon Neptune Documentation](https://docs.aws.amazon.com/neptune/)
- [Chronicling America API](https://chroniclingamerica.loc.gov/about/api/)

## 🤝 Support

For issues:

1. Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
2. Review CloudWatch Logs
3. Run `./test-deployment.sh`
4. Check AWS service quotas
5. Verify IAM permissions

## 📝 License

This project is provided as-is for educational and research purposes.

## 🎉 Success!

After deployment, you'll have:

- ✅ Complete data extraction pipeline
- ✅ Graph database with historical data
- ✅ Chat API for querying
- ✅ Automated orchestration
- ✅ Monitoring and logging

**Start extracting historical insights!** 🚀
