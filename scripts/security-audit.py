#!/usr/bin/env python3
"""
Security Audit Script for AWS S3 Sync Application

This script audits the repository to ensure it's safe for public release.
It checks for exposed credentials, real infrastructure names, and other sensitive data.

Usage:
    python scripts/security-audit.py
"""

import argparse
import json
import re
import sys
from pathlib import Path

class SecurityAuditor:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.issues = []
        self.warnings = []
        
    def check_for_real_aws_credentials(self):
        """Check for real AWS credentials in the repository"""
        print("🔍 Checking for real AWS credentials...")
        
        # Check for real access keys (AKIA pattern)
        access_key_pattern = r'AKIA[0-9A-Z]{16}'
        
        for file_path in self.project_root.rglob('*.json'):
            if 'template' in file_path.name:
                continue  # Skip template files
            if '.venv' in str(file_path):
                continue  # Skip virtual environment files
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                matches = re.findall(access_key_pattern, content)
                if matches:
                    self.issues.append(f"❌ REAL AWS ACCESS KEY FOUND in {file_path}: {matches[0]}")
                    
            except Exception as e:
                self.warnings.append(f"⚠️  Could not read {file_path}: {e}")
        
        # Check for real secret keys (base64 pattern)
        secret_key_pattern = r'[A-Za-z0-9+/]{40}'
        
        for file_path in self.project_root.rglob('*.json'):
            if 'template' in file_path.name:
                continue
            if '.venv' in str(file_path):
                continue  # Skip virtual environment files
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                matches = re.findall(secret_key_pattern, content)
                for match in matches:
                    if not match.startswith('YOUR_') and not match.startswith('your-'):
                        self.issues.append(f"❌ POTENTIAL SECRET KEY FOUND in {file_path}: {match[:10]}...")
                        
            except Exception as e:
                self.warnings.append(f"⚠️  Could not read {file_path}: {e}")
        
        print("✅ AWS credentials check completed")
    
    def check_for_real_bucket_names(self):
        """Check for real S3 bucket names"""
        print("🔍 Checking for real S3 bucket names...")
        
        # Look for bucket names that don't look like placeholders
        bucket_pattern = r'"bucket_name":\s*"([^"]+)"'
        
        for file_path in self.project_root.rglob('*.json'):
            if 'template' in file_path.name:
                continue
            if '.venv' in str(file_path):
                continue  # Skip virtual environment files
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                matches = re.findall(bucket_pattern, content)
                for match in matches:
                    if not match.startswith('YOUR-') and not match.startswith('your-') and not match.startswith('my-'):
                        if len(match) > 10:  # Likely a real bucket name
                            self.issues.append(f"❌ REAL BUCKET NAME FOUND in {file_path}: {match}")
                            
            except Exception as e:
                self.warnings.append(f"⚠️  Could not read {file_path}: {e}")
        
        print("✅ S3 bucket names check completed")
    
    def check_for_real_account_ids(self):
        """Check for real AWS account IDs"""
        print("🔍 Checking for real AWS account IDs...")
        
        # Look for 12-digit account IDs that aren't test values
        account_pattern = r'123456789012|(\d{12})'
        
        for file_path in self.project_root.rglob('*.py'):
            if '.venv' in str(file_path):
                continue  # Skip virtual environment files
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                matches = re.findall(account_pattern, content)
                for match in matches:
                    if match and match != '123456789012':  # Skip test account ID
                        self.issues.append(f"❌ REAL ACCOUNT ID FOUND in {file_path}: {match}")
                        
            except Exception as e:
                self.warnings.append(f"⚠️  Could not read {file_path}: {e}")
        
        print("✅ AWS account IDs check completed")
    
    def check_for_real_emails(self):
        """Check for real email addresses"""
        print("🔍 Checking for real email addresses...")
        
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        for file_path in self.project_root.rglob('*.json'):
            if 'template' in file_path.name:
                continue
            if '.venv' in str(file_path):
                continue  # Skip virtual environment files
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                matches = re.findall(email_pattern, content)
                for match in matches:
                    if not match.startswith('your-') and not match.startswith('YOUR_') and not match.startswith('admin@example.com'):
                        self.issues.append(f"❌ REAL EMAIL FOUND in {file_path}: {match}")
                        
            except Exception as e:
                self.warnings.append(f"⚠️  Could not read {file_path}: {e}")
        
        print("✅ Email addresses check completed")
    
    def check_for_real_webhooks(self):
        """Check for real webhook URLs"""
        print("🔍 Checking for real webhook URLs...")
        
        webhook_pattern = r'https://hooks\.slack\.com/services/[A-Za-z0-9/]+'
        
        for file_path in self.project_root.rglob('*.json'):
            if 'template' in file_path.name:
                continue
            if '.venv' in str(file_path):
                continue  # Skip virtual environment files
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                matches = re.findall(webhook_pattern, content)
                for match in matches:
                    if 'YOUR' not in match and 'your' not in match:
                        self.issues.append(f"❌ REAL WEBHOOK URL FOUND in {file_path}: {match}")
                        
            except Exception as e:
                self.warnings.append(f"⚠️  Could not read {file_path}: {e}")
        
        print("✅ Webhook URLs check completed")
    
    def check_gitignore(self):
        """Check if sensitive files are properly ignored"""
        print("🔍 Checking .gitignore configuration...")
        
        gitignore_path = self.project_root / ".gitignore"
        
        if not gitignore_path.exists():
            self.issues.append("❌ .gitignore file not found")
            return
        
        try:
            with open(gitignore_path, 'r') as f:
                content = f.read()
            
            required_patterns = [
                'config/aws-credentials.json',
                'config/aws-config.json',
                'config/sync-config.json'
            ]
            
            for pattern in required_patterns:
                if pattern not in content:
                    self.issues.append(f"❌ Missing from .gitignore: {pattern}")
                else:
                    print(f"✅ {pattern} is properly ignored")
                    
        except Exception as e:
            self.issues.append(f"❌ Could not read .gitignore: {e}")
        
        print("✅ .gitignore check completed")
    
    def check_template_files(self):
        """Check if template files exist and are safe"""
        print("🔍 Checking template files...")
        
        required_templates = [
            'config/aws-credentials-template.json',
            'config/aws-config-template.json',
            'config/sync-config-template.json'
        ]
        
        for template in required_templates:
            template_path = self.project_root / template
            if not template_path.exists():
                self.issues.append(f"❌ Missing template file: {template}")
            else:
                print(f"✅ Template file exists: {template}")
        
        print("✅ Template files check completed")
    
    def run_audit(self):
        """Run the complete security audit"""
        print("🔒 Security Audit for Public Repository Release")
        print("=" * 60)
        
        # Run all checks
        self.check_for_real_aws_credentials()
        self.check_for_real_bucket_names()
        self.check_for_real_account_ids()
        self.check_for_real_emails()
        self.check_for_real_webhooks()
        self.check_gitignore()
        self.check_template_files()
        
        # Print results
        print("\n" + "=" * 60)
        print("📋 AUDIT RESULTS")
        print("=" * 60)
        
        if self.issues:
            print("\n🚨 CRITICAL ISSUES FOUND:")
            for issue in self.issues:
                print(f"   {issue}")
            print("\n❌ Repository is NOT safe for public release!")
            print("   Please fix the issues above before making public.")
        else:
            print("\n✅ NO CRITICAL ISSUES FOUND")
            print("   Repository appears safe for public release.")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Critical Issues: {len(self.issues)}")
        print(f"   Warnings: {len(self.warnings)}")
        
        if not self.issues:
            print("\n🎉 Repository is ready for public release!")
            print("   All sensitive data has been properly secured.")
        else:
            print(f"\n🔧 Please fix {len(self.issues)} critical issue(s) before release.")
        
        return len(self.issues) == 0

def main():
    parser = argparse.ArgumentParser(
        description="Audit repository for security issues before public release"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix common issues (not implemented yet)"
    )
    
    args = parser.parse_args()
    
    auditor = SecurityAuditor()
    success = auditor.run_audit()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 