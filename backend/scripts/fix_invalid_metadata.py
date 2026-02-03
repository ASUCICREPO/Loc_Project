#!/usr/bin/env python3
"""
Fix invalid metadata in existing .metadata.json files
Removes empty strings and None values that cause Knowledge Base ingestion errors
"""

import boto3
import json
import os

s3 = boto3.client('s3')

# Get bucket name from environment or use default
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'test-data-541064517181-us-east-1')

def clean_metadata_attributes(attrs):
    """
    Remove invalid metadata attributes:
    - Empty strings
    - None values
    - 'Unknown' values
    
    Knowledge Base only accepts: strings, numbers, or booleans with actual values
    """
    cleaned = {}
    
    for key, value in attrs.items():
        # Skip if value is None
        if value is None:
            continue
        
        # Skip if value is empty string
        if isinstance(value, str) and value.strip() == '':
            continue
        
        # Skip if value is 'Unknown'
        if isinstance(value, str) and value == 'Unknown':
            continue
        
        # Keep the value
        cleaned[key] = value
    
    return cleaned

def fix_metadata_file(metadata_key):
    """Fix a single metadata file"""
    try:
        # Download existing metadata
        response = s3.get_object(Bucket=BUCKET_NAME, Key=metadata_key)
        metadata_json = json.loads(response['Body'].read())
        
        # Clean the attributes
        original_attrs = metadata_json.get('metadataAttributes', {})
        cleaned_attrs = clean_metadata_attributes(original_attrs)
        
        # Check if anything changed
        if original_attrs == cleaned_attrs:
            return 'unchanged'
        
        # Update metadata
        metadata_json['metadataAttributes'] = cleaned_attrs
        
        # Upload fixed metadata
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=metadata_key,
            Body=json.dumps(metadata_json, indent=2),
            ContentType='application/json'
        )
        
        return 'fixed'
        
    except Exception as e:
        print(f"✗ Error fixing {metadata_key}: {e}")
        return 'error'

def fix_all_metadata_files():
    """Fix all metadata files in S3"""
    print(f"Scanning S3 bucket: {BUCKET_NAME}")
    print(f"Looking for .metadata.json files to fix...\n")
    
    # List all metadata files
    paginator = s3.get_paginator('list_objects_v2')
    
    # Check both bills and newspapers
    prefixes = ['bills/', 'newspapers/']
    
    fixed = 0
    unchanged = 0
    errors = 0
    total = 0
    
    for prefix in prefixes:
        print(f"\nProcessing {prefix}...")
        
        pages = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix=prefix
        )
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Only process .metadata.json files
                if not key.endswith('.metadata.json'):
                    continue
                
                total += 1
                result = fix_metadata_file(key)
                
                if result == 'fixed':
                    fixed += 1
                    if fixed <= 10:  # Log first 10 fixes
                        print(f"  ✓ Fixed: {key}")
                elif result == 'unchanged':
                    unchanged += 1
                elif result == 'error':
                    errors += 1
                
                # Progress update every 100 files
                if total % 100 == 0:
                    print(f"  Progress: {total} files processed (Fixed: {fixed}, Unchanged: {unchanged}, Errors: {errors})")
    
    print(f"\n{'='*60}")
    print(f"Metadata Fix Complete!")
    print(f"{'='*60}")
    print(f"Total files processed: {total}")
    print(f"Fixed: {fixed}")
    print(f"Unchanged: {unchanged}")
    print(f"Errors: {errors}")
    print(f"{'='*60}\n")
    
    if fixed > 0:
        print("⚠️  IMPORTANT: Re-ingest the fixed files for changes to take effect!")
        print("   Run: python direct_ingestion.py")

if __name__ == '__main__':
    fix_all_metadata_files()
