"""Result types for function return values.

Provides NamedTuples that support tuple unpacking while adding named field access.
"""

from selectors import SelectorKey
from typing import TYPE_CHECKING, NamedTuple

from .api import ProviderMetadata, StreamMetadata

if TYPE_CHECKING:
    from .common import ContainerLabels
    from .status import PortMapping


class ParseResult(NamedTuple):
    """Result from parsing a stream message."""

    text: str
    metadata: StreamMetadata | None


class ProviderResult(NamedTuple):
    """Result from provider execution."""

    output: str
    metadata: ProviderMetadata | None


class SafetyCheckResult(NamedTuple):
    """Result from a safety check."""

    is_safe: bool
    message: str


class ReadLineResult(NamedTuple):
    """Result from reading a streaming line."""

    line: str | None
    is_complete: bool


class ComposeInfo(NamedTuple):
    """Docker compose information extracted from ExecStart."""

    managed_container: str | None
    compose_file: str | None
    compose_profiles: list[str]


class LegendRender(NamedTuple):
    """Rendered legend lines."""

    icons_line: str
    labels_line: str


class BinaryCheckResult(NamedTuple):
    """Result from checking if a binary exists."""

    exists: bool
    version: str | None


class ConfigDefaults(NamedTuple):
    """Default configuration values."""

    provider: str
    model: str


class FormattedPrefix(NamedTuple):
    """Prefix with formatting and visible width."""

    formatted: str
    visible: str


class GroupRange(NamedTuple):
    """Range information for a dialog group."""

    header_idx: int
    start: int
    end: int


class FileViolation(NamedTuple):
    """A file that violates a policy."""

    filepath: str
    line_count: int


class TempFileEntry(NamedTuple):
    """A temporary file with its size."""

    path: str
    size_bytes: int


class ComponentStatusEntry(NamedTuple):
    """Status entry for a single component."""

    name: str
    installed: bool
    version: str | None
    description: str
    category: str = ""


class ColorPair(NamedTuple):
    """A pair of foreground and background colors."""

    fg: int
    bg: int


class SelectorEvent(NamedTuple):
    """A selector event with key and mask."""

    key: SelectorKey
    mask: int


class DeleteResult(NamedTuple):
    """Result from deleting items."""

    deleted: int
    errors: int


class ScanResult(NamedTuple):
    """Result from scanning for files."""

    found: list[str]
    large: list[str]


class ContainerStatusDisplay(NamedTuple):
    """Display info for container status."""

    icon: str
    color: str


class CharWithOrdinal(NamedTuple):
    """Character with its ordinal value."""

    char: str
    ordinal: int


class ModeHandler(NamedTuple):
    """Mode handler with condition and handler function."""

    condition: str | bool | None
    handler: object  # Callable[[], int]


class KeyHandleResult(NamedTuple):
    """Result from handling a key press in selection dialog."""

    should_continue: bool
    result: object  # SelectableItem | SelectableItemDict | list | None


class ContainerInspectInfo(NamedTuple):
    """Port and label info from container inspection."""

    ports: "list[PortMapping]"
    labels: "ContainerLabels"


class NamedComponentStatus(NamedTuple):
    """Component status paired with its name for collection use."""

    name: str
    installed: bool
    version: str | None
    path: str | None
