# Dynamic Dashboard Guide

## What This Does
A comprehensive real-time dashboard for S3 sync operations that displays rich progress information including upload speed, verification status, file types, age analysis, and performance metrics without screen scrolling. Provides both rich terminal display (with `rich` library) and fallback simple display.

## AWS Concepts Covered
- **Real-time Monitoring** - Live progress tracking and metrics
- **Performance Analytics** - Upload speed, throughput, and efficiency measurement
- **File Metadata Analysis** - File types, sizes, and age categorization
- **Operational Dashboards** - Visual monitoring and reporting
- **Error Tracking** - Real-time error detection and reporting
- **Progress Visualization** - Dynamic updates without screen scrolling

## Prerequisites
- Python 3.8+ with required dependencies
- `rich` library for enhanced display (optional but recommended)
- AWS credentials configured for sync operations

## Quick Start

### 1. Basic Usage
```python
from scripts.dashboard import SyncDashboard

# Create dashboard
dashboard = SyncDashboard('my-sync-operation')

# Start dashboard
dashboard.start()

# Set total files
dashboard.set_total_files(100)

# Update progress
dashboard.increment_processed()
dashboard.increment_uploaded(1024*1024)  # 1MB
dashboard.update_progress(
    file_info={'file_path': '/path/to/file.jpg', 'file_size': 1024*1024},
    upload_speed=5.5,
    verification_status='passed'
)

# Stop dashboard
dashboard.stop()
```

### 2. Integration with Sync Script
The dashboard is automatically integrated into the sync script when available:
```bash
# Run sync with dashboard
python scripts/sync.py --local-path ./photos --bucket my-bucket

# Demo the dashboard
python scripts/demo_dashboard.py
```

## Dashboard Features

### Real-time Progress Tracking
- **Overall Progress**: Percentage completion and file counts
- **Upload Progress**: Files uploaded vs total files
- **Data Transfer**: Bytes uploaded in GB/MB with speed metrics
- **Verification Status**: Passed, failed, and pending verification counts

### File Analysis
- **File Types**: Distribution of file extensions (.jpg, .png, .mp4, etc.)
- **File Ages**: Categorization by age (Today, This Week, This Month, etc.)
- **Recent Uploads**: Last 10 uploaded files with sizes
- **File Sizes**: Average file size and size distribution

### Performance Metrics
- **Upload Speed**: Current and average upload speed in Mbps
- **Throughput**: Data transfer rate and efficiency
- **Error Rate**: Failed uploads and error tracking
- **Retry Count**: Number of retry attempts

### Error and Warning Tracking
- **Real-time Errors**: Live error display with file context
- **Warning Messages**: Performance and configuration warnings
- **Error History**: Recent errors with timestamps and file names

## Configuration

### Dashboard Configuration
```json
{
  "dashboard": {
    "enabled": true,
    "refresh_rate": 2,
    "max_recent_uploads": 10
  }
}
```

### Rich Display Features
When the `rich` library is available, the dashboard provides:
- **Multi-panel Layout**: Header, progress, details, and footer sections
- **Color-coded Information**: Different colors for different data types
- **Real-time Updates**: Live refresh without screen clearing
- **Professional Appearance**: Clean, organized display

### Fallback Display
When `rich` is not available, provides:
- **Simple Progress**: Basic progress line with key metrics
- **Compatibility**: Works on all terminal types
- **Essential Information**: Core progress data without advanced formatting

## API Reference

### Core Methods
```python
# Dashboard lifecycle
dashboard.start()                    # Start dashboard display
dashboard.stop()                     # Stop dashboard display

# Progress tracking
dashboard.set_total_files(count)     # Set total files to process
dashboard.increment_processed()      # Increment processed counter
dashboard.increment_uploaded(bytes)  # Increment uploaded with bytes
dashboard.increment_skipped()        # Increment skipped counter
dashboard.increment_failed()         # Increment failed counter

# Progress updates
dashboard.update_progress(
    file_info=dict,                 # File information
    upload_speed=float,             # Upload speed in Mbps
    verification_status=str,         # 'passed', 'failed', 'pending'
    error=Exception                 # Error object
)

# Error and warning tracking
dashboard.add_error(error, file_name)
dashboard.add_warning(message)

# Data retrieval
summary = dashboard.get_progress_summary()
```

