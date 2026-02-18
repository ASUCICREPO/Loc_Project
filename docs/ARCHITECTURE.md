# Architecture Deep Dive

## System Architecture

### High-Level Architecture

The application follows a serverless, event-driven architecture on AWS, designed for scalability, cost-effectiveness, and maintainability. It enables users to explore historical documents from the Library of Congress through natural language conversations.

### Core Components

#### 1. Frontend Layer

**Technology:** Next.js 15 with React 18 and Material-UI

**Hosting:** AWS Amplify

**Features:**
- Responsive chat interface
- Persona-based response customization (General User, Congressional Staffer, Research Journalist, Law Student)
- Markdown rendering for formatted responses
- Source citations with document links
- Session persistence for conversation continuity
- Typing indicators and auto-scroll

#### 2. API Layer

**Technology:** Amazon API Gateway (REST API)

**Endpoints:**
- `POST /chat` - Main conversation handler

**Features:**
- CORS enabled for all origins
- Lambda proxy integration
- Public access without authentication

#### 3. Compute Layer

**Technology:** AWS Lambda Functions (Python 3.11)

**Functions:**
- **Chat Handler:** Main conversation handler with Knowledge Base search and LLM invocation (1024 MB, 60s timeout)
- **Fargate Trigger:** Launches ECS Fargate task for data collection (256 MB, 30s timeout)
- **KB Sync Trigger:** Triggers Knowledge Base ingestion jobs (256 MB, 2 min timeout)

**Container Compute:**
- **ECS Fargate:** Long-running data collection task (2 vCPU, 4 GB memory)
- **ECR:** Docker image repository for Fargate container

#### 4. AI/ML Layer

**Technology:** Amazon Bedrock

**Components:**
- **Knowledge Base with GraphRAG:** Semantic search with Neptune Analytics for relationship discovery
- **Claude 4.5 Sonnet:** Primary LLM for response generation
- **Claude 3 Haiku:** Context enrichment during document ingestion
- **Amazon Titan Text Embeddings V1:** Vector embeddings for semantic search (1024 dimensions)
- **AgentCore Memory:** Session-based conversation history storage

#### 5. Data Layer

**Storage:**
- **S3 Data Bucket:** Historical documents (`bills/`, `newspapers/` prefixes)
- **S3 Supplemental Bucket:** Bedrock Data Automation storage (30-day lifecycle)
- **S3 Builds Bucket:** Frontend deployment artifacts

**Graph Database:**
- **Neptune Analytics:** Stores entities and relationships extracted from documents

#### 6. Deployment Layer

**Technology:**
- **AWS CDK:** Infrastructure as Code (TypeScript)
- **CodeBuild:** CI/CD deployment pipeline
- **CloudFormation:** Resource provisioning

---

## Data Flow

### User Interaction Flow

1. User sends message through Next.js frontend hosted on AWS Amplify
2. Frontend calls API Gateway REST endpoint (`POST /chat`)
3. Chat Handler Lambda loads conversation history from AgentCore Memory
4. Lambda enhances vague queries using LLM (e.g., "tell me more" → specific topic)
5. Lambda queries Bedrock Knowledge Base using `retrieve` API
6. Knowledge Base performs semantic vector search with Neptune graph traversal
7. Lambda builds context from retrieved documents and conversation history
8. Lambda calls Bedrock LLM (Claude 3.5 Sonnet) with persona-specific system prompt
9. Lambda saves conversation to AgentCore Memory for future context
10. Response returned to user with formatted answer and source citations

### Data Ingestion Flow

1. Fargate Trigger Lambda launches ECS Fargate task
2. Fargate container runs `collect_bills.py` for data collection
3. **Congressional Bills Collection:**
   - Fetches bills from Congress.gov API (Congress 1-16, 1789-1875)
   - Gets text versions (priority: TXT > HTML > PDF)
   - Extracts text from PDFs using AWS Textract
   - Saves to S3 (`bills/` prefix) with metadata
4. **Newspaper Collection:**
   - Streams from Hugging Face dataset (`loc_chronicling_america_1770-1810`)
   - Extracts pre-OCR'd text content
   - Saves to S3 (`newspapers/` prefix) with metadata
