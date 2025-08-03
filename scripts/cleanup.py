#!/usr/bin/env python3
"""
Cleanup Script for AWS S3 Sync Operations

This script provides comprehensive cleanup functionality including temporary file
cleanup, old backup removal, log rotation, and S3 cleanup operations. Designed
for AWS certification study with practical cleanup implementation.

AWS Concepts Covered:
- S3 object lifecycle management
- Storage cost optimization
- Data retention policies
- Cleanup strategies and automation
- Storage class transitions

Usage:
    python scripts/cleanup.py --temp-files
    python scripts/cleanup.py --old-backups
    python scripts/cleanup.py --logs
    python scripts/cleanup.py --s3
    python scripts/cleanup.py --all
"""

import argparse
import json
import os
import sys
import shutil
import glob
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


class CleanupManager:
    """Comprehensive cleanup manager for sync operations"""
    
    def __init__(self):
        """Initialize cleanup manager"""
        self.project_root = Path(__file__).parent.parent
        self.config_manager = ConfigManager()
        self.logger = SyncLogger("cleanup")
        
        # Cleanup settings
        self.backup_retention_days = 30
        self.log_retention_days = 7
        self.temp_file_patterns = [
            "*.tmp",
            "*.temp",
            "*.swp",
            "*.bak",
            "*.old",
            "._*",
            ".DS_Store",
            "Thumbs.db"
        ]
    
    def cleanup_temp_files(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up temporary files
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary containing cleanup results
        """
        results = {"success": True, "deleted_files": [], "deleted_count": 0, "errors": []}
        
        try:
            # Clean up temp files in project directories
            directories_to_clean = [
                "data",
                "logs",
                "backups",
                "restore"
            ]
            
            for directory in directories_to_clean:
                dir_path = self.project_root / directory
                if dir_path.exists():
                    self._cleanup_directory_temp_files(dir_path, results, dry_run)
            
            # Clean up temp files in root project directory
            self._cleanup_directory_temp_files(self.project_root, results, dry_run)
            
            self.logger.log_info(f"Temp file cleanup completed: {results['deleted_count']} files")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Temp file cleanup failed")
        
        return results
    
    def cleanup_old_backups(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up old backup files
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary containing cleanup results
        """
        results = {"success": True, "deleted_files": [], "deleted_count": 0, "errors": []}
        
        try:
            backup_dir = self.project_root / "backups"
            if not backup_dir.exists():
                return results
            
            cutoff_date = datetime.now() - timedelta(days=self.backup_retention_days)
            
            for backup_file in backup_dir.glob("*.tar.gz"):
                try:
                    stat = backup_file.stat()
                    file_date = datetime.fromtimestamp(stat.st_mtime)
                    
                    if file_date < cutoff_date:
                        if not dry_run:
                            backup_file.unlink()
                            results["deleted_files"].append(str(backup_file))
                            results["deleted_count"] += 1
                            self.logger.log_info(f"Deleted old backup: {backup_file.name}")
                        else:
                            results["deleted_files"].append(str(backup_file))
                            results["deleted_count"] += 1
                
                except Exception as e:
                    results["errors"].append(f"Failed to process {backup_file.name}: {e}")
            
            self.logger.log_info(f"Old backup cleanup completed: {results['deleted_count']} files")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Old backup cleanup failed")
        
        return results
    
    def cleanup_logs(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up old log files
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary containing cleanup results
        """
        results = {"success": True, "deleted_files": [], "deleted_count": 0, "errors": []}
        
        try:
            logs_dir = self.project_root / "logs"
            if not logs_dir.exists():
                return results
            
            cutoff_date = datetime.now() - timedelta(days=self.log_retention_days)
            
            for log_file in logs_dir.glob("*.log"):
                try:
                    stat = log_file.stat()
                    file_date = datetime.fromtimestamp(stat.st_mtime)
                    
                    if file_date < cutoff_date:
                        if not dry_run:
                            log_file.unlink()
                            results["deleted_files"].append(str(log_file))
                            results["deleted_count"] += 1
                            self.logger.log_info(f"Deleted old log: {log_file.name}")
                        else:
                            results["deleted_files"].append(str(log_file))
                            results["deleted_count"] += 1
                
                except Exception as e:
                    results["errors"].append(f"Failed to process {log_file.name}: {e}")
            
            self.logger.log_info(f"Log cleanup completed: {results['deleted_count']} files")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Log cleanup failed")
        
        return results
    
    def cleanup_s3(self, bucket_name: str = None, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up S3 objects based on lifecycle policies
        
        Args:
            bucket_name: S3 bucket name (optional, uses config if not provided)
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary containing cleanup results
        """
        results = {"success": True, "deleted_objects": [], "deleted_count": 0, "errors": []}
        
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
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name)
            
            cutoff_date = datetime.now() - timedelta(days=self.backup_retention_days)
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    last_modified = obj['LastModified']
                    
                    # Skip system files and current data
                    if key.startswith('system/') or not key.startswith('backups/'):
                        continue
                    
                    # Check if object is old enough to delete
                    if last_modified < cutoff_date:
                        if not dry_run:
                            try:
                                s3.delete_object(Bucket=bucket_name, Key=key)
                                results["deleted_objects"].append(key)
                                results["deleted_count"] += 1
                                self.logger.log_info(f"Deleted S3 object: {key}")
                            except Exception as e:
                                results["errors"].append(f"Failed to delete {key}: {e}")
                        else:
                            results["deleted_objects"].append(key)
                            results["deleted_count"] += 1
            
            self.logger.log_info(f"S3 cleanup completed: {results['deleted_count']} objects")
            
        except NoCredentialsError:
            results["success"] = False
            results["errors"].append("AWS credentials not found")
        except ClientError as e:
            results["success"] = False
            results["errors"].append(f"S3 cleanup error: {e}")
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "S3 cleanup failed")
        
        return results
    
    def cleanup_restore_directory(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up restore directory
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary containing cleanup results
        """
        results = {"success": True, "deleted_files": [], "deleted_count": 0, "errors": []}
        
        try:
            restore_dir = self.project_root / "restore"
            if not restore_dir.exists():
                return results
            
            # Remove all files in restore directory
            for item in restore_dir.iterdir():
                try:
                    if item.is_file():
                        if not dry_run:
                            item.unlink()
                            results["deleted_files"].append(str(item))
                            results["deleted_count"] += 1
                        else:
                            results["deleted_files"].append(str(item))
                            results["deleted_count"] += 1
                    elif item.is_dir():
                        if not dry_run:
                            shutil.rmtree(item)
                            results["deleted_files"].append(str(item))
                            results["deleted_count"] += 1
                        else:
                            results["deleted_files"].append(str(item))
                            results["deleted_count"] += 1
                
                except Exception as e:
                    results["errors"].append(f"Failed to delete {item.name}: {e}")
            
            self.logger.log_info(f"Restore directory cleanup completed: {results['deleted_count']} items")
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
            self.logger.log_error(e, "Restore directory cleanup failed")
        
        return results
    
    def cleanup_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run all cleanup operations
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary containing cleanup results
        """
        results = {
            "temp_files": self.cleanup_temp_files(dry_run),
            "old_backups": self.cleanup_old_backups(dry_run),
            "logs": self.cleanup_logs(dry_run),
            "s3": self.cleanup_s3(dry_run=dry_run),
            "restore_dir": self.cleanup_restore_directory(dry_run)
        }
        
        # Calculate totals
        total_deleted = sum(result.get("deleted_count", 0) for result in results.values())
        total_errors = sum(len(result.get("errors", [])) for result in results.values())
        
        results["summary"] = {
            "total_deleted": total_deleted,
            "total_errors": total_errors,
            "all_successful": all(result.get("success", False) for result in results.values())
        }
        
        return results
    
    def get_cleanup_stats(self) -> Dict[str, Any]:
        """Get statistics about cleanup opportunities
        
        Returns:
            Dictionary containing cleanup statistics
        """
        stats = {
            "temp_files": self._count_temp_files(),
            "old_backups": self._count_old_backups(),
            "old_logs": self._count_old_logs(),
            "restore_files": self._count_restore_files()
        }
        
        return stats
    
    def _cleanup_directory_temp_files(self, directory: Path, results: Dict[str, Any], dry_run: bool) -> None:
        """Clean up temp files in a specific directory"""
        for pattern in self.temp_file_patterns:
            for temp_file in directory.glob(pattern):
                try:
                    if not dry_run:
                        temp_file.unlink()
                        results["deleted_files"].append(str(temp_file))
                        results["deleted_count"] += 1
                    else:
                        results["deleted_files"].append(str(temp_file))
                        results["deleted_count"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete {temp_file.name}: {e}")
    
    def _count_temp_files(self) -> int:
        """Count temporary files in project"""
        count = 0
        for pattern in self.temp_file_patterns:
            for file_path in self.project_root.rglob(pattern):
                if file_path.is_file():
                    count += 1
        return count
    
    def _count_old_backups(self) -> int:
        """Count old backup files"""
        count = 0
        backup_dir = self.project_root / "backups"
        if backup_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=self.backup_retention_days)
            for backup_file in backup_dir.glob("*.tar.gz"):
                try:
                    stat = backup_file.stat()
                    file_date = datetime.fromtimestamp(stat.st_mtime)
                    if file_date < cutoff_date:
                        count += 1
                except Exception:
                    pass
        return count
    
    def _count_old_logs(self) -> int:
        """Count old log files"""
        count = 0
        logs_dir = self.project_root / "logs"
        if logs_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=self.log_retention_days)
            for log_file in logs_dir.glob("*.log"):
                try:
                    stat = log_file.stat()
                    file_date = datetime.fromtimestamp(stat.st_mtime)
                    if file_date < cutoff_date:
                        count += 1
                except Exception:
                    pass
        return count
    
    def _count_restore_files(self) -> int:
        """Count files in restore directory"""
        count = 0
        restore_dir = self.project_root / "restore"
        if restore_dir.exists():
            for item in restore_dir.iterdir():
                if item.is_file():
                    count += 1
                elif item.is_dir():
                    count += len(list(item.rglob("*")))
        return count


