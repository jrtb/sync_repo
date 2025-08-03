#!/usr/bin/env python3
"""
Backup Script for AWS S3 Sync Operations

This script provides comprehensive backup functionality including local data backup,
configuration backup, and S3 backup operations. Designed for AWS certification
study with practical backup implementation.

AWS Concepts Covered:
- S3 backup and restore operations
- Data lifecycle management
- Backup strategies and retention policies
- Cross-region backup replication
- Backup encryption and security

Usage:
    python scripts/backup.py --local
    python scripts/backup.py --config
    python scripts/backup.py --s3
    python scripts/backup.py --all
"""

import argparse
import json
import os
import sys
import shutil
import tarfile
import zipfile
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


class BackupManager:
    """Comprehensive backup manager for sync operations"""
    
    def __init__(self):
        """Initialize backup manager"""
        self.project_root = Path(__file__).parent.parent
        self.config_manager = ConfigManager()
        self.logger = SyncLogger("backup")
        
        # Backup directories
        self.backup_dir = self.project_root / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Backup retention settings
        self.retention_days = 30
        self.max_backups = 10
    
    def create_local_backup(self, include_data: bool = True) -> Dict[str, Any]:
        """Create local backup of project files
        
        Args:
            include_data: Whether to include data directory
            
        Returns:
            Dictionary containing backup results
        """
        results = {"success": True, "backup_path": None, "errors": []}
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"local_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            # Backup configuration files
            config_backup_path = backup_path / "config"
            config_backup_path.mkdir(exist_ok=True)
            
            config_files = [
                "config/aws-config.json",
                "config/sync-config.json",
                "config/aws-credentials.json"
            ]
            
            for config_file in config_files:
                source_path = self.project_root / config_file
                if source_path.exists():
                    dest_path = config_backup_path / source_path.name
                    shutil.copy2(source_path, dest_path)
                    self.logger.log_info(f"Backed up: {config_file}")
            
            # Backup logs
            logs_backup_path = backup_path / "logs"
            logs_backup_path.mkdir(exist_ok=True)
            
            logs_dir = self.project_root / "logs"
            if logs_dir.exists():
                for log_file in logs_dir.glob("*.log"):
                    shutil.copy2(log_file, logs_backup_path)
                    self.logger.log_info(f"Backed up log: {log_file.name}")
            
            # Backup data if requested
            if include_data:
                data_backup_path = backup_path / "data"
                data_backup_path.mkdir(exist_ok=True)
                
                data_dir = self.project_root / "data"
                if data_dir.exists():
                    self._backup_directory(data_dir, data_backup_path)
                    self.logger.log_info("Backed up data directory")
            
            # Create backup manifest
            manifest = {
                "backup_type": "local",
                "timestamp": datetime.now().isoformat(),
                "include_data": include_data,
                "files_backed_up": self._count_backed_files(backup_path)
            }
            
            with open(backup_path / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create compressed archive
            archive_path = self.backup_dir / f"{backup_name}.tar.gz"
            self._create_tar_archive(backup_path, archive_path)
            
            # Clean up uncompressed backup
            shutil.rmtree(backup_path)
            
            results["backup_path"] = str(archive_path)
            self.logger.log_info(f"Local backup created: {archive_path}")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Local backup failed")
        
        return results
    
    def create_config_backup(self) -> Dict[str, Any]:
        """Create configuration backup
        
        Returns:
            Dictionary containing backup results
        """
        results = {"success": True, "backup_path": None, "errors": []}
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"config_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            # Backup all configuration files
            config_dir = self.project_root / "config"
            if config_dir.exists():
                for config_file in config_dir.glob("*.json"):
                    shutil.copy2(config_file, backup_path)
                    self.logger.log_info(f"Backed up config: {config_file.name}")
            
            # Create backup manifest
            manifest = {
                "backup_type": "config",
                "timestamp": datetime.now().isoformat(),
                "config_files": [f.name for f in backup_path.glob("*.json")]
            }
            
            with open(backup_path / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create compressed archive
            archive_path = self.backup_dir / f"{backup_name}.tar.gz"
            self._create_tar_archive(backup_path, archive_path)
            
            # Clean up uncompressed backup
            shutil.rmtree(backup_path)
            
            results["backup_path"] = str(archive_path)
            self.logger.log_info(f"Configuration backup created: {archive_path}")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Configuration backup failed")
        
        return results
    
    def create_s3_backup(self, bucket_name: str = None) -> Dict[str, Any]:
        """Create S3 backup of local data
        
        Args:
            bucket_name: S3 bucket name (optional, uses config if not provided)
            
        Returns:
            Dictionary containing backup results
        """
        results = {"success": True, "backup_path": None, "errors": []}
        
        try:
            # Get bucket name from config if not provided
            if not bucket_name:
                config = self.config_manager.load_config("aws")
                bucket_name = config["aws"]["s3"]["bucket_name"]
            
            if bucket_name == "your-sync-bucket":
                results["success"] = False
                results["errors"].append("Invalid bucket name in configuration")
                return results
            
            # Create local backup first
            local_backup = self.create_local_backup(include_data=True)
            if not local_backup["success"]:
                results["success"] = False
                results["errors"].extend(local_backup["errors"])
                return results
            
            # Upload to S3
            session = boto3.Session()
            s3 = session.client('s3')
            
            backup_file = Path(local_backup["backup_path"])
            s3_key = f"backups/{backup_file.name}"
            
            # Upload with encryption
            s3.upload_file(
                str(backup_file),
                bucket_name,
                s3_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'Metadata': {
                        'backup-type': 'local-backup',
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            
            results["backup_path"] = f"s3://{bucket_name}/{s3_key}"
            self.logger.log_info(f"S3 backup created: {results['backup_path']}")
            
            # Clean up local backup file
            backup_file.unlink()
            
        except NoCredentialsError:
            results["success"] = False
            results["errors"].append("AWS credentials not found")
        except ClientError as e:
            results["success"] = False
            results["errors"].append(f"S3 backup error: {e}")
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "S3 backup failed")
        
        return results
    
    def restore_backup(self, backup_path: str, restore_type: str = "auto") -> Dict[str, Any]:
        """Restore from backup
        
        Args:
            backup_path: Path to backup file
            restore_type: Type of restore (auto, config, local)
            
        Returns:
            Dictionary containing restore results
        """
        results = {"success": True, "errors": []}
        
        try:
            backup_file = Path(backup_path)
            
            if not backup_file.exists():
                results["success"] = False
                results["errors"].append(f"Backup file not found: {backup_path}")
                return results
            
            # Extract backup
            extract_path = self.backup_dir / f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            extract_path.mkdir(exist_ok=True)
            
            if backup_file.suffix == '.tar.gz':
                self._extract_tar_archive(backup_file, extract_path)
            elif backup_file.suffix == '.zip':
                with zipfile.ZipFile(backup_file, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
            else:
                results["success"] = False
                results["errors"].append(f"Unsupported backup format: {backup_file.suffix}")
                return results
            
            # Read manifest
            manifest_path = extract_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                backup_type = manifest.get("backup_type", "unknown")
                self.logger.log_info(f"Restoring {backup_type} backup")
                
                if backup_type == "config":
                    self._restore_config_backup(extract_path)
                elif backup_type == "local":
                    self._restore_local_backup(extract_path)
                else:
                    results["success"] = False
                    results["errors"].append(f"Unknown backup type: {backup_type}")
            else:
                results["success"] = False
                results["errors"].append("Backup manifest not found")
            
            # Clean up extracted files
            shutil.rmtree(extract_path)
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Backup restore failed")
        
        return results
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_file in self.backup_dir.glob("*.tar.gz"):
            try:
                stat = backup_file.stat()
                backup_info = {
                    "name": backup_file.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
                
                # Try to extract manifest for more info
                try:
                    with tarfile.open(backup_file, 'r:gz') as tar:
                        manifest_member = None
                        for member in tar.getmembers():
                            if member.name.endswith('manifest.json'):
                                manifest_member = member
                                break
                        
                        if manifest_member:
                            manifest_data = tar.extractfile(manifest_member).read()
                            manifest = json.loads(manifest_data.decode('utf-8'))
                            backup_info["type"] = manifest.get("backup_type", "unknown")
                            backup_info["timestamp"] = manifest.get("timestamp", "")
                
                except Exception:
                    backup_info["type"] = "unknown"
                
                backups.append(backup_info)
                
            except Exception as e:
                self.logger.log_warning(f"Could not read backup info for {backup_file.name}: {e}")
        
        return sorted(backups, key=lambda x: x["created"], reverse=True)
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Clean up old backups based on retention policy
        
        Returns:
            Dictionary containing cleanup results
        """
        results = {"success": True, "deleted_count": 0, "errors": []}
        
        try:
            backups = self.list_backups()
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            for backup in backups:
                backup_date = datetime.fromisoformat(backup["created"])
                if backup_date < cutoff_date:
                    backup_file = self.backup_dir / backup["name"]
                    try:
                        backup_file.unlink()
                        results["deleted_count"] += 1
                        self.logger.log_info(f"Deleted old backup: {backup['name']}")
                    except Exception as e:
                        results["errors"].append(f"Failed to delete {backup['name']}: {e}")
            
            # Also limit total number of backups
            if len(backups) > self.max_backups:
                excess_backups = backups[self.max_backups:]
                for backup in excess_backups:
                    backup_file = self.backup_dir / backup["name"]
                    try:
                        backup_file.unlink()
                        results["deleted_count"] += 1
                        self.logger.log_info(f"Deleted excess backup: {backup['name']}")
                    except Exception as e:
                        results["errors"].append(f"Failed to delete {backup['name']}: {e}")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Backup cleanup failed")
        
        return results
    
    def _backup_directory(self, source_dir: Path, dest_dir: Path) -> None:
        """Recursively backup directory"""
        for item in source_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, dest_dir)
            elif item.is_dir():
                new_dest = dest_dir / item.name
                new_dest.mkdir(exist_ok=True)
                self._backup_directory(item, new_dest)
    
    def _count_backed_files(self, backup_path: Path) -> int:
        """Count files in backup directory"""
        count = 0
        for item in backup_path.rglob("*"):
            if item.is_file():
                count += 1
        return count
    
    def _create_tar_archive(self, source_path: Path, dest_path: Path) -> None:
        """Create tar.gz archive"""
        with tarfile.open(dest_path, 'w:gz') as tar:
            tar.add(source_path, arcname=source_path.name)
    
    def _extract_tar_archive(self, archive_path: Path, extract_path: Path) -> None:
        """Extract tar.gz archive"""
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_path)
    
    def _restore_config_backup(self, backup_path: Path) -> None:
        """Restore configuration backup"""
        config_dir = self.project_root / "config"
        
        for config_file in backup_path.glob("*.json"):
            if config_file.name != "manifest.json":
                dest_path = config_dir / config_file.name
                shutil.copy2(config_file, dest_path)
                self.logger.log_info(f"Restored config: {config_file.name}")
    
    def _restore_local_backup(self, backup_path: Path) -> None:
        """Restore local backup"""
        # Restore config
        config_backup = backup_path / "config"
        if config_backup.exists():
            self._restore_config_backup(config_backup)
        
        # Restore logs
        logs_backup = backup_path / "logs"
        if logs_backup.exists():
            logs_dir = self.project_root / "logs"
            for log_file in logs_backup.glob("*.log"):
                shutil.copy2(log_file, logs_dir)
                self.logger.log_info(f"Restored log: {log_file.name}")
        
        # Restore data
        data_backup = backup_path / "data"
        if data_backup.exists():
            data_dir = self.project_root / "data"
            if data_dir.exists():
                shutil.rmtree(data_dir)
            shutil.copytree(data_backup, data_dir)
            self.logger.log_info("Restored data directory")


def main():
    """Main backup function"""
    parser = argparse.ArgumentParser(description="Backup Manager CLI")
    parser.add_argument("--local", action="store_true", help="Create local backup")
    parser.add_argument("--config", action="store_true", help="Create configuration backup")
    parser.add_argument("--s3", action="store_true", help="Create S3 backup")
    parser.add_argument("--all", action="store_true", help="Create all backups")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--restore", type=str, help="Restore from backup file")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old backups")
    parser.add_argument("--bucket", type=str, help="S3 bucket name for backup")
    
    args = parser.parse_args()
    
    backup_manager = BackupManager()
    
    if args.local:
        print("💾 Creating local backup...")
        results = backup_manager.create_local_backup()
        if results["success"]:
            print(f"✅ Local backup created: {results['backup_path']}")
        else:
            print(f"❌ Local backup failed: {results['errors']}")
            sys.exit(1)
    
    elif args.config:
        print("📁 Creating configuration backup...")
        results = backup_manager.create_config_backup()
        if results["success"]:
            print(f"✅ Configuration backup created: {results['backup_path']}")
        else:
            print(f"❌ Configuration backup failed: {results['errors']}")
            sys.exit(1)
    
    elif args.s3:
        print("☁️ Creating S3 backup...")
        results = backup_manager.create_s3_backup(args.bucket)
        if results["success"]:
            print(f"✅ S3 backup created: {results['backup_path']}")
        else:
            print(f"❌ S3 backup failed: {results['errors']}")
            sys.exit(1)
    
    elif args.all:
        print("🔄 Creating all backups...")
        
        # Local backup
        local_results = backup_manager.create_local_backup()
        if local_results["success"]:
            print(f"✅ Local backup created: {local_results['backup_path']}")
        else:
            print(f"❌ Local backup failed: {local_results['errors']}")
        
        # Config backup
        config_results = backup_manager.create_config_backup()
        if config_results["success"]:
            print(f"✅ Configuration backup created: {config_results['backup_path']}")
        else:
            print(f"❌ Configuration backup failed: {config_results['errors']}")
        
        # S3 backup
        s3_results = backup_manager.create_s3_backup(args.bucket)
        if s3_results["success"]:
            print(f"✅ S3 backup created: {s3_results['backup_path']}")
        else:
            print(f"❌ S3 backup failed: {s3_results['errors']}")
    
    elif args.list:
        print("📋 Available backups:")
        backups = backup_manager.list_backups()
        for backup in backups:
            size_mb = backup["size"] / (1024 * 1024)
            print(f"  📦 {backup['name']} ({size_mb:.1f}MB) - {backup['type']} - {backup['created']}")
    
    elif args.restore:
        print(f"🔄 Restoring from backup: {args.restore}")
        results = backup_manager.restore_backup(args.restore)
        if results["success"]:
            print("✅ Backup restored successfully")
        else:
            print(f"❌ Backup restore failed: {results['errors']}")
            sys.exit(1)
    
    elif args.cleanup:
        print("🧹 Cleaning up old backups...")
        results = backup_manager.cleanup_old_backups()
        if results["success"]:
            print(f"✅ Cleanup completed - deleted {results['deleted_count']} backups")
        else:
            print(f"❌ Cleanup failed: {results['errors']}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 