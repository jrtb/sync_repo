#!/usr/bin/env python3
"""
Dashboard Demo Script

This script demonstrates the dynamic dashboard functionality by simulating
a realistic sync operation with various file types, upload speeds, and scenarios.

Usage:
    python scripts/demo_dashboard.py
"""

import time
import random
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add the scripts directory to the path
import sys
sys.path.append(str(Path(__file__).parent))

from dashboard import SyncDashboard


def create_demo_files():
    """Create some demo files for testing"""
    demo_files = []
    
    # Create temporary files with different types and sizes
    file_types = ['.jpg', '.png', '.mp4', '.mov', '.raw', '.cr2', '.nef']
    file_sizes = [1024*1024, 2048*1024, 5120*1024, 10240*1024, 20480*1024]  # 1MB to 20MB
    
    for i in range(20):
        # Create a temporary file
        suffix = random.choice(file_types)
        size = random.choice(file_sizes)
        
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            # Write some data to make the file the desired size
            tmp_file.write(b'x' * size)
            tmp_file_path = Path(tmp_file.name)
        
        # Set file modification time to simulate different ages
        age_days = random.randint(0, 365)
        mod_time = datetime.now() - timedelta(days=age_days)
        os.utime(tmp_file_path, (mod_time.timestamp(), mod_time.timestamp()))
        
        demo_files.append({
            'path': tmp_file_path,
            'size': size,
            'type': suffix,
            'age_days': age_days
        })
    
    return demo_files


def simulate_sync_operation():
    """Simulate a realistic sync operation with the dashboard"""
    print("🚀 Starting S3 Sync Dashboard Demo")
    print("=" * 50)
    
    # Create demo files
    print("📁 Creating demo files...")
    demo_files = create_demo_files()
    print(f"✅ Created {len(demo_files)} demo files")
    
    # Initialize dashboard
    config = {
        'dashboard': {
            'enabled': True,
            'refresh_rate': 2
        }
    }
    dashboard = SyncDashboard('demo-sync', config)
    
    try:
        # Start dashboard
        dashboard.start()
        
        # Set total files
        dashboard.set_total_files(len(demo_files))
        
        print("\n🔄 Simulating sync operation...")
        print("Press Ctrl+C to stop the demo\n")
        
        # Simulate file processing
        for i, file_info in enumerate(demo_files):
            # Simulate processing time
            time.sleep(random.uniform(0.5, 2.0))
            
            # Simulate upload speed (varies between 2-15 Mbps)
            upload_speed = random.uniform(2.0, 15.0)
            
            # Simulate verification status (mostly passed, some failed)
            verification_status = 'passed' if random.random() > 0.1 else 'failed'
            
            # Simulate occasional errors
            error = None
            if random.random() < 0.05:  # 5% error rate
                error = Exception(f"Network timeout for {file_info['path'].name}")
            
            # Update dashboard
            dashboard.increment_processed()
            
            if error:
                dashboard.increment_failed()
                dashboard.add_error(error, file_info['path'].name)
            elif verification_status == 'failed':
                dashboard.increment_failed()
            else:
                dashboard.increment_uploaded(file_info['size'])
            
            # Update progress with file info
            dashboard.update_progress(
                file_info={
                    'file_path': str(file_info['path']),
                    'file_size': file_info['size'],
                    'file_name': file_info['path'].name
                },
                upload_speed=upload_speed,
                verification_status=verification_status,
                error=error
            )
            
            # Add some warnings occasionally
            if random.random() < 0.1:  # 10% warning rate
                dashboard.add_warning(f"Large file detected: {file_info['path'].name}")
        
        # Keep dashboard running for a moment to show final state
        time.sleep(3)
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    finally:
        # Stop dashboard
        dashboard.stop()
        
        # Cleanup demo files
        print("\n🧹 Cleaning up demo files...")
        for file_info in demo_files:
            try:
                os.unlink(file_info['path'])
            except OSError:
                pass
        print("✅ Demo files cleaned up")


def main():
    """Main demo function"""
    try:
        simulate_sync_operation()
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return 1
    
    print("\n🎉 Demo completed successfully!")
    return 0


if __name__ == "__main__":
    exit(main()) 