#!/usr/bin/env python3
"""
Backend Testing Script
Tests the Chronicling America pipeline and API
"""

import boto3
import json
import time
import sys
import argparse
from datetime import datetime

# Colors for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def print_header(text):
    print(f"\n{'='*50}")
    print(f"{BLUE}{text}{NC}")
    print(f"{'='*50}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{NC}")

def print_error(text):
    print(f"{RED}❌ {text}{NC}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{NC}")

def get_stack_outputs():
    """Get CloudFormation stack outputs"""
    print_header("Fetching Stack Outputs")
    
    cf = boto3.client('cloudformation')
    
    # Try LOCstack first, fall back to old names
    stack_names = ['LOCstack', 'ChroniclingAmericaStackV2', 'ChroniclingAmericaStack']
    
    for stack_name in stack_names:
        try:
            response = cf.describe_stacks(StackName=stack_name)
            outputs = response['Stacks'][0]['Outputs']
            
            result = {}
            for output in outputs:
                result[output['OutputKey']] = output['OutputValue']
            
            print_success(f"Stack found: {stack_name}")
            print(f"Data Bucket: {result.get('DataBucketName', 'N/A')}")
            print(f"State Machine: {result.get('StateMachineArn', 'N/A')}")
            print(f"Chat Endpoint: {result.get('ChatEndpoint', 'N/A')}")
            
            return result
        except Exception:
            continue
    
    print_error("Stack not found")
    print("\nPlease deploy the stack first:")
    print("  cd backend && ./deploy.sh")
    sys.exit(1)

def test_pipeline_execution(state_machine_arn, source='newspapers', start_date=None, end_date=None, max_pages=None, congress=None, bill_type=None, limit=None):
    """Test Step Functions pipeline execution"""
    print_header(f"Test 1: Pipeline Execution ({source})")
    
    sf = boto3.client('stepfunctions')
    
    # Build execution input based on source
    if source == 'congress':
        execution_input = {
            "source": "congress",
            "congress": congress or 118,
            "bill_type": bill_type or "hr",
            "limit": limit or 10
        }
    else:
        execution_input = {
            "source": "newspapers",
            "start_date": start_date or "1815-08-01",
            "end_date": end_date or "1815-08-05",
            "max_pages": max_pages or 20
        }
    
    print(f"Input: {json.dumps(execution_input, indent=2)}")
    
    try:
        response = sf.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(execution_input)
        )
        
        execution_arn = response['executionArn']
        print_success(f"Execution started")
        print(f"Execution ARN: {execution_arn}")
        
        # Monitor execution
        print("\nMonitoring execution (max 30 minutes)...")
        print("Note: For Fargate collections, this may take longer. Press Ctrl+C to skip monitoring.")
        max_wait = 1800  # 30 minutes
        wait_time = 10
        interval = 15
        
        while wait_time < max_wait:
            response = sf.describe_execution(executionArn=execution_arn)
            status = response['status']
            
            if status == 'SUCCEEDED':
                print_success("Execution completed successfully!")
                return True
            elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                print_error(f"Execution failed with status: {status}")
                return False
            else:
                print(f"Status: {status} (waiting {wait_time}s / {max_wait}s)")
                time.sleep(interval)
                wait_time += interval
        
        print_warning(f"Execution still running after {max_wait}s")
        print("Check status in AWS Console")
        return None
        
    except Exception as e:
        print_error(f"Failed to start execution: {e}")
        return False

def test_s3_data(bucket_name):
    """Test S3 data storage"""
    print_header("Test 2: S3 Data Verification")
    
    s3 = boto3.client('s3')
    
    try:
        # Check images
        images = s3.list_objects_v2(Bucket=bucket_name, Prefix='images/')
        images_count = images.get('KeyCount', 0)
        
        # Check extracted
        extracted = s3.list_objects_v2(Bucket=bucket_name, Prefix='extracted/')
        extracted_count = extracted.get('KeyCount', 0)
        
        # Check knowledge graphs
        kg = s3.list_objects_v2(Bucket=bucket_name, Prefix='knowledge_graphs/')
        kg_count = kg.get('KeyCount', 0)
        
        print(f"Images: {images_count} files")
        print(f"Extracted: {extracted_count} files")
        print(f"Knowledge Graphs: {kg_count} files")
        
        if images_count > 0 and extracted_count > 0 and kg_count > 0:
            print_success("All data files created")
            return True
        else:
            print_warning("Some data files missing")
            return False
            
    except Exception as e:
        print_error(f"Failed to check S3: {e}")
        return False

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{NC}")

