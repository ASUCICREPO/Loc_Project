"""
Chat Handler Lambda Function
Uses direct KB retrieval + direct LLM call for fast responses
Uses AgentCore Memory short-term storage (session-based, no summarization)
"""

import json
import os
import boto3
import uuid
import logging

from bedrock_agentcore.memory import MemoryClient

# Configure logging
logger = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)

# AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
bedrock_runtime = boto3.client('bedrock-runtime')

# Environment variables
BEDROCK_MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
AGENTCORE_MEMORY_ID = os.environ.get('AGENTCORE_MEMORY_ID', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
MAX_HISTORY_ITEMS = int(os.environ.get('MAX_HISTORY_ITEMS', '10'))  # Sliding window

# Initialize Memory Client
memory_client = None
if AGENTCORE_MEMORY_ID:
    try:
        memory_client = MemoryClient(region_name=AWS_REGION)
        logger.info(f"AgentCore Memory initialized: {AGENTCORE_MEMORY_ID}")
    except Exception as e:
        logger.warning(f"Failed to initialize AgentCore Memory: {e}")


# =============================================================================
# SESSION-BASED MEMORY (Simple - No Summarization)
# =============================================================================

def get_session_history(session_id: str, user_id: str) -> str:
    """Load conversation history for this session using list_events (sliding window)"""
    if not memory_client or not AGENTCORE_MEMORY_ID:
        return ""
    
    try:
        # list_events returns recent events for this session - simple retrieval, no semantic search
        events = memory_client.list_events(
            memory_id=AGENTCORE_MEMORY_ID,
            actor_id=user_id,
            session_id=session_id,
            max_results=MAX_HISTORY_ITEMS  # Sliding window size
        )
        
        logger.info(f"Retrieved {len(events) if events else 0} events for session")
        
        if not events:
            logger.debug("No events found for this session")
            return ""
        
        # Build context from events
        context_parts = []
        for idx, event in enumerate(events):
            # Messages are in 'payload', not 'messages'
            payload = event.get('payload', [])
            
            # Skip empty events
            if not payload:
                logger.debug(f"Event {idx + 1} has no payload, skipping")
                continue
            
            for item in payload:
                # Structure: {'conversational': {'content': {'text': '...'}, 'role': 'USER/ASSISTANT'}}
                conv = item.get('conversational', {})
                if conv:
                    content = conv.get('content', {}).get('text', '')
                    role = conv.get('role', '')
                    if content and role:
                        role_label = "User" if role == "USER" else "Assistant"
                        context_parts.append(f"{role_label}: {content}")
        
        if not context_parts:
            logger.debug("No valid messages found in events")
            return ""
        
        logger.info(f"Built context from {len(context_parts)} messages")
        conversation_text = "\n\n".join(context_parts)
        return conversation_text
        
    except Exception as e:
        logger.warning(f"Failed to load session history: {e}")
        return ""


def save_to_session(session_id: str, user_id: str, question: str, answer: str):
    """Save Q&A to session (only response, not retrieved docs)"""
    if not memory_client or not AGENTCORE_MEMORY_ID:
        return
    
    try:
        memory_client.create_event(
            memory_id=AGENTCORE_MEMORY_ID,
            actor_id=user_id,
            session_id=session_id,
            messages=[
                (question, "USER"),
                (answer, "ASSISTANT"),
            ],
        )
        logger.info(f"Saved conversation to session {session_id}")
    except Exception as e:
        logger.error(f"Failed to save to session: {e}")


# =============================================================================
# QUERY ENHANCEMENT FOR FOLLOW-UPS (LLM-based)
# =============================================================================

def enhance_query_with_llm(question: str, conversation_context: str) -> str:
    """
    Use LLM to enhance vague follow-up questions by analyzing conversation context.
    The LLM determines what topic to search for in the Knowledge Base.
    """
    if not conversation_context:
        return question
    
    # Ask LLM to create a better search query
    enhancement_prompt = f"""You are a query enhancement assistant. Your job is to create a better search query for a knowledge base.

Given the conversation history and the user's current question, create a clear, specific search query that will retrieve relevant documents.

Conversation History:
{conversation_context}

Current Question: {question}

If the current question is vague (like "explain more", "what is it?", "tell me about that"), extract the main topic from the conversation history and create a specific search query.

If the current question is already clear and specific, return it as-is.

Return ONLY the enhanced search query, nothing else. No explanations."""

    try:
        messages = [{"role": "user", "content": [{"text": enhancement_prompt}]}]
        
        response = bedrock_runtime.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=messages,
            inferenceConfig={"maxTokens": 200, "temperature": 0}
        )
        
        enhanced_query = response['output']['message']['content'][0]['text'].strip()
        
        if enhanced_query and enhanced_query != question:
            logger.info(f"Enhanced query: '{question}' -> '{enhanced_query}'")
            return enhanced_query
        
        return question
        
    except Exception as e:
        logger.warning(f"Failed to enhance query with LLM: {e}")
        return question


# =============================================================================
# KNOWLEDGE BASE RETRIEVAL
# =============================================================================

