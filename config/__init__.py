"""
Configuration Management Package

This package provides configuration management functionality for AWS S3 sync operations.
"""

from .config_manager import ConfigManager, ConfigError, create_config_manager

__all__ = ['ConfigManager', 'ConfigError', 'create_config_manager'] 