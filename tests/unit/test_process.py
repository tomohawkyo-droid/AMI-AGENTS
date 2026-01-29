"""Unit tests for utils/process module."""

import selectors
from io import TextIOWrapper
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.types.common import ProcessEnvironment
from ami.types.results import SelectorEvent
from ami.utils.process import (
    SELECTOR_POLL_INTERVAL,
    TIMEOUT_RETURN_CODE,
    ProcessExecutor,
    ProcessResult,
    _create_result,
    _drain_pipes,
    _process_pipe_events,
)

EXPECTED_TIMEOUT_RETURN_CODE = 124
EXPECTED_POLL_INTERVAL = 0.1
EXPECTED_EXIT_CODE_42 = 42


class TestCreateResult:
    """Tests for _create_result helper function."""

    def test_creates_result_dict(self) -> None:
        """Test that result dict is created correctly."""
        result = _create_result("output", "error", 0)

        assert result["stdout"] == "output"
        assert result["stderr"] == "error"
        assert result["returncode"] == 0

    def test_with_non_zero_returncode(self) -> None:
        """Test result with non-zero return code."""
        result = _create_result("", "error message", 1)

        assert result["returncode"] == 1

    def test_with_timeout_returncode(self) -> None:
        """Test result with timeout return code."""
        result = _create_result("partial", "timed out", TIMEOUT_RETURN_CODE)

        assert result["returncode"] == TIMEOUT_RETURN_CODE


class TestConstants:
    """Tests for module constants."""

    def test_timeout_return_code(self) -> None:
        """Test TIMEOUT_RETURN_CODE value."""
        assert TIMEOUT_RETURN_CODE == EXPECTED_TIMEOUT_RETURN_CODE

    def test_selector_poll_interval(self) -> None:
        """Test SELECTOR_POLL_INTERVAL value."""
        assert SELECTOR_POLL_INTERVAL == EXPECTED_POLL_INTERVAL


