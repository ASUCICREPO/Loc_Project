#!/usr/bin/env python3
"""
Fargate Task: Multi-Source Data Collector
Fetches data from:
1. Congress API (bills from Congress 1-16)
2. Chronicling America (newspapers 1760-1820)
Uses Bedrock Data Automation for text extraction from PDFs
"""

import os
import sys
import json
import time
import boto3
import requests
from datetime import datetime
from typing import List, Dict, Any

# Configuration
CONGRESS_API_KEY = os.environ.get('CONGRESS_API_KEY', 'MThtRT5WkFu8I8CHOfiLLebG4nsnKcX3JnNv2N8A')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')

# Congress configuration
START_CONGRESS = int(os.environ.get('START_CONGRESS', '1'))
END_CONGRESS = int(os.environ.get('END_CONGRESS', '16'))
BILL_TYPES = os.environ.get('BILL_TYPES', 'hr,s,hjres,sjres,hconres,sconres,hres,sres').split(',')

# Chronicling America configuration
START_YEAR = int(os.environ.get('START_YEAR', '1760'))
END_YEAR = int(os.environ.get('END_YEAR', '1820'))
MAX_NEWSPAPER_PAGES = int(os.environ.get('MAX_NEWSPAPER_PAGES', '1000'))

# AWS clients
s3 = boto3.client('s3')
textract = boto3.client('textract')

