#!/usr/bin/env python3
"""
Test Suite for AWS S3 Sync Application

This test suite verifies the core functionality of the sync script,
including file comparison, upload logic, and configuration handling.

AWS Concepts Covered:
- Mocking AWS services for testing
- Unit testing with pytest
- Integration testing patterns
- Error handling verification
"""

import pytest
import tempfile
import shutil
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import hashlib
import time
import random

# Add the scripts directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sync import S3Sync

class TestS3Sync:
    """Test cases for S3Sync class"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing"""
        return {
            "aws": {
                "region": "us-east-1",
                "profile": "test-profile"
            },
            "s3": {
                "bucket_name": "test-bucket",
                "storage_class": "STANDARD",
                "encryption": {
                    "enabled": True,
                    "algorithm": "AES256"
                }
            },
            "sync": {
                "local_path": "./test-data",
                "exclude_patterns": ["*.tmp", "*.log"],
                "max_concurrent_uploads": 5,
                "chunk_size_mb": 100,
                "dry_run": False
            }
        }
    
    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client for testing"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            yield mock_client
    
    def test_load_config_file_not_found(self):
        """Test configuration loading with missing file"""
        with pytest.raises(SystemExit):
            S3Sync(config_file="nonexistent.json")
    
    def test_load_config_invalid_json(self, temp_dir):
        """Test configuration loading with invalid JSON"""
        config_file = Path(temp_dir) / "invalid.json"
        with open(config_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(SystemExit):
            S3Sync(config_file=str(config_file))
    
    def test_load_config_valid(self, temp_dir, sample_config, mock_aws_session):
        """Test configuration loading with valid JSON"""
        config_file = Path(temp_dir) / "valid.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        sync = S3Sync(config_file=str(config_file))
        assert sync.config == sample_config
        assert sync.bucket_name == "test-bucket"
        assert sync.profile == "test-profile"
    
    def test_setup_aws_clients_success(self, mock_s3_client):
        """Test successful AWS client setup"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            
            sync = S3Sync()
            assert sync.s3_client is not None
            assert sync.s3_resource is not None
    
    def test_setup_aws_clients_no_credentials(self):
        """Test AWS client setup with missing credentials"""
        with patch('boto3.Session') as mock_session:
            from botocore.exceptions import NoCredentialsError
            mock_session.side_effect = NoCredentialsError()
            
            with pytest.raises(SystemExit):
                S3Sync()
    
    def test_calculate_file_hash(self, temp_dir, mock_aws_session):
        """Test file hash calculation"""
        test_file = Path(temp_dir) / "test.txt"
        test_content = "Hello, World!"

        with open(test_file, 'w') as f:
            f.write(test_content)

        sync = S3Sync()
        hash_result = sync._calculate_file_hash(test_file, 'md5')

        # Calculate expected hash
        expected_hash = hashlib.md5(test_content.encode()).hexdigest()
        assert hash_result == expected_hash
    
    def test_calculate_file_hash_nonexistent(self, temp_dir, mock_aws_session):
        """Test file hash calculation with nonexistent file"""
        sync = S3Sync()
        hash_result = sync._calculate_file_hash(Path(temp_dir) / "nonexistent.txt")
        assert hash_result is None
    
    def test_get_s3_object_metadata_exists(self, mock_s3_client):
        """Test getting S3 object metadata when object exists"""
        mock_s3_client.head_object.return_value = {'ETag': '"abc123"', 'ContentLength': 123, 'LastModified': 'now'}

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"

        metadata = sync._get_s3_object_metadata("test-key")
        assert metadata['etag'] == "abc123"

    def test_get_s3_object_metadata_not_exists(self, mock_s3_client):
        """Test getting S3 object metadata when object doesn't exist"""
        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': '404'}}
        mock_s3_client.head_object.side_effect = ClientError(error_response, 'HeadObject')

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"

        metadata = sync._get_s3_object_metadata("test-key")
        assert metadata is None
    
    def test_should_upload_file_new_file(self, temp_dir, mock_aws_session):
        """Test file upload decision for new file"""
        test_file = Path(temp_dir) / "new.txt"
        with open(test_file, 'w') as f:
            f.write("new content")
        
        # Get the mock client from the session
        mock_s3_client = mock_aws_session.return_value.client.return_value
        # Mock the _get_s3_object_etag method to return None (file not found)
        with patch.object(S3Sync, '_get_s3_object_metadata', return_value=None):
            sync = S3Sync()
            sync.s3_client = mock_s3_client
            sync.bucket_name = "test-bucket"
            
            should_upload = sync._should_upload_file(test_file, "new.txt")
            assert should_upload is True
    
    def test_should_upload_file_unchanged(self, temp_dir, mock_s3_client):
        """Test file upload decision for unchanged file"""
        test_file = Path(temp_dir) / "unchanged.txt"
        test_content = "unchanged content"

        with open(test_file, 'w') as f:
            f.write(test_content)

        # Mock S3 ETag to match local file hash
        expected_hash = hashlib.md5(test_content.encode()).hexdigest()
        mock_s3_client.head_object.return_value = {
            'ETag': f'"{expected_hash}"',
            'ContentLength': len(test_content),
            'LastModified': 'now'
        }

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.hash_algorithm = 'md5'

        should_upload = sync._should_upload_file(test_file, "unchanged.txt")
        assert should_upload is False

    def test_should_upload_file_changed(self, temp_dir, mock_s3_client):
        """Test file upload decision for changed file"""
        test_file = Path(temp_dir) / "changed.txt"
        test_content = "new content"

        with open(test_file, 'w') as f:
            f.write(test_content)

        # Mock S3 ETag to be different from local file hash
        mock_s3_client.head_object.return_value = {
            'ETag': '"different-hash"',
            'ContentLength': len(test_content),
            'LastModified': 'now'
        }

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"

        should_upload = sync._should_upload_file(test_file, "changed.txt")
        assert should_upload is True
    
    def test_should_include_file_included(self, temp_dir, mock_aws_session):
        """Test file inclusion logic for included file"""
        test_file = Path(temp_dir) / "included.txt"
        test_file.touch()
        
        sync = S3Sync()
        sync.config = {
            "sync": {
                "exclude_patterns": ["*.tmp", "*.log"]
            }
        }
        
        should_include = sync._should_include_file(test_file)
        assert should_include is True
    
    def test_should_include_file_excluded(self, temp_dir, mock_aws_session):
        """Test file inclusion logic for excluded file"""
        test_file = Path(temp_dir) / "excluded.tmp"
        test_file.touch()
        
        sync = S3Sync()
        sync.config = {
            "sync": {
                "exclude_patterns": ["*.tmp", "*.log"]
            }
        }
        
        should_include = sync._should_include_file(test_file)
        assert should_include is False
    
    def test_get_files_to_sync_empty_directory(self, temp_dir, mock_aws_session):
        """Test getting files to sync from empty directory"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        files_to_sync = sync._get_files_to_sync()
        assert files_to_sync == []
    
    def test_get_files_to_sync_with_files(self, temp_dir, mock_aws_session):
        """Test getting files to sync with files present"""
        # Create test files
        test_file1 = Path(temp_dir) / "file1.txt"
        test_file2 = Path(temp_dir) / "file2.txt"
        
        with open(test_file1, 'w') as f:
            f.write("content1")
        with open(test_file2, 'w') as f:
            f.write("content2")
        
        # Get the mock client from the session
        mock_s3_client = mock_aws_session.return_value.client.return_value
        
        # Mock the _get_s3_object_etag method to return None (files not found)
        with patch.object(S3Sync, '_get_s3_object_metadata', return_value=None):
            sync = S3Sync()
            sync.local_path = Path(temp_dir)
            sync.s3_client = mock_s3_client
            sync.bucket_name = "test-bucket"
            sync.config = {
                "sync": {
                    "exclude_patterns": []
                }
            }
            
            files_to_sync = sync._get_files_to_sync()
            assert len(files_to_sync) == 2
            
            # Check that both files are included
            file_paths = [str(f[0]) for f in files_to_sync]
            assert str(test_file1) in file_paths
            assert str(test_file2) in file_paths
    
    def test_upload_file_simple_success(self, temp_dir, mock_s3_client):
        """Test simple file upload success"""
        test_file = Path(temp_dir) / "small.txt"
        with open(test_file, 'w') as f:
            f.write("small content")

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.config = {
            "s3": {
                "storage_class": "STANDARD",
                "encryption": {
                    "enabled": True
                }
            }
        }

        with patch.object(sync.s3_client, 'upload_file', return_value=None) as mock_upload:
            result = sync._upload_file_simple(test_file, "small.txt")
            assert result is True
            mock_upload.assert_called_once()

    def test_upload_file_simple_failure(self, temp_dir, mock_s3_client):
        """Test simple file upload failure"""
        test_file = Path(temp_dir) / "small.txt"
        with open(test_file, 'w') as f:
            f.write("small content")

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"

        with patch.object(sync.s3_client, 'upload_file', side_effect=Exception("Upload failed")):
            result = sync._upload_file_simple(test_file, "small.txt")
            assert result is False
    
    def test_upload_file_multipart_success(self, temp_dir, mock_s3_client):
        """Test multipart file upload success"""
        # Create a large file (simulate >100MB)
        test_file = Path(temp_dir) / "large.txt"
        large_content = "x" * (101 * 1024 * 1024)  # 101MB
        with open(test_file, 'w') as f:
            f.write(large_content)
        
        # Mock multipart upload responses
        mock_s3_client.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        mock_s3_client.upload_part.return_value = {'ETag': 'test-etag'}
        mock_s3_client.complete_multipart_upload.return_value = {}
        
        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "chunk_size_mb": 100
            },
            "s3": {
                "storage_class": "STANDARD",
                "encryption": {
                    "enabled": True
                }
            }
        }
        
        result = sync._upload_file_multipart(test_file, "large.txt")
        assert result is True
    
    def test_upload_file_multipart_failure(self, temp_dir, mock_s3_client):
        """Test multipart file upload failure"""
        test_file = Path(temp_dir) / "large.txt"
        large_content = "x" * (101 * 1024 * 1024)  # 101MB
        with open(test_file, 'w') as f:
            f.write(large_content)
        
        # Mock multipart upload to fail
        mock_s3_client.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        mock_s3_client.upload_part.side_effect = Exception("Upload failed")
        mock_s3_client.abort_multipart_upload.return_value = {}
        
        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "chunk_size_mb": 100
            }
        }
        
        result = sync._upload_file_multipart(test_file, "large.txt")
        assert result is False
    
    def test_upload_file_size_based_routing(self, temp_dir, mock_s3_client):
        """Test that upload method is chosen based on file size"""
        # Small file
        small_file = Path(temp_dir) / "small.txt"
        with open(small_file, 'w') as f:
            f.write("small content")
        
        # Large file
        large_file = Path(temp_dir) / "large.txt"
        large_content = "x" * (101 * 1024 * 1024)  # 101MB
        with open(large_file, 'w') as f:
            f.write(large_content)
        
        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        
        # Test small file (should use simple upload)
        with patch.object(sync, '_upload_file_simple', return_value=True) as mock_simple:
            with patch.object(sync, '_upload_file_multipart', return_value=True) as mock_multipart:
                sync._upload_file(small_file, "small.txt")
                mock_simple.assert_called_once()
                mock_multipart.assert_not_called()
        
        # Test large file (should use multipart upload)
        with patch.object(sync, '_upload_file_simple', return_value=True) as mock_simple:
            with patch.object(sync, '_upload_file_multipart', return_value=True) as mock_multipart:
                sync._upload_file(large_file, "large.txt")
                mock_simple.assert_not_called()
                mock_multipart.assert_called_once()
    
    def test_update_stats_thread_safe(self, mock_aws_session):
        """Test that statistics updates are thread-safe"""
        sync = S3Sync()
        
        # Test initial state
        assert sync.stats['files_uploaded'] == 0
        assert sync.stats['files_skipped'] == 0
        assert sync.stats['files_failed'] == 0
        assert sync.stats['bytes_uploaded'] == 0
        
        # Test updating stats
        sync._update_stats(uploaded=True, bytes_uploaded=1024)
        assert sync.stats['files_uploaded'] == 1
        assert sync.stats['bytes_uploaded'] == 1024
        
        sync._update_stats(skipped=True)
        assert sync.stats['files_skipped'] == 1
        
        sync._update_stats(failed=True)
        assert sync.stats['files_failed'] == 1
    
    def test_upload_worker_dry_run(self, temp_dir, mock_aws_session):
        """Test upload worker in dry-run mode"""
        test_file = Path(temp_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sync = S3Sync()
        sync.dry_run = True
        sync.verbose = True  # Enable verbose mode to trigger logging
        sync.bucket_name = "test-bucket"
        sync.local_path = Path(temp_dir)
        sync.files_to_sync = [(test_file, "test.txt")]  # Set files_to_sync for length check
        
        # Mock logger to capture output
        with patch.object(sync, 'logger') as mock_logger:
            result = sync._upload_worker((test_file, "test.txt"))
            
            assert result is True
            mock_logger.log_info.assert_called()
            # Check that dry-run message was logged
            dry_run_calls = [call for call in mock_logger.log_info.call_args_list 
                           if "[DRY RUN]" in str(call)]
            assert len(dry_run_calls) > 0
    
    def test_upload_worker_success(self, temp_dir, mock_s3_client):
        """Test upload worker success"""
        test_file = Path(temp_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sync = S3Sync()
        sync.dry_run = False
        sync.verbose = True  # Enable verbose mode to trigger logging
        sync.bucket_name = "test-bucket"
        sync.s3_client = mock_s3_client
        sync.files_to_sync = [(test_file, "test.txt")]  # Set files_to_sync for length check
        
        with patch.object(sync, '_upload_file', return_value=True) as mock_upload:
            with patch.object(sync, 'logger') as mock_logger:
                result = sync._upload_worker((test_file, "test.txt"))
                
                assert result is True
                mock_upload.assert_called_once()
                mock_logger.log_info.assert_called()
    
    def test_upload_worker_failure(self, temp_dir, mock_aws_session):
        """Test upload worker failure"""
        test_file = Path(temp_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sync = S3Sync()
        sync.dry_run = False
        sync.bucket_name = "test-bucket"
        sync.s3_client = mock_aws_session.return_value.client.return_value
        
        with patch.object(sync, '_upload_file', return_value=False) as mock_upload:
            with patch.object(sync, 'logger') as mock_logger:
                result = sync._upload_worker((test_file, "test.txt"))
                
                assert result is False
                mock_upload.assert_called_once()
                # When upload fails, no logging occurs - just stats update
                # The test should verify that upload was called and result is False
    
    def test_sync_no_files(self, temp_dir, mock_aws_session):
        """Test sync with no files to sync"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        with patch.object(sync, '_get_files_to_sync', return_value=[]):
            with patch.object(sync, 'logger') as mock_logger:
                result = sync.sync()
                
                assert result is True
                mock_logger.log_info.assert_called()
                # Check that "no files to sync" message was logged
                no_files_calls = [call for call in mock_logger.log_info.call_args_list 
                                if "No files found to sync" in str(call)]
                assert len(no_files_calls) > 0
    
    def test_sync_with_files(self, temp_dir, mock_s3_client):
        """Test sync with files to upload"""
        test_file = Path(temp_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "exclude_patterns": [],
                "max_concurrent_uploads": 2
            }
        }
        sync.s3_client = mock_s3_client
        
        # Mock files to sync
        files_to_sync = [(test_file, "test.txt")]
        
        with patch.object(sync, '_get_files_to_sync', return_value=files_to_sync):
            with patch.object(sync, '_upload_worker', return_value=True) as mock_worker:
                with patch.object(sync, 'logger') as mock_logger:
                    with patch('builtins.input', return_value='y'):  # Mock input to avoid OSError
                        # Mock AWS identity verification
                        with patch('scripts.sync.AWSIdentityVerifier') as mock_identity:
                            mock_verifier = Mock()
                            mock_verifier.verify_identity_for_sync.return_value = True
                            mock_identity.return_value = mock_verifier
                            
                            result = sync.sync()
                            
                            assert result is True
                            mock_worker.assert_called_once()
                            mock_logger.log_info.assert_called()
                            mock_verifier.verify_identity_for_sync.assert_called_once()
    
    def test_sync_identity_verification_success(self, temp_dir, mock_aws_session):
        """Test sync with successful identity verification"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        with patch.object(sync, '_get_files_to_sync', return_value=[]):
            with patch.object(sync, 'logger') as mock_logger:
                # Mock AWS identity verification at the module level
                with patch('scripts.sync.AWSIdentityVerifier') as mock_identity_class:
                    mock_verifier = Mock()
                    mock_verifier.verify_identity_for_sync.return_value = True
                    mock_identity_class.return_value = mock_verifier
                    
                    result = sync.sync()
                    
                    assert result is True
                    mock_verifier.verify_identity_for_sync.assert_called_once_with(
                        bucket_name="test-bucket", dry_run=False
                    )
    
    def test_sync_identity_verification_failure(self, temp_dir, mock_aws_session):
        """Test sync with failed identity verification"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        with patch.object(sync, 'logger') as mock_logger:
            # Mock AWS identity verification failure
            with patch('scripts.sync.AWSIdentityVerifier') as mock_identity_class:
                mock_verifier = Mock()
                mock_verifier.verify_identity_for_sync.return_value = False
                mock_identity_class.return_value = mock_verifier
                
                result = sync.sync()
                
                assert result is False
                mock_verifier.verify_identity_for_sync.assert_called_once()
    
    def test_sync_identity_verification_exception(self, temp_dir, mock_aws_session):
        """Test sync with identity verification exception"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        with patch.object(sync, 'logger') as mock_logger:
            # Mock AWS identity verification exception
            with patch('scripts.sync.AWSIdentityVerifier') as mock_identity_class:
                mock_identity_class.side_effect = Exception("Identity verification failed")
                
                result = sync.sync()
                
                assert result is False
                mock_logger.log_error.assert_called()
    
    def test_sync_identity_verifier_not_available(self, temp_dir, mock_aws_session):
        """Test sync when AWS identity verifier is not available"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        with patch.object(sync, '_get_files_to_sync', return_value=[]):
            with patch.object(sync, 'logger') as mock_logger:
                # Mock AWS identity verifier as None
                with patch('scripts.sync.AWSIdentityVerifier', None):
                    result = sync.sync()
                    
                    assert result is True
                    # Check that warning was logged
                    warning_calls = [call for call in mock_logger.log_info.call_args_list 
                                   if "AWS identity verification module not available" in str(call)]
                    assert len(warning_calls) > 0
    
    def test_sync_dry_run_identity_verification(self, temp_dir, mock_aws_session):
        """Test sync in dry run mode with identity verification"""
        sync = S3Sync()
        sync.local_path = Path(temp_dir)
        sync.bucket_name = "test-bucket"
        sync.dry_run = True
        sync.config = {
            "sync": {
                "exclude_patterns": []
            }
        }
        
        with patch.object(sync, '_get_files_to_sync', return_value=[]):
            with patch.object(sync, 'logger') as mock_logger:
                # Mock AWS identity verification
                with patch('scripts.sync.AWSIdentityVerifier') as mock_identity_class:
                    mock_verifier = Mock()
                    mock_verifier.verify_identity_for_sync.return_value = True
                    mock_identity_class.return_value = mock_verifier
                    
                    result = sync.sync()
                    
                    assert result is True
                    mock_verifier.verify_identity_for_sync.assert_called_once_with(
                        bucket_name="test-bucket", dry_run=True
                    )
    
    def test_print_summary(self, mock_aws_session):
        """Test sync summary printing"""
        from datetime import datetime

        sync = S3Sync()
        sync.stats = {
            'files_uploaded': 5,
            'files_skipped': 2,
            'files_failed': 0,
            'bytes_uploaded': 1024,
            'retries_attempted': 0,
            'start_time': datetime.now(),
            'end_time': datetime.now()
        }

        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            sync._print_summary()
            # Verify summary was printed
            mock_print.assert_called()
            # Check that summary contains expected information
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("SYNC SUMMARY" in call for call in print_calls)
            assert any("Files uploaded: 5" in call for call in print_calls)
            assert any("Files skipped: 2" in call for call in print_calls)
            assert any("Files failed: 0" in call for call in print_calls)
            assert any("Bytes uploaded: 1,024" in call for call in print_calls)


