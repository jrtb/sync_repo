#!/usr/bin/env python3
"""
Setup Credentials Script for AWS S3 Sync Application

This script helps users set up their credentials from template files.
It copies template files to their real locations and prompts for real values.

Usage:
    python scripts/setup-credentials.py
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

class CredentialSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        
    def get_user_input(self, prompt, default=None, required=False):
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
    
    def copy_template_to_real(self, template_name, real_name, description):
        """Copy template file to real file"""
        template_path = self.config_dir / template_name
        real_path = self.config_dir / real_name
        
        if not template_path.exists():
            print(f"❌ Template file not found: {template_path}")
            return False
        
        if real_path.exists():
            overwrite = input(f"⚠️  {real_name} already exists. Overwrite? (y/N): ").strip().lower()
            if overwrite != 'y':
                print(f"⏭️  Skipping {real_name}")
                return True
        
        try:
            shutil.copy2(template_path, real_path)
            print(f"✅ Created {real_name} from template")
            return True
        except Exception as e:
            print(f"❌ Failed to create {real_name}: {e}")
            return False
    
    def setup_aws_credentials(self):
        """Set up AWS credentials file"""
        print("\n🔑 Setting up AWS credentials...")
        
        if not self.copy_template_to_real("aws-credentials-template.json", "aws-credentials.json", "AWS credentials"):
            return False
        
        credentials_file = self.config_dir / "aws-credentials.json"
        
        try:
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
            
            print("\n📝 Please enter your AWS credentials:")
            credentials['aws_access_key_id'] = self.get_user_input("AWS Access Key ID", required=True)
            credentials['aws_secret_access_key'] = self.get_user_input("AWS Secret Access Key", required=True)
            credentials['region'] = self.get_user_input("AWS Region", "us-east-1")
            credentials['username'] = self.get_user_input("IAM Username", "s3-sync-user")
            credentials['created_at'] = datetime.now().isoformat() + "+00:00"
            
            with open(credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(credentials_file, 0o600)
            print("✅ AWS credentials configured successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to configure AWS credentials: {e}")
            return False
    
    def setup_aws_config(self):
        """Set up AWS configuration file"""
        print("\n⚙️  Setting up AWS configuration...")
        
        if not self.copy_template_to_real("aws-config-template.json", "aws-config.json", "AWS configuration"):
            return False
        
        config_file = self.config_dir / "aws-config.json"
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            print("\n📝 Please enter your AWS configuration:")
            bucket_name = self.get_user_input("S3 Bucket Name", required=True)
            config['s3']['bucket_name'] = bucket_name
            
            profile_name = self.get_user_input("AWS Profile Name", "s3-sync")
            config['aws']['profile'] = profile_name
            
            region = self.get_user_input("AWS Region", "us-east-1")
            config['aws']['region'] = region
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ AWS configuration updated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to configure AWS settings: {e}")
            return False
    
    def setup_sync_config(self):
        """Set up sync configuration file"""
        print("\n🔄 Setting up sync configuration...")
        
        if not self.copy_template_to_real("sync-config-template.json", "sync-config.json", "sync configuration"):
            return False
        
        config_file = self.config_dir / "sync-config.json"
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            print("\n📝 Please enter your sync configuration (press Enter to use defaults):")
            
            # Email configuration
            enable_email = self.get_user_input("Enable email notifications? (y/N)", "N").strip().lower()
            if enable_email == 'y':
                config['notifications']['email']['enabled'] = True
                config['notifications']['email']['username'] = self.get_user_input("Email username")
                config['notifications']['email']['password'] = self.get_user_input("Email password")
                config['notifications']['email']['recipients'] = [self.get_user_input("Email recipient")]
            
            # Webhook configuration
            enable_webhook = self.get_user_input("Enable webhook notifications? (y/N)", "N").strip().lower()
            if enable_webhook == 'y':
                config['notifications']['webhook']['enabled'] = True
                config['notifications']['webhook']['url'] = self.get_user_input("Webhook URL")
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Sync configuration updated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to configure sync settings: {e}")
            return False
    
    def setup(self):
        """Main setup process"""
        print("🔧 Setting up AWS S3 Sync Credentials")
        print("=" * 50)
        
        print("This script will help you set up your credentials from template files.")
        print("Make sure you have your AWS credentials ready.")
        print()
        
        # Set up all configuration files
        success = True
        success &= self.setup_aws_credentials()
        success &= self.setup_aws_config()
        success &= self.setup_sync_config()
        
        if success:
            print("\n" + "=" * 50)
            print("✅ Credential setup completed successfully!")
            print("\n📋 Next steps:")
            print("   1. Test your credentials: python scripts/test-credentials.py")
            print("   2. Verify your setup: python scripts/verify-production-setup.py")
            print("   3. Run a test sync: python scripts/sync.py")
            print("\n⚠️  IMPORTANT: Keep your credential files secure!")
            print("   - config/aws-credentials.json is in .gitignore")
            print("   - Never commit credentials to version control")
        else:
            print("\n❌ Credential setup failed. Please check the errors above.")
            return False
        
        return True

def main():
    parser = argparse.ArgumentParser(
        description="Set up credentials from template files"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode (requires environment variables)"
    )
    
    args = parser.parse_args()
    
    setup = CredentialSetup()
    success = setup.setup()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 