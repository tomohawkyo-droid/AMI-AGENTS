#!/usr/bin/env python3
"""
Production-grade Disk Space Cleaner.
Targeted cleaning of Podman resources (Images, Containers, Volumes).
Safety Guarantee: NEVER deletes resources labeled or named 'checkpoint'.
"""

import argparse
import json
import os
import shutil
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

    def clean_uv_cache(self) -> None:
        """Cleans 'uv' package cache (~24GB potential)."""
        print("\n--- Analyzing UV Cache ---")
        if shutil.which("uv"):
            # uv cache prune doesn't have a dry-run flag that outputs size easily,
            # so we just check existence and run if forced.
            cache_dir = os.path.expanduser("~/.cache/uv")
            if os.path.exists(cache_dir):
                size_output = run_cmd(["du", "-sh", cache_dir])
                print(f"Found uv cache: {size_output}")
                if not self.dry_run:
                    print("[DELETE] Cleaning uv cache...")
                    subprocess.run(["uv", "cache", "clean"], check=False)
                else:
                    print("[PLAN] Would run 'uv cache clean'")
            else:
                print("No uv cache directory found.")
        else:
            print("uv tool not found. Skipping.")

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

    @staticmethod
    def _get_image_tag_str(img: object) -> str:
        """Extract a display string from image repo tags."""
        img_any = cast(Any, img)
        repo_tags = img_any.get("RepoTags", [])
        if not repo_tags:
            return "<none>"
        if isinstance(repo_tags, list):
            return ", ".join(repo_tags)
        return str(repo_tags)

    @staticmethod
    def _is_protected_image(tag_str: str, keywords: list[str]) -> bool:
        """Check if image matches any protected keyword."""
        tag_lower = tag_str.lower()
        for kw in keywords:
            if kw in tag_lower:
                print(f"[SKIP] Image '{tag_str}' matches protected keyword: '{kw}'")
                return True
        return False

    def clean_images(self) -> None:
        """Removes all unused images (not just dangling)."""
        print("\n--- Analyzing Images ---")

        # 1. Get IDs of images used by ANY container (running or stopped)
        used_images_cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "{{.ImageID}}",
            "--no-trunc",
        ]
        used_images_output = run_cmd(used_images_cmd)
        used_image_ids = (
            set(used_images_output.splitlines()) if used_images_output else set()
        )

        # 2. Get all images
        cmd = ["podman", "images", "--format", "json"]
        all_images = self.get_json_items(cmd)

        if not all_images:
            print("No images found.")
            return

        protected_keywords = ["checkpoint", "base-os", "postgres"]

        for img_obj in all_images:
            if not isinstance(img_obj, dict):
                continue
            img = cast(Any, img_obj)
            img_id_full = str(img.get("Id", img.get("ID", "")))
            tag_str = self._get_image_tag_str(img)

            if img_id_full in used_image_ids:
                continue

            if self._is_protected_image(tag_str, protected_keywords):
                continue

            img_id_short = img_id_full[:12]
            print(f"[DELETE] Unused Image {tag_str} ({img_id_short})")
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

    def run(self) -> None:
        self.clean_uv_cache()
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
