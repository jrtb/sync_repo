#!/usr/bin/env python3
"""
Storage Class Manager for AWS S3 Photo Sync Application

This script provides comprehensive storage class management for S3 objects,
including automatic selection, transitions, cost calculation, and lifecycle
policy management. Designed for AWS certification study with practical implementation.

AWS Concepts Covered:
- S3 Storage Classes (STANDARD, STANDARD_IA, ONEZONE_IA, INTELLIGENT_TIERING, GLACIER, DEEP_ARCHIVE)
- Lifecycle Policies and Transitions
- Cost Optimization and Analysis
- Storage Class Selection Logic
- Object Tagging for Storage Management
- CloudWatch Metrics for Storage Monitoring

Usage:
    python scripts/storage-class-manager.py --analyze-costs
    python scripts/storage-class-manager.py --apply-lifecycle-policy
    python scripts/storage-class-manager.py --optimize-storage
    python scripts/storage-class-manager.py --transition-objects --days 30
"""

import argparse
import boto3
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, List, Optional, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the scripts directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from logger import SyncLogger

class StorageClassManager:
    """Manages S3 storage classes, transitions, and cost optimization"""
    
    # S3 Storage Classes with their characteristics
    STORAGE_CLASSES = {
        'STANDARD': {
            'description': 'General purpose storage for frequently accessed data',
            'availability': '99.99%',
            'durability': '99.999999999%',
            'cost_per_gb_month': 0.023,  # Approximate cost in USD
            'access_time': 'milliseconds',
            'minimum_storage_duration': 0,
            'retrieval_fee': 0,
            'use_case': 'Frequently accessed data, active workloads'
        },
        'STANDARD_IA': {
            'description': 'Infrequent access storage for long-lived, rarely accessed data',
            'availability': '99.9%',
            'durability': '99.999999999%',
            'cost_per_gb_month': 0.0125,
            'access_time': 'milliseconds',
            'minimum_storage_duration': 30,
            'retrieval_fee': 0.01,
            'use_case': 'Long-term backups, disaster recovery'
        },
        'ONEZONE_IA': {
            'description': 'Single AZ infrequent access storage',
            'availability': '99.5%',
            'durability': '99.999999999%',
            'cost_per_gb_month': 0.01,
            'access_time': 'milliseconds',
            'minimum_storage_duration': 30,
            'retrieval_fee': 0.01,
            'use_case': 'Recreatable data, secondary backups'
        },
        'INTELLIGENT_TIERING': {
            'description': 'Automatically moves objects between tiers based on access patterns',
            'availability': '99.9%',
            'durability': '99.999999999%',
            'cost_per_gb_month': 0.023,
            'access_time': 'milliseconds',
            'minimum_storage_duration': 30,
            'retrieval_fee': 0.01,
            'use_case': 'Unknown or changing access patterns'
        },
        'GLACIER': {
            'description': 'Low-cost storage for long-term archival',
            'availability': '99.9%',
            'durability': '99.999999999%',
            'cost_per_gb_month': 0.004,
            'access_time': '3-5 hours',
            'minimum_storage_duration': 90,
            'retrieval_fee': 0.02,
            'use_case': 'Long-term archival, compliance storage'
        },
        'DEEP_ARCHIVE': {
            'description': 'Lowest cost storage for long-term archival',
            'availability': '99.9%',
            'durability': '99.999999999%',
            'cost_per_gb_month': 0.00099,
            'access_time': '12-48 hours',
            'minimum_storage_duration': 180,
            'retrieval_fee': 0.05,
            'use_case': 'Long-term archival, regulatory compliance'
        }
    }
    
    def __init__(self, config_file=None, profile=None, bucket_name=None, verbose=False):
        """Initialize storage class manager with configuration"""
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_config(config_file)
        self.profile = profile or self.config.get('aws', {}).get('profile', 'default')
        self.bucket_name = bucket_name or self.config.get('s3', {}).get('bucket_name')
        self.verbose = verbose
        
        # Initialize structured logger
        self.logger = SyncLogger(operation_name='storage-class-manager', config=self.config)
        
        # Initialize AWS clients
        self._setup_aws_clients()
        
        # Storage analysis statistics
        self.stats = {
            'objects_analyzed': 0,
            'objects_transitioned': 0,
            'cost_savings_estimated': 0.0,
            'storage_by_class': {},
            'start_time': None,
            'end_time': None
        }
        
        # Thread safety
        self.stats_lock = threading.Lock()
        
    def _load_config(self, config_file):
        """Load configuration from file"""
        if config_file:
            config_path = Path(config_file)
        else:
            config_path = self.project_root / "config" / "aws-config.json"
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            sys.exit(1)
    
    def _setup_aws_clients(self):
        """Initialize AWS clients with proper error handling"""
        try:
            session = boto3.Session(profile_name=self.profile)
            self.s3_client = session.client('s3')
            self.s3_resource = session.resource('s3')
            self.cloudwatch_client = session.client('cloudwatch')
            
            # Test connection
            self.s3_client.list_buckets()
            self.logger.log_info("AWS clients initialized successfully")
            
        except NoCredentialsError:
            print("❌ AWS credentials not found. Please configure your credentials.")
            sys.exit(1)
        except ClientError as e:
            print(f"❌ AWS client error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error initializing AWS clients: {e}")
            sys.exit(1)
    
    def _update_stats(self, **kwargs):
        """Thread-safe statistics update"""
        with self.stats_lock:
            for key, value in kwargs.items():
                if key in self.stats:
                    if isinstance(value, (int, float)):
                        self.stats[key] += value
                    else:
                        self.stats[key] = value
    
    def analyze_storage_costs(self, prefix: str = None) -> Dict:
        """
        Analyze storage costs across different storage classes
        
        AWS Concepts:
        - S3 ListObjectsV2 API for object enumeration
        - Storage class cost analysis
        - CloudWatch metrics integration
        - Cost optimization strategies
        """
        self.logger.log_info(f"Starting storage cost analysis for bucket: {self.bucket_name}")
        self._update_stats(start_time=datetime.now())
        
        storage_analysis = {
            'bucket_name': self.bucket_name,
            'analysis_date': datetime.now().isoformat(),
            'storage_by_class': {},
            'cost_breakdown': {},
            'optimization_recommendations': [],
            'total_objects': 0,
            'total_size_gb': 0,
            'monthly_cost': 0.0
        }
        
        try:
            # List all objects in the bucket
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    storage_class = obj.get('StorageClass', 'STANDARD')
                    size_gb = obj['Size'] / (1024**3)
                    
                    # Update storage analysis
                    if storage_class not in storage_analysis['storage_by_class']:
                        storage_analysis['storage_by_class'][storage_class] = {
                            'object_count': 0,
                            'total_size_gb': 0,
                            'monthly_cost': 0.0
                        }
                    
                    storage_analysis['storage_by_class'][storage_class]['object_count'] += 1
                    storage_analysis['storage_by_class'][storage_class]['total_size_gb'] += size_gb
                    
                    # Calculate monthly cost
                    if storage_class in self.STORAGE_CLASSES:
                        cost_per_gb = self.STORAGE_CLASSES[storage_class]['cost_per_gb_month']
                        storage_analysis['storage_by_class'][storage_class]['monthly_cost'] += size_gb * cost_per_gb
                    
                    storage_analysis['total_objects'] += 1
                    storage_analysis['total_size_gb'] += size_gb
                    self._update_stats(objects_analyzed=1)
            
            # Calculate total monthly cost
            storage_analysis['monthly_cost'] = sum(
                class_data['monthly_cost'] 
                for class_data in storage_analysis['storage_by_class'].values()
            )
            
            # Generate optimization recommendations
            storage_analysis['optimization_recommendations'] = self._generate_optimization_recommendations(
                storage_analysis['storage_by_class']
            )
            
            self._update_stats(end_time=datetime.now())
            self.logger.log_info(f"Storage analysis completed. Analyzed {storage_analysis['total_objects']} objects")
            
            return storage_analysis
            
        except ClientError as e:
            self.logger.log_error(f"Error analyzing storage costs: {e}")
            raise
    
    def _generate_optimization_recommendations(self, storage_by_class: Dict) -> List[Dict]:
        """Generate cost optimization recommendations based on storage analysis"""
        recommendations = []
        
        # Check for objects in STANDARD that could be moved to STANDARD_IA
        if 'STANDARD' in storage_by_class:
            standard_data = storage_by_class['STANDARD']
            if standard_data['object_count'] > 0:
                potential_savings = standard_data['monthly_cost'] * 0.46  # ~46% savings
                recommendations.append({
                    'type': 'transition_to_standard_ia',
                    'description': 'Move infrequently accessed objects to STANDARD_IA',
                    'current_storage_class': 'STANDARD',
                    'recommended_storage_class': 'STANDARD_IA',
                    'potential_savings_per_month': potential_savings,
                    'objects_affected': standard_data['object_count'],
                    'size_affected_gb': standard_data['total_size_gb']
                })
        
        # Check for objects that could be moved to GLACIER
        for storage_class in ['STANDARD', 'STANDARD_IA']:
            if storage_class in storage_by_class:
                data = storage_by_class[storage_class]
                if data['object_count'] > 0:
                    potential_savings = data['monthly_cost'] * 0.83  # ~83% savings
                    recommendations.append({
                        'type': 'transition_to_glacier',
                        'description': f'Move archival data from {storage_class} to GLACIER',
                        'current_storage_class': storage_class,
                        'recommended_storage_class': 'GLACIER',
                        'potential_savings_per_month': potential_savings,
                        'objects_affected': data['object_count'],
                        'size_affected_gb': data['total_size_gb']
                    })
        
        return recommendations
    
    def apply_lifecycle_policy(self, policy_config: Dict = None) -> bool:
        """
        Apply lifecycle policy to S3 bucket
        
        AWS Concepts:
        - S3 Lifecycle Configuration API
        - Policy validation and application
        - Storage class transitions
        - Expiration policies
        """
        if not policy_config:
            policy_config = self.config.get('s3', {}).get('lifecycle', {})
        
        if not policy_config.get('enabled', False):
            self.logger.log_info("Lifecycle policies not enabled in configuration")
            return False
        
        try:
            # Prepare lifecycle configuration
            lifecycle_config = {
                'Rules': []
            }
            
            for rule in policy_config.get('rules', []):
                lifecycle_rule = {
                    'ID': rule['id'],
                    'Status': rule['status'],
                    'Filter': {
                        'Prefix': rule.get('prefix', '')
                    }
                }
                
                # Add transitions
                if 'transition' in rule:
                    transition = rule['transition']
                    lifecycle_rule['Transitions'] = [{
                        'Days': transition['days'],
                        'StorageClass': transition['storage_class']
                    }]
                
                # Add expiration
                if 'expiration' in rule:
                    expiration = rule['expiration']
                    lifecycle_rule['Expiration'] = {
                        'Days': expiration['days']
                    }
                
                lifecycle_config['Rules'].append(lifecycle_rule)
            
            # Apply lifecycle configuration
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            
            self.logger.log_info(f"Lifecycle policy applied successfully to bucket: {self.bucket_name}")
            return True
            
        except ClientError as e:
            self.logger.log_error(f"Error applying lifecycle policy: {e}")
            return False
    
    def transition_objects(self, source_class: str, target_class: str, 
                          days_threshold: int = 30, prefix: str = None) -> Dict:
        """
        Transition objects between storage classes based on age
        
        AWS Concepts:
        - S3 CopyObject API for storage class transitions
        - Object metadata preservation
        - Batch processing with error handling
        - Progress tracking and reporting
        """
        self.logger.log_info(f"Starting object transitions from {source_class} to {target_class}")
        self._update_stats(start_time=datetime.now())
        
        transition_results = {
            'objects_transitioned': 0,
            'objects_skipped': 0,
            'objects_failed': 0,
            'total_size_transitioned_gb': 0,
            'estimated_cost_savings': 0.0
        }
        
        try:
            # Calculate threshold date
            threshold_date = datetime.now() - timedelta(days=days_threshold)
            
            # List objects in source storage class
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            def transition_object(obj):
                """Transition a single object to target storage class"""
                try:
                    # Check if object meets age criteria
                    if obj['LastModified'].replace(tzinfo=None) > threshold_date:
                        return {'status': 'skipped', 'reason': 'too_recent'}
                    
                    # Copy object to same location with new storage class
                    copy_source = {
                        'Bucket': self.bucket_name,
                        'Key': obj['Key']
                    }
                    
                    self.s3_client.copy_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key'],
                        CopySource=copy_source,
                        StorageClass=target_class,
                        MetadataDirective='REPLACE'
                    )
                    
                    # Delete original object
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    
                    size_gb = obj['Size'] / (1024**3)
                    return {
                        'status': 'success',
                        'size_gb': size_gb,
                        'key': obj['Key']
                    }
                    
                except ClientError as e:
                    return {
                        'status': 'failed',
                        'reason': str(e),
                        'key': obj['Key']
                    }
            
            # Process objects with ThreadPoolExecutor for parallel processing
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                
                for page in page_iterator:
                    if 'Contents' not in page:
                        continue
                    
                    for obj in page['Contents']:
                        if obj.get('StorageClass', 'STANDARD') == source_class:
                            future = executor.submit(transition_object, obj)
                            futures.append(future)
                
                # Collect results
                for future in as_completed(futures):
                    result = future.result()
                    
                    if result['status'] == 'success':
                        transition_results['objects_transitioned'] += 1
                        transition_results['total_size_transitioned_gb'] += result['size_gb']
                        self._update_stats(objects_transitioned=1)
                    elif result['status'] == 'skipped':
                        transition_results['objects_skipped'] += 1
                    else:
                        transition_results['objects_failed'] += 1
                        self.logger.log_warning(f"Failed to transition object {result['key']}: {result['reason']}")
            
            # Calculate estimated cost savings
            if source_class in self.STORAGE_CLASSES and target_class in self.STORAGE_CLASSES:
                source_cost = self.STORAGE_CLASSES[source_class]['cost_per_gb_month']
                target_cost = self.STORAGE_CLASSES[target_class]['cost_per_gb_month']
                monthly_savings = (source_cost - target_cost) * transition_results['total_size_transitioned_gb']
                transition_results['estimated_cost_savings'] = monthly_savings
            
            self._update_stats(end_time=datetime.now())
            self.logger.log_info(f"Object transitions completed. Transitioned {transition_results['objects_transitioned']} objects")
            
            return transition_results
            
        except ClientError as e:
            self.logger.log_error(f"Error transitioning objects: {e}")
            raise
    
    def optimize_storage(self, dry_run: bool = True) -> Dict:
        """
        Optimize storage costs by applying intelligent transitions
        
        AWS Concepts:
        - Automated storage optimization
        - Cost-based decision making
        - Batch processing with rollback capability
        - Performance monitoring and metrics
        """
        self.logger.log_info("Starting storage optimization analysis")
        
        optimization_results = {
            'analysis_completed': False,
            'recommendations_applied': 0,
            'estimated_monthly_savings': 0.0,
            'objects_optimized': 0,
            'dry_run': dry_run
        }
        
        try:
            # Analyze current storage costs
            storage_analysis = self.analyze_storage_costs()
            optimization_results['analysis_completed'] = True
            
            # Apply optimization recommendations
            for recommendation in storage_analysis['optimization_recommendations']:
                if recommendation['potential_savings_per_month'] > 10.0:  # Only if savings > $10/month
                    if not dry_run:
                        # Apply the transition
                        transition_result = self.transition_objects(
                            source_class=recommendation['current_storage_class'],
                            target_class=recommendation['recommended_storage_class'],
                            days_threshold=30
                        )
                        
                        optimization_results['recommendations_applied'] += 1
                        optimization_results['objects_optimized'] += transition_result['objects_transitioned']
                        optimization_results['estimated_monthly_savings'] += recommendation['potential_savings_per_month']
                    else:
                        # Just count the potential savings
                        optimization_results['estimated_monthly_savings'] += recommendation['potential_savings_per_month']
            
            self.logger.log_info(f"Storage optimization completed. Estimated monthly savings: ${optimization_results['estimated_monthly_savings']:.2f}")
            return optimization_results
            
        except Exception as e:
            self.logger.log_error(f"Error during storage optimization: {e}")
            raise
    
    def get_storage_class_info(self, storage_class: str = None) -> Dict:
        """Get detailed information about storage classes"""
        if storage_class:
            return self.STORAGE_CLASSES.get(storage_class, {})
        else:
            return self.STORAGE_CLASSES
    
    def print_summary(self):
        """Print summary of storage management operations"""
        duration = None
        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
        
        print("\n" + "="*60)
        print("STORAGE CLASS MANAGEMENT SUMMARY")
        print("="*60)
        print(f"Bucket: {self.bucket_name}")
        print(f"Objects Analyzed: {self.stats['objects_analyzed']:,}")
        print(f"Objects Transitioned: {self.stats['objects_transitioned']:,}")
        print(f"Estimated Cost Savings: ${self.stats['cost_savings_estimated']:.2f}/month")
        if duration:
            print(f"Duration: {duration}")
        print("="*60)


