# AWS CLI Setup Guide

## What This Does
Sets up AWS CLI for S3 sync operations. Essential for AWS certification and automation.

## AWS Concepts Covered
- **AWS CLI**: Command-line interface for AWS services
- **IAM Credentials**: Authentication for programmatic access
- **S3 Permissions**: Access control for object storage
- **CloudWatch**: Monitoring and logging capabilities

## Prerequisites
- Python 3.7+
- AWS CLI installation
- AWS account with appropriate permissions

## AWS CLI Installation

### macOS
```bash
brew install awscli  # Using Homebrew
```

### Linux
```bash
# Ubuntu/Debian
sudo apt-get install awscli

# Or via pip
pip install awscli
```

### Windows
Download from: https://awscli.amazonaws.com/AWSCLIV2.msi

## AWS Credentials Setup

### Option 1: AWS CLI Configure (Recommended)
```bash
aws configure  # Sets up credentials and default region
```

**What this does**: Creates `~/.aws/credentials` and `~/.aws/config` files.

### Option 2: IAM Role (EC2)
If running on EC2, attach an IAM role with S3 permissions instead of access keys.

### Option 3: AWS Profiles
```bash
aws configure --profile production  # Multiple environments
```

## Required IAM Permissions

### S3 Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",     // Read files from S3
                "s3:PutObject",     // Upload files to S3
                "s3:DeleteObject",  // Delete files from S3
                "s3:ListBucket"     // List bucket contents
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

### CloudWatch Permissions (for monitoring)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData",    // Send metrics
                "logs:CreateLogGroup",         // Create log groups
                "logs:PutLogEvents"            // Write logs
            ],
            "Resource": "*"
        }
    ]
}
```

## S3 Bucket Setup

### Create S3 Bucket
```bash
aws s3 mb s3://your-sync-bucket-name --region us-east-1
```

### Enable Security Features
```bash
# Enable versioning for data protection
aws s3api put-bucket-versioning \
    --bucket your-sync-bucket-name \
    --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
    --bucket your-sync-bucket-name \
    --server-side-encryption-configuration '{
        "Rules": [
            {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }
        ]
    }'
```

## Configuration Files

### Update aws-config.json
1. Copy `config/aws-config.json` to your working directory
2. Update these fields:
   - `aws.region`: Your AWS region
   - `aws.profile`: Your AWS profile name
   - `s3.bucket_name`: Your S3 bucket name
   - `sync.local_directory`: Path to your local directory

### Update sync-config.json
1. Copy `config/sync-config.json` to your working directory
2. Customize sync settings based on your needs

## Testing Setup

### Verify AWS CLI Configuration
```bash
aws sts get-caller-identity  # Shows your AWS account info
```

### Test S3 Access
```bash
aws s3 ls s3://your-bucket-name  # List bucket contents
```

### Test Upload/Download
```bash
echo "test" > test.txt
aws s3 cp test.txt s3://your-bucket-name/  # Upload
aws s3 cp s3://your-bucket-name/test.txt test-download.txt  # Download
aws s3 rm s3://your-bucket-name/test.txt  # Clean up
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
- **Region Mismatch**: Ensure bucket and CLI region match
- **Network Issues**: Check connectivity and firewall settings

### Debug Commands
```bash
aws --version                   # Check CLI version
aws configure list              # Show configuration
aws s3 ls --debug              # Debug S3 operations
aws s3api get-bucket-policy --bucket your-bucket-name  # Check bucket policy
```

## Next Steps

After completing this setup:
1. Update configuration files with your specific values
2. Test the sync functionality with a small directory
3. Review and adjust storage class policies
4. Set up monitoring and alerting 