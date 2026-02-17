#!/usr/bin/env python3
"""
Direct Ingestion Module for Knowledge Base
Uses IngestKnowledgeBaseDocuments API to add files without 1000-file sync limit
"""

import os
import boto3
import time
import concurrent.futures
import threading

# AWS clients
s3 = boto3.client('s3')
bedrock_agent = boto3.client('bedrock-agent')

BUCKET_NAME = os.environ.get('BUCKET_NAME')


def trigger_kb_sync_with_direct_ingestion(kb_id: str):
    """
    Trigger Knowledge Base sync using Direct Ingestion API
    
    Strategy:
    1. Sync congress-bills data source (traditional sync, only 985 files)
    2. For newspapers, use IngestKnowledgeBaseDocuments API to add files directly
    3. Process files in parallel (10 concurrent requests) for faster ingestion
    4. No 1000-file limit, no prefix rotation, no deletions!
    
    This is much faster and simpler than traditional sync approach
    """
    try:
        if not kb_id:
            print("⚠️  KB sync skipped: KNOWLEDGE_BASE_ID not set")
            return
        
        print(f"\n{'='*60}")
        print("Triggering Knowledge Base Sync with Direct Ingestion API")
        print(f"{'='*60}")
        print(f"Knowledge Base ID: {kb_id}")
        
        # List all data sources for this Knowledge Base
        print("\nFetching data sources...")
        response = bedrock_agent.list_data_sources(
            knowledgeBaseId=kb_id,
            maxResults=10
        )
        
        data_sources = {ds['name']: ds['dataSourceId'] for ds in response.get('dataSourceSummaries', [])}
        
        if not data_sources:
            print("⚠️  No data sources found for this Knowledge Base")
            return
        
        print(f"Found {len(data_sources)} data sources: {', '.join(data_sources.keys())}")
        
        # Step 1: Sync congress-bills using traditional sync (only 985 files, fast)
        if 'congress-bills' in data_sources:
            print(f"\n{'='*60}")
            print(f"[1/2] Syncing: congress-bills (traditional sync)")
            print(f"{'='*60}")
            
            sync_data_source_traditional(kb_id, data_sources['congress-bills'], 'congress-bills')
        else:
            print("⚠️  'congress-bills' data source not found, skipping")
        
        # Step 2: Ingest newspapers using Direct Ingestion API
        if 'newspapers' not in data_sources:
            print("⚠️  'newspapers' data source not found, skipping newspaper ingestion")
            return
        
        newspapers_ds_id = data_sources['newspapers']
        
        print(f"\n{'='*60}")
        print(f"[2/2] Ingesting: newspapers (Direct Ingestion API)")
        print(f"{'='*60}")
        
        # Get all newspaper files from S3
        print("\nScanning S3 for newspaper files...")
        newspaper_files = list_newspaper_files_in_s3()
        print(f"Found {len(newspaper_files)} newspaper files to ingest")
        
        if len(newspaper_files) == 0:
            print("⚠️  No newspaper files found in S3")
            return
        
        # Ingest files using Direct Ingestion API (10 concurrent)
        ingest_files_directly(kb_id, newspapers_ds_id, newspaper_files)
        
        print(f"\n{'='*60}")
        print("All data sources sync complete!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"⚠️  Failed to trigger KB sync: {e}")
        import traceback
        traceback.print_exc()
        print("You can trigger it manually later from AWS Console")


def sync_data_source_traditional(kb_id: str, ds_id: str, ds_name: str):
    """Sync a data source using traditional StartIngestionJob (for bills)"""
    try:
        # Start ingestion job
        sync_response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id
        )
        
        job_id = sync_response['ingestionJob']['ingestionJobId']
        print(f"✓ Ingestion job started: {job_id}")
        print("Waiting for ingestion to complete...")
        
        # Poll for completion
        poll_interval = 30
        elapsed = 0
        
        while True:
            time.sleep(poll_interval)
            elapsed += poll_interval
            
            # Check job status
            job_response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                ingestionJobId=job_id
            )
            
            status = job_response['ingestionJob']['status']
            
            # Log progress every 5 minutes
            if elapsed % 300 == 0:
                minutes = elapsed // 60
                print(f"  Status: {status} ({minutes} minutes elapsed)")
            
            if status == 'COMPLETE':
                stats = job_response['ingestionJob'].get('statistics', {})
                print(f"\n✓ Ingestion COMPLETE for {ds_name}")
                print(f"  Documents scanned: {stats.get('numberOfDocumentsScanned', 0)}")
                print(f"  Documents indexed: {stats.get('numberOfNewDocumentsIndexed', 0)}")
                print(f"  Time taken: {elapsed // 60} minutes")
                return True
            
            elif status == 'FAILED':
                failure_reasons = job_response['ingestionJob'].get('failureReasons', [])
                print(f"\n✗ Ingestion FAILED for {ds_name}")
                print(f"  Failure reasons: {', '.join(failure_reasons)}")
                return False
        
    except Exception as e:
        print(f"\n✗ Failed to sync {ds_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_newspaper_files_in_s3() -> list:
    """List all newspaper .txt files in S3 newspapers/ prefix"""
    try:
        files = []
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix='newspapers/'
        )
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                # Only include .txt files, not .metadata.json files
                if key.endswith('.txt'):
                    files.append(key)
        
        return files
        
    except Exception as e:
        print(f"⚠️  Error listing newspaper files: {e}")
        return []


