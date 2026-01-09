#!/usr/bin/env python3
"""
Fargate Task: Multi-Source Data Collector with Textract
Fetches data from:
1. Congress API (bills from Congress 1-16)
2. Chronicling America (newspapers 1760-1820)
Uses Amazon Textract for text extraction from PDFs and images
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
    
    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def extract_text_with_textract(self, pdf_url: str, doc_id: str) -> str:
        """
        Extract text from PDF or image using Amazon Textract
        Automatically chooses sync or async based on file size
        
        Textract Limitations:
        - Synchronous: Max 5MB, single page, 1 TPS
        - Asynchronous: Max 500MB, up to 3000 pages, 2 TPS
        """
        try:
            self.log(f"  Downloading from: {pdf_url}")
            
            # Download file
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(pdf_url, headers=headers, timeout=60)
            response.raise_for_status()
            
            file_bytes = response.content
            size_mb = len(file_bytes) / (1024 * 1024)
            
            # Check Content-Type header
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type or 'text/plain' in content_type:
                self.log(f"  ⚠️  Server returned {content_type}, not a PDF")
                return None
            
            self.log(f"  File size: {size_mb:.2f}MB")
            
            # Skip very small files (likely corrupted or empty)
            if size_mb < 0.001:  # Less than 1KB
                self.log(f"  ⚠️  File too small, likely empty or corrupted")
                return None
            
            # Check size limits
            if size_mb > 500:
                self.log(f"  ✗ File too large for Textract (max 500MB)")
                return None
            
            # Verify it's actually a PDF by checking magic bytes
            if not self._is_valid_pdf(file_bytes):
                self.log(f"  ⚠️  Not a valid PDF file (might be HTML or corrupted)")
                # Try to detect if it's HTML
                if file_bytes[:15].lower().startswith(b'<!doctype') or file_bytes[:6].lower().startswith(b'<html'):
                    self.log(f"  ⚠️  File is HTML, not PDF")
                return None
            
            # Strategy: Try sync first (faster), fallback to async if needed
            # Sync API: Single-page only, 1 TPS, instant results
            # Async API: Multi-page support, 2 TPS, ~30-60s processing
            
            if size_mb <= 5:
                # Try sync first for speed
                result = self._textract_sync(file_bytes, doc_id)
                if result:
                    return result
                # Sync failed (likely multi-page), try async
                self.log(f"  Retrying with async API for multi-page support...")
                return self._textract_async(file_bytes, doc_id)
            else:
                # Large files, use async directly
                return self._textract_async(file_bytes, doc_id)
            
        except Exception as e:
            self.log(f"  ✗ Error with Textract extraction: {str(e)}")
            return None
    
    def _is_valid_pdf(self, file_bytes: bytes) -> bool:
        """Check if file is a valid PDF by checking magic bytes"""
        if len(file_bytes) < 4:
            return False
        # PDF files start with %PDF
        return file_bytes[:4] == b'%PDF'
    
    def _textract_sync(self, file_bytes: bytes, doc_id: str) -> str:
        """
        Synchronous Textract for files <= 5MB
        Returns None if document is multi-page (needs async)
        """
        try:
            self.log(f"  Using Textract synchronous API...")
            
            # Call Textract
            response = textract.detect_document_text(
                Document={'Bytes': file_bytes}
            )
            
            # Extract text from LINE blocks
            text_parts = []
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text_parts.append(block['Text'])
            
            extracted_text = '\n'.join(text_parts)
            char_count = len(extracted_text)
            
            self.log(f"  ✓ Extracted {char_count} characters (sync)")
            
            # Rate limiting: 1 TPS for sync API
            time.sleep(1)
            
            return extracted_text if char_count > 0 else None
            
        except textract.exceptions.UnsupportedDocumentException as e:
            # This often means multi-page document - return None to trigger async retry
            self.log(f"  ⚠️  Sync API failed (likely multi-page document)")
            return None
        except textract.exceptions.InvalidParameterException as e:
            self.log(f"  ⚠️  Invalid document (corrupted or wrong format)")
            return None
        except Exception as e:
            error_str = str(e)
            if 'UnsupportedDocument' in error_str:
                self.log(f"  ⚠️  Sync API failed (likely multi-page)")
                return None
            elif 'InvalidParameter' in error_str:
                self.log(f"  ⚠️  Invalid document")
                return None
            else:
                self.log(f"  ✗ Textract sync error: {e}")
                return None
    
    def _textract_async(self, file_bytes: bytes, doc_id: str) -> str:
        """Asynchronous Textract for files > 5MB"""
        try:
            self.log(f"  Using Textract asynchronous API...")
            
            # Upload to S3 (required for async)
            temp_key = f"temp/textract/{doc_id}.pdf"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=temp_key,
                Body=file_bytes,
                ContentType='application/pdf'
            )
            
            self.log(f"  Uploaded to S3: {temp_key}")
            
            # Start async text detection job
            response = textract.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': BUCKET_NAME,
                        'Name': temp_key
                    }
                }
            )
            
            job_id = response['JobId']
            self.log(f"  Textract job started: {job_id}")
            
            # Poll for completion
            max_wait = 600  # 10 minutes
            elapsed = 0
            poll_interval = 10
            
            while elapsed < max_wait:
                result = textract.get_document_text_detection(JobId=job_id)
                status = result['JobStatus']
                
                if elapsed % 30 == 0:  # Log every 30 seconds
                    self.log(f"  Textract status: {status} ({elapsed}s)")
                
                if status == 'SUCCEEDED':
                    # Extract text from all pages
                    text_parts = []
                    page_count = 0
                    
                    # Get first batch
                    for block in result.get('Blocks', []):
                        if block['BlockType'] == 'LINE':
                            text_parts.append(block['Text'])
                        elif block['BlockType'] == 'PAGE':
                            page_count += 1
                    
                    # Get remaining pages (pagination)
                    next_token = result.get('NextToken')
                    while next_token:
                        result = textract.get_document_text_detection(
                            JobId=job_id,
                            NextToken=next_token
                        )
                        for block in result.get('Blocks', []):
                            if block['BlockType'] == 'LINE':
                                text_parts.append(block['Text'])
                            elif block['BlockType'] == 'PAGE':
                                page_count += 1
                        next_token = result.get('NextToken')
                    
                    extracted_text = '\n'.join(text_parts)
                    char_count = len(extracted_text)
                    
                    self.log(f"  ✓ Extracted {char_count} characters from {page_count} pages")
                    
                    # Cleanup
                    self._cleanup_s3_file(temp_key)
                    
                    # Rate limiting: 2 TPS for async API
                    time.sleep(0.5)
                    
                    return extracted_text if char_count > 0 else None
                    
                elif status == 'FAILED':
                    self.log(f"  ✗ Textract job failed")
                    status_message = result.get('StatusMessage', 'Unknown error')
                    self.log(f"  Error: {status_message}")
                    self._cleanup_s3_file(temp_key)
                    return None
                
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            self.log(f"  ✗ Textract timeout after {max_wait}s")
            self._cleanup_s3_file(temp_key)
            return None
            
        except Exception as e:
            self.log(f"  ✗ Textract async error: {e}")
            self._cleanup_s3_file(f"temp/textract/{doc_id}.pdf")
            return None
    
    def _cleanup_s3_file(self, key: str):
        """Delete a single S3 object"""
        try:
            s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        except Exception as e:
            self.log(f"  Cleanup warning: {e}")
    
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
            
            # Handle API errors gracefully
            if response.status_code == 500:
                self.log(f"  ⚠️  Congress API returned 500 error (bill may not have text)")
                return None
            elif response.status_code == 404:
                self.log(f"  ⚠️  Bill text not found (404)")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            if 'textVersions' not in data or not data['textVersions']:
                self.log(f"  ⚠️  No text versions available")
                return None
            
            # Get the first (latest) text version
            text_version = data['textVersions'][0]
            formats = text_version.get('formats', [])
            
            if not formats:
                self.log(f"  ⚠️  No formats available")
                return None
            
            # Priority: Plain Text > PDF (with Textract)
            pdf_url = None
            
            # Try Plain Text first
            for fmt in formats:
                if fmt.get('type') == 'Plain Text':
                    try:
                        self.log(f"  Downloading plain text")
                        response = requests.get(fmt['url'], headers=headers, timeout=30)
                        response.raise_for_status()
                        text = response.text
                        # Verify it's actually text, not HTML
                        if '<html' in text.lower() or '<!doctype' in text.lower():
                            self.log(f"  ⚠️  Plain text is actually HTML, skipping")
                            continue
                        return text
                    except Exception as e:
                        self.log(f"  ⚠️  Plain text download failed: {e}")
            
            # Try PDF with Textract
            for fmt in formats:
                if fmt.get('type') == 'PDF':
                    pdf_url = fmt['url']
                    break
            
            if pdf_url:
                doc_id = f"congress_{congress_num}_{bill_type}_{bill_number}"
                text_content = self.extract_text_with_textract(pdf_url, doc_id)
                if text_content:
                    return text_content
            
            self.log(f"  ⚠️  No usable text format found")
            return None
            
        except requests.exceptions.HTTPError as e:
            if '500' in str(e):
                self.log(f"  ⚠️  Congress API error (500) - bill may not have text")
            else:
                self.log(f"  ⚠️  HTTP error: {e}")
            return None
        except Exception as e:
            self.log(f"  ✗ Error getting bill text: {str(e)}")
            return None
    
    def save_bill_to_s3(self, congress_num, bill_type, bill_number, text_content, metadata):
        """Save extracted bill text to S3 as TXT file with metadata for transformation lambda"""
        try:
            # Create structured text document with metadata header
            header = f"""BILL METADATA:
Congress: {congress_num}
Bill Type: {bill_type.upper()}
Bill Number: {bill_number}
Bill ID: congress_{congress_num}_{bill_type}_{bill_number}
Title: {metadata.get('title', 'N/A')}
Introduced Date: {metadata.get('introducedDate', 'N/A')}
Latest Action: {metadata.get('latestAction', {}).get('text', 'N/A')}
Latest Action Date: {metadata.get('latestAction', {}).get('actionDate', 'N/A')}

BILL TEXT:
{text_content}
"""
            
            content_bytes = header.encode('utf-8')
            size_mb = len(content_bytes) / (1024 * 1024)
            
            # Check file size (KB has 50MB limit)
            if size_mb > 50:
                self.log(f"  ✗ File too large: {size_mb:.2f}MB (KB limit is 50MB)")
                return False
            
            # Prepare metadata for transformation lambda
            # These will be available as x-amz-meta-* in the transformation lambda
            latest_action = metadata.get('latestAction', {})
            s3_metadata = {
                # Core identifiers (required by transformation lambda)
                'bill_id': f"congress_{congress_num}_{bill_type}_{bill_number}",
                'congress': str(congress_num),
                'bill_type': bill_type.upper(),
                'bill_number': str(bill_number),
                
                # Additional metadata for enriched responses
                'title': (metadata.get('title', '') or 'N/A')[:1024],  # S3 metadata limit
                'introduced_date': (metadata.get('introducedDate', '') or 'N/A')[:100],
                'latest_action': (latest_action.get('text', '') or 'N/A')[:1024],
                'latest_action_date': (latest_action.get('actionDate', '') or 'N/A')[:100],
                
                # Source information
                'source': 'congress.gov',
                'entity_type': 'bill',
            }
            
            # Save to S3 as TXT file with metadata for transformation lambda
            key = f"extracted/congress_{congress_num}/{bill_type}_{bill_number}.txt"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=content_bytes,
                ContentType='text/plain',
                Metadata=s3_metadata
            )
            
            self.log(f"  ✓ Saved to S3: {key} ({size_mb:.2f}MB)")
            self.log(f"  ✓ Added metadata for transformation lambda: bill_id={s3_metadata['bill_id']}")
            return True
            
        except Exception as e:
            self.log(f"  ✗ Error saving to S3: {str(e)}")
            return False
    
    def save_newspaper_to_s3(self, page_id, date, title, text_content):
        """Save extracted newspaper text to S3"""
        try:
            # Create metadata header
            header = f"""# Library of Congress Newspaper
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
                        pdf_url = iiif_url.replace('/pct:6.25/', '/full/')
                        pdf_url = pdf_url.replace('.jpg', '.pdf')
                        pdf_url = pdf_url.split('#')[0]
                        
                        self.log(f"\n[{collected+1}] Processing: {title[:80]}")
                        self.log(f"  Date: {date}")
                        self.log(f"  PDF URL: {pdf_url}")
                        
                        self.newspaper_stats['total'] += 1
                        
                        # Extract text with Textract
                        doc_id = f"newspaper_{page_id.replace('/', '_')}"
                        text_content = self.extract_text_with_textract(pdf_url, doc_id)
                        
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