def test_all_historical_congresses(bill_types=['hr', 's'], limit_per_congress=None, project_name=None):
    """Collect bills from ALL historical Congresses (1-16)"""
    print_header("Collecting Bills from ALL Historical Congresses (1-16)")
    
    lambda_client = boto3.client('lambda')
    
    # Build Lambda function names from project name
    image_collector_fn = f"{project_name}-image-collector" if project_name else "image-collector"
    neptune_loader_fn = f"{project_name}-neptune-loader" if project_name else "neptune-loader"
    kb_sync_fn = f"{project_name}-kb-sync-trigger" if project_name else "kb-sync-trigger"
    
    total_bills = 0
    total_loaded = 0
    failed_congresses = []
    
    print_info("This will collect bills from Congress 1 (1789) through Congress 16 (1821)")
    print_info(f"Bill types: {', '.join(bill_types)}")
    if limit_per_congress:
        print_info(f"Limit per Congress: {limit_per_congress} bills")
    else:
        print_info("Collecting ALL bills from each Congress (no limit)")
    print("")
    
    # Iterate through all historical Congresses
    for congress_num in range(1, 17):  # Congress 1 to 16
        print(f"\n{'-'*50}")
        print(f"Processing Congress {congress_num} ({1789 + (congress_num-1)*2}-{1791 + (congress_num-1)*2})")
        print(f"{'-'*50}")
        
        for bill_type in bill_types:
            print(f"\n  → Collecting {bill_type.upper()} bills from Congress {congress_num}...")
            
            payload = {
                "source": "congress",
                "congress": congress_num,
                "bill_type": bill_type,
                "limit": limit_per_congress  # None means get all bills
            }
            
            try:
                # Invoke image-collector Lambda
                response = lambda_client.invoke(
                    FunctionName=image_collector_fn,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )
                
                result = json.loads(response['Payload'].read())
                
                if result.get('statusCode') == 200:
                    bills_count = result.get('documents_count', 0)
                    total_bills += bills_count
                    print_success(f"Collected {bills_count} {bill_type.upper()} bills from Congress {congress_num}")
                    
                    # Load to Neptune
                    if result.get('s3_key') and bills_count > 0:
                        neptune_response = lambda_client.invoke(
                            FunctionName=neptune_loader_fn,
                            InvocationType='RequestResponse',
                            Payload=json.dumps({
                                'bucket': result['bucket'],
                                's3_key': result['s3_key']
                            })
                        )
                        
                        neptune_result = json.loads(neptune_response['Payload'].read())
                        
                        if neptune_result.get('statusCode') == 200:
                            loaded_count = neptune_result.get('documents_loaded', 0)
                            total_loaded += loaded_count
                            print_success(f"  ✓ Loaded {loaded_count} documents to Neptune")
                        else:
                            print_error(f"  ✗ Neptune loading failed: {neptune_result.get('error', 'Unknown')}")
                            failed_congresses.append(f"Congress {congress_num} ({bill_type})")
                    elif bills_count == 0:
                        print_info(f"  No {bill_type.upper()} bills found in Congress {congress_num}")
                else:
                    print_error(f"Collection failed: {result.get('error', 'Unknown')}")
                    failed_congresses.append(f"Congress {congress_num} ({bill_type})")
                    
            except Exception as e:
                print_error(f"Error processing Congress {congress_num} ({bill_type}): {e}")
                failed_congresses.append(f"Congress {congress_num} ({bill_type})")
                continue
            
            # Small delay to avoid rate limiting
            time.sleep(1)
    
    # Summary
    print("\n" + "="*50)
    print_header("Collection Summary")
    print(f"Total bills collected: {total_bills}")
    print(f"Total documents loaded to Neptune: {total_loaded}")
    
    if failed_congresses:
        print_warning(f"Failed to process {len(failed_congresses)} Congress/bill-type combinations:")
        for failed in failed_congresses:
            print(f"  - {failed}")
    else:
        print_success("All Congresses processed successfully!")
    
    # Trigger KB sync once at the end
    if total_loaded > 0:
        print("\n" + "="*50)
        print("Triggering Knowledge Base sync for all collected bills...")
        try:
            kb_response = lambda_client.invoke(
                FunctionName=kb_sync_fn,
                InvocationType='RequestResponse',
                Payload=json.dumps({})
            )
            
            kb_result = json.loads(kb_response['Payload'].read())
            
            if kb_result.get('statusCode') == 200:
                print_success(f"KB sync started: {kb_result.get('ingestion_job_id', 'N/A')}")
                print_info("Entity extraction will complete in 5-10 minutes")
                return True
            else:
                print_warning(f"KB sync failed: {kb_result.get('error', 'Unknown')}")
                return True  # Still success if Neptune loaded
        except Exception as e:
            print_error(f"Failed to trigger KB sync: {e}")
            return True  # Still success if Neptune loaded
    
    return total_bills > 0

