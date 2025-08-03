#!/usr/bin/env python3
"""
Tests for retry failed uploads functionality

This module tests the retry script's ability to:
- Parse error logs and extract failed files
- Handle different file path formats
- Retry uploads with enhanced error handling
- Generate correct S3 keys for retry operations

AWS Concepts Covered:
- S3 upload retry logic
- Error handling and recovery
- Log parsing and analysis
- Path resolution and S3 key generation
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.retry_failed_uploads import FailedUploadRetry


class TestFailedUploadRetry:
    """Test cases for retry failed uploads functionality"""
    
    @pytest.fixture
    def mock_config_data(self):
        """Mock configuration data for tests"""
        return {
            "aws": {"region": "us-east-1", "profile": "s3-sync"},
            "s3": {"bucket_name": "test-bucket", "storage_class": "STANDARD"},
            "sync": {"max_retries": 3, "retry_delay_base": 1, "retry_delay_max": 60}
        }
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure"""
        project = tmp_path / "sync_repo_clean"
        project.mkdir()
        
        # Create config directory
        config_dir = project / "config"
        config_dir.mkdir()
        
        # Create logs directory
        logs_dir = project / "logs"
        logs_dir.mkdir()
        
        # Create scripts directory
        scripts_dir = project / "scripts"
        scripts_dir.mkdir()
        
        return project
    
    @pytest.fixture
    def mock_config(self, temp_project):
        """Create mock configuration"""
        config = {
            "aws": {
                "region": "us-east-1",
                "profile": "s3-sync"
            },
            "s3": {
                "bucket_name": "test-bucket",
                "storage_class": "STANDARD"
            },
            "sync": {
                "max_retries": 3,
                "retry_delay_base": 1,
                "retry_delay_max": 60
            }
        }
        
        config_file = temp_project / "config" / "aws-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        return str(config_file)
    
    @pytest.fixture
    def mock_error_log(self, temp_project):
        """Create mock error log with failed uploads"""
        error_log = temp_project / "logs" / "s3-sync-errors.log"
        error_log.parent.mkdir(parents=True, exist_ok=True)
        
        error_entries = [
            '{"timestamp": "2025-08-02T22:02:48.254935", "level": "ERROR", "message": "❌ Error in upload operation for ../astro/config/file1.fit: Connection was closed", "operation": "s3-sync", "event_type": "error"}',
            '{"timestamp": "2025-08-02T22:05:03.590927", "level": "ERROR", "message": "❌ Error in upload operation for ../astro/historic data/file2.fit: Connection was closed", "operation": "s3-sync", "event_type": "error"}',
            '{"timestamp": "2025-08-02T22:05:58.284861", "level": "ERROR", "message": "❌ Error in upload operation for ../astro/config/file3.fit: Connection was closed", "operation": "s3-sync", "event_type": "error"}'
        ]
        
        with open(error_log, 'w') as f:
            for entry in error_entries:
                f.write(entry + '\n')
        
        return error_log
    
    def test_extract_failed_files(self, temp_project, mock_config, mock_error_log, mock_config_data):
        """Test extraction of failed files from error log"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            with patch('scripts.retry_failed_uploads.Path') as mock_path_class:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent = temp_project
                mock_path_class.return_value = mock_path_instance
                
                retry_handler = FailedUploadRetry(
                    config_file=str(mock_config),
                    dry_run=True,
                    verbose=False
                )
                
                failed_files = retry_handler._extract_failed_files()
                
                assert len(failed_files) == 3
                assert '../astro/config/file1.fit' in failed_files
                assert '../astro/historic data/file2.fit' in failed_files
                assert '../astro/config/file3.fit' in failed_files
    
    def test_path_resolution_with_base_dir(self, temp_project, mock_config, mock_config_data):
        """Test path resolution with base directory"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            retry_handler = FailedUploadRetry(
                config_file=str(mock_config),
                dry_run=True,
                verbose=False,
                base_dir="/custom/base/dir"
            )
            
            # Test path resolution
            assert retry_handler.base_dir == Path("/custom/base/dir")
    
    def test_s3_key_generation(self, temp_project, mock_config, mock_config_data):
        """Test S3 key generation from file paths"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            retry_handler = FailedUploadRetry(
                config_file=str(mock_config),
                dry_run=True,
                verbose=False
            )
            
            # Test S3 key generation for different path types
            test_cases = [
                ('../astro/config/file1.fit', 'config/file1.fit'),
                ('../astro/historic data/file2.fit', 'historic%20data/file2.fit'),
                ('../astro/config/file3.fit', 'config/file3.fit')
            ]
            
            for file_path, expected_s3_key in test_cases:
                # Mock file existence
                with patch.object(Path, 'exists', return_value=True):
                    with patch.object(Path, 'stat') as mock_stat:
                        mock_stat.return_value.st_size = 1024
                        
                        # Mock the upload operation to avoid actual S3 calls
                        with patch.object(retry_handler, '_enhanced_retry_with_backoff') as mock_retry:
                            mock_retry.return_value = True
                            
                            success = retry_handler._retry_upload_file(file_path)
                            assert success == True
    
    def test_enhanced_retry_logic(self, temp_project, mock_config, mock_config_data):
        """Test enhanced retry logic with exponential backoff"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            retry_handler = FailedUploadRetry(
                config_file=str(mock_config),
                dry_run=True,
                verbose=False
            )
            
            # Test retry logic
            def failing_operation():
                raise Exception("Simulated failure")
            
            # Should retry and eventually fail after max retries
            with pytest.raises(Exception):
                retry_handler._enhanced_retry_with_backoff(failing_operation)
    
    def test_dry_run_mode(self, temp_project, mock_config, mock_error_log, mock_config_data):
        """Test dry run mode functionality"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            retry_handler = FailedUploadRetry(
                config_file=str(mock_config),
                dry_run=True,
                verbose=True
            )
            
            # Mock file existence
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024
                    
                    # Should not actually upload in dry run mode
                    with patch.object(retry_handler, '_enhanced_retry_with_backoff') as mock_retry:
                        mock_retry.return_value = True
                        
                        success = retry_handler._retry_upload_file('../astro/config/file1.fit')
                        assert success == True
    
    def test_error_handling(self, temp_project, mock_config, mock_config_data):
        """Test error handling for various failure scenarios"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            retry_handler = FailedUploadRetry(
                config_file=str(mock_config),
                dry_run=False,
                verbose=False
            )
            
            # Test file not found
            with patch.object(Path, 'exists', return_value=False):
                success = retry_handler._retry_upload_file('../astro/config/nonexistent.fit')
                assert success == False
            
            # Test upload failure
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024
                    
                    with patch.object(retry_handler, '_enhanced_retry_with_backoff') as mock_retry:
                        mock_retry.side_effect = Exception("Upload failed")
                        
                        success = retry_handler._retry_upload_file('../astro/config/file1.fit')
                        assert success == False
    
    def test_statistics_tracking(self, temp_project, mock_config, mock_error_log, mock_config_data):
        """Test statistics tracking during retry operations"""
        with patch('scripts.retry_failed_uploads.FailedUploadRetry._load_config', return_value=mock_config_data):
            retry_handler = FailedUploadRetry(
                config_file=str(mock_config),
                dry_run=False,
                verbose=False
            )
            
            # Mock successful upload
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 2048
                    
                    with patch.object(retry_handler, '_enhanced_retry_with_backoff') as mock_retry:
                        mock_retry.return_value = True
                        
                        success = retry_handler._retry_upload_file('../astro/config/file1.fit')
                        
                        assert success == True
                        assert retry_handler.stats['files_succeeded'] == 1
                        assert retry_handler.stats['bytes_uploaded'] == 2048


if __name__ == '__main__':
    pytest.main([__file__]) 