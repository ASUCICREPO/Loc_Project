"""
Knowledge Base Sync Trigger Lambda
Triggers Bedrock Knowledge Base sync for congress-bills data source only
(Newspapers are synced via rotating batch script)
"""

import json
import os
import boto3

bedrock_agent = boto3.client('bedrock-agent')

KB_ID = os.environ['KNOWLEDGE_BASE_ID']


def lambda_handler(event, context):
    """
    Trigger Knowledge Base ingestion job for congress-bills data source
    
    Input: 
        - dataSourceName (optional): Name of data source to sync (default: congress-bills)
        - dataSourceId (optional): ID of data source to sync
    Output: Ingestion job details
    """
    # Log request metadata only
    print(f"KB sync trigger invoked for KB: {KB_ID}")
    
    # Get data source to sync (default to congress-bills)
    ds_name = event.get('dataSourceName', 'congress-bills')
    ds_id = event.get('dataSourceId')
    
    # If no data source ID provided, look it up by name
    if not ds_id:
        try:
            response = bedrock_agent.list_data_sources(
                knowledgeBaseId=KB_ID
            )
            
            for ds in response.get('dataSourceSummaries', []):
                if ds['name'] == ds_name:
                    ds_id = ds['dataSourceId']
                    break
            
            if not ds_id:
                return {
                    'statusCode': 404,
                    'error': f"Data source '{ds_name}' not found",
                    'message': 'Failed to find data source'
                }
                
        except Exception as e:
            print(f"❌ Error finding data source: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'statusCode': 500,
                'error': str(e),
                'message': 'Failed to find data source'
            }
    
    print(f"Triggering KB sync for KB: {KB_ID}, DS: {ds_name} ({ds_id})")
    
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KB_ID,
            dataSourceId=ds_id
        )
        
        job = response['ingestionJob']
        job_id = job['ingestionJobId']
        status = job['status']
        
        print(f"✅ Ingestion job started: {job_id}")
        print(f"Status: {status}")
        
        return {
            'statusCode': 200,
            'ingestion_job_id': job_id,
            'status': status,
            'knowledge_base_id': KB_ID,
            'data_source_id': ds_id,
            'data_source_name': ds_name,
            'message': 'Knowledge Base sync started successfully'
        }
        
    except Exception as e:
        print(f"❌ Error starting ingestion job: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'error': str(e),
            'message': 'Failed to start Knowledge Base sync'
        }
