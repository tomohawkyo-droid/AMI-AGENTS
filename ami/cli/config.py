"""Configuration classes for agent execution."""

from typing import Any, Optional

from ami.cli.provider_type import ProviderType as CLIProvider
from ami.core.config import get_config
from ami.core.models import AgentConfig


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
    def worker(session_id: str | None = None) -> AgentConfig:
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
    def interactive(session_id: str | None = None, mcp_servers: dict[str, Any] | None = None) -> AgentConfig:
        """Interactive agent."""
        from ami.core.config import get_config
        
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