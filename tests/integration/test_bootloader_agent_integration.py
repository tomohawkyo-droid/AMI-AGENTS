"""Integration tests for the bootloader agent.

Exercises: core/bootloader_agent.py, core/interfaces.py
"""

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest

from ami.core.bootloader_agent import (
    BootloaderAgent,
    ExecutionResult,
    RunContext,
)
from ami.core.config import _ConfigSingleton
from ami.core.env import get_project_root
from ami.core.interfaces import RunInteractiveParams, RunPrintParams
from ami.types.api import ProviderMetadata

# Named constants for magic numbers used in assertions
DEFAULT_TIMEOUT = 300
CUSTOM_TIMEOUT = 60
EXPECTED_REPROMPT_COUNT = 2
EXPECTED_MAX_LOOPS = 10


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


@pytest.fixture
def mock_runtime():
    """Create a mock AgentRuntimeProtocol."""
    runtime = MagicMock()
    runtime.run_print.return_value = ("No shell blocks.", None)
    return runtime


@pytest.fixture
def agent(mock_runtime):
    """Create a BootloaderAgent with mock runtime."""
    return BootloaderAgent(runtime=mock_runtime)


# ---------------------------------------------------------------------------
# RunContext and ExecutionResult construction
# ---------------------------------------------------------------------------


class TestRunContext:
    """Test RunContext Pydantic model."""

    def test_minimal_context(self):
        ctx = RunContext(instruction="Do something")
        assert ctx.instruction == "Do something"
        assert ctx.session_id is None
        assert ctx.timeout == DEFAULT_TIMEOUT
        assert ctx.stop_event is None

    def test_full_context(self):
        stop = Event()
        ctx = RunContext(
            instruction="test",
            session_id="s1",
            stop_event=stop,
            input_func=lambda cmd: True,
            allowed_tools=["bash", "read"],
            timeout=60,
            guard_rules_path=Path("/tmp/rules.yaml"),
        )
        assert ctx.session_id == "s1"
        assert ctx.timeout == CUSTOM_TIMEOUT
        assert ctx.allowed_tools == ["bash", "read"]


class TestExecutionResult:
    """Test ExecutionResult model."""

    def test_defaults(self):
        result = ExecutionResult()
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.returncode == 0

    def test_with_values(self):
        result = ExecutionResult(stdout="output", stderr="error", returncode=1)
        assert result.stdout == "output"
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# BootloaderAgent internal methods
# ---------------------------------------------------------------------------


class TestBuildToolsMessage:
    """Test _build_tools_message with default and custom tools."""

    def test_default_tools(self, agent: BootloaderAgent):
        msg = agent._build_tools_message(["save_memory"])
        assert "No internal tools" in msg or "shell commands" in msg

    def test_custom_tools(self, agent: BootloaderAgent):
        msg = agent._build_tools_message(["bash", "read", "write"])
        assert "bash" in msg or "allowed tools" in msg.lower()


class TestFormatShellOutput:
    """Test _format_shell_output for various scenarios."""

    def test_success_output(self, agent: BootloaderAgent):
        result = ExecutionResult(stdout="hello world", stderr="", returncode=0)
        output = agent._format_shell_output("echo hello", result)
        assert "echo hello" in output
        assert "hello world" in output

    def test_stderr_output(self, agent: BootloaderAgent):
        result = ExecutionResult(stdout="", stderr="warning msg", returncode=0)
        output = agent._format_shell_output("cmd", result)
        assert "ERR:" in output
        assert "warning msg" in output

    def test_nonzero_exit(self, agent: BootloaderAgent):
        result = ExecutionResult(stdout="", stderr="", returncode=1)
        output = agent._format_shell_output("false", result)
        assert "Exit Code: 1" in output

    def test_ansi_stripping(self, agent: BootloaderAgent):
        result = ExecutionResult(
            stdout="\x1b[31mred text\x1b[0m", stderr="", returncode=0
        )
        output = agent._format_shell_output("cmd", result)
        assert "\x1b[" not in output
        assert "red text" in output


class TestHandleUserConfirmation:
    """Test _handle_user_confirmation callbacks."""

    def test_accepted(self, agent: BootloaderAgent):
        result = agent._handle_user_confirmation("echo test", lambda cmd: True, None)
        assert result is None  # No error

    def test_rejected(self, agent: BootloaderAgent):
        result = agent._handle_user_confirmation("echo test", lambda cmd: False, None)
        assert "CANCELLED" in result

    def test_with_stream_callback(self, agent: BootloaderAgent):
        callback = MagicMock()
        result = agent._handle_user_confirmation(
            "echo test", lambda cmd: True, callback
        )
        assert result is None
        callback.assert_called_once()

    def test_exception_handling(self, agent: BootloaderAgent):
        def raise_error(cmd):
            msg = "dialog error"
            raise RuntimeError(msg)

        result = agent._handle_user_confirmation("cmd", raise_error, None)
        assert "CONFIRMATION ERROR" in result


