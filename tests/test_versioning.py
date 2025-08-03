#!/usr/bin/env python3
"""
Tests for S3 Bucket Versioning Functionality

This module tests the versioning management functionality including enabling
versioning, checking status, and educational features. Designed for AWS
certification study with practical testing implementation.

AWS Concepts Covered:
- S3 Bucket Versioning testing and validation
- Security testing with MFA delete protection
- Error handling and edge case testing
- Integration testing with security manager
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from scripts.enable_versioning import VersioningManager


class TestVersioningManager:
    """Test cases for VersioningManager class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        with patch('scripts.enable_versioning.SecurityManager'):
            with patch('scripts.enable_versioning.SyncLogger'):
                self.manager = VersioningManager()
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_enable_versioning_basic_success(self, mock_logger, mock_security_manager):
        """Test enabling basic versioning successfully."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.return_value = True
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test enabling versioning
        success = manager.enable_versioning("test-bucket")
        
        assert success is True
        mock_security.enable_bucket_versioning.assert_called_once_with(
            "test-bucket", False, None
        )
        mock_log.log_info.assert_called()
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_enable_versioning_with_mfa_success(self, mock_logger, mock_security_manager):
        """Test enabling versioning with MFA delete successfully."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.return_value = True
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test enabling versioning with MFA
        mfa_serial = "arn:aws:iam::123456789012:mfa/user"
        success = manager.enable_versioning("test-bucket", mfa_delete=True, mfa_serial=mfa_serial)
        
        assert success is True
        mock_security.enable_bucket_versioning.assert_called_once_with(
            "test-bucket", True, mfa_serial
        )
        mock_log.log_info.assert_called()
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_enable_versioning_failure(self, mock_logger, mock_security_manager):
        """Test enabling versioning when it fails."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.return_value = False
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test enabling versioning failure
        success = manager.enable_versioning("test-bucket")
        
        assert success is False
        mock_security.enable_bucket_versioning.assert_called_once()
        mock_log.log_error.assert_called()
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_enable_versioning_exception(self, mock_logger, mock_security_manager):
        """Test enabling versioning when an exception occurs."""
        # Mock security manager to raise exception
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.side_effect = Exception("Test error")
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test enabling versioning with exception
        success = manager.enable_versioning("test-bucket")
        
        assert success is False
        mock_log.log_error.assert_called()
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_check_versioning_status_success(self, mock_logger, mock_security_manager):
        """Test checking versioning status successfully."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.get_security_status.return_value = {
            'versioning_enabled': True,
            'mfa_delete_enabled': False
        }
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test checking status
        status = manager.check_versioning_status("test-bucket")
        
        expected_status = {
            'versioning_enabled': True,
            'mfa_delete_enabled': False,
            'bucket_name': 'test-bucket'
        }
        
        assert status == expected_status
        mock_security.get_security_status.assert_called_once_with("test-bucket")
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_check_versioning_status_with_mfa(self, mock_logger, mock_security_manager):
        """Test checking versioning status with MFA delete enabled."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.get_security_status.return_value = {
            'versioning_enabled': True,
            'mfa_delete_enabled': True
        }
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test checking status with MFA
        status = manager.check_versioning_status("test-bucket")
        
        expected_status = {
            'versioning_enabled': True,
            'mfa_delete_enabled': True,
            'bucket_name': 'test-bucket'
        }
        
        assert status == expected_status
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_check_versioning_status_exception(self, mock_logger, mock_security_manager):
        """Test checking versioning status when an exception occurs."""
        # Mock security manager to raise exception
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.get_security_status.side_effect = Exception("Test error")
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test checking status with exception
        status = manager.check_versioning_status("test-bucket")
        
        expected_status = {
            'versioning_enabled': False,
            'mfa_delete_enabled': False,
            'bucket_name': 'test-bucket',
            'error': 'Test error'
        }
        
        assert status == expected_status
        mock_log.log_error.assert_called()
    
    def test_print_versioning_info(self, capsys):
        """Test printing educational versioning information."""
        manager = VersioningManager()
        
        # Test printing info
        manager.print_versioning_info("test-bucket")
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify educational content is included
        assert "S3 Bucket Versioning - AWS Certification Concepts" in output
        assert "What is S3 Versioning?" in output
        assert "Cost Considerations:" in output
        assert "Security Features:" in output
        assert "AWS Certification Topics:" in output
        assert "Data Protection and Recovery Strategies" in output


class TestVersioningIntegration:
    """Integration tests for versioning functionality"""
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_versioning_manager_integration(self, mock_logger, mock_security_manager):
        """Test integration between VersioningManager and SecurityManager."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.return_value = True
        mock_security.get_security_status.return_value = {
            'versioning_enabled': True,
            'mfa_delete_enabled': False
        }
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test full workflow
        success = manager.enable_versioning("test-bucket")
        status = manager.check_versioning_status("test-bucket")
        
        assert success is True
        assert status['versioning_enabled'] is True
        assert status['bucket_name'] == "test-bucket"
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_mfa_delete_workflow(self, mock_logger, mock_security_manager):
        """Test complete MFA delete workflow."""
        # Mock security manager
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.return_value = True
        mock_security.get_security_status.return_value = {
            'versioning_enabled': True,
            'mfa_delete_enabled': True
        }
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test MFA delete workflow
        mfa_serial = "arn:aws:iam::123456789012:mfa/user"
        success = manager.enable_versioning("test-bucket", mfa_delete=True, mfa_serial=mfa_serial)
        status = manager.check_versioning_status("test-bucket")
        
        assert success is True
        assert status['versioning_enabled'] is True
        assert status['mfa_delete_enabled'] is True
        
        # Verify MFA parameters were passed correctly
        mock_security.enable_bucket_versioning.assert_called_once_with(
            "test-bucket", True, mfa_serial
        )


class TestVersioningErrorHandling:
    """Error handling tests for versioning functionality"""
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_aws_client_error_handling(self, mock_logger, mock_security_manager):
        """Test handling of AWS ClientError exceptions."""
        # Mock security manager to raise ClientError
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access denied'
            }
        }
        mock_security.enable_bucket_versioning.side_effect = ClientError(
            error_response, 'PutBucketVersioning'
        )
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test error handling
        success = manager.enable_versioning("test-bucket")
        
        assert success is False
        mock_log.log_error.assert_called()
    
    @patch('scripts.enable_versioning.SecurityManager')
    @patch('scripts.enable_versioning.SyncLogger')
    def test_network_error_handling(self, mock_logger, mock_security_manager):
        """Test handling of network-related errors."""
        # Mock security manager to raise network error
        mock_security = Mock()
        mock_security_manager.return_value = mock_security
        mock_security.enable_bucket_versioning.side_effect = ConnectionError("Network error")
        
        # Mock logger
        mock_log = Mock()
        mock_logger.return_value = mock_log
        
        manager = VersioningManager()
        
        # Test error handling
        success = manager.enable_versioning("test-bucket")
        
        assert success is False
        mock_log.log_error.assert_called()


if __name__ == "__main__":
    pytest.main([__file__]) 