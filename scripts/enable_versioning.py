#!/usr/bin/env python3
"""
Enable S3 Bucket Versioning Script

This script enables versioning on S3 buckets for data protection and recovery.
Designed for AWS certification study with practical implementation.

AWS Concepts Covered:
- S3 Bucket Versioning: Data protection and recovery capabilities
- S3 Lifecycle Management: Cost optimization with versioned objects
- IAM Permissions: Required permissions for versioning operations
- Security Best Practices: MFA delete protection for critical data

Usage:
    python scripts/enable_versioning.py --bucket my-bucket-name
    python scripts/enable_versioning.py --bucket my-bucket-name --mfa-delete
    python scripts/enable_versioning.py --bucket my-bucket-name --mfa-serial arn:aws:iam::123456789012:mfa/user
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from scripts.security_manager import SecurityManager
from scripts.logger import SyncLogger


class VersioningManager:
    """Manages S3 bucket versioning operations"""
    
    def __init__(self):
        """Initialize versioning manager"""
        self.security_manager = SecurityManager()
        self.logger = SyncLogger("versioning")
    
    def enable_versioning(self, bucket_name: str, mfa_delete: bool = False, 
                         mfa_serial: str = None) -> bool:
        """Enable versioning on an S3 bucket
        
        Args:
            bucket_name: Name of the S3 bucket
            mfa_delete: Whether to enable MFA delete protection
            mfa_serial: MFA device serial number (required if mfa_delete=True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.log_info(f"Enabling versioning for bucket: {bucket_name}")
            
            # Enable versioning using security manager
            success = self.security_manager.enable_bucket_versioning(
                bucket_name, mfa_delete, mfa_serial
            )
            
            if success:
                self.logger.log_info(f"✅ Versioning enabled successfully for bucket: {bucket_name}")
                if mfa_delete:
                    self.logger.log_info("MFA delete protection enabled")
                return True
            else:
                self.logger.log_error(f"Failed to enable versioning for bucket: {bucket_name}")
                return False
                
        except Exception as e:
            self.logger.log_error(e, f"Error enabling versioning for bucket: {bucket_name}")
            return False
    
    def check_versioning_status(self, bucket_name: str) -> dict:
        """Check current versioning status of a bucket
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            Dictionary containing versioning status information
        """
        try:
            status = self.security_manager.get_security_status(bucket_name)
            return {
                'versioning_enabled': status.get('versioning_enabled', False),
                'mfa_delete_enabled': status.get('mfa_delete_enabled', False),
                'bucket_name': bucket_name
            }
        except Exception as e:
            self.logger.log_error(e, f"Error checking versioning status for bucket: {bucket_name}")
            return {
                'versioning_enabled': False,
                'mfa_delete_enabled': False,
                'bucket_name': bucket_name,
                'error': str(e)
            }
    
    def print_versioning_info(self, bucket_name: str):
        """Print educational information about S3 versioning"""
        print("\n📚 S3 Bucket Versioning - AWS Certification Concepts")
        print("=" * 60)
        print("🔍 What is S3 Versioning?")
        print("   - Protects against accidental deletion and overwrites")
        print("   - Maintains multiple versions of the same object")
        print("   - Enables point-in-time recovery of data")
        print("   - Important for compliance and data governance")
        
        print("\n💰 Cost Considerations:")
        print("   - Each version of an object incurs storage costs")
        print("   - Use lifecycle policies to manage version costs")
        print("   - Consider transitioning old versions to cheaper storage")
        
        print("\n🔐 Security Features:")
        print("   - MFA Delete: Requires MFA to permanently delete versions")
        print("   - Access Control: IAM policies control version access")
        print("   - Encryption: Versions inherit bucket encryption settings")
        
        print("\n⚡ AWS Certification Topics:")
        print("   - S3 Storage Classes and Lifecycle Management")
        print("   - Data Protection and Recovery Strategies")
        print("   - Security and Compliance Best Practices")
        print("   - Cost Optimization and Management")


def main():
    """Main function for versioning management"""
    parser = argparse.ArgumentParser(
        description="Enable S3 bucket versioning for data protection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enable basic versioning
  python scripts/enable_versioning.py --bucket my-photo-bucket
  
  # Enable versioning with MFA delete protection
  python scripts/enable_versioning.py --bucket my-photo-bucket --mfa-delete --mfa-serial arn:aws:iam::123456789012:mfa/user
  
  # Check current versioning status
  python scripts/enable_versioning.py --bucket my-photo-bucket --check-status
        """
    )
    
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name to enable versioning on"
    )
    
    parser.add_argument(
        "--mfa-delete",
        action="store_true",
        help="Enable MFA delete protection (requires --mfa-serial)"
    )
    
    parser.add_argument(
        "--mfa-serial",
        help="MFA device serial number (required with --mfa-delete)"
    )
    
    parser.add_argument(
        "--check-status",
        action="store_true",
        help="Check current versioning status without making changes"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Validate MFA arguments
    if args.mfa_delete and not args.mfa_serial:
        print("❌ Error: --mfa-serial is required when using --mfa-delete")
        sys.exit(1)
    
    # Create versioning manager
    manager = VersioningManager()
    
    # Print educational information
    manager.print_versioning_info(args.bucket)
    
    if args.check_status:
        # Check current status
        print(f"\n🔍 Checking versioning status for bucket: {args.bucket}")
        status = manager.check_versioning_status(args.bucket)
        
        print(f"\n📊 Versioning Status:")
        print(f"   Bucket: {status['bucket_name']}")
        print(f"   Versioning Enabled: {'✅' if status['versioning_enabled'] else '❌'}")
        print(f"   MFA Delete Enabled: {'✅' if status['mfa_delete_enabled'] else '❌'}")
        
        if 'error' in status:
            print(f"   Error: {status['error']}")
        
        if status['versioning_enabled']:
            print("\n💡 Versioning is already enabled on this bucket")
        else:
            print("\n💡 Versioning is not enabled. Use --bucket without --check-status to enable it")
        
    else:
        # Enable versioning
        print(f"\n🚀 Enabling versioning for bucket: {args.bucket}")
        
        success = manager.enable_versioning(
            args.bucket, 
            mfa_delete=args.mfa_delete,
            mfa_serial=args.mfa_serial
        )
        
        if success:
            print(f"\n✅ Versioning enabled successfully for bucket: {args.bucket}")
            
            if args.mfa_delete:
                print("🔐 MFA delete protection enabled")
                print("   Note: You'll need MFA to permanently delete versions")
            
            print("\n📋 Next Steps:")
            print("   1. Configure lifecycle policies to manage version costs")
            print("   2. Test versioning by uploading and overwriting files")
            print("   3. Monitor storage costs for versioned objects")
            print("   4. Consider enabling cross-region replication for disaster recovery")
            
        else:
            print(f"\n❌ Failed to enable versioning for bucket: {args.bucket}")
            print("   Check your AWS credentials and bucket permissions")
            sys.exit(1)


if __name__ == "__main__":
    main() 