#!/usr/bin/env python3
"""
Quick verification script for us-west-2 deployment
"""

import boto3
import os

AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
boto3.setup_default_session(region_name=AWS_REGION)

print(f"Checking deployment in region: {AWS_REGION}\n")

# 1. Check CloudFormation stack
print("1. Checking CloudFormation stack...")
cf = boto3.client('cloudformation')
try:
    response = cf.describe_stacks(StackName='LOCstack')
    stack = response['Stacks'][0]
    print(f"   ✅ Stack found: {stack['StackName']}")
    print(f"   Status: {stack['StackStatus']}")
except Exception as e:
    print(f"   ❌ Stack not found: {e}")
    exit(1)

# 2. Get project name from outputs
outputs = {o['OutputKey']: o['OutputValue'] for o in stack.get('Outputs', [])}
data_bucket = outputs.get('DataBucketName')
project_name = data_bucket.split('-data-')[0] if data_bucket else None

if not project_name:
    print("   ❌ Could not determine project name")
    exit(1)

print(f"   Project name: {project_name}")

# 3. Check fargate-trigger Lambda
print("\n2. Checking fargate-trigger Lambda...")
lambda_client = boto3.client('lambda')
try:
    response = lambda_client.get_function_configuration(
        FunctionName=f"{project_name}-fargate-trigger"
    )
    print(f"   ✅ Lambda found: {response['FunctionName']}")
    
    # Check critical env vars
    env_vars = response.get('Environment', {}).get('Variables', {})
    required_vars = ['ECS_CLUSTER_NAME', 'TASK_DEFINITION_ARN', 'SUBNET_IDS', 'SECURITY_GROUP_ID', 'BUCKET_NAME']
    
    print("   Environment variables:")
    for var in required_vars:
        value = env_vars.get(var)
        if value:
            print(f"      ✅ {var}: {value[:50]}...")
        else:
            print(f"      ❌ {var}: NOT SET")
            
except Exception as e:
    print(f"   ❌ Lambda not found: {e}")
    exit(1)

# 4. Check ECS cluster
print("\n3. Checking ECS cluster...")
ecs = boto3.client('ecs')
try:
    cluster_name = env_vars.get('ECS_CLUSTER_NAME')
    response = ecs.describe_clusters(clusters=[cluster_name])
    if response['clusters']:
        cluster = response['clusters'][0]
        print(f"   ✅ Cluster found: {cluster['clusterName']}")
        print(f"   Status: {cluster['status']}")
        print(f"   Running tasks: {cluster.get('runningTasksCount', 0)}")
    else:
        print(f"   ❌ Cluster not found: {cluster_name}")
except Exception as e:
    print(f"   ❌ Error checking cluster: {e}")

# 5. Check S3 bucket
print("\n4. Checking S3 bucket...")
s3 = boto3.client('s3')
try:
    response = s3.head_bucket(Bucket=data_bucket)
    print(f"   ✅ Bucket exists: {data_bucket}")
    
    # Check if extracted/ prefix exists
    try:
        response = s3.list_objects_v2(Bucket=data_bucket, Prefix='extracted/', MaxKeys=1)
        if response.get('KeyCount', 0) > 0:
            print(f"   ✅ Has existing data in extracted/")
        else:
            print(f"   ℹ️  No data in extracted/ yet (expected for new deployment)")
    except:
        pass
        
except Exception as e:
    print(f"   ❌ Bucket not accessible: {e}")

# 6. Check Textract availability
print("\n5. Checking Textract availability...")
textract = boto3.client('textract')
try:
    # Just check if we can call the service
    textract.get_document_analysis(JobId='test-job-id')
except textract.exceptions.InvalidJobIdException:
    print(f"   ✅ Textract is available in {AWS_REGION}")
except Exception as e:
    if 'InvalidJobIdException' in str(e):
        print(f"   ✅ Textract is available in {AWS_REGION}")
    else:
        print(f"   ⚠️  Textract check inconclusive: {e}")

print("\n" + "="*60)
print("✅ Setup verification complete!")
print("="*60)
print("\nYou can now run:")
print(f"  export AWS_REGION={AWS_REGION}")
print("  python3 test_complete_pipeline.py")
