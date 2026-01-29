#!/usr/bin/env python3
"""Container-related functions for the AMI status display."""

import json
import os
import re
from typing import cast

from ami.cli_components.status_utils import (
    C_DIM,
    C_RESET,
    DISPLAY_WIDTH,
    I_CONT,
    I_CPU,
    I_MEM,
    I_VOL,
    MIN_PARTS_COUNT,
    MIN_STATS_PARTS,
    MIN_VOLUME_BYTES,
    SYSTEM_DOCKER_BIN,
    _format_port_string,
    _get_container_status_display,
    format_bytes,
    format_ports,
    print_box_line,
    run_cmd,
)
from ami.cli_components.text_input_utils import Colors
from ami.types.common import (
    ContainerLabels,
    ContainerSizeData,
    ContainerStatsData,
    PortData,
    VolumeData,
)
from ami.types.results import ContainerInspectInfo
from ami.types.status import PodmanContainer, PortMapping


def _parse_port_mapping(port_data: PortData) -> PortMapping:
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
        hostPort=int(host_port) if host_port else None,
        containerPort=int(container_port) if container_port else None,
        protocol=str(proto),
    )


def _get_container_inspect_info(name: str, podman_bin: str) -> ContainerInspectInfo:
    """Get exposed ports and labels from container inspect data."""
    inspect_raw = run_cmd(f"{podman_bin} inspect {name} --format json")
    exposed_ports: list[PortMapping] = []
    labels = cast(ContainerLabels, {})
    if not inspect_raw:
        return ContainerInspectInfo(exposed_ports, labels)
    try:
        inspect_data = json.loads(inspect_raw)
        if not inspect_data:
            return ContainerInspectInfo(exposed_ports, labels)
        config = inspect_data[0].get("Config", {})
        labels = cast(ContainerLabels, config.get("Labels", {}) or {})
        exp = config.get("ExposedPorts") or {}
        for p in exp:
            port_num, proto = p.split("/")
            exposed_ports.append(
                PortMapping(containerPort=int(port_num), protocol=proto)
            )
    except Exception:
        pass
    return ContainerInspectInfo(exposed_ports, labels)


def get_container_stats() -> list[ContainerStatsData]:
    """Get CPU/memory stats for all running containers."""
    stats: list[ContainerStatsData] = []
    raw = run_cmd("podman stats --no-stream --format json")
    if not raw:
        return stats
    try:
        data = json.loads(raw)
        for entry in data:
            name = entry.get("Name", entry.get("name", ""))
            if not name:
                continue
            stats.append(
                ContainerStatsData(
                    name=name,
                    cpu=entry.get("CPU", entry.get("cpu_percent", "0%")),
                    mem_usage=entry.get("MemUsage", entry.get("mem_usage", "")),
                    mem_percent=entry.get("MemPerc", entry.get("mem_percent", "0%")),
                )
            )
    except (json.JSONDecodeError, KeyError):
        pass
    return stats


def get_container_sizes() -> list[ContainerSizeData]:
    """Get disk sizes for all containers."""
    sizes: list[ContainerSizeData] = []
    # Format: "name\twritable (virtual total)"
    raw = run_cmd('podman ps -a --size --format "{{.Names}}\t{{.Size}}"')
    if not raw:
        return sizes
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < MIN_PARTS_COUNT:
            continue
        name = parts[0]
        size_str = parts[1]
        # Parse "22kB (virtual 198MB)"
        writable = "-"
        virtual = "-"
        if "(" in size_str:
            writable = size_str.split("(")[0].strip()
            virtual_match = size_str.split("virtual ")
            if len(virtual_match) > 1:
                virtual = virtual_match[1].rstrip(")")
        else:
            writable = size_str.strip()
        sizes.append(ContainerSizeData(name=name, writable=writable, virtual=virtual))
    return sizes


