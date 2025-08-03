#!/usr/bin/env python3
"""
Validation Script for AWS S3 Sync Operations

This script provides comprehensive validation functionality including configuration
validation, credential verification, and system requirement checks. Designed for
AWS certification study with practical validation implementation.

AWS Concepts Covered:
- Configuration validation and verification
- AWS credential and permission validation
- S3 bucket access and permissions
- Security configuration validation
- System requirement verification

Usage:
    python scripts/validate.py --config
    python scripts/validate.py --credentials
    python scripts/validate.py --all
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.config_manager import ConfigManager, ConfigError
from scripts.logger import SyncLogger


class ValidationManager:
    """Comprehensive validation manager for sync operations"""
    
    def __init__(self):
        """Initialize validation manager"""
        self.project_root = Path(__file__).parent.parent
        self.config_manager = ConfigManager()
        self.logger = SyncLogger("validation")
        
        # Validation categories
        self.validation_categories = {
            "config": self._validate_configuration,
            "credentials": self._validate_credentials,
            "permissions": self._validate_permissions,
            "system": self._validate_system_requirements,
            "network": self._validate_network_connectivity,
            "storage": self._validate_storage_access
        }
    
    def validate_all(self) -> Dict[str, Any]:
        """Run all validation checks
        
        Returns:
            Dictionary containing all validation results
        """
        results = {}
        
        for category, validator in self.validation_categories.items():
            self.logger.log_info(f"Running {category} validation")
            results[category] = validator()
        
        return results
    
    def validate_category(self, category: str) -> Dict[str, Any]:
        """Run validation for specific category
        
        Args:
            category: Validation category name
            
        Returns:
            Dictionary containing validation results
        """
        if category not in self.validation_categories:
            return {"valid": False, "errors": [f"Unknown validation category: {category}"]}
        
        return self.validation_categories[category]()
    
    def _validate_configuration(self) -> Dict[str, Any]:
        """Validate configuration files and settings"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        try:
            # Load and validate configuration
            config = self.config_manager.load_config()
            validation_errors = self.config_manager.validate_config(config)
            
            if validation_errors:
                results["valid"] = False
                results["errors"].extend(validation_errors)
            else:
                results["details"] = {
                    "aws_config_loaded": True,
                    "sync_config_loaded": True,
                    "config_files_valid": True
                }
                
        except ConfigError as e:
            results["valid"] = False
            results["errors"].append(f"Configuration error: {e}")
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Unexpected error: {e}")
        
        return results
    
    def _validate_credentials(self) -> Dict[str, Any]:
        """Validate AWS credentials and permissions"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        try:
            # Test AWS credentials
            session = boto3.Session()
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            
            results["details"] = {
                "account_id": identity.get('Account'),
                "user_arn": identity.get('Arn'),
                "user_id": identity.get('UserId')
            }
            
            # Test S3 access
            config = self.config_manager.load_config("aws")
            bucket_name = config["aws"]["s3"]["bucket_name"]
            
            if bucket_name != "your-sync-bucket":
                try:
                    s3 = session.client('s3')
                    s3.head_bucket(Bucket=bucket_name)
                    results["details"]["s3_access"] = True
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'NoSuchBucket':
                        results["warnings"].append(f"S3 bucket '{bucket_name}' does not exist")
                    elif error_code == 'AccessDenied':
                        results["errors"].append(f"Access denied to S3 bucket '{bucket_name}'")
                        results["valid"] = False
                    else:
                        results["errors"].append(f"S3 access error: {e}")
                        results["valid"] = False
            else:
                results["warnings"].append("Using placeholder bucket name - update configuration")
                
        except NoCredentialsError:
            results["valid"] = False
            results["errors"].append("AWS credentials not found")
        except ClientError as e:
            results["valid"] = False
            results["errors"].append(f"AWS credentials error: {e}")
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Unexpected error: {e}")
        
        return results
    
    def _validate_permissions(self) -> Dict[str, Any]:
        """Validate file and directory permissions"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        # Check critical directories
        critical_dirs = [
            "config",
            "logs",
            "data",
            "backups"
        ]
        
        for directory in critical_dirs:
            dir_path = self.project_root / directory
            if not dir_path.exists():
                results["warnings"].append(f"Directory missing: {directory}")
            elif not os.access(dir_path, os.W_OK):
                results["errors"].append(f"Directory not writable: {directory}")
                results["valid"] = False
        
        # Check configuration files
        config_files = [
            "config/aws-config.json",
            "config/sync-config.json"
        ]
        
        for config_file in config_files:
            file_path = self.project_root / config_file
            if not file_path.exists():
                results["warnings"].append(f"Configuration file missing: {config_file}")
            elif not os.access(file_path, os.R_OK):
                results["errors"].append(f"Configuration file not readable: {config_file}")
                results["valid"] = False
        
        return results
    
    def _validate_system_requirements(self) -> Dict[str, Any]:
        """Validate system requirements"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 7):
            results["errors"].append("Python 3.7 or higher required")
            results["valid"] = False
        else:
            results["details"] = {
                "python_version": f"{python_version.major}.{python_version.minor}.{python_version.micro}"
            }
        
        # Check required packages
        required_packages = [
            "boto3",
            "botocore",
            "jsonschema"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            results["errors"].append(f"Missing required packages: {', '.join(missing_packages)}")
            results["valid"] = False
        
        # Check available disk space
        try:
            stat = os.statvfs(self.project_root)
            free_space_gb = (stat.f_frsize * stat.f_bavail) / (1024**3)
            results["details"]["free_space_gb"] = round(free_space_gb, 2)
            
            if free_space_gb < 1.0:
                results["warnings"].append("Low disk space (< 1GB)")
        except Exception:
            results["warnings"].append("Could not check disk space")
        
        return results
    
    def _validate_network_connectivity(self) -> Dict[str, Any]:
        """Validate network connectivity"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        # Test basic internet connectivity
        test_urls = [
            "https://www.google.com",
            "https://aws.amazon.com"
        ]
        
        import urllib.request
        import urllib.error
        
        for url in test_urls:
            try:
                urllib.request.urlopen(url, timeout=10)
                results["details"] = results.get("details", {})
                results["details"][f"connectivity_{url.split('//')[1]}"] = True
            except (urllib.error.URLError, urllib.error.HTTPError):
                results["warnings"].append(f"Cannot reach {url}")
            except Exception:
                results["warnings"].append(f"Network connectivity test failed for {url}")
        
        # Test AWS endpoint connectivity
        try:
            session = boto3.Session()
            sts = session.client('sts', region_name='us-east-1')
            sts.get_caller_identity()
            results["details"]["aws_connectivity"] = True
        except Exception:
            results["warnings"].append("Cannot connect to AWS services")
        
        return results
    
    def _validate_storage_access(self) -> Dict[str, Any]:
        """Validate storage access and configuration"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        try:
            config = self.config_manager.load_config("aws")
            local_path = config["aws"]["sync"]["local_path"]
            
            # Check if local path exists and is accessible
            local_path_obj = Path(local_path)
            if not local_path_obj.exists():
                try:
                    local_path_obj.mkdir(parents=True, exist_ok=True)
                    results["details"]["local_path_created"] = True
                except Exception as e:
                    results["errors"].append(f"Cannot create local path: {e}")
                    results["valid"] = False
            else:
                if not os.access(local_path_obj, os.R_OK | os.W_OK):
                    results["errors"].append(f"Local path not accessible: {local_path}")
                    results["valid"] = False
                else:
                    results["details"]["local_path_accessible"] = True
            
            # Check S3 bucket configuration
            bucket_name = config["aws"]["s3"]["bucket_name"]
            if bucket_name == "your-sync-bucket":
                results["warnings"].append("Using placeholder bucket name")
            else:
                results["details"]["bucket_configured"] = True
                
        except Exception as e:
            results["errors"].append(f"Storage validation error: {e}")
            results["valid"] = False
        
        return results
    
    def print_results(self, results: Dict[str, Any], category: str = None) -> None:
        """Print validation results in a formatted way
        
        Args:
            results: Validation results dictionary
            category: Specific category name (optional)
        """
        if category:
            print(f"\n🔍 {category.upper()} VALIDATION")
            print("=" * 50)
            
            if results.get("valid", False):
                print("✅ Validation passed")
            else:
                print("❌ Validation failed")
            
            if results.get("errors"):
                print("\nErrors:")
                for error in results["errors"]:
                    print(f"  ❌ {error}")
            
            if results.get("warnings"):
                print("\nWarnings:")
                for warning in results["warnings"]:
                    print(f"  ⚠️  {warning}")
            
            if results.get("details"):
                print("\nDetails:")
                for key, value in results["details"].items():
                    print(f"  📋 {key}: {value}")
        
        else:
            # Print all categories
            print("\n🔍 VALIDATION RESULTS")
            print("=" * 50)
            
            all_valid = True
            for cat, result in results.items():
                if not result.get("valid", False):
                    all_valid = False
                    break
            
            if all_valid:
                print("✅ All validations passed")
            else:
                print("❌ Some validations failed")
            
            for cat, result in results.items():
                status = "✅" if result.get("valid", False) else "❌"
                print(f"\n{status} {cat.upper()}")
                
                if result.get("errors"):
                    for error in result["errors"]:
                        print(f"  ❌ {error}")
                
                if result.get("warnings"):
                    for warning in result["warnings"]:
                        print(f"  ⚠️  {warning}")


def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(description="Validation Manager CLI")
    parser.add_argument("--config", action="store_true", help="Validate configuration")
    parser.add_argument("--credentials", action="store_true", help="Validate credentials")
    parser.add_argument("--permissions", action="store_true", help="Validate permissions")
    parser.add_argument("--system", action="store_true", help="Validate system requirements")
    parser.add_argument("--network", action="store_true", help="Validate network connectivity")
    parser.add_argument("--storage", action="store_true", help="Validate storage access")
    parser.add_argument("--all", action="store_true", help="Run all validations")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    validation_manager = ValidationManager()
    
    if args.all:
        print("🔍 Running all validations...")
        results = validation_manager.validate_all()
        validation_manager.print_results(results)
        
        # Exit with error code if any validation failed
        all_valid = all(result.get("valid", False) for result in results.values())
        sys.exit(0 if all_valid else 1)
    
    elif args.config:
        results = validation_manager.validate_category("config")
        validation_manager.print_results(results, "config")
    
    elif args.credentials:
        results = validation_manager.validate_category("credentials")
        validation_manager.print_results(results, "credentials")
    
    elif args.permissions:
        results = validation_manager.validate_category("permissions")
        validation_manager.print_results(results, "permissions")
    
    elif args.system:
        results = validation_manager.validate_category("system")
        validation_manager.print_results(results, "system")
    
    elif args.network:
        results = validation_manager.validate_category("network")
        validation_manager.print_results(results, "network")
    
    elif args.storage:
        results = validation_manager.validate_category("storage")
        validation_manager.print_results(results, "storage")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 