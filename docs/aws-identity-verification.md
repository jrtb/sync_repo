# AWS Identity Verification Guide

## What This Does
The AWS Identity Verification feature prominently displays IAM username and AWS account information before uploading files to S3. This ensures you're uploading to the correct AWS account and using the intended IAM user, preventing accidental uploads to wrong accounts or with incorrect permissions.

## AWS Concepts Covered
- **IAM Identity Verification**: Using AWS STS to get caller identity
- **Account Management**: Displaying AWS account ID and account aliases
- **Security Best Practices**: Confirming identity before sensitive operations
- **Error Handling**: Graceful handling of authentication and permission issues

## Prerequisites
- AWS credentials configured (access keys or IAM roles)
- IAM permissions for `sts:GetCallerIdentity` and `iam:ListAccountAliases`
- Python boto3 library installed

## Setup Steps
1. **Import the module** - The AWSIdentityVerifier is automatically imported in sync operations
2. **Configure AWS credentials** - Ensure your AWS profile has the necessary permissions
3. **Run sync operations** - Identity verification happens automatically before file uploads

## Testing
```bash
# Test the identity verification module directly
python -c "
from scripts.aws_identity import AWSIdentityVerifier
verifier = AWSIdentityVerifier(profile='your-profile')
identity = verifier.get_identity_info()
print(f'Account: {identity[\"account_id\"]}')
print(f'User: {identity[\"username\"]}')
"

# Test with sync operation (dry run)
python scripts/sync.py --dry-run --local-path ./test-data
```

## Security Notes
- **Account Verification**: Always verify the AWS Account ID matches your intended destination
- **User Permissions**: Ensure the IAM user has appropriate S3 permissions
- **Credential Rotation**: Regularly rotate access keys and use IAM roles when possible
- **MFA**: Enable multi-factor authentication for additional security

## Troubleshooting
- **No credentials found**: Run `aws configure` or set up credentials properly
- **Permission denied**: Ensure IAM user has `sts:GetCallerIdentity` permission
- **Account alias not available**: This is optional and won't affect core functionality

## Integration with Sync Operations
The identity verification is automatically integrated into all sync operations:

1. **Pre-upload verification**: Identity is verified before any files are uploaded
2. **User confirmation**: Users must confirm the account and user before proceeding
3. **Dry run support**: Identity is displayed but no confirmation required in dry run mode
4. **Error handling**: Sync operations are cancelled if identity verification fails

## Example Output
```
================================================================================
🔐 AWS IDENTITY VERIFICATION
================================================================================
📋 AWS Account ID: 123456789012
📋 Account Alias: my-company-account
👤 IAM User: photo-sync-user
🆔 User ID: AIDACKCEVSQ6C2EXAMPLE
🌍 Region: us-east-1
🔗 ARN: arn:aws:iam::123456789012:user/photo-sync-user
🪣 Target Bucket: my-photo-bucket
================================================================================
⚠️  SECURITY WARNING:
   • Verify the AWS Account ID matches your intended destination
   • Ensure you're using the correct IAM user for this operation
   • Files will be uploaded to this account with these permissions
================================================================================

❓ Do you want to proceed with this AWS account? (yes/no): yes
✅ Confirmed - proceeding with sync operation
```

## Educational Value for AWS Certification
This feature demonstrates several important AWS concepts:
- **IAM Identity Management**: Understanding how to verify current identity
- **Security Best Practices**: Confirming identity before sensitive operations
- **Error Handling**: Proper handling of authentication and permission errors
- **User Experience**: Clear communication of security-critical information 