"""
Pytest configuration for AWS S3 Sync Application tests

This file contains shared fixtures and configuration for all tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data that persists across tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_aws_session():
    """Mock AWS session for testing"""
    with patch('boto3.Session') as mock_session:
        mock_client = Mock()
        mock_resource = Mock()
        mock_session.return_value.client.return_value = mock_client
        mock_session.return_value.resource.return_value = mock_resource
        mock_client.list_buckets.return_value = {}
        yield mock_session

@pytest.fixture
def sample_sync_config():
    """Sample sync configuration for testing"""
    return {
        "aws": {
            "region": "us-east-1",
            "profile": "test-profile"
        },
        "s3": {
            "bucket_name": "test-sync-bucket",
            "storage_class": "STANDARD",
            "encryption": {
                "enabled": True,
                "algorithm": "AES256"
            }
        },
        "sync": {
            "local_path": "./test-data",
            "exclude_patterns": ["*.tmp", "*.log", ".DS_Store"],
            "max_concurrent_uploads": 3,
            "chunk_size_mb": 50,
            "dry_run": False
        },
        "monitoring": {
            "cloudwatch": {
                "enabled": True,
                "namespace": "S3SyncTest"
            }
        }
    }

@pytest.fixture
def mock_s3_responses():
    """Mock S3 API responses for testing"""
    return {
        "head_object_exists": {
            "ETag": '"d41d8cd98f00b204e9800998ecf8427e"',
            "ContentLength": 1024,
            "LastModified": "2023-01-01T00:00:00Z"
        },
        "head_object_not_found": {
            "Error": {
                "Code": "404",
                "Message": "Not Found"
            }
        },
        "list_objects": {
            "Contents": [
                {
                    "Key": "file1.txt",
                    "Size": 1024,
                    "LastModified": "2023-01-01T00:00:00Z"
                },
                {
                    "Key": "file2.txt", 
                    "Size": 2048,
                    "LastModified": "2023-01-02T00:00:00Z"
                }
            ]
        },
        "multipart_upload": {
            "UploadId": "test-upload-id-12345"
        },
        "upload_part": {
            "ETag": '"part-etag-12345"'
        }
    } 