def ingest_files_directly(kb_id: str, ds_id: str, files: list):
    """
    Ingest files directly using IngestKnowledgeBaseDocuments API
    Processes files in parallel (2 concurrent requests for maximum safety)
    AWS limit: 10 concurrent IngestKnowledgeBaseDocuments + DeleteKnowledgeBaseDocuments per account
    """
    total_files = len(files)
    successful = 0
    failed = 0
    lock = threading.Lock()
    
    print(f"\nIngesting {total_files} files using Direct Ingestion API...")
    print(f"Processing with 2 concurrent requests (conservative for maximum reliability)")
    print(f"Estimated time: {(total_files / 2 / 60):.1f} minutes (~{(total_files / 2 / 3600):.1f} hours)\n")
    
    def ingest_single_file(file_key: str, index: int) -> bool:
        """Ingest a single file with retry logic"""
        nonlocal successful, failed
        
        max_retries = 5
        base_delay = 2  # Start with 2 seconds (increased from 1)
        
        for attempt in range(max_retries):
            try:
                # Log progress every 100 files
                if index % 100 == 0:
                    with lock:
                        progress = (index / total_files) * 100
                        print(f"Progress: {index}/{total_files} ({progress:.1f}%) - Success: {successful}, Failed: {failed}")
                
                # Prepare document for ingestion
                document = {
                    'content': {
                        'dataSourceType': 'S3',
                        's3': {
                            's3Location': {
                                'uri': f's3://{BUCKET_NAME}/{file_key}'
                            }
                        }
                    }
                }
                
                # Check if metadata file exists
                metadata_key = f"{file_key}.metadata.json"
                try:
                    s3.head_object(Bucket=BUCKET_NAME, Key=metadata_key)
                    # Metadata exists, include it
                    document['metadata'] = {
                        's3Location': {
                            'uri': f's3://{BUCKET_NAME}/{metadata_key}'
                        },
                        'type': 'S3_LOCATION'
                    }
                except:
                    # No metadata file, that's okay
                    pass
                
                # Ingest the document
                bedrock_agent.ingest_knowledge_base_documents(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_id,
                    documents=[document]
                )
                
                with lock:
                    successful += 1
                return True
                
            except Exception as e:
                error_str = str(e)
                # Check if it's a throttling/concurrency error
                if ("throttl" in error_str.lower() or "concurrent" in error_str.lower() or "validationexception" in error_str.lower()) and attempt < max_retries - 1:
                    # Retry with exponential backoff + jitter
                    delay = base_delay * (2 ** attempt) + (attempt * 0.5)  # Add jitter
                    print(f"  ⚠️  Throttled, retrying {file_key} in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # Final failure or non-throttling error
                    with lock:
                        failed += 1
                        # Log ALL errors (removed the limit)
                        print(f"✗ Error ingesting {file_key}: {error_str}")
                    return False
    
    # Process files in parallel with ThreadPoolExecutor (2 concurrent for maximum safety)
    # AWS limit: 10 concurrent IngestKnowledgeBaseDocuments + DeleteKnowledgeBaseDocuments per account
    # Using 2 workers provides 80% headroom below the limit, ensuring reliable ingestion
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit all files for processing
        futures = {executor.submit(ingest_single_file, file_key, idx): file_key 
                  for idx, file_key in enumerate(files, 1)}
        
        # Wait for all to complete
        concurrent.futures.wait(futures)
    
    elapsed_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"Direct Ingestion Complete!")
    print(f"{'='*60}")
    print(f"Total files: {total_files}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Time taken: {elapsed_time/60:.1f} minutes ({elapsed_time/3600:.1f} hours)")
    print(f"Average: {elapsed_time/total_files:.2f} seconds per file")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    """
    Main execution: Sync Knowledge Base using Direct Ingestion API
    
    Usage:
        python direct_ingestion.py
    
    Environment Variables:
        KNOWLEDGE_BASE_ID - Required
        BUCKET_NAME - Required
    """
    import sys
    
    # Get Knowledge Base ID from environment
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
    
    if not kb_id:
        print("❌ Error: KNOWLEDGE_BASE_ID environment variable not set")
        print("\nUsage:")
        print("  export KNOWLEDGE_BASE_ID=<your-kb-id>")
        print("  export BUCKET_NAME=<your-bucket-name>")
        print("  python direct_ingestion.py")
        sys.exit(1)
    
    if not BUCKET_NAME:
        print("❌ Error: BUCKET_NAME environment variable not set")
        print("\nUsage:")
        print("  export BUCKET_NAME=<your-bucket-name>")
        print("  python direct_ingestion.py")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print("Direct Ingestion Script")
    print(f"{'='*60}")
    print(f"Knowledge Base ID: {kb_id}")
    print(f"S3 Bucket: {BUCKET_NAME}")
    print(f"{'='*60}\n")
    
    # Run the sync
    trigger_kb_sync_with_direct_ingestion(kb_id)
    
    print("\n✅ Direct ingestion complete!")
    print("Files have been ingested into the Knowledge Base.")
    print("Wait 1-2 minutes for indexing to complete.\n")
