"""
Path utilities for backup/restore operations.
Centralizes logic for finding project root and tools.
"""

import shutil
import sys

from ami.core.env import get_project_root

__all__ = ["get_project_root"]


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
