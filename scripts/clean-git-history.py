#!/usr/bin/env python3
"""
Clean Git History Script for AWS S3 Sync Application

This script removes sensitive files from Git history to ensure they never existed
in the repository. It uses BFG Repo-Cleaner or git filter-branch to remove
files containing credentials, bucket names, and other sensitive data.

Usage:
    python scripts/clean-git-history.py
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

class GitHistoryCleaner:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.sensitive_patterns = [
            'config/aws-credentials.json',
            'AKIA[0-9A-Z]{16}',  # AWS access key pattern
            'REMOVED_BUCKET_NAME ',  # Real bucket name
            '891377140797',  # Real account ID
        ]
        
    def check_bfg_available(self):
        """Check if BFG Repo-Cleaner is available"""
        try:
            result = subprocess.run(['bfg', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def create_bfg_script(self):
        """Create BFG script to remove sensitive files"""
        bfg_script = self.project_root / "bfg-clean.sh"
        
        script_content = """#!/bin/bash
# BFG Repo-Cleaner script to remove sensitive data from Git history

echo "🧹 Cleaning Git history of sensitive data..."

# Remove files that might contain credentials
bfg --delete-files aws-credentials.json
bfg --delete-files aws-config.json
bfg --delete-files sync-config.json

# Remove lines containing sensitive patterns
bfg --replace-text sensitive-patterns.txt

echo "✅ Git history cleaned successfully!"
echo "⚠️  IMPORTANT: Run 'git push --force' to update remote repository"
"""
        
        with open(bfg_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(bfg_script, 0o755)
        return bfg_script
    
    def create_sensitive_patterns_file(self):
        """Create file with sensitive patterns for BFG"""
        patterns_file = self.project_root / "sensitive-patterns.txt"
        
        patterns = [
            # AWS Access Keys
            'AKIA[0-9A-Z]{16}',
            # Real bucket name
            'REMOVED_BUCKET_NAME ',
            # Real account ID
            '891377140797',
            # Real credentials (if any were committed)
            'ycLHdrC3csBcY27AmzVXoZB9pCyvzFt9iIpPa+OK',
        ]
        
        with open(patterns_file, 'w') as f:
            for pattern in patterns:
                f.write(f'{pattern}==>REMOVED\n')
        
        return patterns_file
    
    def create_git_filter_script(self):
        """Create git filter-branch script as alternative to BFG"""
        filter_script = self.project_root / "git-filter-clean.sh"
        
        script_content = """#!/bin/bash
# Git filter-branch script to remove sensitive data from Git history

echo "🧹 Cleaning Git history using git filter-branch..."

# Create a backup branch
git branch backup-before-clean

# Remove sensitive files from all commits
git filter-branch --force --index-filter '
    git rm --cached --ignore-unmatch config/aws-credentials.json 2>/dev/null || true
    git rm --cached --ignore-unmatch config/aws-config.json 2>/dev/null || true
    git rm --cached --ignore-unmatch config/sync-config.json 2>/dev/null || true
' --prune-empty --tag-name-filter cat -- --all

