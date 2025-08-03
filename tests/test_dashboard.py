#!/usr/bin/env python3
"""
Tests for the Dynamic Dashboard Module

This module tests the SyncDashboard functionality including:
- Dashboard initialization and configuration
- Progress tracking and updates
- File analysis and categorization
- Error handling and reporting
- Performance metrics calculation
- Rich display functionality (when available)

AWS Concepts Covered:
- Real-time monitoring and metrics testing
- Performance analytics validation
- File metadata analysis testing
- Progress visualization verification
"""

import pytest
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# Add the scripts directory to the path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

from dashboard import SyncDashboard, RICH_AVAILABLE


class TestSyncDashboard:
    """Test cases for SyncDashboard functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.config = {
            'dashboard': {
                'enabled': True,
                'refresh_rate': 2
            }
        }
        self.dashboard = SyncDashboard('test-operation', self.config)
    
    def teardown_method(self):
        """Cleanup after tests"""
        if self.dashboard.dashboard_active:
            self.dashboard.stop()
    
    def test_dashboard_initialization(self):
        """Test dashboard initialization"""
        assert self.dashboard.operation_name == 'test-operation'
        assert self.dashboard.config == self.config
        assert self.dashboard.dashboard_active == False
        assert self.dashboard.start_time is None
        assert self.dashboard.progress_data['total_files'] == 0
    
    def test_dashboard_start_stop(self):
        """Test dashboard start and stop functionality"""
        # Test start
        self.dashboard.start()
        assert self.dashboard.dashboard_active == True
        assert self.dashboard.start_time is not None
        
        # Test stop
        self.dashboard.stop()
        assert self.dashboard.dashboard_active == False
    
    def test_set_total_files(self):
        """Test setting total files count"""
        self.dashboard.set_total_files(100)
        assert self.dashboard.progress_data['total_files'] == 100
    
    def test_increment_counters(self):
        """Test incrementing various counters"""
        # Test processed
        self.dashboard.increment_processed()
        assert self.dashboard.progress_data['files_processed'] == 1
        
        # Test uploaded
        self.dashboard.increment_uploaded(1024 * 1024)  # 1MB
        assert self.dashboard.progress_data['files_uploaded'] == 1
        assert self.dashboard.progress_data['bytes_uploaded'] == 1024 * 1024
        
        # Test skipped
        self.dashboard.increment_skipped()
        assert self.dashboard.progress_data['files_skipped'] == 1
        
        # Test failed
        self.dashboard.increment_failed()
        assert self.dashboard.progress_data['files_failed'] == 1
    
    def test_update_progress_with_file_info(self):
        """Test updating progress with file information"""
        file_info = {
            'file_path': '/path/to/test.jpg',
            'file_size': 2048 * 1024,  # 2MB
            'file_name': 'test.jpg'
        }
        
        self.dashboard.update_progress(
            file_info=file_info,
            upload_speed=5.5,
            verification_status='passed'
        )
        
        # Check file type tracking
        assert '.jpg' in self.dashboard.progress_data['file_types']
        assert self.dashboard.progress_data['file_types']['.jpg'] == 1
        
        # Check file sizes
        assert len(self.dashboard.progress_data['file_sizes']) == 1
        assert self.dashboard.progress_data['file_sizes'][0] == 2048 * 1024
        
        # Check recent uploads
        assert len(self.dashboard.progress_data['recent_uploads']) == 1
        assert self.dashboard.progress_data['recent_uploads'][0]['name'] == 'test.jpg'
    
    def test_upload_speed_calculation(self):
        """Test upload speed tracking"""
        self.dashboard.update_progress(upload_speed=10.5)
        assert self.dashboard.progress_data['upload_speed_mbps'] == 10.5
        
        # Test average speed calculation
        self.dashboard.update_progress(upload_speed=15.0)
        assert self.dashboard.progress_data['average_speed_mbps'] == 12.75  # (10.5 + 15.0) / 2
    
    def test_verification_status_tracking(self):
        """Test verification status tracking"""
        self.dashboard.update_progress(verification_status='passed')
        assert self.dashboard.progress_data['verification_passed'] == 1
        
        self.dashboard.update_progress(verification_status='failed')
        assert self.dashboard.progress_data['verification_failed'] == 1
        
        self.dashboard.update_progress(verification_status='pending')
        assert self.dashboard.progress_data['verification_pending'] == 1
    
    def test_error_tracking(self):
        """Test error tracking functionality"""
        error = Exception("Test error")
        file_info = {'file_name': 'test.jpg'}
        
        self.dashboard.update_progress(error=error, file_info=file_info)
        
        assert len(self.dashboard.progress_data['errors']) == 1
        assert self.dashboard.progress_data['errors'][0]['error'] == "Test error"
        assert self.dashboard.progress_data['errors'][0]['file'] == 'test.jpg'
    
    def test_file_age_categorization(self):
        """Test file age categorization"""
        # Test today
        assert self.dashboard._categorize_file_age(0) == 'Today'
        assert self.dashboard._categorize_file_age(0.5) == 'Today'
        
        # Test this week
        assert self.dashboard._categorize_file_age(3) == 'This Week'
        assert self.dashboard._categorize_file_age(6) == 'This Week'
        
        # Test this month
        assert self.dashboard._categorize_file_age(15) == 'This Month'
        assert self.dashboard._categorize_file_age(29) == 'This Month'
        
        # Test last 3 months
        assert self.dashboard._categorize_file_age(45) == 'Last 3 Months'
        assert self.dashboard._categorize_file_age(89) == 'Last 3 Months'
        
        # Test last year
        assert self.dashboard._categorize_file_age(180) == 'Last Year'
        assert self.dashboard._categorize_file_age(364) == 'Last Year'
        
        # Test older
        assert self.dashboard._categorize_file_age(400) == 'Older'
        assert self.dashboard._categorize_file_age(1000) == 'Older'
    
    def test_recent_uploads_limiting(self):
        """Test that recent uploads list is limited"""
        # Add more than 10 uploads
        for i in range(15):
            file_info = {
                'file_path': f'/path/to/file{i}.jpg',
                'file_size': 1024 * 1024,
                'file_name': f'file{i}.jpg'
            }
            self.dashboard.update_progress(file_info=file_info)
        
        # Should only keep last 10
        assert len(self.dashboard.progress_data['recent_uploads']) == 10
        assert self.dashboard.progress_data['recent_uploads'][-1]['name'] == 'file14.jpg'
    
    def test_get_progress_summary(self):
        """Test getting progress summary"""
        # Set up some progress data
        self.dashboard.set_total_files(100)
        self.dashboard.increment_processed()
        self.dashboard.increment_uploaded(1024 * 1024)
        self.dashboard.increment_skipped()
        self.dashboard.increment_failed()
        
        summary = self.dashboard.get_progress_summary()
        
        assert summary['total_files'] == 100
        assert summary['files_processed'] == 1
        assert summary['files_uploaded'] == 1
        assert summary['files_skipped'] == 1
        assert summary['files_failed'] == 1
        assert summary['bytes_uploaded'] == 1024 * 1024
    
    def test_add_error_and_warning(self):
        """Test adding errors and warnings"""
        error = Exception("Test error")
        self.dashboard.add_error(error, "test.jpg")
        
        assert len(self.dashboard.progress_data['errors']) == 1
        assert self.dashboard.progress_data['errors'][0]['error'] == "Test error"
        assert self.dashboard.progress_data['errors'][0]['file'] == "test.jpg"
        
        self.dashboard.add_warning("Test warning")
        assert len(self.dashboard.progress_data['warnings']) == 1
        assert self.dashboard.progress_data['warnings'][0] == "Test warning"
    
    @patch('dashboard.RICH_AVAILABLE', False)
    def test_simple_progress_display(self):
        """Test simple progress display when rich is not available"""
        dashboard = SyncDashboard('test-simple')
        dashboard.start()
        
        # Set up some data
        dashboard.set_total_files(10)
        dashboard.increment_processed()
        dashboard.increment_uploaded(1024 * 1024)
        
        # This should not raise any exceptions
        dashboard.update_progress(upload_speed=5.5)
        dashboard.stop()
    
    def test_dashboard_with_real_file_info(self):
        """Test dashboard with realistic file information"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_file.write(b'test data')
            tmp_file_path = Path(tmp_file.name)
        
        try:
            file_info = {
                'file_path': str(tmp_file_path),
                'file_size': tmp_file_path.stat().st_size,
                'file_name': tmp_file_path.name
            }
            
            self.dashboard.update_progress(
                file_info=file_info,
                upload_speed=8.5,
                verification_status='passed'
            )
            
            # Check file type
            assert '.jpg' in self.dashboard.progress_data['file_types']
            
            # Check file size
            assert tmp_file_path.stat().st_size in self.dashboard.progress_data['file_sizes']
            
        finally:
            # Cleanup
            os.unlink(tmp_file_path)
    
    def test_concurrent_access(self):
        """Test thread safety of dashboard operations"""
        import threading
        
        def worker():
            for i in range(10):
                self.dashboard.increment_processed()
                self.dashboard.increment_uploaded(1024 * 1024)
                time.sleep(0.001)  # Small delay
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all operations were recorded
        assert self.dashboard.progress_data['files_processed'] == 50  # 5 threads * 10 iterations
        assert self.dashboard.progress_data['files_uploaded'] == 50
        assert self.dashboard.progress_data['bytes_uploaded'] == 50 * 1024 * 1024
    
    def test_dashboard_configuration(self):
        """Test dashboard with different configurations"""
        # Test with empty config
        dashboard = SyncDashboard('test-empty', {})
        assert dashboard.config == {}
        
        # Test with custom config
        custom_config = {
            'dashboard': {
                'refresh_rate': 5,
                'max_recent_uploads': 20
            }
        }
        dashboard = SyncDashboard('test-custom', custom_config)
        assert dashboard.config == custom_config
    
    def test_performance_metrics(self):
        """Test performance metrics tracking"""
        # Simulate some upload times
        upload_times = [2.5, 3.1, 1.8, 4.2, 2.9]
        
        for speed in upload_times:
            self.dashboard.update_progress(upload_speed=speed)
        
        # Check that upload times are tracked
        assert len(self.dashboard.progress_data['performance_metrics']['upload_times']) == 5
        
        # Check average calculation
        expected_avg = sum(upload_times) / len(upload_times)
        assert self.dashboard.progress_data['average_speed_mbps'] == expected_avg


class TestDashboardIntegration:
    """Test dashboard integration with sync operations"""
    
    def test_dashboard_creation(self):
        """Test dashboard creation function"""
        from dashboard import create_sync_dashboard
        
        dashboard = create_sync_dashboard('test-integration', {'test': 'config'})
        assert isinstance(dashboard, SyncDashboard)
        assert dashboard.operation_name == 'test-integration'
        assert dashboard.config == {'test': 'config'}


if __name__ == "__main__":
    pytest.main([__file__]) 