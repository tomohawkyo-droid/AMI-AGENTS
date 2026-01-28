"""Integration tests for the streaming pipeline.

Exercises: cli/stream_processor.py, cli/streaming.py, cli/streaming_utils.py,
types/events.py, types/api.py, types/config.py, cli/exceptions.py
"""

import time
from pathlib import Path

from ami.cli.exceptions import (
    AgentCommandNotFoundError,
    AgentError,
    AgentExecutionError,
    AgentProcessKillError,
    AgentTimeoutError,
)
from ami.cli.provider_type import ProviderType
from ami.cli.streaming_utils import (
    calculate_timeout,
    load_instruction_with_replacements,
)
from ami.types.api import (
    MCPServerConfig,
    ProviderMetadata,
    ProviderResponse,
    StreamEventData,
    StreamMetadata,
)
from ami.types.config import AgentConfig
from ami.types.events import StreamEvent, StreamEventType

# ---------------------------------------------------------------------------
# Constants for magic number comparisons
# ---------------------------------------------------------------------------
EXPECTED_TOKENS_USED = 100
EXPECTED_COST_USD = 0.01
EXPECTED_DURATION = 2.5
EXPECTED_DEFAULT_TIMEOUT = 180
EXPECTED_CUSTOM_TIMEOUT = 60
EXPECTED_TIMEOUT_VALUE = 30
EXPECTED_TIMEOUT_DURATION = 29.5
EXPECTED_KILL_PID = 12345
EXPECTED_INITIAL_TIMEOUT = 10.0
EXPECTED_BASE_TIMEOUT = 180.0

# ---------------------------------------------------------------------------
# StreamEvent factory methods
# ---------------------------------------------------------------------------


class TestStreamEvent:
    """Test all StreamEvent factory methods."""

    def test_chunk_event(self):
        event = StreamEvent.chunk("hello")
        assert event.type == StreamEventType.CHUNK
        assert event.data == "hello"
        assert event.timestamp > 0

    def test_metadata_event(self):
        meta = StreamMetadata(session_id="s1", model="gpt-4")
        event = StreamEvent.metadata(meta)
        assert event.type == StreamEventType.METADATA
        assert event.data.session_id == "s1"

    def test_error_event(self):
        event = StreamEvent.error("something broke")
        assert event.type == StreamEventType.ERROR
        assert event.data == "something broke"

    def test_complete_event(self):
        meta = ProviderMetadata(session_id="s2", duration=1.5, exit_code=0)
        event = StreamEvent.complete("full output", meta)
        assert event.type == StreamEventType.COMPLETE
        assert isinstance(event.data, StreamEventData)
        assert event.data.output == "full output"
        assert event.data.metadata.exit_code == 0

    def test_timestamp_auto_generated(self):
        before = time.time()
        event = StreamEvent.chunk("test")
        after = time.time()
        assert before <= event.timestamp <= after

    def test_event_type_enum_values(self):
        assert StreamEventType.CHUNK.value == "chunk"
        assert StreamEventType.METADATA.value == "metadata"
        assert StreamEventType.ERROR.value == "error"
        assert StreamEventType.COMPLETE.value == "complete"


# ---------------------------------------------------------------------------
# API types
# ---------------------------------------------------------------------------


class TestAPITypes:
    """Test Pydantic API models."""

    def test_stream_metadata_defaults(self):
        meta = StreamMetadata()
        assert meta.session_id is None
        assert meta.model is None
        assert meta.extra == {}

    def test_stream_metadata_with_values(self):
        meta = StreamMetadata(
            session_id="sess-123",
            model="claude-3",
            provider="anthropic",
            tokens_used=100,
            cost_usd=0.01,
            duration_ms=500,
        )
        assert meta.tokens_used == EXPECTED_TOKENS_USED
        assert meta.cost_usd == EXPECTED_COST_USD

    def test_provider_metadata_defaults(self):
        meta = ProviderMetadata()
        assert meta.exit_code is None
        assert meta.duration is None

    def test_provider_metadata_with_values(self):
        meta = ProviderMetadata(
            session_id="s1",
            duration=2.5,
            exit_code=0,
            model="claude",
            tokens=500,
            extra={"custom": "data"},
        )
        assert meta.duration == EXPECTED_DURATION
        assert meta.extra["custom"] == "data"

    def test_provider_response(self):
        resp = ProviderResponse(content="Hello World")
        assert resp.content == "Hello World"
        assert resp.metadata is None

    def test_provider_response_with_metadata(self):
        meta = ProviderMetadata(exit_code=0)
        resp = ProviderResponse(content="output", metadata=meta)
        assert resp.metadata.exit_code == 0

    def test_mcp_server_config(self):
        cfg = MCPServerConfig(command="node", args=["server.js"])
        assert cfg.command == "node"
        assert cfg.args == ["server.js"]
        assert cfg.env == {}

    def test_mcp_server_config_with_env(self):
        cfg = MCPServerConfig(
            command="python3",
            args=["-m", "mcp"],
            env={"API_KEY": "test"},
        )
        assert cfg.env["API_KEY"] == "test"

    def test_stream_event_data(self):
        meta = ProviderMetadata(exit_code=0)
        data = StreamEventData(output="result", metadata=meta)
        assert data.output == "result"
        assert data.metadata.exit_code == 0


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------


