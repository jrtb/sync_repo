# AWS S3 Sync System

A comprehensive AWS S3 file synchronization and management system designed for both educational AWS certification study and practical file backup/sync operations.

## What This System Does

Provides secure, cost-optimized file synchronization with:
- **Complete AWS Integration**: IAM, S3, CloudWatch, and security services
- **Storage Class Management**: Automatic cost optimization using S3 storage classes
- **Security-First Design**: IAM roles, encryption, access policies, and monitoring
- **Educational Focus**: Learn AWS concepts through practical implementation
- **Production Ready**: Backup, restore, validation, and maintenance tools

## AWS Concepts Covered

- **IAM**: Identity management and least-privilege access
- **S3**: Object storage, storage classes, and lifecycle policies
- **CloudWatch**: Monitoring, logging, and metrics
- **Security**: Encryption, access control, and best practices

## Quick Start

### Prerequisites
- Python 3.7+
- AWS CLI installed and configured
- AWS account with IAM permissions

### Initial Setup
```bash
# 1. Clone the repository
git clone <your-repo-url>
cd sync_repo

# 2. Create IAM user and S3 bucket (automated setup)
python scripts/setup-iam-user.py --bucket-name my-sync-bucket

# 3. Test credentials and verify setup
python scripts/test-credentials.py
python scripts/verify-production-setup.py

# 4. Initialize project structure
python scripts/setup.py --init
```

**What this creates**:
- IAM user with minimal S3 permissions
- S3 bucket with encryption and versioning
- CloudWatch monitoring permissions
- AWS CLI profile (`s3-sync`)
- Secure credential storage (never committed to git)
- Complete project structure and configurations

### Security Note
This repository contains **template files only**. Real credentials are:
- Stored in AWS CLI profiles (`~/.aws/credentials`)
- Generated during setup (`config/aws-credentials.json`)
- Never committed to version control

## Repository Structure

```
sync_repo/
├── scripts/           # Core sync and management scripts
├── config/            # AWS and sync configuration
├── docs/              # Educational documentation
├── templates/         # IAM and bucket policy templates
├── tests/             # Comprehensive test suite
└── logs/              # Sync operation logs
```

## Key Features

### Core Sync Engine
- Incremental file synchronization to S3
- Multipart uploads for large files
- Concurrent uploads for performance
- Dry-run mode for testing
- Progress reporting and logging

### Storage Class Optimization
- **Standard**: Frequently accessed data
- **IA (Infrequent Access)**: Less frequently accessed
- **Glacier**: Long-term archival
- **Intelligent Tiering**: Automatic optimization

### Security Features
- IAM roles with minimal permissions
- Server-side encryption enabled
- Bucket versioning for data protection
- Access logging and monitoring

### Management Tools
- Configuration management and validation
- Backup and restore capabilities
- Automated cleanup and maintenance
- Comprehensive system validation

### Monitoring
- CloudWatch metrics for sync operations
- Cost tracking and optimization
- Performance monitoring
- Error tracking and alerting

## Security

### Credential Management
This system uses **secure credential injection**:

1. **AWS CLI Profiles**: Primary authentication via `~/.aws/credentials`
2. **Template Files**: Safe placeholder files in repository
3. **Setup Scripts**: Generate real credentials during setup
4. **Git Ignore**: Prevents credential files from being committed

### Security Features
- ✅ **No hardcoded credentials** in repository
- ✅ **AWS CLI profile authentication** (industry standard)
- ✅ **Template-based configuration** (safe for public repos)
- ✅ **Automatic credential generation** during setup
- ✅ **Restrictive file permissions** (600 for credential files)

## Configuration

### Template Files
The repository includes safe template files:
- `config/aws-credentials-template.json` - Credential template
- `config/aws-config-template.json` - AWS configuration template
- `config/sync-config-template.json` - Sync configuration template

### AWS Configuration
```json
{
  "aws": {
    "region": "us-east-1",
    "profile": "s3-sync"
  },
  "s3": {
    "bucket_name": "my-sync-bucket",
    "storage_class": "STANDARD_IA"
  }
}
```

### Sync Configuration
```json
{
  "sync": {
    "local_path": ".",
    "exclude_patterns": ["*.tmp", ".DS_Store"],
    "dry_run": false
  }
}
```

## Installation Options

### Option 1: Path Alias (Recommended)
Install the `s3-sync` command to be available from any directory:

```bash
./install-path-alias.sh
```

