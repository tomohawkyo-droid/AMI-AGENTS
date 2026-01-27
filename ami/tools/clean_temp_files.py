#!/usr/bin/env python3
"""
Clean temporary files and directories.

Usage:
  clean_temp_files.py [--dry-run]

Options:
  --dry-run   List files and directories to be cleaned without deleting them.
"""

import argparse
import os
import shutil
from pathlib import Path

from ami.cli_components.confirmation_dialog import confirm

# Size conversion constant
BYTES_PER_UNIT = 1024.0


def get_size(path: Path) -> int:
    """Calculate the size of a file or directory in bytes safely."""
    total_size = 0
    try:
        if path.is_file():
            return path.stat().st_size

        # Iterative walk using stack to avoid recursion depth issues
        stack = [path]
        while stack:
            current_dir = stack.pop()
            try:
                with os.scandir(current_dir) as it:
                    for entry in it:
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_file():
                                total_size += entry.stat().st_size
                            elif entry.is_dir():
                                stack.append(Path(entry.path))
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception:
        pass
    return total_size


def format_size(size: int) -> str:
    """Format size in bytes to human-readable string."""
    size_float: float = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_float < BYTES_PER_UNIT:
            return f"{size_float:.2f} {unit}"
        size_float /= BYTES_PER_UNIT
    return f"{size_float:.2f} TB"


