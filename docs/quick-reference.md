# Quick Reference Guide

## Essential Commands

### Setup and Validation
```bash
# Create IAM user and S3 bucket
python scripts/setup-iam-user.py --bucket-name my-sync-bucket

# Test credentials and verify setup
python scripts/test-credentials.py
python scripts/verify-production-setup.py

# Initialize project structure
python scripts/setup.py --init

# Validate current setup
python scripts/validate.py --all
```

### Sync Operations
```bash
# Using path alias (if installed)
s3-sync --help                    # Show help
s3-sync --dry-run                 # Preview sync
s3-sync --local-path ./photos     # Sync specific directory

# Using direct script execution
python scripts/sync.py --help
python scripts/sync.py --dry-run
python scripts/sync.py --local-path ./photos --bucket my-sync-bucket
python scripts/sync.py --verbose
python scripts/sync.py --config config/sync-config.json
```

### Storage Management
```bash
# Analyze storage costs
python scripts/storage-class-manager.py --analyze-costs

# Optimize storage classes
python scripts/storage-class-manager.py --optimize-storage --dry-run
python scripts/storage-class-manager.py --optimize-storage
```

### Maintenance
```bash
# Create backup before changes
python scripts/backup.py --local
python scripts/backup.py --s3

# Perform maintenance operations
python scripts/cleanup.py --old-backups
python scripts/cleanup.py --temp-files

# Restore from backup
python scripts/restore.py --from-backup backup.tar.gz
```



## AWS Concepts Covered

### S3 (Simple Storage Service)
- **Storage Classes**: STANDARD, STANDARD_IA, GLACIER
- **Encryption**: Server-side encryption with AES256
- **Versioning**: Track multiple versions of objects
- **Lifecycle Policies**: Automatic storage class transitions
- **Multipart Uploads**: Handle large files efficiently

### IAM (Identity and Access Management)
- **Principle of Least Privilege**: Minimal required permissions
- **Access Keys**: Programmatic access to AWS services
- **Policies**: JSON documents defining permissions
- **Users**: Individual AWS accounts with specific permissions

### CloudWatch
- **Monitoring**: Track sync operations and performance
- **Logging**: Structured logging for troubleshooting
- **Metrics**: Performance and cost metrics
- **Alerts**: Notifications for sync issues

## Configuration Files

### `config/aws-config.json`
- AWS region and profile settings
- S3 bucket configuration
- Sync parameters and filters
- Monitoring and notification settings

### `config/sync-config.json`
- Detailed sync behavior settings
- File handling parameters
- Performance optimization settings
- Backup and recovery options

## Security Best Practices

### Credential Management
- Use IAM users with minimal permissions
- Rotate access keys regularly
- Never commit credentials to version control
- Use AWS profiles for different environments

### Data Protection
- Enable server-side encryption
- Use HTTPS for data in transit
- Implement proper access controls
- Monitor access patterns

### Cost Optimization
- Use appropriate storage classes
- Implement lifecycle policies
- Monitor usage and costs
- Clean up unused resources

## Troubleshooting

### Common Issues
1. **Credentials not found**: Run `setup-iam-user.py`
2. **Permission denied**: Check IAM user permissions
3. **Bucket not found**: Verify bucket name and region
4. **Upload failures**: Check network and file permissions

### Debug Commands
```bash
# Test AWS connectivity
aws sts get-caller-identity --profile s3-sync

# List S3 buckets
aws s3 ls --profile s3-sync

# Check sync logs
tail -f logs/sync.log
```

## Performance Tips

### Upload Optimization
- Use concurrent uploads (default: 5)
- Implement multipart uploads for large files
- Configure appropriate chunk sizes
- Monitor network performance

### Storage Optimization
- Choose appropriate storage classes
- Implement lifecycle policies
- Use compression where beneficial
- Monitor storage costs

### Monitoring and Reporting
- Track sync performance with CloudWatch metrics
- Generate cost analysis and storage usage reports
- Set up automated alerts for critical issues
- Monitor throughput, latency, and error rates

## System Status

### Completed ✅
- **Phase 1**: Core infrastructure setup
- **Phase 2**: Core sync scripts with incremental sync
- **Phase 3**: Storage class management with cost optimization
- **Phase 4**: Access policies and security features
- **Phase 5**: Configuration and utilities

### Current Status
- **Phase 6**: Monitoring and reporting ✅
- **Phase 7**: Advanced features (planned)

### Key Features Available
- Complete sync functionality with multipart uploads
- Storage class optimization and cost management
- Comprehensive backup and restore capabilities
- Security validation and policy management
- Configuration management and validation
- Automated cleanup and maintenance tools
- Real-time monitoring with CloudWatch integration
- Performance analytics and cost analysis
- Automated alerting and reporting systems 