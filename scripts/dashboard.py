#!/usr/bin/env python3
"""
Dynamic Dashboard Module for S3 Sync Operations

This module provides a comprehensive real-time dashboard for sync operations,
showing detailed progress information including upload speed, verification status,
file types, age analysis, and performance metrics without screen scrolling.

AWS Concepts Covered:
- Real-time monitoring and metrics
- Performance analytics and optimization
- File metadata analysis and tracking
- Progress visualization and reporting
- Operational dashboards and insights

Usage:
    from scripts.dashboard import SyncDashboard
    dashboard = SyncDashboard('sync-operation')
    dashboard.start()
    dashboard.update_progress(file_info, upload_speed, verification_status)
    dashboard.stop()
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
from collections import defaultdict, Counter
import math

# Try to import rich for enhanced display
try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.layout import Layout
    from rich.columns import Columns
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

class SyncDashboard:
    """Dynamic dashboard for sync operations with real-time progress monitoring"""
    
    def __init__(self, operation_name: str, config: Dict[str, Any] = None):
        """Initialize sync dashboard with configuration"""
        self.operation_name = operation_name
        self.config = config or {}
        self.project_root = Path(__file__).parent.parent
        
        # Dashboard state
        self.dashboard_active = False
        self.start_time = None
        self.last_update_time = None
        
        # Rich console setup
        if RICH_AVAILABLE:
            self.console = Console()
            self.live = None
        else:
            self.console = None
            self.live = None
        
        # Progress tracking
        self.progress_data = {
            'total_files': 0,
            'files_processed': 0,
            'files_uploaded': 0,
            'files_skipped': 0,
            'files_failed': 0,
            'files_verifying': 0,
            'bytes_uploaded': 0,
            'bytes_processed': 0,
            'upload_speed_mbps': 0.0,
            'average_speed_mbps': 0.0,
            'peak_speed_mbps': 0.0,
            'bandwidth_history': [],
            'verification_passed': 0,
            'verification_failed': 0,
            'verification_pending': 0,
            'errors': [],
            'warnings': [],
            'file_types': Counter(),
            'file_ages': defaultdict(int),
            'file_sizes': [],
            'recent_uploads': [],
            'performance_metrics': {
                'upload_times': [],
                'verification_times': [],
                'retry_count': 0,
                'concurrent_uploads': 0
            }
        }
        
        # Thread safety
        self.progress_lock = threading.Lock()
        
        # Setup dashboard infrastructure
        self._setup_dashboard()
    
    def _setup_dashboard(self):
        """Setup dashboard infrastructure"""
        # Setup logging
        self.logger = logging.getLogger(f"dashboard.{self.operation_name}")
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
    
    def start(self):
        """Start the dashboard display"""
        self.dashboard_active = True
        self.start_time = datetime.now()
        self.last_update_time = self.start_time
        
        if RICH_AVAILABLE:
            self.live = Live(self._create_dashboard_layout(), refresh_per_second=2)
            self.live.start()
        else:
            self._print_simple_header()
    
    def stop(self):
        """Stop the dashboard display"""
        self.dashboard_active = False
        
        if RICH_AVAILABLE and self.live:
            self.live.stop()
        
        self._print_final_summary()
    
    def update_progress(self, file_info: Dict[str, Any] = None, 
                       upload_speed: float = None, 
                       verification_status: str = None,
                       error: Exception = None):
        """Update progress with new information"""
        with self.progress_lock:
            current_time = datetime.now()
            
            # Update basic progress
            if file_info:
                self._update_file_progress(file_info)
            
            # Update upload speed
            if upload_speed is not None:
                self.progress_data['upload_speed_mbps'] = upload_speed
                self.progress_data['performance_metrics']['upload_times'].append(upload_speed)
                
                # Track peak speed
                if upload_speed > self.progress_data['peak_speed_mbps']:
                    self.progress_data['peak_speed_mbps'] = upload_speed
                
                # Add to bandwidth history with timestamp
                self.progress_data['bandwidth_history'].append({
                    'speed': upload_speed,
                    'timestamp': current_time,
                    'bytes_uploaded': self.progress_data['bytes_uploaded']
                })
                
                # Keep only last 100 bandwidth measurements
                if len(self.progress_data['bandwidth_history']) > 100:
                    self.progress_data['bandwidth_history'] = self.progress_data['bandwidth_history'][-100:]
                
                # Calculate average speed
                if self.progress_data['performance_metrics']['upload_times']:
                    self.progress_data['average_speed_mbps'] = sum(
                        self.progress_data['performance_metrics']['upload_times']
                    ) / len(self.progress_data['performance_metrics']['upload_times'])
            
            # Update verification status
            if verification_status:
                self._update_verification_status(verification_status)
            
            # Update errors
            if error:
                self.progress_data['errors'].append({
                    'error': str(error),
                    'time': current_time,
                    'file': file_info.get('file_name', 'Unknown') if file_info else 'Unknown'
                })
            
            # Update display only if dashboard is active
            if self.dashboard_active:
                self.last_update_time = current_time
                
                if RICH_AVAILABLE and self.live:
                    self.live.update(self._create_dashboard_layout())
                else:
                    self._print_simple_progress()
    
    def _update_file_progress(self, file_info: Dict[str, Any]):
        """Update file-specific progress information"""
        file_path = Path(file_info.get('file_path', ''))
        file_size = file_info.get('file_size', 0)
        file_type = file_path.suffix.lower() if file_path.suffix else 'unknown'
        
        # Calculate file age safely
        try:
            file_age_days = (datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)).days
        except (FileNotFoundError, OSError):
            # If file doesn't exist, use a default age
            file_age_days = 0
        
        # Update file type counter
        self.progress_data['file_types'][file_type] += 1
        
        # Update file age distribution
        age_category = self._categorize_file_age(file_age_days)
        self.progress_data['file_ages'][age_category] += 1
        
        # Update file sizes
        self.progress_data['file_sizes'].append(file_size)
        
        # Update recent uploads
        self.progress_data['recent_uploads'].append({
            'name': file_path.name,
            'size': file_size,
            'type': file_type,
            'time': datetime.now()
        })
        
        # Keep only last 10 recent uploads
        if len(self.progress_data['recent_uploads']) > 10:
            self.progress_data['recent_uploads'] = self.progress_data['recent_uploads'][-10:]
    
    def _update_verification_status(self, status: str):
        """Update verification status counters"""
        if status == 'passed':
            self.progress_data['verification_passed'] += 1
        elif status == 'failed':
            self.progress_data['verification_failed'] += 1
        elif status == 'pending':
            self.progress_data['verification_pending'] += 1
    
    def _categorize_file_age(self, age_days: int) -> str:
        """Categorize file age for display"""
        if age_days < 1:
            return 'Today'
        elif age_days < 7:
            return 'This Week'
        elif age_days < 30:
            return 'This Month'
        elif age_days < 90:
            return 'Last 3 Months'
        elif age_days < 365:
            return 'Last Year'
        else:
            return 'Older'
    
    def _create_dashboard_layout(self):
        """Create the rich dashboard layout"""
        layout = Layout()
        
        # Create main sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=8)
        )
        
        layout["main"].split_row(
            Layout(name="progress", ratio=2),
            Layout(name="details", ratio=1)
        )
        
        # Populate sections
        layout["header"].update(self._create_header_panel())
        layout["progress"].update(self._create_progress_panel())
        layout["details"].update(self._create_details_panel())
        layout["footer"].update(self._create_footer_panel())
        
        return layout
    
    def _create_header_panel(self):
        """Create header panel with operation info"""
        duration = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        header_text = f"""
