"""
Knowledge Base Sync Trigger Lambda
Automatically triggers Bedrock Knowledge Base sync after Neptune loading
"""

import json
import os
import boto3

bedrock_agent = boto3.client('bedrock-agent')

KB_ID = os.environ['KNOWLEDGE_BASE_ID']
DS_ID = os.environ['DATA_SOURCE_ID']


def lambda_handler(event, context):
    """
    Trigger Knowledge Base ingestion job to extract entities from Neptune
    
    Input: Result from neptune-loader (optional)
    Output: Ingestion job details
    """
    print(f"Event: {json.dumps(event)}")
    print(f"Triggering KB sync for KB: {KB_ID}, DS: {DS_ID}")
    
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KB_ID,
            dataSourceId=DS_ID
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
            'data_source_id': DS_ID,
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
