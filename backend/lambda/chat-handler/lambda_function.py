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
    """
    prompts = {
        'congressional_staffer': """You are an expert constitutional research assistant for Congressional staff. 
Your responses should be:
- Precise and authoritative with specific citations
- Focused on precedent and constitutional interpretation
- Include relevant Federalist Papers references when applicable
- Provide historical context for legislative decisions
- Use formal, professional language suitable for briefing members of Congress
- Cite specific articles, sections, and amendments
- Reference relevant Supreme Court cases with case names and years""",
        
        'research_journalist': """You are a constitutional expert helping journalists research stories.
Your responses should be:
- Provide cultural and historical context from the era
- Explain constitutional language in accessible terms
- Connect constitutional provisions to modern relevance
- Include interesting historical anecdotes and context
- Explain the "why" behind constitutional decisions
- Reference the social and political climate of the time
- Use clear, engaging language suitable for news articles""",
        
        'law_student': """You are a constitutional law professor helping students learn.
Your responses should be:
- Educational and comprehensive
- Explain legal reasoning and constitutional theory
- Trace the evolution of constitutional interpretation
- Reference landmark cases with detailed analysis
- Explain both majority and dissenting opinions
- Connect constitutional provisions to broader legal principles
- Use precise legal terminology with explanations
- Encourage critical thinking about constitutional questions""",
        
        'general': """You are a knowledgeable constitutional expert.
Your responses should be:
- Clear and informative
- Balanced and objective
- Include relevant historical context
- Cite specific constitutional provisions
- Reference important court cases when relevant
- Use accessible language while maintaining accuracy"""
    }
    
    return prompts.get(persona, prompts['general'])


def extract_bill_info(question: str) -> dict:
    """
    Extract bill information from user question for metadata filtering
    
    Examples:
    - "what is bill HR 1 in congress 6?" -> {"congress": "6", "bill_type": "HR", "bill_number": "1"}
    - "show me bill S 2 from congress 16" -> {"congress": "16", "bill_type": "S", "bill_number": "2"}
    - "tell me about HR1 congress 6" -> {"congress": "6", "bill_type": "HR", "bill_number": "1"}
    """
    import re
    
    # Normalize question to lowercase for pattern matching
    q = question.lower()
    
    bill_info = {}
    
    # Pattern 1: "bill HR 1 in congress 6" or "bill HR1 congress 6"
    pattern1 = r'bill\s+([a-z]+)\s*(\d+).*congress\s+(\d+)'
    match1 = re.search(pattern1, q)
    if match1:
        bill_info = {
            "bill_type": match1.group(1).upper(),
            "bill_number": match1.group(2),
            "congress": match1.group(3)
        }
    
    # Pattern 2: "HR 1 from congress 6" or "S2 congress 16"
    pattern2 = r'([a-z]+)\s*(\d+).*congress\s+(\d+)'
    match2 = re.search(pattern2, q)
    if match2 and not match1:  # Only if pattern1 didn't match
        bill_info = {
            "bill_type": match2.group(1).upper(),
            "bill_number": match2.group(2),
            "congress": match2.group(3)
        }
    
    # Pattern 3: "congress 6 bill HR 1"
    pattern3 = r'congress\s+(\d+).*bill\s+([a-z]+)\s*(\d+)'
    match3 = re.search(pattern3, q)
    if match3 and not match1 and not match2:
        bill_info = {
            "congress": match3.group(1),
            "bill_type": match3.group(2).upper(),
            "bill_number": match3.group(3)
        }
    
    print(f"Extracted bill info from '{question}': {bill_info}")
    return bill_info


def build_metadata_filter(bill_info: dict) -> dict:
    """
    Build metadata filter for Knowledge Base using mapped S3 metadata attributes
    Now that we have proper metadata mapping, these filters will work
    """
    if not bill_info:
        return None
    
    filters = []
    
    # Add congress filter (now mapped to KB metadata)
    if 'congress' in bill_info:
        filters.append({
            "equals": {
                "key": "congress",
                "value": bill_info['congress']
            }
        })
    
    # Add bill type filter
    if 'bill_type' in bill_info:
        filters.append({
            "equals": {
                "key": "bill_type", 
                "value": bill_info['bill_type']
            }
        })
    
    # Add bill number filter
    if 'bill_number' in bill_info:
        filters.append({
            "equals": {
                "key": "bill_number",
                "value": bill_info['bill_number']
            }
        })
    
    # Combine all filters with AND logic
    if len(filters) == 1:
        return filters[0]
    elif len(filters) > 1:
        return {"andAll": filters}
    
    return None





def query_knowledge_base(question: str, persona: str = 'general') -> dict:
    """
    Query Knowledge Base - handles both specific bill queries and general questions
    """
    print(f"Querying Knowledge Base: {KNOWLEDGE_BASE_ID}")
    
    # Extract bill information for potential filtering
    bill_info = extract_bill_info(question)
    
    # Get AWS context
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity()['Account']
    
    try:
        # Determine model ARN
        if BEDROCK_MODEL_ID.startswith(('us.', 'eu.', 'global.')):
            model_arn = f'arn:aws:bedrock:{aws_region}:{account_id}:inference-profile/{BEDROCK_MODEL_ID}'
        else:
            model_arn = f'arn:aws:bedrock:{aws_region}::foundation-model/{BEDROCK_MODEL_ID}'
        
        # Get persona-specific system prompt
        system_prompt = get_persona_prompt(persona)
        
        # Build retrieval configuration
        retrieval_config = {
            'vectorSearchConfiguration': {
                'numberOfResults': 50,
                'overrideSearchType': 'SEMANTIC'
            }
        }
        
        # Add metadata filter only if specific bill is detected
        metadata_filter = build_metadata_filter(bill_info)
        if metadata_filter:
            retrieval_config['vectorSearchConfiguration']['filter'] = metadata_filter
            print(f"Specific bill detected - applying metadata filter for precise targeting")
        else:
            print("General query - searching all documents")
        
        # Build the configuration
        retrieve_and_generate_config = {
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                'modelArn': model_arn,
                'generationConfiguration': {
                    'promptTemplate': {
                        'textPromptTemplate': f"""{system_prompt}

