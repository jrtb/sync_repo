#!/usr/bin/env python3
"""
Tests for Utility Scripts

This module tests the utility scripts including setup, validate, backup, restore,
and cleanup functionality. Designed for AWS certification study with practical
testing implementation.

AWS Concepts Covered:
- Utility script testing and validation
- Configuration management testing
- Backup and restore testing
- Cleanup operation testing
- Error handling and edge cases
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scripts.setup import SetupManager
from scripts.validate import ValidationManager
from scripts.backup import BackupManager
from scripts.restore import RestoreManager
from scripts.cleanup import CleanupManager


class TestSetupManager:
    """Test suite for SetupManager class"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory"""
        temp_dir = tempfile.mkdtemp()
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        yield str(project_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def setup_manager(self, temp_project_dir):
        """Create SetupManager instance"""
        with patch('scripts.setup.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(temp_project_dir)
            return SetupManager()
    
    def test_init(self, setup_manager):
        """Test SetupManager initialization"""
        assert setup_manager.project_root is not None
        assert setup_manager.config_manager is not None
        assert setup_manager.logger is not None
        assert len(setup_manager.directories) > 0
    
    def test_validate_setup(self, setup_manager):
        """Test setup validation"""
        results = setup_manager.validate_setup()
        
        assert isinstance(results, dict)
        assert "directories" in results
        assert "config_files" in results
        assert "aws_credentials" in results
        assert "s3_access" in results
        assert "permissions" in results
    
    def test_create_environment(self, setup_manager):
        """Test environment creation"""
        with patch.object(setup_manager.config_manager, 'load_config') as mock_load:
            mock_load.return_value = {"aws": {}, "sync": {}}
            
            with patch.object(setup_manager.config_manager, 'create_environment_config') as mock_create:
                mock_create.return_value = {"aws": {}, "sync": {}}
                
                with patch.object(setup_manager.config_manager, 'save_config') as mock_save:
                    result = setup_manager.create_environment("dev")
                    assert result == True


class TestValidationManager:
    """Test suite for ValidationManager class"""
    
    @pytest.fixture
    def validation_manager(self):
        """Create ValidationManager instance"""
        return ValidationManager()
    
    def test_init(self, validation_manager):
        """Test ValidationManager initialization"""
        assert validation_manager.project_root is not None
        assert validation_manager.config_manager is not None
        assert validation_manager.logger is not None
        assert len(validation_manager.validation_categories) > 0
    
    def test_validate_all(self, validation_manager):
        """Test all validation categories"""
        results = validation_manager.validate_all()
        
        assert isinstance(results, dict)
        assert "config" in results
        assert "credentials" in results
        assert "permissions" in results
        assert "system" in results
        assert "network" in results
        assert "storage" in results
    
    def test_validate_category(self, validation_manager):
        """Test specific category validation"""
        results = validation_manager.validate_category("config")
        assert isinstance(results, dict)
        assert "valid" in results
        assert "errors" in results
    
    def test_validate_category_invalid(self, validation_manager):
        """Test invalid category validation"""
        results = validation_manager.validate_category("invalid_category")
        assert results["valid"] == False
        assert "Unknown validation category" in results["errors"][0]


class TestBackupManager:
    """Test suite for BackupManager class"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory"""
        temp_dir = tempfile.mkdtemp()
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        # Create test directories
        (project_dir / "config").mkdir()
        (project_dir / "logs").mkdir()
        (project_dir / "data").mkdir()
        (project_dir / "backups").mkdir()
        
        yield str(project_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def backup_manager(self, temp_project_dir):
        """Create BackupManager instance"""
        with patch('scripts.backup.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(temp_project_dir)
            return BackupManager()
    
    def test_init(self, backup_manager):
        """Test BackupManager initialization"""
        assert backup_manager.project_root is not None
        assert backup_manager.config_manager is not None
        assert backup_manager.logger is not None
        assert backup_manager.backup_dir is not None
        assert backup_manager.retention_days > 0
        assert backup_manager.max_backups > 0
    
    def test_create_config_backup(self, backup_manager):
        """Test configuration backup creation"""
        # Create test config file
        config_dir = backup_manager.project_root / "config"
        test_config = {"test": "data"}
        with open(config_dir / "test-config.json", 'w') as f:
            json.dump(test_config, f)
        
        results = backup_manager.create_config_backup()
        assert results["success"] == True
        assert results["backup_path"] is not None
    
    def test_list_backups(self, backup_manager):
        """Test backup listing"""
        backups = backup_manager.list_backups()
        assert isinstance(backups, list)
    
    def test_cleanup_old_backups(self, backup_manager):
        """Test old backup cleanup"""
        results = backup_manager.cleanup_old_backups()
        assert isinstance(results, dict)
        assert "success" in results
        assert "deleted_count" in results
        assert "errors" in results


class TestRestoreManager:
    """Test suite for RestoreManager class"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory"""
        temp_dir = tempfile.mkdtemp()
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        # Create test directories
        (project_dir / "config").mkdir()
        (project_dir / "logs").mkdir()
        (project_dir / "data").mkdir()
        (project_dir / "restore").mkdir()
        
        yield str(project_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def restore_manager(self, temp_project_dir):
        """Create RestoreManager instance"""
        with patch('scripts.restore.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(temp_project_dir)
            return RestoreManager()
    
    def test_init(self, restore_manager):
        """Test RestoreManager initialization"""
        assert restore_manager.project_root is not None
        assert restore_manager.config_manager is not None
        assert restore_manager.logger is not None
        assert restore_manager.restore_dir is not None
        assert restore_manager.verify_checksums == True
        assert restore_manager.overwrite_existing == False
    
    def test_verify_restore(self, restore_manager):
        """Test restore verification"""
        results = restore_manager.verify_restore()
        assert isinstance(results, dict)
        assert "success" in results
        assert "verified_files" in results
        assert "errors" in results
    
    def test_list_available_restores(self, restore_manager):
        """Test available restore points listing"""
        restore_points = restore_manager.list_available_restores()
        assert isinstance(restore_points, list)
    
    def test_s3_key_to_local_path(self, restore_manager):
        """Test S3 key to local path conversion"""
        # Test data prefix
        result = restore_manager._s3_key_to_local_path("data/test.txt")
        assert result == "data/test.txt"
        
        # Test other prefix
        result = restore_manager._s3_key_to_local_path("other/test.txt")
        assert result == "data/other/test.txt"


class TestCleanupManager:
    """Test suite for CleanupManager class"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory"""
        temp_dir = tempfile.mkdtemp()
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        # Create test directories
        (project_dir / "config").mkdir()
        (project_dir / "logs").mkdir()
        (project_dir / "data").mkdir()
        (project_dir / "backups").mkdir()
        (project_dir / "restore").mkdir()
        
        yield str(project_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def cleanup_manager(self, temp_project_dir):
        """Create CleanupManager instance"""
        with patch('scripts.cleanup.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(temp_project_dir)
            return CleanupManager()
    
    def test_init(self, cleanup_manager):
        """Test CleanupManager initialization"""
        assert cleanup_manager.project_root is not None
        assert cleanup_manager.config_manager is not None
        assert cleanup_manager.logger is not None
        assert cleanup_manager.backup_retention_days > 0
        assert cleanup_manager.log_retention_days > 0
        assert len(cleanup_manager.temp_file_patterns) > 0
    
    def test_cleanup_temp_files(self, cleanup_manager):
        """Test temp file cleanup"""
        # Create test temp file
        temp_file = cleanup_manager.project_root / "test.tmp"
        temp_file.write_text("test content")
        
        results = cleanup_manager.cleanup_temp_files(dry_run=True)
        assert isinstance(results, dict)
        assert "success" in results
        assert "deleted_files" in results
        assert "deleted_count" in results
        assert "errors" in results
    
    def test_cleanup_old_backups(self, cleanup_manager):
        """Test old backup cleanup"""
        results = cleanup_manager.cleanup_old_backups(dry_run=True)
        assert isinstance(results, dict)
        assert "success" in results
        assert "deleted_files" in results
        assert "deleted_count" in results
        assert "errors" in results
    
    def test_cleanup_logs(self, cleanup_manager):
        """Test log cleanup"""
        results = cleanup_manager.cleanup_logs(dry_run=True)
        assert isinstance(results, dict)
        assert "success" in results
        assert "deleted_files" in results
        assert "deleted_count" in results
        assert "errors" in results
    
    def test_cleanup_restore_directory(self, cleanup_manager):
        """Test restore directory cleanup"""
        # Create test file in restore directory
        test_file = cleanup_manager.project_root / "restore" / "test.txt"
        test_file.write_text("test content")
        
        results = cleanup_manager.cleanup_restore_directory(dry_run=True)
        assert isinstance(results, dict)
        assert "success" in results
        assert "deleted_files" in results
        assert "deleted_count" in results
        assert "errors" in results
    
    def test_cleanup_all(self, cleanup_manager):
        """Test all cleanup operations"""
        results = cleanup_manager.cleanup_all(dry_run=True)
        assert isinstance(results, dict)
        assert "temp_files" in results
        assert "old_backups" in results
        assert "logs" in results
        assert "s3" in results
        assert "restore_dir" in results
        assert "summary" in results
    
    def test_get_cleanup_stats(self, cleanup_manager):
        """Test cleanup statistics"""
        stats = cleanup_manager.get_cleanup_stats()
        assert isinstance(stats, dict)
        assert "temp_files" in stats
        assert "old_backups" in stats
        assert "old_logs" in stats
        assert "restore_files" in stats
    
    def test_count_temp_files(self, cleanup_manager):
        """Test temp file counting"""
        # Create test temp file
        temp_file = cleanup_manager.project_root / "test.tmp"
        temp_file.write_text("test content")
        
        count = cleanup_manager._count_temp_files()
        assert isinstance(count, int)
        assert count >= 0
    
    def test_count_old_backups(self, cleanup_manager):
        """Test old backup counting"""
        count = cleanup_manager._count_old_backups()
        assert isinstance(count, int)
        assert count >= 0
    
    def test_count_old_logs(self, cleanup_manager):
        """Test old log counting"""
        count = cleanup_manager._count_old_logs()
        assert isinstance(count, int)
        assert count >= 0
    
    def test_count_restore_files(self, cleanup_manager):
        """Test restore file counting"""
        count = cleanup_manager._count_restore_files()
        assert isinstance(count, int)
        assert count >= 0


if __name__ == "__main__":
    pytest.main([__file__]) 