### File Information Format
```python
file_info = {
    'file_path': '/path/to/file.jpg',    # Full file path
    'file_size': 1024*1024,             # File size in bytes
    'file_name': 'file.jpg'              # File name
}
```

## Testing

### Run Dashboard Tests
```bash
# Run all dashboard tests
python -m pytest tests/test_dashboard.py -v

# Run specific test categories
python -m pytest tests/test_dashboard.py::TestSyncDashboard::test_dashboard_initialization -v
```

### Demo the Dashboard
```bash
# Run the interactive demo
python scripts/demo_dashboard.py
```

## Integration with Sync Script

### Automatic Integration
The dashboard is automatically integrated into the sync script:
1. **Dashboard Creation**: Created during sync initialization
2. **Progress Tracking**: Updates during file uploads
3. **Error Handling**: Captures and displays errors
4. **Performance Monitoring**: Tracks upload speeds and metrics

### Manual Integration
For custom sync operations:
```python
from scripts.dashboard import SyncDashboard
from scripts.sync import S3Sync

# Create sync instance
sync = S3Sync(...)

# Access dashboard
dashboard = sync.dashboard

# Custom progress updates
dashboard.update_progress(
    file_info={'file_path': 'custom.jpg', 'file_size': 1024},
    upload_speed=10.5,
    verification_status='passed'
)
```

## Performance Considerations

### Memory Usage
- **Recent Uploads**: Limited to last 10 files by default
- **Error History**: Unlimited but can be configured
- **File Analysis**: Efficient counters and categorization

### Display Performance
- **Rich Library**: Hardware-accelerated rendering when available
- **Simple Fallback**: Minimal CPU usage for basic display
- **Update Frequency**: Configurable refresh rate (default: 2Hz)

### Thread Safety
- **Concurrent Access**: Thread-safe operations for multi-threaded sync
- **Lock Protection**: All data updates protected by locks
- **Atomic Operations**: Progress updates are atomic

## Troubleshooting

### Common Issues

#### Dashboard Not Displaying
```bash
# Check if rich is installed
pip install rich

# Verify dashboard is enabled in config
# Check config/dashboard.json or sync config
```

#### Performance Issues
```python
# Reduce refresh rate for better performance
config = {'dashboard': {'refresh_rate': 1}}  # 1Hz instead of 2Hz
```

#### Display Problems
```python
# Force simple display mode
# Set RICH_AVAILABLE = False in dashboard.py
# Or uninstall rich: pip uninstall rich
```

### Debug Information
```python
# Get current progress summary
summary = dashboard.get_progress_summary()
print(f"Files processed: {summary['files_processed']}")
print(f"Upload speed: {summary['upload_speed_mbps']} Mbps")
```

## Security Notes
- **File Paths**: Dashboard displays file paths - ensure no sensitive information
- **Error Messages**: Error details are logged - review for sensitive data
- **Performance Data**: Upload speeds and metrics are tracked for analysis

## Best Practices
1. **Use Rich Library**: Install `rich` for best display experience
2. **Configure Refresh Rate**: Adjust based on system performance
3. **Monitor Memory**: Large file sets may require memory monitoring
4. **Error Handling**: Always handle dashboard exceptions gracefully
5. **Testing**: Test dashboard with various file types and sizes

## Educational Value
This dashboard implementation demonstrates:
- **Real-time Monitoring**: Live progress tracking without blocking
- **Performance Analytics**: Upload speed and efficiency measurement
- **File Metadata Analysis**: Understanding file characteristics
- **Error Handling**: Comprehensive error tracking and reporting
- **User Experience**: Professional progress visualization
- **Thread Safety**: Concurrent operation handling
- **Fallback Design**: Graceful degradation when dependencies unavailable

---

**Last Updated**: August 1, 2025  
**Purpose**: Dynamic dashboard documentation for S3 sync operations  
**Status**: Active 