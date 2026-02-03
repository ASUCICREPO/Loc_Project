"""
Chat Handler Lambda Function
Provides chat interface using Bedrock Knowledge Base with GraphRAG
Uses Neptune Analytics graph through Knowledge Base for entity extraction
"""

import json
import os
import boto3

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

BEDROCK_MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')

def lambda_handler(event, context):
    """
    Handle chat requests
    
    GET /health - Health check
    POST /chat - Chat query
    """
    print(f"Event: {json.dumps(event)}")
    
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
                'service': 'chronicling-america-chat',
                'knowledge_base_id': KNOWLEDGE_BASE_ID,
                'model_id': BEDROCK_MODEL_ID
            })
        }
    
    # Chat query
    try:
        body = json.loads(event.get('body', '{}'))
        # Handle both 'message' (from frontend) and 'question' (legacy) fields
        question = body.get('message', body.get('question', ''))
        language = body.get('language', 'en')
        persona = body.get('persona', 'general')  # congressional_staffer, research_journalist, law_student, general
        
        if not question:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Message is required'})
            }
        
        print(f"Question: {question}")
        print(f"Language: {language}")
        print(f"Persona: {persona}")
        
        # Check if Knowledge Base is configured
        if not KNOWLEDGE_BASE_ID:
            print("ERROR: KNOWLEDGE_BASE_ID not set")
            return {
                'statusCode': 503,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Knowledge Base not configured yet. Please run the deployment pipeline first.'
                })
            }
        
        # Query Knowledge Base (handles both specific bills and general queries)
        response = query_knowledge_base(question, persona)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': response['answer'],  # Frontend expects 'message' field
                'answer': response['answer'],   # Keep 'answer' for compatibility
                'sources': response.get('sources', []),
                'entities': response.get('entities', [])
            })
        }
        
    except Exception as e:
        # Log detailed error for debugging
        print(f"ERROR in lambda_handler: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Return user-friendly error message
        return {
            'statusCode': 200,  # Return 200 to avoid frontend errors
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': "I'm sorry, I encountered an unexpected error. Please try again in a moment.",
                'answer': "I'm sorry, I encountered an unexpected error. Please try again in a moment.",
                'sources': [],
                'entities': [],
                'error': True
            })
        }



def get_persona_prompt(persona: str) -> str:
    """
    Get system prompt based on user persona
    All prompts enforce strict adherence to provided documents only
    """
    prompts = {
        'congressional_staffer': """You are an expert constitutional research assistant for Congressional staff.

CRITICAL RULE: Answer ONLY using information from the provided documents. Do NOT use your general knowledge.

Your responses should be:
- Precise and authoritative with specific citations from the documents
- Focused on precedent and constitutional interpretation found in the documents
- Include relevant references when they appear in the documents
- Provide historical context ONLY from the documents
- Use formal, professional language suitable for briefing members of Congress
- If information is not in the documents, clearly state: "This information is not available in the provided documents."
""",
        
        'research_journalist': """You are a constitutional expert helping journalists research stories.

CRITICAL RULE: Answer ONLY using information from the provided documents. Do NOT use your general knowledge.

Your responses should be:
- Provide cultural and historical context ONLY from the documents
- Explain constitutional language using information in the documents
- Include interesting historical details ONLY if they appear in the documents
- Use clear, engaging language suitable for news articles
- If information is not in the documents, clearly state: "This information is not available in the provided documents."
""",
        
        'law_student': """You are a constitutional law professor helping students learn.

CRITICAL RULE: Answer ONLY using information from the provided documents. Do NOT use your general knowledge.

Your responses should be:
- Educational and comprehensive using ONLY the provided documents
- Explain legal reasoning found in the documents
- Reference cases and provisions ONLY if they appear in the documents
- Use precise legal terminology from the documents
- If information is not in the documents, clearly state: "This information is not available in the provided documents."
""",
        
        'general': """You are a knowledgeable constitutional expert.

CRITICAL RULE: Answer ONLY using information from the provided documents. Do NOT use your general knowledge.

Your responses should be:
- Clear and informative using ONLY the provided documents
- Balanced and objective based on the documents
- Include relevant historical context ONLY from the documents
- Cite specific provisions ONLY if they appear in the documents
- If information is not in the documents, clearly state: "This information is not available in the provided documents."
"""
    }
    
    return prompts.get(persona, prompts['general'])


