"""Environment setup for agent execution."""

import os
from pathlib import Path


class _ProjectRootCache:
    """Cache for project root to avoid repeated filesystem lookups."""

    _value: Path | None = None

    @classmethod
    def get(cls) -> Path | None:
        """Get cached project root."""
        return cls._value

    @classmethod
    def set(cls, path: Path) -> None:
        """Set cached project root."""
        cls._value = path


def get_project_root() -> Path:
    """Get the project root directory.

    Finds root by looking for pyproject.toml or .git marker files.
    Falls back to AMI_PROJECT_ROOT environment variable if set.
    """
    cached = _ProjectRootCache.get()
    if cached is not None:
        return cached

    # Check environment variable first
    env_root = os.environ.get("AMI_PROJECT_ROOT")
    if env_root:
        result = Path(env_root)
        _ProjectRootCache.set(result)
        return result

    # Walk up from this file looking for project markers
    current = Path(__file__).resolve()
    while current != current.parent:  # Stop at filesystem root
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            _ProjectRootCache.set(current)
            return current
        current = current.parent

    # No project markers found in any parent directory
    raise RuntimeError(
        "Could not determine project root. Set AMI_PROJECT_ROOT env var."
    )


def setup_agent_env() -> None:
    """Ensure agent execution environment is correct."""
    # Environment setup is now handled externally (e.g. via .bashrc or container env)
    pass


# Module-level constant for direct import
PROJECT_ROOT = get_project_root()