Use the following context to answer the question. Provide a well-formatted response.

Context:
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
        
        # Query Knowledge Base
        print(f"Calling retrieve_and_generate with config: {json.dumps(retrieve_and_generate_config, indent=2)}")
        
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={'text': question},
            retrieveAndGenerateConfiguration=retrieve_and_generate_config
        )
        
        print(f"Raw Knowledge Base response: {json.dumps(response, indent=2, default=str)}")
        
        # Extract answer and sources
        answer = response['output']['text']
        print(f"Extracted answer: {answer}")
        
        sources = []
        
        if 'citations' in response:
            print(f"Found {len(response['citations'])} citations")
            for i, citation in enumerate(response['citations']):
                print(f"Citation {i}: {json.dumps(citation, indent=2, default=str)}")
                retrieved_refs = citation.get('retrievedReferences', [])
                for j, reference in enumerate(retrieved_refs):
                    print(f"  Reference {j}: {json.dumps(reference, indent=2, default=str)}")
                    source_info = {
                        'document_id': reference.get('location', {}).get('s3Location', {}).get('uri', ''),
                        'content': reference.get('content', {}).get('text', '')[:200] + '...',
                        'score': reference.get('score', 0),
                        'title': reference.get('metadata', {}).get('title', ''),
                        'url': reference.get('location', {}).get('s3Location', {}).get('uri', '')
                    }
                    sources.append(source_info)
                    print(f"  Processed source: {source_info}")
        else:
            print("No citations found in response")
        
        # PREVENT HALLUCINATION: If no sources found, return appropriate message
        if len(sources) == 0:
            print("⚠️ WARNING: No sources found - Knowledge Base may be empty or not synced")
            return {
                'answer': "I don't have access to the historical documents yet. The Knowledge Base may still be syncing or needs to be populated with data. Please try again later or contact support.",
                'sources': [],
                'entities': [],
                'warning': 'no_sources_found'
            }
        
        # Extract entities
        entities = []
        if 'metadata' in response:
            entities = response['metadata'].get('entities', [])
            print(f"Found {len(entities)} entities: {entities}")
        else:
            print("No metadata found in response")
        
        print(f"✓ Knowledge Base returned answer with {len(sources)} sources and {len(entities)} entities")
        
        return {
            'answer': answer,
            'sources': sources,
            'entities': entities
        }
        
    except Exception as e:
        print(f"ERROR querying Knowledge Base: {str(e)}")
        return {
            'answer': "I encountered an error while searching. Please try again.",
            'sources': [],
            'entities': [],
            'error': True
        }









