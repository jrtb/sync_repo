# Retry Failed Uploads Guide

## What This Does
Automatically retries S3 uploads that failed during the main sync operation. This script reads the error log, identifies failed files, and attempts to upload them with enhanced retry logic and error handling.

## AWS Concepts Covered
- **S3 Multipart Uploads**: Handles large file uploads with retry logic
- **Error Handling**: Implements exponential backoff for network issues
- **CloudWatch Logging**: Structured logging for operational monitoring
- **IAM Permissions**: Requires S3 upload permissions
- **Cost Optimization**: Only retries files that actually failed

## Prerequisites
- AWS credentials configured and validated
- Previous sync operation with failed uploads
- Error log file (`logs/s3-sync-errors.log`) containing failed upload records

## Setup Steps
1. **Verify AWS credentials** - Ensure access to S3 bucket
   ```bash
   python scripts/test-credentials.py
   ```

2. **Check error log** - Verify failed uploads exist
   ```bash
   ls -la logs/s3-sync-errors.log
   ```

3. **Identify base directory** - Determine where original files are located
   ```bash
   # If files are in parent directory
   python scripts/retry_failed_uploads.py --base-dir ..
   ```

## Usage

### Dry Run (Recommended First)
```bash
python scripts/retry_failed_uploads.py --dry-run --verbose --base-dir ..
```

### Actual Retry
```bash
python scripts/retry_failed_uploads.py --verbose --base-dir ..
```

### Command Line Options
- `--dry-run`: Show what would be done without uploading
- `--verbose`: Display detailed progress information
- `--base-dir`: Specify base directory for resolving relative paths
- `--config`: Use custom configuration file

## Testing
```bash
# Test with dry run
python scripts/retry_failed_uploads.py --dry-run --verbose --base-dir ..

# Verify error log parsing
python scripts/retry_failed_uploads.py --dry-run --verbose

# Check specific failed files
grep "upload operation for" logs/s3-sync-errors.log
```

## Security Notes
- **IAM Permissions**: Requires `s3:PutObject` and `s3:PutObjectAcl` permissions
- **Error Logs**: Contains file paths - ensure logs are secured
- **Retry Limits**: Configured to prevent infinite retry loops
- **Network Security**: Uses HTTPS for all S3 communications

## Troubleshooting

### Files Not Found
- **Issue**: Script can't locate files
- **Solution**: Use `--base-dir` to specify correct directory
- **Example**: `--base-dir /path/to/astro/files`

### S3 Key Errors
- **Issue**: Invalid S3 key format (e.g., `../astro/` prefix)
- **Solution**: Script automatically removes `../astro/` prefix
- **Verification**: Check S3 key format in verbose output

### Permission Errors
- **Issue**: AWS credentials insufficient
- **Solution**: Verify IAM permissions include S3 upload access
- **Test**: Run `python scripts/test-credentials.py`

## AWS Certification Context

### S3 Best Practices
- **Multipart Uploads**: Essential for large files (>100MB)
- **Retry Logic**: Critical for network reliability
- **Error Handling**: Required for production systems

### Monitoring and Logging
- **Structured Logging**: CloudWatch integration for operational visibility
- **Metrics Collection**: Track retry attempts and success rates
- **Cost Monitoring**: Only upload files that actually failed

### Security Implementation
- **IAM Least Privilege**: Minimal permissions for retry operations
- **Encryption**: Server-side encryption for all uploads
- **Audit Trail**: Comprehensive logging for compliance

## Integration with Main Sync

The retry script complements the main sync operation:
- **Main Sync**: Handles initial upload with retry logic
- **Retry Script**: Focused recovery for persistent failures
- **Error Log**: Provides audit trail of failed operations

This separation allows for targeted recovery without re-running the entire sync operation. 