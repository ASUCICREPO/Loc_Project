"""
Chat Handler Lambda Function
Uses Strands Agents with Bedrock AgentCore Memory for conversational AI
Integrates with Bedrock Knowledge Base for document retrieval (GraphRAG)
"""

import json
import os
import re
import boto3
import uuid
import logging

from strands import Agent, tool
from strands.models import BedrockModel
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient

# Configure logging
logger = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)

# AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
sts_client = boto3.client('sts')

# Environment variables
BEDROCK_MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
AGENTCORE_MEMORY_ID = os.environ.get('AGENTCORE_MEMORY_ID', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize Memory Client
memory_client = None
if AGENTCORE_MEMORY_ID:
    try:
        memory_client = MemoryClient(region_name=AWS_REGION)
        logger.info(f"AgentCore Memory initialized: {AGENTCORE_MEMORY_ID}")
    except Exception as e:
        logger.warning(f"Failed to initialize AgentCore Memory: {e}")

# Store for sources (to return with response)
_current_sources = []


# =============================================================================
# KNOWLEDGE BASE TOOL
# =============================================================================

@tool
def search_historical_documents(query: str) -> str:
    """Search Library of Congress historical documents, congressional bills, and newspapers.
    Use this tool to find information about constitutional history, legislation, and historical events.
    
    Args:
        query: The search query about historical documents, bills, amendments, or newspapers
    """
    global _current_sources
    
    if not KNOWLEDGE_BASE_ID:
        return "Knowledge Base is not configured. Please contact support."
    
    logger.info(f"Searching Knowledge Base for: {query}")
    
    try:
        # Get AWS account ID for model ARN
        account_id = sts_client.get_caller_identity()['Account']
        
        # Build retrieval configuration
        retrieval_config = {
            'vectorSearchConfiguration': {
                'numberOfResults': 20,
                'overrideSearchType': 'SEMANTIC'
            }
        }
        
        # Step 1: Retrieve documents
        retrieve_response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration=retrieval_config
        )
        
        results = retrieve_response.get('retrievalResults', [])
        logger.info(f"Retrieved {len(results)} documents")
        
        if not results:
            return "No relevant documents found in the historical archives."
        
        # Extract sources for frontend
        sources = []
        for result in results:
            location = result.get('location', {}).get('s3Location', {})
            content_text = result.get('content', {}).get('text', '')
            metadata = result.get('metadata', {})
            
            original_url = metadata.get('source_url', '')
            entity_type = metadata.get('entity_type', 'document')
            
            # Determine title based on document type
            if entity_type == 'bill':
                congress = metadata.get('congress', '')
                bill_type = metadata.get('bill_type', '')
                bill_number = metadata.get('bill_number', '')
                title = f"Congress {congress} - {bill_type} {bill_number}" if congress else "Congressional Bill"
                doc_type = "Bill"
            elif entity_type == 'newspaper':
                newspaper_title = metadata.get('newspaper_title', '')
                issue_date = metadata.get('issue_date', '')
                title = f"{newspaper_title} ({issue_date})" if (newspaper_title and issue_date) else "Historical Newspaper"
                doc_type = "Newspaper"
            else:
                title = "Historical Document"
                doc_type = "Document"
            
            sources.append({
                'document_id': location.get('uri', ''),
                'url': original_url if original_url else location.get('uri', ''),
                'title': title,
                'type': doc_type,
                'content': content_text[:300] + '...' if len(content_text) > 300 else content_text,
                'score': result.get('score', 0),
                'metadata': {
                    'entity_type': entity_type,
                    'congress': metadata.get('congress', ''),
                    'bill_type': metadata.get('bill_type', ''),
                    'bill_number': metadata.get('bill_number', ''),
                    'newspaper_title': metadata.get('newspaper_title', ''),
                    'issue_date': metadata.get('issue_date', ''),
                    'year': metadata.get('year', ''),
                    'source': metadata.get('source', '')
                }
            })
        
        # Store sources globally for response
        _current_sources = sources
        
        # Step 2: Generate answer using retrieve_and_generate
        if BEDROCK_MODEL_ID.startswith(('us.', 'eu.', 'global.')):
            model_arn = f'arn:aws:bedrock:{AWS_REGION}:{account_id}:inference-profile/{BEDROCK_MODEL_ID}'
        else:
            model_arn = f'arn:aws:bedrock:{AWS_REGION}::foundation-model/{BEDROCK_MODEL_ID}'
        
        retrieve_and_generate_config = {
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                'modelArn': model_arn,
                'generationConfiguration': {
                    'promptTemplate': {
                        'textPromptTemplate': """Answer the question using ONLY the context provided below.
If the information is not in the context, say "I cannot find this information in the available documents."

Context from Historical Documents:
$search_results$

Question: $query$

Answer:"""
                    },
                    'inferenceConfig': {
                        'textInferenceConfig': {
                            'temperature': 0.1,
                            'maxTokens': 2000
                        }
                    }
                },
                'retrievalConfiguration': retrieval_config
            }
        }
        
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={'text': query},
            retrieveAndGenerateConfiguration=retrieve_and_generate_config
        )
        
        answer = response['output']['text']
        logger.info(f"Generated answer: {answer[:100]}...")
        
        return answer
        
    except Exception as e:
        logger.error(f"Error searching Knowledge Base: {e}")
        return f"Error searching documents: {str(e)}"


