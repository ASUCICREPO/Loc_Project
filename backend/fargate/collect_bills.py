#!/usr/bin/env python3
"""
Fargate Task: Multi-Source Data Collector
Fetches data from:
1. Congress API (bills from Congress 1-16) - Uses Textract for PDF extraction
2. Hugging Face Dataset (newspapers 1770-1810) - Uses pre-extracted OCR text
"""

import os
import sys
import json
import time
import boto3
import requests
from datetime import datetime
from typing import List, Dict, Any
from datasets import load_dataset

# Configuration
CONGRESS_API_KEY = os.environ.get('CONGRESS_API_KEY', 'MThtRT5WkFu8I8CHOfiLLebG4nsnKcX3JnNv2N8A')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

# Congress configuration
START_CONGRESS = int(os.environ.get('START_CONGRESS', '1'))
END_CONGRESS = int(os.environ.get('END_CONGRESS', '16'))
BILL_TYPES = os.environ.get('BILL_TYPES', 'hr,s,hjres,sjres,hconres,sconres,hres,sres').split(',')

# Hugging Face Dataset configuration for newspapers
HUGGINGFACE_DATASET = os.environ.get('HUGGINGFACE_DATASET', 'RevolutionCrossroads/loc_chronicling_america_1770-1810')
MAX_NEWSPAPER_PAGES = int(os.environ.get('MAX_NEWSPAPER_PAGES', '0'))  # 0 = process ALL newspapers, or set a limit

# AWS clients
s3 = boto3.client('s3')
textract = boto3.client('textract')

