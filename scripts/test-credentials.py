#!/usr/bin/env python3
"""
Test Credentials Script for AWS S3 Sync Application

This script tests the IAM user credentials to ensure they have the correct
permissions for S3 sync operations and CloudWatch monitoring.

Usage:
    python scripts/test-credentials.py --profile s3-sync --bucket-name my-sync-bucket
"""

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path

class CredentialTester:
    def __init__(self, profile, bucket_name, region='us-east-1'):
        self.profile = profile
        self.bucket_name = bucket_name
        self.region = region
        self.project_root = Path(__file__).parent.parent
        
    def run_aws_command(self, command, capture_output=True):
        """Run AWS CLI command with profile and return result"""
        try:
            full_command = f"aws {command} --profile {self.profile}"
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=capture_output,
                text=True,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"❌ AWS CLI command failed: {e}")
            if e.stderr:
                print(f"Error: {e.stderr}")
            return None
    
    def test_aws_identity(self):
        """Test AWS identity and account access"""
        print("🔍 Testing AWS identity...")
        
        result = self.run_aws_command("sts get-caller-identity --output json")
        if not result:
            print("❌ Failed to get caller identity")
            return False
        
        identity = json.loads(result.stdout)
        print(f"✅ AWS Identity:")
        print(f"   Account: {identity['Account']}")
        print(f"   User ID: {identity['UserId']}")
        print(f"   ARN: {identity['Arn']}")
        
        return True
    
    def test_s3_bucket_access(self):
        """Test S3 bucket access"""
        print(f"\n🪣 Testing S3 bucket access: {self.bucket_name}")
        
        # Test bucket listing
        result = self.run_aws_command(f"s3 ls s3://{self.bucket_name}")
        if result:
            print("✅ S3 bucket listing successful")
            if result.stdout.strip():
                print("   Bucket contents:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"   {line}")
            else:
                print("   Bucket is empty")
        else:
            print("❌ Failed to list S3 bucket")
            return False
        
        return True
    
    def test_s3_upload_download(self):
        """Test S3 upload and download operations"""
        print(f"\n📤 Testing S3 upload/download operations")
        
        # Create test file
        test_file = self.project_root / "test-upload.txt"
        test_content = f"Test file created at {subprocess.run('date', capture_output=True, text=True).stdout.strip()}"
        
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        try:
            # Upload test file
            result = self.run_aws_command(f"s3 cp {test_file} s3://{self.bucket_name}/test-upload.txt")
            if not result:
                print("❌ Failed to upload test file")
                return False
            print("✅ Test file uploaded successfully")
            
            # Download test file
            download_file = self.project_root / "test-download.txt"
            result = self.run_aws_command(f"s3 cp s3://{self.bucket_name}/test-upload.txt {download_file}")
            if not result:
                print("❌ Failed to download test file")
                return False
            print("✅ Test file downloaded successfully")
            
            # Verify content
            with open(download_file, 'r') as f:
                downloaded_content = f.read()
            
            if downloaded_content == test_content:
                print("✅ File content verification successful")
            else:
                print("❌ File content verification failed")
                return False
            
            # Clean up test files
            result = self.run_aws_command(f"s3 rm s3://{self.bucket_name}/test-upload.txt")
            if result:
                print("✅ Test file cleaned up from S3")
            
            return True
            
        finally:
            # Clean up local test files
            if test_file.exists():
                test_file.unlink()
            if download_file.exists():
                download_file.unlink()
    
    def test_s3_bucket_metadata(self):
        """Test S3 bucket metadata operations"""
        print(f"\n📋 Testing S3 bucket metadata operations")
        
        # Test bucket location
        result = self.run_aws_command(f"s3api get-bucket-location --bucket {self.bucket_name} --output json")
        if result:
            location_data = json.loads(result.stdout)
            print(f"✅ Bucket location: {location_data.get('LocationConstraint', 'us-east-1')}")
        else:
            print("❌ Failed to get bucket location")
            return False
        
        # Test bucket versioning
        result = self.run_aws_command(f"s3api get-bucket-versioning --bucket {self.bucket_name} --output json")
        if result:
            versioning_data = json.loads(result.stdout)
            status = versioning_data.get('Status', 'NotEnabled')
            print(f"✅ Bucket versioning: {status}")
        else:
            print("❌ Failed to get bucket versioning")
            return False
        
        return True
    
    def test_cloudwatch_permissions(self):
        """Test CloudWatch permissions"""
        print(f"\n📊 Testing CloudWatch permissions")
        
        # Test metric data
        result = self.run_aws_command(
            f"cloudwatch put-metric-data "
            f"--namespace S3Sync "
            f"--metric-data MetricName=TestMetric,Value=1,Unit=Count "
            f"--output json"
        )
        
        if result:
            print("✅ CloudWatch metric data sent successfully")
        else:
            print("❌ Failed to send CloudWatch metric data")
            return False
        
        # Test log group creation (if it doesn't exist)
        log_group_name = "/aws/s3-sync/test"
        result = self.run_aws_command(f"logs describe-log-groups --log-group-name-prefix {log_group_name} --output json")
        
        if result:
            log_groups = json.loads(result.stdout)
            if not log_groups.get('logGroups'):
                # Create log group
                result = self.run_aws_command(f"logs create-log-group --log-group-name {log_group_name}")
                if result:
                    print("✅ CloudWatch log group created successfully")
                else:
                    print("❌ Failed to create CloudWatch log group")
                    return False
            else:
                print("✅ CloudWatch log group access verified")
        
        return True
    
    def test_iam_permissions(self):
        """Test IAM permissions"""
        print(f"\n👤 Testing IAM permissions")
        
        # Test getting user info
        result = self.run_aws_command("iam get-user --output json")
        if result:
            user_data = json.loads(result.stdout)
            print(f"✅ IAM user access verified: {user_data['User']['UserName']}")
        else:
            print("❌ Failed to get IAM user info")
            return False
        
        # Test listing attached policies
        result = self.run_aws_command("iam list-attached-user-policies --user-name s3-sync-user --output json")
        if result:
            policies_data = json.loads(result.stdout)
            print("✅ Attached policies:")
            for policy in policies_data.get('AttachedPolicies', []):
                print(f"   - {policy['PolicyName']}")
        else:
            print("❌ Failed to list attached policies")
            return False
        
        return True
    
    def run_all_tests(self):
        """Run all credential tests"""
        print("🚀 Starting credential tests for AWS S3 Sync Application")
        print("=" * 60)
        
        tests = [
            ("AWS Identity", self.test_aws_identity),
            ("S3 Bucket Access", self.test_s3_bucket_access),
            ("S3 Upload/Download", self.test_s3_upload_download),
            ("S3 Bucket Metadata", self.test_s3_bucket_metadata),
            ("CloudWatch Permissions", self.test_cloudwatch_permissions),
            ("IAM Permissions", self.test_iam_permissions)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    print(f"❌ {test_name} test failed")
            except Exception as e:
                print(f"❌ {test_name} test failed with exception: {e}")
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Your IAM user is properly configured.")
            return True
        else:
            print("💥 Some tests failed. Please check the IAM user permissions.")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Test IAM user credentials for AWS S3 Sync"
    )
    parser.add_argument(
        "--profile",
        default="s3-sync",
        help="AWS CLI profile name (default: s3-sync)"
    )
    parser.add_argument(
        "--bucket-name",
        required=True,
        help="S3 bucket name to test"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    
    args = parser.parse_args()
    
    tester = CredentialTester(args.profile, args.bucket_name, args.region)
    
    if tester.run_all_tests():
        print("\n✅ Credential testing completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Credential testing failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 