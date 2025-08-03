#!/usr/bin/env python3
"""
Configuration Management Module for AWS S3 Sync Operations

This module provides comprehensive configuration management including validation,
environment-specific configs, and migration utilities. Designed for AWS certification
study with practical configuration management implementation.

AWS Concepts Covered:
- Configuration management for AWS services
- Environment-specific configurations
- Configuration validation and security
- Configuration migration and versioning
- Best practices for configuration management

Usage:
    from config.config_manager import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.load_config()
    config_manager.validate_config(config)
    config_manager.migrate_config(old_config, new_schema)
"""

import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import jsonschema
from jsonschema import ValidationError
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

class ConfigManager:
    """Comprehensive configuration manager for sync operations"""
    
    def __init__(self, config_dir: str = "config"):
        """Initialize configuration manager"""
        self.config_dir = Path(config_dir)
        self.project_root = Path(__file__).parent.parent
        
        # Configuration file paths
        self.aws_config_path = self.config_dir / "aws-config.json"
        self.sync_config_path = self.config_dir / "sync-config.json"
        self.credentials_path = self.config_dir / "aws-credentials.json"
        
        # Backup directory
        self.backup_dir = self.config_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Schema definitions for validation
        self._load_schemas()
    
    def _load_schemas(self):
        """Load JSON schemas for configuration validation"""
        self.aws_schema = {
            "type": "object",
            "properties": {
                "aws": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                        "profile": {"type": "string"},
                        "credentials_file": {"type": "string"}
                    },
                    "required": ["region", "profile"]
                },
                "s3": {
                    "type": "object",
                    "properties": {
                        "bucket_name": {"type": "string", "pattern": "^[a-z0-9.-]+$"},
                        "sync_path": {"type": "string"},
                        "storage_class": {
                            "type": "string",
                            "enum": ["STANDARD", "STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING", "GLACIER", "DEEP_ARCHIVE"]
                        },
                        "encryption": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                                "algorithm": {"type": "string", "enum": ["AES256", "aws:kms"]}
                            },
                            "required": ["enabled"]
                        },
                        "versioning": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"}
                            },
                            "required": ["enabled"]
                        }
                    },
                    "required": ["bucket_name", "storage_class", "encryption", "versioning"]
                },
                "sync": {
                    "type": "object",
                    "properties": {
                        "local_path": {"type": "string"},
                        "exclude_patterns": {"type": "array", "items": {"type": "string"}},
                        "include_patterns": {"type": "array", "items": {"type": "string"}},
                        "max_concurrent_uploads": {"type": "integer", "minimum": 1, "maximum": 50},
                        "chunk_size_mb": {"type": "integer", "minimum": 1, "maximum": 5000},
                        "retry_attempts": {"type": "integer", "minimum": 0, "maximum": 10},
                        "dry_run": {"type": "boolean"}
                    },
                    "required": ["local_path", "exclude_patterns", "include_patterns"]
                }
            },
            "required": ["aws", "s3", "sync"]
        }
        
        self.sync_schema = {
            "type": "object",
            "properties": {
                "sync_settings": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": ["incremental", "full", "mirror"]},
                        "dry_run": {"type": "boolean"},
                        "force_sync": {"type": "boolean"},
                        "delete_remote": {"type": "boolean"},
                        "preserve_timestamps": {"type": "boolean"},
                        "verify_checksums": {"type": "boolean"}
                    },
                    "required": ["mode", "dry_run", "force_sync", "delete_remote"]
                },
                "file_handling": {
                    "type": "object",
                    "properties": {
                        "max_file_size": {"type": "integer", "minimum": 1},
                        "chunk_size": {"type": "integer", "minimum": 1024},
                        "concurrent_uploads": {"type": "integer", "minimum": 1, "maximum": 20},
                        "timeout": {"type": "integer", "minimum": 30},
                        "retry_attempts": {"type": "integer", "minimum": 0, "maximum": 10},
                        "retry_delay": {"type": "integer", "minimum": 1}
                    },
                    "required": ["max_file_size", "chunk_size", "concurrent_uploads", "timeout"]
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "include_extensions": {"type": "array", "items": {"type": "string"}},
                        "exclude_extensions": {"type": "array", "items": {"type": "string"}},
                        "exclude_directories": {"type": "array", "items": {"type": "string"}},
                        "exclude_files": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["include_extensions", "exclude_extensions", "exclude_directories", "exclude_files"]
                }
            },
            "required": ["sync_settings", "file_handling", "filters"]
        }
    
    def load_config(self, config_type: str = "all") -> Dict[str, Any]:
        """Load configuration files
        
        Args:
            config_type: "aws", "sync", or "all"
            
        Returns:
            Dictionary containing configuration data
        """
        config = {}
        
        if config_type in ["aws", "all"]:
            if self.aws_config_path.exists():
                try:
                    with open(self.aws_config_path, 'r') as f:
                        config["aws"] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    raise ConfigError(f"Failed to load AWS config: {e}")
            else:
                raise ConfigError(f"AWS config file not found: {self.aws_config_path}")
        
        if config_type in ["sync", "all"]:
            if self.sync_config_path.exists():
                try:
                    with open(self.sync_config_path, 'r') as f:
                        config["sync"] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    raise ConfigError(f"Failed to load sync config: {e}")
            else:
                raise ConfigError(f"Sync config file not found: {self.sync_config_path}")
        
        return config
    
    def save_config(self, config: Dict[str, Any], config_type: str = "all") -> None:
        """Save configuration to files
        
        Args:
            config: Configuration dictionary
            config_type: "aws", "sync", or "all"
        """
        # Create backup before saving
        self._create_backup()
        
        if config_type in ["aws", "all"] and "aws" in config:
            try:
                with open(self.aws_config_path, 'w') as f:
                    json.dump(config["aws"], f, indent=2)
            except IOError as e:
                raise ConfigError(f"Failed to save AWS config: {e}")
        
        if config_type in ["sync", "all"] and "sync" in config:
            try:
                with open(self.sync_config_path, 'w') as f:
                    json.dump(config["sync"], f, indent=2)
            except IOError as e:
                raise ConfigError(f"Failed to save sync config: {e}")
    
    def validate_config(self, config: Dict[str, Any], config_type: str = "all") -> List[str]:
        """Validate configuration against schemas
        
        Args:
            config: Configuration dictionary
            config_type: "aws", "sync", or "all"
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if config_type in ["aws", "all"] and "aws" in config:
            try:
                jsonschema.validate(config["aws"], self.aws_schema)
            except ValidationError as e:
                errors.append(f"AWS config validation error: {e.message}")
        
        if config_type in ["sync", "all"] and "sync" in config:
            try:
                jsonschema.validate(config["sync"], self.sync_schema)
            except ValidationError as e:
                errors.append(f"Sync config validation error: {e.message}")
        
        return errors
    
    def create_environment_config(self, environment: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create environment-specific configuration
        
        Args:
            environment: Environment name (dev, staging, prod)
            base_config: Base configuration dictionary
            
        Returns:
            Environment-specific configuration
        """
        env_config = self._deep_copy_config(base_config)
        
        # Environment-specific overrides
        if environment == "dev":
            env_config["aws"]["s3"]["bucket_name"] = f"{env_config['aws']['s3']['bucket_name']}-dev"
            env_config["sync"]["sync_settings"]["dry_run"] = True
            env_config["sync"]["file_handling"]["concurrent_uploads"] = 2
        
        elif environment == "staging":
            env_config["aws"]["s3"]["bucket_name"] = f"{env_config['aws']['s3']['bucket_name']}-staging"
            env_config["sync"]["sync_settings"]["dry_run"] = False
            env_config["sync"]["file_handling"]["concurrent_uploads"] = 5
        
        elif environment == "prod":
            env_config["sync"]["sync_settings"]["dry_run"] = False
            env_config["sync"]["file_handling"]["concurrent_uploads"] = 10
            env_config["sync"]["file_handling"]["retry_attempts"] = 5
        
        return env_config
    
    def migrate_config(self, old_config: Dict[str, Any], target_version: str) -> Dict[str, Any]:
        """Migrate configuration to new version
        
        Args:
            old_config: Old configuration dictionary
            target_version: Target version string
            
        Returns:
            Migrated configuration
        """
        migrated_config = self._deep_copy_config(old_config)
        
        # Version-specific migrations
        if target_version == "2.0":
            # Add new required fields with defaults
            if "aws" in migrated_config:
                if "monitoring" not in migrated_config["aws"]:
                    migrated_config["aws"]["monitoring"] = {
                        "cloudwatch": {"enabled": True},
                        "logging": {"level": "INFO"}
                    }
            
            if "sync" in migrated_config:
                if "performance" not in migrated_config["sync"]:
                    migrated_config["sync"]["performance"] = {
                        "buffer_size": 8192,
                        "enable_compression": False
                    }
        
        return migrated_config
    
    def _create_backup(self) -> None:
        """Create backup of current configuration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for config_file in [self.aws_config_path, self.sync_config_path]:
            if config_file.exists():
                backup_path = self.backup_dir / f"{config_file.stem}_{timestamp}.json"
                shutil.copy2(config_file, backup_path)
    
    def _deep_copy_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create deep copy of configuration dictionary"""
        return json.loads(json.dumps(config))
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get information about current configuration files"""
        info = {
            "config_directory": str(self.config_dir),
            "files": {},
            "backups": []
        }
        
        for config_file in [self.aws_config_path, self.sync_config_path]:
            if config_file.exists():
                stat = config_file.stat()
                info["files"][config_file.name] = {
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "exists": True
                }
            else:
                info["files"][config_file.name] = {"exists": False}
        
        # List backup files
        for backup_file in self.backup_dir.glob("*.json"):
            stat = backup_file.stat()
            info["backups"].append({
                "name": backup_file.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        
        return info
    
    def restore_backup(self, backup_name: str) -> bool:
        """Restore configuration from backup
        
        Args:
            backup_name: Name of backup file to restore
            
        Returns:
            True if restore successful, False otherwise
        """
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            return False
        
        try:
            # Create current backup before restoring
            self._create_backup()
            
            # Determine which config file to restore
            if "aws-config" in backup_name:
                shutil.copy2(backup_path, self.aws_config_path)
            elif "sync-config" in backup_name:
                shutil.copy2(backup_path, self.sync_config_path)
            else:
                return False
            
            return True
        except Exception:
            return False
    
    def validate_aws_credentials(self) -> List[str]:
        """Validate AWS credentials and permissions
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        try:
            # Test AWS credentials
            session = boto3.Session()
            sts = session.client('sts')
            sts.get_caller_identity()
        except NoCredentialsError:
            errors.append("AWS credentials not found")
        except ClientError as e:
            errors.append(f"AWS credentials error: {e}")
        
        # Test S3 access
        try:
            config = self.load_config("aws")
            bucket_name = config["aws"]["s3"]["bucket_name"]
            s3 = session.client('s3')
            s3.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            errors.append(f"S3 bucket access error: {e}")
        except Exception as e:
            errors.append(f"Configuration error: {e}")
        
        return errors

