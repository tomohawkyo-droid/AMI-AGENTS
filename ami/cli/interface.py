"""Abstract interface for agent CLI operations."""

from abc import ABC, abstractmethod

from ami.core.interfaces import RunInteractiveParams, RunPrintParams
from ami.types.results import ProviderResult


class AgentCLI(ABC):
    """Abstract base class defining the interface for agent interactions."""

    @abstractmethod
    def run_interactive(
        self,
        params: RunInteractiveParams | None = None,
    ) -> ProviderResult:
        """Run agent interactively with CLI.

        Args:
            params: RunInteractiveParams with instruction, cwd,
                session_id, mcp_servers

        Returns:
            ProviderResult with (output, metadata) where metadata includes session info

        Raises:
            AgentError: If agent execution fails
        """

    @abstractmethod
    def run_print(
        self,
        params: RunPrintParams | None = None,
    ) -> ProviderResult:
        """Run agent in print mode with CLI.

        Args:
            params: RunPrintParams with instruction, cwd, agent_config,
                instruction_file, stdin

        Returns:
            ProviderResult with (output, metadata) where metadata includes session info

        Raises:
            AgentError: If agent execution fails
        """
