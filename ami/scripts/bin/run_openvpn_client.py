#!/usr/bin/env bash
""":'
exec "$(dirname "$0")/../scripts/ami-run" "$0" "$@"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple


class VPNHealthStatus(NamedTuple):
    """VPN health check status."""

    status: str
    connected: bool


def check_openvpn_installed() -> bool:
    try:
        result = subprocess.run(
            ["which", "openvpn"], capture_output=True, text=True, check=False
        )
    except OSError:
        return False
    else:
        return result.returncode == 0


def validate_ovpn_file(path: str) -> bool:
    try:
        ovpn_path = Path(path)
        if not ovpn_path.exists():
            return False
        content = ovpn_path.read_text(encoding="utf-8")
        return any(d in content.lower() for d in ["remote ", "proto ", "dev "])
    except Exception:
        return False


def run_openvpn_client(
    ovpn_file: str,
    auth_user_pass: str | None = None,
    additional_args: list[str] | None = None,
) -> subprocess.Popen[str]:
    cmd = ["openvpn", "--config", ovpn_file]
    if auth_user_pass:
        cmd.extend(["--auth-user-pass", auth_user_pass])
    if additional_args:
        cmd.extend(additional_args)
    print(f"Starting OpenVPN client: {' '.join(cmd)}")
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def check_vpn_connection() -> bool:
    try:
        if (
            subprocess.run(
                ["pgrep", "-f", "openvpn"], capture_output=True, check=False
            ).returncode
            != 0
        ):
            return False
        return (
            subprocess.run(
                ["ip", "addr", "show", "tun0"], capture_output=True, check=False
            ).returncode
            == 0
        )
    except Exception:
        return False


async def health_check() -> VPNHealthStatus:
    is_connected = check_vpn_connection()
    return VPNHealthStatus(
        status="connected" if is_connected else "disconnected",
        connected=is_connected,
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ovpn-file")
    parser.add_argument("--auth-file")
    parser.add_argument("--action", default="start")
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()
    if args.action == "health":
        health_status = await health_check()
        print(
            json.dumps(
                {"status": health_status.status, "connected": health_status.connected}
            )
        )
        return 0
    if args.action == "start":
        ovpn = args.ovpn_file or os.environ.get("OPENVPN_CONFIG_FILE")
        if not ovpn or not validate_ovpn_file(ovpn):
            return 1
        process = run_openvpn_client(ovpn, args.auth_file)
        if not args.daemon:
            while process.poll() is None:
                await asyncio.sleep(1)
    return 0


if __name__ == "__main__":
    asyncio.run(main())
