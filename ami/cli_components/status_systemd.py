#!/usr/bin/env python3
"""Systemd-related functions for the AMI status display."""

import os
import re
import sys
import types
from pathlib import Path

from ami.cli_components.status_utils import (
    C_DIM,
    C_RESET,
    DISPLAY_WIDTH,
    I_BOOT,
    I_FAIL,
    I_NOBOOT,
    I_OK,
    I_STOP,
    I_WARN,
    _get_restart_icon,
    get_local_ports,
    print_box_line,
    run_cmd,
)
from ami.cli_components.text_input_utils import Colors
from ami.types.status import (
    PodmanContainer,
    ServiceDisplayInfo,
    SystemdService,
)

yaml: types.ModuleType | None
try:
    import yaml
except ImportError:
    yaml = None

# Ansible inventory path (relative to project root)
ANSIBLE_INVENTORY_PATH = "ansible/inventory/host_vars/localhost.yml"

SYSTEMD_PREFIXES = [
    "ami-",
    "matrix-",
    "postgres",
    "valkey",
    "traefik",
    "exim-relay",
    "git-",
]


def get_managed_service_names() -> set[str]:
    """Load managed service names from Ansible inventory."""
    managed: set[str] = set()

    # Find project root by looking for ansible directory
    search_paths = [
        Path.home() / "Projects" / "AMI-ORCHESTRATOR",
        Path.cwd(),
        Path.cwd().parent,
    ]

    inventory_path = None
    for base in search_paths:
        candidate = base / ANSIBLE_INVENTORY_PATH
        if candidate.exists():
            inventory_path = candidate
            break

    if not inventory_path or not yaml:
        return managed

    try:
        with open(inventory_path) as f:
            data = yaml.safe_load(f)

        # Add local_services (ami-cms, ami-secrets-broker, etc.)
        local_services = data.get("local_services", {})
        for svc_name in local_services:
            managed.add(f"{svc_name}.service")

        # Add compose service (ami-compose.service is the unified service)
        if data.get("compose_services"):
            managed.add("ami-compose.service")

    except (OSError, yaml.YAMLError) as e:
        # Log to stderr but don't crash - status should still work without inventory
        print(f"Warning: Failed to load Ansible inventory: {e}", file=sys.stderr)

    return managed


def _parse_systemd_details(details_raw: str) -> dict[str, str]:
    """Parse systemd show output into a dict."""
    details: dict[str, str] = {}
    for d_line in details_raw.splitlines():
        if "=" in d_line:
            k, v = d_line.split("=", 1)
            details[k] = v
    return details


def _extract_compose_info(exec_start: str) -> tuple[str | None, str | None, list[str]]:
    """Extract compose file and profiles from ExecStart string."""
    managed_container = None
    compose_file = None
    compose_profiles: list[str] = []

    container_match = re.search(r"podman start .*? ([a-zA-Z0-9_-]+)", exec_start)
    if container_match:
        managed_container = container_match.group(1)

    if "podman-compose" in exec_start:
        file_match = re.search(r"-f ([a-zA-Z0-9._-]+)", exec_start)
        if file_match:
            compose_file = file_match.group(1)
        profile_matches = re.findall(r"--profile ([a-zA-Z0-9_-]+)", exec_start)
        if profile_matches:
            compose_profiles = profile_matches

    return managed_container, compose_file, compose_profiles


def get_systemd_services() -> dict[str, SystemdService]:
    """Get systemd services matching known prefixes."""
    services: dict[str, SystemdService] = {}

    commands = [
        (
            "user",
            "systemctl --user list-units --type=service --all --no-legend --no-pager",
        ),
        ("system", "systemctl list-units --type=service --all --no-legend --no-pager"),
    ]

    for scope, cmd in commands:
        raw = run_cmd(cmd)
        for line in raw.splitlines():
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            if not any(name.startswith(p) for p in SYSTEMD_PREFIXES):
                continue

            # Skip if already found in user scope (prefer user scope)
            if name in services:
                continue

            scope_flag = "--user" if scope == "user" else ""
            props = (
                "Id,ActiveState,SubState,FragmentPath,"
                "MainPID,ExecStart,Restart,UnitFileState"
            )
            details_raw = run_cmd(
                f"systemctl {scope_flag} show {name} --property={props}"
            )
            details = _parse_systemd_details(details_raw)
            exec_start = details.get("ExecStart", "")
            managed_container, compose_file, compose_profiles = _extract_compose_info(
                exec_start
            )

            services[name] = SystemdService(
                name=name,
                scope=scope,
                active=details.get("ActiveState", ""),
                sub=details.get("SubState", ""),
                path=details.get("FragmentPath", ""),
                pid=details.get("MainPID", "0"),
                managed_container=managed_container,
                compose_file=compose_file,
                compose_profiles=compose_profiles,
                restart=details.get("Restart", ""),
                enabled=details.get("UnitFileState", ""),
            )
    return services


