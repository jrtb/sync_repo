#!/usr/bin/env python3
"""
S3 Security Manager

Implements comprehensive security features for S3 buckets including encryption,
access logging, versioning, and MFA delete protection. This script helps
secure the photo sync tool's S3 buckets following AWS security best practices.

AWS Concepts Covered:
- S3 encryption at rest and in transit
- S3 bucket versioning and MFA delete
- S3 access logging and monitoring
- Security best practices
- Compliance requirements
"""

import boto3
import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages S3 bucket security features."""
    
    def __init__(self, aws_profile: Optional[str] = None):
        """Initialize the security manager.
        
        Args:
            aws_profile: AWS profile to use
        """
        self.session = boto3.Session(profile_name=aws_profile)
        self.s3_client = self.session.client('s3')
        
    def enable_encryption_at_rest(self, bucket_name: str, 
                                 encryption_type: str = 'AES256') -> bool:
        """Enable server-side encryption at rest.
        
        Args:
            bucket_name: Name of the S3 bucket
            encryption_type: Type of encryption (AES256 or aws:kms)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if encryption_type == 'AES256':
                encryption_config = {
                    'ServerSideEncryptionConfiguration': {
                        'Rules': [
                            {
                                'ApplyServerSideEncryptionByDefault': {
                                    'SSEAlgorithm': 'AES256'
                                }
                            }
                        ]
                    }
                }
            else:
                # For KMS encryption, you would specify a KMS key
                encryption_config = {
                    'ServerSideEncryptionConfiguration': {
                        'Rules': [
                            {
                                'ApplyServerSideEncryptionByDefault': {
                                    'SSEAlgorithm': 'aws:kms',
                                    'KMSMasterKeyID': encryption_type
                                }
                            }
                        ]
                    }
                }
                
            self.s3_client.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration=encryption_config['ServerSideEncryptionConfiguration']
            )
            
            logger.info(f"Enabled {encryption_type} encryption for bucket {bucket_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to enable encryption: {e}")
            return False
            
    def enable_bucket_versioning(self, bucket_name: str, mfa_delete: bool = False,
                                mfa_serial: Optional[str] = None) -> bool:
        """Enable bucket versioning with optional MFA delete.
        
        Args:
            bucket_name: Name of the S3 bucket
            mfa_delete: Whether to enable MFA delete
            mfa_serial: MFA device serial number (required if mfa_delete=True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            versioning_config = {
                'Status': 'Enabled'
            }
            
            if mfa_delete:
                if not mfa_serial:
                    logger.error("MFA serial number required when enabling MFA delete")
                    return False
                    
                versioning_config['MFADelete'] = 'Enabled'
                
            # Prepare the API call parameters
            api_params = {
                'Bucket': bucket_name,
                'VersioningConfiguration': versioning_config
            }
            
            # Only add MFA parameter if it's provided
            if mfa_delete and mfa_serial:
                api_params['MFA'] = mfa_serial
                
            self.s3_client.put_bucket_versioning(**api_params)
            
            logger.info(f"Enabled versioning for bucket {bucket_name}")
            if mfa_delete:
                logger.info("MFA delete protection enabled")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to enable versioning: {e}")
            return False
            
    def enable_access_logging(self, bucket_name: str, log_bucket: str,
                             log_prefix: str = 'logs/') -> bool:
        """Enable access logging for the bucket.
        
        Args:
            bucket_name: Name of the S3 bucket to log
            log_bucket: Name of the bucket to store logs
            log_prefix: Prefix for log files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logging_config = {
                'LoggingEnabled': {
                    'TargetBucket': log_bucket,
                    'TargetPrefix': log_prefix
                }
            }
            
            self.s3_client.put_bucket_logging(
                Bucket=bucket_name,
                BucketLoggingStatus=logging_config
            )
            
            logger.info(f"Enabled access logging for bucket {bucket_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to enable access logging: {e}")
            return False
            
    def configure_public_access_block(self, bucket_name: str) -> bool:
        """Configure public access block settings.
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            True if successful, False otherwise
        """
        try:
            public_access_block_config = {
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
            
            self.s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration=public_access_block_config
            )
            
            logger.info(f"Configured public access block for bucket {bucket_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to configure public access block: {e}")
            return False
            
    def enable_encryption_in_transit(self, bucket_name: str) -> bool:
        """Enforce encryption in transit by updating bucket policy.
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current bucket policy
            try:
                response = self.s3_client.get_bucket_policy(Bucket=bucket_name)
                current_policy = json.loads(response['Policy'])
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                    current_policy = {'Version': '2012-10-17', 'Statement': []}
                else:
                    raise
                    
            # Add TLS enforcement statement
            tls_statement = {
                'Sid': 'EnforceTLS',
                'Effect': 'Deny',
                'Principal': '*',
                'Action': 's3:*',
                'Resource': [
                    f'arn:aws:s3:::{bucket_name}',
                    f'arn:aws:s3:::{bucket_name}/*'
                ],
                'Condition': {
                    'Bool': {
                        'aws:SecureTransport': 'false'
                    }
                }
            }
            
            # Check if TLS statement already exists
            tls_exists = False
            for statement in current_policy['Statement']:
                if statement.get('Sid') == 'EnforceTLS':
                    tls_exists = True
                    break
                    
            if not tls_exists:
                current_policy['Statement'].append(tls_statement)
                
                # Apply updated policy
                self.s3_client.put_bucket_policy(
                    Bucket=bucket_name,
                    Policy=json.dumps(current_policy)
                )
                
                logger.info(f"Enforced TLS for bucket {bucket_name}")
                return True
            else:
                logger.info(f"TLS enforcement already configured for bucket {bucket_name}")
                return True
                
        except ClientError as e:
            logger.error(f"Failed to enforce TLS: {e}")
            return False
            
    def get_security_status(self, bucket_name: str) -> Dict[str, Any]:
        """Get the current security status of a bucket.
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            Dictionary containing security status
        """
        status = {
            'bucket_name': bucket_name,
            'encryption_enabled': False,
            'versioning_enabled': False,
            'mfa_delete_enabled': False,
            'access_logging_enabled': False,
            'public_access_blocked': False,
            'tls_enforced': False
        }
        
        try:
            # Check encryption
            try:
                response = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                status['encryption_enabled'] = True
                status['encryption_type'] = response['ServerSideEncryptionConfiguration']['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']
            except ClientError as e:
                if e.response['Error']['Code'] != 'ServerSideEncryptionConfigurationNotFoundError':
                    logger.warning(f"Error checking encryption: {e}")
                    
            # Check versioning
            try:
                response = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                if response.get('Status') == 'Enabled':
                    status['versioning_enabled'] = True
                    if response.get('MFADelete') == 'Enabled':
                        status['mfa_delete_enabled'] = True
            except ClientError as e:
                logger.warning(f"Error checking versioning: {e}")
                
            # Check access logging
            try:
                response = self.s3_client.get_bucket_logging(Bucket=bucket_name)
                if response.get('LoggingEnabled'):
                    status['access_logging_enabled'] = True
                    status['log_bucket'] = response['LoggingEnabled']['TargetBucket']
                    status['log_prefix'] = response['LoggingEnabled']['TargetPrefix']
            except ClientError as e:
                logger.warning(f"Error checking access logging: {e}")
                
            # Check public access block
            try:
                response = self.s3_client.get_public_access_block(Bucket=bucket_name)
                config = response['PublicAccessBlockConfiguration']
                status['public_access_blocked'] = (
                    config['BlockPublicAcls'] and
                    config['IgnorePublicAcls'] and
                    config['BlockPublicPolicy'] and
                    config['RestrictPublicBuckets']
                )
            except ClientError as e:
                logger.warning(f"Error checking public access block: {e}")
                
            # Check TLS enforcement in bucket policy
            try:
                response = self.s3_client.get_bucket_policy(Bucket=bucket_name)
                policy = json.loads(response['Policy'])
                for statement in policy.get('Statement', []):
                    if (statement.get('Sid') == 'EnforceTLS' and
                        statement.get('Effect') == 'Deny' and
                        'aws:SecureTransport' in str(statement.get('Condition', {}))):
                        status['tls_enforced'] = True
                        break
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchBucketPolicy':
                    logger.warning(f"Error checking bucket policy: {e}")
                    
        except Exception as e:
            logger.error(f"Error getting security status: {e}")
            
        return status
        
    def apply_comprehensive_security(self, bucket_name: str, log_bucket: Optional[str] = None,
                                   mfa_serial: Optional[str] = None) -> bool:
        """Apply all security features to a bucket.
        
        Args:
            bucket_name: Name of the S3 bucket
            log_bucket: Bucket for access logs (optional)
            mfa_serial: MFA device serial for MFA delete (optional)
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Applying comprehensive security to bucket {bucket_name}")
        
        # Enable encryption at rest
        if not self.enable_encryption_at_rest(bucket_name):
            return False
            
        # Enable versioning
        if not self.enable_bucket_versioning(bucket_name, 
                                           mfa_delete=bool(mfa_serial),
                                           mfa_serial=mfa_serial):
            return False
            
        # Configure public access block
        if not self.configure_public_access_block(bucket_name):
            return False
            
        # Enforce TLS
        if not self.enable_encryption_in_transit(bucket_name):
            return False
            
        # Enable access logging if log bucket provided
        if log_bucket:
            if not self.enable_access_logging(bucket_name, log_bucket):
                return False
                
        logger.info(f"Successfully applied comprehensive security to bucket {bucket_name}")
        return True


