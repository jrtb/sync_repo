# S3 Bucket Versioning Guide

## What This Does
This guide covers S3 bucket versioning implementation for data protection and recovery. Versioning maintains multiple versions of objects, protecting against accidental deletion and enabling point-in-time recovery. Essential for AWS certification study and production data protection.

## AWS Concepts Covered
- **S3 Bucket Versioning**: Data protection and recovery capabilities
- **S3 Lifecycle Management**: Cost optimization with versioned objects
- **IAM Permissions**: Required permissions for versioning operations
- **Security Best Practices**: MFA delete protection for critical data
- **Cost Management**: Storage costs for multiple object versions
- **Compliance**: Data governance and retention policies

## Prerequisites
- AWS CLI configured with appropriate permissions
- S3 bucket created and accessible
- IAM permissions for versioning operations

## Setup Steps

### 1. **Enable Basic Versioning** - Data Protection Foundation
```bash
# Enable versioning on your bucket
python scripts/enable_versioning.py --bucket your-bucket-name
```

**Why this matters**: Versioning protects against accidental deletion and overwrites, maintaining object history.

### 2. **Enable MFA Delete Protection** - Enhanced Security
```bash
# Enable MFA delete for critical data protection
python scripts/enable_versioning.py --bucket your-bucket-name --mfa-delete --mfa-serial arn:aws:iam::123456789012:mfa/user
```

**Why this matters**: MFA delete requires additional authentication to permanently delete versions, preventing unauthorized data loss.

### 3. **Check Versioning Status** - Verification
```bash
# Verify versioning is enabled
python scripts/enable_versioning.py --bucket your-bucket-name --check-status
```

**Why this matters**: Confirms versioning is properly configured and shows current settings.

## Testing

### Verify Versioning Works
```bash
# Upload a test file
aws s3 cp test.txt s3://your-bucket-name/

# Overwrite the file (creates a new version)
echo "updated content" > test.txt
aws s3 cp test.txt s3://your-bucket-name/

# List all versions
aws s3api list-object-versions --bucket your-bucket-name --prefix test.txt
```

### Test MFA Delete (if enabled)
```bash
# Try to delete a version (should require MFA)
aws s3api delete-object --bucket your-bucket-name --key test.txt --version-id VERSION_ID
```

## Security Notes

### IAM Permissions Required
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutBucketVersioning",
                "s3:GetBucketVersioning",
                "s3:ListBucketVersions",
                "s3:GetObjectVersion",
                "s3:DeleteObjectVersion"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

### Security Best Practices
- **Enable MFA Delete** for critical data
- **Use lifecycle policies** to manage version costs
- **Monitor storage costs** regularly
- **Implement access logging** for audit trails
- **Use encryption** for all versioned objects

## Cost Considerations

### Storage Costs
- **Each version** of an object incurs storage costs
- **Use lifecycle policies** to transition old versions to cheaper storage
- **Monitor costs** with CloudWatch metrics

### Lifecycle Policy Example
```json
{
    "Rules": [
        {
            "ID": "VersioningLifecycle",
            "Status": "Enabled",
            "Filter": {},
            "NoncurrentVersionTransitions": [
                {
                    "NoncurrentDays": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "NoncurrentDays": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 365
            }
        }
    ]
}
```

## Troubleshooting

### Common Issues

**Versioning not enabled**
```bash
# Check bucket versioning status
aws s3api get-bucket-versioning --bucket your-bucket-name
```

**Access denied errors**
- Verify IAM permissions include versioning operations
- Check bucket policy allows versioning actions

**High storage costs**
- Implement lifecycle policies to manage old versions
- Consider transitioning to cheaper storage classes
- Monitor with CloudWatch metrics

### Error Messages

**"Access Denied"**
- Ensure IAM user has `s3:PutBucketVersioning` permission
- Check bucket policy doesn't block versioning

**"MFA serial required"**
- Provide MFA device serial number when using `--mfa-delete`
- Format: `arn:aws:iam::ACCOUNT:mfa/USERNAME`

## AWS Certification Topics

### S3 Storage Classes and Lifecycle Management
- **Versioning** works with all storage classes
- **Lifecycle policies** can transition versions between classes
- **Cost optimization** through intelligent tiering

### Data Protection and Recovery Strategies
- **Point-in-time recovery** using object versions
- **Accidental deletion protection** with versioning
- **Compliance requirements** for data retention

### Security and Compliance Best Practices
- **MFA delete** for enhanced security
- **Access control** with IAM policies
- **Audit trails** with access logging

### Cost Optimization and Management
- **Storage cost monitoring** for versioned objects
- **Lifecycle management** to reduce costs
- **CloudWatch metrics** for cost tracking

## Integration with Sync Script

### Automatic Versioning Setup
The sync setup process now automatically enables versioning:

```bash
# Setup includes versioning by default
python scripts/setup-iam-user.py --bucket-name your-bucket-name
```

### Manual Versioning for Existing Buckets
```bash
# Enable versioning on existing bucket
python scripts/enable_versioning.py --bucket existing-bucket-name
```

## Quick Reference Commands

```bash
# Enable basic versioning
python scripts/enable_versioning.py --bucket my-bucket

# Enable with MFA delete
python scripts/enable_versioning.py --bucket my-bucket --mfa-delete --mfa-serial arn:aws:iam::123456789012:mfa/user

# Check status
python scripts/enable_versioning.py --bucket my-bucket --check-status

# List all versions of an object
aws s3api list-object-versions --bucket my-bucket --prefix filename.txt

# Download specific version
aws s3api get-object --bucket my-bucket --key filename.txt --version-id VERSION_ID output.txt

# Delete specific version (requires MFA if enabled)
aws s3api delete-object --bucket my-bucket --key filename.txt --version-id VERSION_ID
```

---

**Last Updated**: August 1, 2025  
**Purpose**: S3 bucket versioning implementation guide  
**Status**: Active 