"""
Configuration utilities for ami-agents package.

This module provides utilities for accessing shared configuration files.
"""

from pathlib import Path

from ami.core.env import get_project_root


def get_config_path(config_name: str) -> Path:
    """
    Get the path to a shared configuration file.

    Args:
        config_name: Name of the configuration file (e.g., "ruff.toml", "mypy.toml")

    Returns:
        Path to the configuration file
    """
    return get_project_root() / "res" / "config" / config_name


def get_vendor_config_path(config_name: str) -> Path:
    """
    Get the path to a vendor-specific configuration file.

    Args:
        config_name: Name of the vendor configuration file (e.g., "sources-cuda.toml")

    Returns:
        Path to the vendor configuration file
    """
    return get_project_root() / "res" / "config" / "vendor" / config_name
