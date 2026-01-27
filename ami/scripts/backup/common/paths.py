"""
Path utilities for backup/restore operations.
Centralizes logic for finding project root and tools.
"""

import os
import shutil
import sys
from pathlib import Path


def _is_project_root_marker(path: Path) -> bool:
    """Check if a path contains project root markers."""
    if (path / "base").exists() and (path / "scripts").exists():
        return True
    return (path / "pyproject.toml").exists()


def _find_root_from_path(start: Path) -> Path | None:
    """Walk up from a path looking for project root markers."""
    current = start
    while current != current.parent:
        if _is_project_root_marker(current):
            return current
        current = current.parent
    return None


def get_project_root() -> Path:
    """
    Locate the project root directory.
    Look for 'base' directory or pyproject.toml as markers.
    """
    # Check environment variable first
    env_root = os.environ.get("AMI_PROJECT_ROOT")
    if env_root:
        return Path(env_root)

    # Try to find from current file location by walking up
    try:
        result = _find_root_from_path(Path(__file__).resolve())
        if result:
            return result
    except Exception:
        pass

    # Try to find from CWD
    try:
        result = _find_root_from_path(Path.cwd().resolve())
        if result:
            return result
    except Exception:
        pass

    msg = "project root not found"
    raise RuntimeError(msg)


def setup_sys_path() -> None:
    """Add project root to sys.path if not present."""
    root = get_project_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def find_gcloud() -> str | None:
    """Find gcloud CLI binary (local or system)."""
    root = get_project_root()

    # Check for local installation first
    local_gcloud = root / ".gcloud" / "google-cloud-sdk" / "bin" / "gcloud"

    if local_gcloud.exists():
        return str(local_gcloud)

    # Check system PATH
    system_gcloud = shutil.which("gcloud")
    if system_gcloud:
        return system_gcloud

    return None
