#!/usr/bin/env python3
"""
Test script to verify that the relative path issue has been fixed.

This script tests the scenario where sync is run from different directories
to ensure that files aren't re-uploaded due to path differences.
"""

import os
import sys
import tempfile
import shutil
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, Mock

# Add the scripts directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from sync import S3Sync


def create_test_structure():
    """Create a test directory structure"""
    temp_dir = tempfile.mkdtemp()
    
    # Create project structure
    project_root = Path(temp_dir) / "test_project"
    project_root.mkdir()
    
    # Create data directory
    data_dir = project_root / "data"
    data_dir.mkdir()
    
    # Create subdirectories
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
    
    return temp_dir, project_root, data_dir, config_file


def test_s3_key_consistency():
    """Test that S3 keys are consistent regardless of working directory"""
    print("🔍 Testing S3 key consistency...")
    
    temp_dir, project_root, data_dir, config_file = create_test_structure()
    
    try:
        # Mock AWS session
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            
            # Create sync instance
            sync = S3Sync(
                config_file=str(config_file),
                local_path=str(data_dir),
                dry_run=True
            )
            
            # Test files
            test_files = [
                data_dir / "file1.txt",
                data_dir / "subdir1" / "file3.txt",
                data_dir / "subdir1" / "nested" / "file5.txt"
            ]
            
            # Test from different working directories
            original_cwd = os.getcwd()
            
            results = {}
            
            # Test from project root
            os.chdir(project_root)
            print(f"  📁 Testing from project root: {project_root}")
            for file_path in test_files:
                key = sync._calculate_s3_key(file_path)
                results[f"root_{file_path.name}"] = key
                print(f"    {file_path.name} -> {key}")
            
            # Test from data directory
            os.chdir(data_dir)
            print(f"  📁 Testing from data directory: {data_dir}")
            for file_path in test_files:
                key = sync._calculate_s3_key(file_path)
                results[f"data_{file_path.name}"] = key
                print(f"    {file_path.name} -> {key}")
            
            # Test from parent directory
            os.chdir(Path(project_root).parent)
            print(f"  📁 Testing from parent directory: {Path(project_root).parent}")
            for file_path in test_files:
                key = sync._calculate_s3_key(file_path)
                results[f"parent_{file_path.name}"] = key
                print(f"    {file_path.name} -> {key}")
            
            # Restore original working directory
            os.chdir(original_cwd)
            
            # Verify consistency
            print("\n✅ Verifying consistency...")
            all_consistent = True
            
            for filename in ["file1.txt", "file3.txt", "file5.txt"]:
                root_key = results[f"root_{filename}"]
                data_key = results[f"data_{filename}"]
                parent_key = results[f"parent_{filename}"]
                
                if root_key == data_key == parent_key:
                    print(f"  ✅ {filename}: {root_key}")
                else:
                    print(f"  ❌ {filename}: root={root_key}, data={data_key}, parent={parent_key}")
                    all_consistent = False
            
            return all_consistent
            
    finally:
        shutil.rmtree(temp_dir)


def test_absolute_vs_relative_paths():
    """Test that absolute and relative paths produce the same S3 keys"""
    print("\n🔍 Testing absolute vs relative paths...")
    
    temp_dir, project_root, data_dir, config_file = create_test_structure()
    
    try:
        # Mock AWS session
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            
            sync = S3Sync(
                config_file=str(config_file),
                local_path=str(data_dir),
                dry_run=True
            )
            
            test_file = data_dir / "file1.txt"
            
            # Test with relative path
            relative_key = sync._calculate_s3_key(test_file)
            print(f"  📄 Relative path: {test_file} -> {relative_key}")
            
            # Test with absolute path
            absolute_key = sync._calculate_s3_key(test_file.resolve())
            print(f"  📄 Absolute path: {test_file.resolve()} -> {absolute_key}")
            
            if relative_key == absolute_key:
                print("  ✅ Keys are identical")
                return True
            else:
                print("  ❌ Keys are different")
                return False
                
    finally:
        shutil.rmtree(temp_dir)


