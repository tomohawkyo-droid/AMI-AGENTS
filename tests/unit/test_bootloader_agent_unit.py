"""Unit tests for Core Agent."""

from unittest.mock import MagicMock, patch
import pytest

from ami.core.bootloader_agent import BootloaderAgent


class TestBootloaderAgent:
    """Unit tests for BootloaderAgent class."""

    @pytest.fixture
    def agent(self):
        """Fixture for BootloaderAgent."""
        with patch("ami.core.bootloader_agent.BootloaderAgent._get_banner", return_value="MOCKED BANNER"):
            yield BootloaderAgent()

    @patch("ami.core.bootloader_agent.check_command_safety")
    @patch("ami.core.bootloader_agent.ProcessExecutor")
    def test_execute_shell_safe(self, MockExecutor, mock_safety, agent):
        """execute_shell executes command if safe."""
        mock_safety.return_value = (True, "")
        
        # Mock extensions setup
        with patch.object(BootloaderAgent, "_load_extensions", return_value='eval "$(./ami-agent -i)"'):
            # Mock executor result
            mock_instance = MockExecutor.return_value
            mock_instance.run.return_value = {
                "stdout": "\x1b[31moutput\x1b[0m",
                "stderr": "",
                "returncode": 0
            }

            result = agent.execute_shell("echo test")

            assert "output" in result
            assert "\x1b" not in result # No ANSI codes
            
            # Verify call arguments
            mock_instance.run.assert_called_once()
            args, kwargs = mock_instance.run.call_args
            cmd_list = args[0]
            assert cmd_list[0] == "/bin/bash"
            assert cmd_list[1] == "-c"
            assert 'eval "$(./ami-agent -i)"' in cmd_list[2]
            assert "echo test" in cmd_list[2]

    @patch("ami.core.bootloader_agent.check_command_safety")
    @patch("ami.core.bootloader_agent.ProcessExecutor")
    def test_execute_shell_unsafe(self, MockExecutor, mock_safety, agent):
        """execute_shell blocks unsafe commands."""
        mock_safety.return_value = (False, "Violation detected")

        result = agent.execute_shell("rm -rf /")

        assert "🛑 BLOCKED:" in result
        assert "Violation detected" in result
        MockExecutor.return_value.run.assert_not_called()

    @patch("ami.core.bootloader_agent.get_agent_cli")
    def test_run_new_session(self, mock_get_cli, agent):
        """run() initiates new session if none provided."""
        mock_cli = MagicMock()
        mock_get_cli.return_value = mock_cli
        mock_cli.run_print.return_value = ("Agent response", {"session_id": "new-uuid"})

        response, session_id = agent.run("Hello")

        assert response == "Agent response"
        assert session_id == "new-uuid"
        
        # Verify prompt contains banner
        args, kwargs = mock_cli.run_print.call_args
        instruction = kwargs.get("instruction", "")
        assert "MOCKED BANNER" in instruction

    @patch("ami.core.bootloader_agent.get_agent_cli")
    def test_run_resume_session(self, mock_get_cli, agent):
        """run() uses existing session if provided."""
        mock_cli = MagicMock()
        mock_get_cli.return_value = mock_cli
        mock_cli.run_print.return_value = ("Resumed response", {})

        response, session_id = agent.run("Continue", session_id="existing-uuid")

        assert response == "Resumed response"
        assert session_id == "existing-uuid"
        
        # Verify config has session_id
        config = mock_get_cli.call_args[0][0]
        assert config.session_id == "existing-uuid"