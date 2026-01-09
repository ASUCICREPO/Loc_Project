#!/usr/bin/env python3
"""
Complete Pipeline Test
Tests the full flow: Fargate → S3 → Knowledge Base → Query
"""

import boto3
import json
import time
import sys
import os

# Set region - CHANGE THIS to match your deployment region
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')

# Configure boto3 to use the correct region
boto3.setup_default_session(region_name=AWS_REGION)

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

print(f"Using AWS Region: {AWS_REGION}")

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{BLUE}{text}{NC}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{NC}")

def print_error(text):
    print(f"{RED}❌ {text}{NC}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{NC}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{NC}")

def get_resources():
    """Get deployed resources"""
    print_header("Step 1: Finding Deployed Resources")
    
    cf = boto3.client('cloudformation')
    
    # Try to find the stack
    stack_names = ['LOCstack', 'ChroniclingAmericaStackV2', 'ChroniclingAmericaStack']
    
    for stack_name in stack_names:
        try:
            response = cf.describe_stacks(StackName=stack_name)
            outputs = response['Stacks'][0]['Outputs']
            
            resources = {}
            for output in outputs:
                resources[output['OutputKey']] = output['OutputValue']
            
            print_success(f"Found stack: {stack_name}")
            
            # Extract what we need
            data_bucket = resources.get('DataBucketName')
            kb_role_arn = resources.get('KnowledgeBaseRoleArn')
            
            print(f"Data Bucket: {data_bucket}")
            print(f"KB Role: {kb_role_arn}")
            
            # Get KB and DS IDs from Lambda environment variables
            lambda_client = boto3.client('lambda')
            
            # Try to find the project name from bucket
            project_name = data_bucket.split('-data-')[0] if data_bucket else 'loc-testing'
            
            print(f"Project Name: {project_name}")
            
            # Get KB IDs from Lambda
            try:
                kb_sync_fn = f"{project_name}-kb-sync-trigger"
                response = lambda_client.get_function_configuration(FunctionName=kb_sync_fn)
                env_vars = response.get('Environment', {}).get('Variables', {})
                
                kb_id = env_vars.get('KNOWLEDGE_BASE_ID')
                ds_id = env_vars.get('DATA_SOURCE_ID')
                
                print(f"Knowledge Base ID: {kb_id}")
                print(f"Data Source ID: {ds_id}")
                
                return {
                    'project_name': project_name,
                    'data_bucket': data_bucket,
                    'kb_id': kb_id,
                    'ds_id': ds_id,
                    'kb_sync_fn': kb_sync_fn,
                    'fargate_trigger_fn': f"{project_name}-fargate-trigger",
                    'chat_handler_fn': f"{project_name}-chat-handler"
                }
            except Exception as e:
                print_error(f"Could not get Lambda config: {e}")
                return None
                
        except Exception:
            continue
    
    print_error("Stack not found. Please deploy first:")
    print("  cd backend && ./deploy.sh")
    sys.exit(1)

