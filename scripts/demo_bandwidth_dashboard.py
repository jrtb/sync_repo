#!/usr/bin/env python3
"""
Demo script to showcase enhanced bandwidth tracking in the dashboard

This script demonstrates the new bandwidth tracking features including:
- Current bandwidth usage
- Peak bandwidth tracking
- Average bandwidth calculation
- Bandwidth history tracking
- Real-time status line updates

Usage:
    python scripts/demo_bandwidth_dashboard.py
"""

import time
import random
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.dashboard import SyncDashboard

def demo_bandwidth_tracking():
    """Demonstrate enhanced bandwidth tracking features"""
    print("🚀 Enhanced Bandwidth Tracking Demo")
    print("=" * 50)
    
    # Create dashboard
    dashboard = SyncDashboard("bandwidth-demo")
    dashboard.start()
    
    # Set total files for progress calculation
    dashboard.set_total_files(20)
    
    print("\n📊 Starting bandwidth tracking demo...")
    print("Watch the status line for real-time bandwidth updates!")
    print("\n" + "="*80)
    
    # Simulate file uploads with varying bandwidth
    for i in range(20):
        # Simulate realistic bandwidth variations
        base_speed = 8.0  # Base speed in Mbps
        variation = random.uniform(-3.0, 5.0)  # Random variation
        upload_speed = max(0.1, base_speed + variation)  # Ensure positive speed
        
        # Simulate file info
        file_info = {
            'file_path': f'/demo/file_{i:02d}.jpg',
            'file_size': random.randint(1024*1024, 10*1024*1024),  # 1-10MB
            'file_name': f'file_{i:02d}.jpg'
        }
        
        # Update dashboard with progress
        dashboard.increment_processed()
        dashboard.increment_uploaded(file_info['file_size'])
        dashboard.update_progress(
            file_info=file_info,
            upload_speed=upload_speed,
            verification_status='passed'
        )
        
        # Pause to show real-time updates
        time.sleep(0.5)
    
    # Stop dashboard and show final summary
    dashboard.stop()
    
    print("\n" + "="*80)
    print("📊 Final Bandwidth Statistics:")
    
    # Get final summary
    summary = dashboard.get_progress_summary()
    
    print(f"  📈 Total Measurements: {summary['bandwidth_measurements']}")
    print(f"  ⚡ Current Speed: {summary['upload_speed_mbps']:.2f} Mbps")
    print(f"  📊 Average Speed: {summary['average_speed_mbps']:.2f} Mbps")
    print(f"  🏆 Peak Speed: {summary['peak_speed_mbps']:.2f} Mbps")
    print(f"  💾 Data Uploaded: {summary['bytes_uploaded'] / (1024**3):.2f} GB")
    print(f"  📁 Files Processed: {summary['files_uploaded']}")
    
    # Show bandwidth history analysis
    history = dashboard.progress_data['bandwidth_history']
    if history:
        speeds = [entry['speed'] for entry in history]
        print(f"\n📈 Bandwidth Analysis:")
        print(f"  📊 Min Speed: {min(speeds):.2f} Mbps")
        print(f"  📊 Max Speed: {max(speeds):.2f} Mbps")
        print(f"  📊 Median Speed: {sorted(speeds)[len(speeds)//2]:.2f} Mbps")
        
        # Show recent trend
        recent_speeds = speeds[-5:]
        recent_avg = sum(recent_speeds) / len(recent_speeds)
        print(f"  📈 Recent 5 Avg: {recent_avg:.2f} Mbps")
    
    print("\n✅ Demo completed! Enhanced bandwidth tracking is working.")

if __name__ == "__main__":
    demo_bandwidth_tracking() 