# Setup Guide: AWS S3 Sync System

This guide explains how to set up the AWS S3 Sync system with your own credentials and infrastructure.

## 🔐 Credential Management Overview

The system uses a **multi-layered credential approach** for security:

1. **AWS CLI Profile** (`~/.aws/credentials`) - Primary authentication
2. **Project Credentials** (`config/aws-credentials.json`) - Script authentication
3. **Project Configuration** (`config/aws-config.json`) - Infrastructure details

## 🚀 Quick Setup (Recommended)

### Step 1: Prerequisites
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure admin credentials
aws configure
```

### Step 2: Automated Setup
```bash
# Run the setup script (creates everything automatically)
python scripts/setup-iam-user.py --bucket-name my-sync-bucket

# This creates:
# ✅ IAM user: s3-sync-user
# ✅ Access key: AKIA...
# ✅ S3 bucket: my-sync-bucket
# ✅ AWS CLI profile: s3-sync
# ✅ Project credentials: config/aws-credentials.json
# ✅ Project config: config/aws-config.json
```

### Step 3: Test Setup
```bash
# Test AWS CLI profile
aws s3 ls s3://my-sync-bucket --profile s3-sync

# Test sync script
python scripts/sync.py --profile s3-sync
```

## 🔧 Manual Setup (Advanced)

If you prefer manual setup or need custom configuration:

### Step 1: Create IAM User
```bash
# Create IAM user
aws iam create-user --user-name s3-sync-user

# Create access key
aws iam create-access-key --user-name s3-sync-user
```

### Step 2: Create S3 Bucket
```bash
# Create bucket (must be globally unique)
aws s3api create-bucket --bucket my-sync-bucket --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning --bucket my-sync-bucket --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption --bucket my-sync-bucket --server-side-encryption-configuration '{
  "Rules": [{
    "ApplyServerSideEncryptionByDefault": {
      "SSEAlgorithm": "AES256"
    }
  }]
}'
```

### Step 3: Configure AWS CLI Profile
```bash
# Configure the s3-sync profile
aws configure --profile s3-sync

# Enter your credentials when prompted:
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region name: us-east-1
# Default output format: json
```

### Step 4: Create Project Files

**Create `config/aws-credentials.json`:**
```json
{
  "aws_access_key_id": "YOUR_ACCESS_KEY_ID",
  "aws_secret_access_key": "YOUR_SECRET_ACCESS_KEY",
  "region": "us-east-1",
  "username": "s3-sync-user",
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

**Update `config/aws-config.json`:**
```json
{
  "aws": {
    "region": "us-east-1",
    "profile": "s3-sync",
    "credentials_file": "config/aws-credentials.json"
  },
  "s3": {
    "bucket_name": "YOUR-BUCKET-NAME",
    "sync_path": "/",
    "storage_class": "STANDARD"
  }
}
```

## 🔄 Credential Injection Flow

### How the System Uses Credentials

1. **Scripts use AWS Profile**:
   ```python
   session = boto3.Session(profile_name='s3-sync')
   s3_client = session.client('s3')
   ```

2. **Profile reads from `~/.aws/credentials`**:
   ```ini
   [s3-sync]
   aws_access_key_id = AKIA...
   aws_secret_access_key = ...
   region = us-east-1
   ```

3. **Project config provides bucket name**:
   ```python
   bucket_name = config.get('s3', {}).get('bucket_name')
   ```

### Security Benefits

- ✅ **Credentials never in code** - Stored in AWS CLI profile
- ✅ **Project files ignored** - `config/aws-credentials.json` in `.gitignore`
- ✅ **Template files safe** - No real credentials in repository
- ✅ **Standard AWS practice** - Uses AWS CLI profile system

## 🛡️ Security Best Practices

### Credential Security
- ✅ Use AWS CLI profiles (not hardcoded credentials)
- ✅ Set restrictive file permissions: `chmod 600 config/aws-credentials.json`
- ✅ Never commit credentials to version control
- ✅ Rotate access keys regularly

### IAM Security
- ✅ Use least-privilege permissions
- ✅ Bucket-specific access (not global S3 access)
- ✅ Enable CloudWatch monitoring
- ✅ Use MFA for admin accounts

### S3 Security
- ✅ Enable server-side encryption
- ✅ Enable bucket versioning
- ✅ Configure lifecycle policies
- ✅ Enable access logging

## 🔍 Troubleshooting

### Common Issues

**"AWS credentials not found"**
```bash
# Check if profile exists
aws configure list --profile s3-sync

# Reconfigure if needed
aws configure --profile s3-sync
```

**"Access Denied"**
```bash
# Test credentials
aws sts get-caller-identity --profile s3-sync

# Check IAM permissions
aws iam get-user --profile s3-sync
```

**"Bucket not found"**
```bash
# List buckets
aws s3 ls --profile s3-sync

# Check bucket name in config
cat config/aws-config.json | grep bucket_name
```

### File Locations

- **AWS CLI Profile**: `~/.aws/credentials`
- **Project Credentials**: `config/aws-credentials.json`
- **Project Config**: `config/aws-config.json`
- **Template Files**: `config/*-template.json`

## 📋 Setup Checklist

- [ ] AWS CLI installed and configured
- [ ] IAM user created with appropriate permissions
- [ ] S3 bucket created with encryption and versioning
- [ ] AWS CLI profile configured (`s3-sync`)
- [ ] Project credentials file created
- [ ] Project configuration updated with bucket name
- [ ] Test sync operation successful
- [ ] CloudWatch monitoring enabled
- [ ] Security policies applied

## 🎯 Next Steps

After setup, you can:

1. **Run your first sync**: `python scripts/sync.py`
2. **Monitor costs**: `python scripts/storage-class-manager.py`
3. **Generate reports**: `python scripts/report.py`
4. **Validate security**: `python scripts/verify-production-setup.py`

For more information, see the [Usage Guide](usage-guide.md) and [Security Guide](security.md). 