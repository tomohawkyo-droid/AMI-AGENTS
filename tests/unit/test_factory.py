"""Unit tests for AgentFactory."""

from unittest.mock import MagicMock, patch

from ami.core.bootloader_agent import BootloaderAgent
from ami.core.factory import AgentFactory


class TestAgentFactory:
    @patch("ami.core.factory.get_agent_cli")
    def test_create_bootloader_default(self, mock_get_cli):
        """Test creating bootloader with default runtime."""
        agent = AgentFactory.create_bootloader()

        assert isinstance(agent, BootloaderAgent)
        assert agent.runtime == mock_get_cli.return_value

    def test_create_bootloader_injected(self):
        """Test creating bootloader with injected runtime."""
        mock_runtime = MagicMock()
        agent = AgentFactory.create_bootloader(runtime=mock_runtime)

        assert isinstance(agent, BootloaderAgent)
        assert agent.runtime == mock_runtime