def main():
    """Main function for security management."""
    parser = argparse.ArgumentParser(description='Manage S3 bucket security')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--action', choices=['status', 'encrypt', 'version', 'logging', 
                                           'public-block', 'tls', 'comprehensive'],
                       default='status', help='Security action to perform')
    parser.add_argument('--log-bucket', help='Bucket for access logs')
    parser.add_argument('--mfa-serial', help='MFA device serial number')
    parser.add_argument('--encryption-type', default='AES256', 
                       help='Encryption type (AES256 or KMS key ID)')
    
    args = parser.parse_args()
    
    manager = SecurityManager(aws_profile=args.profile)
    
    if args.action == 'status':
        status = manager.get_security_status(args.bucket)
        print(f"\nSecurity Status for bucket: {status['bucket_name']}")
        print("=" * 50)
        print(f"Encryption Enabled: {'✅' if status['encryption_enabled'] else '❌'}")
        if status['encryption_enabled']:
            print(f"Encryption Type: {status.get('encryption_type', 'Unknown')}")
        print(f"Versioning Enabled: {'✅' if status['versioning_enabled'] else '❌'}")
        print(f"MFA Delete Enabled: {'✅' if status['mfa_delete_enabled'] else '❌'}")
        print(f"Access Logging Enabled: {'✅' if status['access_logging_enabled'] else '❌'}")
        if status['access_logging_enabled']:
            print(f"Log Bucket: {status.get('log_bucket', 'Unknown')}")
            print(f"Log Prefix: {status.get('log_prefix', 'Unknown')}")
        print(f"Public Access Blocked: {'✅' if status['public_access_blocked'] else '❌'}")
        print(f"TLS Enforced: {'✅' if status['tls_enforced'] else '❌'}")
        
    elif args.action == 'encrypt':
        success = manager.enable_encryption_at_rest(args.bucket, args.encryption_type)
        if success:
            print(f"✅ Enabled encryption for bucket {args.bucket}")
        else:
            print(f"❌ Failed to enable encryption for bucket {args.bucket}")
            sys.exit(1)
            
    elif args.action == 'version':
        success = manager.enable_bucket_versioning(args.bucket, 
                                                mfa_delete=bool(args.mfa_serial),
                                                mfa_serial=args.mfa_serial)
        if success:
            print(f"✅ Enabled versioning for bucket {args.bucket}")
        else:
            print(f"❌ Failed to enable versioning for bucket {args.bucket}")
            sys.exit(1)
            
    elif args.action == 'logging':
        if not args.log_bucket:
            print("Error: --log-bucket required for logging action")
            sys.exit(1)
        success = manager.enable_access_logging(args.bucket, args.log_bucket)
        if success:
            print(f"✅ Enabled access logging for bucket {args.bucket}")
        else:
            print(f"❌ Failed to enable access logging for bucket {args.bucket}")
            sys.exit(1)
            
    elif args.action == 'public-block':
        success = manager.configure_public_access_block(args.bucket)
        if success:
            print(f"✅ Configured public access block for bucket {args.bucket}")
        else:
            print(f"❌ Failed to configure public access block for bucket {args.bucket}")
            sys.exit(1)
            
    elif args.action == 'tls':
        success = manager.enable_encryption_in_transit(args.bucket)
        if success:
            print(f"✅ Enforced TLS for bucket {args.bucket}")
        else:
            print(f"❌ Failed to enforce TLS for bucket {args.bucket}")
            sys.exit(1)
            
    elif args.action == 'comprehensive':
        success = manager.apply_comprehensive_security(args.bucket, 
                                                    args.log_bucket,
                                                    args.mfa_serial)
        if success:
            print(f"✅ Applied comprehensive security to bucket {args.bucket}")
        else:
            print(f"❌ Failed to apply comprehensive security to bucket {args.bucket}")
            sys.exit(1)


if __name__ == '__main__':
    main() 