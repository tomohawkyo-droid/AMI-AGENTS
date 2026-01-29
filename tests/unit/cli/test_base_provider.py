"""Unit tests for ami/cli/base_provider.py."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.base_provider import CLIProvider
from ami.core.interfaces import RunInteractiveParams, RunPrintParams
from ami.types.config import AgentConfig
from ami.types.results import ParseResult, ProviderResult


class MockCLIProvider(CLIProvider):
    """Concrete implementation for testing."""

    def _build_command(
        self,
        instruction: str,
        cwd: Path | None,
        config: AgentConfig,
    ) -> list[str]:
        return ["test-cli", "--prompt", instruction]

    def _parse_stream_message(
        self,
        line: str,
        cmd: list[str],
        line_count: int,
        agent_config: AgentConfig | None,
    ) -> ParseResult:
        return ParseResult(line, None)

    def _get_default_config(self) -> AgentConfig:
        return AgentConfig(
            model="test-model",
            provider=self,
        )


class TestCLIProviderInit:
    """Tests for CLIProvider initialization."""

    def test_init_sets_current_process_to_none(self):
        """Test initialization sets current_process to None."""
        provider = MockCLIProvider()
        assert provider.current_process is None


class TestKillCurrentProcess:
    """Tests for kill_current_process method."""

    def test_returns_false_when_no_process(self):
        """Test returns False when no current process."""
        provider = MockCLIProvider()
        result = provider.kill_current_process()
        assert result is False

    def test_terminates_running_process(self):
        """Test terminates a running process."""
        provider = MockCLIProvider()
        mock_process = MagicMock()
        provider.current_process = mock_process

        result = provider.kill_current_process()

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()
        assert provider.current_process is None

    def test_kills_process_on_timeout(self):
        """Test kills process when terminate times out."""
        provider = MockCLIProvider()
        mock_process = MagicMock()
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=2),
            None,
        ]
        provider.current_process = mock_process

        result = provider.kill_current_process()

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert provider.current_process is None

    def test_handles_process_lookup_error(self):
        """Test handles ProcessLookupError gracefully."""
        provider = MockCLIProvider()
        mock_process = MagicMock()
        mock_process.terminate.side_effect = ProcessLookupError()
        provider.current_process = mock_process

        result = provider.kill_current_process()

        assert result is True
        assert provider.current_process is None


class TestRunInteractive:
    """Tests for run_interactive method."""

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_with_default_params(self, mock_logger_cls, mock_execute):
        """Test run_interactive with default params."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)

        provider = MockCLIProvider()
        output, _metadata = provider.run_interactive()

        assert output == "output"
        mock_execute.assert_called_once()

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_with_params(self, mock_logger_cls, mock_execute):
        """Test run_interactive with custom params."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)

        provider = MockCLIProvider()
        params = RunInteractiveParams(
            instruction="Test instruction",
            cwd=Path("/tmp"),
            session_id="test-session",
        )
        output, _metadata = provider.run_interactive(params)

        assert output == "output"
        mock_execute.assert_called_once()

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_logs_user_message(self, mock_logger_cls, mock_execute):
        """Test logs user message."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)

        provider = MockCLIProvider()
        params = RunInteractiveParams(instruction="Hello")
        provider.run_interactive(params)

        mock_logger.log_user_message.assert_called_once()


class TestRunPrint:
    """Tests for run_print method."""

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_with_instruction(self, mock_logger_cls, mock_execute):
        """Test run_print with instruction."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)

        provider = MockCLIProvider()
        params = RunPrintParams(instruction="Test instruction")
        output, _metadata = provider.run_print(params)

        assert output == "output"

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    @patch("ami.cli.base_provider.load_instruction_with_replacements")
    def test_with_instruction_file(
        self, mock_load, mock_logger_cls, mock_execute, tmp_path
    ):
        """Test run_print with instruction_file."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)
        mock_load.return_value = "File content"

        provider = MockCLIProvider()
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Test")
        params = RunPrintParams(instruction_file=instruction_file)
        output, _metadata = provider.run_print(params)

        assert output == "output"
        mock_load.assert_called_once_with(instruction_file)

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_raises_with_both_instruction_and_file(
        self, mock_logger_cls, mock_execute, tmp_path
    ):
        """Test raises ValueError when both instruction and file provided."""
        provider = MockCLIProvider()
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Test")
        params = RunPrintParams(
            instruction="Test",
            instruction_file=instruction_file,
        )

        with pytest.raises(ValueError, match="Cannot provide both"):
            provider.run_print(params)

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_raises_when_instruction_is_path(
        self, mock_logger_cls, mock_execute, tmp_path
    ):
        """Test raises ValueError when instruction is a Path object."""
        provider = MockCLIProvider()
        params = RunPrintParams(instruction=tmp_path)

        with pytest.raises(ValueError, match="instruction_file parameter"):
            provider.run_print(params)

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_raises_when_instruction_is_none(self, mock_logger_cls, mock_execute):
        """Test raises ValueError when instruction is None."""
        provider = MockCLIProvider()
        params = RunPrintParams()  # instruction is None, instruction_file is None

        with pytest.raises(
            ValueError, match="instruction or instruction_file is required"
        ):
            provider.run_print(params)

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_uses_default_config_when_not_provided(self, mock_logger_cls, mock_execute):
        """Test uses default config when not provided."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)

        provider = MockCLIProvider()
        params = RunPrintParams(instruction="Test")
        provider.run_print(params)

        # Verify execute_streaming was called with config from _get_default_config
        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["agent_config"].model == "test-model"

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_includes_stdin_in_log(self, mock_logger_cls, mock_execute):
        """Test stdin data is included in log message."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.return_value = ProviderResult("output", None)

        provider = MockCLIProvider()
        params = RunPrintParams(instruction="Test", stdin="input data")
        provider.run_print(params)

        # Check that log_user_message was called with stdin info
        call_args = mock_logger.log_user_message.call_args[0][0]
        assert "input data" in call_args


class TestExecuteWithTimeout:
    """Tests for _execute_with_timeout method."""

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_logs_error_on_exception(self, mock_logger_cls, mock_execute):
        """Test logs error when execution fails."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_execute.side_effect = Exception("Execution failed")

        provider = MockCLIProvider()
        config = provider._get_default_config()

        with pytest.raises(Exception, match="Execution failed"):
            provider._execute_with_timeout("test", None, config)

        mock_logger.log_error.assert_called_once_with("Execution failed")

    @patch("ami.cli.base_provider.execute_streaming")
    @patch("ami.cli.base_provider.TranscriptLogger")
    def test_logs_assistant_message_on_success(self, mock_logger_cls, mock_execute):
        """Test logs assistant message on successful execution."""
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger
        mock_metadata = MagicMock()
        mock_execute.return_value = ProviderResult("output text", mock_metadata)

        provider = MockCLIProvider()
        config = provider._get_default_config()
        output, metadata = provider._execute_with_timeout("test", None, config)

        assert output == "output text"
        assert metadata == mock_metadata
        mock_logger.log_assistant_message.assert_called_once_with(
            "output text", mock_metadata
        )
