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
# HELPER FUNCTIONS FOR METADATA FILTERING
# =============================================================================

def extract_filters_from_query(query: str) -> dict:
    """
    Extract metadata filters from the user's query.
    Detects years, congress numbers, and document types.
    
    Available metadata fields:
    - entity_type: "bill" or "newspaper"
    - year: e.g., "1793", "1798"
    - congress: congress number e.g., "1", "5", "16"
    - bill_type: "HR", "S", "HJRES", etc.
    - newspaper_title: newspaper name
    - issue_date: date string
    """
    filters = {}
    query_lower = query.lower()
    
    # Extract year (4-digit number between 1770-1830)
    year_match = re.search(r'\b(17[7-9]\d|18[0-2]\d)\b', query)
    if year_match:
        filters['year'] = year_match.group(1)
    
    # Extract congress number
    # Patterns: "5th congress", "congress 5", "fifth congress", etc.
    congress_patterns = [
        r'(\d+)(?:st|nd|rd|th)?\s*congress',
        r'congress\s*(\d+)',
        r'(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth)\s*congress'
    ]
    
    ordinal_map = {
        'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
        'sixth': '6', 'seventh': '7', 'eighth': '8', 'ninth': '9', 'tenth': '10',
        'eleventh': '11', 'twelfth': '12', 'thirteenth': '13', 'fourteenth': '14',
        'fifteenth': '15', 'sixteenth': '16'
    }
    
    for pattern in congress_patterns:
        match = re.search(pattern, query_lower)
        if match:
            congress_val = match.group(1)
            if congress_val in ordinal_map:
                filters['congress'] = ordinal_map[congress_val]
            else:
                filters['congress'] = congress_val
            break
    
    # If year is provided but no congress, calculate approximate congress
    # Congress 1 = 1789-1791, Congress 2 = 1791-1793, etc.
    if 'year' in filters and 'congress' not in filters:
        year = int(filters['year'])
        if year >= 1789:
            approx_congress = ((year - 1789) // 2) + 1
            if 1 <= approx_congress <= 16:
                filters['congress'] = str(approx_congress)
    
    # Detect document type preference
    if any(word in query_lower for word in ['bill', 'legislation', 'act', 'law', 'congress', 'senate', 'house']):
        filters['entity_type'] = 'bill'
    elif any(word in query_lower for word in ['newspaper', 'news', 'article', 'press', 'gazette']):
        filters['entity_type'] = 'newspaper'
    
    # Detect bill type
    bill_type_patterns = {
        'HR': r'\b(h\.?r\.?|house\s*resolution|house\s*bill)\b',
        'S': r'\b(s\.?\s*\d|senate\s*bill)\b',
        'HJRES': r'\b(h\.?j\.?\s*res|house\s*joint\s*resolution)\b',
        'SJRES': r'\b(s\.?j\.?\s*res|senate\s*joint\s*resolution)\b',
    }
    
    for bill_type, pattern in bill_type_patterns.items():
        if re.search(pattern, query_lower):
            filters['bill_type'] = bill_type
            filters['entity_type'] = 'bill'
            break
    
    return filters


def build_retrieval_filter(filters: dict) -> dict:
    """
    Build Bedrock Knowledge Base filter from extracted filters.
    Uses the filter syntax for Bedrock KB retrieve API.
    """
    if not filters:
        return None
    
    filter_conditions = []
    
    # Year filter (exact match)
    if 'year' in filters:
        filter_conditions.append({
            'equals': {
                'key': 'year',
                'value': filters['year']
            }
        })
    
    # Congress filter (exact match)
    if 'congress' in filters:
        filter_conditions.append({
            'equals': {
                'key': 'congress',
                'value': filters['congress']
            }
        })
    
    # Entity type filter
    if 'entity_type' in filters:
        filter_conditions.append({
            'equals': {
                'key': 'entity_type',
                'value': filters['entity_type']
            }
        })
    
    # Bill type filter
    if 'bill_type' in filters:
        filter_conditions.append({
            'equals': {
                'key': 'bill_type',
                'value': filters['bill_type']
            }
        })
    
    # Combine filters with AND
    if len(filter_conditions) == 0:
        return None
    elif len(filter_conditions) == 1:
        return filter_conditions[0]
    else:
        return {
            'andAll': filter_conditions
        }


# =============================================================================
# KNOWLEDGE BASE TOOL
# =============================================================================

@tool
def search_historical_documents(query: str) -> str:
    """Search Library of Congress historical documents, congressional bills, and newspapers.
    Use this tool to find information about constitutional history, legislation, and historical events.
    Returns the document content which you should use to answer the user's question.
    
    Args:
        query: The search query about historical documents, bills, amendments, or newspapers
    """
    global _current_sources
    
    if not KNOWLEDGE_BASE_ID:
        return "Knowledge Base is not configured. Please contact support."
    
    logger.info(f"Searching Knowledge Base for: {query}")
    
    # Extract metadata filters from query
    filters = extract_filters_from_query(query)
    if filters:
        logger.info(f"Extracted filters: {filters}")
    
    try:
        # Build retrieval configuration
        retrieval_config = {
            'vectorSearchConfiguration': {
                'numberOfResults': 20,
                'overrideSearchType': 'SEMANTIC'
            }
        }
        
        # Add metadata filter if we extracted any
        kb_filter = build_retrieval_filter(filters)
        if kb_filter:
            retrieval_config['vectorSearchConfiguration']['filter'] = kb_filter
            logger.info(f"Applied KB filter: {kb_filter}")
        
        # Retrieve documents with filters
        retrieve_response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration=retrieval_config
        )
        
        results = retrieve_response.get('retrievalResults', [])
        logger.info(f"Retrieved {len(results)} documents with filters")
        
        # If no results with filters, try without filters as fallback
        if not results and kb_filter:
            logger.info("No results with filters, retrying without filters...")
            retrieval_config['vectorSearchConfiguration'].pop('filter', None)
            retrieve_response = bedrock_agent_runtime.retrieve(
                knowledgeBaseId=KNOWLEDGE_BASE_ID,
                retrievalQuery={'text': query},
                retrievalConfiguration=retrieval_config
            )
            results = retrieve_response.get('retrievalResults', [])
            logger.info(f"Retrieved {len(results)} documents without filters")
        
        if not results:
            return "No relevant documents found in the historical archives."
        
        # Extract sources for frontend and build context for agent
        sources = []
        document_context = []
        
        for i, result in enumerate(results):  # Use all retrieved documents for context
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
            
            # Build context for agent to use
            document_context.append(f"[Document {i+1}: {title}]\n{content_text[:1500]}")
        
        # Accumulate sources globally for response (don't overwrite, append and dedupe)
        existing_urls = {s['url'] for s in _current_sources}
        for source in sources:
            if source['url'] not in existing_urls:
                _current_sources.append(source)
                existing_urls.add(source['url'])
        
        # Return document content for Strands Agent to use (NO second LLM call)
        context = "\n\n---\n\n".join(document_context)
        return f"""Found {len(results)} relevant documents. Here are the most relevant excerpts:

{context}

Use ONLY the information above to answer the user's question. If the answer is not in these documents, say so."""
        
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

