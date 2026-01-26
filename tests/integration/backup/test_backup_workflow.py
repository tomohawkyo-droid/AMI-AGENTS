"""Integration test for the backup creation workflow.

REPRODUCTION ATTEMPT: Runs against the REAL project root to trigger the scale-based segfault.

Note: Path setup is handled by tests/conftest.py.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from ami.scripts.backup.create import archiver


@pytest.mark.asyncio
async def test_reproduce_real_world_segfault():
    """
    Test the full backup creation process against the ACTUAL project root.
    This is the only way to reproduce the segfault if it's caused by
    specific files or the sheer scale (280k+ files) of the repo.
    """
    # Use the actual project root
    real_root = Path.cwd()

    print(f"\n[Reproduction] Running backup against real root: {real_root}")

    # Create a temp directory for the output to avoid polluting the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)

        print("[Reproduction] Starting create_zip_archive...")
        try:
            # We use the real archiver logic
            # This will scan 280k+ files and attempt to tar them
            archive_path = await archiver.create_zip_archive(
                real_root,
                output_dir=output_dir,
                ignore_exclusions=False,  # Respect exclusions like real run
            )

            print(f"[Reproduction] Archive created successfully at: {archive_path}")
            print(f"[Reproduction] Archive size: {archive_path.stat().st_size} bytes")

        except Exception as e:
            print(f"[Reproduction] Failed with error: {e}")
            raise


if __name__ == "__main__":
    # Allow running directly
    asyncio.run(test_reproduce_real_world_segfault())
