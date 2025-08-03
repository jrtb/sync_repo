"""
Tests for the S3 Bucket Policy Validator

Tests the policy validation functionality to ensure S3 bucket policies
follow security best practices and are properly configured for the sync tool.

AWS Concepts Covered:
- S3 bucket policy validation
- Security compliance testing
- Policy structure validation
- Encryption and TLS enforcement
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError

# Import the module to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from policy_validator import PolicyValidator


class TestPolicyValidator:
    """Test cases for PolicyValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PolicyValidator()
        
    def test_validate_policy_structure_valid(self):
        """Test validation of a valid policy structure."""
        valid_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowSyncAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"]
                }
            ]
        }
        
        errors = self.validator.validate_policy_structure(valid_policy)
        assert len(errors) == 0
        
    def test_validate_policy_structure_invalid_version(self):
        """Test validation with invalid policy version."""
        invalid_policy = {
            "Version": "2012-10-16",  # Invalid version
            "Statement": []
        }
        
        errors = self.validator.validate_policy_structure(invalid_policy)
        assert len(errors) == 1
        assert "Policy version must be '2012-10-17'" in errors[0]
        
    def test_validate_policy_structure_missing_version(self):
        """Test validation with missing version field."""
        invalid_policy = {
            "Statement": []
        }
        
        errors = self.validator.validate_policy_structure(invalid_policy)
        assert len(errors) == 1
        assert "Policy missing 'Version' field" in errors[0]
        
    def test_validate_policy_structure_missing_statement(self):
        """Test validation with missing statement field."""
        invalid_policy = {
            "Version": "2012-10-17"
        }
        
        errors = self.validator.validate_policy_structure(invalid_policy)
        assert len(errors) == 1
        assert "Policy missing 'Statement' field" in errors[0]
        
    def test_validate_policy_structure_invalid_statement_type(self):
        """Test validation with invalid statement type."""
        invalid_policy = {
            "Version": "2012-10-17",
            "Statement": "not a list"
        }
        
        errors = self.validator.validate_policy_structure(invalid_policy)
        assert len(errors) == 1
        assert "Policy 'Statement' must be a list" in errors[0]
        
    def test_validate_statement_missing_required_fields(self):
        """Test validation of statement with missing required fields."""
        statement = {
            "Effect": "Allow"
            # Missing Action and Resource
        }
        
        errors = self.validator._validate_statement(statement, 0)
        assert len(errors) == 2
        assert any("missing required field 'Action'" in error for error in errors)
        assert any("missing required field 'Resource'" in error for error in errors)
        
    def test_validate_statement_invalid_effect(self):
        """Test validation of statement with invalid effect."""
        statement = {
            "Effect": "Maybe",  # Invalid effect
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::test-bucket/*"
        }
        
        errors = self.validator._validate_statement(statement, 0)
        assert len(errors) == 1
        assert "Effect must be 'Allow' or 'Deny'" in errors[0]
        
    def test_validate_statement_string_action(self):
        """Test validation of statement with string action (should be converted to list)."""
        statement = {
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::test-bucket/*"
        }
        
        errors = self.validator._validate_statement(statement, 0)
        assert len(errors) == 0
        assert isinstance(statement["Action"], list)
        
    def test_validate_statement_string_resource(self):
        """Test validation of statement with string resource (should be converted to list)."""
        statement = {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": "arn:aws:s3:::test-bucket/*"
        }
        
        errors = self.validator._validate_statement(statement, 0)
        assert len(errors) == 0
        assert isinstance(statement["Resource"], list)
        
    def test_validate_security_requirements_encryption_enforcement(self):
        """Test validation of encryption enforcement requirement."""
        policy_with_encryption = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyUnencryptedUploads",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:PutObject",
                    "Resource": "arn:aws:s3:::test-bucket/*",
                    "Condition": {
                        "StringNotEquals": {
                            "s3:x-amz-server-side-encryption": "AES256"
                        }
                    }
                },
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
                },
                {
                    "Sid": "BlockPublicAccess",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:PrincipalIsAnonymous": "true"
                        }
                    }
                }
            ]
        }
        
        errors = self.validator.validate_security_requirements(policy_with_encryption)
        assert len(errors) == 0
        
    def test_validate_security_requirements_missing_encryption(self):
        """Test validation when encryption enforcement is missing."""
        policy_without_encryption = {
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
        
        errors = self.validator.validate_security_requirements(policy_without_encryption)
        assert len(errors) == 3  # Missing encryption, TLS, and public access prevention
        assert "Policy should enforce server-side encryption for uploads" in errors
        assert "Policy should enforce TLS/HTTPS for all requests" in errors
        assert "Policy should prevent anonymous/public access" in errors
        
    def test_validate_security_requirements_tls_enforcement(self):
        """Test validation of TLS enforcement requirement."""
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
                },
                {
                    "Sid": "DenyUnencryptedUploads",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:PutObject",
                    "Resource": "arn:aws:s3:::test-bucket/*",
                    "Condition": {
                        "StringNotEquals": {
                            "s3:x-amz-server-side-encryption": "AES256"
                        }
                    }
                },
                {
                    "Sid": "BlockPublicAccess",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:PrincipalIsAnonymous": "true"
                        }
                    }
                }
            ]
        }
        
        errors = self.validator.validate_security_requirements(policy_with_tls)
        assert len(errors) == 0
        
    def test_validate_security_requirements_missing_tls(self):
        """Test validation when TLS enforcement is missing."""
        policy_without_tls = {
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
        
        errors = self.validator.validate_security_requirements(policy_without_tls)
        assert len(errors) == 3  # Missing encryption, TLS, and public access prevention
        assert "Policy should enforce server-side encryption for uploads" in errors
        assert "Policy should enforce TLS/HTTPS for all requests" in errors
        assert "Policy should prevent anonymous/public access" in errors
        
    def test_validate_security_requirements_public_access_prevention(self):
        """Test validation of public access prevention requirement."""
        policy_with_public_block = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BlockPublicAccess",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:PrincipalIsAnonymous": "true"
                        }
                    }
                },
                {
                    "Sid": "DenyUnencryptedUploads",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:PutObject",
                    "Resource": "arn:aws:s3:::test-bucket/*",
                    "Condition": {
                        "StringNotEquals": {
                            "s3:x-amz-server-side-encryption": "AES256"
                        }
                    }
                },
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
        
        errors = self.validator.validate_security_requirements(policy_with_public_block)
        assert len(errors) == 0
        
    def test_validate_security_requirements_missing_public_block(self):
        """Test validation when public access prevention is missing."""
        policy_without_public_block = {
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
        
        errors = self.validator.validate_security_requirements(policy_without_public_block)
        assert len(errors) == 3  # Missing encryption, TLS, and public access prevention
        assert "Policy should enforce server-side encryption for uploads" in errors
        assert "Policy should enforce TLS/HTTPS for all requests" in errors
        assert "Policy should prevent anonymous/public access" in errors
        
    def test_validate_sync_tool_access_complete(self):
        """Test validation when all required sync tool permissions are present."""
        policy_with_complete_access = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "SyncToolAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket",
                        "s3:GetBucketLocation"
                    ],
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"]
                }
            ]
        }
        
        errors = self.validator.validate_sync_tool_access(policy_with_complete_access)
        assert len(errors) == 0
        
    def test_validate_sync_tool_access_missing_permissions(self):
        """Test validation when required sync tool permissions are missing."""
        policy_with_missing_permissions = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "SyncToolAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": ["s3:GetObject"],  # Missing other required permissions
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"]
                }
            ]
        }
        
        errors = self.validator.validate_sync_tool_access(policy_with_missing_permissions)
        assert len(errors) == 1
        assert "Policy missing required sync tool permissions" in errors[0]
        
    def test_validate_policy_file_valid(self):
        """Test validation of a valid policy file."""
        valid_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowSyncAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"],
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"]
                },
                {
                    "Sid": "DenyUnencryptedUploads",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:PutObject",
                    "Resource": "arn:aws:s3:::test-bucket/*",
                    "Condition": {
                        "StringNotEquals": {
                            "s3:x-amz-server-side-encryption": "AES256"
                        }
                    }
                },
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
                },
                {
                    "Sid": "BlockPublicAccess",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:PrincipalIsAnonymous": "true"
                        }
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_policy, f)
            temp_file = Path(f.name)
            
        try:
            result = self.validator.validate_policy_file(temp_file)
            assert result['valid'] is True
            assert len(result['errors']) == 0
        finally:
            temp_file.unlink()
            
    def test_validate_policy_file_invalid_json(self):
        """Test validation of an invalid JSON policy file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')
            temp_file = Path(f.name)
            
        try:
            result = self.validator.validate_policy_file(temp_file)
            assert result['valid'] is False
            assert len(result['errors']) == 1
            assert "Failed to load policy file" in result['errors'][0]
        finally:
            temp_file.unlink()
            
    def test_validate_policy_file_nonexistent(self):
        """Test validation of a nonexistent policy file."""
        nonexistent_file = Path("/nonexistent/policy.json")
        result = self.validator.validate_policy_file(nonexistent_file)
        assert result['valid'] is False
        assert len(result['errors']) == 1
        assert "Failed to load policy file" in result['errors'][0]
        
    @patch('policy_validator.boto3.Session')
    def test_validate_bucket_policy_success(self, mock_session):
        """Test successful validation of bucket policy."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowSyncAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"],
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"]
                },
                {
                    "Sid": "DenyUnencryptedUploads",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:PutObject",
                    "Resource": "arn:aws:s3:::test-bucket/*",
                    "Condition": {
                        "StringNotEquals": {
                            "s3:x-amz-server-side-encryption": "AES256"
                        }
                    }
                },
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
                },
                {
                    "Sid": "BlockPublicAccess",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {
                        "Bool": {
                            "aws:PrincipalIsAnonymous": "true"
                        }
                    }
                }
            ]
        }
        
        mock_s3_client.get_bucket_policy.return_value = {
            'Policy': json.dumps(bucket_policy)
        }
        
        validator = PolicyValidator()
        result = validator.validate_bucket_policy("test-bucket")
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
        mock_s3_client.get_bucket_policy.assert_called_once_with(Bucket="test-bucket")
        
    @patch('policy_validator.boto3.Session')
    def test_validate_bucket_policy_no_policy(self, mock_session):
        """Test validation when bucket has no policy."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucketPolicy',
                'Message': 'The bucket policy does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        validator = PolicyValidator()
        result = validator.validate_bucket_policy("test-bucket")
        
        assert result['valid'] is False
        assert len(result['errors']) == 1
        assert "No bucket policy found" in result['errors'][0]
        
    @patch('policy_validator.boto3.Session')
    def test_validate_bucket_policy_aws_error(self, mock_session):
        """Test validation when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.get_bucket_policy.side_effect = ClientError(error_response, 'GetBucketPolicy')
        
        validator = PolicyValidator()
        result = validator.validate_bucket_policy("nonexistent-bucket")
        
        assert result['valid'] is False
        assert len(result['errors']) == 1
        assert "AWS error" in result['errors'][0]
        
    @patch('policy_validator.boto3.Session')
    def test_validate_bucket_policy_no_credentials(self, mock_session):
        """Test validation when AWS credentials are not available."""
        # Mock the session to raise NoCredentialsError when called
        mock_session.side_effect = NoCredentialsError()
        
        # The PolicyValidator constructor will fail, so we need to handle this
        try:
            validator = PolicyValidator()
            # If we get here, the test should fail
            assert False, "Expected PolicyValidator to fail with NoCredentialsError"
        except NoCredentialsError:
            # This is expected behavior
            pass
        
    @patch('policy_validator.boto3.Session')
    def test_apply_policy_template_success(self, mock_session):
        """Test successful application of policy template."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        template_content = '''{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowSyncAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::ACCOUNT_ID:user/SYNC_USER"},
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": ["arn:aws:s3:::BUCKET_NAME", "arn:aws:s3:::BUCKET_NAME/*"]
                }
            ]
        }'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(template_content)
            temp_file = Path(f.name)
            
        try:
            validator = PolicyValidator()
            success = validator.apply_policy_template(
                "test-bucket",
                temp_file,
                {
                    "ACCOUNT_ID": "123456789012",
                    "SYNC_USER": "sync-user",
                    "BUCKET_NAME": "test-bucket"
                }
            )
            
            assert success is True
            mock_s3_client.put_bucket_policy.assert_called_once()
            
            # Verify the policy was processed correctly
            call_args = mock_s3_client.put_bucket_policy.call_args
            applied_policy = json.loads(call_args[1]['Policy'])
            assert applied_policy['Statement'][0]['Principal']['AWS'] == "arn:aws:iam::123456789012:user/sync-user"
            
        finally:
            temp_file.unlink()
            
    @patch('policy_validator.boto3.Session')
    def test_apply_policy_template_invalid_template(self, mock_session):
        """Test application of invalid policy template."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')
            temp_file = Path(f.name)
            
        try:
            validator = PolicyValidator()
            success = validator.apply_policy_template(
                "test-bucket",
                temp_file,
                {}
            )
            
            assert success is False
            mock_s3_client.put_bucket_policy.assert_not_called()
            
        finally:
            temp_file.unlink()
            
    @patch('policy_validator.boto3.Session')
    def test_apply_policy_template_aws_error(self, mock_session):
        """Test application of policy template when AWS returns an error."""
        mock_s3_client = Mock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_s3_client.put_bucket_policy.side_effect = ClientError(error_response, 'PutBucketPolicy')
        
        template_content = '''{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowSyncAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/sync-user"},
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"]
                }
            ]
        }'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(template_content)
            temp_file = Path(f.name)
            
        try:
            validator = PolicyValidator()
            success = validator.apply_policy_template(
                "nonexistent-bucket",
                temp_file,
                {}
            )
            
            assert success is False
            
        finally:
            temp_file.unlink()


if __name__ == '__main__':
    pytest.main([__file__]) 