After installation, you can use:
```bash
s3-sync --help                    # Show help
s3-sync --dry-run                 # Preview sync
s3-sync --local-path ./photos     # Sync specific directory
```

### Option 2: Direct Script Execution
Run the sync script directly:

```bash
python scripts/sync.py --help
python scripts/sync.py --dry-run
python scripts/sync.py --local-path ./photos
```

## Common Commands

### Setup and Validation
```bash
# Create IAM user and bucket
python scripts/setup-iam-user.py --bucket-name my-bucket

# Test credentials and verify setup
python scripts/test-credentials.py
python scripts/verify-production-setup.py

# Initialize project structure
python scripts/setup.py --init
```

### Sync Operations
```bash
# Validate current setup
python scripts/validate.py --all

# Run sync operation
python scripts/sync.py --local-path ./photos --dry-run  # Test first
python scripts/sync.py --local-path ./photos            # Actual sync

# Optimize storage costs
python scripts/storage-class-manager.py --analyze-costs
python scripts/storage-class-manager.py --optimize-storage --dry-run
```

### Maintenance
```bash
# Create backup before changes
python scripts/backup.py --local

# Perform maintenance operations
python scripts/cleanup.py --old-backups
python scripts/storage-class-manager.py --optimize-storage

# Validate system health
python scripts/validate.py --all
```

## Security Best Practices

### IAM Security
- Use IAM roles instead of access keys when possible
- Follow principle of least privilege
- Rotate access keys regularly
- Enable MFA for all users

### S3 Security
- Enable server-side encryption
- Use bucket policies for access control
- Enable versioning for data protection
- Configure access logging

### Credential Management
- Never commit credentials to version control
- Use secure credential storage
- Monitor access with CloudTrail
- Implement proper access controls

## Troubleshooting

### Common Issues
- **Access Denied**: Check IAM permissions and bucket policies
- **Invalid Credentials**: Verify AWS CLI configuration
- **Bucket Not Found**: Ensure bucket exists in correct region
- **Network Issues**: Check connectivity and firewall settings

### Debug Commands
```bash
aws sts get-caller-identity    # Verify identity
aws s3 ls --debug              # Debug S3 operations
aws configure list             # Show configuration
```

## Documentation

### Core Documentation
- **[System Overview](docs/system-overview.md)**: Complete system architecture and workflow integration
- **[Usage Guide](docs/usage-guide.md)**: Complete walkthrough from setup to maintenance
- **[Quick Reference](docs/quick-reference.md)**: Essential commands and concepts

### Setup and Configuration
- **[AWS Setup](docs/aws-setup.md)**: AWS CLI and account configuration
- **[IAM Setup](docs/iam-user-setup.md)**: IAM user creation and permissions
- **[AWS CLI Installation](docs/aws-cli-installation.md)**: AWS CLI installation guide

### Specialized Guides
- **[Security Guide](docs/security.md)**: Security implementation and best practices
- **[Storage Class Management](docs/storage-class-management.md)**: Cost optimization and storage class management
- **[Testing Guide](docs/testing.md)**: Comprehensive testing framework

### Development
- **[Workflow](workflow.md)**: Documentation and development workflow directive
- **[Style Guide](docs/documentation-style-guide.md)**: Documentation standards

## Certification Focus

### AWS Services Covered
- **SAA-C03**: S3, IAM, CloudWatch
- **SAP-C02**: Advanced security and monitoring
- **SCS-C02**: Security-focused implementation

### Key Learning Areas
- IAM identity management and permissions
- S3 object storage and security
- CloudWatch monitoring and logging
- Security best practices and compliance
- Cost optimization and management

## Development Status

### Completed ✅
- IAM user setup with minimal permissions
- S3 bucket creation with security features
- CloudWatch monitoring integration
- Core sync functionality with incremental sync
- Storage class management with cost optimization
- Configuration management and validation
- Backup, restore, and cleanup utilities
- Comprehensive test coverage
- Educational documentation structure

### In Progress 🔄
- Enhanced monitoring and reporting
- Advanced security features
- Performance optimization

### Planned 📋
- Automated sync scheduling
- Event-driven syncs
- Advanced monitoring and alerting
- Lambda function integration

## Contributing

Focus areas for contributions:
- Improving sync efficiency and reliability
- Enhancing security practices
- Optimizing storage costs
- Adding educational content for AWS certification

## License

[Add appropriate license information] 