class ConfigError(Exception):
    """Configuration management error"""
    pass

def create_config_manager(config_dir: str = "config") -> ConfigManager:
    """Factory function to create configuration manager"""
    return ConfigManager(config_dir)

def main():
    """Main CLI function for configuration management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Configuration Manager CLI")
    parser.add_argument("--validate", action="store_true", help="Validate current configuration")
    parser.add_argument("--info", action="store_true", help="Show configuration information")
    parser.add_argument("--create-env", type=str, help="Create environment-specific config")
    parser.add_argument("--migrate", type=str, help="Migrate to specified version")
    parser.add_argument("--restore", type=str, help="Restore from backup")
    
    args = parser.parse_args()
    
    config_manager = ConfigManager()
    
    if args.validate:
        try:
            config = config_manager.load_config()
            errors = config_manager.validate_config(config)
            if errors:
                print("Configuration validation errors:")
                for error in errors:
                    print(f"  - {error}")
            else:
                print("Configuration is valid")
        except Exception as e:
            print(f"Validation failed: {e}")
    
    elif args.info:
        info = config_manager.get_config_info()
        print(json.dumps(info, indent=2))
    
    elif args.create_env:
        try:
            config = config_manager.load_config()
            env_config = config_manager.create_environment_config(args.create_env, config)
            config_manager.save_config(env_config)
            print(f"Environment config created for {args.create_env}")
        except Exception as e:
            print(f"Failed to create environment config: {e}")
    
    elif args.migrate:
        try:
            config = config_manager.load_config()
            migrated_config = config_manager.migrate_config(config, args.migrate)
            config_manager.save_config(migrated_config)
            print(f"Configuration migrated to version {args.migrate}")
        except Exception as e:
            print(f"Migration failed: {e}")
    
    elif args.restore:
        if config_manager.restore_backup(args.restore):
            print(f"Configuration restored from {args.restore}")
        else:
            print(f"Failed to restore from {args.restore}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 