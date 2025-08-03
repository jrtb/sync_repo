# Storage Class Management Guide

## What This Does
The Storage Class Manager provides comprehensive S3 storage class management, including cost analysis, automatic transitions, lifecycle policies, and optimization recommendations. This tool helps you understand and implement AWS S3 storage class best practices for cost optimization.

## AWS Concepts Covered
- **S3 Storage Classes**: STANDARD, STANDARD_IA, ONEZONE_IA, INTELLIGENT_TIERING, GLACIER, DEEP_ARCHIVE
- **Lifecycle Policies**: Automatic transitions between storage classes based on age
- **Cost Optimization**: Storage class selection for different access patterns
- **CloudWatch Integration**: Monitoring storage usage and costs

## Quick Start

### Analyze Storage Costs
```bash
# Analyze current storage costs and get recommendations
python scripts/storage-class-manager.py --analyze-costs

# Analyze specific prefix (e.g., photos folder)
python scripts/storage-class-manager.py --analyze-costs --prefix photos/
```

### Optimize Storage Costs
```bash
# Dry run to see potential savings
python scripts/storage-class-manager.py --optimize-storage --dry-run

# Apply optimizations automatically
python scripts/storage-class-manager.py --optimize-storage
```

### Apply Lifecycle Policies
```bash
# Apply lifecycle policies from configuration
python scripts/storage-class-manager.py --apply-lifecycle-policy

# View storage class information
python scripts/storage-class-manager.py --storage-class-info STANDARD
```

## Storage Class Selection Guide

### STANDARD
- **Use for**: Frequently accessed data, active workloads
- **Cost**: $0.023/GB/month
- **Access**: Milliseconds
- **Availability**: 99.99%

### STANDARD_IA (Infrequent Access)
- **Use for**: Long-term backups, disaster recovery
- **Cost**: $0.0125/GB/month (46% savings)
- **Access**: Milliseconds
- **Availability**: 99.9%
- **Minimum Duration**: 30 days

### GLACIER
- **Use for**: Long-term archival, compliance storage
- **Cost**: $0.004/GB/month (83% savings)
- **Access**: 3-5 hours
- **Availability**: 99.9%
- **Minimum Duration**: 90 days

### DEEP_ARCHIVE
- **Use for**: Long-term archival, regulatory compliance
- **Cost**: $0.00099/GB/month (96% savings)
- **Access**: 12-48 hours
- **Availability**: 99.9%
- **Minimum Duration**: 180 days

### INTELLIGENT_TIERING
- **Use for**: Unknown or changing access patterns
- **Cost**: Automatic optimization
- **Access**: Milliseconds to hours
- **Availability**: 99.9%
- **Features**: Automatic transitions based on access patterns

## Advanced Operations

### Manual Object Transitions
```bash
# Transition objects older than 30 days from STANDARD to STANDARD_IA
python scripts/storage-class-manager.py --transition-objects \
  --source STANDARD --target STANDARD_IA --days 30

# Transition specific prefix
python scripts/storage-class-manager.py --transition-objects \
  --source STANDARD --target GLACIER --days 90 --prefix archive/
```

### Lifecycle Policy Management
```bash
# Create lifecycle policy for automatic transitions
python scripts/storage-class-manager.py --create-lifecycle-policy \
  --bucket your-bucket --transition-days 30,90,180

# View existing lifecycle policies
python scripts/storage-class-manager.py --list-lifecycle-policies --bucket your-bucket
```

## Cost Optimization Strategies

### 1. **Access Pattern Analysis**
- Monitor object access patterns
- Identify infrequently accessed data
- Use Intelligent Tiering for unknown patterns

### 2. **Lifecycle Policy Implementation**
- Transition to STANDARD_IA after 30 days
- Transition to GLACIER after 90 days
- Use DEEP_ARCHIVE for long-term storage

### 3. **Storage Class Selection**
- **Active Data**: STANDARD
- **Backup Data**: STANDARD_IA
- **Archive Data**: GLACIER
- **Compliance Data**: DEEP_ARCHIVE

## Monitoring and Reporting

### CloudWatch Integration
```bash
# View storage metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name BucketSizeBytes \
  --dimensions Name=BucketName,Value=your-bucket \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600 \
  --statistics Average
```

### Cost Analysis
```bash
# Generate cost report
python scripts/storage-class-manager.py --cost-report --bucket your-bucket

# Export cost data
python scripts/storage-class-manager.py --export-costs --format csv
```

## Best Practices

### 1. **Start with Intelligent Tiering**
- Use for unknown access patterns
- Automatically optimizes costs
- No minimum storage duration

### 2. **Implement Lifecycle Policies**
- Automate storage class transitions
- Reduce manual management overhead
- Ensure consistent cost optimization

### 3. **Monitor Access Patterns**
- Use CloudWatch metrics
- Analyze access logs
- Adjust policies based on usage

### 4. **Regular Optimization**
- Run cost analysis monthly
- Review and update lifecycle policies
- Monitor for cost anomalies

## Troubleshooting

### Common Issues

#### Access Denied Errors
```bash
# Check IAM permissions
python scripts/storage-class-manager.py --check-permissions

# Verify bucket access
aws s3 ls s3://your-bucket --profile s3-sync
```

#### Lifecycle Policy Errors
```bash
# Validate lifecycle policy
python scripts/storage-class-manager.py --validate-lifecycle-policy

# Check policy status
aws s3api get-bucket-lifecycle-configuration --bucket your-bucket
```

#### Cost Analysis Issues
```bash
# Check CloudWatch permissions
python scripts/storage-class-manager.py --check-cloudwatch-access

# Verify cost data availability
aws ce get-cost-and-usage --time-period Start=2024-01-01,End=2024-01-31
```

---

**Educational Focus**: This guide demonstrates S3 storage class optimization for AWS certification study and practical cost management.

**Production Ready**: Includes comprehensive monitoring, validation, and troubleshooting capabilities. 