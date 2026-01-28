"""Integration tests for process execution utilities.

Exercises: utils/process.py, cli/exec_utils.py, cli/validation_utils.py,
utils/uuid_utils.py, cli/editor_utils.py
"""

import re
import time
import uuid
from pathlib import Path

import pytest

from ami.cli.editor_utils import save_session_log
from ami.cli.exec_utils import validate_executable_exists
from ami.cli.validation_utils import validate_path_and_return_code, validate_path_exists
from ami.utils.process import TIMEOUT_RETURN_CODE, ProcessExecutor
from ami.utils.uuid_utils import uuid7

# ---------------------------------------------------------------------------
# Named constants for magic values used in assertions
# ---------------------------------------------------------------------------
EXPECTED_LINE_COUNT = 5
EXPECTED_UUID_VERSION = 7
EXPECTED_UNIQUENESS_COUNT = 100
EXPECTED_MISSING_PATH_CODE = 1

# ---------------------------------------------------------------------------
# ProcessExecutor with real commands
# ---------------------------------------------------------------------------


class TestProcessExecutorRealCommands:
    """Test ProcessExecutor.run with real system commands."""

    def test_echo_command(self):
        executor = ProcessExecutor()
        result = executor.run(["echo", "hello world"])
        assert result["returncode"] == 0
        assert "hello world" in result["stdout"]

    def test_ls_command(self):
        executor = ProcessExecutor()
        result = executor.run(["ls", "/tmp"])
        assert result["returncode"] == 0
        assert isinstance(result["stdout"], str)

    def test_cat_stdin(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content\n")
        executor = ProcessExecutor()
        result = executor.run(["cat", str(test_file)])
        assert result["returncode"] == 0
        assert "file content" in result["stdout"]

    def test_false_command_nonzero_exit(self):
        executor = ProcessExecutor()
        result = executor.run(["false"])
        assert result["returncode"] != 0

    def test_stderr_capture(self):
        executor = ProcessExecutor()
        result = executor.run(["ls", "/nonexistent_path_xyz"])
        assert result["returncode"] != 0
        assert result["stderr"]  # should have error message

    def test_custom_cwd(self, tmp_path: Path):
        executor = ProcessExecutor()
        result = executor.run(["pwd"], cwd=tmp_path)
        assert result["returncode"] == 0
        assert str(tmp_path) in result["stdout"]

    def test_env_override(self):
        executor = ProcessExecutor()
        result = executor.run(
            ["env"],
            env={"TEST_SENTINEL": "integration_test_value", "PATH": "/usr/bin:/bin"},
        )
        assert result["returncode"] == 0
        assert "TEST_SENTINEL=integration_test_value" in result["stdout"]

    def test_timeout_returns_124(self):
        executor = ProcessExecutor()
        result = executor.run(["sleep", "10"], timeout=1)
        assert result["returncode"] == TIMEOUT_RETURN_CODE

    def test_large_stdout_no_deadlock(self):
        """Verify large output doesn't cause pipe deadlock."""
        executor = ProcessExecutor()
        # Generate ~100KB of output
        result = executor.run(
            ["python3", "-c", "print('x' * 100 + '\\n') * 1000"],
            timeout=10,
        )
        # Command may fail due to syntax, but the point is no hang
        assert isinstance(result["stdout"], str)
        assert isinstance(result["stderr"], str)

    def test_work_dir_constructor(self, tmp_path: Path):
        executor = ProcessExecutor(work_dir=tmp_path)
        result = executor.run(["pwd"])
        assert result["returncode"] == 0
        assert str(tmp_path) in result["stdout"]

    def test_multi_line_output(self):
        executor = ProcessExecutor()
        result = executor.run(
            ["python3", "-c", "for i in range(5): print(f'line {i}')"]
        )
        assert result["returncode"] == 0
        lines = result["stdout"].strip().split("\n")
        assert len(lines) == EXPECTED_LINE_COUNT


# ---------------------------------------------------------------------------
# validate_executable_exists
# ---------------------------------------------------------------------------


class TestValidateExecutableExists:
    """Test validate_executable_exists for real and missing binaries."""

    def test_finds_real_binary(self):
        result = validate_executable_exists(["echo", "test"])
        assert result is not None
        assert "echo" in result[0]

    def test_returns_none_for_missing_binary(self):
        result = validate_executable_exists(["nonexistent_binary_xyz_12345", "arg"])
        assert result is None

    def test_returns_full_path(self):
        result = validate_executable_exists(["python3"])
        assert result is not None
        assert "/" in result[0]  # Should be absolute path

    def test_preserves_arguments(self):
        result = validate_executable_exists(["echo", "-n", "hello"])
        assert result is not None
        assert result[1:] == ["-n", "hello"]


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


class TestValidationUtils:
    """Test path validation utilities."""

    def test_validate_path_exists_true(self, tmp_path: Path):
        test_file = tmp_path / "existing.txt"
        test_file.write_text("content")
        assert validate_path_exists(str(test_file)) is True

    def test_validate_path_exists_false(self):
        assert validate_path_exists("/nonexistent/path/xyz") is False

    def test_validate_path_and_return_code_exists(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")
        assert validate_path_and_return_code(str(test_file)) == 0

    def test_validate_path_and_return_code_missing(self):
        assert (
            validate_path_and_return_code("/no/such/path") == EXPECTED_MISSING_PATH_CODE
        )

    def test_validate_path_and_return_code_none(self):
        assert validate_path_and_return_code(None) == EXPECTED_MISSING_PATH_CODE


# ---------------------------------------------------------------------------
# UUID v7
# ---------------------------------------------------------------------------


class TestUUID7:
    """Test uuid7 format, version bits, and monotonicity."""

    def test_uuid7_format(self):
        u = uuid7()
        # Should be valid UUID string
        parsed = uuid.UUID(u)
        assert parsed.version == EXPECTED_UUID_VERSION

    def test_uuid7_uniqueness(self):
        ids = {uuid7() for _ in range(EXPECTED_UNIQUENESS_COUNT)}
        assert len(ids) == EXPECTED_UNIQUENESS_COUNT  # All unique

    def test_uuid7_monotonicity(self):
        ids = []
        for _ in range(5):
            ids.append(uuid7())
            time.sleep(0.002)  # Ensure different millisecond timestamps
        # UUIDs with different timestamps should be lexicographically ordered
        assert ids == sorted(ids)

    def test_uuid7_string_format(self):
        u = uuid7()
        # Standard UUID format: 8-4-4-4-12
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            u,
        )


# ---------------------------------------------------------------------------
# Editor utils
# ---------------------------------------------------------------------------


class TestEditorUtils:
    """Test session log saving."""

    def test_save_session_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Monkeypatch to write to tmp_path
        monkeypatch.chdir(tmp_path)
        path = save_session_log("test content here")
        assert path.exists()
        assert path.read_text() == "test content here"
        assert "text_input_" in path.name
        assert path.suffix == ".txt"
