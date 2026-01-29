"""Core interfaces for AMI Agent orchestration.

This module defines protocols that decouple core logic from implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ami.types.api import MCPServerConfig
from ami.types.config import AgentConfig
from ami.types.results import ProviderResult

if TYPE_CHECKING:
    pass  # All imports are now runtime imports


class RunPrintParams(BaseModel):
    """Parameters for run_print method."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    instruction: str | Path | None = None
    cwd: Path | None = None
    agent_config: AgentConfig | None = None
    instruction_file: Path | None = None
    stdin: str | None = None


class RunInteractiveParams(BaseModel):
    """Parameters for run_interactive method."""

    instruction: str = ""
    cwd: Path | None = None
    session_id: str | None = None
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)


class AgentRuntimeProtocol(Protocol):
    """Protocol defining the required interface for an agent runtime."""

    def run_print(
        self,
        params: RunPrintParams | None = None,
    ) -> ProviderResult:
        """Run agent in print mode."""
        ...

    def run_interactive(
        self,
        params: RunInteractiveParams | None = None,
    ) -> ProviderResult:
        """Run agent interactively."""
        ...
