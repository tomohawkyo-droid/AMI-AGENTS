"""Configuration classes for agent execution."""

from typing import Any, Optional

from agents.ami.cli.provider_type import ProviderType as CLIProvider
from agents.ami.core.config import get_config


class AgentConfig:
    """Configuration for an agent execution.

    Defines tools, model, hooks, timeout, and session settings for an agent.

    NOTE: disallowed_tools is NOT stored here - it's computed automatically
    by the provider CLI implementation.
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


class AgentConfigPresets:
    """Common agent configuration presets.

    Identifies patterns behind audit agents, code quality agents, worker agents, etc.
    """

    @staticmethod
    def _get_defaults(role: str) -> tuple[CLIProvider, str]:
        """Get default provider and model for a role (worker or moderator)."""
        config = get_config()
        
        # 1. Try role-specific config
        provider_name = config.get(f"agent.{role}.provider")
        model = config.get(f"agent.{role}.model")
        
        # 2. Fallback to global agent provider
        if not provider_name:
            provider_name = config.get("agent.provider", "claude")
            
        try:
            provider = CLIProvider(provider_name)
        except ValueError:
            provider = CLIProvider.CLAUDE
            
        # 3. Fallback to provider default model
        if not model:
            model = config.get_provider_default_model(provider)
            
        return provider, model

    @staticmethod
    def worker(session_id: str) -> AgentConfig:
        """General worker agent: All tools, hooks enabled."""
        provider, model = AgentConfigPresets._get_defaults("worker")
        return AgentConfig(
            model=model,
            session_id=session_id,
            provider=provider,
            allowed_tools=None,
            enable_hooks=True,
            timeout=180,
        )

    @staticmethod
    def interactive(session_id: str, mcp_servers: dict[str, Any] | None = None) -> AgentConfig:
        """Interactive agent."""
        from agents.ami.core.config import get_config
        
        provider, model = AgentConfigPresets._get_defaults("worker")
        config = get_config()
        guard_rules_path = config.root / "scripts/config/patterns/interactive_agent_commands.yaml"

        return AgentConfig(
            model=model,
            session_id=session_id,
            provider=provider,
            allowed_tools=None,
            enable_hooks=True,
            timeout=None,
            mcp_servers=mcp_servers,
            guard_rules_path=guard_rules_path,
        )