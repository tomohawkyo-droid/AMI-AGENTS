"""ami storage: aggregated disk-usage report.

Composes existing utilities:
- ami.scripts.utils.sys_info: ProgressBar + get_size_str (root filesystem usage)
- ami.scripts.utils.analyze_disk_usage: du-based top-25 directory breakdown
- ami.cli_components.status_containers.get_container_sizes: podman volume sizes
"""

from __future__ import annotations

import argparse

import psutil

from ami.cli_components.status_containers import get_container_sizes
from ami.scripts.utils.analyze_disk_usage import analyze
from ami.scripts.utils.sys_info import ProgressBar, get_size_str

_BAR_WIDTH = 40


def _print_root_disk() -> None:
    disk = psutil.disk_usage(".")
    bar = ProgressBar(width=_BAR_WIDTH)
    line = bar.render(
        percent=disk.percent,
        label="Root Disk",
        value=f"{get_size_str(disk.used)} / {get_size_str(disk.total)}",
    )
    print(line)


def _print_container_sizes() -> None:
    sizes = get_container_sizes()
    print("\nContainer Sizes")
    print("-" * 60)
    if not sizes:
        print("  No containers (podman unavailable or none running).")
        return
    for s in sizes:
        name = s["name"]
        writable = s["writable"]
        virtual = s["virtual"]
        print(f"  {name:<32} writable={writable:<10} virtual={virtual}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ami storage",
        description=(
            "Aggregated storage report: root disk, repo breakdown, container sizes."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to break down (default: current directory)",
    )
    parser.add_argument(
        "--no-containers",
        action="store_true",
        help="Skip container size collection",
    )
    parser.add_argument(
        "--no-breakdown",
        action="store_true",
        help="Skip top-25 directory breakdown",
    )
    args = parser.parse_args()
    _print_root_disk()
    if not args.no_breakdown:
        print()
        analyze(args.path)
    if not args.no_containers:
        _print_container_sizes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
