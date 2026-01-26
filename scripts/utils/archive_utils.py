"""Archive utilities for creating compressed backups."""

from __future__ import annotations

import asyncio
import fnmatch
from datetime import datetime
from pathlib import Path

import zstandard as zstd


class ArchiveError(Exception):
    """Error during archive creation."""

    pass


def _should_exclude_path(
    path_str: str,
    root_dir_str: str,
    exclusion_patterns: list[str],
    ignore_exclusions: bool = False,
) -> bool:
    """Check if a path should be excluded from the archive.

    Args:
        path_str: Path to check
        root_dir_str: Root directory of the archive
        exclusion_patterns: List of glob patterns to exclude
        ignore_exclusions: If True, don't exclude anything

    Returns:
        True if the path should be excluded
    """
    if ignore_exclusions:
        return False

    path = Path(path_str)
    rel_path = path.relative_to(root_dir_str) if path.is_absolute() else path

    for pattern in exclusion_patterns:
        if fnmatch.fnmatch(str(rel_path), pattern):
            return True
        if fnmatch.fnmatch(rel_path.name, pattern):
            return True
        for part in rel_path.parts:
            if fnmatch.fnmatch(part, pattern):
                return True

    return False


async def create_archive(
    root_dir: Path,
    output_filename: str | None = None,
    exclusion_patterns: list[str] | None = None,
    ignore_exclusions: bool = False,
    output_dir: Path | None = None,
) -> Path:
    """Create a compressed tar.zst archive.

    Args:
        root_dir: Directory to archive
        output_filename: Custom output filename (without extension)
        exclusion_patterns: List of glob patterns to exclude
        ignore_exclusions: If True, include all files
        output_dir: Directory for output file (default: root_dir parent)

    Returns:
        Path to the created archive

    Raises:
        ArchiveError: If archive creation fails
    """
    if exclusion_patterns is None:
        exclusion_patterns = []

    root_dir = root_dir.resolve()
    if not root_dir.exists():
        raise ArchiveError(f"Source directory does not exist: {root_dir}")

    if output_dir is None:
        output_dir = root_dir.parent

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = output_filename or f"{root_dir.name}-{timestamp}"
    archive_path = output_dir / f"{base_name}.tar.zst"

    exclude_args = []
    for pattern in exclusion_patterns:
        exclude_args.extend(["--exclude", pattern])

    cmd = [
        "tar",
        "-cf",
        "-",
        *exclude_args,
        "-C",
        str(root_dir.parent),
        root_dir.name,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        tar_data, stderr = await proc.communicate()
    except FileNotFoundError:
        raise ArchiveError("tar command not found") from None

    if proc.returncode != 0:
        raise ArchiveError(f"tar failed: {stderr.decode()}")

    try:
        cctx = zstd.ZstdCompressor(level=3)
        compressed = cctx.compress(tar_data)
        archive_path.write_bytes(compressed)
    except Exception as e:
        raise ArchiveError(f"Archive creation failed: {e}") from e

    return archive_path
