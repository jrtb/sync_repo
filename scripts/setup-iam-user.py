#!/usr/bin/env python3
"""
IAM User Setup Script for AWS S3 Sync Application

This script creates an IAM user with programmatic access and attaches
the necessary policies for S3 sync operations and CloudWatch monitoring.

Usage:
    python scripts/setup-iam-user.py --username s3-sync-user --bucket-name my-sync-bucket
"""

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path

class IAMUserSetup:
    def __init__(self, username, bucket_name, region='us-east-1'):
        self.username = username
        self.bucket_name = bucket_name
        self.region = region
        self.project_root = Path(__file__).parent.parent
        
    def run_aws_command(self, command, capture_output=True, suppress_errors=False):
        """Run AWS CLI command and return result"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=capture_output,
                text=True,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                print(f"❌ AWS CLI command failed: {e}")
                if e.stderr:
                    print(f"Error: {e.stderr}")
            return None
    
    def check_resource_exists(self, check_command, resource_type, resource_name):
        """Check if a resource exists and return appropriate message"""
        print(f"🔍 Checking if {resource_type} '{resource_name}' exists...")
        result = self.run_aws_command(check_command, suppress_errors=True)
        
        if result:
            print(f"✅ {resource_type} '{resource_name}' already exists")
            return True
        else:
            print(f"ℹ️  {resource_type} '{resource_name}' not found (will create new one)")
            return False
    
    def get_account_id(self):
        """Get the current AWS account ID"""
        result = self.run_aws_command("aws sts get-caller-identity --output json", suppress_errors=True)
        if result:
            identity = json.loads(result.stdout)
            return identity['Account']
        return None
    
    def check_aws_cli_installed(self):
        """Check if AWS CLI is installed and configured"""
        print("🔍 Checking AWS CLI installation...")
        
        # Check if aws command exists
        result = self.run_aws_command("aws --version")
        if not result:
            print("❌ AWS CLI is not installed or not in PATH")
            print("Please install AWS CLI first: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
            return False
        
        print(f"✅ AWS CLI version: {result.stdout.strip()}")
        
        # Check if AWS is configured
        result = self.run_aws_command("aws sts get-caller-identity --output json")
        if not result:
            print("❌ AWS CLI is not configured")
            print("Please run 'aws configure' to set up your credentials")
            return False
        
        identity = json.loads(result.stdout)
        print(f"✅ AWS CLI configured for account: {identity['Account']}")
        print(f"✅ User/ARN: {identity['Arn']}")
        
        return True
    
    def create_iam_user(self):
        """Create the IAM user"""
        print(f"\n👤 Setting up IAM user: {self.username}")
        
        # Check if user already exists
        check_command = f"aws iam get-user --user-name {self.username} --output json"
        user_exists = self.check_resource_exists(check_command, "IAM user", self.username)
        
        if user_exists:
            return True
        
        # Create the user
        print(f"🛠️  Creating new IAM user: {self.username}")
        command = f"aws iam create-user --user-name {self.username} --output json"
        result = self.run_aws_command(command)
        
        if result:
            print(f"✅ IAM user '{self.username}' created successfully")
            return True
        else:
            print(f"❌ Failed to create IAM user '{self.username}'")
            return False
    
    def create_access_key(self):
        """Create access key for the IAM user"""
        print(f"\n🔑 Creating access key for user: {self.username}")
        
        command = f"aws iam create-access-key --user-name {self.username} --output json"
        result = self.run_aws_command(command)
        
        if result:
            access_key_data = json.loads(result.stdout)
            access_key = access_key_data['AccessKey']
            
            print("✅ Access key created successfully")
            print(f"   Access Key ID: {access_key['AccessKeyId']}")
            print(f"   Secret Access Key: {access_key['SecretAccessKey']}")
            print(f"   Status: {access_key['Status']}")
            
            # Save credentials to file
            self.save_credentials(access_key)
            return access_key
        else:
            print("❌ Failed to create access key")
            return None
    
    def save_credentials(self, access_key):
        """Save credentials to a secure file"""
        credentials_file = self.project_root / "config" / "aws-credentials.json"
        
        credentials = {
            "aws_access_key_id": access_key['AccessKeyId'],
            "aws_secret_access_key": access_key['SecretAccessKey'],
            "region": self.region,
            "username": self.username,
            "created_at": access_key['CreateDate']
        }
        
        # Ensure config directory exists
        credentials_file.parent.mkdir(exist_ok=True)
        
        with open(credentials_file, 'w') as f:
            json.dump(credentials, f, indent=2, default=str)
        
        # Set restrictive permissions
        os.chmod(credentials_file, 0o600)
        
        print(f"💾 Credentials saved to: {credentials_file}")
        print("⚠️  IMPORTANT: Keep this file secure and never commit it to version control!")
    
    def create_s3_sync_policy(self):
        """Create the S3 sync policy"""
        print(f"\n📋 Setting up S3 sync policy for bucket: {self.bucket_name}")
        
        # Read the policy template
        policy_template = self.project_root / "templates" / "iam-policies" / "s3-sync-policy.json"
        
        if not policy_template.exists():
            print(f"❌ Policy template not found: {policy_template}")
            return None
        
        with open(policy_template, 'r') as f:
            policy = json.load(f)
        
        # Replace placeholder with actual bucket name
        policy_str = json.dumps(policy).replace("YOUR-BUCKET-NAME", self.bucket_name)
        
        # Create the policy
        policy_name = f"{self.username}-s3-sync-policy"
        
        # Try to create the policy (will fail gracefully if it already exists)
        command = f"aws iam create-policy --policy-name {policy_name} --policy-document '{policy_str}' --output json"
        result = self.run_aws_command(command, suppress_errors=True)
        
        if result:
            policy_data = json.loads(result.stdout)
            policy_arn = policy_data['Policy']['Arn']
            print(f"✅ S3 sync policy created: {policy_arn}")
            return policy_arn
        else:
            # Policy might already exist, try to get its ARN
            print(f"ℹ️  Policy '{policy_name}' may already exist, getting ARN...")
            get_arn_command = f"aws iam get-policy --policy-arn arn:aws:iam::{self.get_account_id()}:policy/{policy_name} --output json"
            arn_result = self.run_aws_command(get_arn_command, suppress_errors=True)
            
            if arn_result:
                policy_data = json.loads(arn_result.stdout)
                policy_arn = policy_data['Policy']['Arn']
                print(f"✅ Using existing S3 sync policy: {policy_arn}")
                return policy_arn
            else:
                print("❌ Failed to create or find S3 sync policy")
                return None
    
    def create_cloudwatch_policy(self):
        """Create the CloudWatch monitoring policy"""
        print(f"\n📊 Setting up CloudWatch monitoring policy")
        
        # Read the policy template
        policy_template = self.project_root / "templates" / "iam-policies" / "cloudwatch-monitoring-policy.json"
        
        if not policy_template.exists():
            print(f"❌ Policy template not found: {policy_template}")
            return None
        
        with open(policy_template, 'r') as f:
            policy = json.load(f)
        
        # Create the policy
        policy_name = f"{self.username}-cloudwatch-policy"
        policy_str = json.dumps(policy)
        command = f"aws iam create-policy --policy-name {policy_name} --policy-document '{policy_str}' --output json"
        
        result = self.run_aws_command(command, suppress_errors=True)
        
        if result:
            policy_data = json.loads(result.stdout)
            policy_arn = policy_data['Policy']['Arn']
            print(f"✅ CloudWatch policy created: {policy_arn}")
            return policy_arn
        else:
            # Policy might already exist, try to get its ARN
            print(f"ℹ️  Policy '{policy_name}' may already exist, getting ARN...")
            get_arn_command = f"aws iam get-policy --policy-arn arn:aws:iam::{self.get_account_id()}:policy/{policy_name} --output json"
            arn_result = self.run_aws_command(get_arn_command, suppress_errors=True)
            
            if arn_result:
                policy_data = json.loads(arn_result.stdout)
                policy_arn = policy_data['Policy']['Arn']
                print(f"✅ Using existing CloudWatch policy: {policy_arn}")
                return policy_arn
            else:
                print("❌ Failed to create or find CloudWatch policy")
                return None
    
    def attach_policies(self, s3_policy_arn, cloudwatch_policy_arn):
        """Attach policies to the IAM user"""
        print(f"\n🔗 Setting up policy attachments for user: {self.username}")
        
        policies = []
        if s3_policy_arn:
            policies.append(s3_policy_arn)
        if cloudwatch_policy_arn:
            policies.append(cloudwatch_policy_arn)
        
        for policy_arn in policies:
            policy_name = policy_arn.split('/')[-1]
            print(f"🔗 Attaching policy: {policy_name}")
            
            command = f"aws iam attach-user-policy --user-name {self.username} --policy-arn {policy_arn}"
            result = self.run_aws_command(command, suppress_errors=True)
            
            if result:
                print(f"✅ Policy attached successfully: {policy_name}")
            else:
                print(f"ℹ️  Policy '{policy_name}' may already be attached (continuing...)")
    
    def create_s3_bucket(self):
        """Create S3 bucket if it doesn't exist"""
        print(f"\n🪣 Setting up S3 bucket: {self.bucket_name}")
        
        # Check if bucket exists
        command = f"aws s3api head-bucket --bucket {self.bucket_name}"
        bucket_exists = self.check_resource_exists(command, "S3 bucket", self.bucket_name)
        
        if bucket_exists:
            return True
        
        # Create bucket
        print(f"🛠️  Creating new S3 bucket: {self.bucket_name}")
        command = f"aws s3api create-bucket --bucket {self.bucket_name} --region {self.region}"
        result = self.run_aws_command(command)
        
        if result:
            print(f"✅ S3 bucket '{self.bucket_name}' created successfully")
            return True
        else:
            print(f"❌ Failed to create S3 bucket '{self.bucket_name}'")
            return False
    
    def apply_bucket_security(self):
        """Apply security features to the S3 bucket including versioning"""
        print(f"\n🔒 Setting up bucket security features for: {self.bucket_name}")
        
        try:
            # Import security manager
            from scripts.security_manager import SecurityManager
            
            # Create security manager
            security_manager = SecurityManager()
            
            # Apply comprehensive security features
            success = security_manager.apply_comprehensive_security(self.bucket_name)
            
            if success:
                print(f"✅ Security features applied successfully to bucket '{self.bucket_name}'")
                print("   - Server-side encryption enabled")
                print("   - Bucket versioning enabled")
                print("   - Public access blocked")
                print("   - TLS/HTTPS enforcement enabled")
                return True
            else:
                print(f"❌ Failed to apply security features to bucket '{self.bucket_name}'")
                return False
                
        except ImportError:
            print("⚠️  Security manager not available, skipping security features")
            print("   You can manually enable versioning with:")
            print(f"   aws s3api put-bucket-versioning --bucket {self.bucket_name} --versioning-configuration Status=Enabled")
            return True  # Don't fail setup if security manager is not available
        except Exception as e:
            print(f"❌ Error applying security features: {e}")
            return False
    
    def setup(self):
        """Main setup process"""
        print("🚀 Starting IAM user setup for AWS S3 Sync Application")
        print("=" * 60)
        
        # Check prerequisites
        if not self.check_aws_cli_installed():
            return False
        
        # Create S3 bucket
        if not self.create_s3_bucket():
            return False
        
        # Apply security features to bucket
        if not self.apply_bucket_security():
            return False
        
        # Create IAM user
        if not self.create_iam_user():
            return False
        
        # Create access key
        access_key = self.create_access_key()
        if not access_key:
            return False
        
        # Create policies
        s3_policy_arn = self.create_s3_sync_policy()
        cloudwatch_policy_arn = self.create_cloudwatch_policy()
        
        # Attach policies
        self.attach_policies(s3_policy_arn, cloudwatch_policy_arn)
        
        print("\n" + "=" * 60)
        print("✅ IAM user setup completed successfully!")
        print("\n📋 Summary:")
        print(f"   Username: {self.username}")
        print(f"   S3 Bucket: {self.bucket_name}")
        print(f"   Access Key ID: {access_key['AccessKeyId']}")
        print(f"   Credentials saved to: config/aws-credentials.json")
        
        print("\n🔧 Next steps:")
        print("   1. Test the credentials with: aws configure --profile s3-sync")
        print("   2. Update your sync configuration files")
        print("   3. Run a test sync operation")
        
        return True