def search_knowledge_base(query: str) -> tuple:
    """Search Knowledge Base and return documents + sources"""
    if not KNOWLEDGE_BASE_ID:
        return "", []
    
    logger.info(f"Searching Knowledge Base for: {query}")
    
    try:
        retrieval_config = {
            'vectorSearchConfiguration': {
                'numberOfResults': 20,
                'overrideSearchType': 'SEMANTIC'
            }
        }
        
        retrieve_response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration=retrieval_config
        )
        
        results = retrieve_response.get('retrievalResults', [])
        logger.info(f"Retrieved {len(results)} documents")
        
        if not results:
            return "", []
        
        sources = []
        document_context = []
        
        for i, result in enumerate(results):
            location = result.get('location', {}).get('s3Location', {})
            content_text = result.get('content', {}).get('text', '')
            metadata = result.get('metadata', {})
            
            original_url = metadata.get('source_url', '')
            entity_type = metadata.get('entity_type', 'document')
            
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
            
            document_context.append(f"[Document {i+1}: {title}]\n{content_text}")
        
        context = "\n\n---\n\n".join(document_context)
        return context, sources
        
    except Exception as e:
        logger.error(f"Error searching Knowledge Base: {e}")
        return "", []


# =============================================================================
# LLM CALL
# =============================================================================

def get_system_prompt(persona: str) -> str:
    """Get system prompt based on user persona"""
    
    base_prompt = """You are Histora, an AI assistant for the Library of Congress.
You help users explore historical documents, congressional bills, and newspaper archives.

You will be provided with:
1. Retrieved historical documents from the Knowledge Base
2. Previous conversation context (if any) - use this ONLY for understanding follow-up questions, NOT as factual source

ABSOLUTE RULES:
1. Answer ONLY using information from the provided documents
2. You CAN make reasonable inferences by combining information FROM the documents
3. Do NOT use your pre-trained knowledge or general knowledge to fill gaps
4. Do NOT add facts that are not in the documents (like dates, numbers, names you "know")
5. If you cannot answer from the documents, simply say: "I couldn't find this information in the available archives."
6. NEVER contradict yourself - if you say you can't find something, don't then provide an answer

RESPONSE STYLE:
- Give natural, conversational answers like a knowledgeable historian would
- NEVER mention "Document 1", "Document 4", or any document numbers
- Simply provide the answer directly without referencing document numbers
- Keep responses concise and focused on answering the question
- Be consistent - either you found the answer in the documents or you didn't
"""
    
    persona_additions = {
        'interested_person': "\nYou are a knowledgeable constitutional expert. Be clear, informative, and balanced.",
        'policy_analyst': "\nYou are an expert for Congressional staff. Be precise with formal, professional language.",
        'research_journalist': "\nYou are helping journalists. Provide cultural/historical context in engaging language.",
        'law_student': "\nYou are a law professor. Be educational with precise legal terminology."
    }
    
    return base_prompt + persona_additions.get(persona, persona_additions['interested_person'])


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call Bedrock LLM directly"""
    try:
        messages = [{"role": "user", "content": [{"text": user_message}]}]
        
        response = bedrock_runtime.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1}
        )
        
        return response['output']['message']['content'][0]['text']
        
    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        raise e


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def lambda_handler(event, context):
    """Handle chat requests - sessionID based context via AgentCore Memory"""
    
    # Log request metadata only, not full event body
    logger.info(f"Request received: method={event.get('httpMethod', 'POST')}, path={event.get('path', '/chat')}")
    
    http_method = event.get('httpMethod', 'POST')
    
    # Health check
    if http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'status': 'healthy',
                'service': 'loc-histora-chat',
                'knowledge_base_id': KNOWLEDGE_BASE_ID,
                'model_id': BEDROCK_MODEL_ID,
                'memory_enabled': bool(AGENTCORE_MEMORY_ID)
            })
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        question = body.get('message', body.get('question', ''))
        persona = body.get('persona', 'interested_person')
        user_id = body.get('user_id', 'anonymous')
        session_id = body.get('session_id', str(uuid.uuid4()))
        
        if not question:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Message is required'})
            }
        
        logger.info(f"Question: {question}, Session: {session_id}, User: {user_id}")
        
        if not KNOWLEDGE_BASE_ID:
            return {
                'statusCode': 503,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Knowledge Base not configured.'})
            }
        
        # Step 1: Load session history from AgentCore Memory (same sessionID = load context)
        conversation_context = get_session_history(session_id, user_id)
        
        # Step 2: Enhance query using LLM if it's a vague follow-up, then search KB
        search_query = enhance_query_with_llm(question, conversation_context)
        document_context, sources = search_knowledge_base(search_query)
        
        if not document_context:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': "I couldn't find any relevant documents in the archives for your question.",
                    'answer': "I couldn't find any relevant documents in the archives for your question.",
                    'sources': [],
                    'session_id': session_id
                })
            }
        
        # Step 3: Build prompt with session context + KB docs
        user_message = f"Question: {question}\n\n"
        if conversation_context:
            user_message += f"Previous Conversation:\n{conversation_context}\n\n"
        user_message += f"Retrieved Documents:\n{document_context}\n\nPlease answer based on the documents above."
        
        # Step 4: Call LLM
        system_prompt = get_system_prompt(persona)
        answer = call_llm(system_prompt, user_message)
        logger.info(f"LLM response: {answer[:100]}...")
        
        # Step 5: Save only Q&A to session (not documents)
        save_to_session(session_id, user_id, question, answer)
        
        sorted_sources = sorted(sources, key=lambda x: x.get('score', 0), reverse=True)[:20]
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': answer,
                'answer': answer,
                'sources': sorted_sources,
                'session_id': session_id
            })
        }
        
    except Exception as e:
        logger.error(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': "I'm sorry, I encountered an error. Please try again.",
                'sources': [],
                'error': True
            })
        }