ABSOLUTE RULES - NEVER VIOLATE THESE:
1. You MUST ALWAYS call the search_historical_documents tool for EVERY question - even if you think you know the answer
2. You can ONLY answer using information that appears in the documents returned by the tool
3. You are FORBIDDEN from using your pre-trained knowledge, general knowledge, or any information not in the retrieved documents
4. You are FORBIDDEN from making up, inferring, or supplementing information beyond what's in the documents
5. If the documents don't contain the answer, you MUST say: "I couldn't find information about [topic] in the available historical archives."
6. Make at most 2-3 search attempts before concluding

IMPORTANT ABOUT PREVIOUS CONTEXT:
- Previous Context is ONLY for understanding conversation flow (e.g., what "it" refers to)
- You MUST NOT use Previous Context as a source of facts or answers
- Even if Previous Context mentions an answer, you MUST search the Knowledge Base to verify
- ALWAYS call search_historical_documents - do not skip it because of Previous Context

WHAT YOU MUST NEVER DO:
- NEVER answer without first calling search_historical_documents
- NEVER provide historical facts from Previous Context without verifying via search
- NEVER say "Based on previous context" and then give an answer
- NEVER provide historical facts, dates, names, or events from your training data
- NEVER fill in gaps with general knowledge

RESPONSE FORMAT:
- FIRST: Always call search_historical_documents
- THEN: If you found relevant documents, quote or paraphrase directly from them
- If documents don't contain the answer: Say "I couldn't find this in the available archives"
- DO NOT mention your search process or tool calls in your response
"""
    
    persona_additions = {
        'congressional_staffer': """
You are assisting Congressional staff with research.
- Be precise and cite specific documents
- Only reference what's in the retrieved documents
- Use formal, professional language
""",
        'research_journalist': """
You are helping journalists research stories.
- Only provide context found in the documents
- Quote directly from historical sources when possible
- Be clear about what the archives do and don't contain
""",
        'law_student': """
You are helping law students with research.
- Only reference cases and provisions found in the documents
- Be educational but stick to document content
- Clearly distinguish between what's in archives vs. not available
""",
        'general': """
You are helping a general user explore history.
- Be clear and informative using only document content
- If information isn't available, suggest what topics ARE in the archives
- Make the available historical content engaging
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
        
        # Run agent with max_turns limit to prevent timeout
        logger.info("Running Strands Agent...")
        result = agent(question, max_turns=5)  # Limit to 5 turns (includes tool calls + responses)
        
        # Extract response text
        answer = str(result)
        logger.info(f"Agent response: {answer[:100]}...")
        
        # Sort sources by score and limit to top results
        sorted_sources = sorted(_current_sources, key=lambda x: x.get('score', 0), reverse=True)[:20]
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': answer,
                'answer': answer,
                'sources': sorted_sources,
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
