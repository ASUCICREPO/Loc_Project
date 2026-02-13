# Technical Documentation - Cultural Heritage Chatbot

**Version**: 1.0.0
**Last Updated**: February 2026

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Technology Stack](#technology-stack)
3. [Infrastructure Components](#infrastructure-components)
4. [API Specifications](#api-specifications)
5. [Frontend Architecture](#frontend-architecture)
6. [Backend Services](#backend-services)
7. [Data Models](#data-models)
8. [Persona System](#persona-system)
9. [Knowledge Base & GraphRAG](#knowledge-base--graphrag)
10. [Memory System](#memory-system)
11. [Security & IAM](#security--iam)
12. [Deployment Architecture](#deployment-architecture)
13. [Development Guide](#development-guide)
14. [Configuration Management](#configuration-management)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Next.js 15 Frontend (AWS Amplify)                        │  │
│  │  - React 18 Components                                     │  │
│  │  - Material-UI                                             │  │
│  │  - Persona Selection Interface                             │  │
│  │  - Markdown Rendering                                      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    HTTPS (REST API)
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                      API Gateway Layer                             │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  Amazon API Gateway                                        │   │
│  │  - /chat (POST)     - Chat endpoint                       │   │
│  │  - /health (GET)    - Health check                        │   │
│  │  - /collect (POST)  - Data collection trigger             │   │
│  │  - CORS enabled                                            │   │
│  └───────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
                              │
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                      Lambda Functions Layer                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ Chat Handler     │  │ KB Sync Trigger  │  │ Fargate Trigger│  │
│  │ - Strands Agent  │  │ - Start KB Sync  │  │ - Run ECS Task │  │
│  │ - Memory Hooks   │  │ - Monitor Status │  │ - Data Collect │  │
│  │ - Persona Logic  │  └──────────────────┘  └────────────────┘  │
│  └──────────────────┘                                             │
└───────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌─────────▼────────┐  ┌───────▼───────────┐
│  Bedrock Agent │  │ Knowledge Base   │  │ AgentCore Memory  │
│  - Claude 3.5  │  │ - GraphRAG       │  │ - Session History │
│  - Strands SDK │  │ - Neptune Graph  │  │ - Context Mgmt    │
│  - Tool Calling│  │ - OpenSearch     │  │ - Auto Retrieval  │
└────────────────┘  │ - Metadata Filter│  └───────────────────┘
                    │ - 20 Results     │
                    └──────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼──────────┐  ┌───────▼──────────┐  ┌──────▼──────────┐
│ Amazon Neptune   │  │ OpenSearch       │  │ S3 Buckets      │
│ - Graph Database │  │ - Vector Search  │  │ - Data Storage  │
│ - Relationships  │  │ - Embeddings     │  │ - Bills         │
│ - Entity Store   │  │ - Semantic Query │  │ - Newspapers    │
└──────────────────┘  └──────────────────┘  └─────────────────┘
```

### Data Flow

1. **User Query** → Frontend (Next.js)
2. **API Request** → API Gateway → Lambda (Chat Handler)
3. **Agent Processing**:
   - Memory retrieval (previous context)
   - Knowledge Base search (with metadata filtering)
   - Claude model invocation via Strands Agent
   - Response generation
   - Memory storage (conversation history)
4. **Response** → Frontend → User Display

---

## Technology Stack

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Next.js** | 15.5.12 | React framework with SSR/SSG |
| **React** | 18 | UI library |
| **Material-UI** | Latest | Component library |
| **React Markdown** | Latest | Markdown rendering for bot responses |
| **TypeScript** | Latest | Type safety |
| **Node.js** | 20+ | Runtime environment |

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **AWS CDK** | 2.179.0 | Infrastructure as code |
| **TypeScript** | 5.3.3 | CDK stack definitions |
| **Python** | 3.11 | Lambda functions |
| **AWS Lambda** | Runtime 3.11 | Serverless compute |
| **AWS Bedrock** | - | AI model access (Claude 3.5 Sonnet) |
| **Strands SDK** | Latest | Agent framework with tool calling |
| **bedrock-agentcore** | Latest | Memory management |

### Data & Storage

| Service | Purpose |
|---------|---------|
| **Amazon Neptune Analytics** | Graph database for relationships |
| **Amazon OpenSearch** | Vector search and embeddings |
| **Amazon S3** | Document storage (bills, newspapers) |
| **AWS Bedrock Knowledge Base** | GraphRAG with semantic search |

### Infrastructure

| Service | Purpose |
|---------|---------|
| **Amazon API Gateway** | REST API management |
| **AWS Lambda** | Serverless functions |
| **Amazon ECS Fargate** | Containerized data collection |
| **Amazon ECR** | Docker image registry |
| **AWS Amplify** | Frontend hosting and CI/CD |
| **AWS CodeBuild** | Build automation |
| **Amazon CloudWatch** | Logging and monitoring |

---

## Infrastructure Components

### S3 Buckets

#### 1. Data Bucket
**Name**: `{projectName}-data-{account}-{region}`

- Stores raw historical documents
- **Prefixes**:
  - `bills/` - Congressional bills (1789-1875)
  - `newspapers/` - Historical newspapers (1770-1810)
- **Access**: Bedrock service, Lambda functions, Fargate tasks
- **Lifecycle**: Auto-delete on stack destruction

#### 2. Transformation Bucket
**Name**: `{projectName}-transformation-{account}-{region}`

- Intermediate storage for Knowledge Base processing
- **Lifecycle**: 7-day expiration for temp files
- **Access**: Bedrock Knowledge Base

#### 3. Supplemental Bucket
**Name**: `{projectName}-supp-{account}-{region}`

- Bedrock Data Automation supplemental data
- **Lifecycle**: 30-day expiration
- **Access**: Fargate tasks, Bedrock service

#### 4. Builds Bucket
**Name**: `{projectName}-builds-{account}-{region}`

- Frontend build artifacts for Amplify
- **Access**: Amplify service

### VPC Configuration

```typescript
VPC:
  - Max AZs: 2
  - NAT Gateways: 0 (cost optimization)
  - Subnets: Public only (CIDR /24)
  - Security Groups: Fargate tasks
```

### ECS Cluster

**Name**: `{projectName}-cluster`

- **Purpose**: Run data collection Fargate tasks
- **Container Insights**: Enabled
- **Task Definition**:
  - CPU: 2048 (2 vCPU)
  - Memory: 4096 MB (4 GB)
  - Image: ECR repository (`{projectName}-collector:latest`)

---

## API Specifications

### Base URL

```
https://{api-id}.execute-api.{region}.amazonaws.com/prod/
```

### Endpoints

#### 1. POST /chat

**Purpose**: Process user chat messages with persona-based responses

**Request**:
```json
{
  "message": "What is the First Amendment?",
  "persona": "interested_person",
  "user_id": "user-123-abc",
  "session_id": "session-456-def",
  "language": "en"
}
```

**Parameters**:
- `message` (required): User's question
- `persona` (optional): One of `interested_person`, `policy_analyst`, `research_journalist`, `law_student`
- `user_id` (optional): Unique user identifier for memory
- `session_id` (optional): Session identifier for conversation context
- `language` (optional): Language code (currently `en` only)

**Response** (200 OK):
```json
{
  "message": "The First Amendment protects five fundamental freedoms...",
  "answer": "The First Amendment protects five fundamental freedoms...",
  "sources": [
    {
      "document_id": "s3://bucket/bills/congress-1/hr-1.txt",
      "url": "https://www.congress.gov/bill/1st-congress/house-bill/1",
      "title": "Congress 1 - HR 1",
      "type": "Bill",
      "content": "Excerpt from the document...",
      "score": 0.85,
      "metadata": {
        "entity_type": "bill",
        "congress": "1",
        "bill_type": "HR",
        "bill_number": "1",
        "year": "1789",
        "source": "congress.gov"
      }
    }
  ],
  "entities": [],
  "session_id": "session-456-def"
}
```

**Error Response** (400/500):
```json
{
  "error": "Message is required"
}
```

#### 2. GET /health

**Purpose**: Health check endpoint

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "loc-histora-chat",
  "knowledge_base_id": "KB123ABC",
  "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "memory_enabled": true
}
```

#### 3. POST /collect

**Purpose**: Trigger data collection Fargate task

**Request**:
```json
{
  "action": "collect"
}
```

**Response** (200 OK):
```json
{
  "message": "Collection task started",
  "task_arn": "arn:aws:ecs:..."
}
```

### CORS Configuration

All endpoints support CORS with:
- **Allow-Origins**: `*` (all origins)
- **Allow-Methods**: `GET, POST, OPTIONS`
- **Allow-Headers**: `Content-Type, Authorization`

---

## Frontend Architecture

### Component Structure

```
frontend/
├── app/
│   ├── components/
│   │   ├── ChatBody.jsx           # Main chat interface
│   │   ├── BotReply.jsx           # Bot message rendering
│   │   ├── UserReply.jsx          # User message rendering
│   │   ├── MarkdownContent.jsx    # Markdown parser
│   │   └── HistoraChatbot.jsx     # Alternative chatbot UI
│   ├── config/
│   │   └── svg-paths.js           # SVG icon definitions
│   ├── globals.css                # Global styles
│   ├── layout.tsx                 # Root layout
│   └── page.tsx                   # Main page
├── public/
│   └── logo.png                   # Logo asset
├── next.config.js                 # Next.js configuration
└── package.json                   # Dependencies
```

### Key Components

#### ChatBody Component

**File**: [frontend/app/components/ChatBody.jsx](frontend/app/components/ChatBody.jsx)

**State Management**:
```javascript
const [messages, setMessages] = useState([])       // Chat history
const [selectedPersona, setSelectedPersona] = useState('')  // Current persona
const [inputValue, setInputValue] = useState('')   // Input text
const [isLoading, setIsLoading] = useState(false)  // API loading state
const [isTyping, setIsTyping] = useState(false)    // Typing indicator
const [sessionId, setSessionId] = useState('')     // Session ID
const [userId, setUserId] = useState('')           // User ID from localStorage
```

**Features**:
- Persona selection (dropdown + buttons)
- Real-time message streaming
- Markdown rendering for bot responses
- Source citations display
- Session persistence
- Typing indicators
- Auto-scroll to latest message

**Persona Management**:
```javascript
const personas = {
  'interested_person': 'Interested Person',
  'policy_analyst': 'Policy Analyst',
  'research_journalist': 'Research Journalist',
  'law_student': 'Law Student'
}
```

#### API Integration

**Endpoint Construction**:
```javascript
const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL ||
               process.env.NEXT_PUBLIC_CHAT_ENDPOINT
const chatEndpoint = `${apiUrl}chat`
```

**Request Format**:
```javascript
const response = await fetch(chatEndpoint, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: messageToSend,
    persona: selectedPersona,
    language: currentLanguage,
    user_id: userId,
    session_id: sessionId,
  }),
})
```

### Styling

- **Design System**: Custom CSS with Tailwind-like utilities
- **Color Palette**:
  - Primary: `#28333a` (Dark header)
  - Background: `#f4eee5` (Warm beige)
  - Accent: `rgba(198,156,115,0.3)` (Light brown)
- **Typography**: Inter font family
- **Responsive**: Fixed fullscreen layout

---

## Backend Services

### Lambda Functions

#### 1. Chat Handler Lambda

**File**: [backend/lambda/chat-handler/lambda_function.py](backend/lambda/chat-handler/lambda_function.py)

**Configuration**:
- Runtime: Python 3.11
- Memory: 1024 MB
- Timeout: 60 seconds
- Handler: `lambda_function.lambda_handler`

**Key Features**:
- **Strands Agent**: Tool-calling framework
- **Memory Hooks**: Auto context retrieval and storage
- **Metadata Filtering**: Extract filters from query (year, congress, document type)
- **Knowledge Base Search**: 20 results with semantic search
- **Persona Prompts**: Dynamic system prompts based on user type

**Environment Variables**:
- `KNOWLEDGE_BASE_ID`: Bedrock KB identifier
- `MODEL_ID`: Bedrock model (Claude 3.5 Sonnet)
- `DATA_BUCKET_NAME`: S3 bucket for documents
- `AGENTCORE_MEMORY_ID`: Memory ID for conversation history
- `AWS_REGION`: AWS region

**Dependencies** (requirements.txt):
```
strands
bedrock-agentcore
boto3
```

#### 2. KB Sync Trigger Lambda

**Purpose**: Trigger Knowledge Base ingestion after data collection

**Configuration**:
- Runtime: Python 3.11
- Memory: 256 MB
- Timeout: 2 minutes

**Workflow**:
1. Receive S3 event notification (optional)
2. Query Knowledge Base for data source IDs
3. Start ingestion job for bills data source
4. Monitor ingestion status

#### 3. Fargate Trigger Lambda

**Purpose**: Launch ECS Fargate task for data collection

**Configuration**:
- Runtime: Python 3.11
- Memory: 256 MB
- Timeout: 30 seconds

**Workflow**:
1. Receive trigger request
2. Construct ECS RunTask parameters
3. Launch Fargate task in public subnet
4. Return task ARN

#### 4. KB Transformation Lambda

**Purpose**: Transform documents for GraphRAG structure

**Configuration**:
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 60 seconds

**Called By**: Bedrock Knowledge Base during ingestion

---

## Data Models

### Message Format

```typescript
interface Message {
  id: string
  type: 'user' | 'bot'
  content: string | JSX.Element
  timestamp: Date
  sources?: Source[]
}
```

### Source Format

```typescript
interface Source {
  document_id: string        // S3 URI
  url: string                // Original source URL
  title: string              // Display title
  type: 'Bill' | 'Newspaper' | 'Document'
  content: string            // Excerpt (300 chars)
  score: number              // Relevance score (0-1)
  metadata: {
    entity_type: 'bill' | 'newspaper'
    congress?: string        // "1" to "16"
    bill_type?: string       // "HR", "S", "HJRES", etc.
    bill_number?: string     // "1", "2", etc.
    newspaper_title?: string // Newspaper name
    issue_date?: string      // Publication date
    year?: string            // "1789" to "1875"
    source?: string          // "congress.gov", etc.
  }
}
```

### Knowledge Base Document Metadata

**Bills**:
```json
{
  "entity_type": "bill",
  "congress": "5",
  "bill_type": "HR",
  "bill_number": "123",
  "year": "1798",
  "source": "congress.gov",
  "source_url": "https://www.congress.gov/bill/5th-congress/house-bill/123"
}
```

**Newspapers**:
```json
{
  "entity_type": "newspaper",
  "newspaper_title": "Pennsylvania Gazette",
  "issue_date": "1776-07-04",
  "year": "1776",
  "source": "loc_chronicling_america",
  "source_url": "https://chroniclingamerica.loc.gov/..."
}
```

---

## Persona System

### Persona Definitions

#### 1. Interested Person
**Target**: General public, students, history enthusiasts

**System Prompt Addition**:
```
You are helping a general user explore history.
- Be clear and informative using only document content
- If information isn't available, suggest what topics ARE in the archives
- Make the available historical content engaging
```

**Response Style**:
- Clear, accessible language
- Educational tone
- Historical context from documents
- Minimal jargon

#### 2. Policy Analyst
**Target**: Policy professionals, government researchers

**System Prompt Addition**:
```
You are assisting Congressional staff with research.
- Be precise and cite specific documents
- Only reference what's in the retrieved documents
- Use formal, professional language
```

**Response Style**:
- Analytical and structured
- Focus on precedents
- Constitutional interpretations
- Policy implications

#### 3. Research Journalist
**Target**: Writers, journalists, content creators

**System Prompt Addition**:
```
You are helping journalists research stories.
- Only provide context found in the documents
- Quote directly from historical sources when possible
- Be clear about what the archives do and don't contain
```

**Response Style**:
- Narrative and contextual
- Cultural background
- Story-driven explanations
- Direct quotations

#### 4. Law Student
**Target**: Legal professionals, law students

**System Prompt Addition**:
```
You are helping law students with research.
- Only reference cases and provisions found in the documents
- Be educational but stick to document content
- Clearly distinguish between what's in archives vs. not available
```

**Response Style**:
- Precise legal terminology
- Case references
- Legal reasoning
- Statutory interpretation

### Implementation

**Backend** ([lambda/chat-handler/lambda_function.py:443-504](backend/lambda/chat-handler/lambda_function.py#L443-L504)):
```python
def get_system_prompt(persona: str) -> str:
    base_prompt = """You are Histora, an AI assistant for the Library of Congress.

    ABSOLUTE RULES:
    1. You MUST ALWAYS call search_historical_documents for EVERY question
    2. You can ONLY answer using information in retrieved documents
    3. FORBIDDEN from using pre-trained knowledge
    ...
    """

    persona_additions = {
        'congressional_staffer': "...",
        'research_journalist': "...",
        'law_student': "...",
        'general': "..."
    }

    return base_prompt + persona_additions.get(persona, persona_additions['general'])
```

**Frontend** ([frontend/app/components/ChatBody.jsx:54-59](frontend/app/components/ChatBody.jsx#L54-L59)):
```javascript
const personas = {
  'interested_person': 'Interested Person',
  'policy_analyst': 'Policy Analyst',
  'research_journalist': 'Research Journalist',
  'law_student': 'Law Student'
}
```

---

## Knowledge Base & GraphRAG

### Architecture

**Knowledge Base Type**: Graph Knowledge Base with Neptune Analytics

**Configuration**:
```typescript
new bedrockConstructs.GraphKnowledgeBase(this, "ChroniclingAmericaKB", {
  name: `${projectName}-knowledge-base`,
  embeddingModel: BedrockFoundationModel.TITAN_EMBED_TEXT_V2_1024,
  instruction: "You are a historical research assistant...",
  existingRole: knowledgeBaseRole
})
```

### Data Sources

#### 1. Congress Bills Data Source
- **Name**: `congress-bills`
- **Description**: Congressional bills from Congress 1-16 (1789-1875)
- **S3 Prefix**: `bills/`
- **Chunking**: Fixed size (1500 tokens, 20% overlap)
- **Context Enrichment**: Claude Haiku for entity extraction

#### 2. Newspapers Data Source
- **Name**: `newspapers`
- **Description**: Chronicling America newspapers 1770-1810
- **S3 Prefix**: `newspapers/`
- **Ingestion Method**: Direct Ingestion API (no 1000-file limit)
- **Chunking**: Fixed size (1500 tokens, 20% overlap)
- **Context Enrichment**: Claude Haiku

### Metadata Filtering

**Query Processing** ([lambda/chat-handler/lambda_function.py:50-125](backend/lambda/chat-handler/lambda_function.py#L50-L125)):

```python
def extract_filters_from_query(query: str) -> dict:
    """
    Extract metadata filters from user query.

    Patterns:
    - Year: 4-digit number (1770-1830)
    - Congress: "5th congress", "congress 5", "fifth congress"
    - Document type: keywords trigger entity_type filter
    - Bill type: "H.R.", "S.", "HJRES", etc.
    """
    filters = {}

    # Extract year
    year_match = re.search(r'\b(17[7-9]\d|18[0-2]\d)\b', query)
    if year_match:
        filters['year'] = year_match.group(1)

    # Extract congress number
    congress_patterns = [
        r'(\d+)(?:st|nd|rd|th)?\s*congress',
        r'congress\s*(\d+)',
        ...
    ]

    # Calculate congress from year if not explicit
    if 'year' in filters and 'congress' not in filters:
        year = int(filters['year'])
        if year >= 1789:
            approx_congress = ((year - 1789) // 2) + 1
            filters['congress'] = str(approx_congress)

    return filters
```

**Filter Construction** ([lambda/chat-handler/lambda_function.py:128-183](backend/lambda/chat-handler/lambda_function.py#L128-L183)):

```python
def build_retrieval_filter(filters: dict) -> dict:
    """
    Build Bedrock KB filter syntax.

    Example output:
    {
      'andAll': [
        {'equals': {'key': 'year', 'value': '1798'}},
        {'equals': {'key': 'congress', 'value': '5'}},
        {'equals': {'key': 'entity_type', 'value': 'bill'}}
      ]
    }
    """
```

### Retrieval Configuration

**Search Parameters**:
```python
retrieval_config = {
    'vectorSearchConfiguration': {
        'numberOfResults': 20,              # Top 20 results
        'overrideSearchType': 'SEMANTIC',   # Semantic search
        'filter': kb_filter                 # Metadata filters
    }
}
```

**Fallback Strategy**:
1. Try with metadata filters
2. If no results, retry without filters
3. Return all relevant documents

### GraphRAG Benefits

- **Relationship Extraction**: Neptune identifies connections between bills, people, events
- **Entity Recognition**: Automatic extraction of names, dates, locations
- **Contextual Search**: Graph traversal enhances semantic search
- **Multi-hop Queries**: "Who influenced what legislation" queries work naturally

---

## Memory System

### AgentCore Memory

**Type**: AWS Bedrock AgentCore Memory

**Configuration**:
- **Memory ID**: Set via `create_memory.py` script before deployment
- **Stored in**: `cdk.context.json` under `agentcore-memory-id`

### Memory Strategies

**Namespaces**:
1. **Conversation History**: Full turn-by-turn dialogue
2. **Context Memory**: Key facts and entities
3. **Session Memory**: Per-session context

**Retrieved via**:
```python
memories = memory_client.retrieve_memories(
    memory_id=AGENTCORE_MEMORY_ID,
    namespace=namespace.format(actorId=actor_id, sessionId=""),
    query=user_query,
    top_k=3
)
```

### Memory Hooks

**Implementation** ([lambda/chat-handler/lambda_function.py:324-436](backend/lambda/chat-handler/lambda_function.py#L324-L436)):

#### 1. Context Retrieval Hook

**Event**: `MessageAddedEvent` (before processing user message)

**Function**: `retrieve_context()`

**Workflow**:
1. Extract user query from message
2. Retrieve top 3 memories from each namespace
3. Inject context into user message as prefix:
   ```
   Previous Context:
   [CONVERSATION] User asked about First Amendment
   [CONTEXT] First Amendment protects five freedoms

   Current Question: Tell me more about freedom of speech
   ```

**Code**:
```python
def retrieve_context(self, event: MessageAddedEvent):
    messages = event.agent.messages
    user_query = messages[-1]["content"][0]["text"]

    all_context = []
    for context_type, namespace in self.namespaces.items():
        memories = self.client.retrieve_memories(
            memory_id=self.memory_id,
            namespace=namespace,
            query=user_query,
            top_k=3
        )
        for memory in memories:
            all_context.append(f"[{context_type}] {memory['text']}")

    # Inject into message
    messages[-1]["content"][0]["text"] = f"""Previous Context:
{context}

Current Question: {original_query}"""
```

#### 2. Conversation Storage Hook

**Event**: `AfterInvocationEvent` (after agent generates response)

**Function**: `save_conversation()`

**Workflow**:
1. Extract user query and agent response
2. Clean responses (remove `<thinking>` tags)
3. Store as memory event with USER/ASSISTANT messages

**Code**:
```python
def save_conversation(self, event: AfterInvocationEvent):
    messages = event.agent.messages

    # Extract latest Q&A pair
    user_query = extract_user_message(messages)
    agent_response = extract_agent_response(messages)

    # Save to memory
    self.client.create_event(
        memory_id=self.memory_id,
        actor_id=self.actor_id,
        session_id=self.session_id,
        messages=[
            (user_query, "USER"),
            (agent_response, "ASSISTANT")
        ]
    )
```

### Memory Lifecycle

**Per Request**:
1. User sends message with `user_id` and `session_id`
2. Memory hook retrieves relevant past context (auto)
3. Agent processes with enhanced context
4. Memory hook stores conversation (auto)

**Session Persistence**:
- `user_id`: Persistent across sessions (stored in `localStorage`)
- `session_id`: Unique per browser tab/conversation
- Memory retrieval spans all sessions for `user_id`

---

## Security & IAM

### IAM Roles

#### 1. Knowledge Base Role

**Assumed By**: `bedrock.amazonaws.com`

**Permissions**:
```json
{
  "S3": ["GetObject", "ListBucket", "PutObject", "DeleteObject"],
  "Neptune": ["neptune-graph:*", "neptune-db:*"],
  "Bedrock": ["InvokeModel"],
  "Lambda": ["InvokeFunction"]
}
```

**Resources**:
- Data bucket, transformation bucket, supplemental bucket
- All Neptune resources
- Bedrock models: Titan Embeddings, Claude Haiku
- KB transformation Lambda function

#### 2. Lambda Execution Role

**Assumed By**: `lambda.amazonaws.com`

**Managed Policies**:
- `AWSLambdaBasicExecutionRole` (CloudWatch Logs)

**Inline Policies**:
```json
{
  "Bedrock": [
    "InvokeModel",
    "InvokeModelWithResponseStream",
    "Retrieve",
    "RetrieveAndGenerate",
    "Rerank",
    "StartIngestionJob",
    "GetIngestionJob"
  ],
  "AgentCore": [
    "CreateEvent",
    "ListEvents",
    "RetrieveMemories",
    "RetrieveMemoryRecords",
    "GetMemory"
  ],
  "S3": ["GetObject", "ListBucket"],
  "STS": ["GetCallerIdentity"]
}
```

#### 3. Fargate Task Role

**Assumed By**: `ecs-tasks.amazonaws.com`

**Permissions**:
```json
{
  "S3": ["GetObject", "PutObject", "ListBucket", "DeleteObject"],
  "Bedrock": [
    "StartIngestionJob",
    "IngestKnowledgeBaseDocuments",
    "InvokeModel"
  ],
  "Textract": [
    "DetectDocumentText",
    "StartDocumentTextDetection"
  ]
}
```

### S3 Bucket Policies

**Bedrock Service Access**:
```json
{
  "Effect": "Allow",
  "Principal": {"Service": "bedrock.amazonaws.com"},
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": ["arn:aws:s3:::bucket/*"],
  "Condition": {
    "StringEquals": {"aws:SourceAccount": "ACCOUNT_ID"}
  }
}
```

**Amplify Service Access**:
```json
{
  "Effect": "Allow",
  "Principal": {"Service": "amplify.amazonaws.com"},
  "Action": [
    "s3:GetObject", "s3:ListBucket", "s3:GetBucketAcl"
  ],
  "Resource": ["arn:aws:s3:::builds-bucket/*"]
}
```

### API Gateway Security

- **CORS**: Enabled for all origins (`*`)
- **Authentication**: None (public API)
- **Rate Limiting**: AWS default (10,000 req/s)
- **Throttling**: Configurable per stage

### Data Encryption

- **S3**: Server-side encryption (S3-managed keys)
- **Transit**: HTTPS/TLS for all API calls
- **Bedrock**: AWS-managed encryption for model invocations
- **Neptune**: Encryption at rest enabled

---

## Deployment Architecture

### CodeBuild Pipeline

**Purpose**: Build and deploy frontend to Amplify

**Buildspec**:
```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: out
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

### Amplify Hosting

**Platform**: AWS Amplify (WEB)

**Environment Variables**:
```
NEXT_PUBLIC_API_BASE_URL=https://{api-id}.execute-api.{region}.amazonaws.com/prod/
NEXT_PUBLIC_CHAT_ENDPOINT=https://{api-id}.execute-api.{region}.amazonaws.com/prod/
NEXT_PUBLIC_AWS_REGION={region}
AMPLIFY_MONOREPO_APP_ROOT=frontend
```

**Custom Rules**:
```
Source: /<*>
Target: /index.html
Status: 404-200  (SPA routing)
```

### Deployment Flow

```
1. Developer → git push → GitHub
2. CloudShell → ./deploy.sh
3. CDK Bootstrap (if first time)
4. Create AgentCore Memory → save ID to cdk.context.json
5. CDK Deploy → CloudFormation stacks
6. CodeBuild → Amplify deployment
7. Output: Amplify URL (https://main.{app-id}.amplifyapp.com)
```

### Stack Outputs

```bash
# Example outputs
DataBucketName: loc-project-data-123456-us-east-1
KnowledgeBaseId: ABC123DEF
APIGatewayURL: https://xyz.execute-api.us-east-1.amazonaws.com/prod/
ChatEndpoint: https://xyz.execute-api.us-east-1.amazonaws.com/prod/chat
AmplifyAppUrl: https://main.d123abc.amplifyapp.com
AgentCoreMemoryId: mem-abc123
```

---

## Development Guide

### Prerequisites

**System Requirements**:
- Node.js 20+
- Python 3.9+
- AWS CLI configured
- Docker (for local Lambda development)
- AWS CDK CLI 2.x

### Local Development

#### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

**Environment Variables** (`.env.local`):
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:3000
NEXT_PUBLIC_CHAT_ENDPOINT=https://your-api-gateway.amazonaws.com/chat
```

#### Backend

```bash
cd backend
npm install
npm run build      # Compile TypeScript
npm run watch      # Watch for changes
```

**CDK Commands**:
```bash
cdk diff           # Preview changes
cdk synth          # Generate CloudFormation
cdk deploy         # Deploy to AWS
cdk destroy        # Delete all resources
```

### Testing

#### Frontend Testing

```bash
cd frontend
npm run lint       # ESLint
npm run type-check # TypeScript validation
npm test          # Jest (if configured)
```

#### Backend Testing

```bash
cd backend
python test_backend.py           # Test Lambda functions
python test_complete_pipeline.py # End-to-end test
python test_queries.py           # Knowledge Base queries
```

### Debugging

#### Lambda Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/loc-project-chat-handler --follow

# Specific time range
aws logs filter-log-events \
  --log-group-name /aws/lambda/loc-project-chat-handler \
  --start-time $(date -u -d '5 minutes ago' +%s)000
```

#### API Gateway

```bash
# Test endpoint
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the First Amendment?"}'
```

### Code Style

**Frontend**:
- ESLint with Next.js config
- Prettier for formatting
- JSX for React components

**Backend**:
- TypeScript for CDK stacks
- Python PEP 8 for Lambda functions
- Type hints for Python code

---

## Configuration Management

### Environment Variables

#### Frontend

**File**: `frontend/.env.local` (not committed)

```env
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
NEXT_PUBLIC_CHAT_ENDPOINT=https://api.example.com/chat
```

**Usage**:
```javascript
const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL
```

#### Backend Lambda

**Set in CDK Stack** ([lib/chronicling-america-stack.ts:692-697](backend/lib/chronicling-america-stack.ts#L692-L697)):

```typescript
environment: {
  KNOWLEDGE_BASE_ID: knowledgeBaseId,
  MODEL_ID: bedrockModelId,
  DATA_BUCKET_NAME: dataBucket.bucketName,
  AGENTCORE_MEMORY_ID: agentCoreMemoryId
}
```

### CDK Context

**File**: `backend/cdk.context.json`

**Structure**:
```json
{
  "agentcore-memory-id": "mem-abc123def",
  "@aws-cdk/aws-lambda:recognizeLayerVersion": true,
  ...
}
```

**Usage**:
```typescript
const memoryId = this.node.tryGetContext('agentcore-memory-id')
```

### Feature Flags

**CDK Feature Flags** (cdk.json):
```json
{
  "context": {
    "@aws-cdk/core:enablePartitionLiterals": true,
    "@aws-cdk/aws-apigateway:disableCloudWatchRole": false,
    ...
  }
}
```

### Secrets Management

**Not Currently Used**, but recommended approach:

```typescript
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager'

const apiKey = secretsmanager.Secret.fromSecretNameV2(
  this, 'ApiKey', 'congress-api-key'
)

// Reference in Lambda
environment: {
  API_KEY_SECRET_ARN: apiKey.secretArn
}
```

---

## Performance Optimization

### Frontend

- **Static Generation**: Next.js builds static pages
- **Code Splitting**: Automatic route-based splitting
- **Image Optimization**: Next.js Image component
- **Lazy Loading**: React.lazy for components

### Backend

- **Lambda Cold Start**: < 2 seconds with bundled dependencies
- **Knowledge Base**: 20 results in ~1-2 seconds
- **Memory Retrieval**: < 500ms for top-3 memories
- **Response Streaming**: Bedrock streaming enabled

### Caching

- **Frontend**: Browser cache for static assets
- **API Gateway**: Response caching (optional, not enabled)
- **Knowledge Base**: Vector index cached by Bedrock

---

## Monitoring & Observability

### CloudWatch Metrics

**Lambda Metrics**:
- Invocations
- Duration
- Errors
- Throttles
- Concurrent executions

**API Gateway**:
- Request count
- Latency (4xx, 5xx errors)
- Integration latency

**ECS Fargate**:
- CPU utilization
- Memory utilization
- Task count

### Logging

**Log Groups**:
- `/aws/lambda/{projectName}-chat-handler`
- `/aws/lambda/{projectName}-kb-sync-trigger`
- `/aws/lambda/{projectName}-fargate-trigger`
- `/ecs/{projectName}-collector`

**Retention**: 7 days (configurable)

### Alarms (Recommended)

```typescript
const errorAlarm = new cloudwatch.Alarm(this, 'LambdaErrors', {
  metric: chatHandlerFunction.metricErrors(),
  threshold: 10,
  evaluationPeriods: 1
})
```

---

## Troubleshooting

### Common Issues

#### 1. Lambda Timeout

**Symptom**: 60-second timeout errors

**Solution**:
- Reduce Knowledge Base results from 20 to 10
- Increase Lambda timeout to 120 seconds
- Check Bedrock model availability

#### 2. Memory Not Working

**Symptom**: No conversation context

**Check**:
```bash
# Verify memory ID is set
cat backend/cdk.context.json | grep agentcore-memory-id

# Re-create memory if needed
cd backend
python scripts/create_memory.py
```

#### 3. Knowledge Base Returns No Results

**Check**:
- Data sources synced: AWS Console → Bedrock → Knowledge Bases
- S3 bucket has documents in `bills/` or `newspapers/` prefix
- Metadata format is correct

**Debug**:
```python
# Test retrieval directly
import boto3
client = boto3.client('bedrock-agent-runtime')
response = client.retrieve(
    knowledgeBaseId='YOUR_KB_ID',
    retrievalQuery={'text': 'First Amendment'}
)
print(response['retrievalResults'])
```

#### 4. CORS Errors

**Symptom**: Browser console shows CORS errors

**Fix**:
- Verify API Gateway CORS settings
- Check `Access-Control-Allow-Origin: *` in Lambda response headers
- Clear browser cache

---

## Cost Estimation

### Monthly Costs (Approximate)

**Assuming 10,000 chat requests/month**:

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 10K invocations × 5s × 1GB | ~$1 |
| API Gateway | 10K requests | ~$0.04 |
| Bedrock (Claude 3.5) | 10K × 1K tokens avg | ~$30 |
| Bedrock KB | 10K retrievals | ~$2 |
| Neptune Analytics | Graph storage | ~$100/mo |
| OpenSearch | Vector index | ~$50/mo |
| S3 | 100GB storage | ~$2.30 |
| Amplify | Hosting + builds | ~$10 |
| **Total** | | **~$195/mo** |

**Notes**:
- Neptune Analytics is the largest cost component
- Bedrock costs scale with token usage
- Free tier covers Lambda, API Gateway, S3 (first year)

---

## Future Enhancements

### Planned Features

1. **Multi-language Support**: Spanish, French translations
2. **Advanced Filters**: Date range, document type selectors in UI
3. **Export**: Download conversation as PDF/Markdown
4. **Bookmarks**: Save favorite documents
5. **User Accounts**: Persistent user profiles
6. **Analytics**: Usage tracking, popular queries
7. **Admin Dashboard**: Monitor system health, usage stats

### Technical Improvements

1. **Caching Layer**: Redis for frequently accessed documents
2. **Rate Limiting**: Per-user API throttling
3. **A/B Testing**: Persona effectiveness experiments
4. **Reranking**: Use Bedrock reranker for better results
5. **Streaming Responses**: Real-time token streaming to frontend
6. **Vector Store Optimization**: Fine-tune embedding parameters

---

## References

### Documentation

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Bedrock Developer Guide](https://docs.aws.amazon.com/bedrock/)
- [Strands Agent SDK](https://github.com/aws-samples/strands)
- [Next.js Documentation](https://nextjs.org/docs)
- [Material-UI Components](https://mui.com/)

### Source Code

- Main Stack: [backend/lib/chronicling-america-stack.ts](backend/lib/chronicling-america-stack.ts)
- Chat Handler: [backend/lambda/chat-handler/lambda_function.py](backend/lambda/chat-handler/lambda_function.py)
- Frontend: [frontend/app/components/ChatBody.jsx](frontend/app/components/ChatBody.jsx)

### Architecture Diagram

See [Architechture_Diagram.png](Architechture_Diagram.png) for visual representation.

---

**Document Version**: 1.0.0
**Last Updated**: February 2026
**Maintained By**: Development Team