def is_subpath(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    else:
        return True


# Size threshold for large files (100MB)
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024

# File extensions to clean
TEMP_FILE_EXTENSIONS = (".pyc", ".log", ".tar", ".tar.gz", ".tar.zst", ".zip")

# Directories to skip during scanning
SKIP_DIRS = {".git", ".venv", "node_modules"}


def _is_temp_file(name: str) -> bool:
    """Check if filename matches temporary file patterns."""
    return any(name.endswith(ext) for ext in TEMP_FILE_EXTENSIONS)


def _is_excluded_path(path_str: str, exclude_paths: set[str]) -> bool:
    """Check if path is in or under any excluded path."""
    return any(
        path_str == ex or path_str.startswith(ex + os.sep) for ex in exclude_paths
    )


def _handle_directory_entry(
    entry: os.DirEntry[str],
    path: Path,
    exclude_paths: set[str],
    found_files: list[Path],
    stack: list[Path],
) -> None:
    """Handle a directory entry during scanning."""
    if entry.name in SKIP_DIRS:
        return

    try:
        if str(path.resolve()) in exclude_paths:
            return
    except Exception:
        pass

    if entry.name == "__pycache__":
        found_files.append(path)
    else:
        stack.append(path)


def _handle_file_entry(
    entry: os.DirEntry[str],
    path: Path,
    found_files: list[Path],
    large_files: list[Path],
) -> None:
    """Handle a file entry during scanning."""
    if _is_temp_file(entry.name):
        found_files.append(path)
        return

    try:
        if entry.stat().st_size > LARGE_FILE_THRESHOLD:
            large_files.append(path)
    except Exception:
        pass


def _process_directory_entry(
    entry: os.DirEntry[str],
    exclude_paths: set[str],
    found_files: list[Path],
    large_files: list[Path],
    stack: list[Path],
) -> None:
    """Process a single directory entry during scanning."""
    if entry.is_symlink():
        return

    path = Path(entry.path)

    if entry.is_dir():
        _handle_directory_entry(entry, path, exclude_paths, found_files, stack)
    elif entry.is_file():
        _handle_file_entry(entry, path, found_files, large_files)


def scan_directory_robust(
    root_dir: Path,
    exclude_dirs: set[Path],
    patterns: list[str],
) -> tuple[list[Path], list[Path]]:
    """
    Robustly scan directory for files matching patterns and large files.
    Skips exclude_dirs.
    Returns (found_files, large_files).
    """
    found_files: list[Path] = []
    large_files: list[Path] = []

    exclude_paths = {str(p.resolve()) for p in exclude_dirs if p.exists()}

    stack = [root_dir]
    while stack:
        current_dir = stack.pop()

        try:
            curr_resolve = str(current_dir.resolve())
            if _is_excluded_path(curr_resolve, exclude_paths):
                continue
        except Exception:
            continue

        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    try:
                        _process_directory_entry(
                            entry, exclude_paths, found_files, large_files, stack
                        )
                    except Exception:
                        continue
        except Exception:
            continue

    return found_files, large_files


def _get_repo_temp_dirs(repo_root: Path) -> list[Path]:
    """Get list of repo-local temporary directories."""
    return [
        repo_root / "tmp",
        repo_root / "test_logs",
        repo_root / ".pytest_cache",
        repo_root / ".ruff_cache",
        repo_root / ".mypy_cache",
        repo_root / "htmlcov",
        repo_root / "dist",
        repo_root / "build",
        repo_root / "_restored",
    ]


def _get_critical_dirs(repo_root: Path) -> list[Path]:
    """Get list of critical directories that should never be cleaned."""
    return [
        repo_root / "logs",
        repo_root / ".git",
        repo_root / ".venv",
        repo_root / "node_modules",
    ]


def _print_repo_temp_dirs(
    repo_temp_dirs: list[Path], exclude_scan_dirs: set[Path]
) -> int:
    """Print and calculate size of repo temp directories. Returns total size."""
    total = 0
    for d in repo_temp_dirs:
        if d.exists():
            exclude_scan_dirs.add(d)
            size = get_size(d)
            total += size
            print(f"[DIR]  {d} ({format_size(size)})")
    return total


def _print_found_files(found_files: list[Path], repo_root: Path) -> int:
    """Print found files and return total size."""
    total = 0
    for f in found_files:
        size = get_size(f)
        total += size
        type_str = "[DIR]" if f.is_dir() else "[FILE]"
        print(f"{type_str} {f.relative_to(repo_root)} ({format_size(size)})")
    return total


def _print_large_files(large_files: list[Path], repo_root: Path) -> None:
    """Print large files found."""
    for f in large_files:
        size = get_size(f)
        print(f"[LARGE] {f.relative_to(repo_root)} ({format_size(size)})")


def _scan_system_tmp(system_tmp: Path) -> None:
    """Scan and print system tmp directory contents."""
    try:
        tmp_items: list[tuple[Path, int]] = []
        user = os.environ.get("USER", "ami")
        with os.scandir(system_tmp) as it:
            for entry in it:
                try:
                    path = Path(entry.path)
                    if path.owner() == user:
                        tmp_items.append((path, get_size(path)))
                except Exception:
                    pass

        tmp_items.sort(key=lambda x: x[1], reverse=True)
        for item, size in tmp_items[:20]:
            print(f"[TMP]  {item} ({format_size(size)})")
    except Exception as e:
        print(f"Error scanning /tmp: {e}")


def _delete_items(items: list[Path]) -> tuple[int, int]:
    """Delete items and return (deleted_count, errors_count)."""
    deleted_count = 0
    errors_count = 0

    for item in items:
        try:
            if not item.exists():
                continue
            if item.is_dir():
                shutil.rmtree(item)
                print(f"[DELETED DIR]  {item}")
            else:
                item.unlink()
                print(f"[DELETED FILE] {item}")
            deleted_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to delete {item}: {e}")
            errors_count += 1

    return deleted_count, errors_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean temporary files and directories."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List items to be cleaned without deleting.",
    )
    args = parser.parse_args()

    repo_root = Path.cwd()
    system_tmp = Path("/tmp")

    repo_temp_dirs = _get_repo_temp_dirs(repo_root)
    critical_dirs = _get_critical_dirs(repo_root)

    print("Scanning for temporary files and directories...\n")

    print(f"--- Repository Temporary Directories ({repo_root}) ---")
    exclude_scan_dirs = set(critical_dirs)
    total_freed = _print_repo_temp_dirs(repo_temp_dirs, exclude_scan_dirs)

    print("\n--- Scanning Repository Files (skipping temp & critical dirs) ---")
    found_files, large_files = scan_directory_robust(repo_root, exclude_scan_dirs, [])

    print("\n--- Repository Temporary Files ---")
    found_files = sorted(set(found_files))
    total_freed += _print_found_files(found_files, repo_root)

    print("\n--- Large Files (>100MB) in Repository ---")
    _print_large_files(large_files, repo_root)

    print(f"\n--- System Temporary Directory ({system_tmp}) ---")
    _scan_system_tmp(system_tmp)

    print(f"\nTotal potential cleanup size (Repo-local): {format_size(total_freed)}")

    if args.dry_run:
        print("\n[DRY RUN] No files were deleted.")
        return

    all_to_delete = list(exclude_scan_dirs - set(critical_dirs)) + found_files
    if not all_to_delete:
        print("\nNothing to delete.")
        return

    size_str = format_size(total_freed)
    msg = f"This will delete {len(all_to_delete)} items and free approx {size_str}."
    should_proceed = confirm(msg, "PERMANENT DELETION WARNING")

    if not should_proceed:
        print("Cleanup cancelled.")
        return

    print("\nStarting cleanup...")
    deleted_count, errors_count = _delete_items(all_to_delete)
    print(f"\nCleanup complete. Deleted {deleted_count} items. Errors: {errors_count}")


if __name__ == "__main__":
    main()