# =============================================================================
# MEMORY HOOKS (Auto context retrieval and saving)
# =============================================================================

class ConversationMemoryHooks(HookProvider):
    """Memory hooks for automatic conversation context management"""
    
    def __init__(self, memory_id: str, client: MemoryClient, actor_id: str, session_id: str):
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespaces = {}
        
        # Get memory strategies/namespaces
        try:
            strategies = self.client.get_memory_strategies(self.memory_id)
            self.namespaces = {
                s["type"]: s["namespaces"][0] for s in strategies
            }
            logger.info(f"Memory namespaces: {self.namespaces}")
        except Exception as e:
            logger.warning(f"Could not get memory strategies: {e}")
    
    def retrieve_context(self, event: MessageAddedEvent):
        """Retrieve conversation context before processing user query"""
        messages = event.agent.messages
        
        # Only process user messages (not tool results)
        if not messages or messages[-1]["role"] != "user":
            return
        if "toolResult" in messages[-1]["content"][0]:
            return
        
        user_query = messages[-1]["content"][0]["text"]
        logger.info(f"Retrieving context for: {user_query[:50]}...")
        
        try:
            all_context = []
            
            # Retrieve from each memory namespace
            for context_type, namespace in self.namespaces.items():
                try:
                    memories = self.client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=namespace.format(actorId=self.actor_id, sessionId=""),
                        query=user_query,
                        top_k=3,
                    )
                    
                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get("content", {})
                            if isinstance(content, dict):
                                text = content.get("text", "").strip()
                                if text:
                                    all_context.append(f"[{context_type.upper()}] {text}")
                except Exception as e:
                    logger.warning(f"Failed to retrieve {context_type}: {e}")
            
            # Inject context into the user message
            if all_context:
                context_text = "\n".join(all_context)
                original_text = messages[-1]["content"][0]["text"]
                messages[-1]["content"][0]["text"] = f"""Previous Context:
{context_text}

Current Question: {original_text}"""
                logger.info(f"Injected {len(all_context)} context items")
                
        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
    
    def save_conversation(self, event: AfterInvocationEvent):
        """Save conversation after agent response"""
        try:
            messages = event.agent.messages
            if len(messages) < 2 or messages[-1]["role"] != "assistant":
                return
            
            # Extract user query and assistant response
            user_query = None
            agent_response = None
            
            for msg in reversed(messages):
                if msg["role"] == "assistant" and not agent_response:
                    output = msg["content"][0].get("text", "")
                    # Remove thinking tags if present
                    agent_response = re.sub(r'<thinking>.*?</thinking>', '', output, flags=re.DOTALL).strip()
                    
                elif msg["role"] == "user" and not user_query:
                    if "toolResult" not in msg["content"][0]:
                        input_text = msg["content"][0].get("text", "")
                        # Remove injected context prefix
                        user_query = re.sub(r'Previous Context:.*?Current Question: ', '', input_text, flags=re.DOTALL).strip()
                        break
            
            if user_query and agent_response:
                self.client.create_event(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[
                        (user_query, "USER"),
                        (agent_response, "ASSISTANT"),
                    ],
                )
                logger.info("Conversation saved to memory")
                
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
    
    def register_hooks(self, registry: HookRegistry) -> None:
        """Register memory hooks"""
        registry.add_callback(MessageAddedEvent, self.retrieve_context)
        registry.add_callback(AfterInvocationEvent, self.save_conversation)
        logger.info("Memory hooks registered")