def trigger_fargate_collection(resources, start_congress=7, end_congress=None, bill_types='hr,s,hjres,sjres,hconres,sconres,hres,sres'):
    """Step 2: Trigger Fargate task to collect data"""
    print_header("Step 2: Triggering Fargate Data Collection")
    
    lambda_client = boto3.client('lambda')
    
    # If end_congress not specified, use start_congress
    if end_congress is None:
        end_congress = start_congress
    
    payload = {
        "body": json.dumps({
            "start_congress": start_congress,
            "end_congress": end_congress,
            "bill_types": bill_types
        })
    }
    
    if start_congress == end_congress:
        print(f"Collecting bills from Congress {start_congress}, types: {bill_types}")
    else:
        print(f"Collecting bills from Congresses {start_congress}-{end_congress}, types: {bill_types}")
    print(f"Invoking Lambda: {resources['fargate_trigger_fn']}")
    
    try:
        response = lambda_client.invoke(
            FunctionName=resources['fargate_trigger_fn'],
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        
        if result.get('statusCode') == 200:
            body = json.loads(result.get('body', '{}'))
            task_arn = body.get('taskArn', 'N/A')
            print_success(f"Fargate task started!")
            print(f"Task ARN: {task_arn}")
            print_info("Task is collecting bills from Congress API...")
            return task_arn
        else:
            error_body = result.get('body', '{}')
            if isinstance(error_body, str):
                error_body = json.loads(error_body)
            error_msg = error_body.get('error', 'Unknown error')
            print_error(f"Failed to start task: {error_msg}")
            
            if 'SECURITY_GROUP_ID' in error_msg:
                print_warning("The Fargate trigger Lambda is missing SECURITY_GROUP_ID")
                print_info("Solution: Redeploy the stack with the updated CDK:")
                print("  cd backend && ./deploy.sh")
            
            return None
            
    except Exception as e:
        print_error(f"Error: {e}")
        return None

def wait_for_s3_data(resources, max_wait=300):
    """Step 3: Wait for data to appear in S3"""
    print_header("Step 3: Waiting for Data in S3")
    
    s3 = boto3.client('s3')
    bucket = resources['data_bucket']
    
    print(f"Checking bucket: {bucket}")
    print(f"Looking for files in: extracted/")
    print(f"Max wait time: {max_wait}s")
    print("")
    print_info("Fargate task is:")
    print("  1. Calling Congress API")
    print("  2. Extracting bill text")
    print("  3. Uploading to S3")
    print("")
    
    elapsed = 0
    interval = 15
    
    while elapsed < max_wait:
        try:
            response = s3.list_objects_v2(
                Bucket=bucket,
                Prefix='extracted/',
                MaxKeys=10
            )
            
            file_count = response.get('KeyCount', 0)
            
            if file_count > 0:
                print_success(f"Found {file_count} files in S3!")
                
                # Show some files
                for obj in response.get('Contents', [])[:5]:
                    print(f"  - {obj['Key']} ({obj['Size']} bytes)")
                
                return True
            else:
                print(f"[{elapsed}s] No files yet... (waiting)")
                
        except Exception as e:
            print_error(f"Error checking S3: {e}")
        
        time.sleep(interval)
        elapsed += interval
    
    print_warning(f"No files found after {max_wait}s")
    print_info("Check CloudWatch logs for Fargate task status:")
    print(f"  Log group: /ecs/{resources['project_name']}-collector")
    print(f"  aws logs tail /ecs/{resources['project_name']}-collector --follow")
    return False

def trigger_kb_sync(resources):
    """Step 4: Trigger Knowledge Base sync"""
    print_header("Step 4: Triggering Knowledge Base Sync")
    
    bedrock_agent = boto3.client('bedrock-agent')
    
    kb_id = resources['kb_id']
    ds_id = resources['ds_id']
    
    print(f"Knowledge Base: {kb_id}")
    print(f"Data Source: {ds_id}")
    
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id
        )
        
        job_id = response['ingestionJob']['ingestionJobId']
        print_success(f"Ingestion job started!")
        print(f"Job ID: {job_id}")
        return job_id
        
    except Exception as e:
        print_error(f"Failed to start ingestion: {e}")
        return None

def wait_for_kb_sync(resources, job_id, max_wait=600):
    """Step 5: Wait for Knowledge Base sync to complete"""
    print_header("Step 5: Waiting for Knowledge Base Sync")
    
    bedrock_agent = boto3.client('bedrock-agent')
    
    kb_id = resources['kb_id']
    ds_id = resources['ds_id']
    
    print(f"Monitoring job: {job_id}")
    print(f"Max wait time: {max_wait}s")
    print("")
    print_info("This includes:")
    print("  - Document chunking")
    print("  - Embedding generation (Titan Embed v2)")
    print("  - Entity extraction (Claude 3 Haiku)")
    print("  - Graph building (Neptune Analytics)")
    print("")
    
    elapsed = 0
    interval = 30
    
    while elapsed < max_wait:
        try:
            response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                ingestionJobId=job_id
            )
            
            job = response['ingestionJob']
            status = job['status']
            
            # Get statistics if available
            stats = job.get('statistics', {})
            docs_scanned = stats.get('numberOfDocumentsScanned', 0)
            docs_modified = stats.get('numberOfModifiedDocuments', 0)
            docs_deleted = stats.get('numberOfDeletedDocuments', 0)
            
            print(f"[{elapsed}s] Status: {status}")
            if docs_scanned > 0:
                print(f"  Documents scanned: {docs_scanned}")
                print(f"  Documents modified: {docs_modified}")
            
            if status == 'COMPLETE':
                print_success("Knowledge Base sync completed!")
                print(f"Total documents processed: {docs_scanned}")
                print_info("Entities and relationships extracted successfully")
                return True
            elif status == 'FAILED':
                print_error("Knowledge Base sync failed")
                failure_reasons = job.get('failureReasons', [])
                for reason in failure_reasons:
                    print(f"  Reason: {reason}")
                return False
            
        except Exception as e:
            print_error(f"Error checking status: {e}")
        
        time.sleep(interval)
        elapsed += interval
    
    print_warning(f"Sync still in progress after {max_wait}s")
    print_info("Check AWS Console → Bedrock → Knowledge Bases for status")
    return None

