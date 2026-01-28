"""Integration tests for the streaming execution pipeline.

Exercises: cli/stream_processor.py, cli/streaming.py, cli/process_utils.py,
cli/mode_handlers.py, cli/base_provider.py
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.exceptions import AgentCommandNotFoundError
from ami.cli.mode_handlers import get_latest_session_id
from ami.cli.stream_processor import StreamObserver, StreamProcessor
from ami.cli.streaming import execute_streaming
from ami.core.config import _ConfigSingleton
from ami.core.interfaces import RunPrintParams
from ami.types.api import ProviderMetadata, StreamEventData, StreamMetadata
from ami.types.events import StreamEvent, StreamEventType

# ---------------------------------------------------------------------------
# Constants for magic number comparisons
# ---------------------------------------------------------------------------
EXPECTED_MULTI_LINE_CHUNKS = 3


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# StreamProcessor with real commands
# ---------------------------------------------------------------------------


class TestStreamProcessorBasic:
    """Test StreamProcessor with real system commands."""

    def test_echo_command_yields_events(self):
        proc = StreamProcessor(cmd=["echo", "hello stream"])
        events = list(proc.run())
        types = [e.type for e in events]
        assert StreamEventType.CHUNK in types
        assert StreamEventType.COMPLETE in types

    def test_complete_event_has_output(self):
        proc = StreamProcessor(cmd=["echo", "output here"])
        events = list(proc.run())
        complete = [e for e in events if e.type == StreamEventType.COMPLETE]
        assert len(complete) == 1
        assert isinstance(complete[0].data, StreamEventData)
        assert "output here" in complete[0].data.output

    def test_complete_event_has_metadata(self):
        proc = StreamProcessor(cmd=["echo", "test"])
        events = list(proc.run())
        complete = next(e for e in events if e.type == StreamEventType.COMPLETE)
        assert isinstance(complete.data, StreamEventData)
        assert complete.data.metadata.exit_code == 0
        assert complete.data.metadata.duration >= 0

    def test_multi_line_output(self):
        proc = StreamProcessor(
            cmd=["python3", "-c", "for i in range(3): print(f'line{i}')"]
        )
        events = list(proc.run())
        chunks = [e for e in events if e.type == StreamEventType.CHUNK]
        assert len(chunks) == EXPECTED_MULTI_LINE_CHUNKS

    def test_nonexistent_command_raises(self):
        proc = StreamProcessor(cmd=["nonexistent_binary_xyz_99"])
        with pytest.raises(AgentCommandNotFoundError):
            list(proc.run())

    def test_full_output_collected(self):
        proc = StreamProcessor(cmd=["echo", "collected"])
        list(proc.run())
        assert "collected" in "".join(proc.full_output)

    def test_exit_code_stored(self):
        proc = StreamProcessor(cmd=["echo", "ok"])
        list(proc.run())
        assert proc._exit_code == 0

    def test_duration_stored(self):
        proc = StreamProcessor(cmd=["echo", "timing"])
        list(proc.run())
        assert proc._duration >= 0


class TestStreamProcessorObserver:
    """Test StreamProcessor observer pattern."""

    def test_observer_receives_events(self):
        received: list[StreamEvent] = []

        class Collector(StreamObserver):
            def on_event(self, event: StreamEvent) -> None:
                received.append(event)

        proc = StreamProcessor(cmd=["echo", "observed"])
        proc.add_observer(Collector())
        list(proc.run())
        assert len(received) > 0
        types = [e.type for e in received]
        assert StreamEventType.CHUNK in types
        assert StreamEventType.COMPLETE in types

    def test_multiple_observers(self):
        counts = {"a": 0, "b": 0}

        class CounterA(StreamObserver):
            def on_event(self, event: StreamEvent) -> None:
                counts["a"] += 1

        class CounterB(StreamObserver):
            def on_event(self, event: StreamEvent) -> None:
                counts["b"] += 1

        proc = StreamProcessor(cmd=["echo", "multi"])
        proc.add_observer(CounterA())
        proc.add_observer(CounterB())
        list(proc.run())
        assert counts["a"] > 0
        assert counts["a"] == counts["b"]

    def test_observer_error_does_not_crash(self):
        class BrokenObserver(StreamObserver):
            def on_event(self, event: StreamEvent) -> None:
                raise RuntimeError("broken")

        proc = StreamProcessor(cmd=["echo", "safe"])
        proc.add_observer(BrokenObserver())
        events = list(proc.run())
        assert len(events) > 0  # Should complete despite observer error


class TestStreamProcessorProvider:
    """Test StreamProcessor with provider parser."""

    def test_provider_parser_called(self):
        mock_provider = MagicMock()
        mock_provider._parse_stream_message.return_value = ("parsed", None)
        proc = StreamProcessor(cmd=["echo", "raw"], provider=mock_provider)
        list(proc.run())
        assert mock_provider._parse_stream_message.called

    def test_provider_metadata_emitted(self):
        meta = StreamMetadata(session_id="s1", model="test")
        mock_provider = MagicMock()
        mock_provider._parse_stream_message.return_value = ("text", meta)
        proc = StreamProcessor(cmd=["echo", "meta"], provider=mock_provider)
        events = list(proc.run())
        meta_events = [e for e in events if e.type == StreamEventType.METADATA]
        assert len(meta_events) > 0


# ---------------------------------------------------------------------------
# execute_streaming
# ---------------------------------------------------------------------------


class TestExecuteStreaming:
    """Test execute_streaming function."""

    def test_basic_execution(self):
        output, metadata = execute_streaming(cmd=["echo", "stream exec"])
        assert "stream exec" in output
        assert isinstance(metadata, ProviderMetadata)
        assert metadata.exit_code == 0

    def test_nonexistent_command(self):
        with pytest.raises(AgentCommandNotFoundError):
            execute_streaming(cmd=["nonexistent_xyz_99"])


# ---------------------------------------------------------------------------
# Mode handlers (testable parts)
# ---------------------------------------------------------------------------


class TestModeHandlers:
    """Test mode handler helper functions."""

    def test_get_latest_session_id_no_dir(self, tmp_path: Path):
        # With no transcripts dir, should return None
        with patch("ami.cli.mode_handlers.get_config") as mock:
            mock_cfg = MagicMock()
            mock_cfg.root = tmp_path
            mock.return_value = mock_cfg
            result = get_latest_session_id()
            assert result is None

    def test_get_latest_session_id_with_files(self, tmp_path: Path):
        transcripts = tmp_path / "logs" / "transcripts"
        transcripts.mkdir(parents=True)
        (transcripts / "abc123.jsonl").write_text("{}")
        with patch("ami.cli.mode_handlers.get_config") as mock:
            mock_cfg = MagicMock()
            mock_cfg.root = tmp_path
            mock.return_value = mock_cfg
            result = get_latest_session_id()
            assert result == "abc123"

    def test_get_latest_session_id_newest_first(self, tmp_path: Path):
        transcripts = tmp_path / "logs" / "transcripts"
        transcripts.mkdir(parents=True)
        f1 = transcripts / "old.jsonl"
        f1.write_text("{}")
        time.sleep(0.05)
        f2 = transcripts / "new.jsonl"
        f2.write_text("{}")
        with patch("ami.cli.mode_handlers.get_config") as mock:
            mock_cfg = MagicMock()
            mock_cfg.root = tmp_path
            mock.return_value = mock_cfg
            result = get_latest_session_id()
            assert result == "new"


# ---------------------------------------------------------------------------
# Base provider run_print validation
# ---------------------------------------------------------------------------


class TestBaseProviderValidation:
    """Test CLIProvider.run_print parameter validation."""

    def test_run_print_both_instruction_and_file_raises(self, tmp_path: Path):
        cli = ClaudeAgentCLI()
        f = tmp_path / "inst.md"
        f.write_text("instruction text")
        params = RunPrintParams(
            instruction="direct text",
            instruction_file=f,
        )
        with pytest.raises(ValueError, match="Cannot provide both"):
            cli.run_print(params=params)

    def test_run_print_no_instruction_raises(self):
        cli = ClaudeAgentCLI()
        params = RunPrintParams()
        with pytest.raises(ValueError, match="Either instruction or instruction_file"):
            cli.run_print(params=params)

    def test_run_print_path_as_instruction_raises(self):
        cli = ClaudeAgentCLI()
        params = RunPrintParams(instruction=Path("/some/file.md"))
        with pytest.raises(ValueError, match="Use instruction_file"):
            cli.run_print(params=params)
