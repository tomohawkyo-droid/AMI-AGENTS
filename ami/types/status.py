"""Type definitions for system status display.

Provides Pydantic models for systemd services and container information.
"""

from pydantic import BaseModel, Field

from ami.types.common import (
    ContainerLabels,
    ContainerSizeData,
    ContainerStatsData,
    empty_labels,
)


class PortMapping(BaseModel):
    """Port mapping information for containers."""

    host_port: int | None = Field(default=None, alias="hostPort")
    container_port: int | None = Field(default=None, alias="containerPort")
    protocol: str = "tcp"

    class Config:
        populate_by_name = True


class PodmanContainer(BaseModel):
    """Container information from podman."""

    id: str
    name: str
    state: str = ""
    status: str = ""
    ports: list[PortMapping] = Field(default_factory=list)
    image: str = ""
    labels: ContainerLabels = Field(default_factory=empty_labels)
    stats: ContainerStatsData | None = None
    size: ContainerSizeData | None = None


class SystemdService(BaseModel):
    """Systemd service information."""

    name: str
    scope: str = ""
    active: str = ""
    sub: str = ""
    path: str = ""
    pid: str = "0"
    managed_container: str | None = None
    compose_file: str | None = None
    compose_profiles: list[str] = Field(default_factory=list)
    # Enhanced fields
    restart: str = ""  # Restart policy (always, on-failure, no)
    enabled: str = ""  # UnitFileState (enabled, disabled, static)
    memory_bytes: int = 0  # MemoryCurrent in bytes
    cpu_ns: int = 0  # CPUUsageNSec
    start_time: str = ""  # ExecMainStartTimestamp
    description: str = ""  # Description
    exec_start: str = ""  # ExecStart command


class ServiceDisplayInfo(BaseModel):
    """Holds processed service information for display."""

    row_type: str
    row_details: list[str] = Field(default_factory=list)
    child_items: list[PodmanContainer] = Field(default_factory=list)
    ports_str: str = ""