def query_knowledge_base(question: str, persona: str = 'general') -> dict:
    """
    Query Knowledge Base using two-step approach for reliable citations
    Step 1: retrieve() - Get explicit document references
    Step 2: Use those documents to generate answer with proper citations
    
    Note: Metadata filtering is not currently configured in the Knowledge Base.
    All queries search across all documents (bills + newspapers).
    """
    print(f"Querying Knowledge Base: {KNOWLEDGE_BASE_ID}")
    
    # Get AWS context
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity()['Account']
    
    try:
        # Build retrieval configuration
        # Search all documents - no metadata filtering
        retrieval_config = {
            'vectorSearchConfiguration': {
                'numberOfResults': 20,
                'overrideSearchType': 'SEMANTIC'
            }
        }
        
        print("General query - searching all documents")
        
        # STEP 1: Retrieve documents explicitly
        print(f"Step 1: Retrieving documents...")
        retrieve_response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': question},
            retrievalConfiguration=retrieval_config
        )
        
        print(f"Retrieved {len(retrieve_response.get('retrievalResults', []))} documents")
        
        # Extract sources from retrieve response
        sources = []
        retrieved_docs = []
        
        for result in retrieve_response.get('retrievalResults', []):
            # Build source info
            location = result.get('location', {}).get('s3Location', {})
            content_text = result.get('content', {}).get('text', '')
            metadata = result.get('metadata', {})
            
            # Extract original URL from unified metadata field
            # This is the actual source URL (congress.gov or chroniclingamerica.loc.gov), not S3 path
            original_url = metadata.get('source_url', '')
            
            # Determine document type and title
            entity_type = metadata.get('entity_type', 'document')
            
            if entity_type == 'bill':
                # For bills, create a descriptive title
                congress = metadata.get('congress', '')
                bill_type = metadata.get('bill_type', '')
                bill_number = metadata.get('bill_number', '')
                title = f"Congress {congress} - {bill_type} {bill_number}" if congress else "Congressional Bill"
                doc_type = "Bill"
            elif entity_type == 'newspaper':
                # For newspapers, use newspaper title and date
                newspaper_title = metadata.get('newspaper_title', '')
                issue_date = metadata.get('issue_date', '')
                
                # Fallback: extract from filename if metadata is missing
                if not newspaper_title:
                    # Filename format: newspaper_15695_1809-06-13_The Kentucky Gazette.txt
                    uri = location.get('uri', '')
                    filename = uri.split('/')[-1].replace('.txt', '')
                    parts = filename.split('_', 3)  # Split into max 4 parts
                    if len(parts) >= 4:
                        newspaper_title = parts[3]  # The newspaper name
                    if len(parts) >= 3 and not issue_date:
                        issue_date = parts[2]  # The date
                
                title = f"{newspaper_title} ({issue_date})" if (newspaper_title and issue_date) else (newspaper_title or "Historical Newspaper")
                doc_type = "Newspaper"
            else:
                # Fallback: try to extract info from S3 URI
                uri = location.get('uri', '')
                filename = uri.split('/')[-1].replace('.txt', '')
                
                # Check if it's a newspaper file (starts with "newspaper_")
                if filename.startswith('newspaper_'):
                    parts = filename.split('_', 3)
                    if len(parts) >= 4:
                        newspaper_title = parts[3]
                        issue_date = parts[2] if len(parts) >= 3 else ''
                        title = f"{newspaper_title} ({issue_date})" if issue_date else newspaper_title
                        doc_type = "Newspaper"
                    else:
                        title = "Historical Newspaper"
                        doc_type = "Newspaper"
                else:
                    title = "Historical Document"
                    doc_type = "Document"
            
            source_info = {
                'document_id': location.get('uri', ''),  # S3 path (for internal tracking)
                'url': original_url if original_url else location.get('uri', ''),  # Original URL for display
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
            }
            sources.append(source_info)
            
            # Keep full content for generation
            retrieved_docs.append({
                'uri': location.get('uri', ''),
                'content': content_text
            })
            
            print(f"  Source: {title}")
            print(f"    Type: {doc_type}")
            print(f"    URL: {source_info['url'][:80]}...")
            print(f"    Score: {source_info['score']:.3f}")
        
        # Check if we found any documents
        if len(sources) == 0:
            print("⚠️ WARNING: No documents found in Knowledge Base")
            return {
                'answer': "I don't have access to the historical documents yet. The Knowledge Base may still be syncing or needs to be populated with data. Please try again later or contact support.",
                'sources': [],
                'entities': [],
                'warning': 'no_sources_found'
            }
        
        # STEP 2: Generate answer using retrieved documents
        print(f"Step 2: Generating answer from {len(retrieved_docs)} documents...")
        
        # Determine model ARN
        if BEDROCK_MODEL_ID.startswith(('us.', 'eu.', 'global.')):
            model_arn = f'arn:aws:bedrock:{aws_region}:{account_id}:inference-profile/{BEDROCK_MODEL_ID}'
        else:
            model_arn = f'arn:aws:bedrock:{aws_region}::foundation-model/{BEDROCK_MODEL_ID}'
        
        # Get persona-specific system prompt
        system_prompt = get_persona_prompt(persona)
        
        # Now use retrieve_and_generate with the same query
        # This will use the same documents but return a generated answer
        retrieve_and_generate_config = {
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                'modelArn': model_arn,
                'generationConfiguration': {
                    'promptTemplate': {
                        'textPromptTemplate': f"""{system_prompt}

CRITICAL INSTRUCTIONS:
1. You MUST answer ONLY using information from the Context provided below
2. If the Context does not contain the answer, you MUST respond with: "I cannot find information about this in the available documents."
3. DO NOT use your general knowledge or training data
4. DO NOT make assumptions beyond what is explicitly stated in the Context
5. DO NOT provide information that is not in the Context, even if you know it from your training

Context from Historical Documents:
$search_results$

Question: $query$

Answer (using ONLY the Context above):"""
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
            input={'text': question},
            retrieveAndGenerateConfiguration=retrieve_and_generate_config
        )
        
        # Extract answer
        answer = response['output']['text']
        print(f"Generated answer: {answer[:200]}...")
        
        print(f"✓ Knowledge Base returned answer with {len(sources)} sources")
        
        return {
            'answer': answer,
            'sources': sources,  # Use sources from retrieve() step
            'entities': []
        }
        
    except Exception as e:
        print(f"ERROR querying Knowledge Base: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'answer': "I encountered an error while searching. Please try again.",
            'sources': [],
            'entities': [],
            'error': True
        }









