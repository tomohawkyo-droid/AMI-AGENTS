#!/usr/bin/env python3
"""System status display for AMI services and containers."""

import json
import os
import re
import subprocess
import unicodedata

try:
    import psutil
except ImportError:
    psutil = None

from ami.cli_components.text_input_utils import Colors
from ami.types.status import (
    PodmanContainer,
    PortMapping,
    ServiceDisplayInfo,
    SystemdService,
)

# Display constants
DISPLAY_WIDTH = 80

# Icons
I_OK = "🟢"
I_FAIL = "🔴"
I_WARN = "🟡"
I_STOP = "⚪"
I_CONT = "🐳"
I_PROC = "⚙️"
I_STACK = "📚"

C_DIM = "\033[2m"
C_RESET = "\033[0m"


def run_cmd(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=False
        )
        return result.stdout.strip()
    except Exception:
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


SYSTEMD_PREFIXES = [
    "ami-",
    "matrix-",
    "postgres",
    "valkey",
    "traefik",
    "exim-relay",
    "git-",
]


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

            scope_flag = "--user" if scope == "user" else ""
            details_raw = run_cmd(
                f"systemctl {scope_flag} show {name} --property=Id,ActiveState,SubState,FragmentPath,MainPID,ExecStart"
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
            )
    return services


def _parse_port_mapping(port_data: dict[str, str | int]) -> PortMapping:
    """Parse a port mapping from JSON data."""
    host_port = (
        port_data.get("hostPort")
        or port_data.get("HostPort")
        or port_data.get("host_port")
    )
    container_port = (
        port_data.get("containerPort")
        or port_data.get("ContainerPort")
        or port_data.get("container_port")
    )
    proto = port_data.get("protocol") or port_data.get("Protocol") or "tcp"

    return PortMapping(
        host_port=int(host_port) if host_port else None,
        container_port=int(container_port) if container_port else None,
        protocol=str(proto),
    )


def _get_container_inspect_info(
    name: str, podman_bin: str
) -> tuple[list[PortMapping], dict[str, str]]:
    """Get exposed ports and labels from container inspect data."""
    inspect_raw = run_cmd(f"{podman_bin} inspect {name} --format json")
    exposed_ports: list[PortMapping] = []
    labels: dict[str, str] = {}
    if not inspect_raw:
        return exposed_ports, labels
    try:
        inspect_data = json.loads(inspect_raw)
        if not inspect_data:
            return exposed_ports, labels
        config = inspect_data[0].get("Config", {})
        labels = config.get("Labels", {}) or {}
        exp = config.get("ExposedPorts") or {}
        for p in exp:
            port_num, proto = p.split("/")
            exposed_ports.append(
                PortMapping(container_port=int(port_num), protocol=proto)
            )
    except Exception:
        pass
    return exposed_ports, labels


def get_podman_containers() -> dict[str, PodmanContainer]:
    """Get podman containers information."""
    podman_bin = "podman"
    raw = run_cmd(f"{podman_bin} ps -a --format json")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        containers: dict[str, PodmanContainer] = {}
        for c in data:
            names = c.get("Names", [])
            name = names[0] if names else c.get("Id")[:12]

            exposed_ports, labels = _get_container_inspect_info(name, podman_bin)

            # Parse ports from container data
            raw_ports = c.get("Ports") or []
            parsed_ports = [
                _parse_port_mapping(port_info)
                for port_info in raw_ports
                if isinstance(port_info, dict)
            ]

            # Use raw ports if available, otherwise use exposed ports
            final_ports = parsed_ports if parsed_ports else exposed_ports

            containers[name] = PodmanContainer(
                id=c.get("Id", "")[:12],
                name=name,
                state=c.get("State", ""),
                status=c.get("Status", ""),
                ports=final_ports,
                image=c.get("Image", ""),
                labels=labels,
            )
    except Exception:
        return {}
    else:
        return containers


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


def _print_header() -> None:
    """Print the status report header."""
    print(f"\n{Colors.CYAN}┌{'─' * (DISPLAY_WIDTH - 2)}┐{Colors.RESET}")
    print_box_line(
        f"{Colors.YELLOW}AMI SYSTEM STATUS REPORT{Colors.RESET}",
        DISPLAY_WIDTH,
        bold=True,
    )
    print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
    print_box_line("", DISPLAY_WIDTH)


def _print_footer() -> None:
    """Print the status report footer."""
    print(f"{Colors.CYAN}└{'─' * (DISPLAY_WIDTH - 2)}┘{Colors.RESET}\n")


def _print_service_children(child_items: list[PodmanContainer]) -> None:
    """Print child containers for a service."""
    if not child_items:
        return
    print_box_line("", DISPLAY_WIDTH)
    for c in child_items:
        c_color = Colors.GREEN if c.state == "running" else Colors.RED
        c_ports = format_ports(c.ports)
        print_box_line(
            f"   ├─ {c_color}{c.name}{Colors.RESET} [{c.state}]", DISPLAY_WIDTH
        )
        print_box_line(f"   │  Img: {c.image[:50]}", DISPLAY_WIDTH)
        if c_ports:
            print_box_line(f"   │  Net: {c_ports}", DISPLAY_WIDTH)


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


def _print_service_entry(svc: SystemdService, info: ServiceDisplayInfo) -> None:
    """Print a single service entry."""
    status_icon = (
        I_OK
        if svc.active == "active"
        else (I_WARN if svc.active == "activating" else I_FAIL)
    )

    print_box_line(
        f"{status_icon} {Colors.BOLD}{svc.name}{Colors.RESET}", DISPLAY_WIDTH
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

    _print_service_children(info.child_items)
    print_box_line("", DISPLAY_WIDTH)


def _print_orphans(
    containers: dict[str, PodmanContainer],
    processed_containers: set[str],
) -> None:
    """Print unmanaged (orphan) containers."""
    orphans = [
        c
        for name, c in containers.items()
        if name not in processed_containers and not name.startswith("run-")
    ]
    if not orphans:
        return

    print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
    print_box_line("", DISPLAY_WIDTH)
    print_box_line(
        f"{Colors.YELLOW}⚠️  UNMANAGED CONTAINERS (Orphans){Colors.RESET}",
        DISPLAY_WIDTH,
        bold=True,
    )
    for c in orphans:
        c_ports = format_ports(c.ports)
        print_box_line(f"   {I_CONT} {c.name} ({c.state})", DISPLAY_WIDTH)
        if c_ports:
            print_box_line(f"      Ports: {c_ports}", DISPLAY_WIDTH)
    print_box_line("", DISPLAY_WIDTH)


def main() -> None:
    """Main entry point for status display."""
    services = get_systemd_services()
    containers = get_podman_containers()
    processed_containers: set[str] = set()

    _print_header()

    sorted_svcs = sorted(services.keys())
    for i, svc_name in enumerate(sorted_svcs):
        svc = services[svc_name]
        display_info = _process_service(svc, containers, processed_containers)
        _print_service_entry(svc, display_info)

        if i < len(sorted_svcs) - 1:
            print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
            print_box_line("", DISPLAY_WIDTH)

    _print_orphans(containers, processed_containers)
    _print_footer()


if __name__ == "__main__":
    main()
