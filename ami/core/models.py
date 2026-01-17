"""Core data models for AMI Agents."""

from typing import Any, Optional
from ami.cli.provider_type import ProviderType as CLIProvider

class AgentConfig:
    """Configuration for an agent execution.

    Defines tools, model, hooks, timeout, and session settings for an agent.
    """

    def __init__(
        self,
        model: str,
        session_id: str,  # Session ID for execution tracking
        provider: CLIProvider,  # AI provider
        allowed_tools: list[str] | None = None,  # None = all tools allowed
        enable_hooks: bool = True,
        enable_streaming: bool | None = False,
        timeout: int | None = 180,  # None = no timeout (interactive)
        mcp_servers: dict[str, Any] | None = None,
        capture_content: bool = False,
        stream_callback: Any = None, # Optional callback(token)
        guard_rules_path: Any | None = None, # Optional path to custom guard rules
    ):
        self.model = model
        self.session_id = session_id
        self.provider = provider
        self.allowed_tools = allowed_tools
        self.enable_hooks = enable_hooks
        self.enable_streaming = enable_streaming
        self.timeout = timeout
        self.mcp_servers = mcp_servers
        self.capture_content = capture_content
        self.stream_callback = stream_callback
        self.guard_rules_path = guard_rules_path