def get_container_volumes(name: str) -> list[VolumeData]:
    """Get volume mounts for a container."""
    volumes: list[VolumeData] = []
    raw = run_cmd(f"podman inspect {name} --format json")
    if not raw:
        return volumes
    try:
        data = json.loads(raw)
        if not data:
            return volumes
        mounts = data[0].get("Mounts", [])
        for m in mounts:
            src = m.get("Source", m.get("source", ""))
            dst = m.get("Destination", m.get("destination", ""))
            vol_type = m.get("Type", m.get("type", "bind"))

            if not dst:
                continue

            # Get size of source directory/file
            size_raw = run_cmd(f"du -sb '{src}' 2>/dev/null | cut -f1") if src else "0"
            try:
                size_bytes = int(size_raw) if size_raw else 0
            except ValueError:
                size_bytes = 0

            # Skip trivial volumes (< 8KB is just filesystem overhead)
            if size_bytes < MIN_VOLUME_BYTES:
                continue

            # Format size
            size_str = format_bytes(size_bytes)

            volumes.append(VolumeData(dst=dst, src=src, type=vol_type, size=size_str))
    except (json.JSONDecodeError, KeyError):
        pass
    return volumes


def get_podman_containers() -> list[PodmanContainer]:
    """Get podman containers information."""
    podman_bin = "podman"
    raw = run_cmd(f"{podman_bin} ps -a --format json")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        containers: list[PodmanContainer] = []
        for c in data:
            names = c.get("Names", [])
            name = names[0] if names else c.get("Id")[:12]

            inspect_info = _get_container_inspect_info(name, podman_bin)
            exposed_ports, labels = inspect_info.ports, inspect_info.labels

            # Parse ports from container data
            raw_ports = c.get("Ports") or []
            parsed_ports = [
                _parse_port_mapping(cast(PortData, port_info))
                for port_info in raw_ports
                if isinstance(port_info, dict)
            ]

            # Use raw ports if available, otherwise use exposed ports
            final_ports = parsed_ports if parsed_ports else exposed_ports

            containers.append(
                PodmanContainer(
                    id=c.get("Id", "")[:12],
                    name=name,
                    state=c.get("State", ""),
                    status=c.get("Status", ""),
                    ports=final_ports,
                    image=c.get("Image", ""),
                    labels={k: str(v) for k, v in labels.items()},
                )
            )
    except Exception:
        return []
    else:
        return containers


def get_system_docker_containers() -> list[PodmanContainer]:
    """Get system Docker containers using /usr/bin/docker."""
    if not os.path.exists(SYSTEM_DOCKER_BIN):
        return []

    # Try without sudo first (user may be in docker group)
    raw = run_cmd(f"{SYSTEM_DOCKER_BIN} ps -a --format json 2>/dev/null")
    if not raw:
        # Fall back to sudo
        raw = run_cmd(f"sudo {SYSTEM_DOCKER_BIN} ps -a --format json 2>/dev/null")
    if not raw:
        return []

    containers: list[PodmanContainer] = []
    try:
        # Docker outputs one JSON object per line, not an array
        for line in raw.strip().split("\n"):
            if not line.strip():
                continue
            c = json.loads(line)
            name = c.get("Names", c.get("ID", "")[:12])

            # Parse ports string like "0.0.0.0:8080->80/tcp"
            ports_str = c.get("Ports", "")
            parsed_ports: list[PortMapping] = []
            if ports_str:
                for port_part in ports_str.split(", "):
                    match = re.match(r"(?:[\d.]+:)?(\d+)->(\d+)/(\w+)", port_part)
                    if match:
                        parsed_ports.append(
                            PortMapping(
                                hostPort=int(match.group(1)),
                                containerPort=int(match.group(2)),
                                protocol=match.group(3),
                            )
                        )

            containers.append(
                PodmanContainer(
                    id=c.get("ID", "")[:12],
                    name=name,
                    state=c.get("State", ""),
                    status=c.get("Status", ""),
                    ports=parsed_ports,
                    image=c.get("Image", ""),
                    labels={},
                )
            )
    except (json.JSONDecodeError, KeyError):
        return []
    return containers


def get_system_docker_stats() -> list[ContainerStatsData]:
    """Get CPU/memory stats for system Docker containers."""
    if not os.path.exists(SYSTEM_DOCKER_BIN):
        return []

    # Try without sudo first (user may be in docker group)
    raw = run_cmd(
        f"{SYSTEM_DOCKER_BIN} stats --no-stream --format "
        "'{{{{.Name}}}}|{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}' 2>/dev/null"
    )
    if not raw:
        # Fall back to sudo
        raw = run_cmd(
            f"sudo {SYSTEM_DOCKER_BIN} stats --no-stream --format "
            "'{{{{.Name}}}}|{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}' 2>/dev/null"
        )
    if not raw:
        return []

    stats: list[ContainerStatsData] = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= MIN_STATS_PARTS:
            stats.append(
                ContainerStatsData(
                    name=parts[0],
                    cpu=parts[1],
                    mem_usage=parts[2],
                    mem_percent="",
                )
            )
    return stats


