# Git History Cleanup Instructions

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
