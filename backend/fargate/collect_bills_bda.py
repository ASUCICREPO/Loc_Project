#!/usr/bin/env python3
"""
Fargate Task: Congress Bills Collector with Bedrock Data Automation
Fetches bills from Congress API and saves raw files to S3 for Bedrock Data Automation parsing
No Textract needed - Bedrock handles PDF/XML/HTML parsing automatically
"""

import os
import sys
import json
import time
import boto3
import requests
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urlparse

# Configuration
CONGRESS_API_KEY = os.environ.get('CONGRESS_API_KEY', 'MThtRT5WkFu8I8CHOfiLLebG4nsnKcX3JnNv2N8A')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
USE_BEDROCK_PARSING = os.environ.get('USE_BEDROCK_PARSING', 'true').lower() == 'true'
BILLS_PREFIX = os.environ.get('BILLS_PREFIX', 'bills/')

# Congress configuration
START_CONGRESS = int(os.environ.get('START_CONGRESS', '1'))
END_CONGRESS = int(os.environ.get('END_CONGRESS', '16'))
BILL_TYPES = os.environ.get('BILL_TYPES', 'hr,s,hjres,sjres,hconres,sconres,hres,sres').split(',')

# AWS clients
s3 = boto3.client('s3')

class BillsCollector:
    def __init__(self):
        self.total_bills = 0
        self.successful = 0
        self.failed = 0
        self.errors = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congress-Bills-Collector/1.0',
            'X-API-Key': CONGRESS_API_KEY
        })
    
    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def get_congress_bills(self, congress: int, bill_type: str, limit: int = 250) -> List[Dict]:
        """Fetch bills from Congress API"""
        bills = []
        offset = 0
        
        while True:
            url = f"https://api.congress.gov/v3/bill/{congress}/{bill_type}"
            params = {
                'api_key': CONGRESS_API_KEY,
                'format': 'json',
                'limit': limit,
                'offset': offset
            }
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                batch_bills = data.get('bills', [])
                if not batch_bills:
                    break
                
                bills.extend(batch_bills)
                self.log(f"Fetched {len(batch_bills)} {bill_type.upper()} bills from Congress {congress} (offset {offset})")
                
                # Check if we have more pages
                if len(batch_bills) < limit:
                    break
                
                offset += limit
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                self.log(f"Error fetching bills for Congress {congress}, type {bill_type}: {e}")
                break
        
        return bills
    
    def download_bill_text(self, bill: Dict) -> tuple:
        """Download bill text in the best available format (PDF, XML, HTML, TXT)"""
        bill_number = bill.get('number', 'unknown')
        bill_type = bill.get('type', 'unknown')
        congress = bill.get('congress', 'unknown')
        bill_id = f"{congress}-{bill_type}-{bill_number}"
        
        # Get text versions URL from bill
        text_versions_info = bill.get('textVersions')
        if not text_versions_info:
            return None, None, "No textVersions field in bill data"
        
        text_versions_url = text_versions_info.get('url')
        if not text_versions_url:
            return None, None, "No textVersions URL"
        
        try:
            # Fetch all available text versions
            self.log(f"Fetching text versions from: {text_versions_url}")
            response = self.session.get(f"{text_versions_url}?api_key={CONGRESS_API_KEY}", timeout=30)
            response.raise_for_status()
            versions_data = response.json()
            
            text_versions_list = versions_data.get('textVersions', [])
            if not text_versions_list:
                return None, None, "No text versions available in API response"
            
            # Try each version until we find one with downloadable content
            for version in text_versions_list:
                formats = version.get('formats', [])
                if not formats:
                    continue
                
                # Try formats in order of preference: PDF, XML, HTML, TXT
                preferred_formats = ['pdf', 'xml', 'html', 'txt']
                
                for preferred_fmt in preferred_formats:
                    for format_info in formats:
                        format_type = format_info.get('type', '').lower()
                        
                        if format_type == preferred_fmt:
                            download_url = format_info.get('url')
                            if not download_url:
                                continue
                            
                            try:
                                # Download the file
                                self.log(f"Downloading {preferred_fmt.upper()} from: {download_url}")
                                file_response = self.session.get(download_url, timeout=60)
                                file_response.raise_for_status()
                                
                                # Verify we got content
                                if len(file_response.content) == 0:
                                    self.log(f"Empty content for {bill_id} in {preferred_fmt}")
                                    continue
                                
                                # Generate filename
                                filename = f"{congress}_{bill_type}_{bill_number}.{preferred_fmt}"
                                
                                self.log(f"✓ Successfully downloaded {bill_id} as {preferred_fmt.upper()} ({len(file_response.content)} bytes)")
                                return file_response.content, filename, None
                                
                            except Exception as e:
                                self.log(f"Failed to download {preferred_fmt} for {bill_id}: {e}")
                                continue
            
            return None, None, "No downloadable formats found in any version"
            
        except Exception as e:
            return None, None, f"API error: {e}"
    
    def save_bill_to_s3(self, content: bytes, filename: str, bill_metadata: Dict) -> bool:
        """Save bill content to S3 with metadata"""
        try:
            s3_key = f"{BILLS_PREFIX}{filename}"
            
            # Add metadata for Bedrock Data Automation
            metadata = {
                'bill-number': str(bill_metadata.get('number', '')),
                'bill-type': str(bill_metadata.get('type', '')),
                'congress': str(bill_metadata.get('congress', '')),
                'title': str(bill_metadata.get('title', ''))[:1000],  # Limit length
                'introduced-date': str(bill_metadata.get('introducedDate', '')),
                'content-type': filename.split('.')[-1].upper()
            }
            
            # Clean metadata (S3 metadata keys must be valid)
            clean_metadata = {}
            for key, value in metadata.items():
                if value and value != 'None':
                    # Replace invalid characters
                    clean_key = key.replace('-', '_').replace(' ', '_')
                    clean_value = str(value).replace('\n', ' ').replace('\r', ' ')[:1000]
                    clean_metadata[clean_key] = clean_value
            
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=content,
                Metadata=clean_metadata,
                ContentType=self.get_content_type(filename)
            )
            
            self.log(f"Saved {filename} to S3: s3://{BUCKET_NAME}/{s3_key}")
            return True
            
        except Exception as e:
            self.log(f"Error saving {filename} to S3: {e}")
            return False
    
    def get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        ext = filename.split('.')[-1].lower()
        content_types = {
            'pdf': 'application/pdf',
            'xml': 'application/xml',
            'html': 'text/html',
            'txt': 'text/plain'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def process_congress_bills(self):
        """Process all bills from specified Congress sessions"""
        self.log(f"Starting Congress bills collection...")
        self.log(f"Congress range: {START_CONGRESS}-{END_CONGRESS}")
        self.log(f"Bill types: {', '.join(BILL_TYPES)}")
        self.log(f"Target bucket: s3://{BUCKET_NAME}/{BILLS_PREFIX}")
        
        for congress in range(START_CONGRESS, END_CONGRESS + 1):
            self.log(f"\n=== Processing Congress {congress} ===")
            
            for bill_type in BILL_TYPES:
                self.log(f"Fetching {bill_type.upper()} bills from Congress {congress}...")
                
                bills = self.get_congress_bills(congress, bill_type)
                self.log(f"Found {len(bills)} {bill_type.upper()} bills")
                
                for i, bill in enumerate(bills, 1):
                    self.total_bills += 1
                    bill_id = f"{congress}-{bill_type}-{bill.get('number', 'unknown')}"
                    
                    self.log(f"Processing bill {i}/{len(bills)}: {bill_id}")
                    
                    # Download bill content
                    content, filename, error = self.download_bill_text(bill)
                    
                    if error:
                        self.log(f"Failed to download {bill_id}: {error}")
                        self.failed += 1
                        self.errors.append(f"{bill_id}: {error}")
                        continue
                    
                    # Save to S3
                    if self.save_bill_to_s3(content, filename, bill):
                        self.successful += 1
                        self.log(f"✓ Successfully processed {bill_id}")
                    else:
                        self.failed += 1
                        self.errors.append(f"{bill_id}: S3 upload failed")
                    
                    # Rate limiting
                    time.sleep(0.2)
                
                self.log(f"Completed {bill_type.upper()} bills for Congress {congress}")
        
        self.log(f"\n=== Collection Summary ===")
        self.log(f"Total bills processed: {self.total_bills}")
        self.log(f"Successful: {self.successful}")
        self.log(f"Failed: {self.failed}")
        
        if self.errors:
            self.log(f"\nErrors encountered:")
            for error in self.errors[:10]:  # Show first 10 errors
                self.log(f"  - {error}")
            if len(self.errors) > 10:
                self.log(f"  ... and {len(self.errors) - 10} more errors")

def main():
    """Main execution function"""
    if not BUCKET_NAME:
        print("ERROR: BUCKET_NAME environment variable not set")
        sys.exit(1)
    
    collector = BillsCollector()
    
    try:
        collector.log("=== Congress Bills Collector with Bedrock Data Automation ===")
        collector.log(f"Bucket: {BUCKET_NAME}")
        collector.log(f"Bills prefix: {BILLS_PREFIX}")
        collector.log(f"Bedrock parsing: {USE_BEDROCK_PARSING}")
        
        collector.process_congress_bills()
        
        # Success metrics
        success_rate = (collector.successful / collector.total_bills * 100) if collector.total_bills > 0 else 0
        collector.log(f"\n=== Final Results ===")
        collector.log(f"Success rate: {success_rate:.1f}%")
        collector.log(f"Ready for Bedrock Data Automation processing")
        
        if collector.failed > 0:
            collector.log(f"Note: {collector.failed} bills failed to process")
            sys.exit(1)
        
    except KeyboardInterrupt:
        collector.log("Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        collector.log(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()