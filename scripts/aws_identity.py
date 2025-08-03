#!/usr/bin/env python3
"""
AWS Identity Verification Module

This module provides functionality to verify and display AWS identity information
including IAM username and AWS account details. This is crucial for ensuring
files are uploaded to the correct AWS account and with the correct permissions.

AWS Concepts Covered:
- IAM identity verification using STS
- AWS account management
- Security best practices for identity confirmation
- Error handling for authentication issues

Usage:
    from scripts.aws_identity import AWSIdentityVerifier
    verifier = AWSIdentityVerifier(profile='default')
    identity_info = verifier.get_identity_info()
    verifier.display_identity_prompt(identity_info)
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path

try:
    from scripts.logger import SyncLogger
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.logger import SyncLogger

class AWSIdentityVerifier:
    """Handles AWS identity verification and display"""
    
    def __init__(self, profile='default', config=None):
        """Initialize the AWS identity verifier"""
        self.profile = profile
        self.config = config or {}
        self.project_root = Path(__file__).parent.parent
        
        # Initialize logger if available
        try:
            self.logger = SyncLogger(operation_name='aws-identity', config=self.config)
        except Exception:
            self.logger = None
        
        # Initialize AWS session
        self._setup_aws_session()
    
    def _setup_aws_session(self):
        """Setup AWS session with proper error handling"""
        try:
            self.session = boto3.Session(profile_name=self.profile)
            self.sts_client = self.session.client('sts')
            if self.logger:
                self.logger.log_info("✅ AWS session initialized successfully")
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "AWS session initialization")
            raise
    
    def get_identity_info(self):
        """Get current AWS identity information"""
        try:
            response = self.sts_client.get_caller_identity()
            
            identity_info = {
                'account_id': response['Account'],
                'user_id': response['UserId'],
                'arn': response['Arn'],
                'username': self._extract_username_from_arn(response['Arn']),
                'account_alias': self._get_account_alias(),
                'region': self.session.region_name
            }
            
            if self.logger:
                self.logger.log_info(f"Retrieved identity info for account {identity_info['account_id']}")
            
            return identity_info
            
        except NoCredentialsError:
            error_msg = "AWS credentials not found"
            if self.logger:
                self.logger.log_error(Exception(error_msg), "credential validation")
            raise Exception(error_msg)
        except ClientError as e:
            error_msg = f"AWS authentication failed: {e}"
            if self.logger:
                self.logger.log_error(e, "AWS authentication")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to get identity info: {e}"
            if self.logger:
                self.logger.log_error(e, "identity retrieval")
            raise Exception(error_msg)
    
    def _extract_username_from_arn(self, arn):
        """Extract username from IAM ARN"""
        try:
            # ARN format: arn:aws:iam::account:user/username
            if '/user/' in arn:
                return arn.split('/user/')[-1]
            elif 'assumed-role' in arn:
                # For assumed role: arn:aws:iam::account:assumed-role/role-name/session-name
                # The format is: arn:aws:iam::account:assumed-role/role-name/session-name
                # So we need to find the role name which is the second-to-last part
                parts = arn.split('/')
                if len(parts) >= 2:
                    return parts[-2]  # Second to last part is the role name
                return "unknown"
            else:
                return arn.split('/')[-1] if '/' in arn else arn
        except Exception:
            return "unknown"
    
    def _get_account_alias(self):
        """Get AWS account alias if available"""
        try:
            iam_client = self.session.client('iam')
            response = iam_client.list_account_aliases()
            if response['AccountAliases']:
                return response['AccountAliases'][0]
            return None
        except Exception:
            # Account alias not available or no permissions
            return None
    
    def display_identity_prompt(self, identity_info, bucket_name=None, require_confirmation=True):
        """Display identity information prominently and optionally require confirmation"""
        print("\n" + "="*80)
        print("🔐 AWS IDENTITY VERIFICATION")
        print("="*80)
        
        # Display account information
        print(f"📋 AWS Account ID: {identity_info['account_id']}")
        if identity_info['account_alias']:
            print(f"📋 Account Alias: {identity_info['account_alias']}")
        print(f"👤 IAM User: {identity_info['username']}")
        print(f"🆔 User ID: {identity_info['user_id']}")
        print(f"🌍 Region: {identity_info['region']}")
        print(f"🔗 ARN: {identity_info['arn']}")
        
        if bucket_name:
            print(f"🪣 Target Bucket: {bucket_name}")
        
        print("="*80)
        
        # Security warning
        print("⚠️  SECURITY WARNING:")
        print("   • Verify the AWS Account ID matches your intended destination")
        print("   • Ensure you're using the correct IAM user for this operation")
        print("   • Files will be uploaded to this account with these permissions")
        print("="*80)
        
        if require_confirmation:
            return self._get_user_confirmation()
        
        return True
    
    def _get_user_confirmation(self):
        """Get user confirmation to proceed"""
        while True:
            response = input("\n❓ Do you want to proceed with this AWS account? (yes/no): ").strip().lower()
            
            if response in ['yes', 'y']:
                print("✅ Confirmed - proceeding with sync operation")
                return True
            elif response in ['no', 'n']:
                print("❌ Cancelled by user")
                return False
            else:
                print("Please enter 'yes' or 'no'")
    
    def verify_identity_for_sync(self, bucket_name=None, dry_run=False):
        """Complete identity verification workflow for sync operations"""
        try:
            # Get identity information
            identity_info = self.get_identity_info()
            
            # For dry runs, display but don't require confirmation
            if dry_run:
                print("\n🔍 DRY RUN MODE - Identity verification:")
                self.display_identity_prompt(identity_info, bucket_name, require_confirmation=False)
                return True
            
            # Display identity and get confirmation
            confirmed = self.display_identity_prompt(identity_info, bucket_name, require_confirmation=True)
            
            if not confirmed:
                if self.logger:
                    self.logger.log_info("Sync operation cancelled by user during identity verification")
                return False
            
            if self.logger:
                self.logger.log_info(f"Identity verified for account {identity_info['account_id']}, user {identity_info['username']}")
            
            return True
            
        except Exception as e:
            error_msg = f"Identity verification failed: {e}"
            print(f"❌ {error_msg}")
            if self.logger:
                self.logger.log_error(e, "identity verification")
            return False
    
    def get_identity_summary(self):
        """Get a concise summary of identity information"""
        try:
            identity_info = self.get_identity_info()
            return {
                'account': identity_info['account_id'],
                'user': identity_info['username'],
                'region': identity_info['region']
            }
        except Exception:
            return None 