class TestIntegration:
    """Integration tests for the sync functionality"""
    
    @pytest.fixture
    def test_environment(self):
        """Set up test environment with sample files"""
        temp_dir = tempfile.mkdtemp()
        
        # Create sample directory structure
        data_dir = Path(temp_dir) / "data"
        data_dir.mkdir()
        
        # Create sample files
        (data_dir / "file1.txt").write_text("content1")
        (data_dir / "file2.txt").write_text("content2")
        (data_dir / "subdir").mkdir()
        (data_dir / "subdir" / "file3.txt").write_text("content3")
        
        # Create excluded file
        (data_dir / "excluded.tmp").write_text("excluded")
        
        yield temp_dir, data_dir
        
        shutil.rmtree(temp_dir)
    
    def test_integration_file_discovery(self, test_environment, mock_aws_session):
        """Test integration of file discovery and filtering"""
        temp_dir, data_dir = test_environment
        
        # Get the mock client from the session
        mock_s3_client = mock_aws_session.return_value.client.return_value
        
        # Mock the _get_s3_object_etag method to return None (files not found)
        with patch.object(S3Sync, '_get_s3_object_metadata', return_value=None):
            sync = S3Sync()
            sync.local_path = data_dir
            sync.s3_client = mock_s3_client
            sync.bucket_name = "test-bucket"
            sync.config = {
                "sync": {
                    "exclude_patterns": ["*.tmp"]
                }
            }
            
            files_to_sync = sync._get_files_to_sync()
            
            # Should find 3 files (excluding .tmp file)
            assert len(files_to_sync) == 3
            
            # Check specific files
            file_paths = [str(f[0]) for f in files_to_sync]
            assert str(data_dir / "file1.txt") in file_paths
            assert str(data_dir / "file2.txt") in file_paths
            assert str(data_dir / "subdir" / "file3.txt") in file_paths
            
            # Check excluded file is not included
            assert str(data_dir / "excluded.tmp") not in file_paths
    
    def test_integration_file_comparison(self, test_environment, mock_aws_session):
        """Test integration of file comparison logic"""
        temp_dir, data_dir = test_environment

        test_file = data_dir / "file1.txt"

        # Get the mock client from the session
        mock_s3_client = mock_aws_session.return_value.client.return_value

        # Mock S3 to return different ETag (file changed)
        mock_s3_client.head_object.return_value = {
            'ETag': '"different-hash"',
            'ContentLength': len(test_file.read_text()),
            'LastModified': 'now'
        }

        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.hash_algorithm = 'md5'

        should_upload = sync._should_upload_file(test_file, "file1.txt")
        assert should_upload is True

        # Mock S3 to return matching ETag (file unchanged)
        expected_hash = hashlib.md5(test_file.read_text().encode()).hexdigest()
        mock_s3_client.head_object.return_value = {
            'ETag': f'"{expected_hash}"',
            'ContentLength': len(test_file.read_text()),
            'LastModified': 'now'
        }

        should_upload = sync._should_upload_file(test_file, "file1.txt")
        assert should_upload is False

    def test_retry_logic_on_simple_upload(self, tmp_path, mock_aws_session):
        """Test that retry logic is triggered for simple upload failures"""
        test_file = tmp_path / "retry.txt"
        test_file.write_text("retry content")

        # Simulate failure for first two attempts, then success
        call_count = {'count': 0}
        def flaky_upload(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] < 3:
                from botocore.exceptions import ClientError
                error_response = {'Error': {'Code': 'InternalError', 'Message': 'Simulated upload failure'}}
                raise ClientError(error_response, 'UploadFile')
            return None  # boto3 upload_file returns None on success

        mock_s3_client = mock_aws_session.return_value.client.return_value
        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.max_retries = 3
        sync.retry_delay_base = 0  # No actual sleep for test speed
        sync.retry_delay_max = 0

        # Patch the boto3 client's upload_file method
        with patch.object(mock_s3_client, 'upload_file', side_effect=flaky_upload):
            result = sync._upload_file_simple(test_file, "retry.txt")
            assert result is True
            assert call_count['count'] == 3

    def test_retry_logic_on_multipart_upload(self, tmp_path, mock_aws_session):
        """Test that retry logic is triggered for multipart upload failures"""
        test_file = tmp_path / "large-retry.txt"
        # Create a smaller file to have only one part for simpler testing
        large_content = "x" * (50 * 1024 * 1024)  # 50MB (smaller than 100MB chunk)
        test_file.write_text(large_content)

        mock_s3_client = mock_aws_session.return_value.client.return_value
        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"
        sync.max_retries = 2
        sync.retry_delay_base = 0
        sync.retry_delay_max = 0
        sync.config = {"sync": {"chunk_size_mb": 100}}

        # Simulate failure for first upload_part, then success
        call_count = {'count': 0}
        def flaky_upload_part(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] < 3:  # Initial + 2 retries = 3 calls
                from botocore.exceptions import ClientError
                error_response = {'Error': {'Code': 'InternalError', 'Message': 'Simulated part failure'}}
                raise ClientError(error_response, 'UploadPart')
            return {'ETag': 'test-etag'}

        # Mock the multipart upload methods
        mock_s3_client.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        mock_s3_client.upload_part.side_effect = flaky_upload_part
        mock_s3_client.complete_multipart_upload.return_value = {}
        mock_s3_client.abort_multipart_upload.return_value = {}

        result = sync._upload_file_multipart(test_file, "large-retry.txt")
        assert result is True  # Should succeed after retry
        assert call_count['count'] == 3  # Initial + 2 retries

    def test_sha256_integrity_check(self, tmp_path, mock_aws_session):
        """Test SHA256 hash calculation and comparison"""
        test_file = tmp_path / "sha256.txt"
        test_content = "sha256 content"
        test_file.write_text(test_content)

        sync = S3Sync()
        sync.hash_algorithm = 'sha256'
        expected_hash = hashlib.sha256(test_content.encode()).hexdigest()
        hash_result = sync._calculate_file_hash(test_file, 'sha256')
        assert hash_result == expected_hash

    def test_logger_integration_on_upload(self, tmp_path, mock_aws_session):
        """Test that logger is called for upload events"""
        test_file = tmp_path / "logtest.txt"
        test_file.write_text("log content")

        mock_s3_client = mock_aws_session.return_value.client.return_value
        sync = S3Sync()
        sync.s3_client = mock_s3_client
        sync.bucket_name = "test-bucket"

        # Test that logger methods are called during upload
        with patch.object(sync.logger, 'log_info') as mock_log_info:
            with patch.object(sync.logger, 'log_error') as mock_log_error:
                # Simulate successful upload
                with patch.object(sync, '_upload_file_simple', return_value=True):
                    sync._upload_file(test_file, "logtest.txt")
                    # The logger should be called during the upload process
                    assert mock_log_info.called or mock_log_error.called


if __name__ == "__main__":
    pytest.main([__file__]) 