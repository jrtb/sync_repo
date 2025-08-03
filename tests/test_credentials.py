#!/usr/bin/env python3
"""
Tests for AWS credential validation and testing functionality

This module tests the credential testing features to ensure
AWS authentication and permissions work correctly.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add the scripts directory to the path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

try:
    from test_credentials import CredentialTester
except ImportError:
    # Skip tests if the module is not available
    CredentialTester = None

@pytest.mark.skipif(CredentialTester is None, reason="test_credentials module not available")
class TestCredentialTester:
    """Test cases for CredentialTester class"""
    
    @pytest.fixture
    def credential_tester(self):
        """Create a CredentialTester instance for testing"""
        return CredentialTester(
            profile="test-profile",
            bucket_name="test-bucket",
            region="us-east-1"
        )
    
    @pytest.fixture
    def mock_aws_command(self):
        """Mock AWS CLI command execution"""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = '{"Account": "123456789012", "UserId": "AIDACKCEVSQ6C2EXAMPLE", "Arn": "arn:aws:iam::123456789012:user/test-user"}'
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            yield mock_run
    
    def test_init(self):
        """Test CredentialTester initialization"""
        tester = CredentialTester("test-profile", "test-bucket", "us-west-2")
        
        assert tester.profile == "test-profile"
        assert tester.bucket_name == "test-bucket"
        assert tester.region == "us-west-2"
        assert tester.project_root is not None
    
    def test_run_aws_command_success(self, credential_tester, mock_aws_command):
        """Test successful AWS command execution"""
        result = credential_tester.run_aws_command("sts get-caller-identity")
        
        assert result is not None
        assert result.returncode == 0
        mock_aws_command.assert_called_once()
        
        # Check that profile was included in command
        call_args = mock_aws_command.call_args[0][0]
        assert "--profile test-profile" in call_args
    
    def test_run_aws_command_failure(self, credential_tester):
        """Test AWS command execution failure"""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Command failed")
            
            result = credential_tester.run_aws_command("invalid command")
            assert result is None
    
    def test_test_aws_identity_success(self, credential_tester, mock_aws_command):
        """Test successful AWS identity verification"""
        result = credential_tester.test_aws_identity()
        
        assert result is True
        mock_aws_command.assert_called_once()
    
    def test_test_aws_identity_failure(self, credential_tester):
        """Test AWS identity verification failure"""
        with patch.object(credential_tester, 'run_aws_command', return_value=None):
            result = credential_tester.test_aws_identity()
            assert result is False
    
    def test_test_s3_bucket_access_success(self, credential_tester, mock_aws_command):
        """Test successful S3 bucket access"""
        mock_aws_command.return_value.stdout = "2023-01-01 12:00:00 file1.txt\n2023-01-01 12:00:00 file2.txt"
        
        result = credential_tester.test_s3_bucket_access()
        
        assert result is True
        mock_aws_command.assert_called_once()
        
        # Check that bucket name was included in command
        call_args = mock_aws_command.call_args[0][0]
        assert "test-bucket" in call_args
    
    def test_test_s3_bucket_access_empty_bucket(self, credential_tester, mock_aws_command):
        """Test S3 bucket access with empty bucket"""
        mock_aws_command.return_value.stdout = ""
        
        result = credential_tester.test_s3_bucket_access()
        
        assert result is True
        mock_aws_command.assert_called_once()
    
    def test_test_s3_bucket_access_failure(self, credential_tester):
        """Test S3 bucket access failure"""
        with patch.object(credential_tester, 'run_aws_command', return_value=None):
            result = credential_tester.test_s3_bucket_access()
            assert result is False
    
    def test_test_s3_upload_download_success(self, credential_tester, mock_aws_command):
        """Test successful S3 upload and download"""
        # Mock file operations
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.write.return_value = None
            
            result = credential_tester.test_s3_upload_download()
            
            assert result is True
            # Verify upload and download commands were called
            assert mock_aws_command.call_count >= 2
    
    def test_test_s3_upload_download_failure(self, credential_tester):
        """Test S3 upload and download failure"""
        with patch.object(credential_tester, 'run_aws_command', return_value=None):
            result = credential_tester.test_s3_upload_download()
            assert result is False
    
    def test_test_s3_bucket_metadata_success(self, credential_tester, mock_aws_command):
        """Test successful S3 bucket metadata retrieval"""
        mock_aws_command.return_value.stdout = '{"Name": "test-bucket", "CreationDate": "2023-01-01T00:00:00Z"}'
        
        result = credential_tester.test_s3_bucket_metadata()
        
        assert result is True
        mock_aws_command.assert_called_once()
    
    def test_test_s3_bucket_metadata_failure(self, credential_tester):
        """Test S3 bucket metadata retrieval failure"""
        with patch.object(credential_tester, 'run_aws_command', return_value=None):
            result = credential_tester.test_s3_bucket_metadata()
            assert result is False
    
    def test_test_cloudwatch_permissions_success(self, credential_tester, mock_aws_command):
        """Test successful CloudWatch permissions"""
        mock_aws_command.return_value.stdout = '{"logGroups": []}'
        
        result = credential_tester.test_cloudwatch_permissions()
        
        assert result is True
        mock_aws_command.assert_called_once()
    
    def test_test_cloudwatch_permissions_failure(self, credential_tester):
        """Test CloudWatch permissions failure"""
        with patch.object(credential_tester, 'run_aws_command', return_value=None):
            result = credential_tester.test_cloudwatch_permissions()
            assert result is False
    
    def test_test_iam_permissions_success(self, credential_tester, mock_aws_command):
        """Test successful IAM permissions"""
        mock_aws_command.return_value.stdout = '{"User": {"UserName": "test-user"}}'
        
        result = credential_tester.test_iam_permissions()
        
        assert result is True
        mock_aws_command.assert_called_once()
    
    def test_test_iam_permissions_failure(self, credential_tester):
        """Test IAM permissions failure"""
        with patch.object(credential_tester, 'run_aws_command', return_value=None):
            result = credential_tester.test_iam_permissions()
            assert result is False
    
    def test_run_all_tests_success(self, credential_tester):
        """Test running all tests successfully"""
        with patch.object(credential_tester, 'test_aws_identity', return_value=True) as mock_identity:
            with patch.object(credential_tester, 'test_s3_bucket_access', return_value=True) as mock_s3:
                with patch.object(credential_tester, 'test_s3_upload_download', return_value=True) as mock_upload:
                    with patch.object(credential_tester, 'test_s3_bucket_metadata', return_value=True) as mock_metadata:
                        with patch.object(credential_tester, 'test_cloudwatch_permissions', return_value=True) as mock_cw:
                            with patch.object(credential_tester, 'test_iam_permissions', return_value=True) as mock_iam:
                                result = credential_tester.run_all_tests()
                                
                                assert result is True
                                mock_identity.assert_called_once()
                                mock_s3.assert_called_once()
                                mock_upload.assert_called_once()
                                mock_metadata.assert_called_once()
                                mock_cw.assert_called_once()
                                mock_iam.assert_called_once()
    
    def test_run_all_tests_partial_failure(self, credential_tester):
        """Test running all tests with partial failures"""
        with patch.object(credential_tester, 'test_aws_identity', return_value=True):
            with patch.object(credential_tester, 'test_s3_bucket_access', return_value=False):
                with patch.object(credential_tester, 'test_s3_upload_download', return_value=True):
                    with patch.object(credential_tester, 'test_s3_bucket_metadata', return_value=True):
                        with patch.object(credential_tester, 'test_cloudwatch_permissions', return_value=True):
                            with patch.object(credential_tester, 'test_iam_permissions', return_value=True):
                                result = credential_tester.run_all_tests()
                                
                                assert result is False
    
    def test_run_all_tests_all_failure(self, credential_tester):
        """Test running all tests with all failures"""
        with patch.object(credential_tester, 'test_aws_identity', return_value=False):
            with patch.object(credential_tester, 'test_s3_bucket_access', return_value=False):
                with patch.object(credential_tester, 'test_s3_upload_download', return_value=False):
                    with patch.object(credential_tester, 'test_s3_bucket_metadata', return_value=False):
                        with patch.object(credential_tester, 'test_cloudwatch_permissions', return_value=False):
                            with patch.object(credential_tester, 'test_iam_permissions', return_value=False):
                                result = credential_tester.run_all_tests()
                                
                                assert result is False


@pytest.mark.skipif(CredentialTester is None, reason="test_credentials module not available")
class TestCredentialTesterIntegration:
    """Integration tests for credential testing"""
    
    @pytest.fixture
    def temp_test_dir(self):
        """Create temporary directory for integration tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir)
    
    def test_integration_credential_validation(self, temp_test_dir):
        """Test integration of credential validation workflow"""
        # Create a test configuration
        config_file = Path(temp_test_dir) / "test-config.json"
        config = {
            "aws": {
                "region": "us-east-1",
                "profile": "test-profile"
            },
            "s3": {
                "bucket_name": "test-bucket"
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        # Mock AWS CLI responses
        with patch('subprocess.run') as mock_run:
            # Mock successful responses
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = '{"Account": "123456789012", "UserId": "AIDACKCEVSQ6C2EXAMPLE", "Arn": "arn:aws:iam::123456789012:user/test-user"}'
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            tester = CredentialTester("test-profile", "test-bucket")
            
            # Test that all validation methods work
            assert tester.test_aws_identity() is True
            assert tester.test_s3_bucket_access() is True
    
    def test_error_handling_integration(self, temp_test_dir):
        """Test error handling in credential validation"""
        with patch('subprocess.run') as mock_run:
            # Mock command failure
            mock_run.side_effect = Exception("AWS CLI not found")
            
            tester = CredentialTester("test-profile", "test-bucket")
            
            # Test that failures are handled gracefully
            assert tester.test_aws_identity() is False
            assert tester.test_s3_bucket_access() is False


if __name__ == "__main__":
    pytest.main([__file__]) 