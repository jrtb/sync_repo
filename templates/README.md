# IAM Policy Templates

This directory contains IAM policy templates for the S3 sync tool.

## Policy Templates

### `iam-policies/s3-sync-policy.json`
Standard S3 sync permissions with full access to bucket operations.

**Use when:**
- You need full control over S3 bucket operations
- Setting up initial sync functionality
- Testing and development environments

**Permissions included:**
- Read/Write/Delete objects
- Bucket management (versioning, policies, lifecycle)
- Object versioning operations

### `iam-policies/s3-sync-restrictive-policy.json`
Restrictive S3 sync permissions with limited access and conditions.

**Use when:**
- Production environments
- Need to restrict access to specific prefixes
- Want to enforce tagging requirements
- Security-focused deployments

**Features:**
- Read-only access to bucket
- Write access only to `/sync/*` prefix
- Environment-based conditions
- Protection against deleting tagged objects

### `iam-policies/cloudwatch-monitoring-policy.json`
CloudWatch monitoring and logging permissions.

**Use when:**
- Setting up monitoring and alerting
- Need to track sync performance
- Want to log sync operations

**Permissions included:**
- CloudWatch metrics and alarms
- CloudWatch Logs access
- Custom namespace for S3 sync metrics

## Usage

### 1. Update Policy Templates
Replace `YOUR-BUCKET-NAME` with your actual S3 bucket name in the policy files.

### 2. Create IAM Policy
```bash
aws iam create-policy \
    --policy-name S3SyncPolicy \
    --policy-document file://templates/iam-policies/s3-sync-policy.json
```

### 3. Attach to User/Role
```bash
# For IAM User
aws iam attach-user-policy \
    --user-name your-username \
    --policy-arn arn:aws:iam::YOUR-ACCOUNT-ID:policy/S3SyncPolicy

# For IAM Role
aws iam attach-role-policy \
    --role-name your-role-name \
    --policy-arn arn:aws:iam::YOUR-ACCOUNT-ID:policy/S3SyncPolicy
```

## Security Best Practices

1. **Principle of Least Privilege**: Use the most restrictive policy that meets your needs
2. **Environment Separation**: Use different policies for dev/staging/production
3. **Regular Review**: Periodically review and update policies
4. **Conditional Access**: Use conditions to limit when policies apply
5. **Tagging**: Implement resource tagging for better management

## Policy Customization

### Adding Conditions
```json
"Condition": {
    "StringEquals": {
        "aws:RequestTag/Environment": "production"
    },
    "StringNotEquals": {
        "aws:RequestTag/Protected": "true"
    }
}
```

### Limiting to Specific Prefixes
```json
"Resource": [
    "arn:aws:s3:::your-bucket-name/sync/*"
]
```

### Time-based Restrictions
```json
"Condition": {
    "DateGreaterThan": {
        "aws:CurrentTime": "2023-01-01T00:00:00Z"
    },
    "DateLessThan": {
        "aws:CurrentTime": "2024-12-31T23:59:59Z"
    }
}
```

## Monitoring and Auditing

### Enable CloudTrail
```bash
aws cloudtrail create-trail \
    --name S3SyncTrail \
    --s3-bucket-name your-logs-bucket \
    --include-global-service-events
```

### Set up CloudWatch Alarms
```bash
aws cloudwatch put-metric-alarm \
    --alarm-name S3SyncErrors \
    --metric-name Errors \
    --namespace S3Sync \
    --statistic Sum \
    --period 300 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold
```

## Troubleshooting

### Common Issues

1. **Access Denied**: Check if policy is attached to correct user/role
2. **Insufficient Permissions**: Verify all required permissions are included
3. **Condition Failures**: Check if conditions match your use case
4. **Resource Mismatch**: Ensure bucket name is correct in policy

### Debug Commands
```bash
# Check user policies
aws iam list-attached-user-policies --user-name your-username

# Check role policies
aws iam list-attached-role-policies --role-name your-role-name

# Test policy with AWS Policy Simulator
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::YOUR-ACCOUNT-ID:user/your-username \
    --action-names s3:PutObject \
    --resource-arns arn:aws:s3:::your-bucket-name/test.txt
``` 