def _find_stats_by_name(
    stats_list: list[ContainerStatsData], name: str
) -> ContainerStatsData | None:
    """Find stats entry by container name."""
    for s in stats_list:
        if s["name"] == name:
            return s
    return None


def _find_size_by_name(
    sizes_list: list[ContainerSizeData], name: str
) -> ContainerSizeData | None:
    """Find size entry by container name."""
    for s in sizes_list:
        if s["name"] == name:
            return s
    return None


def _print_service_children(
    child_items: list[PodmanContainer],
    container_stats: list[ContainerStatsData],
    container_sizes: list[ContainerSizeData],
) -> None:
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

        # Show CPU/memory stats if running
        stats = _find_stats_by_name(container_stats, c.name)
        if stats and c.state == "running":
            cpu = stats.get("cpu", "-")
            mem = stats.get("mem_usage", "-")
            print_box_line(f"   │  {I_CPU} {cpu}  {I_MEM} {mem}", DISPLAY_WIDTH)

        # Show disk size
        sizes = _find_size_by_name(container_sizes, c.name)
        if sizes:
            virtual = sizes.get("virtual", "-")
            writable = sizes.get("writable", "-")
            print_box_line(
                f"   │  💿 {virtual} total, {writable} writable", DISPLAY_WIDTH
            )

        # Show volumes with actual data
        volumes = get_container_volumes(c.name)
        if volumes:
            for vol in volumes:
                dst = vol["dst"]
                size = vol["size"]
                print_box_line(f"   │  {I_VOL} {dst} ({size})", DISPLAY_WIDTH)


def _print_orphans(
    containers: list[PodmanContainer],
    processed_containers: set[str],
) -> None:
    """Print unmanaged (orphan) containers."""
    orphans = [
        c
        for c in containers
        if c.name not in processed_containers and not c.name.startswith("run-")
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


def _print_system_docker_section() -> None:
    """Print system Docker containers section."""
    if not os.path.exists(SYSTEM_DOCKER_BIN):
        print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
        print_box_line("", DISPLAY_WIDTH)
        print_box_line(
            f"{Colors.YELLOW}⚠️  SYSTEM DOCKER{Colors.RESET}",
            DISPLAY_WIDTH,
            bold=True,
        )
        print_box_line("", DISPLAY_WIDTH)
        print_box_line(
            f"{C_DIM}Docker not found at {SYSTEM_DOCKER_BIN}{C_RESET}",
            DISPLAY_WIDTH,
        )
        print_box_line("", DISPLAY_WIDTH)
        return

    containers = get_system_docker_containers()
    stats = get_system_docker_stats()

    print(f"{Colors.CYAN}├{'─' * (DISPLAY_WIDTH - 2)}┤{Colors.RESET}")
    print_box_line("", DISPLAY_WIDTH)
    print_box_line(
        f"{Colors.BLUE}🐋 SYSTEM DOCKER (/usr/bin/docker){Colors.RESET}",
        DISPLAY_WIDTH,
        bold=True,
    )
    print_box_line("", DISPLAY_WIDTH)

    if not containers:
        print_box_line(
            f"{C_DIM}No system Docker containers found (may need sudo){C_RESET}",
            DISPLAY_WIDTH,
        )
        print_box_line("", DISPLAY_WIDTH)
        return

    for c in sorted(containers, key=lambda x: x.name):
        status_icon, state_color = _get_container_status_display(c.state)

        name_part = f"{Colors.BOLD}{c.name}{Colors.RESET}"
        state_part = f"[{state_color}{c.state}{Colors.RESET}]"
        print_box_line(f"   {status_icon} {name_part} {state_part}", DISPLAY_WIDTH)
        print_box_line(f"      Img: {c.image}", DISPLAY_WIDTH)

        if c.ports:
            port_strs = [_format_port_string(p) for p in c.ports]
            print_box_line(f"      Net: {', '.join(port_strs)}", DISPLAY_WIDTH)

        container_stats = _find_stats_by_name(stats, c.name)
        if container_stats:
            cpu = container_stats.get("cpu", "-")
            mem = container_stats.get("mem_usage", "-")
            print_box_line(f"      {I_CPU} {cpu}  {I_MEM} {mem}", DISPLAY_WIDTH)

    print_box_line("", DISPLAY_WIDTH)
