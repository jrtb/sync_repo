#!/usr/bin/env python3
"""
Structured Logging Module for AWS S3 Sync Operations

This module provides comprehensive logging functionality for sync operations,
including structured logging, CloudWatch integration, and performance metrics.
Designed for AWS certification study with practical monitoring implementation.

AWS Concepts Covered:
- CloudWatch Logs and Metrics
- Structured logging for operational monitoring
- Performance monitoring and alerting
- Log retention and lifecycle policies
- Security logging and audit trails

Usage:
    from scripts.logger import SyncLogger
    logger = SyncLogger('sync-operation')
    logger.log_sync_start(bucket_name, local_path)
    logger.log_file_upload(file_path, s3_key, file_size)
    logger.log_sync_complete(stats)
"""

import json
import logging
import logging.handlers
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

class SyncLogger:
    """Structured logger for sync operations with CloudWatch integration"""
    
    def __init__(self, operation_name: str, config: Dict[str, Any] = None):
        """Initialize sync logger with configuration"""
        self.operation_name = operation_name
        self.config = config or {}
        self.project_root = Path(__file__).parent.parent
        
        # CloudWatch configuration
        self.cloudwatch_enabled = self.config.get('logging', {}).get('cloudwatch_enabled', False)
        self.log_group_name = self.config.get('logging', {}).get('log_group_name', '/aws/sync/photos')
        self.log_stream_name = f"{operation_name}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        
        # Performance tracking
        self.start_time = None
        self.operation_stats = {
            'files_processed': 0,
            'files_uploaded': 0,
            'files_skipped': 0,
            'files_failed': 0,
            'bytes_uploaded': 0,
            'retries_attempted': 0,
            'errors': []
        }
        
        # Setup logging infrastructure
        self._setup_logging()
        
        # Initialize CloudWatch if enabled
        if self.cloudwatch_enabled:
            self._setup_cloudwatch()
    
    def _setup_logging(self):
        """Setup structured logging with file rotation"""
        # Create logs directory
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(f"sync.{self.operation_name}")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler with structured format
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with JSON structured logging
        log_file = log_dir / f"{self.operation_name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        
        # JSON formatter for structured logging
        class JSONFormatter(logging.Formatter):
            def __init__(self, operation_name, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.operation_name = operation_name
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'operation': self.operation_name
                }
                
                # Add extra fields if present
                if hasattr(record, 'extra_fields'):
                    log_entry.update(record.extra_fields)
                
                return json.dumps(log_entry)
        
        file_handler.setFormatter(JSONFormatter(self.operation_name))
        self.logger.addHandler(file_handler)
        
        # Error file handler
        error_file = log_dir / f"{self.operation_name}-errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter(self.operation_name))
        self.logger.addHandler(error_handler)
    
    def _setup_cloudwatch(self):
        """Initialize CloudWatch logging client"""
        try:
            session = boto3.Session()
            self.cloudwatch_logs = session.client('logs')
            
            # Create log group if it doesn't exist
            try:
                self.cloudwatch_logs.create_log_group(logGroupName=self.log_group_name)
                self.logger.info(f"Created CloudWatch log group: {self.log_group_name}")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    self.logger.warning(f"Could not create CloudWatch log group: {e}")
            
            # Create log stream
            try:
                self.cloudwatch_logs.create_log_stream(
                    logGroupName=self.log_group_name,
                    logStreamName=self.log_stream_name
                )
                self.logger.info(f"Created CloudWatch log stream: {self.log_stream_name}")
            except ClientError as e:
                self.logger.warning(f"Could not create CloudWatch log stream: {e}")
                
        except (NoCredentialsError, ClientError) as e:
            self.logger.warning(f"CloudWatch logging disabled: {e}")
            self.cloudwatch_enabled = False
    
    def _log_to_cloudwatch(self, message: str, level: str = 'INFO', extra_fields: Dict[str, Any] = None):
        """Send log message to CloudWatch"""
        if not self.cloudwatch_enabled:
            return
        
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'message': message,
                'operation': self.operation_name
            }
            
            if extra_fields:
                log_entry.update(extra_fields)
            
            # CloudWatch Logs expects timestamp in milliseconds
            timestamp = int(time.time() * 1000)
            
            self.cloudwatch_logs.put_log_events(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name,
                logEvents=[{
                    'timestamp': timestamp,
                    'message': json.dumps(log_entry)
                }]
            )
            
        except Exception as e:
            # Don't let CloudWatch failures break the main operation
            self.logger.debug(f"Failed to log to CloudWatch: {e}")
    
    def log_sync_start(self, bucket_name: str, local_path: str, dry_run: bool = False):
        """Log sync operation start with configuration details"""
        self.start_time = datetime.now()
        
        message = f"🚀 Starting sync operation: {self.operation_name}"
        extra_fields = {
            'event_type': 'sync_start',
            'bucket_name': bucket_name,
            'local_path': str(local_path),
            'dry_run': dry_run,
            'start_time': self.start_time.isoformat()
        }
        
        self.logger.info(message, extra={'extra_fields': extra_fields})
        self._log_to_cloudwatch(message, 'INFO', extra_fields)
    
    def log_file_upload(self, file_path: Path, s3_key: str, file_size: int, 
                       upload_success: bool, retry_count: int = 0, error: str = None):
        """Log individual file upload attempt"""
        self.operation_stats['files_processed'] += 1
        
        if upload_success:
            self.operation_stats['files_uploaded'] += 1
            self.operation_stats['bytes_uploaded'] += file_size
            message = f"✅ Uploaded: {file_path.name} -> s3://{s3_key}"
            level = 'INFO'
        else:
            self.operation_stats['files_failed'] += 1
            if error:
                self.operation_stats['errors'].append(str(error))
            message = f"❌ Failed to upload: {file_path.name} -> s3://{s3_key}"
            level = 'ERROR'
        
        extra_fields = {
            'event_type': 'file_upload',
            'file_path': str(file_path),
            's3_key': s3_key,
            'file_size': file_size,
            'upload_success': upload_success,
            'retry_count': retry_count,
            'error': error
        }
        
        self.logger.log(
            logging.ERROR if not upload_success else logging.INFO,
            message,
            extra={'extra_fields': extra_fields}
        )
        self._log_to_cloudwatch(message, level, extra_fields)
    
    def log_file_skip(self, file_path: Path, s3_key: str, reason: str):
        """Log file skip operation"""
        self.operation_stats['files_skipped'] += 1
        
        message = f"⏭️  Skipped: {file_path.name} ({reason})"
        extra_fields = {
            'event_type': 'file_skip',
            'file_path': str(file_path),
            's3_key': s3_key,
            'skip_reason': reason
        }
        
        self.logger.info(message, extra={'extra_fields': extra_fields})
        self._log_to_cloudwatch(message, 'INFO', extra_fields)
    
    def log_retry_attempt(self, operation: str, attempt: int, max_retries: int, 
                         delay: float, error: str):
        """Log retry attempt with backoff details"""
        self.operation_stats['retries_attempted'] += 1
        
        message = f"🔄 Retry attempt {attempt}/{max_retries} for {operation} (delay: {delay:.1f}s)"
        extra_fields = {
            'event_type': 'retry_attempt',
            'operation': operation,
            'attempt': attempt,
            'max_retries': max_retries,
            'delay': delay,
            'error': error
        }
        
        self.logger.warning(message, extra={'extra_fields': extra_fields})
        self._log_to_cloudwatch(message, 'WARNING', extra_fields)
    
    def log_verification_result(self, file_path: Path, s3_key: str, verification_passed: bool, 
                              details: str = None):
        """Log file verification results - only log failures to reduce verbosity"""
        extra_fields = {
            'event_type': 'verification_result',
            'file_path': str(file_path),
            's3_key': s3_key,
            'verification_passed': verification_passed,
            'details': details
        }
        
        # Only log verification failures to reduce verbosity
        if not verification_passed:
            message = f"❌ Verification failed: {file_path.name}"
            if details:
                message += f" - {details}"
            
            self.logger.error(message, extra={'extra_fields': extra_fields})
            self._log_to_cloudwatch(message, 'ERROR', extra_fields)
    
    def log_sync_complete(self, final_stats: Dict[str, Any] = None):
        """Log sync operation completion with summary"""
        end_time = datetime.now()
        duration = end_time - self.start_time if self.start_time else timedelta(0)
        
        # Merge with final stats if provided
        if final_stats:
            self.operation_stats.update(final_stats)
        
        # Calculate performance metrics
        throughput = 0
        if duration.total_seconds() > 0:
            throughput = self.operation_stats['bytes_uploaded'] / duration.total_seconds()
        
        success_rate = 0
        total_files = self.operation_stats['files_uploaded'] + self.operation_stats['files_failed']
        if total_files > 0:
            success_rate = (self.operation_stats['files_uploaded'] / total_files) * 100
        
        message = f"🏁 Sync operation completed in {duration}"
        extra_fields = {
            'event_type': 'sync_complete',
            'duration_seconds': duration.total_seconds(),
            'files_uploaded': self.operation_stats['files_uploaded'],
            'files_skipped': self.operation_stats['files_skipped'],
            'files_failed': self.operation_stats['files_failed'],
            'bytes_uploaded': self.operation_stats['bytes_uploaded'],
            'retries_attempted': self.operation_stats['retries_attempted'],
            'throughput_bytes_per_second': throughput,
            'success_rate_percent': success_rate,
            'end_time': end_time.isoformat()
        }
        
        # Add errors if any
        if self.operation_stats['errors']:
            extra_fields['errors'] = self.operation_stats['errors']
        
        level = 'ERROR' if self.operation_stats['files_failed'] > 0 else 'INFO'
        self.logger.log(
            logging.ERROR if self.operation_stats['files_failed'] > 0 else logging.INFO,
            message,
            extra={'extra_fields': extra_fields}
        )
        self._log_to_cloudwatch(message, level, extra_fields)
        
        # Print summary to console
        self._print_summary(duration, throughput, success_rate)
    
    def _print_summary(self, duration: timedelta, throughput: float, success_rate: float):
        """Print human-readable summary to console"""
        print("\n" + "="*60)
        print("📊 SYNC OPERATION SUMMARY")
        print("="*60)
        print(f"Operation: {self.operation_name}")
        print(f"Duration: {duration}")
        print(f"Files uploaded: {self.operation_stats['files_uploaded']}")
        print(f"Files skipped: {self.operation_stats['files_skipped']}")
        print(f"Files failed: {self.operation_stats['files_failed']}")
        print(f"Bytes uploaded: {self.operation_stats['bytes_uploaded']:,}")
        print(f"Throughput: {throughput/1024/1024:.2f} MB/s")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Retries attempted: {self.operation_stats['retries_attempted']}")
        
        if self.operation_stats['files_failed'] == 0:
            print("✅ Operation completed successfully")
        else:
            print("⚠️  Operation completed with errors")
            if self.operation_stats['errors']:
                print("\nErrors encountered:")
                for error in self.operation_stats['errors'][:5]:  # Show first 5 errors
                    print(f"  - {error}")
                if len(self.operation_stats['errors']) > 5:
                    print(f"  ... and {len(self.operation_stats['errors']) - 5} more errors")
        
        print("="*60)
    
    def log_error(self, error: Exception, context: str = None):
        """Log error with context"""
        message = f"❌ Error in {context or 'sync operation'}: {str(error)}"
        extra_fields = {
            'event_type': 'error',
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context
        }
        
        self.logger.error(message, extra={'extra_fields': extra_fields})
        self._log_to_cloudwatch(message, 'ERROR', extra_fields)
    
    def log_warning(self, message: str, extra_fields: Dict[str, Any] = None):
        """Log warning message"""
        extra_fields = extra_fields or {}
        extra_fields['event_type'] = 'warning'
        
        self.logger.warning(message, extra={'extra_fields': extra_fields})
        self._log_to_cloudwatch(message, 'WARNING', extra_fields)
    
    def log_info(self, message: str, extra_fields: Dict[str, Any] = None):
        """Log info message"""
        extra_fields = extra_fields or {}
        extra_fields['event_type'] = 'info'
        
        self.logger.info(message, extra={'extra_fields': extra_fields})
        self._log_to_cloudwatch(message, 'INFO', extra_fields)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current operation statistics"""
        return self.operation_stats.copy()

def create_sync_logger(operation_name: str, config: Dict[str, Any] = None) -> SyncLogger:
    """Factory function to create a sync logger"""
    return SyncLogger(operation_name, config) 