[bold blue]🔄 S3 Sync Dashboard[/bold blue]
[dim]Operation:[/dim] {self.operation_name} | [dim]Duration:[/dim] {str(duration).split('.')[0]} | [dim]Last Update:[/dim] {self.last_update_time.strftime('%H:%M:%S') if self.last_update_time else 'N/A'}
        """.strip()
        
        return Panel(header_text, title="📊 Sync Progress", border_style="blue")
    
    def _create_progress_panel(self):
        """Create main progress panel"""
        total_files = self.progress_data['total_files']
        processed = self.progress_data['files_processed']
        uploaded = self.progress_data['files_uploaded']
        skipped = self.progress_data['files_skipped']
        failed = self.progress_data['files_failed']
        
        # Calculate percentages
        progress_percent = (processed / total_files * 100) if total_files > 0 else 0
        upload_percent = (uploaded / total_files * 100) if total_files > 0 else 0
        
        # Format bytes
        bytes_uploaded = self.progress_data['bytes_uploaded']
        bytes_gb = bytes_uploaded / (1024**3)
        bytes_mb = bytes_uploaded / (1024**2)
        
        # Calculate bandwidth statistics
        current_speed = self.progress_data['upload_speed_mbps']
        avg_speed = self.progress_data['average_speed_mbps']
        peak_speed = self.progress_data['peak_speed_mbps']
        
        # Calculate recent bandwidth trend (last 10 measurements)
        recent_speeds = [entry['speed'] for entry in self.progress_data['bandwidth_history'][-10:]]
        recent_avg = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0
        
        progress_text = f"""
