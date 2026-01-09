import json
import boto3
import os

ecs_client = boto3.client('ecs')

def lambda_handler(event, context):
    """
    Triggers Fargate task to collect bills from Congress API
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        
        # Get parameters
        start_congress = body.get('start_congress', os.environ.get('START_CONGRESS', '1'))
        end_congress = body.get('end_congress', os.environ.get('END_CONGRESS', '16'))
        bill_types = body.get('bill_types', os.environ.get('BILL_TYPES', 'hr,s'))
        
        # Fargate task configuration
        cluster_name = os.environ['ECS_CLUSTER_NAME']
        task_definition = os.environ['TASK_DEFINITION_ARN']
        subnet_ids = os.environ['SUBNET_IDS'].split(',')
        security_group_id = os.environ['SECURITY_GROUP_ID']
        bucket_name = os.environ['BUCKET_NAME']
        
        # Get KB IDs (optional - will be set after deployment)
        kb_id = os.environ.get('KNOWLEDGE_BASE_ID', '')
        ds_id = os.environ.get('DATA_SOURCE_ID', '')
        
        # Build environment variables for container
        container_env = [
            {'name': 'BUCKET_NAME', 'value': bucket_name},
            {'name': 'START_CONGRESS', 'value': str(start_congress)},
            {'name': 'END_CONGRESS', 'value': str(end_congress)},
            {'name': 'BILL_TYPES', 'value': bill_types},
        ]
        
        # Add KB IDs if available
        if kb_id:
            container_env.append({'name': 'KNOWLEDGE_BASE_ID', 'value': kb_id})
        if ds_id:
            container_env.append({'name': 'DATA_SOURCE_ID', 'value': ds_id})
        
        # Start Fargate task
        response = ecs_client.run_task(
            cluster=cluster_name,
            taskDefinition=task_definition,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': subnet_ids,
                    'assignPublicIp': 'ENABLED',
                    'securityGroups': [security_group_id]
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': 'collector',
                        'environment': container_env
                    }
                ]
            }
        )
        
        task_arn = response['tasks'][0]['taskArn']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Fargate task started successfully',
                'taskArn': task_arn,
                'parameters': {
                    'start_congress': start_congress,
                    'end_congress': end_congress,
                    'bill_types': bill_types
                }
            })
        }
        
    except Exception as e:
        print(f"Error starting Fargate task: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }