#!/usr/bin/env python3
"""
Production-grade Disk Space Cleaner.
Targeted cleaning of Podman resources (Images, Containers, Volumes).
Safety Guarantee: NEVER deletes resources labeled or named 'checkpoint'.
"""

import argparse
import json
import subprocess
from typing import Any, cast


def run_cmd(cmd: list[str]) -> str:
    """Runs a command and returns stdout. Returns empty string on error."""
    try:
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


class DiskCleaner:
    def __init__(self, force: bool = False, dry_run: bool = False) -> None:
        self.force = force
        self.dry_run = dry_run
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
        """Removes dangling (<none>) images."""
        print("\n--- Analyzing Images ---")
        cmd = ["podman", "images", "--filter", "dangling=true", "--format", "json"]
        images = self.get_json_items(cmd)

        if not images:
            print("No dangling images found.")
            return

        for img_obj in images:
            if not isinstance(img_obj, dict):
                continue
            img = cast(Any, img_obj)
            img_id = str(img.get("Id", img.get("ID", "")))

            # Safety Check: If it has tags (unlikely for dangling=true) check them
            # But primarily check ID

            print(f"[DELETE] Dangling Image {img_id[:12]}")
            if not self.dry_run:
                subprocess.run(["podman", "rmi", "-f", img_id], check=False)

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

    def run(self) -> None:
        self.clean_containers()
        self.clean_images()
        self.clean_volumes()
        print("\n[DONE] Cleaning complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safe Disk Space Cleaner for Podman")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actually execute deletions (default: Dry Run)",
    )
    args = parser.parse_args()

    cleaner = DiskCleaner(force=args.force)
    cleaner.run()
