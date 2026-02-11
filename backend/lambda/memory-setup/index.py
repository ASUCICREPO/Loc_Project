"""
AgentCore Memory Setup - CDK Custom Resource Handler
Creates/deletes AgentCore Memory automatically during CDK deployment
"""

import json
import boto3
import urllib3
import os
import time

http = urllib3.PoolManager()


def send_response(event, context, status, data, physical_resource_id=None):
    """Send response to CloudFormation"""
    response_body = {
        "Status": status,
        "Reason": f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": physical_resource_id or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data,
    }
    
    json_body = json.dumps(response_body)
    print(f"Response: {json_body}")
    
    headers = {
        "Content-Type": "",
        "Content-Length": str(len(json_body)),
    }
    
    try:
        response = http.request(
            "PUT",
            event["ResponseURL"],
            body=json_body,
            headers=headers,
        )
        print(f"CloudFormation response status: {response.status}")
    except Exception as e:
        print(f"Error sending response: {e}")


def handler(event, context):
    """Handle CloudFormation Custom Resource events"""
    print(f"Event: {json.dumps(event)}")
    
    request_type = event["RequestType"]
    properties = event.get("ResourceProperties", {})
    memory_name = properties.get("MemoryName", os.environ.get("MEMORY_NAME", "LOC-HistoraMemory"))
    event_expiry_days = int(properties.get("EventExpiryDays", 30))
    
    region = os.environ.get("AWS_REGION", "us-east-1")
    
    try:
        if request_type == "Create":
            memory_id = create_memory(memory_name, event_expiry_days, region)
            send_response(
                event, context, "SUCCESS",
                {"MemoryId": memory_id},
                physical_resource_id=memory_id
            )
            
        elif request_type == "Update":
            # For updates, we keep the existing memory
            old_memory_id = event.get("PhysicalResourceId", "")
            send_response(
                event, context, "SUCCESS",
                {"MemoryId": old_memory_id},
                physical_resource_id=old_memory_id
            )
            
        elif request_type == "Delete":
            memory_id = event.get("PhysicalResourceId", "")
            if memory_id and not memory_id.startswith("LogStream") and not memory_id.startswith("/aws/"):
                delete_memory(memory_id, region)
            send_response(
                event, context, "SUCCESS",
                {"MemoryId": ""},
                physical_resource_id=memory_id
            )
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        send_response(
            event, context, "FAILED",
            {"Error": str(e)},
            physical_resource_id=event.get("PhysicalResourceId", context.log_stream_name)
        )


def get_agentcore_client(region: str):
    """Get the AgentCore control plane client"""
    # Try different client names - the service may be named differently
    client_names = [
        "bedrock-agentcore",
        "bedrockagentcore", 
        "bedrock-agent-core",
    ]
    
    for name in client_names:
        try:
            client = boto3.client(name, region_name=region)
            print(f"Successfully created client: {name}")
            return client
        except Exception as e:
            print(f"Failed to create client '{name}': {e}")
    
    # If none work, raise error
    raise Exception(f"Could not create AgentCore client. Available services: {boto3.Session().get_available_services()}")


def create_memory(memory_name: str, event_expiry_days: int, region: str) -> str:
    """Create AgentCore Memory with conversation strategies"""
    print(f"Creating AgentCore Memory: {memory_name}")
    print(f"Region: {region}")
    
    # For now, since AgentCore Memory API may not be available via boto3,
    # we'll use a placeholder approach and return a generated ID
    # The actual memory will need to be created manually or via SDK
    
    try:
        # Try to use the bedrock-agentcore SDK if available
        from bedrock_agentcore.memory import MemoryClient
        from bedrock_agentcore.memory.constants import StrategyType
        
        print("Using bedrock-agentcore SDK")
        memory_client = MemoryClient(region_name=region)
        
        # Check if memory already exists
        try:
            memories = memory_client.list_memories()
            for memory in memories:
                if memory.get('name') == memory_name or memory_name in memory.get('id', ''):
                    memory_id = memory.get('id')
                    print(f"Memory already exists: {memory_id}")
                    return memory_id
        except Exception as e:
            print(f"Error listing memories: {e}")
        
        # Create new memory
        memory = memory_client.create_memory_and_wait(
            name=memory_name,
            description="Memory for Histora chatbot - Library of Congress",
            strategies=[
                {
                    StrategyType.SUMMARY.value: {
                        "name": "ConversationSummary",
                        "namespaces": ["histora/summaries/{actorId}/{sessionId}"]
                    }
                },
                {
                    StrategyType.USER_PREFERENCE.value: {
                        "name": "UserPreferences",
                        "namespaces": ["histora/preferences/{actorId}"],
                    }
                },
                {
                    StrategyType.SEMANTIC.value: {
                        "name": "HistoricalFacts",
                        "namespaces": ["histora/facts/{actorId}/"],
                    }
                },
            ],
            event_expiry_days=event_expiry_days,
        )
        
        memory_id = memory.get('id')
        print(f"✅ Memory created: {memory_id}")
        return memory_id
        
    except ImportError:
        print("bedrock-agentcore SDK not available, skipping memory creation")
        # Return a placeholder - memory will need to be created manually
        placeholder_id = f"{memory_name}-placeholder"
        print(f"Returning placeholder ID: {placeholder_id}")
        return placeholder_id
        
    except Exception as e:
        print(f"Error creating memory: {e}")
        import traceback
        traceback.print_exc()
        raise


def delete_memory(memory_id: str, region: str):
    """Delete AgentCore Memory"""
    print(f"Deleting AgentCore Memory: {memory_id}")
    
    # Skip placeholder IDs
    if "placeholder" in memory_id:
        print("Skipping placeholder memory deletion")
        return
    
    try:
        from bedrock_agentcore.memory import MemoryClient
        
        memory_client = MemoryClient(region_name=region)
        memory_client.delete_memory_and_wait(memory_id=memory_id)
        print(f"✅ Memory deleted: {memory_id}")
        
    except ImportError:
        print("bedrock-agentcore SDK not available, skipping memory deletion")
    except Exception as e:
        print(f"Error deleting memory (continuing anyway): {e}")
        # Don't raise - allow stack deletion to continue