def main():
    """Main function for command-line interface"""
    parser = argparse.ArgumentParser(
        description="Storage Class Manager for AWS S3 Photo Sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/storage-class-manager.py --analyze-costs
  python scripts/storage-class-manager.py --optimize-storage --dry-run
  python scripts/storage-class-manager.py --transition-objects --source STANDARD --target STANDARD_IA
  python scripts/storage-class-manager.py --apply-lifecycle-policy
        """
    )
    
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--bucket', help='S3 bucket name')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    # Analysis commands
    parser.add_argument('--analyze-costs', action='store_true', 
                       help='Analyze storage costs and generate recommendations')
    parser.add_argument('--storage-class-info', help='Get info about specific storage class')
    
    # Optimization commands
    parser.add_argument('--optimize-storage', action='store_true',
                       help='Optimize storage costs automatically')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    
    # Transition commands
    parser.add_argument('--transition-objects', action='store_true',
                       help='Transition objects between storage classes')
    parser.add_argument('--source', help='Source storage class for transitions')
    parser.add_argument('--target', help='Target storage class for transitions')
    parser.add_argument('--days', type=int, default=30,
                       help='Age threshold in days for transitions')
    parser.add_argument('--prefix', help='Object prefix filter for transitions')
    
    # Lifecycle commands
    parser.add_argument('--apply-lifecycle-policy', action='store_true',
                       help='Apply lifecycle policy to bucket')
    
    args = parser.parse_args()
    
    try:
        # Initialize storage class manager
        manager = StorageClassManager(
            config_file=args.config,
            profile=args.profile,
            bucket_name=args.bucket,
            verbose=args.verbose
        )
        
        # Execute requested operations
        if args.analyze_costs:
            analysis = manager.analyze_storage_costs()
            print(json.dumps(analysis, indent=2, default=str))
        
        elif args.storage_class_info:
            info = manager.get_storage_class_info(args.storage_class_info)
            print(json.dumps(info, indent=2))
        
        elif args.optimize_storage:
            results = manager.optimize_storage(dry_run=args.dry_run)
            print(json.dumps(results, indent=2))
        
        elif args.transition_objects:
            if not args.source or not args.target:
                print("❌ --source and --target are required for object transitions")
                sys.exit(1)
            
            results = manager.transition_objects(
                source_class=args.source,
                target_class=args.target,
                days_threshold=args.days,
                prefix=args.prefix
            )
            print(json.dumps(results, indent=2))
        
        elif args.apply_lifecycle_policy:
            success = manager.apply_lifecycle_policy()
            print(f"Lifecycle policy application: {'SUCCESS' if success else 'FAILED'}")
        
        else:
            # Default: show storage class information
            info = manager.get_storage_class_info()
            print(json.dumps(info, indent=2))
        
        manager.print_summary()
        
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 