# =============================================================================
# PERSONA PROMPTS
# =============================================================================

def get_system_prompt(persona: str) -> str:
    """Get system prompt based on user persona"""
    
    base_prompt = """You are Histora, an AI assistant for the Library of Congress.
You help users explore historical documents, congressional bills, and newspaper archives.

IMPORTANT RULES:
1. Use the search_historical_documents tool to find information
2. Answer ONLY using information from the documents returned by the tool
3. If you cannot find information, say so clearly
4. Always be helpful and provide context when available
"""
    
    persona_additions = {
        'congressional_staffer': """
You are assisting Congressional staff with research.
- Be precise and authoritative
- Focus on precedent and constitutional interpretation
- Use formal, professional language
- Cite specific documents when possible
""",
        'research_journalist': """
You are helping journalists research stories.
- Provide cultural and historical context
- Explain constitutional language clearly
- Use engaging language suitable for articles
- Highlight interesting historical details
""",
        'law_student': """
You are a constitutional law professor helping students.
- Be educational and comprehensive
- Explain legal reasoning clearly
- Use precise legal terminology
- Reference relevant cases and provisions
""",
        'general': """
You are helping a general user explore history.
- Be clear and informative
- Provide helpful context
- Use accessible language
- Make history engaging and interesting
"""
    }
    
    return base_prompt + persona_additions.get(persona, persona_additions['general'])


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def lambda_handler(event, context):
    """Handle chat requests using Strands Agent with Memory"""
    global _current_sources
    _current_sources = []
    
    logger.info(f"Event: {json.dumps(event)}")
    
    http_method = event.get('httpMethod', 'POST')
    
    # Health check
    if http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'healthy',
                'service': 'loc-histora-chat',
                'knowledge_base_id': KNOWLEDGE_BASE_ID,
                'model_id': BEDROCK_MODEL_ID,
                'memory_enabled': bool(AGENTCORE_MEMORY_ID)
            })
        }
    
    # Chat query
    try:
        body = json.loads(event.get('body', '{}'))
        question = body.get('message', body.get('question', ''))
        persona = body.get('persona', 'general')
        user_id = body.get('user_id', 'anonymous')
        session_id = body.get('session_id', str(uuid.uuid4()))
        
        if not question:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Message is required'})
            }
        
        logger.info(f"Question: {question}")
        logger.info(f"Persona: {persona}, User: {user_id}, Session: {session_id}")
        
        # Check Knowledge Base
        if not KNOWLEDGE_BASE_ID:
            return {
                'statusCode': 503,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Knowledge Base not configured. Please deploy the infrastructure first.'
                })
            }
        
        # Build hooks list
        hooks = []
        if memory_client and AGENTCORE_MEMORY_ID:
            memory_hooks = ConversationMemoryHooks(
                memory_id=AGENTCORE_MEMORY_ID,
                client=memory_client,
                actor_id=user_id,
                session_id=session_id
            )
            hooks.append(memory_hooks)
            logger.info("Memory hooks enabled")
        
        # Create Strands Agent
        agent = Agent(
            model=BedrockModel(model_id=BEDROCK_MODEL_ID),
            system_prompt=get_system_prompt(persona),
            tools=[search_historical_documents],
            hooks=hooks,
        )
        
        # Run agent
        logger.info("Running Strands Agent...")
        result = agent(question)
        
        # Extract response text
        answer = str(result)
        logger.info(f"Agent response: {answer[:100]}...")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': answer,
                'answer': answer,
                'sources': _current_sources,
                'entities': [],
                'session_id': session_id
            })
        }
        
    except Exception as e:
        logger.error(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': "I'm sorry, I encountered an error. Please try again.",
                'answer': "I'm sorry, I encountered an error. Please try again.",
                'sources': [],
                'entities': [],
                'error': True
            })
        }
