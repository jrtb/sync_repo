#!/usr/bin/env python3
"""
Sync Monitoring Module for AWS S3 Operations

This module provides comprehensive monitoring capabilities for sync operations,
including CloudWatch integration, performance metrics, and alerting systems.
Designed for AWS certification study with practical monitoring implementation.

AWS Concepts Covered:
- CloudWatch Metrics and Alarms
- CloudWatch Logs and Insights
- Performance monitoring and alerting
- Cost monitoring and optimization
- Operational dashboards and reporting
- S3 access logging and monitoring

Usage:
    from scripts.monitor import SyncMonitor
    monitor = SyncMonitor('sync-operation')
    monitor.start_monitoring()
    monitor.record_metric('FilesUploaded', 1, 'Count')
    monitor.create_alarm('HighErrorRate', 'ErrorRate', 'GreaterThanThreshold', 5)
    monitor.stop_monitoring()
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging

class SyncMonitor:
    """Comprehensive monitoring for sync operations with CloudWatch integration"""
    
    def __init__(self, operation_name: str, config: Dict[str, Any] = None):
        """Initialize sync monitor with configuration"""
        self.operation_name = operation_name
        self.config = config or {}
        self.project_root = Path(__file__).parent.parent
        
        # CloudWatch configuration
        self.cloudwatch_enabled = self.config.get('monitoring', {}).get('cloudwatch_enabled', True)
        self.namespace = self.config.get('monitoring', {}).get('namespace', 'S3Sync/Photos')
        self.log_group_name = self.config.get('monitoring', {}).get('log_group_name', '/aws/sync/photos')
        
        # Monitoring state
        self.monitoring_active = False
        self.start_time = None
        self.metrics_buffer = []
        self.alarms_created = []
        
        # Performance tracking
        self.operation_metrics = {
            'files_processed': 0,
            'files_uploaded': 0,
            'files_skipped': 0,
            'files_failed': 0,
            'bytes_uploaded': 0,
            'errors': [],
            'warnings': [],
            'performance_data': []
        }
        
        # Setup monitoring infrastructure
        self._setup_monitoring()
        
        # Initialize CloudWatch if enabled
        if self.cloudwatch_enabled:
            self._setup_cloudwatch()
    
    def _setup_monitoring(self):
        """Setup monitoring infrastructure"""
        # Create logs directory
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger(f"monitor.{self.operation_name}")
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        log_file = log_dir / f"monitor-{self.operation_name}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_formatter)
        self.logger.addHandler(file_handler)
    
    def _setup_cloudwatch(self):
        """Setup CloudWatch clients and configuration"""
        try:
            self.cloudwatch = boto3.client('cloudwatch')
            self.logs = boto3.client('logs')
            self.logger.info("CloudWatch monitoring enabled")
        except (NoCredentialsError, ClientError) as e:
            self.logger.warning(f"CloudWatch setup failed: {e}")
            self.cloudwatch_enabled = False
    
    def start_monitoring(self):
        """Start monitoring session"""
        self.monitoring_active = True
        self.start_time = datetime.now()
        self.logger.info(f"Started monitoring session: {self.operation_name}")
        
        # Create CloudWatch log stream if enabled
        if self.cloudwatch_enabled:
            self._create_log_stream()
    
    def stop_monitoring(self):
        """Stop monitoring session and flush metrics"""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        duration = datetime.now() - self.start_time
        
        # Flush remaining metrics
        self._flush_metrics()
        
        # Generate final report
        self._generate_monitoring_report(duration)
        
        self.logger.info(f"Stopped monitoring session: {self.operation_name}")
    
    def record_metric(self, metric_name: str, value: float, unit: str = 'Count', 
                     dimensions: List[Dict[str, str]] = None):
        """Record a custom metric"""
        if not self.monitoring_active:
            return
        
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': datetime.now(),
            'Dimensions': dimensions or []
        }
        
        self.metrics_buffer.append(metric_data)
        
        # Flush if buffer is full
        if len(self.metrics_buffer) >= 20:
            self._flush_metrics()
    
    def record_performance_data(self, operation: str, duration: float, 
                              file_size: int = None, success: bool = True):
        """Record performance data for operations"""
        if not self.monitoring_active:
            return
        
        performance_entry = {
            'operation': operation,
            'duration': duration,
            'file_size': file_size,
            'success': success,
            'timestamp': datetime.now()
        }
        
        self.operation_metrics['performance_data'].append(performance_entry)
        
        # Record CloudWatch metric
        self.record_metric(f'{operation}Duration', duration, 'Seconds')
        if file_size:
            self.record_metric(f'{operation}Size', file_size, 'Bytes')
    
    def record_error(self, error: Exception, context: str = None):
        """Record an error for monitoring"""
        error_entry = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': datetime.now()
        }
        
        self.operation_metrics['errors'].append(error_entry)
        self.logger.error(f"Error recorded: {error_entry}")
        
        # Record error metric
        self.record_metric('Errors', 1, 'Count')
    
    def record_warning(self, message: str, context: str = None):
        """Record a warning for monitoring"""
        warning_entry = {
            'message': message,
            'context': context,
            'timestamp': datetime.now()
        }
        
        self.operation_metrics['warnings'].append(warning_entry)
        self.logger.warning(f"Warning recorded: {warning_entry}")
        
        # Record warning metric
        self.record_metric('Warnings', 1, 'Count')
    
    def create_alarm(self, alarm_name: str, metric_name: str, comparison_operator: str,
                    threshold: float, evaluation_periods: int = 2, period: int = 300):
        """Create a CloudWatch alarm"""
        if not self.cloudwatch_enabled:
            self.logger.warning("CloudWatch not enabled, cannot create alarm")
            return
        
        try:
            alarm_config = {
                'AlarmName': f"{self.operation_name}-{alarm_name}",
                'AlarmDescription': f"Alarm for {metric_name} in {self.operation_name}",
                'MetricName': metric_name,
                'Namespace': self.namespace,
                'ComparisonOperator': comparison_operator,
                'Threshold': threshold,
                'EvaluationPeriods': evaluation_periods,
                'Period': period,
                'Statistic': 'Average',
                'ActionsEnabled': True
            }
            
            # Add dimensions if available
            if hasattr(self, 'bucket_name'):
                alarm_config['Dimensions'] = [
                    {'Name': 'BucketName', 'Value': self.bucket_name}
                ]
            
            self.cloudwatch.put_metric_alarm(**alarm_config)
            self.alarms_created.append(alarm_name)
            self.logger.info(f"Created alarm: {alarm_name}")
            
        except ClientError as e:
            self.logger.error(f"Failed to create alarm {alarm_name}: {e}")
    
    def _create_log_stream(self):
        """Create CloudWatch log stream"""
        try:
            # Create log group if it doesn't exist
            try:
                self.logs.create_log_group(logGroupName=self.log_group_name)
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
            
            # Create log stream
            stream_name = f"{self.operation_name}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
            try:
                self.logs.create_log_stream(
                    logGroupName=self.log_group_name,
                    logStreamName=stream_name
                )
                self.current_log_stream = stream_name
                self.logger.info(f"Created CloudWatch log stream: {stream_name}")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    self.logger.error(f"Failed to create log stream: {e}")
                else:
                    # Stream already exists, use it
                    self.current_log_stream = stream_name
                    self.logger.info(f"Using existing CloudWatch log stream: {stream_name}")
            
        except ClientError as e:
            self.logger.error(f"Failed to create log stream: {e}")
    
    def _flush_metrics(self):
        """Flush metrics to CloudWatch"""
        if not self.cloudwatch_enabled or not self.metrics_buffer:
            return
        
        try:
            # Prepare metrics for CloudWatch
            cloudwatch_metrics = []
            for metric in self.metrics_buffer:
                cloudwatch_metric = {
                    'MetricName': metric['MetricName'],
                    'Value': metric['Value'],
                    'Unit': metric['Unit'],
                    'Timestamp': metric['Timestamp']
                }
                
                if metric['Dimensions']:
                    cloudwatch_metric['Dimensions'] = metric['Dimensions']
                
                cloudwatch_metrics.append(cloudwatch_metric)
            
            # Send metrics to CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=cloudwatch_metrics
            )
            
            self.logger.debug(f"Flushed {len(self.metrics_buffer)} metrics to CloudWatch")
            self.metrics_buffer.clear()
            
        except ClientError as e:
            self.logger.error(f"Failed to flush metrics to CloudWatch: {e}")
    
    def _generate_monitoring_report(self, duration: timedelta):
        """Generate monitoring report"""
        total_files = (self.operation_metrics['files_uploaded'] + 
                      self.operation_metrics['files_skipped'] + 
                      self.operation_metrics['files_failed'])
        
        success_rate = 0
        if total_files > 0:
            success_rate = (self.operation_metrics['files_uploaded'] / total_files) * 100
        
        throughput = 0
        if duration.total_seconds() > 0:
            throughput = self.operation_metrics['bytes_uploaded'] / duration.total_seconds()
        
        report = {
            'operation_name': self.operation_name,
            'duration': str(duration),
            'files_processed': total_files,
            'files_uploaded': self.operation_metrics['files_uploaded'],
            'files_skipped': self.operation_metrics['files_skipped'],
            'files_failed': self.operation_metrics['files_failed'],
            'bytes_uploaded': self.operation_metrics['bytes_uploaded'],
            'success_rate': f"{success_rate:.2f}%",
            'throughput_mbps': f"{throughput / (1024 * 1024):.2f}",
            'errors_count': len(self.operation_metrics['errors']),
            'warnings_count': len(self.operation_metrics['warnings']),
            'alarms_created': len(self.alarms_created)
        }
        
        # Save report to file
        report_file = self.project_root / "logs" / f"monitor-report-{self.operation_name}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Monitoring report saved to: {report_file}")
        
        # Print summary
        self._print_monitoring_summary(report)
    
    def _print_monitoring_summary(self, report: Dict[str, Any]):
        """Print monitoring summary"""
        print("\n" + "="*60)
        print("MONITORING SUMMARY")
        print("="*60)
        print(f"Operation: {report['operation_name']}")
        print(f"Duration: {report['duration']}")
        print(f"Files Processed: {report['files_processed']}")
        print(f"Files Uploaded: {report['files_uploaded']}")
        print(f"Files Skipped: {report['files_skipped']}")
        print(f"Files Failed: {report['files_failed']}")
        print(f"Success Rate: {report['success_rate']}")
        print(f"Throughput: {report['throughput_mbps']} MB/s")
        print(f"Bytes Uploaded: {report['bytes_uploaded']:,}")
        print(f"Errors: {report['errors_count']}")
        print(f"Warnings: {report['warnings_count']}")
        print(f"Alarms Created: {report['alarms_created']}")
        print("="*60)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        return {
            'operation_name': self.operation_name,
            'monitoring_active': self.monitoring_active,
            'start_time': self.start_time,
            'metrics_buffer_size': len(self.metrics_buffer),
            'operation_metrics': self.operation_metrics.copy(),
            'alarms_created': self.alarms_created.copy()
        }


def create_sync_monitor(operation_name: str, config: Dict[str, Any] = None) -> SyncMonitor:
    """Factory function to create a sync monitor"""
    return SyncMonitor(operation_name, config)


if __name__ == "__main__":
    """Test the monitoring functionality"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test sync monitoring")
    parser.add_argument("--operation", default="test-monitor", help="Operation name")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = SyncMonitor(args.operation)
    monitor.start_monitoring()
    
    # Simulate some operations
    for i in range(5):
        monitor.record_metric('TestMetric', i, 'Count')
        monitor.record_performance_data('TestOperation', 1.5, 1024*1024, True)
        time.sleep(1)
    
    # Create a test alarm
    monitor.create_alarm('TestAlarm', 'TestMetric', 'GreaterThanThreshold', 3)
    
    # Stop monitoring
    monitor.stop_monitoring() 