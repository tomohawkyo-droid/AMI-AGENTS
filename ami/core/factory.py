"""Agent Runtime Factory.

Provides a centralized way to instantiate agent runtimes with dependencies injected.
"""

from ami.cli.factory import get_agent_cli
from ami.core.bootloader_agent import BootloaderAgent
from ami.core.interfaces import AgentRuntimeProtocol


class AgentFactory:
    """Factory for creating agent instances."""

    @staticmethod
    def create_bootloader(
        runtime: AgentRuntimeProtocol | None = None,
    ) -> BootloaderAgent:
        """Create a BootloaderAgent with injected runtime.

        Args:
            runtime: Optional runtime implementation. If None, uses default CLI factory.

        Returns:
            Configured BootloaderAgent instance.
        """
        if runtime is None:
            # Default to the standard CLI implementation
            runtime = get_agent_cli()

        return BootloaderAgent(runtime=runtime)
