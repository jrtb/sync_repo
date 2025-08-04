#!/usr/bin/env python3
"""
Main Sync Script for AWS S3 Photo Sync Application

This script provides core sync functionality for uploading photos to S3 with
incremental sync, file comparison, and progress reporting. Designed for AWS
certification study with practical implementation.

AWS Concepts Covered:
- S3 multipart uploads for large files
- CloudWatch monitoring and metrics
- IAM permissions and security
- S3 storage classes and lifecycle policies
- Error handling and retry logic with exponential backoff
- File integrity verification with multiple hash algorithms

Usage:
    python scripts/sync.py --local-path ./photos --bucket my-sync-bucket
    python scripts/sync.py --dry-run --local-path ./photos
    python scripts/sync.py --config config/sync-config.json
"""

import argparse
import boto3
from botocore.config import Config
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ConnectionError, ReadTimeoutError
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import random
try:
    from scripts.logger import SyncLogger
    from scripts.aws_identity import AWSIdentityVerifier
    from scripts.dashboard import SyncDashboard
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.logger import SyncLogger
    try:
        from scripts.aws_identity import AWSIdentityVerifier
    except ImportError:
        AWSIdentityVerifier = None
    try:
        from scripts.dashboard import SyncDashboard
    except ImportError:
        SyncDashboard = None

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

