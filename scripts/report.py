#!/usr/bin/env python3
"""
Sync Reporting Module for AWS S3 Operations

This module provides comprehensive reporting capabilities for sync operations,
including sync history reports, cost analysis, storage usage, and performance analytics.
Designed for AWS certification study with practical reporting implementation.

AWS Concepts Covered:
- S3 Analytics and Inventory
- CloudWatch Metrics and Insights
- Cost and Usage Reports
- Storage class optimization reporting
- Performance analytics and trends
- Operational reporting and dashboards

Usage:
    from scripts.report import SyncReporter
    reporter = SyncReporter('sync-operation')
    reporter.generate_sync_history_report()
    reporter.generate_cost_analysis_report()
    reporter.generate_storage_usage_report()
    reporter.generate_performance_report()
"""

import json
import os
import sys
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging
from collections import defaultdict, Counter

class SyncReporter:
    """Comprehensive reporting for sync operations with AWS integration"""
    
    def __init__(self, operation_name: str, config: Dict[str, Any] = None):
        """Initialize sync reporter with configuration"""
        self.operation_name = operation_name
        self.config = config or {}
        self.project_root = Path(__file__).parent.parent
        
        # AWS configuration
        self.s3_enabled = self.config.get('reporting', {}).get('s3_enabled', True)
        self.cloudwatch_enabled = self.config.get('reporting', {}).get('cloudwatch_enabled', True)
        self.reports_dir = self.config.get('reporting', {}).get('reports_dir', 'reports')
        
        # Reporting state
        self.reports_generated = []
        self.report_data = {}
        
        # Setup reporting infrastructure
        self._setup_reporting()
        
        # Initialize AWS clients if enabled
        if self.s3_enabled or self.cloudwatch_enabled:
            self._setup_aws_clients()
    
    def _setup_reporting(self):
        """Setup reporting infrastructure"""
        # Create reports directory
        reports_dir = self.project_root / self.reports_dir
        reports_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger(f"reporter.{self.operation_name}")
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"reporter-{self.operation_name}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_formatter)
        self.logger.addHandler(file_handler)
    
    def _setup_aws_clients(self):
        """Setup AWS clients for reporting"""
        try:
            if self.s3_enabled:
                self.s3 = boto3.client('s3')
            if self.cloudwatch_enabled:
                self.cloudwatch = boto3.client('cloudwatch')
            self.logger.info("AWS clients initialized for reporting")
        except (NoCredentialsError, ClientError) as e:
            self.logger.warning(f"AWS setup failed: {e}")
            self.s3_enabled = False
            self.cloudwatch_enabled = False
    
    def generate_sync_history_report(self, days: int = 30, bucket_name: str = None) -> Dict[str, Any]:
        """Generate sync history report"""
        self.logger.info(f"Generating sync history report for {days} days")
        
        # Collect sync history data
        history_data = self._collect_sync_history(days)
        
        # Generate report
        report = {
            'report_type': 'sync_history',
            'operation_name': self.operation_name,
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'bucket_name': bucket_name,
            'summary': {
                'total_syncs': len(history_data),
                'successful_syncs': len([h for h in history_data if h.get('success', False)]),
                'failed_syncs': len([h for h in history_data if not h.get('success', True)]),
                'total_files_processed': sum(h.get('files_processed', 0) for h in history_data),
                'total_bytes_uploaded': sum(h.get('bytes_uploaded', 0) for h in history_data),
                'average_duration': self._calculate_average_duration(history_data)
            },
            'sync_history': history_data,
            'trends': self._analyze_sync_trends(history_data)
        }
        
        # Save report
        self._save_report('sync_history', report)
        
        return report
    
    def generate_cost_analysis_report(self, days: int = 30, bucket_name: str = None) -> Dict[str, Any]:
        """Generate cost analysis report"""
        self.logger.info(f"Generating cost analysis report for {days} days")
        
        # Collect cost data
        cost_data = self._collect_cost_data(days, bucket_name)
        
        # Generate report
        report = {
            'report_type': 'cost_analysis',
            'operation_name': self.operation_name,
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'bucket_name': bucket_name,
            'summary': {
                'total_cost': cost_data.get('total_cost', 0),
                'storage_cost': cost_data.get('storage_cost', 0),
                'transfer_cost': cost_data.get('transfer_cost', 0),
                'request_cost': cost_data.get('request_cost', 0),
                'cost_per_gb': cost_data.get('cost_per_gb', 0),
                'cost_trend': cost_data.get('cost_trend', 'stable')
            },
            'cost_breakdown': cost_data.get('breakdown', {}),
            'storage_class_costs': cost_data.get('storage_class_costs', {}),
            'recommendations': self._generate_cost_recommendations(cost_data)
        }
        
        # Save report
        self._save_report('cost_analysis', report)
        
        return report
    
    def generate_storage_usage_report(self, bucket_name: str = None) -> Dict[str, Any]:
        """Generate storage usage report"""
        self.logger.info(f"Generating storage usage report for bucket: {bucket_name}")
        
        # Collect storage data
        storage_data = self._collect_storage_data(bucket_name)
        
        # Generate report
        report = {
            'report_type': 'storage_usage',
            'operation_name': self.operation_name,
            'generated_at': datetime.now().isoformat(),
            'bucket_name': bucket_name,
            'summary': {
                'total_objects': storage_data.get('total_objects', 0),
                'total_size_bytes': storage_data.get('total_size_bytes', 0),
                'total_size_gb': storage_data.get('total_size_gb', 0),
                'storage_classes': storage_data.get('storage_classes', {}),
                'object_distribution': storage_data.get('object_distribution', {}),
                'size_distribution': storage_data.get('size_distribution', {})
            },
            'storage_details': storage_data.get('details', {}),
            'optimization_opportunities': self._identify_optimization_opportunities(storage_data)
        }
        
        # Save report
        self._save_report('storage_usage', report)
        
        return report
    
    def generate_performance_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate performance analytics report"""
        self.logger.info(f"Generating performance report for {days} days")
        
        # Collect performance data
        performance_data = self._collect_performance_data(days)
        
        # Generate report
        report = {
            'report_type': 'performance_analytics',
            'operation_name': self.operation_name,
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'summary': {
                'average_throughput_mbps': performance_data.get('average_throughput_mbps', 0),
                'peak_throughput_mbps': performance_data.get('peak_throughput_mbps', 0),
                'average_latency_ms': performance_data.get('average_latency_ms', 0),
                'error_rate_percent': performance_data.get('error_rate_percent', 0),
                'success_rate_percent': performance_data.get('success_rate_percent', 100)
            },
            'performance_metrics': performance_data.get('metrics', {}),
            'bottlenecks': performance_data.get('bottlenecks', []),
            'recommendations': self._generate_performance_recommendations(performance_data)
        }
        
        # Save report
        self._save_report('performance_analytics', report)
        
        return report
    
    def _collect_sync_history(self, days: int) -> List[Dict[str, Any]]:
        """Collect sync history data from logs and CloudWatch"""
        history_data = []
        
        # Read from local log files
        log_dir = self.project_root / "logs"
        if log_dir.exists():
            for log_file in log_dir.glob("sync-*.log"):
                history_data.extend(self._parse_sync_log(log_file, days))
        
        # Collect from CloudWatch if enabled
        if self.cloudwatch_enabled:
            history_data.extend(self._collect_cloudwatch_sync_history(days))
        
        # Sort by timestamp, handling both timezone-aware and timezone-naive datetimes
        def get_sortable_timestamp(item):
            timestamp = item.get('timestamp', '')
            if isinstance(timestamp, datetime):
                # Convert to timezone-naive for comparison
                if timestamp.tzinfo is not None:
                    return timestamp.replace(tzinfo=None)
                return timestamp
            return timestamp
        
        return sorted(history_data, key=get_sortable_timestamp, reverse=True)
    
    def _collect_cost_data(self, days: int, bucket_name: str = None) -> Dict[str, Any]:
        """Collect cost data from AWS Cost Explorer and S3"""
        cost_data = {
            'total_cost': 0,
            'storage_cost': 0,
            'transfer_cost': 0,
            'request_cost': 0,
            'cost_per_gb': 0,
            'breakdown': {},
            'storage_class_costs': {},
            'cost_trend': 'stable'
        }
        
        if not bucket_name:
            return cost_data
        
        try:
            # Get bucket size and object count
            response = self.s3.list_objects_v2(Bucket=bucket_name)
            total_size = 0
            object_count = 0
            
            for obj in response.get('Contents', []):
                total_size += obj['Size']
                object_count += 1
            
            # Calculate estimated costs (simplified)
            # These are rough estimates - in production, use Cost Explorer API
            storage_cost_per_gb = 0.023  # Standard storage cost per GB
            transfer_cost_per_gb = 0.09  # Transfer cost per GB
            request_cost_per_1000 = 0.005  # Request cost per 1000 requests
            
            cost_data['storage_cost'] = (total_size / (1024**3)) * storage_cost_per_gb
            cost_data['transfer_cost'] = (total_size / (1024**3)) * transfer_cost_per_gb
            cost_data['request_cost'] = (object_count / 1000) * request_cost_per_1000
            cost_data['total_cost'] = cost_data['storage_cost'] + cost_data['transfer_cost'] + cost_data['request_cost']
            
            if total_size > 0:
                cost_data['cost_per_gb'] = cost_data['total_cost'] / (total_size / (1024**3))
            
        except ClientError as e:
            self.logger.error(f"Failed to collect cost data: {e}")
        
        return cost_data
    
    def _collect_storage_data(self, bucket_name: str = None) -> Dict[str, Any]:
        """Collect storage usage data from S3"""
        storage_data = {
            'total_objects': 0,
            'total_size_bytes': 0,
            'total_size_gb': 0,
            'storage_classes': {},
            'object_distribution': {},
            'size_distribution': {},
            'details': {}
        }
        
        if not bucket_name:
            return storage_data
        
        try:
            # Get bucket objects
            response = self.s3.list_objects_v2(Bucket=bucket_name)
            
            size_ranges = {
                'small': (0, 1024*1024),  # < 1MB
                'medium': (1024*1024, 10*1024*1024),  # 1MB - 10MB
                'large': (10*1024*1024, 100*1024*1024),  # 10MB - 100MB
                'xlarge': (100*1024*1024, float('inf'))  # > 100MB
            }
            
            size_distribution = defaultdict(int)
            storage_classes = defaultdict(int)
            
            for obj in response.get('Contents', []):
                size = obj['Size']
                storage_class = obj.get('StorageClass', 'STANDARD')
                
                storage_data['total_objects'] += 1
                storage_data['total_size_bytes'] += size
                storage_classes[storage_class] += 1
                
                # Categorize by size
                for range_name, (min_size, max_size) in size_ranges.items():
                    if min_size <= size < max_size:
                        size_distribution[range_name] += 1
                        break
            
            storage_data['total_size_gb'] = storage_data['total_size_bytes'] / (1024**3)
            storage_data['storage_classes'] = dict(storage_classes)
            storage_data['size_distribution'] = dict(size_distribution)
            
        except ClientError as e:
            self.logger.error(f"Failed to collect storage data: {e}")
        
        return storage_data
    
    def _collect_performance_data(self, days: int) -> Dict[str, Any]:
        """Collect performance data from CloudWatch and logs"""
        performance_data = {
            'average_throughput_mbps': 0,
            'peak_throughput_mbps': 0,
            'average_latency_ms': 0,
            'error_rate_percent': 0,
            'success_rate_percent': 100,
            'metrics': {},
            'bottlenecks': [],
            'recommendations': []
        }
        
        # Read performance data from logs
        log_dir = self.project_root / "logs"
        if log_dir.exists():
            for log_file in log_dir.glob("monitor-*.log"):
                performance_data.update(self._parse_performance_log(log_file, days))
        
        return performance_data
    
    def _parse_sync_log(self, log_file: Path, days: int) -> List[Dict[str, Any]]:
        """Parse sync log file for history data"""
        history_entries = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if 'sync' in line.lower() and 'start' in line.lower():
                        # Parse sync start entry
                        entry = self._parse_log_line(line)
                        if entry and entry.get('timestamp', datetime.min) >= cutoff_date:
                            history_entries.append(entry)
        except Exception as e:
            self.logger.warning(f"Failed to parse log file {log_file}: {e}")
        
        return history_entries
    
    def _parse_performance_log(self, log_file: Path, days: int) -> Dict[str, Any]:
        """Parse performance log file for metrics"""
        performance_data = {
            'average_throughput_mbps': 0,
            'peak_throughput_mbps': 0,
            'average_latency_ms': 0
        }
        throughput_values = []
        latency_values = []
        
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if 'throughput' in line.lower():
                        # Extract throughput value
                        try:
                            # Look for pattern like "Throughput: 15.5 MB/s"
                            parts = line.split('Throughput:')
                            if len(parts) > 1:
                                throughput_str = parts[1].split()[0]
                                throughput = float(throughput_str)
                                throughput_values.append(throughput)
                        except (IndexError, ValueError):
                            pass
                    
                    if 'latency' in line.lower():
                        # Extract latency value
                        try:
                            # Look for pattern like "Latency: 250 ms"
                            parts = line.split('Latency:')
                            if len(parts) > 1:
                                latency_str = parts[1].split()[0]
                                latency = float(latency_str)
                                latency_values.append(latency)
                        except (IndexError, ValueError):
                            pass
        
        except Exception as e:
            self.logger.warning(f"Failed to parse performance log {log_file}: {e}")
        
        if throughput_values:
            performance_data['average_throughput_mbps'] = sum(throughput_values) / len(throughput_values)
            performance_data['peak_throughput_mbps'] = max(throughput_values)
        
        if latency_values:
            performance_data['average_latency_ms'] = sum(latency_values) / len(latency_values)
        
        return performance_data
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single log line for sync information"""
        try:
            # Simple parsing - in production, use structured logging
            if 'sync' in line.lower() and 'start' in line.lower():
                return {
                    'timestamp': datetime.now(),  # Simplified
                    'operation': 'sync',
                    'success': True,  # Simplified
                    'files_processed': 0,
                    'bytes_uploaded': 0
                }
        except Exception:
            pass
        
        return None
    
    def _collect_cloudwatch_sync_history(self, days: int) -> List[Dict[str, Any]]:
        """Collect sync history from CloudWatch"""
        history_data = []
        
        if not self.cloudwatch_enabled:
            return history_data
        
        try:
            # Get metrics from CloudWatch
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            response = self.cloudwatch.get_metric_data(
                MetricDataQueries=[
                    {
                        'Id': 'sync_operations',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'S3Sync/Photos',
                                'MetricName': 'FilesUploaded'
                            },
                            'Period': 3600,  # 1 hour
                            'Stat': 'Sum'
                        },
                        'ReturnData': True
                    }
                ],
                StartTime=start_time,
                EndTime=end_time
            )
            
            # Process metric data
            for i, timestamp in enumerate(response['MetricDataResults'][0]['Timestamps']):
                value = response['MetricDataResults'][0]['Values'][i]
                history_data.append({
                    'timestamp': timestamp,
                    'operation': 'sync',
                    'files_uploaded': int(value),
                    'success': True
                })
        
        except ClientError as e:
            self.logger.error(f"Failed to collect CloudWatch sync history: {e}")
        
        return history_data
    
    def _calculate_average_duration(self, history_data: List[Dict[str, Any]]) -> float:
        """Calculate average sync duration"""
        durations = [h.get('duration', 0) for h in history_data if h.get('duration')]
        return sum(durations) / len(durations) if durations else 0
    
    def _analyze_sync_trends(self, history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sync trends"""
        if not history_data:
            return {}
        
        # Group by date
        daily_stats = defaultdict(lambda: {'count': 0, 'files': 0, 'bytes': 0})
        
        for entry in history_data:
            date = entry.get('timestamp', datetime.now()).date()
            daily_stats[date]['count'] += 1
            daily_stats[date]['files'] += entry.get('files_processed', 0)
            daily_stats[date]['bytes'] += entry.get('bytes_uploaded', 0)
        
        return {
            'daily_syncs': dict(daily_stats),
            'total_days': len(daily_stats),
            'average_daily_syncs': sum(stats['count'] for stats in daily_stats.values()) / len(daily_stats) if daily_stats else 0
        }
    
    def _generate_cost_recommendations(self, cost_data: Dict[str, Any]) -> List[str]:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        if cost_data.get('storage_cost', 0) > cost_data.get('transfer_cost', 0) * 2:
            recommendations.append("Consider using S3 Intelligent-Tiering for cost optimization")
        
        if cost_data.get('cost_per_gb', 0) > 0.05:  # High cost per GB
            recommendations.append("Review storage class usage - consider moving to cheaper tiers")
        
        if cost_data.get('total_cost', 0) > 100:  # High total cost
            recommendations.append("Consider implementing lifecycle policies to reduce storage costs")
        
        return recommendations
    
    def _identify_optimization_opportunities(self, storage_data: Dict[str, Any]) -> List[str]:
        """Identify storage optimization opportunities"""
        opportunities = []
        
        # Check for large objects that could be compressed
        large_objects = storage_data.get('size_distribution', {}).get('large', 0)
        xlarge_objects = storage_data.get('size_distribution', {}).get('xlarge', 0)
        
        if large_objects + xlarge_objects > 100:
            opportunities.append("Consider compression for large objects to reduce storage costs")
        
        # Check storage class distribution
        storage_classes = storage_data.get('storage_classes', {})
        if storage_classes.get('STANDARD', 0) > storage_classes.get('STANDARD_IA', 0) * 10:
            opportunities.append("Consider moving infrequently accessed objects to STANDARD_IA")
        
        return opportunities
    
    def _generate_performance_recommendations(self, performance_data: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        throughput = performance_data.get('average_throughput_mbps', 0)
        latency = performance_data.get('average_latency_ms', 0)
        error_rate = performance_data.get('error_rate_percent', 0)
        
        if throughput < 10:  # Low throughput
            recommendations.append("Consider using multipart uploads for large files")
        
        if latency > 1000:  # High latency
            recommendations.append("Review network connectivity and consider using AWS Direct Connect")
        
        if error_rate > 5:  # High error rate
            recommendations.append("Implement retry logic with exponential backoff")
        
        return recommendations
    
    def _save_report(self, report_type: str, report_data: Dict[str, Any]):
        """Save report to file"""
        reports_dir = self.project_root / self.reports_dir
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{report_type}_{self.operation_name}_{timestamp}.json"
        report_path = reports_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            self.reports_generated.append(filename)
            self.report_data[report_type] = report_data
            
            self.logger.info(f"Report saved: {report_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
    
    def export_report_to_csv(self, report_type: str, output_file: str = None):
        """Export report to CSV format"""
        if report_type not in self.report_data:
            self.logger.error(f"Report type {report_type} not found")
            return
        
        report = self.report_data[report_type]
        
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"{report_type}_{self.operation_name}_{timestamp}.csv"
        
        reports_dir = self.project_root / self.reports_dir
        csv_path = reports_dir / output_file
        
        try:
            with open(csv_path, 'w', newline='') as csvfile:
                if report_type == 'sync_history':
                    self._export_sync_history_to_csv(report, csvfile)
                elif report_type == 'cost_analysis':
                    self._export_cost_analysis_to_csv(report, csvfile)
                elif report_type == 'storage_usage':
                    self._export_storage_usage_to_csv(report, csvfile)
                elif report_type == 'performance_analytics':
                    self._export_performance_to_csv(report, csvfile)
            
            self.logger.info(f"CSV report exported: {csv_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export CSV report: {e}")
    
    def _export_sync_history_to_csv(self, report: Dict[str, Any], csvfile):
        """Export sync history to CSV"""
        writer = csv.writer(csvfile)
        writer.writerow(['Timestamp', 'Operation', 'Success', 'Files Processed', 'Bytes Uploaded'])
        
        for entry in report.get('sync_history', []):
            writer.writerow([
                entry.get('timestamp', ''),
                entry.get('operation', ''),
                entry.get('success', False),
                entry.get('files_processed', 0),
                entry.get('bytes_uploaded', 0)
            ])
    
    def _export_cost_analysis_to_csv(self, report: Dict[str, Any], csvfile):
        """Export cost analysis to CSV"""
        writer = csv.writer(csvfile)
        writer.writerow(['Cost Type', 'Amount', 'Percentage'])
        
        summary = report.get('summary', {})
        total_cost = summary.get('total_cost', 0)
        
        if total_cost > 0:
            writer.writerow(['Storage Cost', summary.get('storage_cost', 0), 
                           f"{(summary.get('storage_cost', 0) / total_cost) * 100:.2f}%"])
            writer.writerow(['Transfer Cost', summary.get('transfer_cost', 0),
                           f"{(summary.get('transfer_cost', 0) / total_cost) * 100:.2f}%"])
            writer.writerow(['Request Cost', summary.get('request_cost', 0),
                           f"{(summary.get('request_cost', 0) / total_cost) * 100:.2f}%"])
    
    def _export_storage_usage_to_csv(self, report: Dict[str, Any], csvfile):
        """Export storage usage to CSV"""
        writer = csv.writer(csvfile)
        writer.writerow(['Storage Class', 'Object Count', 'Total Size (GB)'])
        
        storage_classes = report.get('summary', {}).get('storage_classes', {})
        for storage_class, count in storage_classes.items():
            writer.writerow([storage_class, count, 0])  # Size calculation would need more data
    
    def _export_performance_to_csv(self, report: Dict[str, Any], csvfile):
        """Export performance analytics to CSV"""
        writer = csv.writer(csvfile)
        writer.writerow(['Metric', 'Value', 'Unit'])
        
        summary = report.get('summary', {})
        writer.writerow(['Average Throughput', summary.get('average_throughput_mbps', 0), 'MB/s'])
        writer.writerow(['Peak Throughput', summary.get('peak_throughput_mbps', 0), 'MB/s'])
        writer.writerow(['Average Latency', summary.get('average_latency_ms', 0), 'ms'])
        writer.writerow(['Error Rate', summary.get('error_rate_percent', 0), '%'])
        writer.writerow(['Success Rate', summary.get('success_rate_percent', 100), '%'])


def create_sync_reporter(operation_name: str, config: Dict[str, Any] = None) -> SyncReporter:
    """Factory function to create a sync reporter"""
    return SyncReporter(operation_name, config)


if __name__ == "__main__":
    """Test the reporting functionality"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test sync reporting")
    parser.add_argument("--operation", default="test-reporter", help="Operation name")
    parser.add_argument("--bucket", help="S3 bucket name for analysis")
    parser.add_argument("--days", type=int, default=30, help="Analysis period in days")
    
    args = parser.parse_args()
    
    # Create reporter
    reporter = SyncReporter(args.operation)
    
    # Generate reports
    reporter.generate_sync_history_report(args.days, args.bucket)
    reporter.generate_cost_analysis_report(args.days, args.bucket)
    reporter.generate_storage_usage_report(args.bucket)
    reporter.generate_performance_report(args.days)
    
    print(f"Generated {len(reporter.reports_generated)} reports") 