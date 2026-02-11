#!/usr/bin/env python3
"""
Simple script to create AgentCore Memory
Runs automatically before CDK deployment via npm predeploy hook
"""

import boto3
import json
import os
from pathlib import Path

# Get region
region = boto3.session.Session().region_name
print(f"Region: {region}")

try:
    from bedrock_agentcore.memory import MemoryClient
    from bedrock_agentcore.memory.constants import StrategyType
except ImportError:
    print("⚠️  bedrock-agentcore not installed")
    print("Installing bedrock-agentcore...")
    import subprocess
    subprocess.check_call(["pip", "install", "bedrock-agentcore", "-q"])
    from bedrock_agentcore.memory import MemoryClient
    from bedrock_agentcore.memory.constants import StrategyType

memory_client = MemoryClient(region_name=region)
memory_name = "CongressMemory"  # Must match pattern: [a-zA-Z][a-zA-Z0-9_]{0,47}

# File to store memory ID
memory_config_file = Path(__file__).parent.parent / "cdk.context.json"

print(f"Creating AgentCore Memory: {memory_name}")

try:
    # Check if memory already exists
    print("Checking for existing memory...")
    memories = memory_client.list_memories()
    existing_memory = None
    
    for m in memories:
        if memory_name in m.get('id', '') or m.get('name') == memory_name:
            existing_memory = m.get('id')
            print(f"✅ Found existing memory: {existing_memory}")
            break
    
    if not existing_memory:
        print("Creating new memory (takes ~3 minutes)...")
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
            event_expiry_days=30,
        )
        
        memory_id = memory.get('id')
        print(f"✅ Memory created: {memory_id}")
    else:
        memory_id = existing_memory
    
    # Save memory ID to cdk.context.json
    context = {}
    if memory_config_file.exists():
        with open(memory_config_file, 'r') as f:
            context = json.load(f)
    
    context['agentcore-memory-id'] = memory_id
    
    with open(memory_config_file, 'w') as f:
        json.dump(context, f, indent=2)
    
    print()
    print("=" * 60)
    print("✅ Memory setup complete!")
    print("=" * 60)
    print(f"Memory ID: {memory_id}")
    print(f"Saved to: {memory_config_file}")
    print()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    # Don't fail the build - CDK will deploy without memory
    print()
    print("⚠️  Continuing without memory (Lambda will work but without conversation history)")
    exit(0)  # Exit successfully to allow CDK deploy to continue