def _process_service(
    svc: SystemdService,
    containers: dict[str, PodmanContainer],
    processed_containers: set[str],
) -> ServiceDisplayInfo:
    """Process a service and return display information."""
    row_type = "Local Process"
    row_details: list[str] = []
    child_items: list[PodmanContainer] = []
    ports_str = ""

    if svc.compose_file:
        row_type = "Unified Stack"
        profiles = svc.compose_profiles
        row_details.append(
            f"Profiles: {', '.join(profiles) if profiles else 'default'}"
        )
        for c_name, c in containers.items():
            c_config_files = c.labels.get("com.docker.compose.project.config_files", "")
            if svc.compose_file in c_config_files:
                child_items.append(c)
                processed_containers.add(c_name)
    elif svc.managed_container:
        row_type = "Container Wrapper"
        managed_c = containers.get(svc.managed_container)
        if managed_c:
            child_items.append(managed_c)
            processed_containers.add(svc.managed_container)
    elif svc.pid != "0":
        ports = get_local_ports(svc.pid)
        if ports:
            ports_str = ", ".join(ports)

    return ServiceDisplayInfo(
        row_type=row_type,
        row_details=row_details,
        child_items=child_items,
        ports_str=ports_str,
    )


def _print_orphan_services(
    services: dict[str, SystemdService],
    managed_services: set[str],
) -> None:
    """Print systemd services not managed by Ansible (orphan services)."""
    # Only check ami-* user services for orphan detection
    orphan_svcs = [
        svc
        for name, svc in services.items()
        if name.startswith("ami-")
        and svc.scope == "user"
        and name not in managed_services
    ]

    if not orphan_svcs:
        return

    print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
    print_box_line("", DISPLAY_WIDTH)
    print_box_line(
        f"{Colors.YELLOW}⚠️  ORPHAN SERVICES (Not in Ansible){Colors.RESET}",
        DISPLAY_WIDTH,
        bold=True,
    )
    print_box_line("", DISPLAY_WIDTH)
    print_box_line(
        f"{C_DIM}These services exist in systemd but not in Ansible.{C_RESET}",
        DISPLAY_WIDTH,
    )
    print_box_line(
        f"{C_DIM}Consider adding them to ansible inventory.{C_RESET}",
        DISPLAY_WIDTH,
    )
    print_box_line("", DISPLAY_WIDTH)

    for svc in sorted(orphan_svcs, key=lambda s: s.name):
        # Status icon based on ActiveState + SubState
        if svc.active == "active" and svc.sub == "running":
            status_icon = I_OK
        elif svc.active == "activating" or svc.sub == "auto-restart":
            status_icon = I_WARN
        elif svc.active in {"inactive", "failed"}:
            status_icon = I_FAIL
        else:
            status_icon = I_STOP

        boot_icon = I_BOOT if svc.enabled == "enabled" else I_NOBOOT
        restart_icon = _get_restart_icon(svc.restart)
        short_path = svc.path.replace(os.path.expanduser("~"), "~")
        name_part = f"{Colors.BOLD}{svc.name}{Colors.RESET}"
        line = f"   {status_icon} {name_part}  {boot_icon} {restart_icon}"
        print_box_line(line, DISPLAY_WIDTH)
        print_box_line(f"      Origin: {short_path}", DISPLAY_WIDTH)

    print_box_line("", DISPLAY_WIDTH)
