"""
Tests for the S3 Security Manager

Tests the security management functionality to ensure S3 buckets are properly
secured with encryption, versioning, access logging, and other security features.

AWS Concepts Covered:
- S3 encryption at rest and in transit
- S3 bucket versioning and MFA delete
- S3 access logging and monitoring
- Security best practices
- Compliance requirements
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError

# Import the module to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from security_manager import SecurityManager


class TestSecurityManager:
    """Test cases for SecurityManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Don't create the manager here - it will be created in each test with proper mocking
        pass
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_at_rest_aes256(self, mock_session):
        """Test enabling AES256 encryption at rest."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful response
        mock_s3_client.put_bucket_encryption.return_value = {}
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_encryption_at_rest("test-bucket", "AES256")
        
        assert success is True
        mock_s3_client.put_bucket_encryption.assert_called_once()
        
        # Verify the encryption configuration
        call_args = mock_s3_client.put_bucket_encryption.call_args
        config = call_args[1]['ServerSideEncryptionConfiguration']
        assert config['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] == 'AES256'
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_at_rest_kms(self, mock_session):
        """Test enabling KMS encryption at rest."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful response
        mock_s3_client.put_bucket_encryption.return_value = {}
        
        kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_encryption_at_rest("test-bucket", kms_key_id)
        
        assert success is True
        mock_s3_client.put_bucket_encryption.assert_called_once()
        
        # Verify the encryption configuration
        call_args = mock_s3_client.put_bucket_encryption.call_args
        config = call_args[1]['ServerSideEncryptionConfiguration']
        assert config['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] == 'aws:kms'
        assert config['Rules'][0]['ApplyServerSideEncryptionByDefault']['KMSMasterKeyID'] == kms_key_id
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_at_rest_failure(self, mock_session):
        """Test enabling encryption when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.put_bucket_encryption.side_effect = ClientError(error_response, 'PutBucketEncryption')
        
        manager = SecurityManager()
        success = manager.enable_encryption_at_rest("nonexistent-bucket", "AES256")
        
        assert success is False
        
    @patch('security_manager.boto3.Session')
    def test_enable_bucket_versioning_basic(self, mock_session):
        """Test enabling basic bucket versioning."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful response
        mock_s3_client.put_bucket_versioning.return_value = {}
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_bucket_versioning("test-bucket")
        
        assert success is True
        mock_s3_client.put_bucket_versioning.assert_called_once()
        
        # Verify the versioning configuration
        call_args = mock_s3_client.put_bucket_versioning.call_args
        config = call_args[1]['VersioningConfiguration']
        assert config['Status'] == 'Enabled'
        assert 'MFADelete' not in config
        
    @patch('security_manager.boto3.Session')
    def test_enable_bucket_versioning_with_mfa(self, mock_session):
        """Test enabling bucket versioning with MFA delete."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful response
        mock_s3_client.put_bucket_versioning.return_value = {}
        
        mfa_serial = "arn:aws:iam::123456789012:mfa/user"
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_bucket_versioning("test-bucket", mfa_delete=True, mfa_serial=mfa_serial)
        
        assert success is True
        mock_s3_client.put_bucket_versioning.assert_called_once()
        
        # Verify the versioning configuration
        call_args = mock_s3_client.put_bucket_versioning.call_args
        config = call_args[1]['VersioningConfiguration']
        assert config['Status'] == 'Enabled'
        assert config['MFADelete'] == 'Enabled'
        assert call_args[1]['MFA'] == mfa_serial
        
    @patch('security_manager.boto3.Session')
    def test_enable_bucket_versioning_mfa_without_serial(self, mock_session):
        """Test enabling MFA delete without providing MFA serial."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_bucket_versioning("test-bucket", mfa_delete=True)
        
        assert success is False
        mock_s3_client.put_bucket_versioning.assert_not_called()
        
    @patch('security_manager.boto3.Session')
    def test_enable_bucket_versioning_failure(self, mock_session):
        """Test enabling versioning when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.put_bucket_versioning.side_effect = ClientError(error_response, 'PutBucketVersioning')
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_bucket_versioning("nonexistent-bucket")
        
        assert success is False
        
    @patch('security_manager.boto3.Session')
    def test_enable_access_logging(self, mock_session):
        """Test enabling access logging."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful response
        mock_s3_client.put_bucket_logging.return_value = {}
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_access_logging("test-bucket", "log-bucket", "logs/")
        
        assert success is True
        mock_s3_client.put_bucket_logging.assert_called_once()
        
        # Verify the logging configuration
        call_args = mock_s3_client.put_bucket_logging.call_args
        config = call_args[1]['BucketLoggingStatus']['LoggingEnabled']
        assert config['TargetBucket'] == "log-bucket"
        assert config['TargetPrefix'] == "logs/"
        
    @patch('security_manager.boto3.Session')
    def test_enable_access_logging_failure(self, mock_session):
        """Test enabling access logging when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.put_bucket_logging.side_effect = ClientError(error_response, 'PutBucketLogging')
        
        # Create manager after mock is set up
        manager = SecurityManager()
        
        success = manager.enable_access_logging("nonexistent-bucket", "log-bucket")
        
        assert success is False
        
    @patch('security_manager.boto3.Session')
    def test_configure_public_access_block(self, mock_session):
        """Test configuring public access block."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful response
        mock_s3_client.put_public_access_block.return_value = {}
        
        manager = SecurityManager()
        success = manager.configure_public_access_block("test-bucket")
        
        assert success is True
        mock_s3_client.put_public_access_block.assert_called_once()
        
        # Verify the public access block configuration
        call_args = mock_s3_client.put_public_access_block.call_args
        config = call_args[1]['PublicAccessBlockConfiguration']
        assert config['BlockPublicAcls'] is True
        assert config['IgnorePublicAcls'] is True
        assert config['BlockPublicPolicy'] is True
        assert config['RestrictPublicBuckets'] is True
        
    @patch('security_manager.boto3.Session')
    def test_configure_public_access_block_failure(self, mock_session):
        """Test configuring public access block when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.put_public_access_block.side_effect = ClientError(error_response, 'PutPublicAccessBlock')
        
        manager = SecurityManager()
        success = manager.configure_public_access_block("nonexistent-bucket")
        
        assert success is False
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_in_transit_new_policy(self, mock_session):
        """Test enabling encryption in transit with new bucket policy."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock no existing policy
        error_response = {
            'Error': {
                'Code': 'NoSuchBucketPolicy',
                'Message': 'The bucket policy does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        # Mock successful policy update
        mock_s3_client.put_bucket_policy.return_value = {}
        
        manager = SecurityManager()
        success = manager.enable_encryption_in_transit("test-bucket")
        
        assert success is True
        mock_s3_client.put_bucket_policy.assert_called_once()
        
        # Verify the TLS enforcement statement was added
        call_args = mock_s3_client.put_bucket_policy.call_args
        policy = json.loads(call_args[1]['Policy'])
        tls_statement = None
        for statement in policy['Statement']:
            if statement.get('Sid') == 'EnforceTLS':
                tls_statement = statement
                break
        assert tls_statement is not None
        assert tls_statement['Effect'] == 'Deny'
        assert 'aws:SecureTransport' in str(tls_statement['Condition'])
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_in_transit_existing_policy(self, mock_session):
        """Test enabling encryption in transit with existing bucket policy."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock existing policy without TLS enforcement
        existing_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::test-bucket/*"
                }
            ]
        }
        mock_s3_client.get_bucket_policy.return_value = {
            'Policy': json.dumps(existing_policy)
        }
        
        # Mock successful policy update
        mock_s3_client.put_bucket_policy.return_value = {}
        
        manager = SecurityManager()
        success = manager.enable_encryption_in_transit("test-bucket")
        
        assert success is True
        mock_s3_client.put_bucket_policy.assert_called_once()
        
        # Verify the TLS enforcement statement was added to existing policy
        call_args = mock_s3_client.put_bucket_policy.call_args
        policy = json.loads(call_args[1]['Policy'])
        assert len(policy['Statement']) == 2  # Original statement + TLS statement
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_in_transit_tls_already_exists(self, mock_session):
        """Test enabling encryption in transit when TLS enforcement already exists."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock existing policy with TLS enforcement
        existing_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EnforceTLS",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false"
                        }
                    }
                }
            ]
        }
        mock_s3_client.get_bucket_policy.return_value = {
            'Policy': json.dumps(existing_policy)
        }
        
        manager = SecurityManager()
        success = manager.enable_encryption_in_transit("test-bucket")
        
        assert success is True
        mock_s3_client.put_bucket_policy.assert_not_called()  # No changes needed
        
    @patch('security_manager.boto3.Session')
    def test_enable_encryption_in_transit_failure(self, mock_session):
        """Test enabling encryption in transit when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        manager = SecurityManager()
        success = manager.enable_encryption_in_transit("nonexistent-bucket")
        
        assert success is False
        
    @patch('security_manager.boto3.Session')
    def test_get_security_status_all_enabled(self, mock_session):
        """Test getting security status when all features are enabled."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock encryption response
        mock_s3_client.get_bucket_encryption.return_value = {
            'ServerSideEncryptionConfiguration': {
                'Rules': [
                    {
                        'ApplyServerSideEncryptionByDefault': {
                            'SSEAlgorithm': 'AES256'
                        }
                    }
                ]
            }
        }
        
        # Mock versioning response
        mock_s3_client.get_bucket_versioning.return_value = {
            'Status': 'Enabled',
            'MFADelete': 'Enabled'
        }
        
        # Mock access logging response
        mock_s3_client.get_bucket_logging.return_value = {
            'LoggingEnabled': {
                'TargetBucket': 'log-bucket',
                'TargetPrefix': 'logs/'
            }
        }
        
        # Mock public access block response
        mock_s3_client.get_public_access_block.return_value = {
            'PublicAccessBlockConfiguration': {
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        }
        
        # Mock bucket policy response
        policy_with_tls = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EnforceTLS",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false"
                        }
                    }
                }
            ]
        }
        mock_s3_client.get_bucket_policy.return_value = {
            'Policy': json.dumps(policy_with_tls)
        }
        
        manager = SecurityManager()
        status = manager.get_security_status("test-bucket")
        
        assert status['bucket_name'] == "test-bucket"
        assert status['encryption_enabled'] is True
        assert status['encryption_type'] == 'AES256'
        assert status['versioning_enabled'] is True
        assert status['mfa_delete_enabled'] is True
        assert status['access_logging_enabled'] is True
        assert status['log_bucket'] == 'log-bucket'
        assert status['log_prefix'] == 'logs/'
        assert status['public_access_blocked'] is True
        assert status['tls_enforced'] is True
        
    @patch('security_manager.boto3.Session')
    def test_get_security_status_none_enabled(self, mock_session):
        """Test getting security status when no features are enabled."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock encryption not enabled
        error_response = {
            'Error': {
                'Code': 'ServerSideEncryptionConfigurationNotFoundError',
                'Message': 'The server side encryption configuration was not found'
            }
        }
        mock_s3_client.get_bucket_encryption.side_effect = ClientError(error_response, 'GetBucketEncryption')
        
        # Mock versioning not enabled
        mock_s3_client.get_bucket_versioning.return_value = {
            'Status': 'Suspended'
        }
        
        # Mock access logging not enabled
        mock_s3_client.get_bucket_logging.return_value = {}
        
        # Mock public access block not configured
        mock_s3_client.get_public_access_block.return_value = {
            'PublicAccessBlockConfiguration': {
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': False,
                'RestrictPublicBuckets': False
            }
        }
        
        # Mock no bucket policy
        error_response = {
            'Error': {
                'Code': 'NoSuchBucketPolicy',
                'Message': 'The bucket policy does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        manager = SecurityManager()
        status = manager.get_security_status("test-bucket")
        
        assert status['bucket_name'] == "test-bucket"
        assert status['encryption_enabled'] is False
        assert status['versioning_enabled'] is False
        assert status['mfa_delete_enabled'] is False
        assert status['access_logging_enabled'] is False
        assert status['public_access_blocked'] is False
        assert status['tls_enforced'] is False
        
    @patch('security_manager.boto3.Session')
    def test_apply_comprehensive_security_success(self, mock_session):
        """Test applying comprehensive security successfully."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock all security operations to succeed
        mock_s3_client.put_bucket_encryption.return_value = {}
        mock_s3_client.put_bucket_versioning.return_value = {}
        mock_s3_client.put_public_access_block.return_value = {}
        mock_s3_client.put_bucket_policy.return_value = {}
        
        # Mock no existing policy for TLS enforcement
        error_response = {
            'Error': {
                'Code': 'NoSuchBucketPolicy',
                'Message': 'The bucket policy does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        manager = SecurityManager()
        success = manager.apply_comprehensive_security("test-bucket", "log-bucket")
        
        assert success is True
        
        # Verify all security features were applied
        mock_s3_client.put_bucket_encryption.assert_called_once()
        mock_s3_client.put_bucket_versioning.assert_called_once()
        mock_s3_client.put_public_access_block.assert_called_once()
        mock_s3_client.put_bucket_policy.assert_called_once()
        
    @patch('security_manager.boto3.Session')
    def test_apply_comprehensive_security_encryption_failure(self, mock_session):
        """Test applying comprehensive security when encryption fails."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock encryption to fail
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.put_bucket_encryption.side_effect = ClientError(error_response, 'PutBucketEncryption')
        
        manager = SecurityManager()
        success = manager.apply_comprehensive_security("nonexistent-bucket")
        
        assert success is False
        mock_s3_client.put_bucket_versioning.assert_not_called()
        mock_s3_client.put_public_access_block.assert_not_called()
        mock_s3_client.put_bucket_policy.assert_not_called()
        
    @patch('security_manager.boto3.Session')
    def test_apply_comprehensive_security_with_mfa(self, mock_session):
        """Test applying comprehensive security with MFA delete."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock all security operations to succeed
        mock_s3_client.put_bucket_encryption.return_value = {}
        mock_s3_client.put_bucket_versioning.return_value = {}
        mock_s3_client.put_public_access_block.return_value = {}
        mock_s3_client.put_bucket_policy.return_value = {}
        
        # Mock no existing policy for TLS enforcement
        error_response = {
            'Error': {
                'Code': 'NoSuchBucketPolicy',
                'Message': 'The bucket policy does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        mfa_serial = "arn:aws:iam::123456789012:mfa/user"
        manager = SecurityManager()
        success = manager.apply_comprehensive_security("test-bucket", mfa_serial=mfa_serial)
        
        assert success is True
        
        # Verify MFA delete was enabled
        call_args = mock_s3_client.put_bucket_versioning.call_args
        config = call_args[1]['VersioningConfiguration']
        assert config['MFADelete'] == 'Enabled'
        assert call_args[1]['MFA'] == mfa_serial


if __name__ == '__main__':
    pytest.main([__file__]) 