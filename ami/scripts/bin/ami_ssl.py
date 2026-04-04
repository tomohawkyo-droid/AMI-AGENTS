#!/usr/bin/env python3
"""AMI OpenSSL Wrapper.

Smart wrapper for openssl with AMI-aware certificate path defaults.
"""

from __future__ import annotations

import os
import shutil
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


def _find_openssl() -> str | None:
    """Find the bootstrapped openssl binary."""
    root = Path(_ami_root())
    boot = root / ".boot-linux" / "bin" / "openssl"
    if boot.exists():
        return str(boot)
    return shutil.which("openssl")


def _find_cert_dir() -> str | None:
    """Find AMI certificate directory."""
    root = Path(_ami_root())
    for name in ["certs", "ssl", "tls"]:
        cert_dir = root / "ami" / "config" / name
        if cert_dir.is_dir():
            return str(cert_dir)
    return None


def main() -> int:
    """Main entry point — pass through to openssl with AMI defaults."""
    binary = _find_openssl()
    if not binary:
        print("Error: openssl not found. Run bootstrap to install it.", file=sys.stderr)
        return 1

    args = list(sys.argv[1:])

    # Inject CApath if user hasn't specified one and we have AMI certs
    has_capath = any(a in ("-CApath", "-CAfile") for a in args)
    if not has_capath:
        cert_dir = _find_cert_dir()
        if cert_dir:
            # Set as environment variable rather than injecting into every subcommand
            os.environ["SSL_CERT_DIR"] = cert_dir

    cmd = [binary, *args]
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
