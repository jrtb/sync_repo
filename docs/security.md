# Security Guide

## What This Does
This guide covers comprehensive S3 bucket security implementation, including encryption, access policies, versioning, and monitoring. These security features protect your data and ensure compliance with AWS best practices.

## AWS Concepts Covered
- **S3 Encryption**: Server-side encryption at rest and in transit
- **IAM Policies**: Fine-grained access control and permissions
- **S3 Bucket Policies**: Resource-level security policies
- **S3 Versioning**: Data protection and recovery capabilities
- **Access Logging**: Security monitoring and audit trails
- **Public Access Block**: Prevention of accidental public exposure

## Quick Start

### Enable Basic Security
```bash
# Apply comprehensive security features
python scripts/security_manager.py --bucket your-bucket-name --action comprehensive

# This enables:
# - Server-side encryption (AES256)
# - TLS/HTTPS enforcement
# - Bucket versioning
# - Public access blocking
# - Access logging
```

### Validate Security Settings
```bash
# Check current security configuration
python scripts/security_manager.py --bucket your-bucket-name --action validate

# Verify IAM policies
python scripts/policy_validator.py --validate-policies
```

## Security Features

### 1. Encryption at Rest
**Why it matters**: Protects data when stored on AWS infrastructure.

```bash
# Enable AES256 encryption
python scripts/security_manager.py --bucket your-bucket-name --action encrypt

# Enable KMS encryption (requires KMS key)
python scripts/security_manager.py --bucket your-bucket-name --action encrypt --encryption-type arn:aws:kms:region:account:key/key-id
```

**AWS Service**: S3 Server-Side Encryption (SSE)
- **AES256**: AWS-managed encryption key
- **AWS KMS**: Customer-managed encryption keys with additional control

### 2. Encryption in Transit
**Why it matters**: Ensures data is encrypted during transmission.

```bash
# Enforce TLS/HTTPS for all requests
python scripts/security_manager.py --bucket your-bucket-name --action tls
```

**AWS Service**: S3 Bucket Policy with TLS enforcement
- Denies all requests not using HTTPS
- Automatically applied to bucket policy

### 3. Bucket Versioning
**Why it matters**: Protects against accidental deletion and enables data recovery.

```bash
# Enable basic versioning
python scripts/security_manager.py --bucket your-bucket-name --action version

# Enable versioning with MFA delete protection
python scripts/security_manager.py --bucket your-bucket-name --action version --mfa-serial arn:aws:iam::account:mfa/user
```

**AWS Service**: S3 Versioning
- **Basic Versioning**: Keeps multiple versions of objects
- **MFA Delete**: Requires MFA token for permanent deletion

### 4. Access Logging
**Why it matters**: Provides audit trail for security monitoring and compliance.

```bash
# Enable access logging
python scripts/security_manager.py --bucket your-bucket-name --action logging --log-bucket log-bucket-name
```

**AWS Service**: S3 Access Logging
- Logs all bucket access requests
- Stored in separate S3 bucket for security

### 5. Public Access Block
**Why it matters**: Prevents accidental public exposure of bucket contents.

```bash
# Configure public access block
python scripts/security_manager.py --bucket your-bucket-name --action public-block
```

**AWS Service**: S3 Public Access Block
- Blocks public ACLs and policies
- Prevents accidental public access

## IAM Security

### Policy Validation
```bash
# Validate IAM policies
python scripts/policy_validator.py --validate-policies

# Check policy permissions
python scripts/policy_validator.py --check-permissions --user s3-sync-user

# Audit access patterns
python scripts/security_manager.py --audit-access
```

### Credential Management
```bash
# Regenerate access keys
python scripts/regenerate-credentials.py

# This:
# - Creates new access keys
# - Deactivates old keys
# - Updates credential files
# - Maintains security best practices
```

## Bucket Policy Templates

### Standard Secure Policy
Provides balanced security with encryption, TLS enforcement, and sync tool access.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EnforceTLS",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::your-bucket/*",
      "Condition": {
        "StringNotEquals": {
          "aws:SecureTransport": "true"
        }
      }
    },
    {
      "Sid": "SyncToolAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::account:user/s3-sync-user"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    }
  ]
}
```

### Restrictive Access Policy
Maximum security with minimal access for sensitive data.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EnforceTLS",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::your-bucket/*",
      "Condition": {
        "StringNotEquals": {
          "aws:SecureTransport": "true"
        }
      }
    },
    {
      "Sid": "SyncToolAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::account:user/s3-sync-user"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

## Security Monitoring

### Access Log Analysis
```bash
# Analyze access logs
python scripts/security_manager.py --analyze-logs --log-bucket log-bucket-name

# Check for suspicious activity
python scripts/security_manager.py --audit-access --bucket your-bucket-name
```

### CloudWatch Integration
```bash
# View security metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name NumberOfRequests \
  --dimensions Name=BucketName,Value=your-bucket \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

## Best Practices

### 1. **Principle of Least Privilege**
- Grant only necessary permissions
- Use IAM roles when possible
- Regularly review and audit permissions

### 2. **Encryption Everywhere**
- Enable server-side encryption
- Enforce HTTPS for all requests
- Use KMS for additional key management

### 3. **Monitoring and Logging**
- Enable access logging
- Monitor CloudWatch metrics
- Set up alerts for suspicious activity

### 4. **Regular Security Reviews**
- Audit access patterns monthly
- Review IAM policies quarterly
- Test security controls regularly

### 5. **Incident Response**
- Document security procedures
- Have rollback plans ready
- Test recovery procedures

## Troubleshooting

### Common Security Issues

#### Access Denied Errors
```bash
# Check IAM permissions
python scripts/test-credentials.py

# Verify bucket policies
python scripts/policy_validator.py --validate-policies

# Test specific permissions
python scripts/security_manager.py --test-permissions --bucket your-bucket
```

#### Encryption Errors
```bash
# Check encryption settings
python scripts/security_manager.py --check-encryption --bucket your-bucket

# Verify KMS key permissions
aws kms describe-key --key-id your-key-id
```

#### Versioning Issues
```bash
# Check versioning status
python scripts/security_manager.py --check-versioning --bucket your-bucket

# List object versions
aws s3api list-object-versions --bucket your-bucket --prefix your-prefix
```

---

**Educational Focus**: This guide demonstrates AWS security best practices for S3 and IAM for certification study and production implementation.

**Production Ready**: Includes comprehensive security validation, monitoring, and incident response capabilities. 