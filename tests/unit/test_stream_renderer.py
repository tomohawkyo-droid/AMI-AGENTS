"""Unit tests for cli_components/stream_renderer module."""

import sys
from io import StringIO
from unittest.mock import patch

from ami.cli_components.stream_renderer import (
    CONTENT_WIDTH,
    TOTAL_WIDTH,
    StreamRenderer,
    StreamResult,
)

EXPECTED_DURATION_VALUE = 1.5
EXPECTED_OUTPUT_LENGTH = 100
EXPECTED_CONTENT_WIDTH_VALUE = 76
EXPECTED_TOTAL_WIDTH_VALUE = 80
EXPECTED_FINISH_OUTPUT_LENGTH = 11


class TestStreamResultTypedDict:
    """Tests for StreamResult TypedDict."""

    def test_create_stream_result(self) -> None:
        """Test creating StreamResult dict."""
        result: StreamResult = {
            "session_id": "test-123",
            "duration": 1.5,
            "output_length": 100,
            "completion": {"type": "none", "content": None},
        }

        assert result["session_id"] == "test-123"
        assert result["duration"] == EXPECTED_DURATION_VALUE
        assert result["output_length"] == EXPECTED_OUTPUT_LENGTH


class TestConstants:
    """Tests for module constants."""

    def test_content_width(self) -> None:
        """Test CONTENT_WIDTH value."""
        assert CONTENT_WIDTH == EXPECTED_CONTENT_WIDTH_VALUE

    def test_total_width(self) -> None:
        """Test TOTAL_WIDTH value."""
        assert TOTAL_WIDTH == EXPECTED_TOTAL_WIDTH_VALUE


class TestStreamRendererInit:
    """Tests for StreamRenderer initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        renderer = StreamRenderer("session-123")

        assert renderer.session_id == "session-123"
        assert renderer.capture_content is False
        assert renderer.full_output == ""
        assert renderer.content_started is False

    def test_capture_mode_initialization(self) -> None:
        """Test initialization with capture mode."""
        renderer = StreamRenderer("session-123", capture_content=True)

        assert renderer.capture_content is True


class TestStreamRendererStart:
    """Tests for StreamRenderer.start method."""

    def test_start_without_capture(self) -> None:
        """Test start without capture mode starts timer."""
        renderer = StreamRenderer("session-123", capture_content=False)

        with patch.object(renderer.timer, "start") as mock_start:
            renderer.start()
            mock_start.assert_called_once()

    def test_start_with_capture(self) -> None:
        """Test start with capture mode doesn't start timer."""
        renderer = StreamRenderer("session-123", capture_content=True)

        with patch.object(renderer.timer, "start") as mock_start:
            renderer.start()
            mock_start.assert_not_called()


class TestStreamRendererProcessChunk:
    """Tests for StreamRenderer.process_chunk method."""

    def test_empty_chunk_does_nothing(self) -> None:
        """Test empty chunk does nothing."""
        renderer = StreamRenderer("session-123", capture_content=True)

        renderer.process_chunk("")

        assert renderer.full_output == ""
        assert renderer.content_started is False

    def test_first_chunk_starts_content(self) -> None:
        """Test first chunk starts content."""
        renderer = StreamRenderer("session-123", capture_content=True)

        renderer.process_chunk("hello")

        assert renderer.content_started is True
        assert renderer.box_displayed is True
        assert "hello" in renderer.full_output

    def test_appends_to_full_output(self) -> None:
        """Test chunks are appended to full output."""
        renderer = StreamRenderer("session-123", capture_content=True)

        renderer.process_chunk("hello ")
        renderer.process_chunk("world")

        assert renderer.full_output == "hello world"

    def test_tracks_newline_ending(self) -> None:
        """Test tracks whether chunk ends with newline."""
        renderer = StreamRenderer("session-123", capture_content=True)

        renderer.process_chunk("no newline")
        assert renderer.last_print_ended_with_newline is False

        renderer.process_chunk("\n")
        assert renderer.last_print_ended_with_newline is True


class TestStreamRendererRenderLine:
    """Tests for StreamRenderer._render_line method."""

    def test_replaces_run_block_markers(self, capsys) -> None:
        """Test replaces ```run markers."""
        renderer = StreamRenderer("session-123", capture_content=False)
        renderer.content_started = True

        renderer._render_line("```run")

        captured = capsys.readouterr()
        assert "</>" in captured.out
        assert renderer.in_run_block is True

    def test_replaces_bash_block_markers(self, capsys) -> None:
        """Test replaces ```bash markers."""
        renderer = StreamRenderer("session-123", capture_content=False)
        renderer.content_started = True

        renderer._render_line("```bash")

        captured = capsys.readouterr()
        assert "</>" in captured.out

    def test_skips_closing_fence(self, capsys) -> None:
        """Test skips closing fence line."""
        renderer = StreamRenderer("session-123", capture_content=False)
        renderer.content_started = True
        renderer.in_run_block = True

        renderer._render_line("```")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert renderer.in_run_block is False

    def test_regular_line_indented(self, capsys) -> None:
        """Test regular line is indented."""
        renderer = StreamRenderer("session-123", capture_content=False)
        renderer.content_started = True

        renderer._render_line("hello world")

        captured = capsys.readouterr()
        assert "  hello world" in captured.out


class TestStreamRendererRenderRawLine:
    """Tests for StreamRenderer.render_raw_line method."""

    def test_renders_short_line(self) -> None:
        """Test renders short line directly."""
        renderer = StreamRenderer("session-123", capture_content=True)

        renderer.render_raw_line("hello")

        assert "hello\n" in renderer.full_output

    def test_wraps_long_line(self) -> None:
        """Test wraps long line."""
        renderer = StreamRenderer("session-123", capture_content=True)
        long_line = "x" * 100

        renderer.render_raw_line(long_line)

        assert renderer.full_output.endswith("\n")

    def test_starts_content_if_not_started(self) -> None:
        """Test starts content if not already started."""
        renderer = StreamRenderer("session-123", capture_content=True)

        renderer.render_raw_line("hello")

        assert renderer.content_started is True
        assert renderer.box_displayed is True


class TestStreamRendererFinish:
    """Tests for StreamRenderer.finish method."""

    def test_returns_stream_result(self) -> None:
        """Test returns StreamResult dict."""
        renderer = StreamRenderer("session-123", capture_content=True)
        renderer.process_chunk("test output")

        result = renderer.finish()

        assert result["session_id"] == "session-123"
        assert result["output_length"] == EXPECTED_FINISH_OUTPUT_LENGTH
        assert "duration" in result
        assert "completion" in result

    def test_stops_running_timer(self) -> None:
        """Test stops running timer."""
        renderer = StreamRenderer("session-123", capture_content=True)
        renderer.timer.is_running = True

        with patch.object(renderer.timer, "stop") as mock_stop:
            renderer.finish()
            mock_stop.assert_called_once()

    def test_parses_completion_marker(self) -> None:
        """Test parses completion marker from output."""
        renderer = StreamRenderer("session-123", capture_content=True)
        renderer.process_chunk("Task done. WORK DONE")

        result = renderer.finish()

        assert result["completion"]["type"] == "work_done"

    def test_flushes_line_buffer(self) -> None:
        """Test flushes remaining line buffer."""
        renderer = StreamRenderer("session-123", capture_content=False)
        renderer.content_started = True
        renderer.line_buffer = "remaining text"

        output = StringIO()
        with (
            patch.object(sys.stdout, "write", output.write),
            patch.object(sys.stdout, "flush"),
        ):
            renderer.finish()

        assert "remaining text" in output.getvalue()
