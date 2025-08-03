# Documentation and Development Workflow Directive

## Purpose
This file serves as the entry point for all changes - both documentation and code. This repository is both educational (AWS certification study) and practical (photo syncing tool implementation). Follow this workflow for every modification to ensure consistency, educational value, and proper cleanup.

## Workflow for All Changes

### 1. **Read and Understand**
- Read the existing documentation to understand current state
- Review `docs/documentation-style-guide.md` for style requirements
- Understand the educational focus for AWS certification study
- Review existing code to understand current implementation

### 2. **Style Guide Compliance**
All documentation must follow these principles:
- **Educational First**: Explain why, not just how
- **Concise and Direct**: Remove unnecessary verbosity
- **AWS Certification Focus**: Connect to certification topics
- **Security Notes**: Include relevant security considerations

### 3. **Documentation Structure**
Use this template for new documentation:
```markdown
# [Feature] Guide

## What This Does
Brief explanation of the feature and its AWS context.

## AWS Concepts Covered
- List relevant AWS services and concepts
- Explain why they're important for certification

## Prerequisites
- Only essential requirements

## Setup Steps
1. **Step with explanation** - Why this matters
2. **Next step** - What AWS service this uses

## Testing
Quick verification commands with explanations.

## Security Notes
Key security considerations and best practices.

## Troubleshooting
Only common, non-obvious issues.
```

### 4. **Update Process**
For every change made:

1. **Read existing docs** to understand current state
2. **Apply style guide** principles to new/updated content
3. **Make changes** (documentation and/or code)
4. **Update related docs** if needed
5. **Add and run tests** for new functionality

## Repository Purpose

### Educational Focus
- **AWS Certification Study**: Learn IAM, S3, CloudWatch concepts
- **Security Best Practices**: Understand encryption, access control
- **Cost Optimization**: Learn storage classes and lifecycle policies
- **Monitoring**: Understand CloudWatch metrics and logging

### Practical Implementation
- **Photo Syncing Tool**: Real-world application development
- **S3 Integration**: Practical file storage and retrieval
- **Automation**: Scripts for setup and management
- **Production Ready**: Security, monitoring, and maintenance

## Key Documentation Files

### Core Documentation
- `README.md` - Main project overview
- `workflow.md` - This workflow directive (top level)
- `docs/documentation-style-guide.md` - Style standards
- `docs/quick-reference.md` - Essential commands and concepts
- `docs/aws-setup.md` - AWS CLI and account setup
- `docs/iam-user-setup.md` - IAM user creation and permissions
- `docs/production-resources.md` - Production infrastructure details
- `docs/setup-summary.md` - Setup completion summary
- `docs/aws-cli-installation.md` - AWS CLI installation guide

### Scripts (Practical Implementation)
- `scripts/setup-iam-user.py` - IAM user setup
- `scripts/test-credentials.py` - Credential testing
- `scripts/verify-production-setup.py` - Setup verification
- `scripts/regenerate-credentials.py` - Credential management
- `scripts/sync.py` - Main sync script ✅
- `scripts/storage-class-manager.py` - Storage optimization ✅
- `scripts/retry_failed_uploads.py` - Failed upload recovery ✅

## Development Areas

### Completed ✅
- IAM user setup with minimal permissions
- S3 bucket creation with security features
- CloudWatch monitoring integration
- Educational documentation structure
- Core sync functionality with incremental sync
- Storage class management with cost optimization
- Comprehensive test coverage
- Monitoring and reporting with CloudWatch integration
- Performance analytics and cost analysis
- Automated alerting and reporting systems
- Failed upload retry functionality with enhanced error handling

### In Progress 🔄
- Advanced security features
- Monitoring and reporting
- Performance optimization

### Planned 📋
- Photo syncing implementation
- Automated sync scheduling
- Cost optimization tools
- Advanced monitoring and alerting

## Style Guide Summary

### What to Include
- **AWS concepts** and why they matter
- **Security implications** of each step
- **Cost considerations** where relevant
- **Best practices** with brief explanations
- **Common mistakes** to avoid
- **Practical implementation** details

### What to Exclude
- Repetitive installation instructions
- Obvious troubleshooting steps
- Excessive command-line examples
- Marketing language or unnecessary context
- Step-by-step GUI instructions (prefer CLI)

### Writing Style
- Use active voice
- Be direct and clear
- Explain one concept at a time
- Use consistent terminology
- Include brief explanations for AWS services
- Connect theory to practical implementation

## Checklist for Every Change

Before completing any work:

- [ ] Read existing documentation to understand context
- [ ] Review style guide for compliance
- [ ] Make changes (docs and/or code) following educational, concise approach
- [ ] Update related documentation if needed
- [ ] Add tests for new functionality (if code changes)
- [ ] Run all tests to ensure nothing is broken
- [ ] Verify all changes follow the established style
- [ ] Ensure educational value for AWS certification study
- [ ] Test practical functionality if code changes were made

## Quick Reference Commands

```bash
# Test credentials
python scripts/test-credentials.py

# Verify production setup
python scripts/verify-production-setup.py

# Regenerate credentials if needed
python scripts/regenerate-credentials.py

# Test sync functionality
python scripts/sync.py --dry-run

# Retry failed uploads
python scripts/retry_failed_uploads.py --dry-run --verbose --base-dir ..

# Analyze storage costs
python scripts/storage-class-manager.py --analyze-costs

# Optimize storage (dry run)
python scripts/storage-class-manager.py --optimize-storage --dry-run

# Run all tests
python run_tests.py

# Run specific test modules
python -m pytest tests/test_credentials.py
python -m pytest tests/test_sync.py
python -m pytest tests/test_storage_class_manager.py
```

## Security Reminders

- Never commit credentials to version control
- Use IAM roles when possible instead of access keys
- Rotate access keys regularly
- Enable MFA for additional security
- Follow principle of least privilege
- Encrypt data at rest and in transit

---

**Last Updated**: August 1, 2025  
**Purpose**: Documentation and development workflow directive  
**Status**: Active 