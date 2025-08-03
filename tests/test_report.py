#!/usr/bin/env python3
"""
Tests for Sync Reporting Module

This module tests the comprehensive reporting capabilities for sync operations,
including sync history reports, cost analysis, storage usage, and performance analytics.
Designed for AWS certification study with practical testing implementation.

AWS Concepts Covered:
- S3 Analytics and Inventory testing
- CloudWatch Metrics and Insights validation
- Cost and Usage Reports testing
- Storage class optimization reporting validation
- Performance analytics and trends testing
- Operational reporting and dashboards validation

Usage:
    python -m pytest tests/test_report.py -v
    python -m pytest tests/test_report.py::test_reporter_initialization -v
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

from report import SyncReporter, create_sync_reporter


class TestSyncReporter:
    """Test cases for SyncReporter class"""
    
    @pytest.fixture
    def temp_project_root(self):
        """Create temporary project root for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create necessary directories
            (temp_path / "logs").mkdir(exist_ok=True)
            (temp_path / "reports").mkdir(exist_ok=True)
            (temp_path / "config").mkdir(exist_ok=True)
            
            yield temp_path
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        return {
            'reporting': {
                's3_enabled': True,
                'cloudwatch_enabled': True,
                'reports_dir': 'reports'
            }
        }
    
    @pytest.fixture
    def reporter(self, temp_project_root, mock_config):
        """Create a test reporter instance"""
        with patch('report.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            return SyncReporter('test-operation', mock_config)
    
    def test_reporter_initialization(self, reporter):
        """Test reporter initialization"""
        assert reporter.operation_name == 'test-operation'
        assert reporter.s3_enabled is True
        assert reporter.cloudwatch_enabled is True
        assert reporter.reports_dir == 'reports'
        assert len(reporter.reports_generated) == 0
        assert len(reporter.report_data) == 0
    
    def test_reporter_initialization_without_config(self, temp_project_root):
        """Test reporter initialization without config"""
        with patch('report.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            reporter = SyncReporter('test-operation')
            
            assert reporter.operation_name == 'test-operation'
            assert reporter.s3_enabled is True  # Default value
            assert reporter.cloudwatch_enabled is True  # Default value
            assert reporter.reports_dir == 'reports'  # Default value
    
    def test_reporter_initialization_aws_disabled(self, temp_project_root):
        """Test reporter initialization with AWS disabled"""
        config = {
            'reporting': {
                's3_enabled': False,
                'cloudwatch_enabled': False
            }
        }
        
        with patch('report.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            reporter = SyncReporter('test-operation', config)
            
            assert reporter.s3_enabled is False
            assert reporter.cloudwatch_enabled is False
    
    @patch('report.boto3.client')
    def test_aws_clients_setup_success(self, mock_boto3_client, reporter):
        """Test successful AWS clients setup"""
        mock_s3 = Mock()
        mock_cloudwatch = Mock()
        mock_boto3_client.side_effect = [mock_s3, mock_cloudwatch]
        
        reporter._setup_aws_clients()
        
        assert reporter.s3 == mock_s3
        assert reporter.cloudwatch == mock_cloudwatch
        assert reporter.s3_enabled is True
        assert reporter.cloudwatch_enabled is True
    
    @patch('report.boto3.client')
    def test_aws_clients_setup_no_credentials(self, mock_boto3_client, reporter):
        """Test AWS clients setup with no credentials"""
        mock_boto3_client.side_effect = NoCredentialsError()
        
        reporter._setup_aws_clients()
        
        assert reporter.s3_enabled is False
        assert reporter.cloudwatch_enabled is False
    
    @patch('report.boto3.client')
    def test_aws_clients_setup_client_error(self, mock_boto3_client, reporter):
        """Test AWS clients setup with client error"""
        mock_boto3_client.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'DescribeBuckets'
        )
        
        reporter._setup_aws_clients()
        
        assert reporter.s3_enabled is False
        assert reporter.cloudwatch_enabled is False
    
    def test_generate_sync_history_report(self, reporter, temp_project_root):
        """Test sync history report generation"""
        # Create some test log files
        log_dir = temp_project_root / "logs"
        test_log_file = log_dir / "sync-test.log"
        with open(test_log_file, 'w') as f:
            f.write("2025-08-02 10:00:00 - sync.test-operation - INFO - Started sync operation\n")
        
        report = reporter.generate_sync_history_report(30)
        
        assert report['report_type'] == 'sync_history'
        assert report['operation_name'] == 'test-operation'
        assert report['period_days'] == 30
        assert 'summary' in report
        assert 'sync_history' in report
        assert 'trends' in report
        
        # Check if report file was created
        reports_dir = temp_project_root / "reports"
        report_files = list(reports_dir.glob("sync_history_*.json"))
        assert len(report_files) == 1
    
    def test_generate_cost_analysis_report(self, reporter, temp_project_root):
        """Test cost analysis report generation"""
        report = reporter.generate_cost_analysis_report(30, 'test-bucket')
        
        assert report['report_type'] == 'cost_analysis'
        assert report['operation_name'] == 'test-operation'
        assert report['period_days'] == 30
        assert report['bucket_name'] == 'test-bucket'
        assert 'summary' in report
        assert 'cost_breakdown' in report
        assert 'storage_class_costs' in report
        assert 'recommendations' in report
        
        # Check if report file was created
        reports_dir = temp_project_root / "reports"
        report_files = list(reports_dir.glob("cost_analysis_*.json"))
        assert len(report_files) == 1
    
    def test_generate_storage_usage_report(self, reporter, temp_project_root):
        """Test storage usage report generation"""
        report = reporter.generate_storage_usage_report('test-bucket')
        
        assert report['report_type'] == 'storage_usage'
        assert report['operation_name'] == 'test-operation'
        assert report['bucket_name'] == 'test-bucket'
        assert 'summary' in report
        assert 'storage_details' in report
        assert 'optimization_opportunities' in report
        
        # Check if report file was created
        reports_dir = temp_project_root / "reports"
        report_files = list(reports_dir.glob("storage_usage_*.json"))
        assert len(report_files) == 1
    
    def test_generate_performance_report(self, reporter, temp_project_root):
        """Test performance report generation"""
        # Create some test monitor log files
        log_dir = temp_project_root / "logs"
        test_log_file = log_dir / "monitor-test.log"
        with open(test_log_file, 'w') as f:
            f.write("2025-08-02 10:00:00 - monitor.test-operation - INFO - Throughput: 15.5 MB/s\n")
            f.write("2025-08-02 10:00:00 - monitor.test-operation - INFO - Latency: 250 ms\n")
        
        report = reporter.generate_performance_report(30)
        
        assert report['report_type'] == 'performance_analytics'
        assert report['operation_name'] == 'test-operation'
        assert report['period_days'] == 30
        assert 'summary' in report
        assert 'performance_metrics' in report
        assert 'bottlenecks' in report
        assert 'recommendations' in report
        
        # Check if report file was created
        reports_dir = temp_project_root / "reports"
        report_files = list(reports_dir.glob("performance_analytics_*.json"))
        assert len(report_files) == 1
    
    @patch('report.boto3.client')
    def test_collect_cost_data_with_bucket(self, mock_boto3_client, reporter):
        """Test cost data collection with bucket"""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Size': 1024*1024*100},  # 100MB
                {'Size': 1024*1024*50},   # 50MB
            ]
        }
        mock_boto3_client.return_value = mock_s3
        
        reporter._setup_aws_clients()
        cost_data = reporter._collect_cost_data(30, 'test-bucket')
        
        assert cost_data['total_cost'] > 0
        assert cost_data['storage_cost'] > 0
        assert cost_data['transfer_cost'] > 0
        assert cost_data['request_cost'] > 0
        assert cost_data['cost_per_gb'] > 0
    
    def test_collect_cost_data_without_bucket(self, reporter):
        """Test cost data collection without bucket"""
        cost_data = reporter._collect_cost_data(30)
        
        assert cost_data['total_cost'] == 0
        assert cost_data['storage_cost'] == 0
        assert cost_data['transfer_cost'] == 0
        assert cost_data['request_cost'] == 0
        assert cost_data['cost_per_gb'] == 0
    
    @patch('report.boto3.client')
    def test_collect_storage_data_with_bucket(self, mock_boto3_client, reporter):
        """Test storage data collection with bucket"""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Size': 1024*1024, 'StorageClass': 'STANDARD'},      # 1MB
                {'Size': 10*1024*1024, 'StorageClass': 'STANDARD_IA'}, # 10MB
                {'Size': 100*1024*1024, 'StorageClass': 'GLACIER'},    # 100MB
            ]
        }
        mock_boto3_client.return_value = mock_s3
        
        reporter._setup_aws_clients()
        storage_data = reporter._collect_storage_data('test-bucket')
        
        assert storage_data['total_objects'] == 3
        assert storage_data['total_size_bytes'] == 111*1024*1024
        assert storage_data['total_size_gb'] > 0
        assert 'STANDARD' in storage_data['storage_classes']
        assert 'STANDARD_IA' in storage_data['storage_classes']
        assert 'GLACIER' in storage_data['storage_classes']
        assert 'medium' in storage_data['size_distribution']
        assert 'large' in storage_data['size_distribution']
    
    def test_collect_storage_data_without_bucket(self, reporter):
        """Test storage data collection without bucket"""
        storage_data = reporter._collect_storage_data()
        
        assert storage_data['total_objects'] == 0
        assert storage_data['total_size_bytes'] == 0
        assert storage_data['total_size_gb'] == 0
        assert len(storage_data['storage_classes']) == 0
        assert len(storage_data['size_distribution']) == 0
    
    def test_parse_sync_log(self, reporter, temp_project_root):
        """Test sync log parsing"""
        # Create test log file
        log_dir = temp_project_root / "logs"
        test_log_file = log_dir / "sync-test.log"
        with open(test_log_file, 'w') as f:
            f.write("2025-08-02 10:00:00 - sync.test-operation - INFO - Started sync operation\n")
            f.write("2025-08-02 10:01:00 - sync.test-operation - INFO - Sync completed\n")
        
        history_data = reporter._parse_sync_log(test_log_file, 30)
        
        assert len(history_data) > 0
    
    def test_parse_performance_log(self, reporter, temp_project_root):
        """Test performance log parsing"""
        # Create test log file
        log_dir = temp_project_root / "logs"
        test_log_file = log_dir / "monitor-test.log"
        with open(test_log_file, 'w') as f:
            f.write("2025-08-02 10:00:00 - monitor.test-operation - INFO - Throughput: 15.5 MB/s\n")
            f.write("2025-08-02 10:00:00 - monitor.test-operation - INFO - Latency: 250 ms\n")
            f.write("2025-08-02 10:01:00 - monitor.test-operation - INFO - Throughput: 20.1 MB/s\n")
            f.write("2025-08-02 10:01:00 - monitor.test-operation - INFO - Latency: 180 ms\n")
        
        performance_data = reporter._parse_performance_log(test_log_file, 30)
        
        assert performance_data['average_throughput_mbps'] > 0
        assert performance_data['peak_throughput_mbps'] > 0
        assert performance_data['average_latency_ms'] > 0
    
    def test_calculate_average_duration(self, reporter):
        """Test average duration calculation"""
        history_data = [
            {'duration': 10.5},
            {'duration': 15.2},
            {'duration': 8.7},
            {'duration': 12.1}
        ]
        
        avg_duration = reporter._calculate_average_duration(history_data)
        expected_avg = (10.5 + 15.2 + 8.7 + 12.1) / 4
        
        assert avg_duration == expected_avg
    
    def test_calculate_average_duration_empty(self, reporter):
        """Test average duration calculation with empty data"""
        history_data = []
        
        avg_duration = reporter._calculate_average_duration(history_data)
        
        assert avg_duration == 0
    
    def test_analyze_sync_trends(self, reporter):
        """Test sync trends analysis"""
        history_data = [
            {'timestamp': datetime.now(), 'files_processed': 10, 'bytes_uploaded': 1024*1024},
            {'timestamp': datetime.now() - timedelta(days=1), 'files_processed': 5, 'bytes_uploaded': 512*1024},
            {'timestamp': datetime.now() - timedelta(days=2), 'files_processed': 15, 'bytes_uploaded': 2048*1024}
        ]
        
        trends = reporter._analyze_sync_trends(history_data)
        
        assert 'daily_syncs' in trends
        assert 'total_days' in trends
        assert 'average_daily_syncs' in trends
        assert trends['total_days'] > 0
        assert trends['average_daily_syncs'] > 0
    
    def test_analyze_sync_trends_empty(self, reporter):
        """Test sync trends analysis with empty data"""
        history_data = []
        
        trends = reporter._analyze_sync_trends(history_data)
        
        assert trends == {}
    
    def test_generate_cost_recommendations(self, reporter):
        """Test cost recommendations generation"""
        # High storage cost scenario
        cost_data = {
            'storage_cost': 200,
            'transfer_cost': 50,
            'cost_per_gb': 0.08,
            'total_cost': 300
        }
        
        recommendations = reporter._generate_cost_recommendations(cost_data)
        
        assert len(recommendations) > 0
        assert any('Intelligent-Tiering' in rec for rec in recommendations)
        assert any('lifecycle policies' in rec for rec in recommendations)
    
    def test_identify_optimization_opportunities(self, reporter):
        """Test optimization opportunities identification"""
        storage_data = {
            'size_distribution': {
                'large': 150,
                'xlarge': 50
            },
            'storage_classes': {
                'STANDARD': 1000,
                'STANDARD_IA': 50
            }
        }
        
        opportunities = reporter._identify_optimization_opportunities(storage_data)
        
        assert len(opportunities) > 0
        assert any('compression' in opp for opp in opportunities)
        assert any('STANDARD_IA' in opp for opp in opportunities)
    
    def test_generate_performance_recommendations(self, reporter):
        """Test performance recommendations generation"""
        # Low performance scenario
        performance_data = {
            'average_throughput_mbps': 5,
            'average_latency_ms': 1500,
            'error_rate_percent': 8
        }
        
        recommendations = reporter._generate_performance_recommendations(performance_data)
        
        assert len(recommendations) > 0
        assert any('multipart uploads' in rec for rec in recommendations)
        assert any('Direct Connect' in rec for rec in recommendations)
        assert any('retry logic' in rec for rec in recommendations)
    
    def test_save_report(self, reporter, temp_project_root):
        """Test report saving"""
        report_data = {
            'test_key': 'test_value',
            'timestamp': datetime.now()
        }
        
        reporter._save_report('test_report', report_data)
        
        # Check if report was saved
        assert len(reporter.reports_generated) == 1
        assert 'test_report' in reporter.report_data
        assert reporter.report_data['test_report'] == report_data
        
        # Check if file was created
        reports_dir = temp_project_root / "reports"
        report_files = list(reports_dir.glob("test_report_*.json"))
        assert len(report_files) == 1
    
    def test_export_report_to_csv(self, reporter, temp_project_root):
        """Test CSV export functionality"""
        # First generate a report
        report_data = {
            'sync_history': [
                {'timestamp': '2025-08-02', 'operation': 'sync', 'success': True, 'files_processed': 10, 'bytes_uploaded': 1024*1024}
            ]
        }
        reporter.report_data['sync_history'] = report_data
        
        reporter.export_report_to_csv('sync_history')
        
        # Check if CSV file was created
        reports_dir = temp_project_root / "reports"
        csv_files = list(reports_dir.glob("sync_history_*.csv"))
        assert len(csv_files) == 1
    
    def test_export_report_to_csv_not_found(self, reporter):
        """Test CSV export with non-existent report"""
        reporter.export_report_to_csv('non_existent_report')
        
        # Should not create any files
        assert len(reporter.reports_generated) == 0
    
    def test_create_sync_reporter_factory(self, temp_project_root, mock_config):
        """Test factory function for creating sync reporter"""
        with patch('report.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            reporter = create_sync_reporter('test-operation', mock_config)
            
            assert isinstance(reporter, SyncReporter)
            assert reporter.operation_name == 'test-operation'
            assert reporter.config == mock_config


class TestReporterIntegration:
    """Integration tests for reporting functionality"""
    
    @pytest.fixture
    def temp_project_root(self):
        """Create temporary project root for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create necessary directories
            (temp_path / "logs").mkdir(exist_ok=True)
            (temp_path / "reports").mkdir(exist_ok=True)
            (temp_path / "config").mkdir(exist_ok=True)
            
            yield temp_path
    
    def test_full_reporting_cycle(self, temp_project_root):
        """Test complete reporting cycle"""
        with patch('report.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            
            # Create reporter
            reporter = SyncReporter('integration-test')
            
            # Generate all types of reports
            sync_report = reporter.generate_sync_history_report(30)
            cost_report = reporter.generate_cost_analysis_report(30, 'test-bucket')
            storage_report = reporter.generate_storage_usage_report('test-bucket')
            performance_report = reporter.generate_performance_report(30)
            
            # Verify reports were generated
            assert sync_report['report_type'] == 'sync_history'
            assert cost_report['report_type'] == 'cost_analysis'
            assert storage_report['report_type'] == 'storage_usage'
            assert performance_report['report_type'] == 'performance_analytics'
            
            # Verify files were created
            reports_dir = temp_project_root / "reports"
            json_files = list(reports_dir.glob("*.json"))
            assert len(json_files) == 4
    
    def test_reporter_with_real_logging(self, temp_project_root):
        """Test reporter with actual logging functionality"""
        with patch('report.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_project_root
            
            # Create some test log files
            log_dir = temp_project_root / "logs"
            sync_log = log_dir / "sync-test.log"
            monitor_log = log_dir / "monitor-test.log"
            
            with open(sync_log, 'w') as f:
                f.write("2025-08-02 10:00:00 - sync.test-operation - INFO - Started sync operation\n")
            
            with open(monitor_log, 'w') as f:
                f.write("2025-08-02 10:00:00 - monitor.test-operation - INFO - Throughput: 15.5 MB/s\n")
                f.write("2025-08-02 10:00:00 - monitor.test-operation - INFO - Latency: 250 ms\n")
            
            reporter = SyncReporter('logging-test')
            
            # Generate reports
            sync_report = reporter.generate_sync_history_report(30)
            performance_report = reporter.generate_performance_report(30)
            
            # Verify reports were generated
            assert sync_report['report_type'] == 'sync_history'
            assert performance_report['report_type'] == 'performance_analytics'
            
            # Check if log files were created
            log_files = list(log_dir.glob("reporter-*.log"))
            assert len(log_files) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 