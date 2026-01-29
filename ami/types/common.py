"""Common type definitions shared across modules.

All structured data uses TypedDict or Pydantic models with KNOWN fields.
NO generic container types allowed.
"""

from typing_extensions import TypedDict


# === Transcript/Logging Metadata ===
class TranscriptMetadata(TypedDict, total=False):
    """Metadata for transcript entries - all fields optional."""

    session_id: str
    duration: float
    exit_code: int
    model: str
    tokens: int


# === Process Environment ===
class ProcessEnvironment(TypedDict, total=False):
    """Environment variables for subprocess execution."""

    HOME: str
    USER: str
    PATH: str
    LANG: str
    LC_ALL: str
    PYTHONUNBUFFERED: str
    FORCE_COLOR: str
    DISABLE_AUTOUPDATER: str
    TERM: str
    SHELL: str


# === Container Data ===
class ContainerStatsData(TypedDict):
    """CPU/memory stats for a container."""

    name: str
    cpu: str
    mem_usage: str
    mem_percent: str


class ContainerSizeData(TypedDict):
    """Disk size information for a container."""

    name: str
    writable: str
    virtual: str


class VolumeData(TypedDict):
    """Volume mount information."""

    dst: str
    src: str
    type: str
    size: str


class PortData(TypedDict, total=False):
    """Raw port mapping data from JSON (multiple naming conventions)."""

    hostPort: str | int
    HostPort: str | int
    host_port: str | int
    containerPort: str | int
    ContainerPort: str | int
    container_port: str | int
    protocol: str
    Protocol: str


# === Policy/Banned Words ===
class PolicyPattern(TypedDict):
    """A policy pattern with pattern and reason."""

    pattern: str
    reason: str


class PolicyPatternWithException(TypedDict, total=False):
    """A policy pattern that may have an exception regex."""

    pattern: str
    reason: str
    exception_regex: str


class BannedPatternError(TypedDict):
    """An error from banned pattern detection."""

    file: str
    line: int
    pattern: str
    reason: str
    content: str


# === Systemd Data ===
class SystemdDetails(TypedDict, total=False):
    """Parsed systemd service details."""

    Id: str
    Description: str
    LoadState: str
    ActiveState: str
    SubState: str
    MainPID: str
    ExecMainStartTimestamp: str
    MemoryCurrent: str
    CPUUsageNSec: str
    FragmentPath: str
    ExecStart: str
    Restart: str
    UnitFileState: str


# === JSON Response Data ===
class JsonResponseData(TypedDict, total=False):
    """Generic JSON response with common fields."""

    id: str
    name: str
    type: str
    status: str
    error: str
    message: str


# === Google Drive API ===
class DriveFileResponse(TypedDict, total=False):
    """Response from Google Drive file operations."""

    id: str
    name: str
    webViewLink: str
    mimeType: str
    size: str
    createdTime: str
    modifiedTime: str


class DriveListResponse(TypedDict, total=False):
    """Response from Google Drive list operations."""

    files: list[DriveFileResponse]
    nextPageToken: str


# === Container Labels ===
class ContainerLabels(TypedDict, total=False):
    """Common container labels."""

    PODMAN_SYSTEMD_UNIT: str
    compose_project: str
    compose_service: str
    compose_config: str


# === Installation Results ===
class InstallationResult(TypedDict):
    """Result of component installation."""

    component_name: str
    success: bool
    error: str | None


# === Version Information ===
class VersionInfo(TypedDict):
    """Version information for a package."""

    current: str
    latest: str
    needs_update: bool


# === Bootstrap Components ===
class ComponentsByGroup(TypedDict, total=False):
    """Components organized by group name."""

    # Use total=False since all groups are optional
    ai_coding_assistants: list[object]
    containers_orchestration: list[object]
    development_tools: list[object]
    security_networking: list[object]
    document_processing: list[object]
    matrix_communication: list[object]
    miscellaneous: list[object]


# Note: ComponentsByGroup uses underscored keys for valid Python identifiers
# The actual group display names are converted to these keys


# === CLI Stream Events ===
class StreamDelta(TypedDict, total=False):
    """Delta content in stream events."""

    type: str
    text: str


class StreamEvent(TypedDict, total=False):
    """Stream event from CLI providers (Claude/Qwen/Gemini)."""

    type: str
    subtype: str
    session_id: str
    model: str
    message: str
    delta: StreamDelta
    event: "StreamEvent"  # Nested for Qwen


# === MCP Server Configuration ===
class MCPServerEntry(TypedDict, total=False):
    """Entry for an MCP server configuration."""

    command: str
    args: list[str]
    env: ProcessEnvironment
