"""Pytest configuration for unit tests.

Handles path setup so test files can import from scripts/ and other modules.
"""

import sys
from pathlib import Path


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


# Add project paths for imports
_root_dir = _find_project_root()
_scripts_dir = _root_dir / "scripts"

# Insert at beginning of path so our modules take precedence
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
