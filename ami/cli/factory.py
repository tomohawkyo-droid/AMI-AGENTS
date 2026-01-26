"""Factory function to get agent CLI instances."""

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.config import AgentConfig
from ami.cli.gemini_cli import GeminiAgentCLI
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.cli.qwen_cli import QwenAgentCLI
from ami.core.config import get_config


def get_agent_cli(agent_config: AgentConfig | None = None) -> AgentCLI:
    """Factory function to get agent CLI instance.

    Args:
        agent_config: Agent configuration containing provider information.
                     If not specified, uses global default from config.

    Returns:
        Agent CLI instance for the specified provider
    """
    if agent_config and agent_config.provider:
        provider = agent_config.provider
    else:
        # Fetch global default from config
        config = get_config()
        provider_name = config.get_value("agent.provider", "claude")
        try:
            provider = ProviderType(str(provider_name))
        except ValueError:
            provider = ProviderType.CLAUDE

    if provider == ProviderType.CLAUDE:
        return ClaudeAgentCLI()
    if provider == ProviderType.QWEN:
        return QwenAgentCLI()
    if provider == ProviderType.GEMINI:
        return GeminiAgentCLI()

    return ClaudeAgentCLI()
