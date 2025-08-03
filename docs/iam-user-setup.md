# IAM User Setup

## What This Does
Creates an IAM user with minimal S3 permissions for sync operations. Demonstrates AWS security best practices and IAM concepts.

## AWS Concepts Covered
- **IAM Users**: Identity for programmatic access
- **IAM Policies**: JSON documents defining permissions
- **Principle of Least Privilege**: Granting minimal required access
- **S3 Security**: Bucket-specific access control
- **CloudWatch**: Monitoring and logging permissions

## Prerequisites
- AWS CLI installed and configured
- Administrative access to create IAM users and policies
- S3 bucket name (globally unique)

## Quick Setup

### Interactive Mode (Recommended)
```bash
python scripts/setup-iam-user.py
```

The script will prompt for:
- **IAM Username** (default: `s3-sync-user`)
- **S3 Bucket Name** (required)

### Command Line Arguments
```bash
python scripts/setup-iam-user.py --bucket-name your-sync-bucket --username s3-sync-user
```

## What the Script Creates

1. ✅ **IAM User**: New user for programmatic access
2. ✅ **S3 Bucket**: Creates bucket if it doesn't exist
3. ✅ **Access Keys**: Generates access key and secret
4. ✅ **IAM Policies**: Creates S3 sync and CloudWatch policies
5. ✅ **Policy Attachment**: Attaches policies to the user
6. ✅ **Credentials**: Saves to `config/aws-credentials.json`

## IAM Policies Created

### S3 Sync Policy
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

### CloudWatch Monitoring Policy
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

## Configuration Files

### AWS Credentials File
After running the script, credentials are saved to `config/aws-credentials.json`:

```json
{
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "...",
  "region": "us-east-1",
  "username": "s3-sync-user",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### AWS Configuration Template
Copy and customize `config/aws-config-template.json`:

```bash
cp config/aws-config-template.json config/aws-config.json
```

Then edit the file to match your requirements:
- Replace `YOUR-BUCKET-NAME` with your actual bucket name
- Adjust sync settings, storage classes, and monitoring options

## Testing the Setup

### Test AWS Credentials
```bash
# Configure AWS CLI with the new credentials
aws configure --profile s3-sync

# Test access to S3
aws s3 ls s3://your-bucket-name --profile s3-sync
```

### Test S3 Operations
```bash
# List bucket contents
aws s3 ls s3://your-bucket-name --profile s3-sync

# Upload a test file
echo "test" > test.txt
aws s3 cp test.txt s3://your-bucket-name/ --profile s3-sync

# Download the file
aws s3 cp s3://your-bucket-name/test.txt test-download.txt --profile s3-sync
```

### Test CloudWatch Permissions
```bash
# Send a test metric
aws cloudwatch put-metric-data \
  --namespace "S3Sync" \
  --metric-data MetricName=TestMetric,Value=1 \
  --profile s3-sync
```

## Security Best Practices

### Credential Security
- ✅ Credentials saved with restrictive permissions (600)
- ✅ File stored in `config/` directory
- ⚠️ **Never commit credentials to version control**
- ⚠️ **Rotate access keys regularly**

### IAM Security
- ✅ Minimal required permissions (principle of least privilege)
- ✅ Bucket-specific access (not global S3 access)
- ✅ CloudWatch namespace restrictions
- ✅ No administrative permissions

### S3 Security
- ✅ Server-side encryption enabled by default
- ✅ Versioning enabled for data protection
- ✅ Lifecycle policies for cost optimization
- ✅ Access logging recommended

## Troubleshooting

### Common Issues

#### AWS CLI Not Configured
```bash
aws configure  # Configure with admin credentials
```

#### Insufficient Permissions
```bash
aws sts get-caller-identity  # Check current identity
aws iam get-user            # Check user details
```

#### Bucket Name Already Exists
- S3 bucket names must be globally unique
- Try a different bucket name or use a unique prefix

#### Policy Creation Fails
- Ensure your account has IAM permissions
- Check for policy name conflicts
- Verify JSON syntax in policy templates

### Error Messages

#### "Access Denied"
- Your AWS account needs IAM permissions
- Contact your AWS administrator

#### "Bucket Already Exists"
- Choose a different bucket name
- Use a unique prefix (e.g., `mycompany-sync-2024`)

#### "Invalid Policy Document"
- Check JSON syntax in policy templates
- Ensure all required fields are present

## Usage Examples

### Interactive Mode (Easiest)
```bash
python scripts/setup-iam-user.py
```

### Partial Arguments
```bash
# Provide bucket name, prompt for username
python scripts/setup-iam-user.py --bucket-name my-bucket

# Provide username, prompt for bucket name
python scripts/setup-iam-user.py --username my-user
```

### Non-Interactive Mode
```bash
# All arguments provided
python scripts/setup-iam-user.py --username my-user --bucket-name my-bucket --region us-west-2
```

## Manual Setup (Alternative)

If you prefer to set up manually using AWS CLI commands:

### 1. Create IAM User
```bash
aws iam create-user --user-name s3-sync-user
```

### 2. Create Access Key
```bash
aws iam create-access-key --user-name s3-sync-user
```

### 3. Create S3 Bucket
```bash
aws s3api create-bucket --bucket your-bucket-name --region us-east-1
```

### 4. Create and Attach Policies
```bash
# Create S3 policy (use template from templates/iam-policies/s3-sync-policy.json)
aws iam create-policy --policy-name s3-sync-policy --policy-document file://templates/iam-policies/s3-sync-policy.json

# Create CloudWatch policy
aws iam create-policy --policy-name cloudwatch-policy --policy-document file://templates/iam-policies/cloudwatch-monitoring-policy.json

# Attach policies to user
aws iam attach-user-policy --user-name s3-sync-user --policy-arn arn:aws:iam::ACCOUNT:policy/s3-sync-policy
aws iam attach-user-policy --user-name s3-sync-user --policy-arn arn:aws:iam::ACCOUNT:policy/cloudwatch-policy
```

## Next Steps

After successful IAM user setup:

1. **Configure Sync Application**: Update your sync scripts to use the new credentials
2. **Test Sync Operations**: Run a test sync to verify everything works
3. **Set Up Monitoring**: Configure CloudWatch alarms and logging
4. **Implement Security**: Add encryption, versioning, and access logging

## Security Notes

⚠️ **Important Security Reminders**:
- Never share or commit access keys to version control
- Rotate access keys every 90 days
- Use IAM roles when possible instead of access keys
- Monitor CloudTrail logs for suspicious activity
- Enable MFA for additional security 