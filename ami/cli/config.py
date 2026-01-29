"""Configuration classes for agent execution."""

from ami.cli.provider_type import ProviderType as CLIProvider
from ami.core.config import get_config
from ami.types.api import MCPServerConfig
from ami.types.config import AgentConfig
from ami.types.results import ConfigDefaults

__all__ = ["AgentConfig", "AgentConfigPresets"]


class AgentConfigPresets:
    """Common agent configuration presets.

    Identifies patterns behind audit agents, code quality agents, worker agents, etc.
    """

    @staticmethod
    def _get_defaults(role: str) -> ConfigDefaults:
        """Get default provider and model for a role (worker or moderator)."""
        config = get_config()

        provider_name = config.get_value(f"agent.{role}.provider")
        model = config.get_value(f"agent.{role}.model")

        if not provider_name:
            provider_name = config.get_value("agent.provider", "claude")

        try:
            provider = CLIProvider(str(provider_name))
        except ValueError:
            provider = CLIProvider.CLAUDE

        if not model:
            model = config.get_provider_default_model(provider)

        return ConfigDefaults(provider.value, str(model))

    @staticmethod
    def worker(session_id: str | None = None) -> AgentConfig:
        """General worker agent: All tools, hooks enabled."""
        defaults = AgentConfigPresets._get_defaults("worker")
        return AgentConfig(
            model=defaults.model,
            session_id=session_id,
            provider=CLIProvider(defaults.provider),
            allowed_tools=None,
            enable_hooks=True,
            timeout=180,
        )

    @staticmethod
    def interactive(
        session_id: str | None = None,
        mcp_servers: list[MCPServerConfig] | None = None,
    ) -> AgentConfig:
        """Interactive agent."""
        defaults = AgentConfigPresets._get_defaults("worker")
        config = get_config()
        guard_rules_path = config.root / "ami/config/policies/interactive.yaml"

        return AgentConfig(
            model=defaults.model,
            session_id=session_id,
            provider=CLIProvider(defaults.provider),
            allowed_tools=None,
            enable_hooks=True,
            timeout=None,
            mcp_servers=mcp_servers,
            guard_rules_path=guard_rules_path,
        )
