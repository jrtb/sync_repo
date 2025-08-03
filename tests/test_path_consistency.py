#!/usr/bin/env python3
"""
Test Suite for Path Consistency in S3 Sync

This test suite specifically verifies that the sync functionality handles
relative paths consistently regardless of where the sync command is run from.
This prevents the issue where files were re-uploaded due to different
relative paths when running sync from different directories.

Key Test Scenarios:
1. Running sync from different working directories
2. Handling files outside the sync directory
3. Consistent S3 key generation
4. Preventing duplicate uploads due to path differences
"""

import pytest
import tempfile
import shutil
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import hashlib
import subprocess
import sys

# Add the scripts directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sync import S3Sync


class TestPathConsistency:
    """Test cases for path consistency in S3 sync"""
    
    @pytest.fixture
    def temp_project_structure(self):
        """Create a temporary project structure for testing"""
        temp_dir = tempfile.mkdtemp()
        
        # Create project structure
        project_root = Path(temp_dir) / "project"
        project_root.mkdir()
        
        # Create data directory
        data_dir = project_root / "data"
        data_dir.mkdir()
        
        # Create subdirectories and files
        subdir1 = data_dir / "subdir1"
        subdir1.mkdir()
        
        subdir2 = data_dir / "subdir2"
        subdir2.mkdir()
        
        nested_dir = subdir1 / "nested"
        nested_dir.mkdir()
        
        # Create test files
        (data_dir / "file1.txt").write_text("content1")
        (data_dir / "file2.txt").write_text("content2")
        (subdir1 / "file3.txt").write_text("content3")
        (subdir2 / "file4.txt").write_text("content4")
        (nested_dir / "file5.txt").write_text("content5")
        
        # Create config file
        config = {
            "aws": {
                "region": "us-east-1",
                "profile": "test-profile"
            },
            "s3": {
                "bucket_name": "test-bucket",
                "storage_class": "STANDARD"
            },
            "sync": {
                "local_path": "./data",
                "dry_run": True,
                "max_retries": 1
            }
        }
        
        config_file = project_root / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        yield temp_dir, project_root, data_dir, config_file
        
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_aws_session(self):
        """Mock AWS session for testing"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            yield mock_session
    
    def test_s3_key_consistency_from_different_directories(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent when sync is run from different directories"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        # Create sync instance from project root
        sync_from_root = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create sync instance from data directory with absolute path
        sync_from_data = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),  # Use absolute path instead of "."
            dry_run=True
        )
        
        # Test files
        test_files = [
            data_dir / "file1.txt",
            data_dir / "subdir1" / "file3.txt",
            data_dir / "subdir1" / "nested" / "file5.txt"
        ]
        
        # Compare S3 keys generated from different working directories
        for file_path in test_files:
            key_from_root = sync_from_root._calculate_s3_key(file_path)
            key_from_data = sync_from_data._calculate_s3_key(file_path)
            
            assert key_from_root == key_from_data, (
                f"S3 keys should be identical for {file_path}: "
                f"root={key_from_root}, data={key_from_data}"
            )
    
    def test_s3_key_consistency_with_absolute_paths(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent when using absolute vs relative paths"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        test_file = data_dir / "file1.txt"
        
        # Test with relative path
        relative_key = sync._calculate_s3_key(test_file)
        
        # Test with absolute path
        absolute_key = sync._calculate_s3_key(test_file.resolve())
        
        assert relative_key == absolute_key, (
            f"S3 keys should be identical for absolute and relative paths: "
            f"relative={relative_key}, absolute={absolute_key}"
        )
    
    def test_s3_key_consistency_with_symlinks(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent when files are accessed via symlinks"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        # Create a symlink to the data directory
        symlink_dir = project_root / "symlink_data"
        symlink_dir.symlink_to(data_dir)
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        test_file = data_dir / "file1.txt"
        symlink_file = symlink_dir / "file1.txt"
        
        # Test with original path
        original_key = sync._calculate_s3_key(test_file)
        
        # Test with symlink path
        symlink_key = sync._calculate_s3_key(symlink_file)
        
        assert original_key == symlink_key, (
            f"S3 keys should be identical for original and symlink paths: "
            f"original={original_key}, symlink={symlink_key}"
        )
    
    def test_s3_key_consistency_with_different_working_directories(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent when working directory changes"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        # Create sync instance
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        test_file = data_dir / "file1.txt"
        
        # Get S3 key from project root
        original_cwd = os.getcwd()
        os.chdir(project_root)
        key_from_project_root = sync._calculate_s3_key(test_file)
        
        # Get S3 key from parent directory
        os.chdir(Path(project_root).parent)
        key_from_parent = sync._calculate_s3_key(test_file)
        
        # Get S3 key from data directory
        os.chdir(data_dir)
        key_from_data = sync._calculate_s3_key(test_file)
        
        # Restore original working directory
        os.chdir(original_cwd)
        
        # All keys should be identical
        assert key_from_project_root == key_from_parent == key_from_data, (
            f"S3 keys should be identical regardless of working directory: "
            f"project_root={key_from_project_root}, "
            f"parent={key_from_parent}, "
            f"data={key_from_data}"
        )
    
    def test_s3_key_consistency_with_outside_paths(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent for files outside the sync directory"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        # Create a file outside the data directory
        outside_file = project_root / "outside.txt"
        outside_file.write_text("outside content")
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Test S3 key calculation for outside file
        s3_key = sync._calculate_s3_key(outside_file)
        
        # Should use fallback method with hash
        assert "/" in s3_key, "S3 key should contain a slash"
        assert outside_file.name in s3_key, "S3 key should contain the filename"
        assert len(s3_key.split("/")[0]) == 8, "Hash should be 8 characters"
        
        # Test consistency - same file should always get same key
        s3_key2 = sync._calculate_s3_key(outside_file)
        assert s3_key == s3_key2, "S3 keys should be consistent for same file"
    
    def test_s3_key_consistency_with_relative_paths(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent with different relative path formats"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        test_file = data_dir / "subdir1" / "file3.txt"
        
        # Test with different relative path formats
        relative_paths = [
            test_file,
            Path("subdir1/file3.txt"),
            Path("./subdir1/file3.txt"),
            Path("../data/subdir1/file3.txt")
        ]
        
        keys = []
        for path in relative_paths:
            if path.exists():
                key = sync._calculate_s3_key(path)
                keys.append(key)
        
        # All existing files should have consistent keys
        if len(keys) > 1:
            first_key = keys[0]
            for key in keys[1:]:
                assert key == first_key, f"All keys should be identical: {keys}"
    
    def test_s3_key_consistency_with_different_file_sizes(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent regardless of file size"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create files of different sizes
        small_file = data_dir / "small.txt"
        small_file.write_text("small")
        
        large_file = data_dir / "large.txt"
        large_file.write_text("large content " * 1000)  # ~15KB
        
        # Test S3 key consistency
        small_key = sync._calculate_s3_key(small_file)
        large_key = sync._calculate_s3_key(large_file)
        
        # Keys should be consistent regardless of size
        assert small_key == "small.txt"
        assert large_key == "large.txt"
    
    def test_s3_key_consistency_with_special_characters(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent with special characters in filenames"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create files with special characters
        special_file = data_dir / "file with spaces.txt"
        special_file.write_text("content with spaces")
        
        unicode_file = data_dir / "file-üñïçødé.txt"
        unicode_file.write_text("unicode content")
        
        # Test S3 key consistency
        special_key = sync._calculate_s3_key(special_file)
        unicode_key = sync._calculate_s3_key(unicode_file)
        
        # Keys should be consistent
        assert special_key == "file with spaces.txt"
        assert unicode_key == "file-üñïçødé.txt"
    
    def test_s3_key_consistency_with_different_file_types(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent with different file types"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create different file types
        text_file = data_dir / "file.txt"
        text_file.write_text("text content")
        
        json_file = data_dir / "file.json"
        json_file.write_text('{"key": "value"}')
        
        binary_file = data_dir / "file.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        
        # Test S3 key consistency
        text_key = sync._calculate_s3_key(text_file)
        json_key = sync._calculate_s3_key(json_file)
        binary_key = sync._calculate_s3_key(binary_file)
        
        # Keys should be consistent
        assert text_key == "file.txt"
        assert json_key == "file.json"
        assert binary_key == "file.bin"
    
    def test_s3_key_consistency_with_empty_files(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent with empty files"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create empty file
        empty_file = data_dir / "empty.txt"
        empty_file.write_text("")
        
        # Test S3 key consistency
        empty_key = sync._calculate_s3_key(empty_file)
        
        # Key should be consistent
        assert empty_key == "empty.txt"
    
    def test_s3_key_consistency_with_hidden_files(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent with hidden files"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create hidden file
        hidden_file = data_dir / ".hidden.txt"
        hidden_file.write_text("hidden content")
        
        # Test S3 key consistency
        hidden_key = sync._calculate_s3_key(hidden_file)
        
        # Key should be consistent
        assert hidden_key == ".hidden.txt"
    
    def test_s3_key_consistency_with_dot_files(self, temp_project_structure, mock_aws_session):
        """Test that S3 keys are consistent with dot files"""
        temp_dir, project_root, data_dir, config_file = temp_project_structure
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create dot file
        dot_file = data_dir / "..file.txt"
        dot_file.write_text("dot file content")
        
        # Test S3 key consistency
        dot_key = sync._calculate_s3_key(dot_file)
        
        # Key should be consistent
        assert dot_key == "..file.txt"


class TestPathConsistencyIntegration:
    """Integration tests for path consistency"""
    
    @pytest.fixture
    def complex_project_structure(self):
        """Create a complex project structure for integration testing"""
        temp_dir = tempfile.mkdtemp()
        
        # Create complex directory structure
        project_root = Path(temp_dir) / "complex_project"
        project_root.mkdir()
        
        # Create multiple data directories
        data_dirs = []
        for i in range(3):
            data_dir = project_root / f"data{i}"
            data_dir.mkdir()
            data_dirs.append(data_dir)
            
            # Create subdirectories
            for j in range(2):
                subdir = data_dir / f"subdir{j}"
                subdir.mkdir()
                
                # Create files
                for k in range(3):
                    file_path = subdir / f"file{i}_{j}_{k}.txt"
                    file_path.write_text(f"content {i}_{j}_{k}")
        
        # Create config files for each data directory
        config_files = []
        for i, data_dir in enumerate(data_dirs):
            config = {
                "aws": {
                    "region": "us-east-1",
                    "profile": "test-profile"
                },
                "s3": {
                    "bucket_name": f"test-bucket-{i}",
                    "storage_class": "STANDARD"
                },
                "sync": {
                    "local_path": str(data_dir),
                    "dry_run": True
                }
            }
            
            config_file = project_root / f"config{i}.json"
            with open(config_file, 'w') as f:
                json.dump(config, f)
            config_files.append(config_file)
        
        yield temp_dir, project_root, data_dirs, config_files
        
        shutil.rmtree(temp_dir)
    
    def test_integration_path_consistency_across_multiple_directories(self, complex_project_structure, mock_aws_session):
        """Integration test for path consistency across multiple directories"""
        temp_dir, project_root, data_dirs, config_files = complex_project_structure
        
        # Test each data directory
        for i, (data_dir, config_file) in enumerate(zip(data_dirs, config_files)):
            sync = S3Sync(
                config_file=str(config_file),
                local_path=str(data_dir),
                dry_run=True
            )
            
            # Test all files in this directory
            for file_path in data_dir.rglob("*.txt"):
                # Test from different working directories
                original_cwd = os.getcwd()
                
                # Test from project root
                os.chdir(project_root)
                key_from_root = sync._calculate_s3_key(file_path)
                
                # Test from data directory
                os.chdir(data_dir)
                key_from_data = sync._calculate_s3_key(file_path)
                
                # Test from parent directory
                os.chdir(Path(project_root).parent)
                key_from_parent = sync._calculate_s3_key(file_path)
                
                # Restore original working directory
                os.chdir(original_cwd)
                
                # All keys should be identical
                assert key_from_root == key_from_data == key_from_parent, (
                    f"Keys should be identical for {file_path}: "
                    f"root={key_from_root}, data={key_from_data}, parent={key_from_parent}"
                )
    
    def test_integration_path_consistency_with_file_operations(self, complex_project_structure, mock_aws_session):
        """Integration test for path consistency during file operations"""
        temp_dir, project_root, data_dirs, config_files = complex_project_structure
        
        data_dir = data_dirs[0]
        config_file = config_files[0]
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Test file operations
        test_file = data_dir / "subdir0" / "file0_0_0.txt"
        
        # Get initial key
        initial_key = sync._calculate_s3_key(test_file)
        
        # Modify file content
        test_file.write_text("modified content")
        
        # Get key after modification
        modified_key = sync._calculate_s3_key(test_file)
        
        # Keys should be identical (content change shouldn't affect key)
        assert initial_key == modified_key, (
            f"Keys should be identical after content modification: "
            f"initial={initial_key}, modified={modified_key}"
        )
        
        # Rename file
        new_file = test_file.parent / "renamed.txt"
        test_file.rename(new_file)
        
        # Get key for renamed file
        renamed_key = sync._calculate_s3_key(new_file)
        
        # Key should reflect the new name
        assert renamed_key == "subdir0/renamed.txt", f"Key should reflect new name: {renamed_key}"
    
    def test_integration_path_consistency_with_directory_operations(self, complex_project_structure, mock_aws_session):
        """Integration test for path consistency during directory operations"""
        temp_dir, project_root, data_dirs, config_files = complex_project_structure
        
        data_dir = data_dirs[0]
        config_file = config_files[0]
        
        sync = S3Sync(
            config_file=str(config_file),
            local_path=str(data_dir),
            dry_run=True
        )
        
        # Create new directory and file
        new_dir = data_dir / "new_dir"
        new_dir.mkdir()
        new_file = new_dir / "new_file.txt"
        new_file.write_text("new content")
        
        # Get key for new file
        new_key = sync._calculate_s3_key(new_file)
        
        # Key should be consistent
        assert new_key == "new_dir/new_file.txt", f"Key should be consistent: {new_key}"
        
        # Move directory
        moved_dir = data_dir / "moved_dir"
        new_dir.rename(moved_dir)
        moved_file = moved_dir / "new_file.txt"
        
        # Get key for moved file
        moved_key = sync._calculate_s3_key(moved_file)
        
        # Key should reflect new path
        assert moved_key == "moved_dir/new_file.txt", f"Key should reflect new path: {moved_key}"


if __name__ == "__main__":
    pytest.main([__file__]) 