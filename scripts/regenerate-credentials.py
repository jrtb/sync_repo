#!/usr/bin/env python3
"""
Regenerate Credentials Script

This script regenerates the credentials file for the production IAM user.
Note: This will create a new access key and delete the old one.

Usage:
    python scripts/regenerate-credentials.py
"""

import json
import subprocess
import sys
from pathlib import Path

class CredentialsRegenerator:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.username = 's3-sync-user'
        self.region = 'us-east-1'
    
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
            print(f"❌ AWS CLI command failed: {e}")
            return None
    
    def delete_old_access_key(self):
        """Delete the existing access key"""
        print(f"🗑️  Deleting old access key for user: {self.username}")
        
        # List current access keys
        list_command = f"aws iam list-access-keys --user-name {self.username} --output json"
        result = self.run_aws_command(list_command)
        
        if not result:
            print("❌ Unable to list access keys")
            return False
        
        access_keys = json.loads(result.stdout)
        
        for key in access_keys['AccessKeyMetadata']:
            key_id = key['AccessKeyId']
            print(f"🗑️  Deleting access key: {key_id}")
            
            delete_command = f"aws iam delete-access-key --user-name {self.username} --access-key-id {key_id}"
            delete_result = self.run_aws_command(delete_command)
            
            if not delete_result:
                print(f"❌ Failed to delete access key: {key_id}")
                return False
        
        print("✅ Old access keys deleted")
        return True
    
    def create_new_access_key(self):
        """Create a new access key"""
        print(f"🔑 Creating new access key for user: {self.username}")
        
        command = f"aws iam create-access-key --user-name {self.username} --output json"
        result = self.run_aws_command(command)
        
        if not result:
            print("❌ Failed to create new access key")
            return None
        
        access_key_data = json.loads(result.stdout)
        access_key = access_key_data['AccessKey']
        
        print("✅ New access key created successfully")
        print(f"   Access Key ID: {access_key['AccessKeyId']}")
        print(f"   Status: {access_key['Status']}")
        
        return access_key
    
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
        import os
        os.chmod(credentials_file, 0o600)
        
        print(f"💾 Credentials saved to: {credentials_file}")
        print("⚠️  IMPORTANT: Keep this file secure and never commit it to version control!")
        
        return True
    
    def regenerate(self):
        """Main regeneration process"""
        print("🔄 Regenerating Credentials")
        print("=" * 40)
        
        # Delete old access key
        if not self.delete_old_access_key():
            return False
        
        # Create new access key
        access_key = self.create_new_access_key()
        if not access_key:
            return False
        
        # Save credentials
        if not self.save_credentials(access_key):
            return False
        
        print("\n✅ Credentials regeneration completed successfully!")
        return True

def main():
    regenerator = CredentialsRegenerator()
    
    if regenerator.regenerate():
        print("\n🎉 Credentials file has been regenerated!")
        sys.exit(0)
    else:
        print("\n💥 Credentials regeneration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 