#!/usr/bin/env python3
"""
S3 Bucket Policy Validator

Validates S3 bucket policies for security compliance and proper configuration.
This script helps ensure that bucket policies follow security best practices
for the photo sync tool.

AWS Concepts Covered:
- S3 bucket policies and security
- IAM policy validation
- Security best practices
- Encryption requirements
"""

import json
import boto3
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolicyValidator:
    """Validates S3 bucket policies for security compliance."""
    
    def __init__(self, aws_profile: Optional[str] = None):
        """Initialize the policy validator.
        
        Args:
            aws_profile: AWS profile to use for validation
        """
        self.session = boto3.Session(profile_name=aws_profile)
        self.s3_client = self.session.client('s3')
        self.iam_client = self.session.client('iam')
        
    def validate_policy_structure(self, policy: Dict[str, Any]) -> List[str]:
        """Validate basic policy structure and syntax.
        
        Args:
            policy: The bucket policy to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check required fields
        if 'Version' not in policy:
            errors.append("Policy missing 'Version' field")
        elif policy['Version'] != '2012-10-17':
            errors.append("Policy version must be '2012-10-17'")
            
        if 'Statement' not in policy:
            errors.append("Policy missing 'Statement' field")
        elif not isinstance(policy['Statement'], list):
            errors.append("Policy 'Statement' must be a list")
            return errors
            
        # Validate each statement
        statements = policy.get('Statement', [])
            
        for i, statement in enumerate(statements):
            if not isinstance(statement, dict):
                errors.append(f"Statement {i}: must be a dictionary")
                continue
            statement_errors = self._validate_statement(statement, i)
            errors.extend(statement_errors)
            
        return errors
    
    def _validate_statement(self, statement: Dict[str, Any], index: int) -> List[str]:
        """Validate individual policy statement.
        
        Args:
            statement: The policy statement to validate
            index: Index of the statement for error reporting
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check required fields
        required_fields = ['Effect', 'Action', 'Resource']
        for field in required_fields:
            if field not in statement:
                errors.append(f"Statement {index}: missing required field '{field}'")
                
        # Validate Effect
        if 'Effect' in statement and statement['Effect'] not in ['Allow', 'Deny']:
            errors.append(f"Statement {index}: Effect must be 'Allow' or 'Deny'")
            
        # Validate Action
        if 'Action' in statement:
            if isinstance(statement['Action'], str):
                statement['Action'] = [statement['Action']]
            elif not isinstance(statement['Action'], list):
                errors.append(f"Statement {index}: Action must be string or list")
                
        # Validate Resource
        if 'Resource' in statement:
            if isinstance(statement['Resource'], str):
                statement['Resource'] = [statement['Resource']]
            elif not isinstance(statement['Resource'], list):
                errors.append(f"Statement {index}: Resource must be string or list")
                
        return errors
    
    def validate_security_requirements(self, policy: Dict[str, Any]) -> List[str]:
        """Validate security requirements for the sync tool.
        
        Args:
            policy: The bucket policy to validate
            
        Returns:
            List of security validation errors
        """
        errors = []
        statements = policy.get('Statement', [])
        
        # Check for encryption enforcement
        has_encryption_enforcement = False
        for statement in statements:
            if (statement.get('Effect') == 'Deny' and 
                's3:PutObject' in statement.get('Action', []) and
                'Condition' in statement and
                's3:x-amz-server-side-encryption' in str(statement['Condition'])):
                has_encryption_enforcement = True
                break
                
        if not has_encryption_enforcement:
            errors.append("Policy should enforce server-side encryption for uploads")
            
        # Check for TLS enforcement
        has_tls_enforcement = False
        for statement in statements:
            if (statement.get('Effect') == 'Deny' and
                'aws:SecureTransport' in str(statement.get('Condition', {}))):
                has_tls_enforcement = True
                break
                
        if not has_tls_enforcement:
            errors.append("Policy should enforce TLS/HTTPS for all requests")
            
        # Check for public access prevention
        has_public_access_prevention = False
        for statement in statements:
            if (statement.get('Effect') == 'Deny' and
                'aws:PrincipalIsAnonymous' in str(statement.get('Condition', {}))):
                has_public_access_prevention = True
                break
                
        if not has_public_access_prevention:
            errors.append("Policy should prevent anonymous/public access")
            
        return errors
    
    def validate_sync_tool_access(self, policy: Dict[str, Any]) -> List[str]:
        """Validate that the policy allows proper sync tool access.
        
        Args:
            policy: The bucket policy to validate
            
        Returns:
            List of access validation errors
        """
        errors = []
        statements = policy.get('Statement', [])
        
        # Check for sync tool access permissions
        required_actions = [
            's3:GetObject',
            's3:PutObject', 
            's3:ListBucket',
            's3:GetBucketLocation'
        ]
        
        allowed_actions = set()
        for statement in statements:
            if statement.get('Effect') == 'Allow':
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                allowed_actions.update(actions)
                
        missing_actions = set(required_actions) - allowed_actions
        if missing_actions:
            errors.append(f"Policy missing required sync tool permissions: {missing_actions}")
            
        return errors
    
    def validate_policy_file(self, policy_file: Path) -> Dict[str, Any]:
        """Validate a policy file and return results.
        
        Args:
            policy_file: Path to the policy file to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            with open(policy_file, 'r') as f:
                policy = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            return {
                'valid': False,
                'errors': [f"Failed to load policy file: {e}"]
            }
            
        # Perform all validations
        structure_errors = self.validate_policy_structure(policy)
        security_errors = self.validate_security_requirements(policy)
        access_errors = self.validate_sync_tool_access(policy)
        
        all_errors = structure_errors + security_errors + access_errors
        
        return {
            'valid': len(structure_errors) == 0,  # Only structure errors make it invalid
            'errors': all_errors,
            'policy': policy
        }
    
    def validate_bucket_policy(self, bucket_name: str) -> Dict[str, Any]:
        """Validate the actual policy applied to an S3 bucket.
        
        Args:
            bucket_name: Name of the S3 bucket to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            response = self.s3_client.get_bucket_policy(Bucket=bucket_name)
            policy = json.loads(response['Policy'])
            
            # Perform validations
            structure_errors = self.validate_policy_structure(policy)
            security_errors = self.validate_security_requirements(policy)
            access_errors = self.validate_sync_tool_access(policy)
            
            all_errors = structure_errors + security_errors + access_errors
            
            return {
                'valid': len(all_errors) == 0,
                'errors': all_errors,
                'policy': policy
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                return {
                    'valid': False,
                    'errors': ['No bucket policy found']
                }
            else:
                return {
                    'valid': False,
                    'errors': [f"AWS error: {e}"]
                }
        except NoCredentialsError:
            return {
                'valid': False,
                'errors': ['AWS credentials not found']
            }
    
    def apply_policy_template(self, bucket_name: str, template_file: Path, 
                            replacements: Dict[str, str]) -> bool:
        """Apply a policy template to a bucket.
        
        Args:
            bucket_name: Name of the S3 bucket
            template_file: Path to the policy template file
            replacements: Dictionary of placeholder replacements
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load and process template
            with open(template_file, 'r') as f:
                template_content = f.read()
                
            # Apply replacements
            for placeholder, value in replacements.items():
                template_content = template_content.replace(placeholder, value)
                
            # Parse the processed template
            policy = json.loads(template_content)
            
            # Validate the processed policy
            validation_result = self.validate_policy_structure(policy)
            if validation_result:
                logger.error(f"Template validation failed: {validation_result}")
                return False
                
            # Apply the policy
            self.s3_client.put_bucket_policy(
                Bucket=bucket_name,
                Policy=json.dumps(policy)
            )
            
            logger.info(f"Successfully applied policy to bucket {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply policy: {e}")
            return False


def main():
    """Main function for policy validation."""
    parser = argparse.ArgumentParser(description='Validate S3 bucket policies')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--bucket', help='S3 bucket name to validate')
    parser.add_argument('--template', type=Path, help='Policy template file to validate')
    parser.add_argument('--apply', type=Path, help='Apply template to bucket')
    parser.add_argument('--replacements', nargs='*', 
                       help='Key=value pairs for template replacements')
    
    args = parser.parse_args()
    
    validator = PolicyValidator(aws_profile=args.profile)
    
    if args.template:
        # Validate template file
        result = validator.validate_policy_file(args.template)
        if result['valid']:
            print(f"✅ Template {args.template} is valid")
        else:
            print(f"❌ Template {args.template} has errors:")
            for error in result['errors']:
                print(f"  - {error}")
            sys.exit(1)
            
    elif args.bucket:
        # Validate bucket policy
        result = validator.validate_bucket_policy(args.bucket)
        if result['valid']:
            print(f"✅ Bucket {args.bucket} policy is valid")
        else:
            print(f"❌ Bucket {args.bucket} policy has errors:")
            for error in result['errors']:
                print(f"  - {error}")
            sys.exit(1)
            
    elif args.apply:
        # Apply template to bucket
        if not args.bucket:
            print("Error: --bucket required when using --apply")
            sys.exit(1)
            
        # Parse replacements
        replacements = {}
        if args.replacements:
            for replacement in args.replacements:
                if '=' in replacement:
                    key, value = replacement.split('=', 1)
                    replacements[key] = value
                    
        success = validator.apply_policy_template(args.bucket, args.apply, replacements)
        if success:
            print(f"✅ Successfully applied policy to {args.bucket}")
        else:
            print(f"❌ Failed to apply policy to {args.bucket}")
            sys.exit(1)
    else:
        print("Error: Must specify --template, --bucket, or --apply")
        sys.exit(1)


if __name__ == '__main__':
    main() 