def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(description="Cleanup Manager CLI")
    parser.add_argument("--temp-files", action="store_true", help="Clean up temporary files")
    parser.add_argument("--old-backups", action="store_true", help="Clean up old backup files")
    parser.add_argument("--logs", action="store_true", help="Clean up old log files")
    parser.add_argument("--s3", action="store_true", help="Clean up S3 objects")
    parser.add_argument("--restore-dir", action="store_true", help="Clean up restore directory")
    parser.add_argument("--all", action="store_true", help="Run all cleanup operations")
    parser.add_argument("--stats", action="store_true", help="Show cleanup statistics")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be cleaned without actually cleaning")
    parser.add_argument("--bucket", type=str, help="S3 bucket name for cleanup")
    
    args = parser.parse_args()
    
    cleanup_manager = CleanupManager()
    
    if args.stats:
        print("📊 Cleanup Statistics:")
        stats = cleanup_manager.get_cleanup_stats()
        print(f"  🗂️  Temp files: {stats['temp_files']}")
        print(f"  📦 Old backups: {stats['old_backups']}")
        print(f"  📋 Old logs: {stats['old_logs']}")
        print(f"  🔄 Restore files: {stats['restore_files']}")
    
    elif args.temp_files:
        print("🧹 Cleaning up temporary files...")
        results = cleanup_manager.cleanup_temp_files(args.dry_run)
        if results["success"]:
            print(f"✅ Temp file cleanup completed: {results['deleted_count']} files")
        else:
            print(f"❌ Temp file cleanup failed: {results['errors']}")
    
    elif args.old_backups:
        print("🗑️ Cleaning up old backups...")
        results = cleanup_manager.cleanup_old_backups(args.dry_run)
        if results["success"]:
            print(f"✅ Old backup cleanup completed: {results['deleted_count']} files")
        else:
            print(f"❌ Old backup cleanup failed: {results['errors']}")
    
    elif args.logs:
        print("📋 Cleaning up old logs...")
        results = cleanup_manager.cleanup_logs(args.dry_run)
        if results["success"]:
            print(f"✅ Log cleanup completed: {results['deleted_count']} files")
        else:
            print(f"❌ Log cleanup failed: {results['errors']}")
    
    elif args.s3:
        print("☁️ Cleaning up S3 objects...")
        results = cleanup_manager.cleanup_s3(args.bucket, args.dry_run)
        if results["success"]:
            print(f"✅ S3 cleanup completed: {results['deleted_count']} objects")
        else:
            print(f"❌ S3 cleanup failed: {results['errors']}")
    
    elif args.restore_dir:
        print("🔄 Cleaning up restore directory...")
        results = cleanup_manager.cleanup_restore_directory(args.dry_run)
        if results["success"]:
            print(f"✅ Restore directory cleanup completed: {results['deleted_count']} files")
        else:
            print(f"❌ Restore directory cleanup failed: {results['errors']}")
    
    elif args.all:
        print("🧹 Running all cleanup operations...")
        results = cleanup_manager.cleanup_all(args.dry_run)
        
        summary = results["summary"]
        if summary["all_successful"]:
            print(f"✅ All cleanup operations completed: {summary['total_deleted']} items cleaned")
        else:
            print(f"❌ Some cleanup operations failed: {summary['total_errors']} errors")
        
        # Print detailed results
        for operation, result in results.items():
            if operation != "summary":
                status = "✅" if result.get("success", False) else "❌"
                print(f"  {status} {operation}: {result.get('deleted_count', 0)} items")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 