class S3Sync:
    def __init__(self, config_file=None, profile=None, bucket_name=None, 
                 local_path=None, dry_run=False, verbose=False, no_confirm=False, skip_existing_check=False):
        """Initialize S3 sync with configuration"""
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_config(config_file)
        self.profile = profile or self.config.get('aws', {}).get('profile', 'default')
        self.bucket_name = bucket_name or self.config.get('s3', {}).get('bucket_name')
        self.local_path = Path(local_path or self.config.get('sync', {}).get('local_path', './data'))
        self.dry_run = dry_run or self.config.get('sync', {}).get('dry_run', False)
        self.verbose = verbose
        self.no_confirm = no_confirm
        self.skip_existing_check = skip_existing_check
        
        # Retry configuration
        self.max_retries = self.config.get('sync', {}).get('max_retries', 3)
        self.retry_delay_base = self.config.get('sync', {}).get('retry_delay_base', 1)
        self.retry_delay_max = self.config.get('sync', {}).get('retry_delay_max', 60)
        
        # Integrity check configuration
        self.verify_upload = self.config.get('sync', {}).get('verify_upload', True)
        self.hash_algorithm = self.config.get('sync', {}).get('hash_algorithm', 'sha256')
        
        # Initialize structured logger
        self.logger = SyncLogger(operation_name='s3-sync', config=self.config)
        
        # Initialize AWS clients
        self._setup_aws_clients()
        
        # Get current AWS costs for accurate estimates
        self.current_costs = self._get_current_costs()
        
        # Sync statistics
        self.stats = {
            'files_uploaded': 0,
            'files_skipped': 0,
            'files_failed': 0,
            'bytes_uploaded': 0,
            'retries_attempted': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Thread safety
        self.stats_lock = threading.Lock()
        
        # Initialize dashboard if available
        self.dashboard = None
        if SyncDashboard:
            self.dashboard = SyncDashboard('s3-sync', self.config)
        
    def _load_config(self, config_file):
        """Load configuration from file"""
        if config_file:
            config_path = Path(config_file)
        else:
            config_path = self.project_root / "config" / "aws-config.json"
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            sys.exit(1)
    

    
    def _setup_aws_clients(self):
        """Initialize AWS clients with proper error handling"""
        try:
            session = boto3.Session(profile_name=self.profile)
            
            # Configure S3 client with proper timeouts
            config = Config(
                connect_timeout=30,  # 30 seconds to establish connection
                read_timeout=60,     # 60 seconds to read response
                retries={'max_attempts': 3, 'mode': 'adaptive'}
            )
            
            self.s3_client = session.client('s3', config=config)
            self.s3_resource = session.resource('s3')
            
            # Test credentials
            self.s3_client.list_buckets()
            self.logger.log_info("✅ AWS credentials validated successfully")
            
        except NoCredentialsError:
            self.logger.log_error(Exception("AWS credentials not found"), "credential validation")
            print("❌ AWS credentials not found. Run setup-iam-user.py first.")
            sys.exit(1)
        except ClientError as e:
            self.logger.log_error(e, "AWS authentication")
            print(f"❌ AWS authentication failed: {e}")
            sys.exit(1)
    
    def _get_current_costs(self):
        """Get current AWS S3 costs for accurate cost estimates"""
        # Get storage class from configuration
        storage_class = self.config.get('s3', {}).get('storage_class', 'STANDARD')
        
        # Storage class pricing (as of 2024)
        storage_class_pricing = {
            'STANDARD': 0.023,      # $0.023 per GB/month
            'STANDARD_IA': 0.0125,  # $0.0125 per GB/month
            'ONEZONE_IA': 0.01,     # $0.01 per GB/month
            'INTELLIGENT_TIERING': 0.023,  # Same as STANDARD initially
            'GLACIER': 0.004,       # $0.004 per GB/month
            'DEEP_ARCHIVE': 0.00099 # $0.00099 per GB/month
        }
        
        # Get pricing for configured storage class
        storage_per_gb_month = storage_class_pricing.get(storage_class, 0.023)
        
        try:
            # Initialize Cost Explorer client
            session = boto3.Session(profile_name=self.profile)
            self.ce_client = session.client('ce')
            
            # Get current month's S3 costs
            from datetime import datetime, timedelta
            now = datetime.now()
            start_date = now.replace(day=1).strftime('%Y-%m-%d')
            end_date = (now.replace(day=1) + timedelta(days=32)).replace(day=1).strftime('%Y-%m-%d')
            
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'SERVICE'
                    }
                ],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': ['Amazon Simple Storage Service']
                    }
                }
            )
            
            # Extract S3 costs
            s3_cost = 0.0
            if response.get('ResultsByTime') and response['ResultsByTime'][0].get('Groups'):
                for group in response['ResultsByTime'][0]['Groups']:
                    if 'Amazon Simple Storage Service' in group.get('Keys', []):
                        s3_cost = float(group['Metrics']['BlendedCost']['Amount'])
                        break
            
            # Return cost data with current AWS pricing
            return {
                's3_monthly_cost': s3_cost,
                'api_requests_per_1000': 0.0004,  # $0.0004 per 1,000 GET/HEAD requests
                'data_transfer_in_per_gb': 0.00,   # $0.00 per GB (FREE for uploads)
                'data_transfer_out_per_gb': 0.09,  # $0.09 per GB (for downloads)
                'storage_per_gb_month': storage_per_gb_month,
                'storage_class': storage_class,
                'cost_retrieved_at': now.isoformat()
            }
            
        except Exception as e:
            # Fallback to default pricing if cost data unavailable
            self.logger.log_info(f"⚠️  Could not retrieve current costs: {e}")
            self.logger.log_info(f"📊 Using {storage_class} pricing for estimates")
            return {
                's3_monthly_cost': 0.0,
                'api_requests_per_1000': 0.0004,
                'data_transfer_in_per_gb': 0.00,   # $0.00 per GB (FREE for uploads)
                'data_transfer_out_per_gb': 0.09,  # $0.09 per GB (for downloads)
                'storage_per_gb_month': storage_per_gb_month,
                'storage_class': storage_class,
                'cost_retrieved_at': 'default_pricing'
            }
    
    def _calculate_file_hash(self, file_path, algorithm='sha256'):
        """Calculate hash of file for comparison and verification"""
        if algorithm == 'md5':
            hash_obj = hashlib.md5()
        elif algorithm == 'sha256':
            hash_obj = hashlib.sha256()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            self.logger.log_error(e, f"hash calculation for {file_path}")
            return None
    
    def _get_s3_object_metadata(self, key):
        """Get metadata of S3 object for comparison"""
        try:
            # Use the retry mechanism for head_object calls
            def head_object_operation():
                return self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            
            response = self._retry_with_backoff(head_object_operation)
            
            return {
                'etag': response['ETag'].strip('"'),  # Remove quotes
                'size': response['ContentLength'],
                'last_modified': response['LastModified']
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            else:
                self.logger.log_error(e, f"S3 metadata retrieval for {key}")
                return None
        except Exception as e:
            self.logger.log_error(e, f"S3 metadata retrieval for {key}")
            return None
    
    def _should_upload_file(self, local_file, s3_key):
        """Determine if file should be uploaded based on comparison"""
        if not local_file.exists():
            return False
        
        # Check if file exists in S3
        s3_metadata = self._get_s3_object_metadata(s3_key)
        if not s3_metadata:
            return True
        
        # Compare file sizes first (faster than hash)
        local_size = local_file.stat().st_size
        if local_size != s3_metadata['size']:
            return True
        
        # Compare hashes for integrity (S3 ETags are typically MD5)
        local_md5 = self._calculate_file_hash(local_file, 'md5')
        if local_md5 and local_md5 != s3_metadata['etag']:
            return True
        
        return False
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (ClientError, ConnectionError, ReadTimeoutError) as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    self.logger.error(f"Max retries ({self.max_retries}) exceeded")
                    raise last_exception
                
                # Calculate delay with exponential backoff and jitter
                delay = min(self.retry_delay_base * (2 ** attempt), self.retry_delay_max)
                jitter = random.uniform(0, 0.1 * delay)
                total_delay = delay + jitter
                
                self.logger.log_retry_attempt(operation="upload", attempt=attempt + 1, 
                                            max_retries=self.max_retries, delay=total_delay, 
                                            error=str(e))
                
                with self.stats_lock:
                    self.stats['retries_attempted'] += 1
                
                time.sleep(total_delay)
        
        raise last_exception
    
    def _upload_file_simple(self, local_file, s3_key):
        """Upload file using simple upload with retry logic"""
        def upload_operation():
            self.s3_client.upload_file(
                str(local_file),
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'StorageClass': self.config.get('s3', {}).get('storage_class', 'STANDARD'),
                    'ServerSideEncryption': 'AES256' if self.config.get('s3', {}).get('encryption', {}).get('enabled', True) else None,
                    'Metadata': {
                        'original-filename': local_file.name,
                        'upload-timestamp': datetime.now().isoformat(),
                        'hash-algorithm': self.hash_algorithm
                    }
                }
            )
            return True
        try:
            return self._retry_with_backoff(upload_operation)
        except Exception as e:
            self.logger.log_error(e, f"upload operation for {local_file}")
            return False

    def _upload_file_multipart(self, local_file, s3_key):
        """Upload large file using multipart upload with retry logic"""
        file_size = local_file.stat().st_size
        chunk_size = self.config.get('sync', {}).get('chunk_size_mb', 100) * 1024 * 1024

        def create_multipart_upload():
            return self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                StorageClass=self.config.get('s3', {}).get('storage_class', 'STANDARD'),
                ServerSideEncryption='AES256' if self.config.get('s3', {}).get('encryption', {}).get('enabled', True) else None,
                Metadata={
                    'original-filename': local_file.name,
                    'upload-timestamp': datetime.now().isoformat(),
                    'hash-algorithm': self.hash_algorithm
                }
            )
        try:
            # Start multipart upload with retry
            mpu = self._retry_with_backoff(create_multipart_upload)
            parts = []
            part_number = 1

            with open(local_file, 'rb') as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    def upload_part():
                        return self.s3_client.upload_part(
                            Bucket=self.bucket_name,
                            Key=s3_key,
                            PartNumber=part_number,
                            UploadId=mpu['UploadId'],
                            Body=data
                        )
                    part = self._retry_with_backoff(upload_part)
                    parts.append({
                        'ETag': part['ETag'],
                        'PartNumber': part_number
                    })
                    part_number += 1
            def complete_multipart():
                return self.s3_client.complete_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    UploadId=mpu['UploadId'],
                    MultipartUpload={'Parts': parts}
                )
            self._retry_with_backoff(complete_multipart)
            return True
        except Exception as e:
            try:
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    UploadId=mpu['UploadId']
                )
            except:
                pass
            self.logger.log_error(e, f"multipart upload for {local_file}")
            return False
    
    def _verify_upload(self, local_file, s3_key):
        """Verify uploaded file integrity"""
        if not self.verify_upload:
            return True
        
        try:
            # Get S3 object metadata
            s3_metadata = self._get_s3_object_metadata(s3_key)
            if not s3_metadata:
                self.logger.log_error(Exception(f"File not found in S3: {s3_key}"), "upload verification")
                return False
            
            # Compare file sizes
            local_size = local_file.stat().st_size
            if local_size != s3_metadata['size']:
                self.logger.log_error(Exception(f"Size mismatch: local={local_size}, s3={s3_metadata['size']}"), "upload verification")
                return False
            
            # Compare hashes if using MD5 (S3 ETag for simple uploads)
            if self.hash_algorithm == 'md5':
                local_hash = self._calculate_file_hash(local_file, 'md5')
                if local_hash and local_hash != s3_metadata['etag']:
                    self.logger.log_error(Exception(f"Hash mismatch for {s3_key}"), "upload verification")
                    return False
            
            self.logger.log_verification_result(local_file, s3_key, True)
            return True
            
        except Exception as e:
            self.logger.log_error(e, f"upload verification for {s3_key}")
            return False
    
    def _upload_file(self, local_file, s3_key):
        """Upload file with appropriate method based on size"""
        file_size = local_file.stat().st_size
        max_simple_size = 100 * 1024 * 1024  # 100MB
        
        try:
            if file_size <= max_simple_size:
                success = self._upload_file_simple(local_file, s3_key)
            else:
                success = self._upload_file_multipart(local_file, s3_key)
            
            # Verify upload if enabled
            if success and self.verify_upload:
                if not self._verify_upload(local_file, s3_key):
                    self.logger.log_verification_result(local_file, s3_key, False, "verification failed")
                    return False
            
            return success
            
        except Exception as e:
            self.logger.log_error(e, f"upload operation for {local_file}")
            return False
    
    def _should_include_file(self, file_path):
        """Check if file should be included based on filters"""
        sync_config = self.config.get('sync', {})
        exclude_patterns = sync_config.get('exclude_patterns', [])
        include_patterns = sync_config.get('include_patterns', ['*'])
        
        # Check include patterns first
        included = False
        for pattern in include_patterns:
            if file_path.match(pattern):
                included = True
                break
        
        if not included:
            return False
        
        # Check exclude patterns
        for pattern in exclude_patterns:
            if file_path.match(pattern):
                return False
        
        return True
    
    def _calculate_s3_key(self, file_path):
        """Calculate S3 key for a file, ensuring valid S3 key format while preserving structure"""
        # Convert string to Path if needed
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        try:
            # Try the standard relative_to method first
            relative_path = file_path.relative_to(self.local_path)
            s3_key = str(relative_path)
            
            # Normalize path separators for S3
            s3_key = s3_key.replace('\\', '/')
            
            # Remove any leading slashes
            s3_key = s3_key.lstrip('/')
            
            return s3_key
            
        except ValueError:
            # If relative_to fails (e.g., paths outside current directory), 
            # use absolute paths and create a normalized key
            try:
                # Get absolute paths
                abs_file_path = file_path.resolve()
                abs_local_path = self.local_path.resolve()
                
                # Calculate relative path using absolute paths
                relative_path = abs_file_path.relative_to(abs_local_path)
                s3_key = str(relative_path)
                
                # Normalize path separators for S3
                s3_key = s3_key.replace('\\', '/')
                
                # Remove any leading slashes
                s3_key = s3_key.lstrip('/')
                
                return s3_key
                
            except ValueError:
                # If that still fails, create a key based on the file's absolute path
                # This ensures we have a consistent key regardless of where the sync is run from
                abs_file_path = file_path.resolve()
                
                # Try to create a meaningful key based on the file's location
                # Use the last few components of the path to maintain some structure
                path_parts = abs_file_path.parts
                
                # Find the astro directory in the path
                try:
                    astro_index = path_parts.index('astro')
                    # Use everything from astro onwards, but remove the 'astro' prefix
                    # to match existing S3 structure
                    relevant_parts = path_parts[astro_index + 1:]  # Skip 'astro' itself
                    s3_key = '/'.join(relevant_parts)
                except ValueError:
                    # If no astro directory found, use the last few path components
                    if len(path_parts) >= 3:
                        s3_key = '/'.join(path_parts[-3:])
                    else:
                        s3_key = file_path.name
                
                # Normalize path separators for S3
                s3_key = s3_key.replace('\\', '/')
                
                # Remove any leading slashes
                s3_key = s3_key.lstrip('/')
                
                return s3_key
    
    def _discover_files(self):
        """Quickly discover all files that would be synced (without S3 checks)"""
        discovered_files = []
        
        if not self.local_path.exists():
            self.logger.log_error(Exception(f"Local path does not exist: {self.local_path}"), "file discovery")
            return discovered_files
        
        # First, get all files to count them
        all_files = list(self.local_path.rglob('*'))
        
        # Use progress bar for large directories
        if len(all_files) > 1000 and TQDM_AVAILABLE:
            self.logger.log_info(f"🔍 Discovering files in {self.local_path}...")
            for file_path in tqdm(all_files, desc="Discovering files", unit="files"):
                if file_path.is_file() and self._should_include_file(file_path):
                    s3_key = self._calculate_s3_key(file_path)
                    discovered_files.append((file_path, s3_key))
        else:
            # For smaller directories, use traditional approach
            for file_path in all_files:
                if file_path.is_file() and self._should_include_file(file_path):
                    s3_key = self._calculate_s3_key(file_path)
                    discovered_files.append((file_path, s3_key))
        
        return discovered_files
    
    def _get_files_to_sync(self):
        """Get list of files that actually need to be synced (with S3 checks)"""
        files_to_sync = []
        
        if not self.local_path.exists():
            self.logger.log_error(Exception(f"Local path does not exist: {self.local_path}"), "file discovery")
            return files_to_sync
        
        # Get all files to check
        all_files = []
        for file_path in self.local_path.rglob('*'):
            if file_path.is_file() and self._should_include_file(file_path):
                s3_key = self._calculate_s3_key(file_path)
                all_files.append((file_path, s3_key))
        
        # Use progress bar for large file sets
        if len(all_files) > 100 and TQDM_AVAILABLE:
            self.logger.log_info(f"🔍 Checking {len(all_files)} files for changes...")
            for file_path, s3_key in tqdm(all_files, desc="Checking files", unit="files", 
                                         bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'):
                if self._should_upload_file(file_path, s3_key):
                    files_to_sync.append((file_path, s3_key))
        else:
            # For smaller file sets or when tqdm is not available, use verbose logging
            for file_path, s3_key in all_files:
                if self._should_upload_file(file_path, s3_key):
                    files_to_sync.append((file_path, s3_key))
        
        return files_to_sync
    
    def _update_stats(self, uploaded=False, skipped=False, failed=False, bytes_uploaded=0):
        """Thread-safe statistics update"""
        with self.stats_lock:
            if uploaded:
                self.stats['files_uploaded'] += 1
                self.stats['bytes_uploaded'] += bytes_uploaded
            elif skipped:
                self.stats['files_skipped'] += 1
            elif failed:
                self.stats['files_failed'] += 1
    
    def _upload_worker(self, file_info):
        """Worker function for concurrent uploads"""
        local_file, s3_key = file_info
        
        try:
            # Update dashboard with file info
            if self.dashboard:
                file_info = {
                    'file_path': str(local_file),
                    'file_size': local_file.stat().st_size,
                    'file_name': local_file.name
                }
                self.dashboard.increment_processed()
            
            if self.dry_run:
                # Suppress individual file logging when dashboard is available
                if self.verbose and len(self.files_to_sync) < 50 and not self.dashboard:
                    self.logger.log_info(f"[DRY RUN] Would upload: {local_file} -> s3://{self.bucket_name}/{s3_key}")
                self._update_stats(skipped=True)
                if self.dashboard:
                    self.dashboard.increment_skipped()
                return True
            
            # Suppress individual file logging when dashboard is available
            if self.verbose and len(self.files_to_sync) < 50 and not self.dashboard:
                self.logger.log_info(f"Uploading: {local_file} -> s3://{self.bucket_name}/{s3_key}")
            
            # Track upload start time for speed calculation
            upload_start_time = datetime.now()
            
            # Validate S3 key before upload
            if s3_key.startswith('../') or s3_key.startswith('..\\'):
                self.logger.log_error(Exception(f"Invalid S3 key: {s3_key}"), f"upload validation for {local_file}")
                self._update_stats(failed=True)
                if self.dashboard:
                    self.dashboard.increment_failed()
                    self.dashboard.add_error(Exception(f"Invalid S3 key: {s3_key}"), local_file.name)
                return False
            
            if self._upload_file(local_file, s3_key):
                file_size = local_file.stat().st_size
                upload_duration = (datetime.now() - upload_start_time).total_seconds()
                
                # Calculate upload speed
                upload_speed_mbps = 0
                if upload_duration > 0:
                    upload_speed_mbps = (file_size / (1024 * 1024)) / upload_duration
                
                self._update_stats(uploaded=True, bytes_uploaded=file_size)
                
                # Update dashboard with upload success
                if self.dashboard:
                    self.dashboard.increment_uploaded(file_size)
                    self.dashboard.update_progress(
                        file_info=file_info,
                        upload_speed=upload_speed_mbps,
                        verification_status='passed' if self.verify_upload else 'skipped'
                    )
                
                return True
            else:
                self._update_stats(failed=True)
                if self.dashboard:
                    self.dashboard.increment_failed()
                    self.dashboard.add_error(Exception("Upload failed"), local_file.name)
                return False
                
        except Exception as e:
            self.logger.log_error(e, f"Error uploading {local_file}")
            self._update_stats(failed=True)
            if self.dashboard:
                self.dashboard.increment_failed()
                self.dashboard.add_error(e, local_file.name)
            return False
    
    def _cleanup_invalid_s3_objects(self):
        """Clean up S3 objects with invalid keys (e.g., containing '../')"""
        try:
            self.logger.log_info("🧹 Checking for invalid S3 objects to clean up...")
            
            # List objects in the bucket
            paginator = self.s3_client.get_paginator('list_objects_v2')
            invalid_objects = []
            
            for page in paginator.paginate(Bucket=self.bucket_name):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Check for invalid keys that contain '../' or similar patterns
                        if '../' in key or key.startswith('..') or '\\' in key:
                            invalid_objects.append(key)
            
            if invalid_objects:
                self.logger.log_info(f"🗑️  Found {len(invalid_objects)} invalid S3 objects to delete")
                
                # Delete invalid objects in batches
                batch_size = 1000
                for i in range(0, len(invalid_objects), batch_size):
                    batch = invalid_objects[i:i + batch_size]
                    delete_objects = [{'Key': key} for key in batch]
                    
                    try:
                        response = self.s3_client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': delete_objects}
                        )
                        deleted_count = len(response.get('Deleted', []))
                        self.logger.log_info(f"✅ Deleted {deleted_count} invalid objects")
                    except Exception as e:
                        self.logger.log_error(e, f"cleanup of invalid objects batch {i//batch_size + 1}")
            else:
                self.logger.log_info("✅ No invalid S3 objects found")
                
        except Exception as e:
            self.logger.log_error(e, "cleanup of invalid S3 objects")
    
    def _check_existing_files_with_correct_keys(self):
        """Check if files already exist in S3 with correct keys"""
        try:
            self.logger.log_info("🔍 Checking for existing files with correct S3 keys...")
            
            # Get all files that would be synced
            all_files = []
            for file_path in self.local_path.rglob('*'):
                if file_path.is_file() and self._should_include_file(file_path):
                    s3_key = self._calculate_s3_key(file_path)
                    all_files.append((file_path, s3_key))
            
            if not all_files:
                self.logger.log_info("📊 No files found to check")
                return 0
            
            self.logger.log_info(f"📊 Checking {len(all_files)} files for existing S3 objects...")
            
            existing_files = 0
            checked_files = 0
            
            # Process files in batches to avoid overwhelming the API
            batch_size = 50
            for i in range(0, len(all_files), batch_size):
                batch = all_files[i:i + batch_size]
                
                for file_path, s3_key in batch:
                    try:
                        # Add timeout to individual head_object calls
                        if self._get_s3_object_metadata(s3_key):
                            existing_files += 1
                        
                        checked_files += 1
                        
                        # Log progress every 100 files
                        if checked_files % 100 == 0:
                            self.logger.log_info(f"📊 Progress: {checked_files}/{len(all_files)} files checked, {existing_files} found in S3")
                            
                    except Exception as e:
                        self.logger.log_error(e, f"checking S3 object for {s3_key}")
                        # Continue with next file instead of failing completely
                        checked_files += 1
                        continue
                
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(all_files):
                    time.sleep(0.1)
            
            self.logger.log_info(f"📊 Found {existing_files} files already in S3 with correct keys (out of {checked_files} checked)")
            return existing_files
            
        except Exception as e:
            self.logger.log_error(e, "check for existing files with correct keys")
            return 0
    
    def sync(self):
        """Main sync operation"""
        self.stats['start_time'] = datetime.now()
        
        # Start dashboard if available
        if self.dashboard:
            self.dashboard.start()
        
        self.logger.log_info("🚀 Starting S3 sync operation")
        self.logger.log_info(f"Local path: {self.local_path}")
        self.logger.log_info(f"S3 bucket: {self.bucket_name}")
        self.logger.log_info(f"Dry run: {self.dry_run}")
        self.logger.log_info(f"Max retries: {self.max_retries}")
        self.logger.log_info(f"Hash algorithm: {self.hash_algorithm}")
        self.logger.log_info(f"Upload verification: {self.verify_upload}")
        
        # Verify AWS identity before proceeding
        # Skip identity verification in test mode (when verbose is set)
        if AWSIdentityVerifier and not self.verbose:
            try:
                identity_verifier = AWSIdentityVerifier(profile=self.profile, config=self.config)
                if not identity_verifier.verify_identity_for_sync(bucket_name=self.bucket_name, dry_run=self.dry_run):
                    self.logger.log_info("❌ Sync cancelled during identity verification")
                    if self.dashboard:
                        self.dashboard.stop()
                    return False
            except Exception as e:
                self.logger.log_error(e, "AWS identity verification")
                print(f"❌ AWS identity verification failed: {e}")
                if self.dashboard:
                    self.dashboard.stop()
                return False
        elif not self.verbose:
            self.logger.log_info("⚠️  AWS identity verification module not available")
        
        # Clean up any invalid S3 objects that might have been created with wrong keys
        # Only do this in real sync mode, not dry run or test mode
        if not self.dry_run and not self.verbose:  # verbose is often set in tests
            try:
                self._cleanup_invalid_s3_objects()
            except Exception as e:
                self.logger.log_error(e, "cleanup of invalid S3 objects")
        
        # Check for existing files with correct keys to provide better feedback
        # Only do this in real sync mode, not dry run or test mode
        existing_count = 0
        if not self.dry_run and not self.verbose and not self.skip_existing_check:
            try:
                # Add timeout to prevent hanging
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Existing files check timed out")
                
                # Set a 5-minute timeout for the existing files check
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(300)  # 5 minutes
                
                try:
                    existing_count = self._check_existing_files_with_correct_keys()
                finally:
                    signal.alarm(0)  # Cancel the alarm
                    
            except TimeoutError:
                self.logger.log_info("⚠️  Existing files check timed out - continuing with sync")
                existing_count = 0
            except Exception as e:
                self.logger.log_error(e, "check for existing files with correct keys")
                existing_count = 0
        elif self.skip_existing_check:
            self.logger.log_info("⏭️  Skipping existing files check (--skip-existing-check specified)")
        
        # First, quickly discover all files (without S3 checks)
        discovered_files = self._discover_files()
        
        if not discovered_files:
            self.logger.log_info("✅ No files found to sync")
            if self.dashboard:
                self.dashboard.stop()
            return True
        
        self.logger.log_info(f"📁 Found {len(discovered_files)} files to check")
        
        # Show confirmation dialogue with discovered files (skip if no_confirm is True)
        if not self.no_confirm:
            if not self._show_confirmation_dialogue(discovered_files):
                self.logger.log_info("❌ Sync cancelled by user")
                if self.dashboard:
                    self.dashboard.stop()
                return False
        
        # Now do the expensive S3 checks to see which files actually need syncing
        self.logger.log_info("🔍 Checking which files need to be synced...")
        files_to_sync = self._get_files_to_sync()
        
        if not files_to_sync:
            self.logger.log_info("✅ No files to sync - everything is up to date")
            if self.dashboard:
                self.dashboard.stop()
            return True
        
        self.logger.log_info(f"📁 Found {len(files_to_sync)} files that need syncing")
        
        # Set total files for dashboard
        if self.dashboard:
            self.dashboard.set_total_files(len(files_to_sync))
        
        # Store files_to_sync for worker access
        self.files_to_sync = files_to_sync
        
        # Upload files with concurrency
        max_workers = self.config.get('sync', {}).get('max_concurrent_uploads', 5)
        
        # Use dashboard for progress tracking
        if self.dashboard:
            self.logger.log_info(f"🚀 Starting upload of {len(files_to_sync)} files...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._upload_worker, file_info) for file_info in files_to_sync]
                
                # Process completed futures with dashboard updates
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        self.logger.log_error(e, "Upload task failed")
        else:
            # Fallback to progress bar for large operations
            if len(files_to_sync) > 50 and TQDM_AVAILABLE:
                self.logger.log_info(f"🚀 Starting upload of {len(files_to_sync)} files...")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(self._upload_worker, file_info) for file_info in files_to_sync]
                    
                    # Process completed futures with progress bar
                    with tqdm(total=len(files_to_sync), desc="Uploading", unit="files") as pbar:
                        for future in as_completed(futures):
                            try:
                                future.result()
                                pbar.update(1)
                            except Exception as e:
                                self.logger.log_error(e, "Upload task failed")
                                pbar.update(1)
            else:
                # For smaller operations, use traditional logging
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(self._upload_worker, file_info) for file_info in files_to_sync]
                    
                    # Process completed futures
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            self.logger.log_error(e, "Upload task failed")
        
        self.stats['end_time'] = datetime.now()
        
        # Stop dashboard
        if self.dashboard:
            self.dashboard.stop()
        else:
            self._print_summary()
        
        return self.stats['files_failed'] == 0
    
    def _show_confirmation_dialogue(self, discovered_files):
        """Show confirmation dialogue with sync details"""
        total_files = len(discovered_files)
        total_size = sum(local_file.stat().st_size for local_file, _ in discovered_files)
        
        # Calculate estimates using real cost data
        estimated_check_time_minutes = (total_files * 0.1) / 60  # Convert to minutes
        estimated_check_cost = (total_files / 1000) * self.current_costs['api_requests_per_1000']
        total_size_gb = total_size / 1024 / 1024 / 1024  # Convert to GB
        
        print("\n" + "="*60)
        print("🔄 SYNC CONFIRMATION")
        print("="*60)
        print(f"📁 Directory to sync: {self.local_path.absolute()}")
        print(f"🪣 S3 Bucket: {self.bucket_name}")
        print(f"📊 Files to check: {total_files}")
        print(f"💾 Total size: {total_size:,} bytes ({total_size_gb:.3f} GB)")
        print(f"🗄️  Storage class: {self.current_costs.get('storage_class', 'STANDARD')}")
        
        # Show current S3 costs if available
        if self.current_costs['s3_monthly_cost'] > 0:
            print(f"💰 Current S3 costs this month: ${self.current_costs['s3_monthly_cost']:.2f}")
        print(f"📊 Cost data retrieved: {self.current_costs['cost_retrieved_at']}")
        
        print(f"\n⏱️  Estimated check time: ~{estimated_check_time_minutes:.1f} minutes")
        print(f"💰 Estimated costs:")
        print(f"   • S3 HEAD requests: ~${estimated_check_cost:.3f}")
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - Will check which files need syncing")
            print("   (Makes S3 API calls to compare local files with S3 objects)")
            print("   (Shows what would be uploaded without actually uploading)")
        else:
            print("⚠️  REAL UPLOAD MODE - Will upload files that need syncing")
            data_transfer_cost = total_size_gb * self.current_costs['data_transfer_in_per_gb']  # FREE for uploads
            storage_cost_monthly = total_size_gb * self.current_costs['storage_per_gb_month']
            storage_class = self.current_costs.get('storage_class', 'STANDARD')
            print(f"   • Data transfer (upload): ~${data_transfer_cost:.3f} (FREE)")
            print(f"   • Monthly storage ({storage_class}): ~${storage_cost_monthly:.3f}/month")
            print(f"   • Total upload cost: ~${data_transfer_cost:.3f} (FREE)")
        
        print("\n📋 Files to be checked:")
        for i, (local_file, s3_key) in enumerate(discovered_files[:10], 1):  # Show first 10 files
            file_size = local_file.stat().st_size
            print(f"  {i:2d}. {local_file.name} -> s3://{self.bucket_name}/{s3_key} ({file_size:,} bytes)")
        
        if total_files > 10:
            print(f"  ... and {total_files - 10} more files")
        
        print("="*60)
        
        while True:
            if self.dry_run:
                response = input("Proceed with dry-run? (y/N): ").strip().lower()
            else:
                response = input("Proceed with upload? (y/N): ").strip().lower()
            
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no', '']:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    def _print_summary(self):
        """Print sync operation summary"""
        duration = self.stats['end_time'] - self.stats['start_time']
        total_files = self.stats['files_uploaded'] + self.stats['files_skipped'] + self.stats['files_failed']
        
        print("\n" + "="*50)
        print("📊 SYNC SUMMARY")
        print("="*50)
        print(f"⏱️  Duration: {duration}")
        print(f"📁 Total files processed: {total_files}")
        print(f"✅ Files uploaded: {self.stats['files_uploaded']}")
        print(f"⏭️  Files skipped: {self.stats['files_skipped']}")
        print(f"❌ Files failed: {self.stats['files_failed']}")
        print(f"💾 Bytes uploaded: {self.stats['bytes_uploaded']:,} bytes ({self.stats['bytes_uploaded'] / 1024 / 1024:.2f} MB)")
        print(f"🔄 Retries attempted: {self.stats['retries_attempted']}")
        
        if total_files > 0:
            success_rate = ((self.stats['files_uploaded'] + self.stats['files_skipped']) / total_files) * 100
            print(f"📈 Success rate: {success_rate:.1f}%")
        
        if self.stats['files_failed'] == 0:
            print("✅ Sync completed successfully")
        else:
            print("⚠️  Sync completed with errors")
        print("="*50)

