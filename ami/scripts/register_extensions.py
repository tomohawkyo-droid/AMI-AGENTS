#!/usr/bin/env python3
"""
Create symlinks and wrappers in .boot-linux/bin/ for all extensions.

Uses manifest discovery from extension_registry (extension.manifest.yaml files).
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

from ami.scripts.shell.extension_registry import (
    ResolvedExtension,
    Status,
    discover_manifests,
    find_ami_root,
    resolve_extensions,
)
from ami.scripts.shell.version_enforcer import enforce_versions


def create_wrapper(path: Path, ami_root: Path, script: str) -> None:
    """Create wrapper script that calls ami-run with the script."""
    wrapper = f"""#!/usr/bin/env bash
exec "{ami_root}/ami/scripts/bin/ami-run" "{ami_root}/{script}" "$@"
"""
    path.write_text(wrapper)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def fix_stale_shebang(binary: Path, ami_root: Path) -> None:
    """Fix stale shebangs in pip-installed entry points (e.g. matrix-commander, synadm).

    When the project moves to a new directory, pip-installed console_scripts retain
    shebangs pointing to the old venv path. This rewrites them to use the current venv.
    Also fixes wrapper scripts that reference old Python paths.
    """
    if not binary.exists() or not binary.is_file():
        return

    try:
        content = binary.read_text()
    except (OSError, UnicodeDecodeError):
        return

    correct_python = str(ami_root / ".venv" / "bin" / "python3")
    correct_python_no3 = str(ami_root / ".venv" / "bin" / "python")
    stale = False

    lines = content.split("\n")

    # Fix shebang (line 0)
    if lines[0].startswith("#!") and "/python" in lines[0]:
        shebang_path = lines[0][2:].strip()
        if not Path(shebang_path).exists():
            lines[0] = f"#!{correct_python}"
            stale = True

    # Fix inline python paths in bash wrappers (e.g. ami-synadm)
    for i in range(1, len(lines)):
        if "/python" in lines[i]:
            new_line = re.sub(
                r'"[^"]*?/python3?"',
                f'"{correct_python_no3}"',
                lines[i],
            )
            if new_line != lines[i]:
                lines[i] = new_line
                stale = True

    if stale:
        binary.write_text("\n".join(lines))
        print(f"  \u2713 Fixed stale shebang in {binary.name}")


def create_symlink(link: Path, target: Path) -> None:
    """Create symlink, removing existing if present."""
    link.unlink(missing_ok=True)
    link.symlink_to(target)


def _register_one(ext: ResolvedExtension, bin_dir: Path, ami_root: Path) -> None:
    """Register a single resolved extension into bin_dir."""
    entry = ext.entry
    name = entry["name"]
    binary = entry["binary"]
    target_path = bin_dir / name
    source_path = ami_root / binary

    # Skip if target already exists at same path
    if target_path.exists() and target_path.resolve() == source_path.resolve():
        print(f"  \u2713 {name} \u2192 {binary} (already in place)")
        return

    if binary.endswith(".py"):
        create_wrapper(target_path, ami_root, binary)
        print(f"  \u2713 {name} \u2192 wrapper({binary})")
    else:
        fix_stale_shebang(source_path, ami_root)
        create_symlink(target_path, source_path)
        print(f"  \u2713 {name} \u2192 {binary}")


def register_extensions() -> None:
    """Register all extensions as symlinks/wrappers in .boot-linux/bin/."""
    ami_root = find_ami_root()
    bin_dir = ami_root / ".boot-linux" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    manifests = discover_manifests(ami_root)
    if not manifests:
        print("[WARN] No extension.manifest.yaml files found.")
        return

    resolved = enforce_versions(resolve_extensions(manifests, ami_root), ami_root)

    print("\U0001f517 Creating extension symlinks/wrappers...")

    registered = 0
    skipped_unavailable = 0
    skipped_mismatch = 0
    for ext in resolved:
        if ext.status == Status.UNAVAILABLE:
            skipped_unavailable += 1
            continue
        if ext.status == Status.VERSION_MISMATCH:
            name = ext.entry["name"]
            print(f"  \u26a0 {name} skipped: {ext.reason}")
            skipped_mismatch += 1
            continue
        _register_one(ext, bin_dir, ami_root)
        registered += 1

    print(f"\n\u2705 Registered {registered} commands in {bin_dir}")
    if skipped_unavailable:
        print(f"   Skipped {skipped_unavailable} unavailable extensions")
    if skipped_mismatch:
        print(f"   Skipped {skipped_mismatch} version-mismatched extensions")

    update_bashrc_path(bin_dir)
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
    print("\u2705 Added PATH to TOP of ~/.bashrc (works for all shells)")


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
        print("\u2705 Removed shell functions from ~/.bashrc")


if __name__ == "__main__":
    register_extensions()