class DataCollector:
    def __init__(self):
        self.total_items = 0
        self.successful = 0
        self.failed = 0
        self.errors = []
        self.congress_stats = {'total': 0, 'successful': 0, 'failed': 0}
        self.newspaper_stats = {'total': 0, 'successful': 0, 'failed': 0}
        self.bda_project_arn = None  # Cache project ARN
    
    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def ensure_bda_project_exists(self) -> str:
        """
        Ensure Bedrock Data Automation project exists, create if needed
        Returns project ARN
        """
        # Return cached ARN if available
        if self.bda_project_arn:
            return self.bda_project_arn
        
        # Use provided ARN if available
        if BEDROCK_PROJECT_ARN:
            self.bda_project_arn = BEDROCK_PROJECT_ARN
            self.log(f"Using provided BDA project: {self.bda_project_arn}")
            return self.bda_project_arn
        
        self.log(f"Checking if BDA project '{BEDROCK_PROJECT_NAME}' exists...")
        
        try:
            # Try to list and find existing project
            response = bedrock_da.list_data_automation_projects()
            projects = response.get('projects', [])
            
            for project in projects:
                if project['projectName'] == BEDROCK_PROJECT_NAME:
                    self.bda_project_arn = project['projectArn']
                    self.log(f"✓ Found existing BDA project: {self.bda_project_arn}")
                    return self.bda_project_arn
            
            self.log(f"Project not found, creating new BDA project: {BEDROCK_PROJECT_NAME}")
            
        except Exception as e:
            self.log(f"Error listing projects: {e}")
        
        # Create new project
        try:
            response = bedrock_da.create_data_automation_project(
                projectName=BEDROCK_PROJECT_NAME,
                projectDescription="Historical document data extraction",
                projectStage='LIVE',
                standardOutputConfiguration={
                    'document': {
                        'extraction': {
                            'granularity': {
                                'types': ['DOCUMENT', 'PAGE', 'ELEMENT', 'WORD', 'LINE']
                            },
                            'boundingBox': {
                                'state': 'ENABLED'
                            }
                        },
                        'generativeField': {
                            'state': 'ENABLED'
                        },
                        'outputFormat': {
                            'textFormat': {
                                'types': ['PLAIN_TEXT', 'MARKDOWN', 'HTML', 'CSV']
                            },
                            'additionalFileFormat': {
                                'state': 'ENABLED'
                            }
                        }
                    }
                }
            )
            
            self.bda_project_arn = response['projectArn']
            self.log(f"✓ Created BDA project: {self.bda_project_arn}")
            return self.bda_project_arn
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"✗ Failed to create BDA project: {error_msg}")
            
            # If conflict, project exists but hidden
            if 'ConflictException' in error_msg or 'already exists' in error_msg.lower():
                self.log("⚠️  Project exists but not visible - using fallback")
                # Try one more time to list
                time.sleep(2)
                try:
                    response = bedrock_da.list_data_automation_projects()
                    for project in response.get('projects', []):
                        if project['projectName'] == BEDROCK_PROJECT_NAME:
                            self.bda_project_arn = project['projectArn']
                            return self.bda_project_arn
                except:
                    pass
            
            raise RuntimeError(f"Failed to create/find BDA project: {error_msg}")
    
    def extract_text_with_bda(self, pdf_url: str, doc_id: str) -> str:
        """
        Extract text from PDF using Bedrock Data Automation
        Downloads PDF, uploads to S3, processes with BDA, returns text
        """
        try:
            self.log(f"  Downloading PDF from: {pdf_url}")
            
            # Add headers for congress.gov
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(pdf_url, headers=headers, timeout=60)
            response.raise_for_status()
            
            # Upload PDF to S3 temp location
            temp_key = f"temp/pdfs/{doc_id}.pdf"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=temp_key,
                Body=response.content,
                ContentType='application/pdf'
            )
            
            self.log(f"  Uploaded PDF to S3: {temp_key}")
            self.log(f"  Processing with Bedrock Data Automation...")
            
            # Ensure BDA project exists
            project_arn = self.ensure_bda_project_exists()
            
            # Process with BDA
            input_s3_uri = f"s3://{BUCKET_NAME}/{temp_key}"
            output_prefix = f"temp/bda-output/{doc_id}/"
            output_s3_uri = f"s3://{BUCKET_NAME}/{output_prefix}"
            
            # Invoke BDA with correct client and parameters
            response = bedrock_da_runtime.invoke_data_automation_async(
                inputConfiguration={
                    's3Uri': input_s3_uri
                },
                outputConfiguration={
                    's3Uri': output_s3_uri
                },
                dataAutomationConfiguration={
                    'dataAutomationProjectArn': project_arn,
                    'stage': 'LIVE'
                },
                dataAutomationProfileArn=BEDROCK_PROFILE_ARN
            )
            
            invocation_arn = response['invocationArn']
            self.log(f"  BDA invocation started: {invocation_arn}")
            
            # Wait for BDA to complete (poll status)
            max_wait = 300  # 5 minutes
            elapsed = 0
            poll_interval = 15
            
            while elapsed < max_wait:
                status_response = bedrock_da_runtime.get_data_automation_status(
                    invocationArn=invocation_arn
                )
                
                status = status_response['status']
                
                if elapsed % 30 == 0:  # Log every 30 seconds
                    self.log(f"  BDA status: {status} (elapsed: {elapsed}s)")
                
                if status == 'Success':
                    self.log(f"  ✓ BDA processing completed in {elapsed}s")
                    
                    # Get actual output URI from response
                    job_metadata_uri = status_response['outputConfiguration']['s3Uri']
                    
                    # Extract text from BDA output
                    text = self._extract_text_from_bda_output(job_metadata_uri)
                    
                    # Cleanup temp files
                    self._cleanup_s3_prefix(f"temp/pdfs/{doc_id}")
                    self._cleanup_s3_prefix(output_prefix)
                    
                    return text
                    
                elif status in ['ClientError', 'ServiceError']:
                    error_msg = status_response.get('errorMessage', 'Unknown error')
                    self.log(f"  ✗ BDA processing failed: {error_msg}")
                    return None
                
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            self.log(f"  ⚠️  BDA processing timeout after {max_wait}s")
            return None
            
        except Exception as e:
            self.log(f"  ✗ Error with BDA extraction: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_text_from_bda_output(self, job_metadata_uri: str) -> str:
        """Extract text from BDA output JSON"""
        try:
            # Parse S3 URI to get bucket and key
            import re
            match = re.match(r's3://([^/]+)/(.+)', job_metadata_uri)
            if not match:
                self.log(f"  ✗ Invalid S3 URI: {job_metadata_uri}")
                return None
            
            bucket = match.group(1)
            job_metadata_key = match.group(2)
            
            # Read job_metadata.json
            self.log(f"  Reading job metadata from: {job_metadata_key}")
            response = s3.get_object(Bucket=bucket, Key=job_metadata_key)
            job_metadata = json.loads(response['Body'].read().decode('utf-8'))
            
            # Extract the standard_output_path from job_metadata
            # Path: output_metadata[0].segment_metadata[0].standard_output_path
            standard_output_path = (
                job_metadata
                .get('output_metadata', [{}])[0]
                .get('segment_metadata', [{}])[0]
                .get('standard_output_path', '')
            )
            
            if not standard_output_path:
                self.log(f"  ⚠️  No standard_output_path in job_metadata")
                return None
            
            # Parse the standard output path
            match = re.match(r's3://([^/]+)/(.+)', standard_output_path)
            if not match:
                self.log(f"  ✗ Invalid standard output path: {standard_output_path}")
                return None
            
            output_bucket = match.group(1)
            output_key = match.group(2)
            
            # Read the actual output file
            self.log(f"  Reading extracted data from: {output_key}")
            response = s3.get_object(Bucket=output_bucket, Key=output_key)
            output_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Extract text from BDA output structure
            # BDA output has different formats - try multiple paths
            text_parts = []
            
            # Try extractedText field
            if 'extractedText' in output_data:
                return output_data['extractedText']
            
            # Try pages array
            if 'pages' in output_data:
                for page in output_data['pages']:
                    if 'text' in page:
                        text_parts.append(page['text'])
                    elif 'content' in page:
                        text_parts.append(page['content'])
            
            # Try blocks array (Textract-style output)
            if 'blocks' in output_data:
                for block in output_data['blocks']:
                    if block.get('blockType') == 'LINE' and 'text' in block:
                        text_parts.append(block['text'])
            
            # Try document field
            if 'document' in output_data:
                doc = output_data['document']
                if 'text' in doc:
                    return doc['text']
                if 'content' in doc:
                    return doc['content']
            
            if text_parts:
                return '\n'.join(text_parts)
            
            self.log(f"  ⚠️  Could not find text in BDA output")
            self.log(f"  Output keys: {list(output_data.keys())}")
            return None
            
        except Exception as e:
            self.log(f"  ✗ Error extracting BDA output: {e}")
            import traceback
            traceback.print_exc()
            return None
    

    
    def _cleanup_s3_prefix(self, prefix: str):
        """Delete all objects under a prefix"""
        try:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
            for obj in response.get('Contents', []):
                s3.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])
        except Exception as e:
            self.log(f"  Cleanup warning: {e}")
    
    def get_bill_text(self, congress_num, bill_type, bill_number):
        """Get bill text from Congress API"""
        try:
            # Get text versions
            text_url = f"https://api.congress.gov/v3/bill/{congress_num}/{bill_type}/{bill_number}/text"
            params = {'api_key': CONGRESS_API_KEY, 'format': 'json'}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            self.log(f"  Fetching text versions from: {text_url}")
            response = requests.get(text_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'textVersions' not in data or not data['textVersions']:
                self.log(f"  No text versions available")
                return None
            
            # Get the first (latest) text version
            text_version = data['textVersions'][0]
            formats = text_version.get('formats', [])
            
            if not formats:
                self.log(f"  No formats available")
                return None
            
            # Priority: Plain Text > PDF (with BDA)
            text_content = None
            pdf_url = None
            
            # Try Plain Text first
            for fmt in formats:
                if fmt.get('type') == 'Plain Text':
                    try:
                        self.log(f"  Downloading plain text")
                        response = requests.get(fmt['url'], headers=headers, timeout=30)
                        response.raise_for_status()
                        return response.text
                    except Exception as e:
                        self.log(f"  Plain text download failed: {e}")
            
            # Try PDF with BDA
            for fmt in formats:
                if fmt.get('type') == 'PDF':
                    pdf_url = fmt['url']
                    break
            
            if pdf_url:
                doc_id = f"congress_{congress_num}_{bill_type}_{bill_number}"
                text_content = self.extract_text_with_bda(pdf_url, doc_id)
                if text_content:
                    return text_content
            
            return None
            
        except Exception as e:
            self.log(f"  Error getting bill text: {str(e)}")
            return None
    
    def save_bill_to_s3(self, congress_num, bill_type, bill_number, text_content, metadata):
        """Save extracted bill text to S3"""
        try:
            # Create metadata header
            header = f"""# Congress {congress_num} - {bill_type.upper()} {bill_number}
# Title: {metadata.get('title', 'N/A')}
# Introduced: {metadata.get('introducedDate', 'N/A')}
# Latest Action: {metadata.get('latestAction', {}).get('text', 'N/A')}
# Latest Action Date: {metadata.get('latestAction', {}).get('actionDate', 'N/A')}

---

"""
            full_content = header + text_content
            content_bytes = full_content.encode('utf-8')
            size_mb = len(content_bytes) / (1024 * 1024)
            
            # Check file size (KB has 50MB limit)
            if size_mb > 50:
                self.log(f"  ✗ File too large: {size_mb:.2f}MB (KB limit is 50MB)")
                return False
            
            # Save to S3
            key = f"extracted/congress_{congress_num}/{bill_type}_{bill_number}.txt"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=content_bytes,
                ContentType='text/plain',
                Metadata={
                    'source': 'congress.gov',
                    'congress': str(congress_num),
                    'bill_type': bill_type,
                    'bill_number': str(bill_number),
                    'title': metadata.get('title', '')[:1024]
                }
            )
            
            self.log(f"  ✓ Saved to S3: {key} ({size_mb:.2f}MB)")
            return True
            
        except Exception as e:
            self.log(f"  ✗ Error saving to S3: {str(e)}")
            return False
    
    def save_newspaper_to_s3(self, page_id, date, title, text_content):
        """Save extracted newspaper text to S3"""
        try:
            # Create metadata header
            header = f"""# Chronicling America Newspaper
# Page ID: {page_id}
# Title: {title}
# Date: {date}

---

"""
            full_content = header + text_content
            content_bytes = full_content.encode('utf-8')
            size_mb = len(content_bytes) / (1024 * 1024)
            
            if size_mb > 50:
                self.log(f"  ✗ File too large: {size_mb:.2f}MB")
                return False
            
            # Save to S3
            # Extract year from date for organization
            year = date.split('-')[0] if date else 'unknown'
            safe_page_id = page_id.replace('/', '_').replace(':', '_')
            key = f"extracted/newspapers_{year}/{safe_page_id}.txt"
            
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=content_bytes,
                ContentType='text/plain',
                Metadata={
                    'source': 'chroniclingamerica.loc.gov',
                    'page_id': page_id[:1024],
                    'date': date,
                    'title': title[:1024]
                }
            )
            
            self.log(f"  ✓ Saved to S3: {key} ({size_mb:.2f}MB)")
            return True
            
        except Exception as e:
            self.log(f"  ✗ Error saving to S3: {str(e)}")
            return False
    
    def collect_bills_for_congress(self, congress_num, bill_type):
        """Collect all bills for a specific Congress and bill type"""
        self.log(f"\n{'='*60}")
        self.log(f"Processing Congress {congress_num} - {bill_type.upper()} bills")
        self.log(f"{'='*60}")
        
        try:
            # Get list of bills
            bills_url = f"https://api.congress.gov/v3/bill/{congress_num}/{bill_type}"
            params = {'api_key': CONGRESS_API_KEY, 'format': 'json', 'limit': 250}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            self.log(f"Fetching bills from: {bills_url}")
            response = requests.get(bills_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            bills = data.get('bills', [])
            
            if not bills:
                self.log(f"No {bill_type.upper()} bills found in Congress {congress_num}")
                return
            
            self.log(f"Found {len(bills)} {bill_type.upper()} bills")
            
            for idx, bill in enumerate(bills, 1):
                bill_number = bill.get('number')
                bill_title = bill.get('title', 'N/A')[:100]
                
                self.log(f"\n[{idx}/{len(bills)}] Processing {bill_type.upper()} {bill_number}")
                self.log(f"  Title: {bill_title}...")
                
                self.congress_stats['total'] += 1
                
                # Get bill text
                text_content = self.get_bill_text(congress_num, bill_type, bill_number)
                
                if text_content:
                    # Save to S3
                    metadata = {
                        'title': bill.get('title', ''),
                        'introducedDate': bill.get('introducedDate', ''),
                        'latestAction': bill.get('latestAction', {})
                    }
                    
                    if self.save_bill_to_s3(congress_num, bill_type, bill_number, text_content, metadata):
                        self.congress_stats['successful'] += 1
                    else:
                        self.congress_stats['failed'] += 1
                        self.errors.append(f"Congress {congress_num} {bill_type} {bill_number}: Save failed")
                else:
                    self.log(f"  ✗ No text content available")
                    self.congress_stats['failed'] += 1
                    self.errors.append(f"Congress {congress_num} {bill_type} {bill_number}: No text")
                
                # Rate limiting
                time.sleep(0.5)
            
        except Exception as e:
            self.log(f"Error processing Congress {congress_num} {bill_type}: {str(e)}")
            self.errors.append(f"Congress {congress_num} {bill_type}: {str(e)}")
    
    def collect_newspapers(self):
        """Collect newspapers from Chronicling America"""
        self.log(f"\n{'='*60}")
        self.log(f"Collecting Chronicling America Newspapers")
        self.log(f"Years: {START_YEAR} to {END_YEAR}")
        self.log(f"{'='*60}")
        
        base_url = "https://www.loc.gov/collections/chronicling-america/"
        page = 1
        collected = 0
        
        while collected < MAX_NEWSPAPER_PAGES:
            try:
                params = {
                    'dl': 'page',
                    'dates': f"{START_YEAR}/{END_YEAR}",
                    'fo': 'json',
                    'c': 100,
                    'sp': page
                }
                
                self.log(f"\nFetching page {page} from LOC API...")
                response = requests.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    self.log(f"No more results at page {page}")
                    break
                
                self.log(f"Processing {len(results)} newspapers from page {page}")
                
                for item in results:
                    if collected >= MAX_NEWSPAPER_PAGES:
                        break
                    
                    try:
                        page_id = item.get('id', 'Unknown')
                        title = item.get('title', 'Unknown')
                        date = item.get('date', 'Unknown')
                        
                        # Get IIIF image URL and convert to high-res PDF
                        image_url_field = item.get('image_url')
                        iiif_url = None
                        
                        if isinstance(image_url_field, list):
                            for url in image_url_field:
                                if isinstance(url, str) and 'iiif' in url and '.jpg' in url:
                                    iiif_url = url
                                    break
                        elif isinstance(image_url_field, str):
                            if 'iiif' in image_url_field and '.jpg' in image_url_field:
                                iiif_url = image_url_field
                        
                        if not iiif_url:
                            self.log(f"  ✗ No IIIF URL for {page_id}")
                            continue
                        
                        # Convert to high-resolution PDF URL
                        # Replace pct:6.25 with full/full for high quality
                        pdf_url = iiif_url.replace('/pct:6.25/', '/full/')
                        pdf_url = pdf_url.replace('.jpg', '.pdf')
                        # Remove fragment if present
                        pdf_url = pdf_url.split('#')[0]
                        
                        self.log(f"\n[{collected+1}] Processing: {title[:80]}")
                        self.log(f"  Date: {date}")
                        self.log(f"  PDF URL: {pdf_url}")
                        
                        self.newspaper_stats['total'] += 1
                        
                        # Extract text with BDA
                        doc_id = f"newspaper_{page_id.replace('/', '_')}"
                        text_content = self.extract_text_with_bda(pdf_url, doc_id)
                        
                        if text_content:
                            if self.save_newspaper_to_s3(page_id, date, title, text_content):
                                self.newspaper_stats['successful'] += 1
                                collected += 1
                            else:
                                self.newspaper_stats['failed'] += 1
                        else:
                            self.log(f"  ✗ Text extraction failed")
                            self.newspaper_stats['failed'] += 1
                        
                        # Rate limiting
                        time.sleep(1)
                        
                    except Exception as e:
                        self.log(f"  Error processing newspaper: {e}")
                        self.newspaper_stats['failed'] += 1
                        continue
                
                page += 1
                
            except Exception as e:
                self.log(f"Error fetching page {page}: {e}")
                break
        
        self.log(f"\nNewspaper collection complete: {collected} newspapers processed")
    
    def run(self):
        """Main execution - collect from both sources"""
        self.log("="*60)
        self.log("Multi-Source Data Collector - Starting")
        self.log("="*60)
        self.log(f"Configuration:")
        self.log(f"  S3 Bucket: {BUCKET_NAME}")
        self.log(f"  Bedrock Model: {BEDROCK_MODEL_ID}")
        self.log(f"  Congress Range: {START_CONGRESS} to {END_CONGRESS}")
        self.log(f"  Bill Types: {', '.join(BILL_TYPES)}")
        self.log(f"  Newspaper Years: {START_YEAR} to {END_YEAR}")
        self.log(f"  Max Newspapers: {MAX_NEWSPAPER_PAGES}")
        self.log("="*60)
        
        start_time = time.time()
        
        # Part 1: Collect Congress Bills
        self.log("\n" + "="*60)
        self.log("PART 1: Collecting Congress Bills")
        self.log("="*60)
        
        for congress_num in range(START_CONGRESS, END_CONGRESS + 1):
            for bill_type in BILL_TYPES:
                self.collect_bills_for_congress(congress_num, bill_type.strip())
        
        # Part 2: Collect Newspapers
        self.log("\n" + "="*60)
        self.log("PART 2: Collecting Chronicling America Newspapers")
        self.log("="*60)
        
        self.collect_newspapers()
        
        # Summary
        elapsed_time = time.time() - start_time
        
        self.log("\n" + "="*60)
        self.log("Collection Complete!")
        self.log("="*60)
        self.log(f"\nCongress Bills:")
        self.log(f"  Total: {self.congress_stats['total']}")
        self.log(f"  Successful: {self.congress_stats['successful']}")
        self.log(f"  Failed: {self.congress_stats['failed']}")
        
        self.log(f"\nNewspapers:")
        self.log(f"  Total: {self.newspaper_stats['total']}")
        self.log(f"  Successful: {self.newspaper_stats['successful']}")
        self.log(f"  Failed: {self.newspaper_stats['failed']}")
        
        total_items = self.congress_stats['total'] + self.newspaper_stats['total']
        total_successful = self.congress_stats['successful'] + self.newspaper_stats['successful']
        total_failed = self.congress_stats['failed'] + self.newspaper_stats['failed']
        
        self.log(f"\nOverall:")
        self.log(f"  Total Items: {total_items}")
        self.log(f"  Successful: {total_successful}")
        self.log(f"  Failed: {total_failed}")
        self.log(f"  Time Elapsed: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
        
        if self.errors:
            self.log(f"\nErrors ({len(self.errors)}):")
            for error in self.errors[:10]:
                self.log(f"  - {error}")
            if len(self.errors) > 10:
                self.log(f"  ... and {len(self.errors) - 10} more")
        
        # Save summary to S3
        summary = {
            'congress_bills': self.congress_stats,
            'newspapers': self.newspaper_stats,
            'total_items': total_items,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'elapsed_seconds': elapsed_time,
            'config': {
                'congress_range': f"{START_CONGRESS}-{END_CONGRESS}",
                'bill_types': BILL_TYPES,
                'newspaper_years': f"{START_YEAR}-{END_YEAR}",
                'bedrock_model': BEDROCK_MODEL_ID
            },
            'timestamp': datetime.now().isoformat(),
            'errors': self.errors
        }
        
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key='collection_summary.json',
            Body=json.dumps(summary, indent=2),
            ContentType='application/json'
        )
        
        self.log(f"\nSummary saved to s3://{BUCKET_NAME}/collection_summary.json")
        
        return 0 if total_failed == 0 else 1

def trigger_kb_sync():
    """Trigger Knowledge Base sync after collection completes"""
    try:
        # Get KB IDs from environment or use defaults
        kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        ds_id = os.environ.get('DATA_SOURCE_ID')
        
        if not kb_id or not ds_id:
            print("⚠️  KB sync skipped: KNOWLEDGE_BASE_ID or DATA_SOURCE_ID not set")
            return
        
        print(f"\n{'='*60}")
        print("Triggering Knowledge Base Sync")
        print(f"{'='*60}")
        print(f"Knowledge Base ID: {kb_id}")
        print(f"Data Source ID: {ds_id}")
        
        bedrock_agent = boto3.client('bedrock-agent')
        
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id
        )
        
        job_id = response['ingestionJob']['ingestionJobId']
        print(f"✓ Ingestion job started: {job_id}")
        print(f"Entity extraction will complete in 5-10 minutes")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"⚠️  Failed to trigger KB sync: {e}")
        print("You can trigger it manually later")

if __name__ == '__main__':
    if not BUCKET_NAME:
        print("ERROR: BUCKET_NAME environment variable not set")
        sys.exit(1)
    
    collector = DataCollector()
    exit_code = collector.run()
    
    # Trigger KB sync after collection (even if some items failed)
    trigger_kb_sync()
    
    sys.exit(exit_code)
