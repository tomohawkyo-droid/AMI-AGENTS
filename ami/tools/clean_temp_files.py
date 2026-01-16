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
import sys
from pathlib import Path
from typing import List, Tuple, Set

from ami.cli_components.confirmation_dialog import confirm

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
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def is_subpath(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False

def scan_directory_robust(root_dir: Path, exclude_dirs: Set[Path], patterns: List[str]) -> Tuple[List[Path], List[Path]]:
    """
    Robustly scan directory for files matching patterns and large files.
    Skips exclude_dirs.
    Returns (found_files, large_files).
    """
    found_files = []
    large_files = []
    
    # Convert exclusions to strings for faster checking
    exclude_paths = {str(p.resolve()) for p in exclude_dirs if p.exists()}
    
    stack = [root_dir]
    while stack:
        current_dir = stack.pop()
        
        # Skip if this dir is in exclusion list (or subpath of one)
        # Note: We checked top-level exclusions before adding to stack for efficiency,
        # but robust check here handles edge cases.
        try:
            curr_resolve = str(current_dir.resolve())
            if any(curr_resolve == ex or curr_resolve.startswith(ex + os.sep) for ex in exclude_paths):
                continue
        except Exception:
            continue

        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    try:
                        path = Path(entry.path)
                        
                        if entry.is_symlink():
                            continue
                            
                        if entry.is_dir():
                            # Don't recurse into hidden dirs like .git unless specifically needed
                            if entry.name == ".git":
                                continue
                            
                            # Recursively exclude venvs and node_modules
                            if entry.name in [".venv", "node_modules"]:
                                continue

                            # Check exclusions before stacking
                            try:
                                full_path = str(path.resolve())
                                if full_path in exclude_paths:
                                    continue
                            except Exception:
                                pass
                                
                            # Check for __pycache__ pattern directly here
                            if entry.name == "__pycache__":
                                found_files.append(path)
                                continue # Don't recurse into pycache we are deleting
                            
                            stack.append(path)
                            
                        elif entry.is_file():
                            # Check patterns
                            name = entry.name
                            matched = False
                            
                            # Simple pattern matching
                            if name.endswith(".pyc"):
                                found_files.append(path)
                                matched = True
                            elif name.endswith(".log"):
                                found_files.append(path)
                                matched = True
                            elif name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tar.zst") or name.endswith(".zip"):
                                found_files.append(path)
                                matched = True
                            
                            # Check size for large files (>100MB)
                            if not matched:
                                try:
                                    if entry.stat().st_size > 100 * 1024 * 1024:
                                        large_files.append(path)
                                except Exception:
                                    pass
                                    
                    except Exception:
                        continue
        except Exception:
            continue
            
    return found_files, large_files

def main():
    parser = argparse.ArgumentParser(description="Clean temporary files and directories.")
    parser.add_argument("--dry-run", action="store_true", help="List items to be cleaned without deleting.")
    args = parser.parse_args()

    repo_root = Path.cwd()
    system_tmp = Path("/tmp")
    
    # 1. Repo-local temporary directories (will be skipped in general scan and reported for cleanup)
    repo_temp_dirs = [
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

    # 2. Critical directories that must NEVER be scanned or cleaned (e.g. production logs)
    critical_dirs = [
        repo_root / "logs",
        repo_root / ".git", # Already handled but good to be explicit
        repo_root / ".venv",
        repo_root / "node_modules",
        # Also exclude nested venvs/node_modules if possible, but for now top-level is key
    ]

    print("Scanning for temporary files and directories...\n")
    
    total_freed = 0
    
    # Group 1: Repo Dirs
    print(f"--- Repository Temporary Directories ({repo_root}) ---")
    exclude_scan_dirs = set(critical_dirs)
    for d in repo_temp_dirs:
        if d.exists():
            exclude_scan_dirs.add(d)
            size = get_size(d)
            total_freed += size
            print(f"[DIR]  {d} ({format_size(size)})")
            
    # Group 2 & 3: Files and Large Files
    print(f"\n--- Scanning Repository Files (skipping temp & critical dirs) ---")
    found_files, large_files = scan_directory_robust(repo_root, exclude_scan_dirs, [])

    print(f"\n--- Repository Temporary Files ---")
    found_files = sorted(list(set(found_files)))
    for f in found_files:
        size = get_size(f)
        total_freed += size
        type_str = "[DIR]" if f.is_dir() else "[FILE]"
        print(f"{type_str} {f.relative_to(repo_root)} ({format_size(size)})")

    print(f"\n--- Large Files (>100MB) in Repository ---")
    for f in large_files:
        size = get_size(f)
        print(f"[LARGE] {f.relative_to(repo_root)} ({format_size(size)})")


    # Group 4: System Tmp
    print(f"\n--- System Temporary Directory ({system_tmp}) ---")
    try:
        tmp_items = []
        user = os.environ.get("USER", "ami")
        with os.scandir(system_tmp) as it:
            for entry in it:
                try:
                    path = Path(entry.path)
                    if path.owner() == user:
                        size = get_size(path)
                        tmp_items.append((path, size))
                except Exception:
                    pass
        
        tmp_items.sort(key=lambda x: x[1], reverse=True)
        
        for item, size in tmp_items[:20]:
             print(f"[TMP]  {item} ({format_size(size)})")
             
    except Exception as e:
        print(f"Error scanning /tmp: {e}")

    print(f"\nTotal potential cleanup size (Repo-local): {format_size(total_freed)}")
    
    if args.dry_run:
        print("\n[DRY RUN] No files were deleted.")
        return

    # Deletion logic
    all_to_delete = list(exclude_scan_dirs - set(critical_dirs)) + found_files
    if not all_to_delete:
        print("\nNothing to delete.")
        return

    should_proceed = confirm(
        f"This will delete {len(all_to_delete)} items and free approx {format_size(total_freed)}.",
        "PERMANENT DELETION WARNING"
    )
    
    if not should_proceed:
        print("Cleanup cancelled.")
        return

    print("\nStarting cleanup...")
    deleted_count = 0
    errors_count = 0
    
    for item in all_to_delete:
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

    # Special handling for /tmp system items (if we want to be aggressive)
    # For now, let's stick to repo cleanup as requested.

    print(f"\nCleanup complete. Deleted {deleted_count} items. Errors: {errors_count}")

if __name__ == "__main__":
    main()
