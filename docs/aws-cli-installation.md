# AWS CLI Installation Guide

## What This Does
Installs AWS CLI for programmatic access to AWS services. Essential for AWS certification and automation.

## AWS Concepts Covered
- **AWS CLI**: Command-line interface for AWS services
- **Programmatic Access**: Using APIs instead of console
- **Credentials**: Authentication for AWS services
- **Regions**: Geographic locations for AWS resources

## Prerequisites
- Administrative privileges on your system
- Internet connection for downloading
- At least 50MB of free disk space

## Installation by Operating System

### macOS Installation

#### Option 1: Using Homebrew (Recommended)
```bash
brew install awscli  # Install AWS CLI
aws --version        # Verify installation
```

#### Option 2: Using the Official Installer
```bash
# Download and install
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
rm AWSCLIV2.pkg  # Clean up

# Verify installation
aws --version
```

### Linux Installation

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install awscli
aws --version
```

#### CentOS/RHEL/Fedora
```bash
# CentOS/RHEL 7 and earlier
sudo yum install awscli

# CentOS/RHEL 8+ and Fedora
sudo dnf install awscli

aws --version
```

#### Manual Installation (All Linux)
```bash
# Download and install
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip  # Clean up

aws --version
```

### Windows Installation

#### Option 1: Using the MSI Installer (Recommended)
1. Download from: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Double-click to run installer
3. Follow installation wizard
4. Open Command Prompt and verify:
   ```cmd
   aws --version
   ```

#### Option 2: Using Chocolatey
```cmd
choco install awscli
aws --version
```

## Post-Installation Setup

### 1. Verify Installation
```bash
aws --version
```

Expected output:
```
aws-cli/2.x.x Python/3.x.x Darwin/xx.x.x source/2.x.x botocore/2.x.x
```

### 2. Configure AWS Credentials

#### Method 1: Interactive Configuration (Recommended)
```bash
aws configure  # Sets up credentials and default region
```

**What this does**: Creates `~/.aws/credentials` and `~/.aws/config` files.

#### Method 2: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_DEFAULT_REGION=us-east-1
```

#### Method 3: Credentials File
Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your_access_key_id
aws_secret_access_key = your_secret_access_key
```

Create `~/.aws/config`:
```ini
[default]
region = us-east-1
output = json
```

### 3. Test Your Configuration
```bash
aws sts get-caller-identity  # Shows your AWS account info
aws s3 ls                    # List S3 buckets (if any)
```

## Troubleshooting

### Common Issues

#### "aws: command not found"
**Solution**:
1. Check if AWS CLI is in your PATH
2. Restart your terminal/command prompt
3. For manual installations, ensure binary is in PATH directory

#### Permission Denied
**Solution**:
1. Use `sudo` for installation on Linux/macOS
2. Run Command Prompt as Administrator on Windows
3. Check file permissions

#### Python Version Conflicts
**Solution**:
1. Use official installer instead of pip
2. Ensure Python 3.7+ is installed
3. Consider using virtual environment

### Verification Commands
```bash
aws --version                   # Check CLI version
aws configure list              # Show configuration
aws sts get-caller-identity    # Test AWS connectivity
```

## Updating AWS CLI

### macOS (Homebrew)
```bash
brew upgrade awscli
```

### Linux (Package Manager)
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get upgrade awscli

# CentOS/RHEL
sudo yum update awscli
```

### Manual Update
```bash
# Download and install latest version
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install --update
rm -rf aws awscliv2.zip
```

## Uninstalling AWS CLI

### macOS (Homebrew)
```bash
brew uninstall awscli
```

### Linux (Package Manager)
```bash
# Ubuntu/Debian
sudo apt-get remove awscli

# CentOS/RHEL
sudo yum remove awscli
```

### Manual Uninstall
```bash
# Remove AWS CLI files
sudo rm -rf /usr/local/aws
sudo rm /usr/local/bin/aws
sudo rm /usr/local/bin/aws_completer
```

## Next Steps

After successful installation:
1. Configure your AWS credentials
2. Set up your preferred region
3. Test your configuration
4. Refer to the main AWS setup guide for S3 configuration
5. Set up IAM permissions as needed

## Security Notes

⚠️ **Important Security Reminders**:
- Never share or commit access keys to version control
- Use IAM roles when possible instead of access keys
- Rotate access keys regularly
- Enable MFA for additional security 