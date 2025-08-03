#!/usr/bin/env python3
"""
Tests for Configuration Management Module

This module tests the configuration management functionality including validation,
environment-specific configs, and migration utilities. Designed for AWS certification
study with practical testing implementation.

AWS Concepts Covered:
- Configuration validation and testing
- Environment-specific configuration testing
- Configuration migration testing
- Error handling and edge cases
- Security testing for configuration management
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Import the module to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from config.config_manager import ConfigManager, ConfigError


class TestConfigManager:
    """Test suite for ConfigManager class"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory"""
        temp_dir = tempfile.mkdtemp()
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()
        
        # Create test configuration files
        aws_config = {
            "aws": {
                "region": "us-east-1",
                "profile": "test-profile",
                "credentials_file": "config/aws-credentials.json"
            },
            "s3": {
                "bucket_name": "test-bucket",
                "sync_path": "/",
                "storage_class": "STANDARD",
                "encryption": {
                    "enabled": True,
                    "algorithm": "AES256"
                },
                "versioning": {
                    "enabled": True
                }
            },
            "sync": {
                "local_path": "./data",
                "exclude_patterns": ["*.tmp", "*.log"],
                "include_patterns": ["*"],
                "max_concurrent_uploads": 5,
                "chunk_size_mb": 100,
                "retry_attempts": 3,
                "dry_run": False
            }
        }
        
        sync_config = {
            "sync_settings": {
                "mode": "incremental",
                "dry_run": False,
                "force_sync": False,
                "delete_remote": False,
                "preserve_timestamps": True,
                "verify_checksums": True
            },
            "file_handling": {
                "max_file_size": 5368709120,
                "chunk_size": 8388608,
                "concurrent_uploads": 5,
                "timeout": 300,
                "retry_attempts": 3,
                "retry_delay": 5
            },
            "filters": {
                "include_extensions": ["*"],
                "exclude_extensions": [".tmp", ".log"],
                "exclude_directories": [".git", "__pycache__"],
                "exclude_files": ["Thumbs.db", ".DS_Store"]
            }
        }
        
        with open(config_dir / "aws-config.json", 'w') as f:
            json.dump(aws_config, f)
        
        with open(config_dir / "sync-config.json", 'w') as f:
            json.dump(sync_config, f)
        
        yield str(config_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create ConfigManager instance with test configuration"""
        return ConfigManager(temp_config_dir)
    
    def test_init(self, temp_config_dir):
        """Test ConfigManager initialization"""
        config_manager = ConfigManager(temp_config_dir)
        
        assert config_manager.config_dir == Path(temp_config_dir)
        assert config_manager.aws_config_path == Path(temp_config_dir) / "aws-config.json"
        assert config_manager.sync_config_path == Path(temp_config_dir) / "sync-config.json"
        assert config_manager.backup_dir.exists()
    
    def test_load_config_all(self, config_manager):
        """Test loading all configuration files"""
        config = config_manager.load_config()
        
        assert "aws" in config
        assert "sync" in config
        assert config["aws"]["aws"]["region"] == "us-east-1"
        assert config["sync"]["sync_settings"]["mode"] == "incremental"
    
    def test_load_config_aws_only(self, config_manager):
        """Test loading AWS configuration only"""
        config = config_manager.load_config("aws")
        
        assert "aws" in config
        assert "sync" not in config
        assert config["aws"]["aws"]["region"] == "us-east-1"
    
    def test_load_config_sync_only(self, config_manager):
        """Test loading sync configuration only"""
        config = config_manager.load_config("sync")
        
        assert "sync" in config
        assert "aws" not in config
        assert config["sync"]["sync_settings"]["mode"] == "incremental"
    
    def test_load_config_missing_file(self, temp_config_dir):
        """Test loading configuration with missing files"""
        config_manager = ConfigManager(temp_config_dir)
        
        # Remove one config file
        (Path(temp_config_dir) / "aws-config.json").unlink()
        
        with pytest.raises(ConfigError, match="AWS config file not found"):
            config_manager.load_config("aws")
    
    def test_load_config_invalid_json(self, temp_config_dir):
        """Test loading configuration with invalid JSON"""
        config_manager = ConfigManager(temp_config_dir)
        
        # Corrupt the JSON file
        with open(Path(temp_config_dir) / "aws-config.json", 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ConfigError, match="Failed to load AWS config"):
            config_manager.load_config("aws")
    
    def test_validate_config_valid(self, config_manager):
        """Test validation of valid configuration"""
        config = config_manager.load_config()
        errors = config_manager.validate_config(config)
        
        assert len(errors) == 0
    
    def test_validate_config_invalid_aws(self, config_manager):
        """Test validation of invalid AWS configuration"""
        config = config_manager.load_config()
        
        # Make AWS config invalid
        config["aws"]["aws"]["region"] = "invalid-region-!"
        
        errors = config_manager.validate_config(config, "aws")
        assert len(errors) > 0
        assert "AWS config validation error" in errors[0]
    
    def test_validate_config_invalid_sync(self, config_manager):
        """Test validation of invalid sync configuration"""
        config = config_manager.load_config()
        
        # Make sync config invalid
        config["sync"]["sync_settings"]["mode"] = "invalid-mode"
        
        errors = config_manager.validate_config(config, "sync")
        assert len(errors) > 0
        assert "Sync config validation error" in errors[0]
    
    def test_create_environment_config_dev(self, config_manager):
        """Test creating development environment configuration"""
        base_config = config_manager.load_config()
        dev_config = config_manager.create_environment_config("dev", base_config)
        
        # Check dev-specific overrides
        assert dev_config["aws"]["s3"]["bucket_name"] == "test-bucket-dev"
        assert dev_config["sync"]["sync_settings"]["dry_run"] == True
        assert dev_config["sync"]["file_handling"]["concurrent_uploads"] == 2
    
    def test_create_environment_config_staging(self, config_manager):
        """Test creating staging environment configuration"""
        base_config = config_manager.load_config()
        staging_config = config_manager.create_environment_config("staging", base_config)
        
        # Check staging-specific overrides
        assert staging_config["aws"]["s3"]["bucket_name"] == "test-bucket-staging"
        assert staging_config["sync"]["sync_settings"]["dry_run"] == False
        assert staging_config["sync"]["file_handling"]["concurrent_uploads"] == 5
    
    def test_create_environment_config_prod(self, config_manager):
        """Test creating production environment configuration"""
        base_config = config_manager.load_config()
        prod_config = config_manager.create_environment_config("prod", base_config)
        
        # Check prod-specific overrides
        assert prod_config["sync"]["sync_settings"]["dry_run"] == False
        assert prod_config["sync"]["file_handling"]["concurrent_uploads"] == 10
        assert prod_config["sync"]["file_handling"]["retry_attempts"] == 5
    
    def test_migrate_config_v2(self, config_manager):
        """Test configuration migration to version 2.0"""
        base_config = config_manager.load_config()
        
        # Remove monitoring section to simulate old config
        if "monitoring" in base_config["aws"]:
            del base_config["aws"]["monitoring"]
        
        migrated_config = config_manager.migrate_config(base_config, "2.0")
        
        # Check that monitoring section was added
        assert "monitoring" in migrated_config["aws"]
        assert migrated_config["aws"]["monitoring"]["cloudwatch"]["enabled"] == True
        assert migrated_config["aws"]["monitoring"]["logging"]["level"] == "INFO"
    
    def test_save_config(self, config_manager):
        """Test saving configuration to files"""
        config = config_manager.load_config()
        
        # Modify config
        config["aws"]["aws"]["region"] = "us-west-2"
        
        # Save config
        config_manager.save_config(config)
        
        # Reload and verify
        reloaded_config = config_manager.load_config()
        assert reloaded_config["aws"]["aws"]["region"] == "us-west-2"
    
    def test_save_config_backup_created(self, config_manager):
        """Test that backup is created when saving config"""
        config = config_manager.load_config()
        
        # Count existing backups
        initial_backup_count = len(list(config_manager.backup_dir.glob("*.json")))
        
        # Save config
        config_manager.save_config(config)
        
        # Check that backup was created
        final_backup_count = len(list(config_manager.backup_dir.glob("*.json")))
        assert final_backup_count > initial_backup_count
    
    def test_get_config_info(self, config_manager):
        """Test getting configuration information"""
        info = config_manager.get_config_info()
        
        assert "config_directory" in info
        assert "files" in info
        assert "backups" in info
        assert "aws-config.json" in info["files"]
        assert "sync-config.json" in info["files"]
        assert info["files"]["aws-config.json"]["exists"] == True
    
    def test_restore_backup_success(self, config_manager):
        """Test successful backup restoration"""
        # Create a backup
        config = config_manager.load_config()
        config["aws"]["aws"]["region"] = "us-west-2"
        config_manager.save_config(config)
        
        # Get backup file name
        backup_files = list(config_manager.backup_dir.glob("*.json"))
        assert len(backup_files) > 0
        
        # Restore backup
        backup_name = backup_files[0].name
        success = config_manager.restore_backup(backup_name)
        
        assert success == True
    
    def test_restore_backup_not_found(self, config_manager):
        """Test backup restoration with non-existent backup"""
        success = config_manager.restore_backup("non-existent-backup.json")
        assert success == False
    
    @patch('boto3.Session')
    def test_validate_aws_credentials_success(self, mock_session, config_manager):
        """Test successful AWS credentials validation"""
        # Mock successful AWS calls
        mock_sts = MagicMock()
        mock_s3 = MagicMock()
        mock_session.return_value.client.side_effect = [mock_sts, mock_s3]
        
        errors = config_manager.validate_aws_credentials()
        assert len(errors) == 0
    
    @patch('boto3.Session')
    def test_validate_aws_credentials_no_credentials(self, mock_session, config_manager):
        """Test AWS credentials validation with no credentials"""
        from botocore.exceptions import NoCredentialsError
        
        # Mock NoCredentialsError
        mock_session.return_value.client.side_effect = NoCredentialsError()
        
        errors = config_manager.validate_aws_credentials()
        assert len(errors) > 0
        assert "AWS credentials not found" in errors[0]
    
    @patch('boto3.Session')
    def test_validate_aws_credentials_s3_error(self, mock_session, config_manager):
        """Test AWS credentials validation with S3 access error"""
        from botocore.exceptions import ClientError
        
        # Mock successful STS but failed S3
        mock_sts = MagicMock()
        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            'HeadBucket'
        )
        mock_session.return_value.client.side_effect = [mock_sts, mock_s3]
        
        errors = config_manager.validate_aws_credentials()
        assert len(errors) > 0
        assert "S3 bucket access error" in errors[0]
    
    def test_deep_copy_config(self, config_manager):
        """Test deep copy of configuration"""
        original_config = config_manager.load_config()
        copied_config = config_manager._deep_copy_config(original_config)
        
        # Modify original
        original_config["aws"]["aws"]["region"] = "modified"
        
        # Check that copy is not affected
        assert copied_config["aws"]["aws"]["region"] != "modified"
    
    def test_config_error_exception(self):
        """Test ConfigError exception"""
        error = ConfigError("Test error message")
        assert str(error) == "Test error message"


class TestConfigManagerCLI:
    """Test suite for ConfigManager CLI functionality"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory for CLI tests"""
        temp_dir = tempfile.mkdtemp()
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()
        
        # Create minimal test configuration
        aws_config = {
            "aws": {
                "region": "us-east-1",
                "profile": "test-profile"
            },
            "s3": {
                "bucket_name": "test-bucket",
                "storage_class": "STANDARD",
                "encryption": {"enabled": True},
                "versioning": {"enabled": True}
            },
            "sync": {
                "local_path": "./data",
                "exclude_patterns": ["*.tmp"],
                "include_patterns": ["*"]
            }
        }
        
        sync_config = {
            "sync_settings": {
                "mode": "incremental",
                "dry_run": False,
                "force_sync": False,
                "delete_remote": False
            },
            "file_handling": {
                "max_file_size": 1000000,
                "chunk_size": 1024,
                "concurrent_uploads": 5,
                "timeout": 300
            },
            "filters": {
                "include_extensions": ["*"],
                "exclude_extensions": [".tmp"],
                "exclude_directories": [".git"],
                "exclude_files": [".DS_Store"]
            }
        }
        
        with open(config_dir / "aws-config.json", 'w') as f:
            json.dump(aws_config, f)
        
        with open(config_dir / "sync-config.json", 'w') as f:
            json.dump(sync_config, f)
        
        yield str(config_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @patch('sys.argv', ['config-manager.py', '--validate'])
    def test_cli_validate_success(self, temp_config_dir, capsys):
        """Test CLI validate command with valid config"""
        with patch('config.config_manager.ConfigManager') as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.load_config.return_value = {"aws": {}, "sync": {}}
            mock_instance.validate_config.return_value = []
            
            # Import and run CLI
            import config.config_manager
            config.config_manager.main()
            
            captured = capsys.readouterr()
            assert "Configuration is valid" in captured.out
    
    @patch('sys.argv', ['config-manager.py', '--info'])
    def test_cli_info(self, temp_config_dir, capsys):
        """Test CLI info command"""
        with patch('config.config_manager.ConfigManager') as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.get_config_info.return_value = {
                "config_directory": "/test/config",
                "files": {"test.json": {"exists": True}},
                "backups": []
            }
            
            # Import and run CLI
            import config.config_manager
            config.config_manager.main()
            
            captured = capsys.readouterr()
            assert "config_directory" in captured.out


if __name__ == "__main__":
    pytest.main([__file__]) 