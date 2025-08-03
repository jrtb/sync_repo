#!/usr/bin/env python3
"""
Test Suite for AWS Identity Verification Module

This test suite verifies the AWS identity verification functionality,
including IAM username extraction, account information display, and
user confirmation workflows.

AWS Concepts Covered:
- Mocking AWS STS and IAM services
- Unit testing AWS identity verification
- Error handling for authentication issues
- Security testing for identity confirmation
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the scripts directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from aws_identity import AWSIdentityVerifier

class TestAWSIdentityVerifier:
    """Test cases for AWSIdentityVerifier class"""
    
    @pytest.fixture
    def mock_aws_session(self):
        """Mock AWS session and clients"""
        with patch('boto3.Session') as mock_session:
            # Mock STS client
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.return_value = {
                'Account': '123456789012',
                'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
                'Arn': 'arn:aws:iam::123456789012:user/test-user'
            }
            
            # Mock IAM client
            mock_iam_client = Mock()
            mock_iam_client.list_account_aliases.return_value = {
                'AccountAliases': ['test-account-alias']
            }
            
            # Setup session mock
            mock_session_instance = Mock()
            mock_session_instance.client.side_effect = lambda service: {
                'sts': mock_sts_client,
                'iam': mock_iam_client
            }[service]
            mock_session_instance.region_name = 'us-east-1'
            mock_session.return_value = mock_session_instance
            
            yield {
                'session': mock_session_instance,
                'sts_client': mock_sts_client,
                'iam_client': mock_iam_client
            }
    
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
                "storage_class": "STANDARD"
            }
        }
    
    def test_init_success(self, mock_aws_session, sample_config):
        """Test successful initialization"""
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        assert verifier.profile == 'test-profile'
        assert verifier.config == sample_config
        assert verifier.project_root is not None
    
    def test_init_aws_session_failure(self):
        """Test initialization with AWS session failure"""
        with patch('boto3.Session') as mock_session:
            mock_session.side_effect = Exception("AWS session failed")
            
            with pytest.raises(Exception):
                AWSIdentityVerifier(profile='test-profile')
    
    def test_get_identity_info_success(self, mock_aws_session, sample_config):
        """Test successful identity info retrieval"""
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        identity_info = verifier.get_identity_info()
        
        assert identity_info['account_id'] == '123456789012'
        assert identity_info['user_id'] == 'AIDACKCEVSQ6C2EXAMPLE'
        assert identity_info['username'] == 'test-user'
        assert identity_info['account_alias'] == 'test-account-alias'
        assert identity_info['region'] == 'us-east-1'
        assert 'arn:aws:iam::123456789012:user/test-user' in identity_info['arn']
    
    def test_get_identity_info_no_credentials(self, sample_config):
        """Test identity info retrieval with no credentials"""
        with patch('boto3.Session') as mock_session:
            mock_session_instance = Mock()
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.side_effect = Exception("No credentials")
            mock_session_instance.client.return_value = mock_sts_client
            mock_session.return_value = mock_session_instance
            
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            
            with pytest.raises(Exception, match="Failed to get identity info"):
                verifier.get_identity_info()
    
    def test_extract_username_from_arn_user(self, mock_aws_session, sample_config):
        """Test username extraction from user ARN"""
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        # Test user ARN
        username = verifier._extract_username_from_arn('arn:aws:iam::123456789012:user/test-user')
        assert username == 'test-user'
        
        # Test role ARN
        username = verifier._extract_username_from_arn('arn:aws:iam::123456789012:assumed-role/test-role/session')
        assert username == 'test-role'
        
        # Test complex ARN
        username = verifier._extract_username_from_arn('arn:aws:iam::123456789012:user/path/to/complex-user')
        assert username == 'complex-user'
    
    def test_extract_username_from_arn_invalid(self, mock_aws_session, sample_config):
        """Test username extraction from invalid ARN"""
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        # Test invalid ARN
        username = verifier._extract_username_from_arn('invalid-arn')
        assert username == 'invalid-arn'
        
        # Test empty ARN
        username = verifier._extract_username_from_arn('')
        assert username == ''
    
    def test_get_account_alias_success(self, mock_aws_session, sample_config):
        """Test successful account alias retrieval"""
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        alias = verifier._get_account_alias()
        assert alias == 'test-account-alias'
    
    def test_get_account_alias_no_permissions(self, mock_aws_session, sample_config):
        """Test account alias retrieval with no permissions"""
        # Override IAM client to raise exception
        mock_aws_session['iam_client'].list_account_aliases.side_effect = Exception("Access denied")
        
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        alias = verifier._get_account_alias()
        assert alias is None
    
    def test_get_account_alias_empty(self, mock_aws_session, sample_config):
        """Test account alias retrieval with empty result"""
        # Override IAM client to return empty aliases
        mock_aws_session['iam_client'].list_account_aliases.return_value = {
            'AccountAliases': []
        }
        
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        alias = verifier._get_account_alias()
        assert alias is None
    
    @patch('builtins.input')
    def test_get_user_confirmation_yes(self, mock_input, mock_aws_session, sample_config):
        """Test user confirmation with 'yes' response"""
        mock_input.return_value = 'yes'
        
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        result = verifier._get_user_confirmation()
        assert result is True
    
    @patch('builtins.input')
    def test_get_user_confirmation_no(self, mock_input, mock_aws_session, sample_config):
        """Test user confirmation with 'no' response"""
        mock_input.return_value = 'no'
        
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        result = verifier._get_user_confirmation()
        assert result is False
    
    @patch('builtins.input')
    def test_get_user_confirmation_invalid_then_valid(self, mock_input, mock_aws_session, sample_config):
        """Test user confirmation with invalid then valid response"""
        mock_input.side_effect = ['invalid', 'maybe', 'yes']
        
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        result = verifier._get_user_confirmation()
        assert result is True
        assert mock_input.call_count == 3
    
    @patch('builtins.print')
    def test_display_identity_prompt_with_confirmation(self, mock_print, mock_aws_session, sample_config):
        """Test identity prompt display with confirmation"""
        identity_info = {
            'account_id': '123456789012',
            'username': 'test-user',
            'user_id': 'AIDACKCEVSQ6C2EXAMPLE',
            'arn': 'arn:aws:iam::123456789012:user/test-user',
            'account_alias': 'test-account-alias',
            'region': 'us-east-1'
        }
        
        with patch.object(AWSIdentityVerifier, '_get_user_confirmation', return_value=True):
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            result = verifier.display_identity_prompt(identity_info, bucket_name='test-bucket')
            
            assert result is True
            
            # Verify that identity information was printed
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any('AWS IDENTITY VERIFICATION' in call for call in print_calls)
            assert any('123456789012' in call for call in print_calls)
            assert any('test-user' in call for call in print_calls)
            assert any('test-bucket' in call for call in print_calls)
    
    @patch('builtins.print')
    def test_display_identity_prompt_without_confirmation(self, mock_print, mock_aws_session, sample_config):
        """Test identity prompt display without confirmation"""
        identity_info = {
            'account_id': '123456789012',
            'username': 'test-user',
            'user_id': 'AIDACKCEVSQ6C2EXAMPLE',
            'arn': 'arn:aws:iam::123456789012:user/test-user',
            'account_alias': 'test-account-alias',
            'region': 'us-east-1'
        }
        
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        result = verifier.display_identity_prompt(identity_info, bucket_name='test-bucket', require_confirmation=False)
        
        assert result is True
        
        # Verify that identity information was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any('AWS IDENTITY VERIFICATION' in call for call in print_calls)
    
    def test_verify_identity_for_sync_success(self, mock_aws_session, sample_config):
        """Test successful identity verification for sync"""
        with patch.object(AWSIdentityVerifier, 'display_identity_prompt', return_value=True):
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            result = verifier.verify_identity_for_sync(bucket_name='test-bucket', dry_run=False)
            
            assert result is True
    
    def test_verify_identity_for_sync_dry_run(self, mock_aws_session, sample_config):
        """Test identity verification for sync in dry run mode"""
        with patch.object(AWSIdentityVerifier, 'display_identity_prompt', return_value=True):
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            result = verifier.verify_identity_for_sync(bucket_name='test-bucket', dry_run=True)
            
            assert result is True
    
    def test_verify_identity_for_sync_user_cancelled(self, mock_aws_session, sample_config):
        """Test identity verification when user cancels"""
        with patch.object(AWSIdentityVerifier, 'display_identity_prompt', return_value=False):
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            result = verifier.verify_identity_for_sync(bucket_name='test-bucket', dry_run=False)
            
            assert result is False
    
    def test_verify_identity_for_sync_failure(self, mock_aws_session, sample_config):
        """Test identity verification when identity retrieval fails"""
        with patch.object(AWSIdentityVerifier, 'get_identity_info', side_effect=Exception("Identity failed")):
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            result = verifier.verify_identity_for_sync(bucket_name='test-bucket', dry_run=False)
            
            assert result is False
    
    def test_get_identity_summary_success(self, mock_aws_session, sample_config):
        """Test successful identity summary retrieval"""
        verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
        
        summary = verifier.get_identity_summary()
        
        assert summary['account'] == '123456789012'
        assert summary['user'] == 'test-user'
        assert summary['region'] == 'us-east-1'
    
    def test_get_identity_summary_failure(self, mock_aws_session, sample_config):
        """Test identity summary retrieval failure"""
        with patch.object(AWSIdentityVerifier, 'get_identity_info', side_effect=Exception("Identity failed")):
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            
            summary = verifier.get_identity_summary()
            assert summary is None

class TestAWSIdentityVerifierIntegration:
    """Integration tests for AWSIdentityVerifier"""
    
    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for integration testing"""
        return {
            "aws": {
                "region": "us-east-1",
                "profile": "test-profile"
            },
            "s3": {
                "bucket_name": "test-bucket",
                "storage_class": "STANDARD"
            }
        }
    
    def test_integration_identity_verification_workflow(self, temp_test_dir, mock_aws_session, sample_config):
        """Test complete identity verification workflow"""
        with patch('builtins.input', return_value='yes'):
            # Mock the get_identity_info method to return valid data
            with patch.object(AWSIdentityVerifier, 'get_identity_info') as mock_get_identity:
                mock_get_identity.return_value = {
                    'account_id': '123456789012',
                    'username': 'test-user',
                    'user_id': 'AIDACKCEVSQ6C2EXAMPLE',
                    'arn': 'arn:aws:iam::123456789012:user/test-user',
                    'account_alias': 'test-account-alias',
                    'region': 'us-east-1'
                }
                
                verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
                
                # Test complete workflow
                result = verifier.verify_identity_for_sync(bucket_name='test-bucket', dry_run=False)
                
                assert result is True
    
    def test_integration_error_handling(self, temp_test_dir):
        """Test error handling in integration scenarios"""
        with patch('boto3.Session') as mock_session:
            mock_session.side_effect = Exception("AWS session failed")
            
            with pytest.raises(Exception):
                AWSIdentityVerifier(profile='test-profile')
    
    def test_integration_logger_integration(self, temp_test_dir, mock_aws_session, sample_config):
        """Test logger integration with identity verification"""
        # Mock get_identity_info to avoid actual AWS calls
        with patch.object(AWSIdentityVerifier, 'get_identity_info') as mock_get_identity:
            mock_get_identity.return_value = {
                'account_id': '123456789012',
                'username': 'test-user',
                'user_id': 'AIDACKCEVSQ6C2EXAMPLE',
                'arn': 'arn:aws:iam::123456789012:user/test-user',
                'account_alias': 'test-account-alias',
                'region': 'us-east-1'
            }
            
            verifier = AWSIdentityVerifier(profile='test-profile', config=sample_config)
            
            # Test identity verification with logger
            with patch.object(verifier, 'display_identity_prompt', return_value=True):
                result = verifier.verify_identity_for_sync(bucket_name='test-bucket', dry_run=False)
                assert result is True 