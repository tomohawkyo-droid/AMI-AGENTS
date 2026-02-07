#!/usr/bin/env python3
"""
Duplicate file finder script that compares filenames between two directories.
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import NamedTuple


class FileEntry(NamedTuple):
    """Information about a file."""

    name: str
    path: str


class DuplicateResult(NamedTuple):
    """Result of duplicate search."""

    duplicates: set[str]
    entries_a: list[FileEntry]
    entries_b: list[FileEntry]


def is_subdirectory(parent: str | Path, child: str | Path) -> bool:
    """Check if child is a subdirectory of parent."""
    try:
        child_path = Path(child).resolve()
        parent_path = Path(parent).resolve()
        child_path.relative_to(parent_path)
    except ValueError:
        return False
    else:
        return True


def get_all_filenames(
    directory: str | Path,
    dir_to_skip: str | Path | None = None,
) -> list[FileEntry]:
    """Get all filenames in a directory recursively."""
    entries: list[FileEntry] = []

    for root, dirs, files in os.walk(directory):
        # Remove hidden directories from the walk
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        # Remove the directory to skip if it's in this level
        if dir_to_skip:
            dirs[:] = [d for d in dirs if d != Path(dir_to_skip).name]

        for file in files:
            # Skip files starting with underscore like __init__
            if not file.startswith("_"):
                filepath = os.path.join(root, file)
                entries.append(FileEntry(name=file, path=filepath))

    return entries


def find_duplicates(dir_a: str | Path, dir_b: str | Path) -> DuplicateResult:
    """Find duplicate filenames between two directories."""
    # Check if one directory is a subdirectory of the other
    if is_subdirectory(dir_a, dir_b):
        print(f"Skipping {dir_b} since it's a child of {dir_a}")
        entries_a = get_all_filenames(dir_a, dir_to_skip=dir_b)
        entries_b: list[FileEntry] = []
    elif is_subdirectory(dir_b, dir_a):
        print(f"Skipping {dir_a} since it's a child of {dir_b}")
        entries_a = []
        entries_b = get_all_filenames(dir_b, dir_to_skip=dir_a)
    else:
        # Neither is a subdirectory of the other
        entries_a = get_all_filenames(dir_a)
        entries_b = get_all_filenames(dir_b)

    names_a = {e.name for e in entries_a}
    names_b = {e.name for e in entries_b}

    duplicates = names_a.intersection(names_b)

    return DuplicateResult(duplicates, entries_a, entries_b)


def _move_to_trash(dup: str, entries: list[FileEntry], trash_path: Path) -> int:
    """Helper to move duplicates to trash."""
    moved_count = 0
    for entry in entries:
        if entry.name == dup:
            try:
                dest_path = trash_path / os.path.basename(entry.path)

                # Handle naming conflicts in trash
                counter = 1
                original_dest = dest_path
                while dest_path.exists():
                    name = f"{original_dest.stem}_{counter}{original_dest.suffix}"
                    dest_path = original_dest.with_name(name)
                    counter += 1

                shutil.move(entry.path, dest_path)
                print(f"Moved to trash: {entry.path}")
                moved_count += 1
            except Exception as e:
                print(f"Error moving {entry.path}: {e}")
    return moved_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find duplicate filenames in two directories"
    )
    parser.add_argument("dir_a", help="First directory to compare")
    parser.add_argument("dir_b", help="Second directory to compare")
    parser.add_argument(
        "--trash",
        action="store_true",
        help="Move all identified duplicates into .trash",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.dir_a) or not os.path.isdir(args.dir_b):
        print("Error: Both arguments must be valid directories")
        return

    # Find duplicates
    res = find_duplicates(args.dir_a, args.dir_b)

    if not res.duplicates:
        print("No duplicate filenames found.")
        return

    print(f"Found {len(res.duplicates)} duplicate filenames:")
    for dup in sorted(res.duplicates):
        print(f"  {dup}")

    if args.trash:
        trash_dir = ".trash"
        trash_path = Path(trash_dir)
        trash_path.mkdir(exist_ok=True)
        print(f"\nMoving all duplicate files to {os.path.abspath(trash_dir)}...")

        moved_count = 0
        for dup in res.duplicates:
            moved_count += _move_to_trash(dup, res.entries_a, trash_path)
            moved_count += _move_to_trash(dup, res.entries_b, trash_path)

        print(f"Moved {moved_count} files to trash.")


if __name__ == "__main__":
    main()