class TestProcessExecutor:
    """Tests for ProcessExecutor class."""

    def test_default_work_dir(self) -> None:
        """Test that default work_dir is cwd."""
        executor = ProcessExecutor()
        assert executor.work_dir == Path.cwd()

    def test_custom_work_dir(self, tmp_path: Path) -> None:
        """Test that custom work_dir is used."""
        executor = ProcessExecutor(work_dir=tmp_path)
        assert executor.work_dir == tmp_path

    def test_run_simple_command(self, tmp_path: Path) -> None:
        """Test running a simple command."""
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run("echo hello")

        assert result["returncode"] == 0
        assert "hello" in result["stdout"]

    def test_run_command_list(self, tmp_path: Path) -> None:
        """Test running command as list."""
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run(["echo", "hello", "world"])

        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
        assert "world" in result["stdout"]

    def test_run_with_custom_cwd(self, tmp_path: Path) -> None:
        """Test running command in custom directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        executor = ProcessExecutor()

        result = executor.run("pwd", cwd=subdir)

        assert result["returncode"] == 0
        assert str(subdir) in result["stdout"]

    def test_run_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test running command in nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        executor = ProcessExecutor()

        result = executor.run("echo test", cwd=nonexistent)

        assert result["returncode"] == 1
        assert "does not exist" in result["stderr"]

    def test_run_with_environment_variables(self, tmp_path: Path) -> None:
        """Test running command with custom environment."""
        executor = ProcessExecutor(work_dir=tmp_path)
        env: ProcessEnvironment = {"PATH": "/usr/bin"}  # Type-safe subset
        # Use shell variable expansion which works with any env
        result = executor.run("echo $PATH", env=env)

        assert result["returncode"] == 0
        assert "/usr/bin" in result["stdout"]

    def test_run_captures_stderr(self, tmp_path: Path) -> None:
        """Test that stderr is captured."""
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run("echo error >&2")

        assert result["returncode"] == 0
        assert "error" in result["stderr"]

    def test_run_returns_nonzero_exit_code(self, tmp_path: Path) -> None:
        """Test that non-zero exit codes are captured."""
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run("exit 42")

        assert result["returncode"] == EXPECTED_EXIT_CODE_42

    def test_run_handles_command_not_found(self, tmp_path: Path) -> None:
        """Test handling of command not found."""
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run("nonexistent_command_xyz123")

        assert result["returncode"] != 0

    @patch("ami.utils.process.subprocess.Popen")
    def test_run_handles_popen_exception(self, mock_popen, tmp_path: Path) -> None:
        """Test handling of Popen exceptions."""
        mock_popen.side_effect = OSError("Failed to start")
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run("echo test")

        assert result["returncode"] == 1
        assert "Execution failed" in result["stderr"]


class TestProcessExecutorTimeout:
    """Tests for ProcessExecutor timeout handling."""

    def test_timeout_kills_process(self, tmp_path: Path) -> None:
        """Test that timeout kills long-running process."""
        executor = ProcessExecutor(work_dir=tmp_path)

        # Sleep for longer than timeout
        result = executor.run("sleep 10", timeout=1)

        assert result["returncode"] == TIMEOUT_RETURN_CODE
        assert "timed out" in result["stderr"]

    def test_fast_command_with_timeout(self, tmp_path: Path) -> None:
        """Test that fast commands complete before timeout."""
        executor = ProcessExecutor(work_dir=tmp_path)

        result = executor.run("echo fast", timeout=10)

        assert result["returncode"] == 0
        assert "fast" in result["stdout"]


class TestDrainPipes:
    """Tests for _drain_pipes helper function."""

    @patch("ami.utils.process.selectors.DefaultSelector")
    def test_drain_pipes_reads_remaining(self, mock_selector_class) -> None:
        """Test that drain_pipes reads remaining data."""
        stdout_data: list[str] = []
        stderr_data: list[str] = []

        # Create mock selector and key
        mock_sel = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = "remaining data"

        mock_key = MagicMock()
        mock_key.fileobj = mock_file
        mock_key.data = stdout_data

        mock_sel.get_map.return_value.values.return_value = [mock_key]

        _drain_pipes(mock_sel, stdout_data, stderr_data)

        assert "remaining data" in stdout_data
        mock_sel.unregister.assert_called_once_with(mock_file)


class TestProcessPipeEvents:
    """Tests for _process_pipe_events helper function."""

    def test_processes_read_events(self) -> None:
        """Test that read events are processed."""
        data_list: list[str] = []

        # Create mock that passes isinstance check
        mock_file = MagicMock(spec=TextIOWrapper)
        mock_file.readline.return_value = "line data\n"

        # Create mock key and selector
        mock_key = MagicMock()
        mock_key.fileobj = mock_file
        mock_key.data = data_list

        mock_sel = MagicMock()
        events = [SelectorEvent(key=mock_key, mask=selectors.EVENT_READ)]

        _process_pipe_events(mock_sel, events)

        assert "line data\n" in data_list

    def test_unregisters_on_eof(self) -> None:
        """Test that empty read (EOF) unregisters file."""
        data_list: list[str] = []

        mock_file = MagicMock(spec=TextIOWrapper)
        mock_file.readline.return_value = ""  # EOF

        mock_key = MagicMock()
        mock_key.fileobj = mock_file
        mock_key.data = data_list

        mock_sel = MagicMock()
        events = [SelectorEvent(key=mock_key, mask=selectors.EVENT_READ)]

        _process_pipe_events(mock_sel, events)

        mock_sel.unregister.assert_called_once_with(mock_file)

    def test_skips_non_text_io_wrapper(self) -> None:
        """Test that non-TextIOWrapper objects are skipped."""
        data_list: list[str] = []

        # Create mock without TextIOWrapper spec
        mock_file = MagicMock()  # Not a TextIOWrapper

        mock_key = MagicMock()
        mock_key.fileobj = mock_file
        mock_key.data = data_list

        mock_sel = MagicMock()
        events = [SelectorEvent(key=mock_key, mask=selectors.EVENT_READ)]

        _process_pipe_events(mock_sel, events)

        # readline should not have been called
        mock_file.readline.assert_not_called()


class TestProcessResultTypedDict:
    """Tests for ProcessResult TypedDict."""

    def test_create_process_result(self) -> None:
        """Test creating a ProcessResult dict."""
        result: ProcessResult = {
            "stdout": "output",
            "stderr": "error",
            "returncode": 0,
        }
        assert result["stdout"] == "output"
        assert result["stderr"] == "error"
        assert result["returncode"] == 0