class TestAgentConfig:
    """Test AgentConfig defaults and fields."""

    def _provider(self):
        return ProviderType.CLAUDE

    def test_defaults(self):
        cfg = AgentConfig(model="test-model", provider=self._provider())
        assert cfg.model == "test-model"
        assert cfg.enable_hooks is True
        assert cfg.enable_streaming is False
        assert cfg.timeout == EXPECTED_DEFAULT_TIMEOUT
        assert cfg.capture_content is False

    def test_optional_fields(self):
        cfg = AgentConfig(
            model="m1",
            provider=self._provider(),
            session_id="s1",
            allowed_tools=["bash", "read"],
            enable_streaming=True,
            timeout=60,
        )
        assert cfg.session_id == "s1"
        assert cfg.allowed_tools == ["bash", "read"]
        assert cfg.enable_streaming is True
        assert cfg.timeout == EXPECTED_CUSTOM_TIMEOUT

    def test_mcp_servers_field(self):
        mcp = MCPServerConfig(command="node")
        cfg = AgentConfig(
            model="m1", provider=self._provider(), mcp_servers={"default": mcp}
        )
        assert "default" in cfg.mcp_servers

    def test_guard_rules_path(self, tmp_path: Path):
        rules = tmp_path / "rules.yaml"
        rules.write_text("rules: []")
        cfg = AgentConfig(model="m1", provider=self._provider(), guard_rules_path=rules)
        assert cfg.guard_rules_path == rules


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TestExceptions:
    """Test all exception classes and their message formatting."""

    def test_agent_error_base(self):
        err = AgentError("base error")
        assert str(err) == "base error"

    def test_agent_timeout_error(self):
        err = AgentTimeoutError(timeout=30, cmd=["claude", "--print"])
        assert "30s" in str(err)
        assert "claude" in str(err)
        assert err.timeout == EXPECTED_TIMEOUT_VALUE
        assert err.cmd == ["claude", "--print"]

    def test_agent_timeout_error_with_duration(self):
        err = AgentTimeoutError(timeout=30, cmd=["cmd"], duration=29.5)
        assert "29.5" in str(err)
        assert err.duration == EXPECTED_TIMEOUT_DURATION

    def test_agent_command_not_found(self):
        err = AgentCommandNotFoundError("qwen")
        assert "qwen" in str(err)
        assert err.cmd == "qwen"

    def test_agent_execution_error(self):
        err = AgentExecutionError(
            exit_code=1,
            stdout="output",
            stderr="error msg",
            cmd=["test", "cmd"],
        )
        assert err.exit_code == 1
        assert "exit code 1" in str(err)
        assert "error msg" in str(err)
        assert err.stdout == "output"

    def test_agent_process_kill_error(self):
        err = AgentProcessKillError(pid=12345, reason="permission denied")
        assert "12345" in str(err)
        assert "permission denied" in str(err)
        assert err.pid == EXPECTED_KILL_PID

    def test_exception_hierarchy(self):
        assert issubclass(AgentTimeoutError, AgentError)
        assert issubclass(AgentCommandNotFoundError, AgentError)
        assert issubclass(AgentExecutionError, AgentError)
        assert issubclass(AgentProcessKillError, AgentError)
        assert issubclass(AgentError, Exception)


# ---------------------------------------------------------------------------
# Streaming utilities
# ---------------------------------------------------------------------------


class TestStreamingUtils:
    """Test streaming utility functions."""

    def test_calculate_timeout_initial_lines(self):
        # First 5 lines should use initial timeout (10s)
        timeout = calculate_timeout(base_timeout=180.0, line_count=1)
        assert timeout == EXPECTED_INITIAL_TIMEOUT

    def test_calculate_timeout_after_initial(self):
        timeout = calculate_timeout(base_timeout=180.0, line_count=10)
        assert timeout == EXPECTED_BASE_TIMEOUT

    def test_calculate_timeout_none_base(self):
        timeout = calculate_timeout(base_timeout=None, line_count=10)
        # Should not crash; returns some default
        assert isinstance(timeout, int | float)

    def test_load_instruction_with_replacements(self, tmp_path: Path):
        instruction = tmp_path / "instruction.md"
        instruction.write_text("Date: {date}\nDone.")
        result = load_instruction_with_replacements(instruction)
        assert "{date}" not in result  # Should be substituted
        assert "Done." in result

    def test_load_instruction_preserves_content(self, tmp_path: Path):
        instruction = tmp_path / "plain.md"
        instruction.write_text("No variables here.")
        result = load_instruction_with_replacements(instruction)
        assert result == "No variables here."
