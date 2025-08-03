#!/bin/bash
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
