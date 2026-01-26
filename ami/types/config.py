"""Configuration types for AMI Agents.

Provides Pydantic models for agent configuration, replacing dataclasses.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ami.types.api import MCPServerConfig

if TYPE_CHECKING:
    from ami.types.events import StreamEvent


# Type alias for stream callbacks
StreamCallback = Callable[["StreamEvent"], None] | None


class AgentConfig(BaseModel):
    """Configuration for an agent execution.

    Defines tools, model, hooks, timeout, and session settings for an agent.
    This Pydantic model replaces the previous dataclass implementation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str
    provider: object  # CLIProvider instance - using object to avoid circular imports
    session_id: str | None = None
    allowed_tools: list[str] | None = None
    enable_hooks: bool = True
    enable_streaming: bool | None = False
    timeout: int | None = 180
    mcp_servers: dict[str, MCPServerConfig] | None = None
    capture_content: bool = False
    stream_callback: StreamCallback = None
    guard_rules_path: Path | None = Field(default=None)
