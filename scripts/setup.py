#!/usr/bin/env python3
"""
Setup Script for AWS S3 Sync Operations

This script provides comprehensive setup functionality including initial configuration,
environment preparation, and validation. Designed for AWS certification study with
practical setup implementation.

AWS Concepts Covered:
- Initial AWS setup and configuration
- Environment preparation and validation
- Security configuration and best practices
- Infrastructure setup and verification
- Configuration management and validation

Usage:
    python scripts/setup.py --init
    python scripts/setup.py --validate
    python scripts/setup.py --create-env dev
"""

import argparse
import json
import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.config_manager import ConfigManager, ConfigError
from scripts.logger import SyncLogger


class SetupManager:
    """Comprehensive setup manager for sync operations"""
    
    def __init__(self):
        """Initialize setup manager"""
        self.project_root = Path(__file__).parent.parent
        self.config_manager = ConfigManager()
        self.logger = SyncLogger("setup")
        
        # Setup directories
        self.directories = [
            "data",
            "logs", 
            "backups",
            "config/backups",
            "templates",
            "tests"
        ]
    
    def initialize_project(self) -> bool:
        """Initialize project structure and configuration
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.log_info("Starting project initialization")
            
            # Create directories
            self._create_directories()
            
            # Create default configuration files
            self._create_default_configs()
            
            # Validate AWS credentials
            aws_errors = self.config_manager.validate_aws_credentials()
            if aws_errors:
                self.logger.log_warning(f"AWS credential issues found: {aws_errors}")
                print("⚠️  AWS credential issues detected. Please configure AWS credentials.")
            else:
                self.logger.log_info("AWS credentials validated successfully")
            
            # Test S3 access
            if self._test_s3_access():
                self.logger.log_info("S3 access verified successfully")
            else:
                self.logger.log_warning("S3 access test failed")
            
            self.logger.log_info("Project initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.log_error(e, "Project initialization failed")
            return False
    
    def validate_setup(self) -> Dict[str, Any]:
        """Validate current setup and configuration
        
        Returns:
            Dictionary containing validation results
        """
        results = {
            "directories": self._validate_directories(),
            "config_files": self._validate_config_files(),
            "aws_credentials": self._validate_aws_credentials(),
            "s3_access": {"valid": self._test_s3_access(), "errors": []},
            "permissions": self._validate_permissions()
        }
        
        # Log validation results
        for component, status in results.items():
            if status.get("valid", False):
                self.logger.log_info(f"{component} validation passed")
            else:
                self.logger.log_warning(f"{component} validation failed: {status.get('errors', [])}")
        
        return results
    
    def create_environment(self, environment: str) -> bool:
        """Create environment-specific configuration
        
        Args:
            environment: Environment name (dev, staging, prod)
            
        Returns:
            True if environment creation successful, False otherwise
        """
        try:
            self.logger.log_info(f"Creating environment configuration for {environment}")
            
            # Load base configuration
            base_config = self.config_manager.load_config()
            
            # Create environment-specific configuration
            env_config = self.config_manager.create_environment_config(environment, base_config)
            
            # Save environment configuration
            self.config_manager.save_config(env_config)
            
            # Create environment-specific directories
            self._create_environment_directories(environment)
            
            self.logger.log_info(f"Environment {environment} created successfully")
            return True
            
        except Exception as e:
            self.logger.log_error(e, f"Failed to create environment {environment}")
            return False
    
    def _create_directories(self) -> None:
        """Create required project directories"""
        for directory in self.directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            self.logger.log_info(f"Created directory: {directory}")
    
    def _create_default_configs(self) -> None:
        """Create default configuration files if they don't exist"""
        config_dir = self.project_root / "config"
        
        # Create default AWS config if it doesn't exist
        aws_config_path = config_dir / "aws-config.json"
        if not aws_config_path.exists():
            default_aws_config = {
                "aws": {
                    "region": "us-east-1",
                    "profile": "default",
                    "credentials_file": "config/aws-credentials.json"
                },
                "s3": {
                    "bucket_name": "your-sync-bucket",
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
                    "exclude_patterns": ["*.tmp", "*.log", ".DS_Store"],
                    "include_patterns": ["*"],
                    "max_concurrent_uploads": 5,
                    "chunk_size_mb": 100,
                    "retry_attempts": 3,
                    "dry_run": False
                }
            }
            
            with open(aws_config_path, 'w') as f:
                json.dump(default_aws_config, f, indent=2)
            
            self.logger.log_info("Created default AWS configuration")
        
        # Create default sync config if it doesn't exist
        sync_config_path = config_dir / "sync-config.json"
        if not sync_config_path.exists():
            default_sync_config = {
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
                    "exclude_extensions": [".tmp", ".log", ".DS_Store"],
                    "exclude_directories": [".git", "__pycache__", "node_modules"],
                    "exclude_files": ["Thumbs.db", ".DS_Store", "desktop.ini"]
                }
            }
            
            with open(sync_config_path, 'w') as f:
                json.dump(default_sync_config, f, indent=2)
            
            self.logger.log_info("Created default sync configuration")
    
    def _validate_directories(self) -> Dict[str, Any]:
        """Validate that required directories exist"""
        results = {"valid": True, "errors": []}
        
        for directory in self.directories:
            dir_path = self.project_root / directory
            if not dir_path.exists():
                results["valid"] = False
                results["errors"].append(f"Directory missing: {directory}")
        
        return results
    
    def _validate_config_files(self) -> Dict[str, Any]:
        """Validate configuration files"""
        results = {"valid": True, "errors": []}
        
        try:
            config = self.config_manager.load_config()
            errors = self.config_manager.validate_config(config)
            
            if errors:
                results["valid"] = False
                results["errors"] = errors
                
        except Exception as e:
            results["valid"] = False
            results["errors"].append(str(e))
        
        return results
    
    def _validate_aws_credentials(self) -> Dict[str, Any]:
        """Validate AWS credentials"""
        results = {"valid": True, "errors": []}
        
        try:
            errors = self.config_manager.validate_aws_credentials()
            if errors:
                results["valid"] = False
                results["errors"] = errors
                
        except Exception as e:
            results["valid"] = False
            results["errors"].append(str(e))
        
        return results
    
    def _test_s3_access(self) -> bool:
        """Test S3 bucket access"""
        try:
            config = self.config_manager.load_config("aws")
            bucket_name = config["aws"]["s3"]["bucket_name"]
            
            # Skip test if bucket name is placeholder
            if bucket_name == "your-sync-bucket":
                return True
            
            session = boto3.Session()
            s3 = session.client('s3')
            s3.head_bucket(Bucket=bucket_name)
            return True
            
        except Exception:
            return False
    
    def _validate_permissions(self) -> Dict[str, Any]:
        """Validate file and directory permissions"""
        results = {"valid": True, "errors": []}
        
        # Check if config directory is writable
        config_dir = self.project_root / "config"
        if not os.access(config_dir, os.W_OK):
            results["valid"] = False
            results["errors"].append("Config directory not writable")
        
        # Check if logs directory is writable
        logs_dir = self.project_root / "logs"
        if not os.access(logs_dir, os.W_OK):
            results["valid"] = False
            results["errors"].append("Logs directory not writable")
        
        return results
    
    def _create_environment_directories(self, environment: str) -> None:
        """Create environment-specific directories"""
        env_dirs = [
            f"data/{environment}",
            f"logs/{environment}",
            f"backups/{environment}"
        ]
        
        for directory in env_dirs:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            self.logger.log_info(f"Created environment directory: {directory}")


def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="Setup Manager CLI")
    parser.add_argument("--init", action="store_true", help="Initialize project structure")
    parser.add_argument("--validate", action="store_true", help="Validate current setup")
    parser.add_argument("--create-env", type=str, help="Create environment configuration")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    setup_manager = SetupManager()
    
    if args.init:
        print("🚀 Initializing project structure...")
        if setup_manager.initialize_project():
            print("✅ Project initialization completed successfully")
        else:
            print("❌ Project initialization failed")
            sys.exit(1)
    
    elif args.validate:
        print("🔍 Validating setup...")
        results = setup_manager.validate_setup()
        
        # Print validation results
        all_valid = all(result.get("valid", False) for result in results.values())
        
        if all_valid:
            print("✅ All setup components are valid")
        else:
            print("❌ Setup validation found issues:")
            for component, result in results.items():
                if not result.get("valid", False):
                    print(f"  - {component}: {result.get('errors', [])}")
    
    elif args.create_env:
        print(f"🌍 Creating environment: {args.create_env}")
        if setup_manager.create_environment(args.create_env):
            print(f"✅ Environment {args.create_env} created successfully")
        else:
            print(f"❌ Failed to create environment {args.create_env}")
            sys.exit(1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 