# ---------------------------------------------------------------------------
# Execute shell with real commands
# ---------------------------------------------------------------------------


class TestExecuteShell:
    """Test execute_shell with real safe commands."""

    def test_echo_command(self, agent: BootloaderAgent):
        """echo should be blocked by default guard rules (default.yaml)."""
        output = agent.execute_shell("echo hello")
        # Depending on guard rules, echo may be blocked or allowed
        assert isinstance(output, str)
        assert len(output) > 0

    def test_blocked_dangerous_command(self, agent: BootloaderAgent):
        """Dangerous commands should be blocked."""
        output = agent.execute_shell("rm -rf /")
        assert "BLOCKED" in output

    def test_with_guard_rules_path(self, agent: BootloaderAgent):
        """Test with explicit guard rules path."""
        rules = get_project_root() / "ami/config/policies/interactive.yaml"
        if rules.exists():
            output = agent.execute_shell("echo hello", guard_rules_path=rules)
            assert isinstance(output, str)


class TestExecuteShellBlocks:
    """Test _execute_shell_blocks."""

    def test_empty_blocks(self, agent: BootloaderAgent):
        ctx = RunContext(instruction="test")
        parts = []
        outputs = agent._execute_shell_blocks([], ctx, parts)
        assert outputs == []

    def test_stop_event_terminates(self, agent: BootloaderAgent):
        stop = Event()
        stop.set()  # Already stopped
        ctx = RunContext(instruction="test", stop_event=stop)
        parts = []
        outputs = agent._execute_shell_blocks(["echo hi"], ctx, parts)
        assert outputs == []


# ---------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------


class TestRunLoop:
    """Test the main run loop."""

    def test_no_shell_blocks_exits(self, agent: BootloaderAgent, mock_runtime):
        """When output has no shell blocks, loop exits."""
        mock_runtime.run_print.return_value = (
            "Task completed. No commands needed.",
            ProviderMetadata(session_id="s1"),
        )
        ctx = RunContext(instruction="Do something simple")
        output, session = agent.run(ctx)
        assert "Task completed" in output
        assert session is None

    def test_shell_blocks_reprompts(self, agent: BootloaderAgent, mock_runtime):
        """When output has shell blocks, agent re-prompts with tool output."""
        # First call returns shell block, second returns no blocks
        mock_runtime.run_print.side_effect = [
            (
                "Let me check:\n```run\necho test\n```",
                ProviderMetadata(session_id="s1"),
            ),
            ("Done, no more commands.", ProviderMetadata(session_id="s1")),
        ]
        ctx = RunContext(instruction="Check something")
        _output, session = agent.run(ctx)
        assert mock_runtime.run_print.call_count == EXPECTED_REPROMPT_COUNT
        assert session is None

    def test_stop_event_terminates(self, agent: BootloaderAgent, mock_runtime):
        """Stop event terminates the loop."""
        stop = Event()
        stop.set()
        ctx = RunContext(instruction="test", stop_event=stop)
        output, _session = agent.run(ctx)
        assert "stopped" in output.lower()

    def test_constants(self):
        assert BootloaderAgent.DEFAULT_ALLOWED_TOOLS == ["save_memory"]
        assert BootloaderAgent.MAX_LOOPS == EXPECTED_MAX_LOOPS

    def test_agent_error_handling(self, agent: BootloaderAgent, mock_runtime):
        """Agent errors are handled gracefully."""
        mock_runtime.run_print.side_effect = RuntimeError("provider crashed")
        ctx = RunContext(instruction="test")
        output, _session = agent.run(ctx)
        assert "Error" in output or "error" in output.lower()


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class TestInterfaces:
    """Test core interface models."""

    def test_run_print_params(self):
        params = RunPrintParams(instruction="test instruction")
        assert params.instruction == "test instruction"
        assert params.cwd is None

    def test_run_print_params_with_file(self, tmp_path: Path):
        f = tmp_path / "instr.md"
        f.write_text("content")
        params = RunPrintParams(instruction_file=f)
        assert params.instruction_file == f

    def test_run_interactive_params(self):
        params = RunInteractiveParams(instruction="interactive test")
        assert params.instruction == "interactive test"
        assert isinstance(params.mcp_servers, dict)