[bold]Overall Progress:[/bold] {progress_percent:.1f}% ({processed}/{total_files})
[bold]Upload Progress:[/bold] {upload_percent:.1f}% ({uploaded}/{total_files})

[bold]📁 Files:[/bold]
  ✅ Uploaded: {uploaded} | ⏭️ Skipped: {skipped} | ❌ Failed: {failed}

[bold]💾 Data:[/bold]
  📦 Uploaded: {bytes_gb:.2f} GB ({bytes_mb:.1f} MB)

[bold]🚀 Bandwidth Usage:[/bold]
  ⚡ Current: {current_speed:.2f} Mbps
  📊 Average: {avg_speed:.2f} Mbps
  🏆 Peak: {peak_speed:.2f} Mbps
  📈 Recent Avg: {recent_avg:.2f} Mbps

[bold]🔍 Verification:[/bold]
  ✅ Passed: {self.progress_data['verification_passed']} | ❌ Failed: {self.progress_data['verification_failed']} | ⏳ Pending: {self.progress_data['verification_pending']}
        """.strip()
        
        return Panel(progress_text, title="📈 Progress Overview", border_style="green")
    
    def _create_details_panel(self):
        """Create details panel with file analysis"""
        # File types
        file_types_text = "\n".join([
            f"  {ext}: {count}" for ext, count in 
            self.progress_data['file_types'].most_common(5)
        ]) if self.progress_data['file_types'] else "  No files processed"
        
        # File ages
        ages_text = "\n".join([
            f"  {age}: {count}" for age, count in 
            sorted(self.progress_data['file_ages'].items())
        ]) if self.progress_data['file_ages'] else "  No age data"
        
        # Recent uploads
        recent_text = "\n".join([
            f"  {upload['name'][:20]}... ({upload['size']/1024/1024:.1f}MB)" 
            for upload in self.progress_data['recent_uploads'][-3:]
        ]) if self.progress_data['recent_uploads'] else "  No recent uploads"
        
        details_text = f"""
[bold]📂 File Types:[/bold]
{file_types_text}

[bold]📅 File Ages:[/bold]
{ages_text}

[bold]🕒 Recent Uploads:[/bold]
{recent_text}
        """.strip()
        
        return Panel(details_text, title="📊 File Analysis", border_style="yellow")
    
    def _create_footer_panel(self):
        """Create footer panel with errors and warnings"""
        # Errors
        errors_text = "\n".join([
            f"  ❌ {error['file']}: {error['error'][:50]}..."
            for error in self.progress_data['errors'][-3:]
        ]) if self.progress_data['errors'] else "  ✅ No errors"
        
        # Warnings
        warnings_text = "\n".join([
            f"  ⚠️ {warning}" for warning in self.progress_data['warnings'][-3:]
        ]) if self.progress_data['warnings'] else "  ✅ No warnings"
        
        # Performance metrics
        avg_file_size = sum(self.progress_data['file_sizes']) / len(self.progress_data['file_sizes']) if self.progress_data['file_sizes'] else 0
        avg_size_mb = avg_file_size / (1024**2)
        
        footer_text = f"""
[bold]❌ Errors:[/bold]
{errors_text}

[bold]⚠️ Warnings:[/bold]
{warnings_text}

