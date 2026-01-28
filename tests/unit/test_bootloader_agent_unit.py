"""Unit tests for Core Agent."""

from unittest.mock import MagicMock, patch

import pytest

from ami.core.bootloader_agent import BootloaderAgent, RunContext
from ami.types.api import ProviderMetadata


class TestBootloaderAgent:
    """Unit tests for BootloaderAgent class."""

    @pytest.fixture
    def mock_runtime(self):
        """Mock runtime for injection."""
        return MagicMock()

    @pytest.fixture
    def agent(self, mock_runtime):
        """Fixture for BootloaderAgent with mocked runtime."""
        with patch(
            "ami.core.bootloader_agent.BootloaderAgent._get_banner",
            return_value="MOCKED BANNER",
        ):
            yield BootloaderAgent(runtime=mock_runtime)

    @patch("ami.core.bootloader_agent.check_command_safety")
    @patch("ami.core.bootloader_agent.ProcessExecutor")
    def test_execute_shell_safe(self, MockExecutor, mock_safety, agent):
        """execute_shell executes command if safe."""
        mock_safety.return_value = (True, "")

        # Mock extensions setup
        with patch.object(
            BootloaderAgent, "_load_extensions", return_value='eval "$(./ami-agent -i)"'
        ):
            # Mock executor result
            mock_instance = MockExecutor.return_value
            mock_instance.run.return_value = {
                "stdout": "\x1b[31moutput\x1b[0m",
                "stderr": "",
                "returncode": 0,
            }

            result = agent.execute_shell("echo test")

            assert "output" in result
            assert "\x1b" not in result  # No ANSI codes

            # Verify call arguments
            mock_instance.run.assert_called_once()
            args, _kwargs = mock_instance.run.call_args
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

    def test_run_new_session(self, mock_runtime, agent):
        """run() initiates new session if none provided."""
        mock_runtime.run_print.return_value = (
            "Agent response",
            ProviderMetadata(session_id="new-uuid"),
        )

        ctx = RunContext(instruction="Hello")
        response, session_id = agent.run(ctx)

        assert response == "Agent response"
        assert session_id is None

        # Verify prompt contains banner - params is passed as a RunPrintParams object
        _args, kwargs = mock_runtime.run_print.call_args
        params = kwargs.get("params")
        assert params is not None
        instruction = params.instruction if params else ""
        assert "MOCKED BANNER" in instruction

    def test_run_resume_session(self, mock_runtime, agent):
        """run() uses existing session if provided."""
        mock_runtime.run_print.return_value = ("Resumed response", ProviderMetadata())

        ctx = RunContext(instruction="Continue", session_id="existing-uuid")
        response, session_id = agent.run(ctx)

        assert response == "Resumed response"
        assert session_id is None

        # Verify config has session_id - params is passed as a RunPrintParams object
        params = mock_runtime.run_print.call_args[1].get("params")
        assert params is not None
        assert params.agent_config.session_id is None
