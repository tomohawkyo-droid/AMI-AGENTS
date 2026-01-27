#!/usr/bin/env python3
"""Utility functions for the AMI status display."""

import re
import subprocess
import unicodedata

try:
    import psutil
except ImportError:
    psutil = None

from ami.cli_components.text_input_utils import Colors
from ami.types.status import PortMapping

# Display constants
DISPLAY_WIDTH = 80
BYTES_PER_KB = 1024
MIN_PARTS_COUNT = 2
MIN_VOLUME_BYTES = 8192
MIN_STATS_PARTS = 3

# Status icons
I_OK = "🟢"
I_FAIL = "🔴"
I_WARN = "🟡"
I_STOP = "⚪"
I_CONT = "🐳"

# Functional icons
I_BOOT = "🚀"  # Enabled (starts on boot)
I_NOBOOT = "💤"  # Disabled (no auto-start)
I_RESTART_ALWAYS = "♻️"  # Restart=always (always restarts)
I_RESTART_FAIL = "🩹"  # Restart=on-failure (restarts on crash)
I_NORESTART = "🚫"  # Restart=no (never restarts)

# Resource icons
I_CPU = "⚡"
I_MEM = "🐏"
I_VOL = "📁"

C_DIM = "\033[2m"
C_RESET = "\033[0m"

# System Docker binary
SYSTEM_DOCKER_BIN = "/usr/bin/docker"


def run_cmd(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=False
        )
        return result.stdout.strip()
    except subprocess.SubprocessError:
        return ""


def get_visual_width(text: str) -> int:
    """Calculate the visual width of a string in terminal cells."""
    clean_text = re.sub(r"\033\[[0-9;]*m", "", text)
    width = 0
    for char in clean_text:
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2
        else:
            width += 1

    for char in ["⚙️", "⚙"]:
        if char in clean_text:
            width += clean_text.count(char)

    return width


def get_local_ports(pid: str) -> list[str]:
    if not psutil or pid == "0" or not pid:
        return []
    ports: set[str] = set()
    try:
        proc = psutil.Process(int(pid))
        procs = [proc, *proc.children(recursive=True)]
        for p in procs:
            try:
                for conn in p.net_connections(kind="inet"):
                    if conn.status == psutil.CONN_LISTEN:
                        ports.add(str(conn.laddr.port))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return []
    return sorted(ports)


def format_ports(ports: list[PortMapping]) -> str:
    """Format port mappings for display."""
    if not ports:
        return ""
    out: list[str] = []
    for p in ports:
        if p.host_port and p.container_port:
            out.append(f"{p.host_port}->{p.container_port}/{p.protocol}")
        elif p.container_port:
            out.append(f"{p.container_port}/{p.protocol}")
    return ", ".join(out) if out else ""


def format_bytes(num_bytes: float) -> str:
    """Format bytes to human readable string."""
    if num_bytes <= 0:
        return "0B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < BYTES_PER_KB:
            if unit in ("B", "KB"):
                return f"{int(num_bytes)}{unit}"
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= BYTES_PER_KB
    return f"{num_bytes:.1f}PB"


def parse_size_to_bytes(size_str: str) -> int:
    """Parse human-readable size string to bytes."""
    if not size_str or size_str == "-":
        return 0
    size_str = size_str.strip().upper()
    multipliers = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return int(float(size_str[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(size_str)
    except ValueError:
        return 0


def print_box_line(
    text: str, width: int, color: str = Colors.CYAN, bold: bool = False
) -> None:
    """Print a line inside the box."""
    visible_width = get_visual_width(text)
    max_content_w = width - 4

    padding = max_content_w - visible_width

    if padding < 0:
        text = text[:max_content_w]
        padding = 0

    style = Colors.BOLD if bold else ""
    print(f"{color}│{Colors.RESET} {style}{text}{' ' * padding} {color}│{Colors.RESET}")


def _get_restart_icon(restart: str) -> str:
    """Get appropriate restart icon based on restart policy."""
    if restart == "always":
        return I_RESTART_ALWAYS
    elif restart in ("on-failure", "on-abnormal", "on-abort", "on-watchdog"):
        return I_RESTART_FAIL
    else:
        return I_NORESTART


def _get_container_status_display(state: str) -> tuple[str, str]:
    """Get status icon and color for a container state."""
    state_map = {
        "running": (I_OK, Colors.GREEN),
        "exited": (I_FAIL, Colors.RED),
        "paused": (I_WARN, Colors.YELLOW),
    }
    return state_map.get(state, (I_STOP, C_DIM))


def _format_port_string(port: PortMapping) -> str:
    """Format a port mapping for display."""
    if port.host_port:
        return f"{port.host_port}->{port.container_port}/{port.protocol}"
    return f"{port.container_port}/{port.protocol}"