[bold]📊 Performance:[/bold]
  📏 Avg File Size: {avg_size_mb:.1f} MB
  🔄 Retries: {self.progress_data['performance_metrics']['retry_count']}
  ⚡ Concurrent: {self.progress_data['performance_metrics']['concurrent_uploads']}
        """.strip()
        
        return Panel(footer_text, title="🔍 Details & Errors", border_style="red")
    
    def _print_simple_header(self):
        """Print simple header for non-rich environments"""
        print("\n" + "="*80)
        print(f"🔄 S3 Sync Dashboard - {self.operation_name}")
        print("="*80)
    
    def _print_simple_progress(self):
        """Print simple progress for non-rich environments"""
        total_files = self.progress_data['total_files']
        processed = self.progress_data['files_processed']
        uploaded = self.progress_data['files_uploaded']
        skipped = self.progress_data['files_skipped']
        failed = self.progress_data['files_failed']
        
        progress_percent = (processed / total_files * 100) if total_files > 0 else 0
        bytes_gb = self.progress_data['bytes_uploaded'] / (1024**3)
        
        # Calculate recent bandwidth trend
        recent_speeds = [entry['speed'] for entry in self.progress_data['bandwidth_history'][-5:]]
        recent_avg = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0
        
        print(f"\r📊 Progress: {progress_percent:.1f}% | "
              f"📁 {processed}/{total_files} | "
              f"✅ {uploaded} | ⏭️ {skipped} | ❌ {failed} | "
              f"💾 {bytes_gb:.2f}GB | "
              f"⚡ {self.progress_data['upload_speed_mbps']:.1f}Mbps | "
              f"📊 {self.progress_data['average_speed_mbps']:.1f}Mbps | "
              f"🏆 {self.progress_data['peak_speed_mbps']:.1f}Mbps", end="")
    
    def _print_final_summary(self):
        """Print final summary when dashboard stops"""
        if not RICH_AVAILABLE:
            print()  # New line after progress updates
        
        duration = datetime.now() - self.start_time if self.start_time else timedelta(0)
        total_files = self.progress_data['total_files']
        uploaded = self.progress_data['files_uploaded']
        bytes_gb = self.progress_data['bytes_uploaded'] / (1024**3)
        
        print(f"\n📊 Final Summary:")
        print(f"  ⏱️  Duration: {str(duration).split('.')[0]}")
        print(f"  📁 Total Files: {total_files}")
        print(f"  ✅ Uploaded: {uploaded}")
        print(f"  💾 Data: {bytes_gb:.2f} GB")
        print(f"  🚀 Bandwidth Stats:")
        print(f"    📊 Average: {self.progress_data['average_speed_mbps']:.2f} Mbps")
        print(f"    🏆 Peak: {self.progress_data['peak_speed_mbps']:.2f} Mbps")
        print(f"    📈 Total Measurements: {len(self.progress_data['bandwidth_history'])}")
        print(f"  🔍 Verification: {self.progress_data['verification_passed']} passed, {self.progress_data['verification_failed']} failed")
    
    def set_total_files(self, total: int):
        """Set the total number of files to process"""
        with self.progress_lock:
            self.progress_data['total_files'] = total
    
    def increment_processed(self):
        """Increment processed files counter"""
        with self.progress_lock:
            self.progress_data['files_processed'] += 1
    
    def increment_uploaded(self, bytes_uploaded: int = 0):
        """Increment uploaded files counter"""
        with self.progress_lock:
            self.progress_data['files_uploaded'] += 1
            self.progress_data['bytes_uploaded'] += bytes_uploaded
    
    def increment_skipped(self):
        """Increment skipped files counter"""
        with self.progress_lock:
            self.progress_data['files_skipped'] += 1
    
    def increment_failed(self):
        """Increment failed files counter"""
        with self.progress_lock:
            self.progress_data['files_failed'] += 1
    
    def add_error(self, error: Exception, file_name: str = "Unknown"):
        """Add error to the dashboard"""
        with self.progress_lock:
            self.progress_data['errors'].append({
                'error': str(error),
                'time': datetime.now(),
                'file': file_name
            })
    
    def add_warning(self, message: str):
        """Add warning to the dashboard"""
        with self.progress_lock:
            self.progress_data['warnings'].append(message)
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary"""
        with self.progress_lock:
            return {
                'total_files': self.progress_data['total_files'],
                'files_processed': self.progress_data['files_processed'],
                'files_uploaded': self.progress_data['files_uploaded'],
                'files_skipped': self.progress_data['files_skipped'],
                'files_failed': self.progress_data['files_failed'],
                'bytes_uploaded': self.progress_data['bytes_uploaded'],
                'upload_speed_mbps': self.progress_data['upload_speed_mbps'],
                'average_speed_mbps': self.progress_data['average_speed_mbps'],
                'peak_speed_mbps': self.progress_data['peak_speed_mbps'],
                'bandwidth_measurements': len(self.progress_data['bandwidth_history']),
                'verification_passed': self.progress_data['verification_passed'],
                'verification_failed': self.progress_data['verification_failed'],
                'errors_count': len(self.progress_data['errors']),
                'warnings_count': len(self.progress_data['warnings'])
            }


def create_sync_dashboard(operation_name: str, config: Dict[str, Any] = None) -> SyncDashboard:
    """Create a sync dashboard instance"""
    return SyncDashboard(operation_name, config)


if __name__ == "__main__":
    # Example usage
    dashboard = SyncDashboard('test-sync')
    dashboard.start()
    
    # Simulate some progress
    dashboard.set_total_files(100)
    
    for i in range(10):
        dashboard.increment_processed()
        dashboard.increment_uploaded(1024*1024)  # 1MB
        dashboard.update_progress(
            file_info={'file_path': f'/path/to/file{i}.jpg', 'file_size': 1024*1024},
            upload_speed=5.5 + i*0.1,
            verification_status='passed' if i % 2 == 0 else 'pending'
        )
        time.sleep(1)
    
    dashboard.stop() 