class DataCollector:
    def __init__(self):
        self.total_items = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
        self.congress_stats = {'total': 0, 'successful': 0, 'failed': 0, 'skipped': 0}
        self.newspaper_stats = {'total': 0, 'successful': 0, 'failed': 0, 'skipped': 0}
    
    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def file_exists_in_s3(self, key: str) -> bool:
        """Check if a file already exists in S3"""
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=key)
            return True
        except:
            return False
    
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
        """
        Get bill text from Congress API
        Returns: tuple (text_content, document_url) or (None, None)
        document_url is the actual PDF/XML/TXT URL from the API for citation
        """
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
                return None, None
            elif response.status_code == 404:
                self.log(f"  ⚠️  Bill text not found (404)")
                return None, None
            
            response.raise_for_status()
            data = response.json()
            
            if 'textVersions' not in data or not data['textVersions']:
                self.log(f"  ⚠️  No text versions available")
                return None, None
            
            # Get the first (latest) text version
            text_version = data['textVersions'][0]
            formats = text_version.get('formats', [])
            
            if not formats:
                self.log(f"  ⚠️  No formats available")
                return None, None
            
            # Priority: Plain Text > PDF (with Textract)
            # Save the actual document URL from API for citation
            document_url = None
            pdf_url = None
            
            # Try Plain Text first
            for fmt in formats:
                if fmt.get('type') == 'Plain Text':
                    document_url = fmt.get('url', '')  # Actual text file URL from API
                    try:
                        self.log(f"  Downloading plain text from: {document_url}")
                        response = requests.get(document_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        text = response.text
                        # Verify it's actually text, not HTML
                        if '<html' in text.lower() or '<!doctype' in text.lower():
                            self.log(f"  ⚠️  Plain text is actually HTML, skipping")
                            continue
                        return text, document_url
                    except Exception as e:
                        self.log(f"  ⚠️  Plain text download failed: {e}")
            
            # Try PDF with Textract
            for fmt in formats:
                if fmt.get('type') == 'PDF':
                    pdf_url = fmt.get('url', '')
                    document_url = pdf_url  # Actual PDF URL from API
                    break
            
            if pdf_url and document_url:
                self.log(f"  Using PDF from: {document_url}")
                doc_id = f"congress_{congress_num}_{bill_type}_{bill_number}"
                text_content = self.extract_text_with_textract(pdf_url, doc_id)
                if text_content:
                    return text_content, document_url
            
            self.log(f"  ⚠️  No usable text format found")
            return None, None
            
        except requests.exceptions.HTTPError as e:
            if '500' in str(e):
                self.log(f"  ⚠️  Congress API error (500) - bill may not have text")
            else:
                self.log(f"  ⚠️  HTTP error: {e}")
            return None, None
        except Exception as e:
            self.log(f"  ✗ Error getting bill text: {str(e)}")
            return None, None
    
    def save_bill_to_s3(self, congress_num, bill_type, bill_number, text_content, metadata, document_url):
        """Save extracted bill text to S3 as TXT file with unified metadata schema"""
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
Document URL: {document_url}

BILL TEXT:
{text_content}
"""
            
            content_bytes = header.encode('utf-8')
            size_mb = len(content_bytes) / (1024 * 1024)
            
            # Check file size (KB has 50MB limit)
            if size_mb > 50:
                self.log(f"  ✗ File too large: {size_mb:.2f}MB (KB limit is 50MB)")
                return False
            
            # Extract year with fallback strategy
            # 1. Try introduced_date first
            introduced_date = metadata.get('introducedDate', '')
            year = introduced_date.split('-')[0] if introduced_date else ''
            
            # 2. If no introduced_date, try latest action date
            if not year:
                latest_action = metadata.get('latestAction', {})
                action_date = latest_action.get('actionDate', '')
                year = action_date.split('-')[0] if action_date else ''
            
            # 3. If still no year, calculate from congress number
            # Each congress is 2 years, starting from 1789
            if not year:
                # Congress 1 = 1789-1791, Congress 2 = 1791-1793, etc.
                start_year = 1789 + ((congress_num - 1) * 2)
                year = str(start_year)
                self.log(f"  ℹ️  No date found, using congress start year: {year}")
            
            # UNIFIED METADATA SCHEMA - works for both bills and newspapers
            # Fill bill-specific fields, set newspaper fields to empty string
            latest_action = metadata.get('latestAction', {})
            s3_metadata = {
                # Common fields (always present)
                'entity_type': 'bill',
                'source': 'congress.gov',
                'year': year or '',
                
                # Bill-specific fields
                'congress': str(congress_num),
                'bill_type': bill_type.upper(),
                'bill_number': str(bill_number),
                'bill_id': f"congress_{congress_num}_{bill_type}_{bill_number}",
                'bill_title': (metadata.get('title', '') or '')[:1024],
                'introduced_date': (introduced_date or '')[:100],
                'latest_action_date': (latest_action.get('actionDate', '') or '')[:100],  # ADD THIS
                'bill_url': document_url[:1024],  # Actual PDF/TXT URL from API
                
                # Newspaper-specific fields (empty for bills)
                'newspaper_title': '',
                'issue_date': '',
                'place_of_publication': '',
                'pdf_url': '',
                'edition_notes': '',
            }
            
            # Save to S3 in bills/ folder (for Knowledge Base ingestion)
            key = f"bills/congress_{congress_num}/{bill_type}_{bill_number}.txt"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=content_bytes,
                ContentType='text/plain',
                Metadata=s3_metadata
            )
            
            self.log(f"  ✓ Saved to S3: {key} ({size_mb:.2f}MB)")
            self.log(f"  ✓ Unified metadata: entity_type=bill, year={year}, congress={congress_num}")
            self.log(f"  ✓ Document URL: {document_url}")
            return True
            
        except Exception as e:
            self.log(f"  ✗ Error saving to S3: {str(e)}")
            return False
    
    def save_newspaper_to_s3(self, newspaper_data: Dict[str, Any], batch_num: int, index: int) -> bool:
        """
        Save newspaper OCR text to S3 with unified metadata schema
        Uses same metadata fields as bills for consistent filtering
        
        Args:
            newspaper_data: Row from Hugging Face dataset
            batch_num: Batch number (1-3) for organizing into separate data sources
            index: Index within the batch
        """
        try:
            # Extract data from Hugging Face dataset
            ocr_text = newspaper_data.get('ocr_text', '')
            pdf_url = newspaper_data.get('pdf_url', '')
            newspaper_title = newspaper_data.get('newspaper_title', 'Unknown')
            issue_date = newspaper_data.get('issue_date', 'Unknown')
            place_of_publication = newspaper_data.get('place_of_publication', 'Unknown')
            edition_notes = newspaper_data.get('edition_notes', '')
            
            # Validate required fields
            if not ocr_text or not pdf_url:
                self.log(f"  ✗ Missing required fields (ocr_text or pdf_url)")
                return False
            
            # Check text size
            content_bytes = ocr_text.encode('utf-8')
            size_mb = len(content_bytes) / (1024 * 1024)
            
            if size_mb > 50:
                self.log(f"  ✗ File too large: {size_mb:.2f}MB (KB limit is 50MB)")
                return False
            
            # Extract year from issue_date
            year = issue_date.split('-')[0] if issue_date and issue_date != 'Unknown' else ''
            
            # Create S3 key with batch organization for multiple data sources
            safe_title = newspaper_title.replace('/', '_').replace(':', '_')[:50]
            safe_date = issue_date.replace('/', '-')
            key = f"newspapers/batch-{batch_num}/newspaper_{index}_{safe_date}_{safe_title}.txt"
            
            # UNIFIED METADATA SCHEMA - works for both bills and newspapers
            # Fill newspaper-specific fields, set bill fields to empty string
            s3_metadata = {
                # Common fields (always present)
                'entity_type': 'newspaper',
                'source': 'chroniclingamerica.loc.gov',
                'year': year or '',
                
                # Bill-specific fields (empty for newspapers)
                'congress': '',
                'bill_type': '',
                'bill_number': '',
                'bill_id': '',
                'bill_title': '',
                'introduced_date': '',
                
                # Newspaper-specific fields
                'newspaper_title': newspaper_title[:1024],
                'issue_date': issue_date[:100],
                'place_of_publication': place_of_publication[:256],
                'pdf_url': pdf_url[:1024],
                'edition_notes': edition_notes[:256] if edition_notes else '',
            }
            
            # Upload to S3 with metadata
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=content_bytes,
                ContentType='text/plain',
                Metadata=s3_metadata
            )
            
            self.log(f"  ✓ Saved to S3: {key} ({size_mb:.2f}MB)")
            self.log(f"  ✓ Unified metadata: entity_type=newspaper, year={year}, title={newspaper_title[:40]}")
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
                
                # Check if file already exists in S3
                key = f"bills/congress_{congress_num}/{bill_type}_{bill_number}.txt"
                if self.file_exists_in_s3(key):
                    self.log(f"  ⏭️  Already exists in S3, skipping")
                    self.congress_stats['skipped'] += 1
                    continue
                
                # Get bill text and document URL
                text_content, document_url = self.get_bill_text(congress_num, bill_type, bill_number)
                
                if text_content and document_url:
                    # Save to S3
                    metadata = {
                        'title': bill.get('title', ''),
                        'introducedDate': bill.get('introducedDate', ''),
                        'latestAction': bill.get('latestAction', {})
                    }
                    
                    if self.save_bill_to_s3(congress_num, bill_type, bill_number, text_content, metadata, document_url):
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
    
    def collect_newspapers_from_huggingface(self):
        """
        Collect newspapers from Hugging Face dataset
        Uses pre-extracted OCR text, no API calls or Textract needed
        Automatically splits into batches of 25k for separate data sources
        """
        self.log(f"\n{'='*60}")
        self.log(f"Collecting Newspapers from Hugging Face Dataset")
        self.log(f"Dataset: {HUGGINGFACE_DATASET}")
        self.log(f"{'='*60}")
        
        try:
            # Load dataset from Hugging Face
            self.log(f"Loading dataset from Hugging Face...")
            dataset = load_dataset(HUGGINGFACE_DATASET, split='train')
            total_rows = len(dataset)
            
            self.log(f"✓ Dataset loaded: {total_rows} newspapers available")
            
            # Process ALL newspapers (no limit)
            # If MAX_NEWSPAPER_PAGES is set and > 0, use it as limit, otherwise process all
            if MAX_NEWSPAPER_PAGES > 0:
                rows_to_process = min(total_rows, MAX_NEWSPAPER_PAGES)
                self.log(f"Processing {rows_to_process} newspapers (limited by MAX_NEWSPAPER_PAGES)")
            else:
                rows_to_process = total_rows
                self.log(f"Processing ALL {rows_to_process} newspapers")
            
            # Calculate batch sizes for data sources
            # Each data source can handle max 25,000 pages
            batch_size = 25000
            num_batches = (rows_to_process + batch_size - 1) // batch_size  # Ceiling division
            
            self.log(f"Will create {num_batches} batches (25,000 pages per batch)")
            
            batches = []
            for i in range(num_batches):
                batch_num = i + 1
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, rows_to_process)
                batches.append((batch_num, start_idx, end_idx))
            
            for batch_num, start_idx, end_idx in batches:
                if start_idx >= rows_to_process:
                    break
                
                batch_count = end_idx - start_idx
                self.log(f"\n{'='*60}")
                self.log(f"Processing Batch {batch_num}: {start_idx} to {end_idx} ({batch_count} newspapers)")
                self.log(f"{'='*60}")
                
                for idx in range(start_idx, end_idx):
                    try:
                        newspaper_data = dataset[idx]
                        
                        # Log progress every 100 items
                        if (idx - start_idx) % 100 == 0:
                            progress = ((idx - start_idx + 1) / batch_count) * 100
                            self.log(f"\n[Batch {batch_num}] Progress: {idx - start_idx + 1}/{batch_count} ({progress:.1f}%)")
                        
                        # Extract key info for logging
                        newspaper_title = newspaper_data.get('newspaper_title', 'Unknown')[:60]
                        issue_date = newspaper_data.get('issue_date', 'Unknown')
                        safe_title = newspaper_title.replace('/', '_').replace(':', '_')[:50]
                        safe_date = issue_date.replace('/', '-')
                        
                        self.log(f"\n[{idx + 1}/{rows_to_process}] {newspaper_title} | {issue_date}")
                        
                        self.newspaper_stats['total'] += 1
                        
                        # Check if file already exists in S3
                        key = f"newspapers/batch-{batch_num}/newspaper_{idx}_{safe_date}_{safe_title}.txt"
                        if self.file_exists_in_s3(key):
                            self.log(f"  ⏭️  Already exists in S3, skipping")
                            self.newspaper_stats['skipped'] += 1
                            continue
                        
                        # Save to S3 with metadata
                        if self.save_newspaper_to_s3(newspaper_data, batch_num, idx):
                            self.newspaper_stats['successful'] += 1
                        else:
                            self.newspaper_stats['failed'] += 1
                            self.errors.append(f"Newspaper {idx}: Save failed")
                        
                        # Small delay to avoid overwhelming S3
                        if (idx - start_idx) % 100 == 0:
                            time.sleep(0.5)
                        
                    except Exception as e:
                        self.log(f"  ✗ Error processing newspaper {idx}: {e}")
                        self.newspaper_stats['failed'] += 1
                        self.errors.append(f"Newspaper {idx}: {str(e)}")
                        continue
                
                self.log(f"\n✓ Batch {batch_num} complete: {end_idx - start_idx} newspapers processed")
            
            self.log(f"\n{'='*60}")
            self.log(f"Newspaper collection complete!")
            self.log(f"Total processed: {self.newspaper_stats['successful']} newspapers")
            self.log(f"{'='*60}")
            
        except Exception as e:
            self.log(f"✗ Error loading Hugging Face dataset: {e}")
            self.log(f"Make sure the 'datasets' library is installed: pip install datasets")
            raise
    
    def run(self):
        """Main execution - collect from both sources"""
        self.log("="*60)
        self.log("Multi-Source Data Collector - Starting")
        self.log("="*60)
        self.log(f"Configuration:")
        self.log(f"  S3 Bucket: {BUCKET_NAME}")
        self.log(f"  Congress Range: {START_CONGRESS} to {END_CONGRESS}")
        self.log(f"  Bill Types: {', '.join(BILL_TYPES)}")
        self.log(f"  Hugging Face Dataset: {HUGGINGFACE_DATASET}")
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
        
        # Part 2: Collect Newspapers from Hugging Face
        self.log("\n" + "="*60)
        self.log("PART 2: Collecting Newspapers from Hugging Face Dataset")
        self.log("="*60)
        
        self.collect_newspapers_from_huggingface()
        
        # Summary
        elapsed_time = time.time() - start_time
        
        self.log("\n" + "="*60)
        self.log("Collection Complete!")
        self.log("="*60)
        self.log(f"\nCongress Bills:")
        self.log(f"  Total: {self.congress_stats['total']}")
        self.log(f"  Successful: {self.congress_stats['successful']}")
        self.log(f"  Skipped: {self.congress_stats['skipped']}")
        self.log(f"  Failed: {self.congress_stats['failed']}")
        
        self.log(f"\nNewspapers:")
        self.log(f"  Total: {self.newspaper_stats['total']}")
        self.log(f"  Successful: {self.newspaper_stats['successful']}")
        self.log(f"  Skipped: {self.newspaper_stats['skipped']}")
        self.log(f"  Failed: {self.newspaper_stats['failed']}")
        
        total_items = self.congress_stats['total'] + self.newspaper_stats['total']
        total_successful = self.congress_stats['successful'] + self.newspaper_stats['successful']
        total_skipped = self.congress_stats['skipped'] + self.newspaper_stats['skipped']
        total_failed = self.congress_stats['failed'] + self.newspaper_stats['failed']
        
        self.log(f"\nOverall:")
        self.log(f"  Total Items: {total_items}")
        self.log(f"  Successful: {total_successful}")
        self.log(f"  Skipped: {total_skipped}")
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
            'total_skipped': total_skipped,
            'total_failed': total_failed,
            'elapsed_seconds': elapsed_time,
            'config': {
                'congress_range': f"{START_CONGRESS}-{END_CONGRESS}",
                'bill_types': BILL_TYPES,
                'huggingface_dataset': HUGGINGFACE_DATASET,
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
    """
    Trigger Knowledge Base sync for all 4 data sources SEQUENTIALLY
    Waits for each data source to complete before starting the next one
    """
    try:
        # Get KB ID from environment
        kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        
        if not kb_id:
            print("⚠️  KB sync skipped: KNOWLEDGE_BASE_ID not set")
            return
        
        print(f"\n{'='*60}")
        print("Triggering Sequential Knowledge Base Sync")
        print(f"{'='*60}")
        print(f"Knowledge Base ID: {kb_id}")
        
        bedrock_agent = boto3.client('bedrock-agent')
        
        # List all data sources for this Knowledge Base
        print("\nFetching data sources...")
        response = bedrock_agent.list_data_sources(
            knowledgeBaseId=kb_id,
            maxResults=10
        )
        
        data_sources = response.get('dataSourceSummaries', [])
        
        if not data_sources:
            print("⚠️  No data sources found for this Knowledge Base")
            return
        
        print(f"Found {len(data_sources)} data sources")
        print("Will sync sequentially to avoid overload\n")
        
        # Sync each data source sequentially
        for idx, ds in enumerate(data_sources, 1):
            ds_id = ds['dataSourceId']
            ds_name = ds.get('name', 'Unknown')
            
            try:
                print(f"\n{'='*60}")
                print(f"[{idx}/{len(data_sources)}] Syncing: {ds_name}")
                print(f"{'='*60}")
                
                # Start ingestion job
                sync_response = bedrock_agent.start_ingestion_job(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_id
                )
                
                job_id = sync_response['ingestionJob']['ingestionJobId']
                print(f"✓ Ingestion job started: {job_id}")
                
                # Poll for completion
                print("Waiting for ingestion to complete...")
                max_wait = 7200  # 2 hours max per data source
                poll_interval = 30  # Check every 30 seconds
                elapsed = 0
                
                while elapsed < max_wait:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    
                    # Check job status
                    job_response = bedrock_agent.get_ingestion_job(
                        knowledgeBaseId=kb_id,
                        dataSourceId=ds_id,
                        ingestionJobId=job_id
                    )
                    
                    status = job_response['ingestionJob']['status']
                    
                    # Log progress every 5 minutes
                    if elapsed % 300 == 0:
                        minutes = elapsed // 60
                        print(f"  Status: {status} ({minutes} minutes elapsed)")
                    
                    if status == 'COMPLETE':
                        stats = job_response['ingestionJob'].get('statistics', {})
                        docs_scanned = stats.get('numberOfDocumentsScanned', 0)
                        docs_indexed = stats.get('numberOfNewDocumentsIndexed', 0)
                        docs_modified = stats.get('numberOfModifiedDocumentsIndexed', 0)
                        docs_deleted = stats.get('numberOfDocumentsDeleted', 0)
                        docs_failed = stats.get('numberOfDocumentsFailed', 0)
                        
                        print(f"\n✓ Ingestion COMPLETE for {ds_name}")
                        print(f"  Documents scanned: {docs_scanned}")
                        print(f"  Documents indexed: {docs_indexed}")
                        print(f"  Documents modified: {docs_modified}")
                        print(f"  Documents deleted: {docs_deleted}")
                        print(f"  Documents failed: {docs_failed}")
                        print(f"  Time taken: {elapsed // 60} minutes")
                        break
                    
                    elif status == 'FAILED':
                        failure_reasons = job_response['ingestionJob'].get('failureReasons', [])
                        print(f"\n✗ Ingestion FAILED for {ds_name}")
                        print(f"  Failure reasons: {', '.join(failure_reasons)}")
                        break
                
                if elapsed >= max_wait:
                    print(f"\n⚠️  Timeout waiting for {ds_name} (exceeded 2 hours)")
                    print(f"  Job may still be running. Check AWS Console.")
                
            except Exception as e:
                print(f"\n✗ Failed to sync {ds_name}: {e}")
                print(f"  Continuing to next data source...")
                continue
        
        print(f"\n{'='*60}")
        print("All data sources sync complete!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"⚠️  Failed to trigger KB sync: {e}")
        print("You can trigger it manually later from AWS Console")

if __name__ == '__main__':
    if not BUCKET_NAME:
        print("ERROR: BUCKET_NAME environment variable not set")
        sys.exit(1)
    
    collector = DataCollector()
    exit_code = collector.run()
    
    # Trigger KB sync after collection (even if some items failed)
    trigger_kb_sync()
    
    sys.exit(exit_code)
