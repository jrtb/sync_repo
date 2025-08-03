#!/usr/bin/env python3
"""
Retry Failed Uploads Script

This script retries uploads that failed during the main sync operation.
It reads the error log and attempts to upload the failed files with
enhanced retry logic and error handling.

Usage:
    python scripts/retry_failed_uploads.py
    python scripts/retry_failed_uploads.py --dry-run
    python scripts/retry_failed_uploads.py --config config/sync-config.json
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ConnectionError, ReadTimeoutError
import threading
import random

try:
    from scripts.logger import SyncLogger
    from scripts.sync import S3Sync
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.logger import SyncLogger
    from scripts.sync import S3Sync

class FailedUploadRetry:
    def __init__(self, config_file=None, dry_run=False, verbose=False, base_dir=None):
        """Initialize retry handler with configuration"""
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_config(config_file)
        self.dry_run = dry_run
        self.verbose = verbose
        self.base_dir = Path(base_dir) if base_dir else self.project_root
        
        # Enhanced retry configuration for failed uploads
        self.max_retries = self.config.get('sync', {}).get('max_retries', 5)  # More retries for failed files
        self.retry_delay_base = self.config.get('sync', {}).get('retry_delay_base', 2)  # Longer base delay
        self.retry_delay_max = self.config.get('sync', {}).get('retry_delay_max', 120)  # Longer max delay
        
        # Initialize structured logger
        self.logger = SyncLogger(operation_name='retry-failed-uploads', config=self.config)
        
        # Initialize S3 sync instance for upload functionality
        self.sync_instance = S3Sync(
            config_file=config_file,
            dry_run=dry_run,
            verbose=verbose
        )
        
        # Retry statistics
        self.stats = {
            'files_retried': 0,
            'files_succeeded': 0,
            'files_failed': 0,
            'bytes_uploaded': 0,
            'retries_attempted': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Thread safety
        self.stats_lock = threading.Lock()
        
    def _load_config(self, config_file):
        """Load configuration from file"""
        if config_file:
            config_path = Path(config_file)
        else:
            config_path = self.project_root / 'config' / 'aws-config.json'
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def _extract_failed_files(self):
        """Extract list of failed files from error log"""
        error_log_path = self.project_root / 'logs' / 's3-sync-errors.log'
        
        if not error_log_path.exists():
            self.logger.warning(f"Error log not found: {error_log_path}")
            return []
        
        failed_files = []
        with open(error_log_path, 'r') as f:
            for line in f:
                if '"message"' in line and 'upload operation for' in line:
                    # Extract file path from error message
                    try:
                        # Find the file path in the error message
                        start_idx = line.find('upload operation for ') + len('upload operation for ')
                        end_idx = line.find(':', start_idx)
                        if end_idx == -1:
                            end_idx = line.find('"', start_idx)
                        
                        if start_idx != -1 and end_idx != -1:
                            file_path = line[start_idx:end_idx].strip()
                            if file_path and file_path not in failed_files:
                                failed_files.append(file_path)
                    except Exception as e:
                        self.logger.warning(f"Could not parse error line: {e}")
                        continue
        
        return failed_files
    
    def _enhanced_retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with enhanced exponential backoff retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (ClientError, ConnectionError, ReadTimeoutError) as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    self.logger.log_error(Exception(f"Max retries ({self.max_retries}) exceeded"), "retry operation")
                    raise last_exception
                
                # Enhanced delay calculation with more aggressive backoff
                delay = min(self.retry_delay_base * (3 ** attempt), self.retry_delay_max)
                jitter = random.uniform(0, 0.2 * delay)  # More jitter for retry operations
                total_delay = delay + jitter
                
                self.logger.log_retry_attempt(
                    operation="retry_upload", 
                    attempt=attempt + 1, 
                    max_retries=self.max_retries, 
                    delay=total_delay, 
                    error=str(e)
                )
                
                with self.stats_lock:
                    self.stats['retries_attempted'] += 1
                
                time.sleep(total_delay)
        
        raise last_exception
    
    def _retry_upload_file(self, file_path):
        """Retry upload for a single file with enhanced error handling"""
        try:
            # Convert relative path to absolute using the base directory
            if file_path.startswith('../'):
                # Handle paths that start with ../ by using the base directory
                relative_path = file_path[3:]  # Remove '../'
                local_file = self.base_dir / relative_path
            else:
                local_file = self.base_dir / file_path
            
            # Check if file exists
            if not local_file.exists():
                self.logger.log_error(Exception(f"File not found: {local_file}"), "file validation")
                return False
            
            # Determine S3 key - should be the relative path without the ../astro/ prefix
            if file_path.startswith('../astro/'):
                # Remove the ../astro/ prefix to get the correct S3 key
                s3_key = file_path[10:]  # Remove '../astro/'
                # Handle spaces in path names for historic data
                if 'historic data/' in s3_key:
                    s3_key = s3_key.replace('historic data/', 'historic%20data/')
            else:
                s3_key = str(local_file)
            
            self.logger.log_info(f"Retrying upload: {local_file} -> {s3_key}")
            
            if self.dry_run:
                self.logger.log_info(f"[DRY RUN] Would retry upload: {local_file}")
                return True
            
            # Use the sync instance's upload method with enhanced retry
            def upload_operation():
                return self.sync_instance._upload_file(local_file, s3_key)
            
            success = self._enhanced_retry_with_backoff(upload_operation)
            
            if success:
                file_size = local_file.stat().st_size
                with self.stats_lock:
                    self.stats['files_succeeded'] += 1
                    self.stats['bytes_uploaded'] += file_size
                
                self.logger.log_info(f"✅ Successfully retried upload: {local_file}")
                return True
            else:
                with self.stats_lock:
                    self.stats['files_failed'] += 1
                
                self.logger.log_error(Exception(f"Failed to retry upload: {local_file}"), f"retry upload for {local_file}")
                return False
                
        except Exception as e:
            with self.stats_lock:
                self.stats['files_failed'] += 1
            
            self.logger.log_error(e, f"retry upload for {file_path}")
            return False
    
    def retry_failed_uploads(self):
        """Main method to retry all failed uploads"""
        self.stats['start_time'] = datetime.now()
        
        # Extract failed files from error log
        failed_files = self._extract_failed_files()
        
        if not failed_files:
            self.logger.log_info("No failed files found in error log")
            return
        
        self.logger.log_info(f"Found {len(failed_files)} failed files to retry")
        
        # Display files to be retried
        if self.verbose:
            for file_path in failed_files:
                self.logger.log_info(f"  - {file_path}")
        
        # Confirm with user if not dry run
        if not self.dry_run:
            response = input(f"\nRetry upload for {len(failed_files)} failed files? (y/N): ")
            if response.lower() != 'y':
                self.logger.log_info("Retry operation cancelled by user")
                return
        
        # Retry each failed file
        for file_path in failed_files:
            with self.stats_lock:
                self.stats['files_retried'] += 1
            
            success = self._retry_upload_file(file_path)
            
            if not success and not self.dry_run:
                self.logger.log_warning(f"Failed to retry: {file_path}")
        
        self.stats['end_time'] = datetime.now()
        self._print_retry_summary()
    
    def _print_retry_summary(self):
        """Print summary of retry operation"""
        duration = self.stats['end_time'] - self.stats['start_time']
        
        print("\n" + "="*50)
        print("🔄 RETRY SUMMARY")
        print("="*50)
        print(f"⏱️  Duration: {duration}")
        print(f"📁 Files retried: {self.stats['files_retried']}")
        print(f"✅ Files succeeded: {self.stats['files_succeeded']}")
        print(f"❌ Files failed: {self.stats['files_failed']}")
        print(f"💾 Bytes uploaded: {self.stats['bytes_uploaded']:,} bytes ({self.stats['bytes_uploaded'] / (1024*1024):.2f} MB)")
        print(f"🔄 Retries attempted: {self.stats['retries_attempted']}")
        
        if self.stats['files_retried'] > 0:
            success_rate = (self.stats['files_succeeded'] / self.stats['files_retried']) * 100
            print(f"📈 Success rate: {success_rate:.1f}%")
        
        if self.stats['files_failed'] > 0:
            print("⚠️  Some files still failed - check logs for details")
        else:
            print("🎉 All retries completed successfully!")
        print("="*50)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Retry failed S3 uploads')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without actually doing it')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--base-dir', help='Base directory for resolving relative paths (default: current directory)')
    
    args = parser.parse_args()
    
    try:
        retry_handler = FailedUploadRetry(
            config_file=args.config,
            dry_run=args.dry_run,
            verbose=args.verbose,
            base_dir=args.base_dir
        )
        
        retry_handler.retry_failed_uploads()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 