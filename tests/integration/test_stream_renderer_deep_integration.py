"""Deep integration tests for stream rendering,
observer routing, provider validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.streaming import RendererObserver
from ami.cli_components.stream_renderer import CONTENT_WIDTH, StreamRenderer
from ami.core.config import _ConfigSingleton
from ami.core.interfaces import RunPrintParams
from ami.types.api import ProviderMetadata, StreamEventData
from ami.types.events import StreamEvent, StreamEventType


@pytest.fixture(autouse=True)
def _reset_config_singleton(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _capture_renderer(sid: str = "test-session") -> StreamRenderer:
    return StreamRenderer(sid, capture_content=True)


def _display_renderer(sid: str = "test-session") -> StreamRenderer:
    return StreamRenderer(sid, capture_content=False)


class TestStreamRendererCaptureMode:
    def test_start_does_not_start_timer(self):
        renderer = _capture_renderer()
        renderer.start()
        assert renderer.timer.is_running is False

    def test_process_chunk_accumulates_full_output(self):
        renderer = _capture_renderer()
        renderer.process_chunk("Hello ")
        renderer.process_chunk("World")
        assert renderer.full_output == "Hello World"
        assert renderer.content_started is True

    def test_process_chunk_multiline_text(self):
        renderer = _capture_renderer()
        renderer.process_chunk("line1\nline2\nline3\n")
        assert renderer.full_output == "line1\nline2\nline3\n"
        assert renderer.content_started is True
        assert renderer.response_box_started is True

    def test_process_chunk_empty_string_is_noop(self):
        renderer = _capture_renderer()
        renderer.process_chunk("")
        assert renderer.full_output == ""
        assert renderer.content_started is False

    def test_process_chunk_sets_last_print_ended_with_newline(self):
        renderer = _capture_renderer()
        renderer.process_chunk("no newline")
        assert renderer.last_print_ended_with_newline is False
        renderer.process_chunk("with newline\n")
        assert renderer.last_print_ended_with_newline is True

    def test_process_chunk_does_not_write_stdout(self, capsys):
        renderer = _capture_renderer()
        renderer.process_chunk("Hello World\n")
        assert capsys.readouterr().out == ""

    def test_render_raw_line_no_stdout_but_appends_output(self, capsys):
        renderer = _capture_renderer()
        renderer.render_raw_line("raw content")
        assert capsys.readouterr().out == ""
        assert "raw content\n" in renderer.full_output
        assert renderer.content_started is True

    def test_render_raw_line_appends_multiple(self):
        renderer = _capture_renderer()
        renderer.render_raw_line("first line")
        renderer.render_raw_line("second line")
        assert renderer.full_output == "first line\nsecond line\n"

    def test_render_raw_line_sets_last_print_newline(self):
        renderer = _capture_renderer()
        renderer.render_raw_line("content")
        assert renderer.last_print_ended_with_newline is True

    def test_finish_returns_stream_result_dict(self):
        renderer = _capture_renderer()
        renderer.process_chunk("some output")
        result = renderer.finish()
        assert result["session_id"] == "test-session"
        assert result["output_length"] == len("some output")
        assert result["duration"] >= 0
        assert "completion" in result

    def test_finish_completion_marker_none(self):
        renderer = _capture_renderer()
        renderer.process_chunk("just some text")
        assert renderer.finish()["completion"]["type"] == "none"

    def test_finish_completion_marker_work_done(self):
        renderer = _capture_renderer()
        renderer.process_chunk("Task complete. WORK DONE")
        assert renderer.finish()["completion"]["type"] == "work_done"

    def test_finish_completion_marker_feedback(self):
        renderer = _capture_renderer()
        renderer.process_chunk("FEEDBACK: needs revision")
        result = renderer.finish()
        assert result["completion"]["type"] == "feedback"
        assert result["completion"]["content"] == "needs revision"

    def test_finish_capture_mode_no_stdout(self, capsys):
        renderer = _capture_renderer()
        renderer.process_chunk("text\n")
        renderer.finish()
        assert capsys.readouterr().out == ""


class TestStreamRendererDisplayMode:
    @patch("ami.cli_components.stream_renderer.time")
    def test_process_chunk_writes_box_top(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.process_chunk("hello\n")
        out = capsys.readouterr().out
        assert "\u250c" in out
        assert "\u2500" in out

    @patch("ami.cli_components.stream_renderer.time")
    def test_process_chunk_line_splitting(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.process_chunk("line1\nline2\n")
        out = capsys.readouterr().out
        assert "line1" in out
        assert "line2" in out

    @patch("ami.cli_components.stream_renderer.time")
    def test_process_chunk_partial_line_buffered(self, mock_time):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.process_chunk("partial")
        assert r.line_buffer == "partial"

    @patch("ami.cli_components.stream_renderer.time")
    def test_process_chunk_code_fence_run(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.process_chunk("```run echo hello\n")
        out = capsys.readouterr().out
        assert "</>" in out
        assert "```run" not in out
        assert r.in_run_block is True

    @patch("ami.cli_components.stream_renderer.time")
    def test_process_chunk_code_fence_bash(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.process_chunk("```bash\n")
        out = capsys.readouterr().out
        assert "</>" in out
        assert "```bash" not in out
        assert r.in_run_block is True

    @patch("ami.cli_components.stream_renderer.time")
    def test_process_chunk_closing_fence_skipped(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.in_run_block = True
        r.content_started = True
        r.response_box_started = True
        r.process_chunk("```\n")
        lines = [ln for ln in capsys.readouterr().out.strip().split("\n") if ln.strip()]
        assert not any(ln.strip() == "```" for ln in lines)
        assert r.in_run_block is False

    @patch("ami.cli_components.stream_renderer.time")
    def test_render_raw_line_short(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.render_raw_line("short line")
        assert "  short line\n" in capsys.readouterr().out

    @patch("ami.cli_components.stream_renderer.time")
    def test_render_raw_line_wraps_long(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.render_raw_line("x " * (CONTENT_WIDTH + 10))
        output_lines = [ln for ln in capsys.readouterr().out.split("\n") if ln.strip()]
        assert len(output_lines) > 1

    @patch("ami.cli_components.stream_renderer.time")
    def test_finish_flushes_line_buffer(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        mock_time.strftime.return_value = "12:00:00"
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.content_started = True
        r.response_box_started = True
        r.line_buffer = "leftover text"
        r.finish()
        assert "leftover text" in capsys.readouterr().out

    @patch("ami.cli_components.stream_renderer.time")
    def test_finish_writes_box_bottom(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        mock_time.strftime.return_value = "12:00:00"
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.content_started = True
        r.response_box_started = True
        r.finish()
        assert "\u2514" in capsys.readouterr().out
        assert r.response_box_ended is True

    @patch("ami.cli_components.stream_renderer.time")
    def test_finish_no_double_close(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        mock_time.strftime.return_value = "12:00:00"
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.content_started = True
        r.response_box_started = True
        r.response_box_ended = True
        r.finish()
        assert capsys.readouterr().out.count("\u2514") == 0

    @patch("ami.cli_components.stream_renderer.time")
    def test_finish_writes_footer(self, mock_time, capsys):
        mock_time.time.return_value = 1000.0
        mock_time.strftime.return_value = "14:30:15"
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        r.finish()
        assert "14:30:15" in capsys.readouterr().out

    def test_start_starts_timer(self):
        r = _display_renderer()
        r.start()
        assert r.timer.is_running is True
        r.timer.stop()


class TestRenderLine:
    def test_plain_text(self, capsys):
        r = _display_renderer()
        r._render_line("plain text")
        assert "  plain text\n" in capsys.readouterr().out

    def test_replaces_run_fence(self, capsys):
        r = _display_renderer()
        r._render_line("```run ls -la")
        out = capsys.readouterr().out
        assert "</>" in out
        assert "```run" not in out
        assert r.in_run_block is True

    def test_replaces_bash_fence(self, capsys):
        r = _display_renderer()
        r._render_line("```bash")
        out = capsys.readouterr().out
        assert "</>" in out
        assert "```bash" not in out
        assert r.in_run_block is True

    def test_closing_fence_skips_print(self, capsys):
        r = _display_renderer()
        r.in_run_block = True
        r._render_line("```")
        assert capsys.readouterr().out == ""
        assert r.in_run_block is False

    def test_closing_fence_with_text_strips_backticks(self, capsys):
        r = _display_renderer()
        r.in_run_block = True
        r._render_line("some``` content")
        out = capsys.readouterr().out
        assert "```" not in out
        assert "some" in out
        assert "content" in out
        assert r.in_run_block is False

    def test_non_run_block_fence_passes_through(self, capsys):
        r = _display_renderer()
        r.in_run_block = False
        r._render_line("```python")
        assert "```python" in capsys.readouterr().out

    def test_empty_string(self, capsys):
        r = _display_renderer()
        r._render_line("")
        assert capsys.readouterr().out == "  \n"


class TestRendererObserver:
    def _make_observer(self) -> tuple[MagicMock, MagicMock, RendererObserver]:
        renderer = MagicMock()
        processor = MagicMock()
        return renderer, processor, RendererObserver(renderer, processor)

    def test_chunk_calls_process_chunk(self):
        renderer, _, obs = self._make_observer()
        obs.on_event(StreamEvent(type=StreamEventType.CHUNK, data="hello world"))
        renderer.process_chunk.assert_called_once_with("hello world")

    def test_chunk_multiline(self):
        renderer, _, obs = self._make_observer()
        obs.on_event(StreamEvent(type=StreamEventType.CHUNK, data="l1\nl2\n"))
        renderer.process_chunk.assert_called_once_with("l1\nl2\n")

    def test_metadata_updates_session_id(self):
        renderer, _, obs = self._make_observer()
        meta = ProviderMetadata(session_id="new-session-id")
        data = StreamEventData(output="", metadata=meta)
        obs.on_event(StreamEvent(type=StreamEventType.METADATA, data=data))
        assert renderer.session_id == "new-session-id"

    def test_metadata_without_session_id_is_noop(self):
        renderer, _, obs = self._make_observer()
        renderer.session_id = "original"
        meta = ProviderMetadata(session_id=None)
        data = StreamEventData(output="", metadata=meta)
        obs.on_event(StreamEvent(type=StreamEventType.METADATA, data=data))
        assert renderer.session_id == "original"

    def test_error_type_is_noop(self):
        renderer, _, obs = self._make_observer()
        obs.on_event(StreamEvent(type=StreamEventType.ERROR, data="error happened"))
        renderer.process_chunk.assert_not_called()

    def test_complete_type_is_noop(self):
        renderer, _, obs = self._make_observer()
        meta = ProviderMetadata(exit_code=0)
        data = StreamEventData(output="done", metadata=meta)
        obs.on_event(StreamEvent(type=StreamEventType.COMPLETE, data=data))
        renderer.process_chunk.assert_not_called()

    def test_chunk_non_string_data_is_noop(self):
        renderer, _, obs = self._make_observer()
        data = StreamEventData(output="text", metadata=ProviderMetadata())
        obs.on_event(StreamEvent(type=StreamEventType.CHUNK, data=data))
        renderer.process_chunk.assert_not_called()

    def test_metadata_string_data_is_noop(self):
        renderer, _, obs = self._make_observer()
        renderer.session_id = "original"
        obs.on_event(StreamEvent(type=StreamEventType.METADATA, data="not-event"))
        assert renderer.session_id == "original"


class TestRunPrintValidation:
    def test_no_instruction_raises(self):
        cli = ClaudeAgentCLI()
        with pytest.raises(
            ValueError, match="Either instruction or instruction_file is required"
        ):
            cli.run_print(RunPrintParams())

    def test_both_instruction_and_file_raises(self, tmp_path: Path):
        cli = ClaudeAgentCLI()
        f = tmp_path / "instr.md"
        f.write_text("content")
        with pytest.raises(
            ValueError, match="Cannot provide both instruction and instruction_file"
        ):
            cli.run_print(RunPrintParams(instruction="inline", instruction_file=f))

    def test_path_as_instruction_raises(self, tmp_path: Path):
        cli = ClaudeAgentCLI()
        with pytest.raises(ValueError, match="Use instruction_file parameter for Path"):
            cli.run_print(RunPrintParams(instruction=tmp_path / "file.md"))

    def test_none_or_no_params_raises(self):
        cli = ClaudeAgentCLI()
        with pytest.raises(
            ValueError, match="Either instruction or instruction_file is required"
        ):
            cli.run_print(params=None)
        with pytest.raises(
            ValueError, match="Either instruction or instruction_file is required"
        ):
            cli.run_print()


class TestStreamRendererTimerInteraction:
    def test_finish_stops_running_timer(self):
        r = _capture_renderer()
        r.timer = MagicMock(is_running=True)
        r.finish()
        r.timer.stop.assert_called_once()

    def test_finish_skips_stopped_timer(self):
        r = _capture_renderer()
        r.timer = MagicMock(is_running=False)
        r.finish()
        r.timer.stop.assert_not_called()

    @patch("ami.cli_components.stream_renderer.time")
    def test_chunk_stops_timer_display(self, mock_time):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=True)
        r.process_chunk("data\n")
        r.timer.stop.assert_called_once()

    def test_chunk_no_timer_stop_capture(self):
        r = _capture_renderer()
        r.timer = MagicMock(is_running=True)
        r.process_chunk("data")
        r.timer.stop.assert_not_called()

    @patch("ami.cli_components.stream_renderer.time")
    def test_raw_line_stops_timer_display(self, mock_time):
        mock_time.time.return_value = 1000.0
        r = _display_renderer()
        r.timer = MagicMock(is_running=True)
        r.render_raw_line("line")
        r.timer.stop.assert_called_once()


class TestStreamRendererSessionId:
    def test_session_id_in_result(self):
        r = _capture_renderer("my-session-abc")
        r.process_chunk("out")
        assert r.finish()["session_id"] == "my-session-abc"

    def test_session_id_can_be_updated(self):
        r = _capture_renderer("initial")
        r.session_id = "updated"
        r.process_chunk("data")
        assert r.finish()["session_id"] == "updated"

    def test_observer_updates_renderer_session_id(self):
        r = _capture_renderer("original-id")
        obs = RendererObserver(r, MagicMock())
        meta = ProviderMetadata(session_id="observer-set-id")
        data = StreamEventData(output="", metadata=meta)
        obs.on_event(StreamEvent(type=StreamEventType.METADATA, data=data))
        assert r.session_id == "observer-set-id"
        r.process_chunk("output")
        assert r.finish()["session_id"] == "observer-set-id"


class TestStreamRendererStateTransitions:
    def test_initial_state(self):
        r = _capture_renderer()
        assert r.content_started is False
        assert r.box_displayed is False
        assert r.response_box_started is False
        assert r.response_box_ended is False
        assert r.line_buffer == ""
        assert r.in_run_block is False
        assert r.full_output == ""

    def test_after_first_chunk(self):
        r = _capture_renderer()
        r.process_chunk("first")
        assert r.content_started is True
        assert r.box_displayed is True
        assert r.response_box_started is True
        assert r.response_box_ended is False

    def test_capture_box_not_ended_after_finish(self):
        r = _capture_renderer()
        r.process_chunk("data")
        r.finish()
        assert r.response_box_ended is False

    def test_display_box_ended_after_finish(self):
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        with patch("ami.cli_components.stream_renderer.time") as mt:
            mt.time.return_value = 1000.0
            mt.strftime.return_value = "00:00:00"
            r.process_chunk("data\n")
            r.finish()
        assert r.response_box_ended is True

    def test_multiple_chunks_accumulate(self):
        r = _capture_renderer()
        r.process_chunk("a")
        r.process_chunk("b")
        r.process_chunk("c")
        assert r.full_output == "abc"

    def test_render_raw_sets_content_started(self):
        r = _capture_renderer()
        assert r.content_started is False
        r.render_raw_line("raw")
        assert r.content_started is True
        assert r.box_displayed is True
