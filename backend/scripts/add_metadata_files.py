#!/usr/bin/env python3
"""
Add .metadata.json files for existing newspaper files in S3
This script creates metadata files that Knowledge Base can read
"""

import boto3
import json
import os
from urllib.parse import unquote

s3 = boto3.client('s3')

# Get bucket name from environment or use default
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'test-data-541064517181-us-east-1')

def extract_metadata_from_filename(filename):
    """
    Extract metadata from newspaper filename
    Format: newspaper_15695_1809-06-13_The Kentucky Gazette.txt
    """
    # Remove .txt extension
    name = filename.replace('.txt', '')
    
    # Split by underscore (max 3 splits to preserve newspaper name with spaces)
    parts = name.split('_', 3)
    
    if len(parts) < 4:
        print(f"  ⚠️  Unexpected filename format: {filename}")
        return None
    
    newspaper_id = parts[1]
    issue_date = parts[2]
    newspaper_title = parts[3]
    
    # Extract year from date
    year = issue_date.split('-')[0] if '-' in issue_date else ''
    
    # Build metadata attributes - only include non-empty values
    metadata_attrs = {
        "entity_type": "newspaper",
        "source": "chronicling_america"
    }
    
    # Add optional fields only if they have values
    if year:
        metadata_attrs["year"] = str(year)
    
    if newspaper_id:
        metadata_attrs["source_url"] = f"https://chroniclingamerica.loc.gov/lccn/{newspaper_id}/"
    
    if newspaper_title:
        metadata_attrs["newspaper_title"] = newspaper_title
    
    if issue_date:
        metadata_attrs["issue_date"] = issue_date
    
    # Don't include place_of_publication or edition_notes if empty
    # (we don't have this info from filenames)
    
    return metadata_attrs

def add_metadata_files():
    """Add .metadata.json files for all newspaper .txt files"""
    print(f"Scanning S3 bucket: {BUCKET_NAME}")
    print(f"Looking for newspaper files without metadata...\n")
    
    # List all newspaper .txt files
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(
        Bucket=BUCKET_NAME,
        Prefix='newspapers/'
    )
    
    txt_files = []
    metadata_files = set()
    
    # First pass: collect all files
    for page in pages:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.txt'):
                txt_files.append(key)
            elif key.endswith('.metadata.json'):
                # Track which txt files already have metadata
                txt_key = key.replace('.metadata.json', '')
                metadata_files.add(txt_key)
    
    print(f"Found {len(txt_files)} newspaper .txt files")
    print(f"Found {len(metadata_files)} existing .metadata.json files")
    
    # Find files that need metadata
    files_needing_metadata = [f for f in txt_files if f not in metadata_files]
    
    print(f"\n{len(files_needing_metadata)} files need metadata files\n")
    
    if len(files_needing_metadata) == 0:
        print("✓ All files already have metadata!")
        return
    
    # Create metadata files
    created = 0
    failed = 0
    
    for i, txt_key in enumerate(files_needing_metadata, 1):
        try:
            # Extract filename
            filename = txt_key.split('/')[-1]
            
            # Extract metadata from filename
            metadata_attrs = extract_metadata_from_filename(filename)
            
            if not metadata_attrs:
                failed += 1
                continue
            
            # Create metadata JSON
            metadata_json = {
                "metadataAttributes": metadata_attrs
            }
            
            # Upload metadata file
            metadata_key = f"{txt_key}.metadata.json"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=metadata_key,
                Body=json.dumps(metadata_json, indent=2),
                ContentType='application/json'
            )
            
            created += 1
            
            # Log progress every 100 files
            if i % 100 == 0:
                progress = (i / len(files_needing_metadata)) * 100
                print(f"Progress: {i}/{len(files_needing_metadata)} ({progress:.1f}%) - Created: {created}, Failed: {failed}")
        
        except Exception as e:
            failed += 1
            if failed <= 10:  # Only log first 10 errors
                print(f"✗ Error creating metadata for {txt_key}: {e}")
    
    print(f"\n{'='*60}")
    print(f"Metadata Creation Complete!")
    print(f"{'='*60}")
    print(f"Total files processed: {len(files_needing_metadata)}")
    print(f"Metadata files created: {created}")
    print(f"Failed: {failed}")
    print(f"{'='*60}\n")
    
    if created > 0:
        print("⚠️  IMPORTANT: You need to re-ingest these files for the metadata to be indexed!")
        print("   Run the direct_ingestion.py script to update the Knowledge Base.")

if __name__ == '__main__':
    add_metadata_files()
