#!/usr/bin/env python3
"""
Create symlinks and wrappers in .boot-linux/bin/ for all extensions.

Reads from ami/config/extensions.yaml (single source of truth).
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import yaml


def create_wrapper(path: Path, ami_root: Path, script: str) -> None:
    """Create wrapper script that calls ami-run with the script."""
    wrapper = f"""#!/usr/bin/env bash
exec "{ami_root}/ami/scripts/bin/ami-run" "{ami_root}/{script}" "$@"
"""
    path.write_text(wrapper)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_symlink(link: Path, target: Path) -> None:
    """Create symlink, removing existing if present."""
    link.unlink(missing_ok=True)
    link.symlink_to(target)


def register_extensions() -> None:
    """Register all extensions as symlinks/wrappers in .boot-linux/bin/."""
    ami_root = Path.cwd()
    bin_dir = ami_root / ".boot-linux" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Read extensions config (single source of truth)
    ext_config = ami_root / "ami/config/extensions.yaml"
    if not ext_config.exists():
        print("[ERROR] Extensions configuration not found.")
        return

    config = yaml.safe_load(ext_config.read_text())
    extensions = config.get("extensions", [])

    print("🔗 Creating extension symlinks/wrappers...")

    for ext in extensions:
        name = ext.get("name")
        binary = ext.get("binary")

        if not name or not binary:
            print(f"  ⚠ Invalid extension entry: {ext}")
            continue

        target_path = bin_dir / name

        if binary.endswith(".py"):
            # Python script - create wrapper
            create_wrapper(target_path, ami_root, binary)
            print(f"  ✓ {name} → wrapper({binary})")
        else:
            # Direct binary - create symlink
            create_symlink(target_path, ami_root / binary)
            print(f"  ✓ {name} → {binary}")

    print(f"\n✅ Created {len(extensions)} commands in {bin_dir}")

    # Add PATH to TOP of ~/.bashrc (before interactive check, works for ALL shells)
    update_bashrc_path(bin_dir)

    # Remove old shell functions from ~/.bashrc
    remove_bashrc_functions()


def update_bashrc_path(bin_dir: Path) -> None:
    """Add .boot-linux/bin to PATH at TOP of ~/.bashrc (before interactive check)."""
    bashrc = Path.home() / ".bashrc"
    if not bashrc.exists():
        return

    marker = "# AMI PATH"
    line = f'export PATH="{bin_dir}:$PATH"  {marker}'

    content = bashrc.read_text()

    # Remove old marker line if exists anywhere
    if marker in content:
        content = re.sub(rf".*{re.escape(marker)}.*\n?", "", content)

    # Find the shebang or first line, insert PATH right after
    lines = content.split("\n")
    insert_idx = 0

    # Skip shebang if present
    if lines and lines[0].startswith("#!"):
        insert_idx = 1
    # Skip initial comments
    while insert_idx < len(lines) and lines[insert_idx].startswith("#"):
        insert_idx += 1

    # Insert PATH line at the top (after comments, before any code)
    lines.insert(insert_idx, line)
    content = "\n".join(lines)

    bashrc.write_text(content)
    print("✅ Added PATH to TOP of ~/.bashrc (works for all shells)")


def remove_bashrc_functions() -> None:
    """Remove AMI AGENT EXTENSIONS block from ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    if not bashrc.exists():
        return

    content = bashrc.read_text()

    start_marker = "# --- AMI AGENT EXTENSIONS START ---"
    end_marker = "# --- AMI AGENT EXTENSIONS END ---"

    if start_marker in content and end_marker in content:
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker) + len(end_marker)
        while end_idx < len(content) and content[end_idx] == "\n":
            end_idx += 1
        content = content[:start_idx].rstrip() + "\n" + content[end_idx:].lstrip()
        bashrc.write_text(content)
        print("✅ Removed shell functions from ~/.bashrc")


if __name__ == "__main__":
    register_extensions()
