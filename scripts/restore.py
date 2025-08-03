#!/usr/bin/env python3
"""
Restore Script for AWS S3 Sync Operations

This script provides comprehensive restore functionality including S3 data restoration,
local backup restoration, and configuration restoration. Designed for AWS certification
study with practical restore implementation.

AWS Concepts Covered:
- S3 data restoration and recovery
- Cross-region data restoration
- Restore strategies and point-in-time recovery
- Data integrity verification during restore
- Restore performance optimization

Usage:
    python scripts/restore.py --from-s3
    python scripts/restore.py --from-backup backup.tar.gz
    python scripts/restore.py --config-only
    python scripts/restore.py --verify
"""

import argparse
import json
import os
import sys
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.config_manager import ConfigManager, ConfigError
from scripts.logger import SyncLogger


class RestoreManager:
    """Comprehensive restore manager for sync operations"""
    
    def __init__(self):
        """Initialize restore manager"""
        self.project_root = Path(__file__).parent.parent
        self.config_manager = ConfigManager()
        self.logger = SyncLogger("restore")
        
        # Restore directories
        self.restore_dir = self.project_root / "restore"
        self.restore_dir.mkdir(exist_ok=True)
        
        # Restore settings
        self.verify_checksums = True
        self.overwrite_existing = False
    
    def restore_from_s3(self, bucket_name: str = None, prefix: str = None, 
                       date_filter: str = None) -> Dict[str, Any]:
        """Restore data from S3
        
        Args:
            bucket_name: S3 bucket name (optional, uses config if not provided)
            prefix: S3 key prefix to restore from
            date_filter: Date filter for restoration (YYYY-MM-DD)
            
        Returns:
            Dictionary containing restore results
        """
        results = {"success": True, "restored_files": [], "errors": []}
        
        try:
            # Get bucket name from config if not provided
            if not bucket_name:
                config = self.config_manager.load_config("aws")
                bucket_name = config["aws"]["s3"]["bucket_name"]
            
            if bucket_name == "your-sync-bucket":
                results["success"] = False
                results["errors"].append("Invalid bucket name in configuration")
                return results
            
            # Initialize S3 client
            session = boto3.Session()
            s3 = session.client('s3')
            
            # List objects in bucket
            list_kwargs = {'Bucket': bucket_name}
            if prefix:
                list_kwargs['Prefix'] = prefix
            
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(**list_kwargs)
            
            restored_count = 0
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    last_modified = obj['LastModified']
                    
                    # Apply date filter if specified
                    if date_filter:
                        filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                        if last_modified.date() < filter_date:
                            continue
                    
                    # Skip backup files and system files
                    if key.startswith('backups/') or key.startswith('system/'):
                        continue
                    
                    # Determine local path
                    local_path = self._s3_key_to_local_path(key)
                    local_file = self.project_root / local_path
                    
                    # Create directory if needed
                    local_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Download file
                    try:
                        s3.download_file(bucket_name, key, str(local_file))
                        restored_count += 1
                        results["restored_files"].append(str(local_file))
                        self.logger.log_info(f"Restored: {key} -> {local_file}")
                        
                        # Verify checksum if enabled
                        if self.verify_checksums:
                            self._verify_file_integrity(s3, bucket_name, key, local_file)
                        
                    except Exception as e:
                        results["errors"].append(f"Failed to restore {key}: {e}")
            
            results["restored_count"] = restored_count
            self.logger.log_info(f"S3 restore completed: {restored_count} files restored")
            
        except NoCredentialsError:
            results["success"] = False
            results["errors"].append("AWS credentials not found")
        except ClientError as e:
            results["success"] = False
            results["errors"].append(f"S3 restore error: {e}")
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "S3 restore failed")
        
        return results
    
    def restore_from_backup(self, backup_path: str, restore_type: str = "auto") -> Dict[str, Any]:
        """Restore from local backup file
        
        Args:
            backup_path: Path to backup file
            restore_type: Type of restore (auto, config, data, all)
            
        Returns:
            Dictionary containing restore results
        """
        results = {"success": True, "restored_files": [], "errors": []}
        
        try:
            backup_file = Path(backup_path)
            
            if not backup_file.exists():
                results["success"] = False
                results["errors"].append(f"Backup file not found: {backup_path}")
                return results
            
            # Extract backup to temporary directory
            temp_restore_dir = self.restore_dir / f"temp_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_restore_dir.mkdir(exist_ok=True)
            
            # Extract backup
            if backup_file.suffix == '.tar.gz':
                import tarfile
                with tarfile.open(backup_file, 'r:gz') as tar:
                    tar.extractall(temp_restore_dir)
            else:
                results["success"] = False
                results["errors"].append(f"Unsupported backup format: {backup_file.suffix}")
                return results
            
            # Read manifest
            manifest_path = temp_restore_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                backup_type = manifest.get("backup_type", "unknown")
                self.logger.log_info(f"Restoring {backup_type} backup")
                
                if restore_type == "auto":
                    restore_type = backup_type
                
                # Perform restore based on type
                if restore_type in ["config", "all"]:
                    self._restore_config_from_backup(temp_restore_dir, results)
                
                if restore_type in ["data", "all"]:
                    self._restore_data_from_backup(temp_restore_dir, results)
                
                if restore_type in ["logs", "all"]:
                    self._restore_logs_from_backup(temp_restore_dir, results)
                
            else:
                results["success"] = False
                results["errors"].append("Backup manifest not found")
            
            # Clean up temporary directory
            shutil.rmtree(temp_restore_dir)
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Backup restore failed")
        
        return results
    
    def restore_configuration(self) -> Dict[str, Any]:
        """Restore configuration from backup
        
        Returns:
            Dictionary containing restore results
        """
        results = {"success": True, "restored_files": [], "errors": []}
        
        try:
            # Find latest config backup
            backup_dir = self.project_root / "backups"
            config_backups = list(backup_dir.glob("config_backup_*.tar.gz"))
            
            if not config_backups:
                results["success"] = False
                results["errors"].append("No configuration backups found")
                return results
            
            # Use most recent backup
            latest_backup = max(config_backups, key=lambda x: x.stat().st_mtime)
            
            # Restore from backup
            backup_results = self.restore_from_backup(str(latest_backup), "config")
            
            if backup_results["success"]:
                results["restored_files"] = backup_results["restored_files"]
                self.logger.log_info("Configuration restored successfully")
            else:
                results["success"] = False
                results["errors"].extend(backup_results["errors"])
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Configuration restore failed")
        
        return results
    
    def verify_restore(self, restore_path: str = None) -> Dict[str, Any]:
        """Verify restored data integrity
        
        Args:
            restore_path: Path to verify (optional, uses project root if not provided)
            
        Returns:
            Dictionary containing verification results
        """
        results = {"success": True, "verified_files": [], "errors": []}
        
        try:
            verify_path = Path(restore_path) if restore_path else self.project_root
            
            if not verify_path.exists():
                results["success"] = False
                results["errors"].append(f"Path does not exist: {verify_path}")
                return results
            
            # Verify configuration files
            config_files = [
                "config/aws-config.json",
                "config/sync-config.json"
            ]
            
            for config_file in config_files:
                file_path = verify_path / config_file
                if file_path.exists():
                    # Validate JSON syntax
                    try:
                        with open(file_path, 'r') as f:
                            json.load(f)
                        results["verified_files"].append(str(file_path))
                    except json.JSONDecodeError as e:
                        results["errors"].append(f"Invalid JSON in {config_file}: {e}")
                else:
                    results["errors"].append(f"Missing configuration file: {config_file}")
            
            # Verify data directory structure
            data_dir = verify_path / "data"
            if data_dir.exists():
                file_count = len(list(data_dir.rglob("*")))
                results["verified_files"].append(f"data directory ({file_count} items)")
            else:
                results["warnings"] = results.get("warnings", [])
                results["warnings"].append("Data directory not found")
            
            # Check file permissions
            critical_dirs = ["config", "logs", "data"]
            for directory in critical_dirs:
                dir_path = verify_path / directory
                if dir_path.exists():
                    if not os.access(dir_path, os.R_OK | os.W_OK):
                        results["errors"].append(f"Directory not accessible: {directory}")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Restore verification failed")
        
        return results
    
    def list_available_restores(self) -> List[Dict[str, Any]]:
        """List available restore points
        
        Returns:
            List of restore point information
        """
        restore_points = []
        
        try:
            # Check local backups
            backup_dir = self.project_root / "backups"
            for backup_file in backup_dir.glob("*.tar.gz"):
                try:
                    stat = backup_file.stat()
                    restore_info = {
                        "type": "local_backup",
                        "name": backup_file.name,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "path": str(backup_file)
                    }
                    restore_points.append(restore_info)
                except Exception as e:
                    self.logger.log_warning(f"Could not read backup info: {e}")
            
            # Check S3 restore points
            try:
                config = self.config_manager.load_config("aws")
                bucket_name = config["aws"]["s3"]["bucket_name"]
                
                if bucket_name != "your-sync-bucket":
                    session = boto3.Session()
                    s3 = session.client('s3')
                    
                    # List S3 objects as potential restore points
                    response = s3.list_objects_v2(
                        Bucket=bucket_name,
                        Prefix="",
                        MaxKeys=100
                    )
                    
                    if 'Contents' in response:
                        for obj in response['Contents']:
                            if not obj['Key'].startswith('backups/'):
                                restore_info = {
                                    "type": "s3_object",
                                    "name": obj['Key'],
                                    "size": obj['Size'],
                                    "created": obj['LastModified'].isoformat(),
                                    "path": f"s3://{bucket_name}/{obj['Key']}"
                                }
                                restore_points.append(restore_info)
            
            except Exception as e:
                self.logger.log_warning(f"Could not list S3 restore points: {e}")
        
        except Exception as e:
            self.logger.log_error(e, "Failed to list restore points")
        
        return sorted(restore_points, key=lambda x: x["created"], reverse=True)
    
    def _s3_key_to_local_path(self, s3_key: str) -> str:
        """Convert S3 key to local file path"""
        # Remove any prefix and convert to local path
        if s3_key.startswith('data/'):
            return s3_key
        else:
            return f"data/{s3_key}"
    
    def _verify_file_integrity(self, s3_client, bucket: str, key: str, local_file: Path) -> bool:
        """Verify file integrity by comparing checksums"""
        try:
            # Get S3 object metadata
            response = s3_client.head_object(Bucket=bucket, Key=key)
            s3_etag = response.get('ETag', '').strip('"')
            
            # Calculate local file MD5
            md5_hash = hashlib.md5()
            with open(local_file, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            local_etag = md5_hash.hexdigest()
            
            if s3_etag != local_etag:
                self.logger.log_warning(f"Checksum mismatch for {key}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.log_warning(f"Could not verify integrity for {key}: {e}")
            return False
    
    def _restore_config_from_backup(self, backup_dir: Path, results: Dict[str, Any]) -> None:
        """Restore configuration from backup directory"""
        config_backup = backup_dir / "config"
        if config_backup.exists():
            config_dir = self.project_root / "config"
            for config_file in config_backup.glob("*.json"):
                if config_file.name != "manifest.json":
                    dest_path = config_dir / config_file.name
                    shutil.copy2(config_file, dest_path)
                    results["restored_files"].append(str(dest_path))
                    self.logger.log_info(f"Restored config: {config_file.name}")
    
    def _restore_data_from_backup(self, backup_dir: Path, results: Dict[str, Any]) -> None:
        """Restore data from backup directory"""
        data_backup = backup_dir / "data"
        if data_backup.exists():
            data_dir = self.project_root / "data"
            
            # Remove existing data if overwrite is enabled
            if self.overwrite_existing and data_dir.exists():
                shutil.rmtree(data_dir)
            
            # Copy data
            if not data_dir.exists():
                shutil.copytree(data_backup, data_dir)
                results["restored_files"].append(str(data_dir))
                self.logger.log_info("Restored data directory")
    
    def _restore_logs_from_backup(self, backup_dir: Path, results: Dict[str, Any]) -> None:
        """Restore logs from backup directory"""
        logs_backup = backup_dir / "logs"
        if logs_backup.exists():
            logs_dir = self.project_root / "logs"
            for log_file in logs_backup.glob("*.log"):
                shutil.copy2(log_file, logs_dir)
                results["restored_files"].append(str(logs_dir / log_file.name))
                self.logger.log_info(f"Restored log: {log_file.name}")


def main():
    """Main restore function"""
    parser = argparse.ArgumentParser(description="Restore Manager CLI")
    parser.add_argument("--from-s3", action="store_true", help="Restore from S3")
    parser.add_argument("--from-backup", type=str, help="Restore from backup file")
    parser.add_argument("--config-only", action="store_true", help="Restore configuration only")
    parser.add_argument("--verify", action="store_true", help="Verify restored data")
    parser.add_argument("--list", action="store_true", help="List available restore points")
    parser.add_argument("--bucket", type=str, help="S3 bucket name")
    parser.add_argument("--prefix", type=str, help="S3 key prefix")
    parser.add_argument("--date", type=str, help="Date filter (YYYY-MM-DD)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    
    args = parser.parse_args()
    
    restore_manager = RestoreManager()
    
    if args.overwrite:
        restore_manager.overwrite_existing = True
    
    if args.from_s3:
        print("☁️ Restoring from S3...")
        results = restore_manager.restore_from_s3(args.bucket, args.prefix, args.date)
        if results["success"]:
            print(f"✅ S3 restore completed: {results.get('restored_count', 0)} files restored")
        else:
            print(f"❌ S3 restore failed: {results['errors']}")
            sys.exit(1)
    
    elif args.from_backup:
        print(f"📦 Restoring from backup: {args.from_backup}")
        results = restore_manager.restore_from_backup(args.from_backup)
        if results["success"]:
            print(f"✅ Backup restore completed: {len(results['restored_files'])} files restored")
        else:
            print(f"❌ Backup restore failed: {results['errors']}")
            sys.exit(1)
    
    elif args.config_only:
        print("⚙️ Restoring configuration...")
        results = restore_manager.restore_configuration()
        if results["success"]:
            print(f"✅ Configuration restored: {len(results['restored_files'])} files")
        else:
            print(f"❌ Configuration restore failed: {results['errors']}")
            sys.exit(1)
    
    elif args.verify:
        print("🔍 Verifying restored data...")
        results = restore_manager.verify_restore()
        if results["success"]:
            print(f"✅ Verification passed: {len(results['verified_files'])} files verified")
        else:
            print(f"❌ Verification failed: {results['errors']}")
            sys.exit(1)
    
    elif args.list:
        print("📋 Available restore points:")
        restore_points = restore_manager.list_available_restores()
        for point in restore_points:
            size_mb = point["size"] / (1024 * 1024) if point["size"] > 0 else 0
            print(f"  📦 {point['name']} ({size_mb:.1f}MB) - {point['type']} - {point['created']}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 