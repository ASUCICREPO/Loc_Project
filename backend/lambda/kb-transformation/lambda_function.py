"""
Knowledge Base Custom Transformation Lambda
Transforms bill documents and adds metadata to each chunk for precise filtering

This Lambda runs DURING chunking and adds structured metadata to each chunk:
- Extracts bill metadata from S3 object metadata
- Attaches metadata to every chunk for exact filtering
- Enables precise bill retrieval using metadata filters

Input: Document chunks from Knowledge Base
Output: Chunks with structured metadata attached
"""

import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Transform document chunks and add structured metadata
    
    Actual event structure from Knowledge Base:
    {
        "version": "1.0",
        "bucketName": "loc-transformation-541064517181-us-east-1",
        "knowledgeBaseId": "ULNF0JAYER",
        "dataSourceId": "F8RGOJVWHT",
        "ingestionJobId": "WC4RZUYTQU",
        "priorTask": "CHUNKING",
        "inputFiles": [
            {
                "contentBatches": [
                    {
                        "key": "temp/aws/bedrock/.../extracted/congress_11/hr_39_1.JSON"
                    }
                ],
                "originalFileLocation": {
                    "type": "S3",
                    "s3_location": {
                        "uri": "s3://congress-bills-data-541064517181-us-east-1/extracted/congress_11/hr_39.txt"
                    }
                }
            }
        ]
    }
    """
    try:
        logger.info(f"Transformation event received")
        logger.info(f"Processing {len(event.get('inputFiles', []))} input files")
        
        # Get S3 client to read original file metadata and chunk content
        s3_client = boto3.client('s3')
        
        # Process each input file
        for input_file in event.get('inputFiles', []):
            # Get original file location to extract S3 metadata
            original_location = input_file.get('originalFileLocation', {})
            if original_location.get('type') == 'S3':
                original_s3_uri = original_location.get('s3_location', {}).get('uri', '')
                logger.info(f"Original file: {original_s3_uri}")
                
                # Parse S3 URI to get bucket and key
                if original_s3_uri.startswith('s3://'):
                    parts = original_s3_uri[5:].split('/', 1)
                    if len(parts) == 2:
                        source_bucket, source_key = parts
                        
                        # Get S3 metadata from original file
                        try:
                            response = s3_client.head_object(Bucket=source_bucket, Key=source_key)
                            file_metadata = response.get('Metadata', {})
                            
                            # Extract bill information from S3 metadata
                            bill_id = file_metadata.get('bill_id', 'unknown')
                            congress = file_metadata.get('congress', 'unknown')
                            bill_type = file_metadata.get('bill_type', 'unknown')
                            bill_number = file_metadata.get('bill_number', 'unknown')
                            title = file_metadata.get('title', 'N/A')
                            introduced_date = file_metadata.get('introduced_date', 'N/A')
                            latest_action = file_metadata.get('latest_action', 'N/A')
                            latest_action_date = file_metadata.get('latest_action_date', 'N/A')
                            
                            logger.info(f"Extracted metadata - Bill ID: {bill_id}, Congress: {congress}, Type: {bill_type}, Number: {bill_number}")
                            
                            # Process each content batch (chunk)
                            for batch in input_file.get('contentBatches', []):
                                chunk_key = batch.get('key', '')
                                if chunk_key:
                                    # Read the chunk content from transformation bucket
                                    try:
                                        chunk_response = s3_client.get_object(
                                            Bucket=event.get('bucketName', ''),
                                            Key=chunk_key
                                        )
                                        chunk_content = json.loads(chunk_response['Body'].read().decode('utf-8'))
                                        
                                        # Handle the actual JSON structure: {"fileContents": [{"contentBody": "...", "contentMetadata": {}}]}
                                        if 'fileContents' in chunk_content:
                                            for file_content in chunk_content['fileContents']:
                                                if 'contentMetadata' not in file_content:
                                                    file_content['contentMetadata'] = {}
                                                
                                                # Add our structured metadata to each file content
                                                file_content['contentMetadata'].update({
                                                    # Core identifiers for filtering
                                                    "bill_id": bill_id,
                                                    "congress": congress,
                                                    "bill_type": bill_type.upper(),
                                                    "bill_number": bill_number,
                                                    "entity_type": "bill",
                                                    
                                                    # Additional metadata for enriched responses
                                                    "title": title,
                                                    "introduced_date": introduced_date,
                                                    "latest_action": latest_action,
                                                    "latest_action_date": latest_action_date,
                                                })
                                        else:
                                            # Fallback: add metadata to root level if structure is different
                                            if 'contentMetadata' not in chunk_content:
                                                chunk_content['contentMetadata'] = {}
                                            
                                            chunk_content['contentMetadata'].update({
                                                "bill_id": bill_id,
                                                "congress": congress,
                                                "bill_type": bill_type.upper(),
                                                "bill_number": bill_number,
                                                "entity_type": "bill",
                                                "title": title,
                                                "introduced_date": introduced_date,
                                                "latest_action": latest_action,
                                                "latest_action_date": latest_action_date,
                                            })
                                        
                                        # Write the updated chunk back to S3
                                        s3_client.put_object(
                                            Bucket=event.get('bucketName', ''),
                                            Key=chunk_key,
                                            Body=json.dumps(chunk_content),
                                            ContentType='application/json'
                                        )
                                        
                                        logger.info(f"Updated chunk {chunk_key} with metadata")
                                        
                                    except Exception as e:
                                        logger.error(f"Error processing chunk {chunk_key}: {str(e)}")
                                        
                        except Exception as e:
                            logger.error(f"Error reading original file metadata: {str(e)}")
        
        logger.info("Transformation completed successfully")
        
        # Return the correct format as per AWS documentation
        # Knowledge Base expects: {"outputFiles": [...]}
        output_files = []
        
        for input_file in event.get('inputFiles', []):
            output_file = {
                "originalFileLocation": input_file.get("originalFileLocation", {}),
                "fileMetadata": input_file.get("fileMetadata", {}),
                "contentBatches": input_file.get("contentBatches", [])
            }
            output_files.append(output_file)
        
        response = {
            "outputFiles": output_files
        }
        
        logger.info(f"Returning correct format with {len(output_files)} output files")
        return response
        
    except Exception as e:
        logger.error(f"Transformation error: {str(e)}", exc_info=True)
        logger.error(f"Returning original files due to error")
        
        # Return error response in correct format
        output_files = []
        for input_file in event.get('inputFiles', []):
            output_file = {
                "originalFileLocation": input_file.get("originalFileLocation", {}),
                "fileMetadata": input_file.get("fileMetadata", {}),
                "contentBatches": input_file.get("contentBatches", [])
            }
            output_files.append(output_file)
        
        return {
            "outputFiles": output_files
        }