def get_user_input(prompt, default=None, required=False):
    """Get user input with optional default value"""
    while True:
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            if not user_input:
                user_input = default
        else:
            user_input = input(f"{prompt}: ").strip()
        
        if user_input or not required:
            return user_input
        else:
            print("❌ This field is required. Please enter a value.")

def main():
    parser = argparse.ArgumentParser(
        description="Set up IAM user with programmatic access for AWS S3 Sync"
    )
    parser.add_argument(
        "--username",
        help="IAM username (will prompt if not provided)"
    )
    parser.add_argument(
        "--bucket-name",
        help="S3 bucket name for sync operations (will prompt if not provided)"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode (requires all arguments)"
    )
    
    args = parser.parse_args()
    
    # Interactive prompts for missing required arguments
    username = args.username
    bucket_name = args.bucket_name
    
    if not args.non_interactive:
        if not username:
            print("\n🔧 IAM User Setup Configuration")
            print("=" * 40)
            username = get_user_input("Enter IAM username", "s3-sync-user", required=True)
        
        if not bucket_name:
            bucket_name = get_user_input("Enter S3 bucket name", required=True)
            print(f"💡 Tip: Bucket names must be globally unique and contain only lowercase letters, numbers, hyphens, and dots")
    
    # Validate required arguments
    if not username or not bucket_name:
        print("❌ Error: Username and bucket name are required")
        print("Usage: python scripts/setup-iam-user.py --username USERNAME --bucket-name BUCKET")
        print("Or run without arguments for interactive mode")
        sys.exit(1)
    
    setup = IAMUserSetup(username, bucket_name, args.region)
    
    if setup.setup():
        print("\n🎉 Setup completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 