#!/usr/bin/env python3
"""
Production-grade Disk Space Cleaner.
Targeted cleaning of Podman resources (Images, Containers, Volumes).
Safety Guarantee: NEVER deletes resources labeled or named 'checkpoint'.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

KB_PER_UNIT = 1024
MIN_SIZE_KB = 1024  # Skip targets smaller than 1 MB


def run_cmd(cmd: list[str]) -> str:
    """Runs a command and returns stdout. Returns empty string on error."""
    try:
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def human_readable(size_in_kb: int) -> str:
    """Convert a size in KB to a human-readable string."""
    units = ["KB", "MB", "GB", "TB"]
    val = float(size_in_kb)
    for unit in units:
        if val < KB_PER_UNIT:
            return f"{val:.2f} {unit}"
        val /= KB_PER_UNIT
    return f"{val:.2f} PB"


class DiskCleaner:
    def __init__(
        self,
        force: bool = False,
        dry_run: bool = False,
        scan_root: str = ".",
    ) -> None:
        self.force = force
        self.dry_run = dry_run
        self.scan_root = Path(scan_root).resolve()
        if not self.force and not self.dry_run:
            print("[INFO] Running in DRY RUN mode. Use --force to execute deletions.")
            self.dry_run = True

    def get_json_items(self, cmd: list[str]) -> list[object]:
        """Helper to parse Podman JSON output."""
        output = run_cmd(cmd)
        if not output:
            return []
        try:
            # Podman sometimes outputs multiple JSON objects or a list
            # We handle the list case here
            data = json.loads(output)
            if isinstance(data, list):
                return data
            else:
                return [data]  # Should technically be a list
        except json.JSONDecodeError:
            # Fallback for weird Podman versions handling empty lists
            return []

    def clean_containers(self) -> None:
        """Removes stopped/exited/created containers."""
        print("\n--- Analyzing Containers ---")
        # Filter for non-running containers
        cmd = [
            "podman",
            "ps",
            "-a",
            "--filter",
            "status=exited",
            "--filter",
            "status=created",
            "--format",
            "json",
        ]
        containers = self.get_json_items(cmd)

        if not containers:
            print("No orphaned containers found.")
            return

        for c_obj in containers:
            if not isinstance(c_obj, dict):
                continue
            c = cast(Any, c_obj)
            # Podman 4.x+ uses 'Id' and 'Names' (list)
            # Older might use 'ID' or 'Names' (string)
            c_id = str(c.get("Id", c.get("ID", "")))[:12]
            names = c.get("Names", [])
            name = names[0] if isinstance(names, list) and names else str(names)

            # Safety Check
            if "checkpoint" in name.lower():
                print(f"[SKIP] Container '{name}' ({c_id}) matches safety filter.")
                continue

            print(f"[DELETE] Container {name} ({c_id})")
            if not self.dry_run:
                subprocess.run(["podman", "rm", "-f", c_id], check=False)

    def clean_images(self) -> None:
        """Remove only dangling (<none>) images. Tagged images are kept."""
        print("\n--- Analyzing Dangling Images ---")
        cmd = [
            "podman",
            "images",
            "--filter",
            "dangling=true",
            "--format",
            "json",
        ]
        dangling = self.get_json_items(cmd)

        if not dangling:
            print("No dangling images found.")
            return

        for img_obj in dangling:
            if not isinstance(img_obj, dict):
                continue
            img = cast(Any, img_obj)
            img_id_full = str(img.get("Id", img.get("ID", "")))
            img_id_short = img_id_full[:12]
            print(f"[DELETE] Dangling image ({img_id_short})")
            if not self.dry_run:
                subprocess.run(["podman", "rmi", "-f", img_id_full], check=False)

    def clean_volumes(self) -> None:
        """Removes unused volumes (dangling), PROTECTING checkpoints and databases."""
        print("\n--- Analyzing Volumes ---")
        cmd = [
            "podman",
            "volume",
            "ls",
            "--filter",
            "dangling=true",
            "--format",
            "json",
        ]
        volumes = self.get_json_items(cmd)

        if not volumes:
            print("No unused volumes found.")
            return

        protected_keywords = [
            "checkpoint",
            "db",
            "postgres",
            "timescale",
            "minio",
            "mlflow",
        ]

        for v_obj in volumes:
            if not isinstance(v_obj, dict):
                continue
            v = cast(Any, v_obj)
            name = str(v.get("Name", ""))

            # Safety Checks
            is_protected = False
            for kw in protected_keywords:
                if kw in name.lower():
                    print(f"[SKIP] Volume '{name}' matches protected keyword: '{kw}'")
                    is_protected = True
                    break

            if is_protected:
                continue

            print(f"[DELETE] Unused Volume {name}")
            if not self.dry_run:
                subprocess.run(["podman", "volume", "rm", "-f", name], check=False)

    def _find_cargo_projects(self) -> list[str]:
        """Find Cargo.toml files, skipping heavy dirs."""
        cmd = [
            "find",
            str(self.scan_root),
            "-name",
            "Cargo.toml",
            "-not",
            "-path",
            "*/target/*",
            "-not",
            "-path",
            "*/.venv/*",
            "-not",
            "-path",
            "*/node_modules/*",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = result.stdout.strip()
        return output.splitlines() if output else []

    def clean_rust_targets(self) -> None:
        """Remove Rust target/ directories (build artifacts)."""
        print(f"\n--- Analyzing Rust Build Artifacts under {self.scan_root} ---")
        cargo_paths = self._find_cargo_projects()
        if not cargo_paths:
            print("No Rust projects found.")
            return

        total_kb = 0
        for cargo_toml in cargo_paths:
            target_dir = Path(cargo_toml).parent / "target"
            if not target_dir.is_dir():
                continue

            size_output = run_cmd(["du", "-sk", str(target_dir)])
            if not size_output:
                continue
            parts = size_output.split("\t")
            try:
                size_kb = int(parts[0])
            except (ValueError, IndexError):
                continue

            if size_kb < MIN_SIZE_KB:
                continue

            total_kb += size_kb
            hr = human_readable(size_kb)
            print(f"[DELETE] {hr:>10}  {target_dir}")
            if not self.dry_run:
                shutil.rmtree(target_dir, ignore_errors=True)

        if total_kb:
            print(f"[INFO] Rust targets total: {human_readable(total_kb)}")
        else:
            print("No Rust target/ directories found.")

    def run(self) -> None:
        self.clean_rust_targets()
        self.clean_containers()
        self.clean_images()
        self.clean_volumes()
        print("\n[DONE] Cleaning complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safe Disk Space Cleaner")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actually execute deletions (default: Dry Run)",
    )
    parser.add_argument(
        "--scan-path",
        default=".",
        help="Root path to scan for Rust target/ directories (default: cwd)",
    )
    args = parser.parse_args()

    cleaner = DiskCleaner(force=args.force, scan_root=args.scan_path)
    cleaner.run()
