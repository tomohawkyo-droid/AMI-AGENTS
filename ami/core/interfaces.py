"""Core interfaces for AMI Agent orchestration.

This module defines the protocols that decouple core logic from interface implementations.
"""

from typing import Protocol, Any, Dict, Tuple, Optional
from pathlib import Path


class AgentRuntimeProtocol(Protocol):
    """Protocol defining the required interface for an agent runtime."""

    def run_print(
        self,
        instruction: str | Path | None = None,
        cwd: Path | None = None,
        agent_config: Any = None,
        instruction_file: Path | None = None,
        stdin: str | None = None,
        audit_log_path: Path | None = None,
    ) -> Tuple[str, Dict[str, Any] | None]:
        """Run agent in print mode."""
        ...

    def run_interactive(
        self,
        instruction: str,
        cwd: Path | None = None,
        session_id: str | None = None,
        mcp_servers: Dict[str, Any] | None = None,
    ) -> Tuple[str, Dict[str, Any] | None]:
        """Run agent interactively."""
        ...
