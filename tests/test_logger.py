#!/usr/bin/env python3
"""
Tests for the SyncLogger structured logging module
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import logging
import json
import sys
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from logger import SyncLogger

def test_log_sync_start_and_complete(tmp_path):
    logger = SyncLogger("test-operation", config={})
    with patch.object(logger, 'logger') as mock_logger:
        logger.log_sync_start("test-bucket", "/tmp/test", dry_run=True)
        assert mock_logger.info.called
        logger.log_sync_complete({
            'files_uploaded': 2,
            'files_skipped': 1,
            'files_failed': 0,
            'bytes_uploaded': 1234,
            'retries_attempted': 1
        })
        assert mock_logger.log.called or mock_logger.info.called

def test_log_file_upload_and_skip(tmp_path):
    logger = SyncLogger("test-operation", config={})
    with patch.object(logger, 'logger') as mock_logger:
        logger.log_file_upload(Path("/tmp/file.txt"), "file.txt", 100, True, retry_count=0)
        assert mock_logger.log.called
        logger.log_file_upload(Path("/tmp/file.txt"), "file.txt", 100, False, retry_count=2, error="fail")
        assert mock_logger.log.called
        logger.log_file_skip(Path("/tmp/file.txt"), "file.txt", reason="excluded")
        assert mock_logger.info.called

def test_log_verification_result(tmp_path):
    logger = SyncLogger("test-operation", config={})
    with patch.object(logger, 'logger') as mock_logger:
        logger.log_verification_result(Path("/tmp/file.txt"), "file.txt", True)
        assert mock_logger.log.called
        logger.log_verification_result(Path("/tmp/file.txt"), "file.txt", False, details="hash mismatch")
        assert mock_logger.log.called

def test_cloudwatch_logging(tmp_path):
    config = {'logging': {'cloudwatch_enabled': True, 'log_group_name': 'test-group'}}
    logger = SyncLogger("test-operation", config=config)
    with patch.object(logger, '_log_to_cloudwatch') as mock_cw:
        logger.log_sync_start("bucket", "/tmp", dry_run=False)
        assert mock_cw.called
        logger.log_file_upload(Path("/tmp/file.txt"), "file.txt", 100, True)
        assert mock_cw.called
        logger.log_sync_complete({'files_uploaded': 1, 'files_skipped': 0, 'files_failed': 0, 'bytes_uploaded': 100, 'retries_attempted': 0})
        assert mock_cw.called