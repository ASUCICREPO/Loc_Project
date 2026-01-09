#!/usr/bin/env python3
"""
Test Knowledge Base Queries
Run this AFTER Fargate task completes and KB sync finishes
"""

import boto3
import sys

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{NC}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{NC}")

def print_error(text):
    print(f"{RED}❌ {text}{NC}")

def get_kb_info():
    """Get KB info from Lambda environment"""
    lambda_client = boto3.client('lambda')
    
    try:
        response = lambda_client.get_function_configuration(
            FunctionName='loc-testing-kb-sync-trigger'
        )
        
        env_vars = response.get('Environment', {}).get('Variables', {})
        
        kb_id = env_vars.get('KNOWLEDGE_BASE_ID')
        
        if not kb_id:
            print_error("Knowledge Base ID not found in Lambda environment")
            sys.exit(1)
        
        return kb_id
        
    except Exception as e:
        print_error(f"Error getting KB info: {e}")
        sys.exit(1)

def test_query(kb_id, question, model_arn):
    """Test a query"""
    print(f"\n{BLUE}Question:{NC} {question}")
    
    bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
    
    try:
        response = bedrock_runtime.retrieve_and_generate(
            input={'text': question},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': model_arn
                }
            }
        )
        
        answer = response['output']['text']
        citations = response.get('citations', [])
        
        print_success("Query successful!")
        print(f"\n{BLUE}Answer:{NC}\n{answer}\n")
        
        if citations:
            print(f"{BLUE}Citations:{NC} {len(citations)} sources")
            for i, citation in enumerate(citations[:3], 1):
                refs = citation.get('retrievedReferences', [])
                if refs:
                    content = refs[0].get('content', {}).get('text', '')
                    location = refs[0].get('location', {}).get('s3Location', {}).get('uri', 'N/A')
                    print(f"  {i}. {location}")
                    print(f"     {content[:100]}...")
        
        return True
        
    except Exception as e:
        print_error(f"Query failed: {e}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}")
    print("Knowledge Base Query Test")
    print(f"{'='*60}{NC}\n")
    
    # Get KB ID
    kb_id = get_kb_info()
    print(f"Knowledge Base ID: {kb_id}")
    
    # Use inference profile (cross-region)
    model_arn = 'arn:aws:bedrock:us-east-1:541064517181:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    print(f"Model: {model_arn}")
    
    # Test questions
    questions = [
        "What bills were introduced in Congress 7?",
        "Who are the people mentioned in the bills?",
        "Summarize the legislation from this Congress",
        "What bills mention taxation or revenue?"
    ]
    
    success_count = 0
    for question in questions:
        if test_query(kb_id, question, model_arn):
            success_count += 1
    
    # Summary
    print_header("Summary")
    print(f"Successful queries: {success_count}/{len(questions)}")
    
    if success_count == len(questions):
        print_success("All queries passed!")
    else:
        print_error(f"{len(questions) - success_count} queries failed")
    
    print("")

if __name__ == '__main__':
    main()
