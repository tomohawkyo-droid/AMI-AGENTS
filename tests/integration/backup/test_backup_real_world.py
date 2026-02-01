"""End-to-End integration test for backup creation.

Tests archiver at scale using real codebase files (.venv).
No synthetic file generation - uses existing directory structure.

Note: Path setup is handled by tests/conftest.py.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from ami.scripts.backup.create import archiver


# Use .venv as the test target - it has thousands of real files
# Walk up from test file to find repo root (contains pyproject.toml)
def _find_repo_root() -> Path:
    """Find repository root by looking for pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    msg = "Could not find repository root"
    raise RuntimeError(msg)


VENV_DIR = _find_repo_root() / ".venv"


@pytest.mark.asyncio
async def test_backup_at_scale() -> None:
    """
    Test archiver at scale using real .venv directory.

    .venv typically contains 50k+ files across deep directory structures,
    symlinks, and various file types - perfect for stress testing.
    """
    if not VENV_DIR.exists():
        pytest.skip(".venv not found - run in development environment")

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)

        archive_path = await archiver.create_zip_archive(
            VENV_DIR, output_dir=output_dir, ignore_exclusions=False
        )

        assert archive_path.exists()
        assert archive_path.stat().st_size > 0


if __name__ == "__main__":
    asyncio.run(test_backup_at_scale())