def test_outside_paths():
    """Test handling of files outside the sync directory"""
    print("\n🔍 Testing files outside sync directory...")
    
    temp_dir, project_root, data_dir, config_file = create_test_structure()
    
    try:
        # Create a file outside the data directory
        outside_file = project_root / "outside.txt"
        outside_file.write_text("outside content")
        
        # Mock AWS session
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            
            sync = S3Sync(
                config_file=str(config_file),
                local_path=str(data_dir),
                dry_run=True
            )
            
            # Test S3 key calculation for outside file
            s3_key = sync._calculate_s3_key(outside_file)
            print(f"  📄 Outside file: {outside_file} -> {s3_key}")
            
            # Should use fallback method with hash
            if "/" in s3_key and outside_file.name in s3_key and len(s3_key.split("/")[0]) == 8:
                print("  ✅ Fallback method used correctly")
                
                # Test consistency
                s3_key2 = sync._calculate_s3_key(outside_file)
                if s3_key == s3_key2:
                    print("  ✅ Keys are consistent")
                    return True
                else:
                    print("  ❌ Keys are inconsistent")
                    return False
            else:
                print("  ❌ Fallback method not used correctly")
                return False
                
    finally:
        shutil.rmtree(temp_dir)


def test_symlink_handling():
    """Test handling of symlinks"""
    print("\n🔍 Testing symlink handling...")
    
    temp_dir, project_root, data_dir, config_file = create_test_structure()
    
    try:
        # Create a symlink to the data directory
        symlink_dir = project_root / "symlink_data"
        symlink_dir.symlink_to(data_dir)
        
        # Mock AWS session
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            
            sync = S3Sync(
                config_file=str(config_file),
                local_path=str(data_dir),
                dry_run=True
            )
            
            test_file = data_dir / "file1.txt"
            symlink_file = symlink_dir / "file1.txt"
            
            # Test with original path
            original_key = sync._calculate_s3_key(test_file)
            print(f"  📄 Original path: {test_file} -> {original_key}")
            
            # Test with symlink path
            symlink_key = sync._calculate_s3_key(symlink_file)
            print(f"  📄 Symlink path: {symlink_file} -> {symlink_key}")
            
            if original_key == symlink_key:
                print("  ✅ Keys are identical")
                return True
            else:
                print("  ❌ Keys are different")
                return False
                
    finally:
        shutil.rmtree(temp_dir)


def test_file_operations():
    """Test path consistency during file operations"""
    print("\n🔍 Testing file operations...")
    
    temp_dir, project_root, data_dir, config_file = create_test_structure()
    
    try:
        # Mock AWS session
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_buckets.return_value = {}
            
            sync = S3Sync(
                config_file=str(config_file),
                local_path=str(data_dir),
                dry_run=True
            )
            
            test_file = data_dir / "subdir1" / "file3.txt"
            
            # Get initial key
            initial_key = sync._calculate_s3_key(test_file)
            print(f"  📄 Initial key: {initial_key}")
            
            # Modify file content
            test_file.write_text("modified content")
            modified_key = sync._calculate_s3_key(test_file)
            print(f"  📄 After modification: {modified_key}")
            
            if initial_key == modified_key:
                print("  ✅ Keys are identical after content modification")
            else:
                print("  ❌ Keys are different after content modification")
                return False
            
            # Rename file
            new_file = test_file.parent / "renamed.txt"
            test_file.rename(new_file)
            renamed_key = sync._calculate_s3_key(new_file)
            print(f"  📄 After rename: {renamed_key}")
            
            # The key should reflect the new path relative to the data directory
            expected_key = "subdir1/renamed.txt"
            if renamed_key == expected_key:
                print("  ✅ Key reflects new name correctly")
                return True
            else:
                print(f"  ❌ Key doesn't reflect new name. Expected: {expected_key}, Got: {renamed_key}")
                return False
                
    finally:
        shutil.rmtree(temp_dir)


def run_all_tests():
    """Run all path consistency tests"""
    print("🚀 Running path consistency tests...\n")
    
    tests = [
        ("S3 Key Consistency", test_s3_key_consistency),
        ("Absolute vs Relative Paths", test_absolute_vs_relative_paths),
        ("Outside Paths", test_outside_paths),
        ("Symlink Handling", test_symlink_handling),
        ("File Operations", test_file_operations),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"🧪 {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"  ✅ {test_name} PASSED\n")
            else:
                print(f"  ❌ {test_name} FAILED\n")
        except Exception as e:
            print(f"  💥 {test_name} ERROR: {e}\n")
            results.append((test_name, False))
    
    # Summary
    print("📊 Test Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"  Total: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {total - passed}")
    
    if passed == total:
        print("\n🎉 All tests passed! The path consistency issue has been fixed.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. The path consistency issue may still exist.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 