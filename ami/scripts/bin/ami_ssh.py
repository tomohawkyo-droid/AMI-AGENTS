#!/usr/bin/env python3
"""AMI SSH Wrapper.

Smart SSH wrapper using AMI's bootstrapped OpenSSH with AMI-aware defaults.
Auto-discovers SSH keys and config from the AMI project structure.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _ami_root() -> str:
    """Get AMI_ROOT."""
    root = os.environ.get("AMI_ROOT")
    if not root:
        print("Error: AMI_ROOT not set", file=sys.stderr)
        sys.exit(1)
    return root


def _find_ssh_binary() -> str:
    """Find the bootstrapped SSH binary."""
    root = Path(_ami_root())
    # Prefer bootstrapped openssh
    boot_ssh = root / ".boot-linux" / "openssh" / "bin" / "ssh"
    if boot_ssh.exists():
        return str(boot_ssh)
    boot_bin_ssh = root / ".boot-linux" / "bin" / "ssh"
    if boot_bin_ssh.exists():
        return str(boot_bin_ssh)
    return "ssh"


def _find_ssh_keys() -> list[str]:
    """Find SSH keys from AMI config and user .ssh."""
    keys: list[str] = []
    root = Path(_ami_root())

    # AMI project SSH keys
    ami_ssh_dir = root / ".ssh"
    if ami_ssh_dir.is_dir():
        keys.extend(
            str(key_file)
            for key_file in ami_ssh_dir.iterdir()
            if key_file.is_file()
            and not key_file.name.endswith(".pub")
            and key_file.name != "known_hosts"
        )

    return keys


def _find_ssh_config() -> str | None:
    """Find AMI SSH config if it exists."""
    root = Path(_ami_root())
    ami_config = root / "ami" / "config" / "ssh_config"
    if ami_config.exists():
        return str(ami_config)
    ami_config = root / ".ssh" / "config"
    if ami_config.exists():
        return str(ami_config)
    return None


def main() -> int:
    """Main entry point — pass through to SSH with AMI defaults."""
    ssh_bin = _find_ssh_binary()
    args = list(sys.argv[1:])

    # Only inject defaults if user hasn't specified them
    has_identity = any(a == "-i" for a in args)
    has_config = any(a == "-F" for a in args)

    inject_args: list[str] = []

    if not has_config:
        config = _find_ssh_config()
        if config:
            inject_args.extend(["-F", config])

    if not has_identity:
        keys = _find_ssh_keys()
        for key in keys:
            inject_args.extend(["-i", key])

    cmd = [ssh_bin, *inject_args, *args]
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
