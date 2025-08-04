#!/usr/bin/env python3
"""
Debug script to identify sync issues

This script helps diagnose why the sync tool is detecting files as needing
upload when they haven't actually changed.
"""

import argparse
import boto3
from botocore.exceptions import ClientError
import hashlib
import json
import os
import sys
from pathlib import Path
from datetime import datetime

def calculate_file_hash(file_path, algorithm='md5'):
    """Calculate hash of a file"""
    hash_obj = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()

def get_s3_object_metadata(s3_client, bucket_name, key):
    """Get metadata of S3 object for comparison"""
    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=key)
        return {
            'etag': response['ETag'].strip('"'),  # Remove quotes
            'size': response['ContentLength'],
            'last_modified': response['LastModified']
        }
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None  # File doesn't exist
        else:
            print(f"Error getting S3 metadata for {key}: {e}")
            return None
    except Exception as e:
        print(f"Unexpected error getting S3 metadata for {key}: {e}")
        return None

def calculate_s3_key(file_path, local_path):
    """Calculate S3 key for a file"""
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    try:
        relative_path = file_path.relative_to(local_path)
        s3_key = str(relative_path)
        s3_key = s3_key.replace('\\', '/')
        s3_key = s3_key.lstrip('/')
        return s3_key
    except ValueError:
        # Fallback for absolute paths
        try:
            abs_file_path = file_path.resolve()
            abs_local_path = local_path.resolve()
            relative_path = abs_file_path.relative_to(abs_local_path)
            s3_key = str(relative_path)
            s3_key = s3_key.replace('\\', '/')
            s3_key = s3_key.lstrip('/')
            return s3_key
        except ValueError:
            # Final fallback
            abs_file_path = file_path.resolve()
            path_parts = abs_file_path.parts
            try:
                astro_index = path_parts.index('astro')
                relevant_parts = path_parts[astro_index + 1:]
                s3_key = '/'.join(relevant_parts)
            except ValueError:
                if len(path_parts) >= 3:
                    s3_key = '/'.join(path_parts[-3:])
                else:
                    s3_key = file_path.name
            
            s3_key = s3_key.replace('\\', '/')
            s3_key = s3_key.lstrip('/')
            return s3_key

def debug_file_comparison(local_file, s3_key, s3_client, bucket_name):
    """Debug comparison for a single file"""
    print(f"\n=== Debugging file: {local_file} ===")
    print(f"S3 key: {s3_key}")
    
    # Check if local file exists
    if not local_file.exists():
        print("❌ Local file does not exist")
        return False
    
    # Get local file info
    local_size = local_file.stat().st_size
    local_md5 = calculate_file_hash(local_file, 'md5')
    print(f"Local size: {local_size}")
    print(f"Local MD5: {local_md5}")
    
    # Get S3 metadata
    s3_metadata = get_s3_object_metadata(s3_client, bucket_name, s3_key)
    if not s3_metadata:
        print("❌ File not found in S3 - needs upload")
        return True
    
    print(f"S3 size: {s3_metadata['size']}")
    print(f"S3 ETag: {s3_metadata['etag']}")
    print(f"S3 last modified: {s3_metadata['last_modified']}")
    
    # Compare sizes
    if local_size != s3_metadata['size']:
        print(f"❌ Size mismatch: local={local_size}, S3={s3_metadata['size']}")
        return True
    
    # For multipart uploads, S3 ETags are not reliable for hash comparison
    # Check if this is a multipart upload (ETag contains "-")
    s3_etag = s3_metadata['etag']
    if '-' in s3_etag:
        # This is a multipart upload - we can't reliably compare hashes
        # because S3 ETags for multipart uploads are not the same as file hashes
        # We'll rely on size comparison and upload verification
        print("✅ File matches S3 (multipart upload - size comparison only)")
        return False
    else:
        # This is a simple upload - we can compare MD5 hashes
        if local_md5 and local_md5 != s3_etag:
            print(f"❌ Hash mismatch: local={local_md5}, S3={s3_etag}")
            return True
    
    print("✅ File matches S3 - no upload needed")
    return False

def main():
    parser = argparse.ArgumentParser(description='Debug sync issues')
    parser.add_argument('--local-path', required=True, help='Local path to sync')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--profile', default='s3-sync-user', help='AWS profile to use')
    parser.add_argument('--sample-size', type=int, default=5, help='Number of files to sample')
    parser.add_argument('--test-file', help='Test a specific file path')
    
    args = parser.parse_args()
    
    # Setup AWS client
    session = boto3.Session(profile_name=args.profile)
    s3_client = session.client('s3')
    
    local_path = Path(args.local_path)
    if not local_path.exists():
        print(f"❌ Local path does not exist: {local_path}")
        return 1
    
    if args.test_file:
        # Test a specific file
        test_file = Path(args.test_file)
        if not test_file.exists():
            print(f"❌ Test file does not exist: {test_file}")
            return 1
        
        s3_key = calculate_s3_key(test_file, local_path)
        debug_file_comparison(test_file, s3_key, s3_client, args.bucket)
        return 0
    
    # Get sample of files
    all_files = []
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            all_files.append(file_path)
    
    print(f"Found {len(all_files)} total files")
    
    # Sample files for debugging
    sample_files = all_files[:args.sample_size]
    print(f"Debugging {len(sample_files)} sample files...")
    
    needs_upload_count = 0
    for file_path in sample_files:
        s3_key = calculate_s3_key(file_path, local_path)
        if debug_file_comparison(file_path, s3_key, s3_client, args.bucket):
            needs_upload_count += 1
    
    print(f"\n=== Summary ===")
    print(f"Sample size: {len(sample_files)}")
    print(f"Files needing upload: {needs_upload_count}")
    print(f"Files matching S3: {len(sample_files) - needs_upload_count}")
    
    if needs_upload_count == len(sample_files):
        print("\n⚠️  ALL sample files need upload - this suggests a systematic issue!")
        print("Possible causes:")
        print("1. S3 key calculation is wrong")
        print("2. S3 metadata retrieval is failing")
        print("3. Hash comparison is broken")
        print("4. Files were uploaded with different keys")
    elif needs_upload_count > 0:
        print(f"\n⚠️  {needs_upload_count}/{len(sample_files)} files need upload")
    else:
        print("\n✅ All sample files match S3 - sync logic appears correct")

if __name__ == '__main__':
    sys.exit(main()) 