def test_query(resources, question, model_arn=None):
    """Step 6: Test querying the Knowledge Base"""
    print_header("Step 6: Testing Knowledge Base Query")
    
    bedrock_runtime = boto3.client('bedrock-agent-runtime')
    
    kb_id = resources['kb_id']
    
    # Use provided model ARN or default to inference profile
    if not model_arn:
        model_arn = f'arn:aws:bedrock:{AWS_REGION}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
    
    print(f"Question: {question}")
    print(f"Model: {model_arn}")
    print("")
    
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
        print(f"\nAnswer:\n{answer}\n")
        
        if citations:
            print(f"Citations: {len(citations)} sources")
            for i, citation in enumerate(citations[:3], 1):
                refs = citation.get('retrievedReferences', [])
                if refs:
                    content = refs[0].get('content', {}).get('text', '')
                    print(f"\n  Source {i}: {content[:100]}...")
        
        return True
        
    except Exception as e:
        print_error(f"Query failed: {e}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}")
    print("Complete Pipeline Test")
    print("Fargate → S3 → Knowledge Base → Query")
    print(f"{'='*60}{NC}\n")
    
    # Get resources
    resources = get_resources()
    if not resources:
        sys.exit(1)
    
    # Check if we have KB IDs
    if not resources.get('kb_id') or not resources.get('ds_id'):
        print_error("Knowledge Base IDs not found!")
        print_info("Make sure the deployment completed successfully")
        sys.exit(1)
    
    # Step 2: Trigger Fargate collection for all Congresses 1-16 with all bill types
    print_info("Collecting data from Congresses 1 through 16...")
    print_info("Bill types: hr, s, hjres, sjres, hconres, sconres, hres, sres")
    task_arn = trigger_fargate_collection(
        resources, 
        start_congress=1, 
        end_congress=16, 
        bill_types='hr,s,hjres,sjres,hconres,sconres,hres,sres'
    )
    if not task_arn:
        print_error("Failed to start Fargate task")
        print("")
        print_info("If you see 'SECURITY_GROUP_ID' error, redeploy the stack:")
        print("  cd backend && ./deploy.sh")
        print("")
        print_info("The CDK stack has been updated to include the security group.")
        sys.exit(1)
    
    # Step 3: Wait for S3 data
    print_info("Waiting for Fargate task to collect and upload data...")
    if not wait_for_s3_data(resources, max_wait=300):
        print_error("No data appeared in S3")
        print("")
        print_info("Troubleshooting:")
        print("  1. Check Fargate task logs:")
        print(f"     aws logs tail /ecs/{resources['project_name']}-collector --follow")
        print("  2. Check task status:")
        print(f"     aws ecs list-tasks --cluster {resources['project_name']}-cluster")
        print("  3. Verify Congress API is accessible")
        sys.exit(1)
    
    # Step 4: Wait for Fargate to complete and trigger KB sync
    print_header("Step 4: Waiting for Fargate Task to Complete")
    print_info("Fargate task will:")
    print("  1. Finish collecting all bills")
    print("  2. Upload all files to S3")
    print("  3. Automatically trigger KB sync")
    print("")
    print_info("This may take 5-15 minutes total")
    print_info("You can monitor:")
    print(f"  - Fargate logs: aws logs tail /ecs/{resources['project_name']}-collector --follow")
    print(f"  - S3 files: aws s3 ls s3://{resources['data_bucket']}/extracted/")
    print("")
    print_success("Pipeline triggered successfully!")
    print("")
    print_info("To check KB sync status later:")
    print(f"  aws bedrock-agent list-ingestion-jobs \\")
    print(f"    --knowledge-base-id {resources['kb_id']} \\")
    print(f"    --data-source-id {resources['ds_id']} \\")
    print(f"    --region {AWS_REGION}")
    print("")
    
    # Don't wait or test queries - let Fargate handle everything
    return
    
    # Step 6: Test queries (removed - will be done after Fargate completes)
    # Summary removed - Fargate handles everything automatically
    
    print(f"\n{BLUE}Next Steps:{NC}")
    print("1. Collect more data:")
    print(f"   python test_complete_pipeline.py")
    print("")
    print("2. Query via CLI:")
    print(f"   aws bedrock-agent-runtime retrieve-and-generate \\")
    print(f"     --input '{{\"text\":\"Your question\"}}' \\")
    print(f"     --retrieve-and-generate-configuration '{{...}}'")
    print("")
    print("3. Monitor costs:")
    print(f"   - Neptune Analytics: Check graph capacity")
    print(f"   - Bedrock: Monitor token usage")
    print("")

if __name__ == '__main__':
    main()