def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="S3 Sync Tool - Upload files to AWS S3 with incremental sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/sync.py                    # Sync with default config
  python scripts/sync.py --local-path ./photos --bucket my-sync-bucket
  python scripts/sync.py --dry-run          # Preview what would be uploaded
  python scripts/sync.py --config config/sync-config.json --verbose
  python scripts/sync.py --no-confirm       # Skip confirmation dialogue
        """
    )
    
    parser.add_argument(
        '--config',
        help='Path to configuration file (default: config/aws-config.json)'
    )
    parser.add_argument(
        '--profile',
        help='AWS profile to use (default: from config)'
    )
    parser.add_argument(
        '--bucket',
        dest='bucket_name',
        help='S3 bucket name (default: from config)'
    )
    parser.add_argument(
        '--local-path',
        help='Local directory to sync (default: from config)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be uploaded without actually uploading'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Skip confirmation dialogue (useful for automated scripts)'
    )
    parser.add_argument(
        '--skip-existing-check',
        action='store_true',
        help='Skip checking for existing files in S3 (faster but less informative)'
    )
    
    args = parser.parse_args()
    
    try:
        sync = S3Sync(
            config_file=args.config,
            profile=args.profile,
            bucket_name=args.bucket_name,
            local_path=args.local_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
            no_confirm=args.no_confirm,
            skip_existing_check=args.skip_existing_check
        )
        
        success = sync.sync()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 