# Clean up refs and force garbage collection
git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ Git history cleaned successfully!"
echo "⚠️  IMPORTANT: Run 'git push --force' to update remote repository"
"""
        
        with open(filter_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(filter_script, 0o755)
        return filter_script
    
    def check_sensitive_data_in_history(self):
        """Check if sensitive data exists in Git history"""
        print("🔍 Checking Git history for sensitive data...")
        
        sensitive_found = False
        
        # Check for AWS access keys
        try:
            result = subprocess.run([
                'git', 'log', '--all', '--full-history', '-p', 
                '|', 'grep', '-E', 'AKIA[0-9A-Z]{16}'
            ], shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                print("❌ Found AWS access keys in Git history")
                sensitive_found = True
        except:
            pass
        
        # Check for real bucket name
        try:
            result = subprocess.run([
                'git', 'log', '--all', '--full-history', '-p',
                '|', 'grep', 'REMOVED_BUCKET_NAME '
            ], shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                print("❌ Found real bucket name in Git history")
                sensitive_found = True
        except:
            pass
        
        # Check for real account ID
        try:
            result = subprocess.run([
                'git', 'log', '--all', '--full-history', '-p',
                '|', 'grep', '891377140797'
            ], shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                print("❌ Found real account ID in Git history")
                sensitive_found = True
        except:
            pass
        
        if not sensitive_found:
            print("✅ No sensitive data found in Git history")
        
        return sensitive_found
    
    def clean_history(self):
        """Clean Git history of sensitive data"""
        print("🧹 Git History Cleaner for AWS S3 Sync")
        print("=" * 50)
        
        # Check if sensitive data exists in history
        if self.check_sensitive_data_in_history():
            print("\n⚠️  SENSITIVE DATA FOUND IN GIT HISTORY")
            print("   Proceeding with cleanup...")
        else:
            print("\n✅ No sensitive data found in Git history")
            print("   Repository appears to be clean already")
            return True
        
        # Check for BFG
        if self.check_bfg_available():
            print("\n🔧 Using BFG Repo-Cleaner (recommended)")
            
            # Create BFG script
            bfg_script = self.create_bfg_script()
            patterns_file = self.create_sensitive_patterns_file()
            
            print(f"📝 Created BFG script: {bfg_script}")
            print(f"📝 Created patterns file: {patterns_file}")
            
            print("\n🚀 To clean Git history:")
            print(f"   1. Run: {bfg_script}")
            print("   2. Run: git push --force")
            print("   3. Delete backup files")
            
        else:
            print("\n🔧 Using git filter-branch (alternative)")
            
            # Create git filter-branch script
            filter_script = self.create_git_filter_script()
            
            print(f"📝 Created filter script: {filter_script}")
            
            print("\n🚀 To clean Git history:")
            print(f"   1. Run: {filter_script}")
            print("   2. Run: git push --force")
            print("   3. Delete backup files")
        
        print("\n⚠️  IMPORTANT WARNINGS:")
        print("   - This will rewrite Git history")
        print("   - All collaborators will need to re-clone")
        print("   - Force push required to update remote")
        print("   - Backup branch created for safety")
        
        return True
    
    def create_cleanup_instructions(self):
        """Create detailed cleanup instructions"""
        instructions_file = self.project_root / "docs/git-history-cleanup.md"
        
        instructions = """# Git History Cleanup Instructions

## Overview
This document provides instructions for cleaning sensitive data from Git history.

## Why Clean Git History?
- Remove any accidentally committed credentials
- Remove real bucket names and account IDs
- Ensure repository is completely safe for public release
- Follow security best practices

## Method 1: BFG Repo-Cleaner (Recommended)

### Prerequisites
```bash
# Install BFG Repo-Cleaner
# macOS
brew install bfg

# Linux
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar -O bfg.jar
```

### Cleanup Steps
```bash
# 1. Create backup
git clone --mirror .git backup-repo

# 2. Run BFG cleanup
./scripts/bfg-clean.sh

# 3. Force push to remote
git push --force

# 4. Clean up
rm -rf backup-repo
rm bfg-clean.sh sensitive-patterns.txt
```

## Method 2: Git Filter-Branch (Alternative)

### Cleanup Steps
```bash
# 1. Create backup
git branch backup-before-clean

# 2. Run filter script
./scripts/git-filter-clean.sh

# 3. Force push to remote
git push --force

# 4. Clean up
git branch -D backup-before-clean
```

## Verification

After cleanup, verify no sensitive data remains:

```bash
# Check for AWS access keys
git log --all --full-history -p | grep -E 'AKIA[0-9A-Z]{16}'

# Check for real bucket name
git log --all --full-history -p | grep 'REMOVED_BUCKET_NAME '

# Check for real account ID
git log --all --full-history -p | grep '891377140797'
```

## Important Notes

- **Force Push Required**: This rewrites history, so force push is needed
- **Collaborator Impact**: All collaborators must re-clone the repository
- **Backup Created**: A backup branch is created before cleanup
- **Test First**: Test on a copy of the repository before running on main

## Safety Checklist

- [ ] Repository backed up
- [ ] Sensitive data identified
- [ ] Cleanup method chosen
- [ ] Test run completed
- [ ] Force push executed
- [ ] Verification completed
- [ ] Backup files cleaned up
"""
        
        instructions_file.parent.mkdir(exist_ok=True)
        with open(instructions_file, 'w') as f:
            f.write(instructions)
        
        print(f"📝 Created cleanup instructions: {instructions_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Clean Git history of sensitive data"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for sensitive data, don't create cleanup scripts"
    )
    
    args = parser.parse_args()
    
    cleaner = GitHistoryCleaner()
    
    if args.check_only:
        cleaner.check_sensitive_data_in_history()
    else:
        cleaner.clean_history()
        cleaner.create_cleanup_instructions()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 