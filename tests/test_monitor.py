#!/usr/bin/env python3
"""
Tests for Sync Monitoring Module

This module tests the comprehensive monitoring capabilities for sync operations,
including CloudWatch integration, performance metrics, and alerting systems.
Designed for AWS certification study with practical testing implementation.

AWS Concepts Covered:
- CloudWatch Metrics and Alarms testing
- Performance monitoring validation
- Error handling and edge cases
- Configuration management testing
- Integration testing with AWS services

Usage:
    python -m pytest tests/test_monitor.py -v
    python -m pytest tests/test_monitor.py::test_monitor_initialization -v
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from monitor import SyncMonitor, create_sync_monitor


class TestSyncMonitor:
    """Test cases for SyncMonitor class"""
    
    @pytest.fixture
    def temp_project_root(self):
        """Create temporary project root for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create necessary directories
            (temp_path / "logs").mkdir(exist_ok=True)
            (temp_path / "config").mkdir(exist_ok=True)
            
            yield temp_path
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        return {
            'monitoring': {
                'cloudwatch_enabled': True,
                'namespace': 'S3Sync/Photos/Test',
                'log_group_name': '/aws/sync/photos/test'
            }
        }
    
    @pytest.fixture
    def monitor(self, temp_project_root, mock_config):
        """Create a test monitor instance"""
        with patch('monitor.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            return SyncMonitor('test-operation', mock_config)
    
    def test_monitor_initialization(self, monitor):
        """Test monitor initialization"""
        assert monitor.operation_name == 'test-operation'
        assert monitor.cloudwatch_enabled is True
        assert monitor.namespace == 'S3Sync/Photos/Test'
        assert monitor.log_group_name == '/aws/sync/photos/test'
        assert monitor.monitoring_active is False
        assert monitor.start_time is None
        assert len(monitor.metrics_buffer) == 0
        assert len(monitor.alarms_created) == 0
    
    def test_monitor_initialization_without_config(self, temp_project_root):
        """Test monitor initialization without config"""
        with patch('monitor.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            monitor = SyncMonitor('test-operation')
            
            assert monitor.operation_name == 'test-operation'
            assert monitor.cloudwatch_enabled is True  # Default value
            assert monitor.namespace == 'S3Sync/Photos'  # Default value
            assert monitor.log_group_name == '/aws/sync/photos'  # Default value
    
    def test_monitor_initialization_cloudwatch_disabled(self, temp_project_root):
        """Test monitor initialization with CloudWatch disabled"""
        config = {
            'monitoring': {
                'cloudwatch_enabled': False
            }
        }
        
        with patch('monitor.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            monitor = SyncMonitor('test-operation', config)
            
            assert monitor.cloudwatch_enabled is False
    
    @patch('monitor.boto3.client')
    def test_cloudwatch_setup_success(self, mock_boto3_client, monitor):
        """Test successful CloudWatch setup"""
        mock_cloudwatch = Mock()
        mock_logs = Mock()
        mock_boto3_client.side_effect = [mock_cloudwatch, mock_logs]
        
        monitor._setup_cloudwatch()
        
        assert monitor.cloudwatch == mock_cloudwatch
        assert monitor.logs == mock_logs
        assert monitor.cloudwatch_enabled is True
    
    @patch('monitor.boto3.client')
    def test_cloudwatch_setup_no_credentials(self, mock_boto3_client, monitor):
        """Test CloudWatch setup with no credentials"""
        mock_boto3_client.side_effect = NoCredentialsError()
        
        monitor._setup_cloudwatch()
        
        assert monitor.cloudwatch_enabled is False
    
    @patch('monitor.boto3.client')
    def test_cloudwatch_setup_client_error(self, mock_boto3_client, monitor):
        """Test CloudWatch setup with client error"""
        mock_boto3_client.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'DescribeLogGroups'
        )
        
        monitor._setup_cloudwatch()
        
        assert monitor.cloudwatch_enabled is False
    
    def test_start_monitoring(self, monitor):
        """Test starting monitoring session"""
        monitor.start_monitoring()
        
        assert monitor.monitoring_active is True
        assert monitor.start_time is not None
        assert isinstance(monitor.start_time, datetime)
    
    def test_stop_monitoring_not_active(self, monitor):
        """Test stopping monitoring when not active"""
        # Don't start monitoring
        monitor.stop_monitoring()
        
        assert monitor.monitoring_active is False
        assert monitor.start_time is None
    
    def test_stop_monitoring_active(self, monitor):
        """Test stopping active monitoring session"""
        monitor.start_monitoring()
        time.sleep(0.1)  # Small delay to ensure different timestamps
        
        monitor.stop_monitoring()
        
        assert monitor.monitoring_active is False
        assert monitor.start_time is not None
    
    def test_record_metric_not_active(self, monitor):
        """Test recording metric when monitoring not active"""
        monitor.record_metric('TestMetric', 1.0, 'Count')
        
        assert len(monitor.metrics_buffer) == 0
    
    def test_record_metric_active(self, monitor):
        """Test recording metric when monitoring active"""
        monitor.start_monitoring()
        monitor.record_metric('TestMetric', 1.0, 'Count')
        
        assert len(monitor.metrics_buffer) == 1
        assert monitor.metrics_buffer[0]['MetricName'] == 'TestMetric'
        assert monitor.metrics_buffer[0]['Value'] == 1.0
        assert monitor.metrics_buffer[0]['Unit'] == 'Count'
    
    def test_record_metric_with_dimensions(self, monitor):
        """Test recording metric with dimensions"""
        monitor.start_monitoring()
        dimensions = [{'Name': 'TestDim', 'Value': 'TestValue'}]
        monitor.record_metric('TestMetric', 1.0, 'Count', dimensions)
        
        assert len(monitor.metrics_buffer) == 1
        assert monitor.metrics_buffer[0]['Dimensions'] == dimensions
    
    def test_record_performance_data(self, monitor):
        """Test recording performance data"""
        monitor.start_monitoring()
        monitor.record_performance_data('TestOperation', 1.5, 1024*1024, True)
        
        assert len(monitor.operation_metrics['performance_data']) == 1
        performance_entry = monitor.operation_metrics['performance_data'][0]
        assert performance_entry['operation'] == 'TestOperation'
        assert performance_entry['duration'] == 1.5
        assert performance_entry['file_size'] == 1024*1024
        assert performance_entry['success'] is True
    
    def test_record_error(self, monitor):
        """Test recording error"""
        monitor.start_monitoring()
        test_error = ValueError("Test error message")
        monitor.record_error(test_error, "test context")
        
        assert len(monitor.operation_metrics['errors']) == 1
        error_entry = monitor.operation_metrics['errors'][0]
        assert error_entry['error_type'] == 'ValueError'
        assert error_entry['error_message'] == "Test error message"
        assert error_entry['context'] == "test context"
    
    def test_record_warning(self, monitor):
        """Test recording warning"""
        monitor.start_monitoring()
        monitor.record_warning("Test warning", "test context")
        
        assert len(monitor.operation_metrics['warnings']) == 1
        warning_entry = monitor.operation_metrics['warnings'][0]
        assert warning_entry['message'] == "Test warning"
        assert warning_entry['context'] == "test context"
    
    @patch('monitor.boto3.client')
    def test_create_alarm_success(self, mock_boto3_client, monitor):
        """Test successful alarm creation"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        monitor._setup_cloudwatch()
        monitor.start_monitoring()
        monitor.create_alarm('TestAlarm', 'TestMetric', 'GreaterThanThreshold', 5.0)
        
        # Verify alarm was created
        mock_cloudwatch.put_metric_alarm.assert_called_once()
        call_args = mock_cloudwatch.put_metric_alarm.call_args[1]
        assert call_args['AlarmName'] == 'test-operation-TestAlarm'
        assert call_args['MetricName'] == 'TestMetric'
        assert call_args['ComparisonOperator'] == 'GreaterThanThreshold'
        assert call_args['Threshold'] == 5.0
        assert len(monitor.alarms_created) == 1
        assert 'TestAlarm' in monitor.alarms_created
    
    def test_create_alarm_cloudwatch_disabled(self, monitor):
        """Test alarm creation when CloudWatch disabled"""
        monitor.cloudwatch_enabled = False
        monitor.start_monitoring()
        monitor.create_alarm('TestAlarm', 'TestMetric', 'GreaterThanThreshold', 5.0)
        
        assert len(monitor.alarms_created) == 0
    
    @patch('monitor.boto3.client')
    def test_create_alarm_client_error(self, mock_boto3_client, monitor):
        """Test alarm creation with client error"""
        mock_cloudwatch = Mock()
        mock_cloudwatch.put_metric_alarm.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutMetricAlarm'
        )
        mock_boto3_client.return_value = mock_cloudwatch
        
        monitor._setup_cloudwatch()
        monitor.start_monitoring()
        monitor.create_alarm('TestAlarm', 'TestMetric', 'GreaterThanThreshold', 5.0)
        
        assert len(monitor.alarms_created) == 0
    
    @patch('monitor.boto3.client')
    def test_flush_metrics_success(self, mock_boto3_client, monitor):
        """Test successful metrics flush"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        monitor._setup_cloudwatch()
        monitor.start_monitoring()
        
        # Add some metrics
        monitor.record_metric('TestMetric1', 1.0, 'Count')
        monitor.record_metric('TestMetric2', 2.0, 'Count')
        
        monitor._flush_metrics()
        
        # Verify metrics were sent to CloudWatch
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        assert call_args['Namespace'] == 'S3Sync/Photos/Test'
        assert len(call_args['MetricData']) == 2
        
        # Verify buffer was cleared
        assert len(monitor.metrics_buffer) == 0
    
    @patch('monitor.boto3.client')
    def test_flush_metrics_client_error(self, mock_boto3_client, monitor):
        """Test metrics flush with client error"""
        mock_cloudwatch = Mock()
        mock_cloudwatch.put_metric_data.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutMetricData'
        )
        mock_boto3_client.return_value = mock_cloudwatch
        
        monitor._setup_cloudwatch()
        monitor.start_monitoring()
        
        # Add some metrics
        monitor.record_metric('TestMetric', 1.0, 'Count')
        
        monitor._flush_metrics()
        
        # Verify buffer was not cleared (metrics preserved)
        assert len(monitor.metrics_buffer) == 1
    
    def test_flush_metrics_cloudwatch_disabled(self, monitor):
        """Test metrics flush when CloudWatch disabled"""
        monitor.cloudwatch_enabled = False
        monitor.start_monitoring()
        
        # Add some metrics
        monitor.record_metric('TestMetric', 1.0, 'Count')
        
        monitor._flush_metrics()
        
        # Verify buffer was not cleared (metrics preserved)
        assert len(monitor.metrics_buffer) == 1
    
    def test_auto_flush_on_buffer_full(self, monitor):
        """Test automatic flush when buffer is full"""
        monitor.start_monitoring()
        
        # Add 20 metrics to trigger auto-flush
        for i in range(20):
            monitor.record_metric(f'TestMetric{i}', i, 'Count')
        
        # Buffer should be empty after auto-flush
        assert len(monitor.metrics_buffer) == 0
    
    def test_generate_monitoring_report(self, monitor, temp_project_root):
        """Test monitoring report generation"""
        monitor.start_monitoring()
        
        # Simulate some operations
        monitor.operation_metrics['files_uploaded'] = 10
        monitor.operation_metrics['files_skipped'] = 2
        monitor.operation_metrics['files_failed'] = 1
        monitor.operation_metrics['bytes_uploaded'] = 1024*1024*10  # 10MB
        monitor.alarms_created = ['TestAlarm1', 'TestAlarm2']
        
        duration = timedelta(seconds=60)
        monitor._generate_monitoring_report(duration)
        
        # Check if report file was created
        report_file = temp_project_root / "logs" / "monitor-report-test-operation.json"
        assert report_file.exists()
        
        # Verify report content
        with open(report_file, 'r') as f:
            report = json.load(f)
        
        assert report['operation_name'] == 'test-operation'
        assert report['files_uploaded'] == 10
        assert report['files_skipped'] == 2
        assert report['files_failed'] == 1
        assert report['bytes_uploaded'] == 1024*1024*10
        assert report['alarms_created'] == 2
    
    def test_get_metrics_summary(self, monitor):
        """Test getting metrics summary"""
        monitor.start_monitoring()
        monitor.record_metric('TestMetric', 1.0, 'Count')
        monitor.operation_metrics['files_uploaded'] = 5
        
        summary = monitor.get_metrics_summary()
        
        assert summary['operation_name'] == 'test-operation'
        assert summary['monitoring_active'] is True
        assert summary['start_time'] is not None
        assert summary['metrics_buffer_size'] == 1
        assert summary['operation_metrics']['files_uploaded'] == 5
        assert isinstance(summary['alarms_created'], list)
    
    def test_create_sync_monitor_factory(self, temp_project_root, mock_config):
        """Test factory function for creating sync monitor"""
        with patch('monitor.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            monitor = create_sync_monitor('test-operation', mock_config)
            
            assert isinstance(monitor, SyncMonitor)
            assert monitor.operation_name == 'test-operation'
            assert monitor.config == mock_config


class TestMonitorIntegration:
    """Integration tests for monitoring functionality"""
    
    @pytest.fixture
    def temp_project_root(self):
        """Create temporary project root for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create necessary directories
            (temp_path / "logs").mkdir(exist_ok=True)
            (temp_path / "config").mkdir(exist_ok=True)
            
            yield temp_path
    
    def test_full_monitoring_cycle(self, temp_project_root):
        """Test complete monitoring cycle"""
        with patch('monitor.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            
            # Create monitor
            monitor = SyncMonitor('integration-test')
            
            # Start monitoring
            monitor.start_monitoring()
            assert monitor.monitoring_active is True
            
            # Record various metrics and data
            monitor.record_metric('FilesUploaded', 5, 'Count')
            monitor.record_performance_data('FileUpload', 2.5, 1024*1024, True)
            monitor.record_error(ValueError("Test error"), "upload context")
            monitor.record_warning("Test warning", "performance context")
            
            # Update operation metrics
            monitor.operation_metrics['files_uploaded'] = 5
            monitor.operation_metrics['files_skipped'] = 1
            monitor.operation_metrics['bytes_uploaded'] = 1024*1024*5
            
            # Stop monitoring
            monitor.stop_monitoring()
            assert monitor.monitoring_active is False
            
            # Verify report was generated
            report_file = temp_project_root / "logs" / "monitor-report-integration-test.json"
            assert report_file.exists()
    
    def test_monitor_with_real_logging(self, temp_project_root):
        """Test monitor with actual logging functionality"""
        with patch('monitor.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            
            monitor = SyncMonitor('logging-test')
            monitor.start_monitoring()
            
            # This should create log files
            monitor.record_metric('TestMetric', 1.0, 'Count')
            monitor.stop_monitoring()
            
            # Check if log file was created
            log_file = temp_project_root / "logs" / "monitor-logging-test.log"
            assert log_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 