# AWS S3 Sync – Full‑Screen TUI

Modern, focused S3 file synchronization with a full‑screen terminal UI. The TUI provides a clear, BBS‑style overview, discovery/check progress, live logs, and a succinct summary.

## What You Get

- **Full‑screen TUI** for end‑to‑end sync workflow
- **Incremental and concurrent uploads** with verification
- **Clear progress panes** for discovery, checking, and upload
- **Minimal confirmations** inline in the log pane
- **Cost hints** (current S3 month‑to‑date and basic estimates)

## AWS Concepts Covered

- **IAM**: Identity management and least-privilege access
- **S3**: Object storage, storage classes, and lifecycle policies
- **CloudWatch**: Monitoring, logging, and metrics
- **Security**: Encryption, access control, and best practices

## Quick Start (TUI‑first)

### Prerequisites
- Python 3.9+
- AWS CLI installed and configured
- An AWS profile (recommended: `s3-sync`)

### Run the TUI
```bash
# Option A: Install a convenient shell alias (recommended)
./install-path-alias.sh
s3-sync --help
s3-sync --local-path ./data --profile s3-sync

# Option B: Run directly
python scripts/sync.py --help
python scripts/sync.py --local-path ./data --profile s3-sync
```

### Security Note
This repository contains **template files only**. Real credentials are:
- Stored in AWS CLI profiles (`~/.aws/credentials`)
- Optionally generated during setup
- Never committed to version control

### Security Setup
Before using this system:

1. **Never commit real credentials** - The `.gitignore` file prevents credential files from being committed
2. **Use AWS CLI profiles** - Set up credentials using `aws configure --profile s3-sync`
3. **Follow least-privilege principle** - The setup scripts create minimal IAM permissions
4. **Enable encryption** - All S3 objects are encrypted by default
5. **Monitor access** - CloudWatch logs track all operations

**Template files included:**
- `config/aws-config-template.json` - Copy to `config/aws-config.json` and customize
- `config/aws-credentials-template.json` - Copy to `config/aws-credentials.json` and add real credentials

## Repository Structure

```
sync_repo_clean/
├── scripts/           # TUI entrypoint (scripts/sync.py) and compatibility utilities
├── core/              # Refactored sync engine and config loading
├── tui/               # Full‑screen dashboard components
├── config/            # Templates and config manager
├── docs/              # Guides (with legacy overview in docs/LEGACY.md)
├── tests/             # Comprehensive test suite
└── logs/              # Sync operation logs
```

## Key Features

### Core Sync Engine
- Incremental file synchronization
- Multipart uploads for large files
- Concurrent uploads with progress callbacks
- Verification and retries with exponential backoff

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

### Legacy Utilities (Still Available)
- Setup, validate, backup/restore, cleanup, storage‑class analysis, policy validation, and more remain for compatibility and tests.
- See `docs/LEGACY.md` for the curated list and current status.

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

See Quick Start above for both alias and direct execution options.

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
# Run the full‑screen TUI
s3-sync --local-path ./photos --profile s3-sync --dry-run  # test first
s3-sync --local-path ./photos --profile s3-sync            # actual sync
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

### Core Guides
- [System Overview](docs/system-overview.md)
- [Usage Guide](docs/usage-guide.md)
- [Quick Reference](docs/quick-reference.md)

### Legacy and Utilities
- [Legacy utilities and docs](docs/LEGACY.md)

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

This repository now prioritizes the full‑screen TUI workflow and refactored core engine. Legacy utilities are maintained for compatibility and tests but are no longer the primary interface.

## Contributing

Focus areas for contributions:
- Improving sync efficiency and reliability
- Enhancing security practices
- Optimizing storage costs
- Adding educational content for AWS certification

## License

[Add appropriate license information] 