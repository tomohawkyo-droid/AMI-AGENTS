#!/usr/bin/env python3
"""Disk usage analyzer for top-level directory contents."""

import subprocess
import sys
from pathlib import Path

KB_PER_UNIT = 1024
MIN_PARTS_PER_LINE = 2
TOP_N_RESULTS = 25


def human_readable(size_in_kb: int) -> str:
    """Convert a size in KB to a human-readable string."""
    units = ["KB", "MB", "GB", "TB"]
    val = float(size_in_kb)
    for unit in units:
        if val < KB_PER_UNIT:
            return f"{val:.2f} {unit}"
        val /= KB_PER_UNIT
    return f"{val:.2f} PB"


def analyze(path: str) -> None:
    """Run du to calculate disk usage for immediate children of the given path."""
    resolved = Path(path).expanduser()
    if not resolved.exists():
        print(f"Error: Path '{resolved}' does not exist.")
        return

    print(f"Scanning '{resolved}' for disk usage... (This may take a moment)")

    cmd = ["du", "-ak", "-d", "1", str(resolved)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = result.stdout
    except Exception as e:
        print(f"Critical error running du: {e}")
        return

    lines = output.strip().split("\n")
    data = []
    path_str = str(resolved)

    for line in lines:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < MIN_PARTS_PER_LINE:
            continue

        try:
            size = int(parts[0])
            fpath = parts[1]

            if fpath == path_str or fpath == path_str.rstrip("/"):
                continue

            data.append((size, fpath))
        except ValueError:
            continue

    data.sort(key=lambda x: x[0], reverse=True)

    print(f"\n{'SIZE':>10}  PATH")
    print("-" * 60)

    if not data:
        print("No readable files or directories found.")
        return

    for size, fpath in data[:TOP_N_RESULTS]:
        print(f"{human_readable(size):>10}  {fpath}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "~"
    analyze(target)