5. **Knowledge Base Sync:**
   - Bills: Traditional `StartIngestionJob` API (~985 files)
   - Newspapers: Direct Ingestion API (`IngestKnowledgeBaseDocuments`) to bypass 1000-file limit (~59K files)
6. Bedrock Knowledge Base processes documents:
   - Chunking: 1500 tokens with 20% overlap
   - Embedding: Amazon Titan Text Embeddings V2
   - Context Enrichment: Claude Haiku extracts entities and relationships
   - Graph Storage: Neptune Analytics stores entity graph

### Knowledge Base Processing

**Chunking Strategy:**
- Fixed size: 1500 tokens per chunk
- Overlap: 20% for context continuity

**Embedding Model:**
- Amazon Titan Text Embeddings V2 (1024 dimensions)

**Context Enrichment:**
- Claude 3 Haiku automatically extracts:
  - Entities (people, places, dates, organizations)
  - Relationships between entities
  - Document metadata

**Graph Storage (Neptune Analytics):**
- Nodes: Documents, entities, concepts
- Edges: Relationships, references, citations
- Enables multi-hop queries and relationship traversal

---

## Security Considerations

### Authentication & Authorization

- Public API access (no authentication required for chat)
- IAM roles with least privilege access for all Lambda functions
- Bedrock service principals for Knowledge Base access
- ECS task roles for Fargate container permissions

### Data Protection

- Encryption at rest for all S3 buckets (S3-managed keys)
- Encryption in transit (HTTPS/TLS for all API calls)
- VPC with public subnets for Fargate tasks
- CloudWatch logging for audit trails

### IAM Roles

- **Lambda Execution Role:** Bedrock, AgentCore, S3 read, ECS RunTask
- **Fargate Task Role:** S3 read/write, Bedrock KB, Textract
- **Knowledge Base Role:** S3 access, Neptune, Bedrock models, Lambda invoke
- **CodeBuild Role:** Administrator access for deployment

---

## Scalability & Performance

### Auto-scaling Components

- Lambda functions scale automatically based on concurrent requests
- Neptune Analytics scales based on query load
- Amplify hosting scales with traffic (built-in CloudFront CDN)
- S3 scales automatically for storage

### Performance Optimizations

- **Semantic Search:** 20 results retrieved per query for comprehensive context
- **Query Enhancement:** LLM improves vague follow-up questions using conversation history
- **Session Memory:** AgentCore Memory provides sliding window of recent conversations (10 events)
- **Direct Ingestion API:** Bypasses 1000-file sync limit for large document collections
- **Fargate for Collection:** No Lambda timeout issues for long-running data collection (hours vs 15 minutes)

### Cost Optimizations

- **No NAT Gateway:** Public subnets only for Fargate tasks
- **S3 Lifecycle Rules:** Auto-delete temporary files (7-30 days)
- **Fargate On-Demand:** Pay only during data collection runs
- **Lambda Pay-per-Use:** No idle costs for API layer

---

## AWS Services Summary

| Category | Service | Purpose |
|----------|---------|---------|
| **Frontend** | Amplify | Next.js hosting with CDN |
| **API** | API Gateway | REST API endpoints |
| **Compute** | Lambda | Chat handler, triggers |
| **Compute** | ECS Fargate | Data collection container |
| **Compute** | ECR | Container image registry |
| **AI/ML** | Bedrock KB | Semantic search with GraphRAG |
| **AI/ML** | Bedrock LLM | Claude 4.5 Sonnet responses |
| **AI/ML** | AgentCore Memory | Conversation history |
| **AI/ML** | Textract | PDF text extraction |
| **Database** | Neptune Analytics | Entity graph storage |
| **Storage** | S3 | Documents, builds, temp files |
| **Networking** | VPC | Network isolation |
| **Security** | IAM | Access control |
| **Monitoring** | CloudWatch | Logging |
| **Deployment** | CodeBuild | CI/CD pipeline |
| **Deployment** | CloudFormation | Infrastructure provisioning |