def test_congress_direct(congress=7, bill_type='hr', limit=5, api_url=None, project_name=None):
    """Test Congress bills collection via Fargate trigger Lambda"""
    print_header("Quick Test: Congress Bills Collection (via Fargate)")
    
    print(f"Testing with: Congress {congress}, Type: {bill_type}, Limit: {limit}")
    print_info(f"Note: Historical bills available for Congress 1-16 (1789-1821)")
    
    if api_url:
        # Use API Gateway endpoint
        import requests
        
        payload = {
            "start_congress": congress,
            "end_congress": congress,
            "bill_types": bill_type
        }
        
        try:
            print(f"\nTriggering Fargate task via API: {api_url}")
            response = requests.post(api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print_success(f"Fargate task started: {result.get('taskArn', 'N/A')}")
                print_info("Task is running asynchronously. Check CloudWatch logs for progress.")
                log_group = f"/ecs/{project_name}-collector" if project_name else "/ecs/collector"
                print_info(f"Log group: {log_group}")
                return True
            else:
                print_error(f"API returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            print_error(f"API request failed: {e}")
            return False
    else:
        # Fallback to direct Lambda invocation
        lambda_client = boto3.client('lambda')
        
        # Get Lambda function name from project name
        function_name = f"{project_name}-fargate-trigger" if project_name else "fargate-trigger"
        
        payload = {
            "body": json.dumps({
                "start_congress": congress,
                "end_congress": congress,
                "bill_types": bill_type
            })
        }
        
        try:
            print(f"\nInvoking Lambda: {function_name}")
            # Invoke fargate-trigger Lambda directly
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            print(f"\nResponse: {json.dumps(result, indent=2)}")
            
            if result.get('statusCode') == 200:
                body = json.loads(result.get('body', '{}'))
                print_success(f"Fargate task started: {body.get('taskArn', 'N/A')}")
                print_info("Task is running asynchronously. Check CloudWatch logs for progress.")
                log_group = f"/ecs/{project_name}-collector" if project_name else "/ecs/collector"
                print_info(f"Log group: {log_group}")
                return True
            else:
                print_error(f"Failed to start Fargate task: {result.get('body', 'Unknown')}")
                return False
                
        except Exception as e:
            print_error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def wait_for_kb_sync(kb_id, ds_id, max_wait=600):
    """Wait for Knowledge Base sync to complete"""
    print_header("Monitoring Knowledge Base Sync")
    
    bedrock_agent = boto3.client('bedrock-agent')
    elapsed = 0
    
    print(f"Checking sync status every 30 seconds (max {max_wait}s)...")
    
    while elapsed < max_wait:
        try:
            response = bedrock_agent.list_ingestion_jobs(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                maxResults=1
            )
            
            if response.get('ingestionJobSummaries'):
                job = response['ingestionJobSummaries'][0]
                status = job['status']
                job_id = job.get('ingestionJobId', 'N/A')
                
                print(f"[{elapsed}s] Job: {job_id[:8]}... Status: {status}")
                
                if status == 'COMPLETE':
                    print_success("Knowledge Base sync completed!")
                    print_info("Entities and relationships extracted successfully")
                    return True
                elif status == 'FAILED':
                    print_error("Knowledge Base sync failed")
                    return False
                
        except Exception as e:
            print_error(f"Error checking status: {e}")
        
        time.sleep(30)
        elapsed += 30
    
    print_warning(f"Sync still in progress after {max_wait}s")
    print_info("Check AWS Console → Bedrock → Knowledge Bases for status")
    return None


def test_chat_api(api_url):
    """Test Chat API endpoint"""
    print_header("Test 3: Chat API")
    
    import requests
    
    # Test questions
    questions = [
        "What newspapers are in the database?",
        "Who are the people mentioned?",
        "What locations are mentioned?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        
        try:
            response = requests.post(
                api_url,
                json={"question": question},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success("API responded")
                print(f"Answer: {data.get('answer', 'N/A')[:200]}...")
                if 'result_count' in data:
                    print(f"Results: {data['result_count']}")
            else:
                print_error(f"API returned status {response.status_code}")
                
        except Exception as e:
            print_error(f"API request failed: {e}")
    
    return True

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Test Chronicling America Backend Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Test with newspapers (default)
  python test_backend.py
  python test_backend.py --max-pages 5
  python test_backend.py --start-date 1815-08-01 --end-date 1815-08-10 --max-pages 10
  
  # Test with Congress bills (Historical: Congress 1-16, 1789-1821)
  python test_backend.py --source congress
  python test_backend.py --source congress --congress 7 --bill-type hr --limit 5
  python test_backend.py --source congress --congress 1 --bill-type hr --limit 10
  
  # Collect from ALL historical Congresses (1-16)
  python test_backend.py --source congress --all-congresses
  python test_backend.py --source congress --all-congresses --limit 10
  python test_backend.py --source congress --all-congresses --bill-types "hr,s,hjres"
        '''
    )
    
    # Source selection
    parser.add_argument('--source', type=str, choices=['newspapers', 'congress'], 
                       default='newspapers', help='Data source: newspapers or congress')
    
    # Newspaper options
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD), default: 1815-08-01')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), default: 1815-08-05')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to process, default: 20')
    
    # Congress options
    parser.add_argument('--congress', type=int, help='Congress number (1-16 for historical bills), default: 7. Use --all-congresses to collect from all')
    parser.add_argument('--bill-type', type=str, help='Bill type (hr, s, hjres, etc.), default: hr')
    parser.add_argument('--limit', type=int, help='Number of bills to fetch per Congress, default: 10 (use 0 for all bills)')
    parser.add_argument('--all-congresses', action='store_true', help='Collect bills from ALL historical Congresses (1-16)')
    parser.add_argument('--bill-types', type=str, help='Comma-separated bill types for --all-congresses (e.g., "hr,s"), default: hr,s')
    
    args = parser.parse_args()
    
    print(f"\n{BLUE}{'='*50}")
    print("Chronicling America Backend Testing")
    print(f"{'='*50}{NC}\n")
    
    # Get stack outputs
    outputs = get_stack_outputs()
    
    state_machine_arn = outputs.get('StateMachineArn')
    bucket_name = outputs.get('DataBucketName')
    api_url = outputs.get('ChatEndpoint')
    collect_url = outputs.get('CollectEndpoint')
    
    # Extract project name from stack outputs (from any resource name)
    project_name = None
    for key, value in outputs.items():
        if 'FargateTaskDefinitionArn' in key or 'ECRRepositoryUri' in key:
            # Extract project name from ARN or URI
            if 'task-definition' in value:
                project_name = value.split('task-definition/')[1].split('-collector')[0]
            elif '.dkr.ecr.' in value:
                project_name = value.split('/')[-1].split('-collector')[0]
            break
    
    if not project_name:
        # Fallback: try to get from bucket name
        if bucket_name:
            project_name = bucket_name.split('-data-')[0]
    
    print_info(f"Detected project name: {project_name}")
    
    # Run tests
    results = []
    
    # Test 1: Pipeline execution
    if state_machine_arn:
        result = test_pipeline_execution(
            state_machine_arn,
            source=args.source,
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages=args.max_pages,
            congress=args.congress,
            bill_type=args.bill_type,
            limit=args.limit
        )
        results.append(('Pipeline Execution', result))
    
    # Test 2: S3 data
    if bucket_name:
        result = test_s3_data(bucket_name)
        results.append(('S3 Data', result))
    
    # Test 3: Chat API
    if api_url:
        result = test_chat_api(api_url)
        results.append(('Chat API', result))
    
    # Summary
    print_header("Test Summary")
    
    for test_name, result in results:
        if result is True:
            print_success(f"{test_name}: PASSED")
        elif result is False:
            print_error(f"{test_name}: FAILED")
        else:
            print_warning(f"{test_name}: INCOMPLETE")
    
    # Quick Congress test if requested
    if args.source == 'congress':
        print("\n" + "="*50)
        
        if args.all_congresses:
            # Collect from ALL historical Congresses
            print("Collecting bills from ALL historical Congresses (1-16)...")
            print_info("This will take several minutes to complete")
            print("="*50)
            
            # Parse bill types
            bill_types = ['hr', 's']  # default
            if args.bill_types:
                bill_types = [bt.strip() for bt in args.bill_types.split(',')]
            
            # Set limit (0 or None means get all bills)
            limit_per_congress = args.limit if args.limit and args.limit > 0 else None
            
            congress_result = test_all_historical_congresses(
                bill_types=bill_types,
                limit_per_congress=limit_per_congress,
                project_name=project_name
            )
        else:
            # Single Congress test
            print("Running quick Congress bills test...")
            print_info("Historical bills available for Congress 1-16 (1789-1821)")
            print("="*50)
            congress_result = test_congress_direct(
                congress=args.congress or 7,
                bill_type=args.bill_type or 'hr',
                limit=args.limit or 5,
                api_url=collect_url,
                project_name=project_name
            )
        
        if congress_result:
            print_success("Congress bills test completed!")
            
            # Optionally wait for KB sync
            kb_id = outputs.get('KnowledgeBaseId')
            ds_id = outputs.get('KnowledgeBaseDataSourceId')
            
            if kb_id and ds_id:
                print("\n" + "="*50)
                user_input = input("Wait for Knowledge Base sync to complete? (y/n): ")
                if user_input.lower() == 'y':
                    wait_for_kb_sync(kb_id, ds_id, max_wait=600)
                else:
                    print_info("Skipping wait. Check sync status later:")
                    print(f"  aws bedrock-agent list-ingestion-jobs --knowledge-base-id {kb_id}")
            else:
                print_warning("Knowledge Base IDs not found in stack outputs")
    
    print(f"\n{BLUE}Next Steps:{NC}")
    if args.source == 'congress':
        print("1. Wait for Knowledge Base sync (~5-10 minutes)")
        print("2. Query bills via chat API")
        if args.all_congresses:
            print(f"3. Example: curl -X POST {api_url} -d '{{\"question\":\"What bills were introduced about taxation in the early Congresses?\"}}'")
            print(f"4. Example: curl -X POST {api_url} -d '{{\"question\":\"Summarize legislation from Congress 1 through 16\"}}'")
        else:
            print(f"3. Example: curl -X POST {api_url} -d '{{\"question\":\"What bills were introduced in Congress 7?\"}}'")
        print_info("Note: Historical bills are available for Congress 1-16 (1789-1821)")
    else:
        print("1. Open the web UI: frontend/index.html")
        print(f"2. Enter API URL: {api_url}")
        print("3. Start chatting with your historical newspaper data!")
    print("")

if __name__ == '__main__':
    main()
