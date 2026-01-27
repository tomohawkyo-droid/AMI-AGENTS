#!/usr/bin/env python3
"""System status display for AMI services and containers."""

import argparse
import os
import types as _types

from ami.cli_components.legend import Legend, LegendItem

# Import from sub-modules for internal use
from ami.cli_components.status_containers import (
    _print_orphans,
    _print_service_children,
    _print_system_docker_section,
    get_container_sizes,
    get_container_stats,
    get_podman_containers,
)
from ami.cli_components.status_systemd import (
    _print_orphan_services,
    _process_service,
    get_managed_service_names,
    get_systemd_services,
)

# ── Backward-compatible re-exports ──────────────────────────────────────────
# Tests and external consumers may import these names from this module.
from ami.cli_components.status_utils import (
    DISPLAY_WIDTH,
    I_BOOT,
    I_FAIL,
    I_NOBOOT,
    I_NORESTART,
    I_OK,
    I_RESTART_ALWAYS,
    I_RESTART_FAIL,
    I_STOP,
    I_WARN,
    _get_restart_icon,
    print_box_line,
)
from ami.cli_components.text_input_utils import Colors
from ami.types.status import ServiceDisplayInfo, SystemdService

yaml: _types.ModuleType | None
try:
    import yaml
except ImportError:
    yaml = None

try:
    import psutil
except ImportError:
    psutil = None


# ── Header / Footer ────────────────────────────────────────────────────────


def _print_header() -> None:
    """Print the status report header."""
    legend = Legend(
        [
            [
                LegendItem(I_OK, "run"),
                LegendItem(I_WARN, "retry"),
                LegendItem(I_FAIL, "fail"),
            ],
            [
                LegendItem(I_BOOT, "boot"),
                LegendItem(I_NOBOOT, "manual"),
            ],
            [
                LegendItem(I_RESTART_ALWAYS, "always"),
                LegendItem(I_RESTART_FAIL, "on-fail"),
                LegendItem(I_NORESTART, "never"),
            ],
        ]
    )
    icons_line, labels_line = legend.render(DISPLAY_WIDTH)

    print(f"\n{Colors.CYAN}┌{'─' * (DISPLAY_WIDTH - 2)}┐{Colors.RESET}")
    print_box_line(
        f"{Colors.YELLOW}AMI SYSTEM STATUS REPORT{Colors.RESET}",
        DISPLAY_WIDTH,
        bold=True,
    )
    print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
    print_box_line(icons_line, DISPLAY_WIDTH)
    print_box_line(labels_line, DISPLAY_WIDTH)
    print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
    print_box_line("", DISPLAY_WIDTH)


def _print_footer() -> None:
    """Print the status report footer."""
    print(f"{Colors.CYAN}└{'─' * (DISPLAY_WIDTH - 2)}┘{Colors.RESET}\n")


# ── Service entry printing ─────────────────────────────────────────────────


def _print_service_entry(
    svc: SystemdService,
    info: ServiceDisplayInfo,
    container_stats: dict[str, dict[str, str]],
    container_sizes: dict[str, dict[str, str]],
) -> None:
    """Print a single service entry."""
    # Status icon based on ActiveState + SubState
    if svc.active == "active" and svc.sub == "running":
        status_icon = I_OK
    elif svc.active == "activating" or svc.sub == "auto-restart":
        status_icon = I_WARN
    elif svc.active in {"inactive", "failed"}:
        status_icon = I_FAIL
    else:
        status_icon = I_STOP

    # Functional icons
    boot_icon = I_BOOT if svc.enabled == "enabled" else I_NOBOOT
    restart_icon = _get_restart_icon(svc.restart)

    # Build flags line
    flags = f"{boot_icon} {restart_icon}"

    print_box_line(
        f"{status_icon} {Colors.BOLD}{svc.name}{Colors.RESET}  {flags}", DISPLAY_WIDTH
    )
    print_box_line(f"   Type:   {info.row_type}", DISPLAY_WIDTH)
    if svc.pid != "0":
        print_box_line(f"   PID:    {svc.pid}", DISPLAY_WIDTH)
    if info.row_details:
        print_box_line(f"   Info:   {' '.join(info.row_details)}", DISPLAY_WIDTH)

    short_path = svc.path.replace(os.path.expanduser("~"), "~")
    print_box_line(f"   Origin: {short_path}", DISPLAY_WIDTH)

    if info.ports_str:
        print_box_line(f"   Ports:  {info.ports_str}", DISPLAY_WIDTH)

    _print_service_children(info.child_items, container_stats, container_sizes)
    print_box_line("", DISPLAY_WIDTH)


# ── Main entry point ───────────────────────────────────────────────────────


def main() -> None:
    """Main entry point for status display."""
    parser = argparse.ArgumentParser(description="AMI System Status")
    parser.add_argument(
        "-s",
        "--system",
        action="store_true",
        help="Include system Docker containers (/usr/bin/docker)",
    )
    args = parser.parse_args()

    services = get_systemd_services()
    containers = get_podman_containers()
    container_stats = get_container_stats()
    container_sizes = get_container_sizes()
    managed_services = get_managed_service_names()
    processed_containers: set[str] = set()

    # Separate managed vs orphan services (ami-* user services not in Ansible)
    orphan_svc_names = {
        name
        for name, svc in services.items()
        if name.startswith("ami-")
        and svc.scope == "user"
        and name not in managed_services
    }

    _print_header()

    # Only print managed services in main section
    managed_svcs = [
        name for name in sorted(services.keys()) if name not in orphan_svc_names
    ]
    for i, svc_name in enumerate(managed_svcs):
        svc = services[svc_name]
        display_info = _process_service(svc, containers, processed_containers)
        _print_service_entry(svc, display_info, container_stats, container_sizes)

        if i < len(managed_svcs) - 1:
            print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
            print_box_line("", DISPLAY_WIDTH)

    _print_orphans(containers, processed_containers)
    _print_orphan_services(services, managed_services)

    if args.system:
        _print_system_docker_section()

    _print_footer()


if __name__ == "__main__":
    main()
