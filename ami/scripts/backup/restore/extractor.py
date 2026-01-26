"""Archive extraction module for backup restore operations.

Provides intelligent file handling for extracting from compressed archives.
Uses memory-efficient streaming approach to avoid segfaults that occurred
in the old system when extracting single files from large archives.
"""

import asyncio
import io
import subprocess
import tarfile
from pathlib import Path

import zstandard as zstd
from loguru import logger

from ami.scripts.backup.backup_exceptions import ArchiveError


async def extract_specific_paths(
    archive_path: Path, paths: list[Path] | None, dest: Path
) -> bool:
    """Extract specific paths from a tar.zst archive with intelligent file handling.

    Uses memory-efficient streaming to avoid segfaults from the old system.
    If paths is None, extracts all files.

    Implements the required behavior:
    1. Overwrites matching documents (files that exist in both current system and backup)
    2. Restores deleted files (files that exist in backup but not in current system)
    3. Preserves new files (files that exist in current system but not in backup)

    Args:
        archive_path: Path to the tar.zst archive
        paths: List of paths to extract from the archive, or None for all
        dest: Directory to extract files to

    Returns:
        True if extraction was successful, False otherwise
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _extract_specific_paths_sync, archive_path, paths, dest
    )


def _get_zstd_binary() -> Path:
    """Get path to zstd binary, preferring bootstrapped version."""
    # Find project root by looking for pyproject.toml or .git
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            zstd_bin = current / ".boot-linux" / "bin" / "zstd"
            if zstd_bin.exists():
                return zstd_bin
            break
        current = current.parent
    logger.warning("Bootstrapped zstd not found, using system zstd")
    return Path("zstd")


def _prune_child_paths(paths: list[Path]) -> list[Path]:
    """Remove child paths when parent is present to avoid tar errors."""
    unique_paths = sorted(set(paths))
    final_paths: list[Path] = []

    for p in unique_paths:
        is_child = False
        for parent in final_paths:
            try:
                p.relative_to(parent)
                if p != parent:
                    is_child = True
                    break
            except ValueError:
                continue

        if not is_child:
            final_paths.append(p)

    return final_paths


def _run_extraction_pipeline(zstd_cmd: list[str], tar_cmd: list[str]) -> None:
    """Run zstd | tar extraction pipeline and handle errors."""
    logger.info(f"Starting extraction pipe: {' '.join(zstd_cmd)} | {' '.join(tar_cmd)}")

    zstd_proc = subprocess.Popen(
        zstd_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    tar_proc = subprocess.Popen(
        tar_cmd,
        stdin=zstd_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if zstd_proc.stdout:
        zstd_proc.stdout.close()

    _t_out, t_err = tar_proc.communicate()
    _z_out, z_err = zstd_proc.communicate()

    if zstd_proc.returncode != 0:
        _raise_decompression_error(z_err.decode())

    if tar_proc.returncode != 0:
        err_msg = t_err.decode()
        if "error" in err_msg.lower() or "failed" in err_msg.lower():
            _raise_extraction_error(err_msg)
        else:
            logger.warning(f"Tar reported warnings: {err_msg}")


def _raise_decompression_error(msg: str) -> None:
    """Raise ArchiveError for decompression failure."""
    raise ArchiveError(f"Decompression failed: {msg}")


def _raise_extraction_error(msg: str) -> None:
    """Raise ArchiveError for extraction failure."""
    raise ArchiveError(f"Extraction failed: {msg}")


def _extract_specific_paths_sync(
    archive_path: Path, paths: list[Path] | None, dest: Path
) -> bool:
    """Synchronous implementation of extract_specific_paths to run in thread.

    Uses a direct OS pipe (zstd | tar) for maximum memory and disk efficiency.
    """
    if not archive_path.exists():
        raise ArchiveError(f"Archive file does not exist: {archive_path}")

    logger.info(f"Extracting from archive: {archive_path} via direct OS pipe")
    if paths:
        logger.info(f"Target paths: {[str(p) for p in paths]}")
    else:
        logger.info("Target: All files")

    try:
        dest.mkdir(parents=True, exist_ok=True)

        zstd_bin = _get_zstd_binary()
        zstd_cmd = [str(zstd_bin), "-dc", str(archive_path)]
        tar_cmd = ["tar", "-xf", "-", "-C", str(dest)]

        if paths:
            final_paths = _prune_child_paths(paths)
            logger.debug(f"Pruned paths from {len(paths)} to {len(final_paths)}")
            tar_cmd += [str(p) for p in final_paths]

        _run_extraction_pipeline(zstd_cmd, tar_cmd)

        logger.info(
            f"Successfully extracted {'all' if paths is None else len(paths)} items to {dest}"
        )

    except Exception as e:
        raise ArchiveError(f"Failed to extract from tar.zst archive: {e}") from e

    return True


async def list_archive_contents(archive_path: Path) -> list[str]:
    """List all contents of a tar.zst archive using memory-efficient streaming approach.

    Args:
        archive_path: Path to the tar.zst archive

    Returns:
        List of file/directory paths in the archive
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list_archive_contents_sync, archive_path)


def _list_archive_contents_sync(archive_path: Path) -> list[str]:
    """Synchronous implementation of list_archive_contents to run in thread.

    Uses streaming to avoid loading entire decompressed archive into memory.
    """
    if not archive_path.exists():
        raise ArchiveError(f"Archive file does not exist: {archive_path}")

    try:
        dctx = zstd.ZstdDecompressor()

        with (
            open(archive_path, "rb") as archive_file,
            dctx.stream_reader(archive_file) as reader,
            tarfile.open(fileobj=reader, mode="r|") as tar,
        ):
            contents = [member.name for member in tar]

    except Exception as e:
        raise ArchiveError(f"Failed to list archive contents: {e}") from e

    return contents


def _validate_tar_sample(tar_data: bytes) -> bool:
    """Validate tar data by attempting to open it."""
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_data[:1024] + b"...")):
            pass
    except (tarfile.TarError, Exception):
        return False
    else:
        return True


def _validate_full_tar(tar_data: bytes) -> bool:
    """Validate full tar data by reading all members."""
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_data), mode="r") as tar:
            tar.getmembers()
    except (tarfile.TarError, Exception):
        return False
    else:
        return True


def validate_archive(archive_path: Path) -> bool:
    """Validate that an archive is accessible and properly formatted.

    Args:
        archive_path: Path to the archive file

    Returns:
        True if archive is valid, False otherwise
    """
    if not archive_path.exists():
        logger.error(f"Archive file does not exist: {archive_path}")
        return False

    try:
        dctx = zstd.ZstdDecompressor()

        with open(archive_path, "rb") as fh:
            with dctx.stream_reader(fh) as initial_reader:
                initial_data = initial_reader.read(1024)

            if not initial_data:
                return True

            fh.seek(0)
            with dctx.stream_reader(fh) as sample_reader:
                tar_data = sample_reader.read(8192)
                if len(tar_data) > 0 and _validate_tar_sample(tar_data):
                    return True

            fh.seek(0)
            with dctx.stream_reader(fh) as full_reader:
                tar_data = full_reader.readall()
                return _validate_full_tar(tar_data)

    except Exception as e:
        logger.error(f"Failed to validate archive {archive_path}: {e}")
        return False
