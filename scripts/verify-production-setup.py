#!/usr/bin/env python3
"""
Production Setup Verification Script

This script verifies that all production AWS resources are properly configured
and accessible for the S3 sync application.

Usage:
    python scripts/verify-production-setup.py
"""

import json
import subprocess
import sys
from pathlib import Path

class ProductionVerifier:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.expected_resources = {
            'iam_user': 's3-sync-user',
            's3_bucket': 'YOUR-BUCKET-NAME',
            'aws_account': '123456789012',
            'region': 'us-east-1'
        }
    
    def run_aws_command(self, command, capture_output=True):
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
            return None
    
    def check_credentials_file(self):
        """Check if credentials file exists and has correct permissions"""
        print("🔑 Checking credentials file...")
        
        credentials_file = self.project_root / "config" / "aws-credentials.json"
        
        if not credentials_file.exists():
            print("❌ Credentials file not found: config/aws-credentials.json")
            return False
        
        # Check file permissions (should be 600)
        import os
        stat = os.stat(credentials_file)
        permissions = oct(stat.st_mode)[-3:]
        
        if permissions != '600':
            print(f"⚠️  Credentials file permissions are {permissions} (should be 600)")
        else:
            print("✅ Credentials file permissions are secure (600)")
        
        # Try to read credentials
        try:
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
            
            required_fields = ['aws_access_key_id', 'aws_secret_access_key', 'username']
            for field in required_fields:
                if field not in credentials:
                    print(f"❌ Missing required field in credentials: {field}")
                    return False
            
            print(f"✅ Credentials file is valid")
            print(f"   Username: {credentials['username']}")
            print(f"   Access Key: {credentials['aws_access_key_id']}")
            return True
            
        except Exception as e:
            print(f"❌ Error reading credentials file: {e}")
            return False
    
    def check_aws_config(self):
        """Check if AWS config file is properly configured"""
        print("\n⚙️  Checking AWS configuration...")
        
        config_file = self.project_root / "config" / "aws-config.json"
        
        if not config_file.exists():
            print("❌ AWS config file not found: config/aws-config.json")
            return False
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            bucket_name = config.get('s3', {}).get('bucket_name')
            if bucket_name != self.expected_resources['s3_bucket']:
                print(f"❌ Bucket name mismatch: {bucket_name} (expected: {self.expected_resources['s3_bucket']})")
                return False
            
            print(f"✅ AWS config is properly configured")
            print(f"   Bucket: {bucket_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error reading AWS config: {e}")
            return False
    
    def check_iam_user(self):
        """Check if IAM user exists and is accessible"""
        print(f"\n👤 Checking IAM user: {self.expected_resources['iam_user']}")
        
        command = f"aws iam get-user --user-name {self.expected_resources['iam_user']} --output json"
        result = self.run_aws_command(command)
        
        if not result:
            print(f"❌ IAM user '{self.expected_resources['iam_user']}' not found or not accessible")
            return False
        
        user_data = json.loads(result.stdout)
        print(f"✅ IAM user exists: {user_data['User']['UserName']}")
        print(f"   ARN: {user_data['User']['Arn']}")
        return True
    
    def check_s3_bucket(self):
        """Check if S3 bucket exists and is accessible"""
        print(f"\n🪣 Checking S3 bucket: {self.expected_resources['s3_bucket']}")
        
        command = f"aws s3api head-bucket --bucket {self.expected_resources['s3_bucket']}"
        result = self.run_aws_command(command)
        
        if not result:
            print(f"❌ S3 bucket '{self.expected_resources['s3_bucket']}' not found or not accessible")
            return False
        
        print(f"✅ S3 bucket exists and is accessible")
        return True
    
    def check_aws_account(self):
        """Check if we're using the correct AWS account"""
        print(f"\n🏢 Checking AWS account...")
        
        command = "aws sts get-caller-identity --output json"
        result = self.run_aws_command(command)
        
        if not result:
            print("❌ Unable to get AWS account information")
            return False
        
        identity = json.loads(result.stdout)
        account_id = identity['Account']
        
        if account_id != self.expected_resources['aws_account']:
            print(f"❌ Wrong AWS account: {account_id} (expected: {self.expected_resources['aws_account']})")
            return False
        
        print(f"✅ Using correct AWS account: {account_id}")
        print(f"   User: {identity['Arn']}")
        return True
    
    def test_s3_access(self):
        """Test S3 access using the sync user credentials"""
        print(f"\n🧪 Testing S3 access with sync user...")
        
        # Test listing bucket contents
        command = f"aws s3 ls s3://{self.expected_resources['s3_bucket']}/"
        result = self.run_aws_command(command)
        
        if not result:
            print("❌ Unable to list S3 bucket contents")
            return False
        
        print("✅ S3 access test successful")
        print("   Bucket listing works correctly")
        return True
    
    def verify(self):
        """Run all verification checks"""
        print("🔍 Verifying Production Setup")
        print("=" * 50)
        
        checks = [
            self.check_credentials_file,
            self.check_aws_config,
            self.check_aws_account,
            self.check_iam_user,
            self.check_s3_bucket,
            self.test_s3_access
        ]
        
        results = []
        for check in checks:
            try:
                result = check()
                results.append(result)
            except Exception as e:
                print(f"❌ Error during verification: {e}")
                results.append(False)
        
        print("\n" + "=" * 50)
        print("📊 Verification Results")
        print("=" * 50)
        
        passed = sum(results)
        total = len(results)
        
        if passed == total:
            print("🎉 All checks passed! Production setup is ready.")
            return True
        else:
            print(f"⚠️  {passed}/{total} checks passed. Some issues need attention.")
            return False

def main():
    verifier = ProductionVerifier()
    
    if verifier.verify():
        print("\n✅ Production setup verification completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Production setup verification failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 