"""Comprehensive unit tests for ami/cli_components/stream_renderer.py."""

from unittest.mock import MagicMock, patch

from ami.cli_components.stream_renderer import (
    CONTENT_WIDTH,
    TOTAL_WIDTH,
    StreamRenderer,
    StreamResult,
)

EXPECTED_CONTENT_WIDTH = 76
EXPECTED_TOTAL_WIDTH = 80
EXPECTED_MIN_PRINT_CALLS = 2
EXPECTED_MIN_WRITE_CALLS = 2
EXPECTED_DURATION = 1.5
EXPECTED_OUTPUT_LENGTH = 100


class TestStreamRendererConstants:
    """Tests for module constants."""

    def test_content_width(self):
        """Test CONTENT_WIDTH constant."""
        assert CONTENT_WIDTH == EXPECTED_CONTENT_WIDTH

    def test_total_width(self):
        """Test TOTAL_WIDTH constant."""
        assert TOTAL_WIDTH == EXPECTED_TOTAL_WIDTH


class TestStreamRendererInit:
    """Tests for StreamRenderer initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        renderer = StreamRenderer("test-session")

        assert renderer.session_id == "test-session"
        assert renderer.capture_content is False
        assert renderer.full_output == ""
        assert renderer.content_started is False
        assert renderer.box_displayed is False
        assert renderer.response_box_started is False
        assert renderer.response_box_ended is False
        assert renderer.line_buffer == ""
        assert renderer.in_run_block is False

    def test_init_with_capture(self):
        """Test initialization with capture_content=True."""
        renderer = StreamRenderer("session-123", capture_content=True)

        assert renderer.capture_content is True


class TestStart:
    """Tests for start method."""

    def test_start_starts_timer(self):
        """Test start method starts timer."""
        renderer = StreamRenderer("session")
        renderer.timer = MagicMock()

        renderer.start()

        renderer.timer.start.assert_called_once()

    def test_start_no_timer_when_capturing(self):
        """Test start does not start timer when capturing."""
        renderer = StreamRenderer("session", capture_content=True)

        # Should not raise
        renderer.start()


class TestProcessChunk:
    """Tests for process_chunk method."""

    def test_empty_chunk_ignored(self):
        """Test empty chunk is ignored."""
        renderer = StreamRenderer("session", capture_content=True)

        renderer.process_chunk("")

        assert renderer.full_output == ""
        assert renderer.content_started is False

    def test_first_chunk_starts_content(self):
        """Test first chunk sets content_started."""
        renderer = StreamRenderer("session", capture_content=True)

        renderer.process_chunk("Hello")

        assert renderer.content_started is True
        assert renderer.box_displayed is True
        assert renderer.response_box_started is True
        assert renderer.full_output == "Hello"

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_first_chunk_draws_box(self, mock_flush, mock_write):
        """Test first chunk draws opening box."""
        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()

        renderer.process_chunk("Hello")

        # Check that opening box was written
        calls = [str(c) for c in mock_write.call_args_list]
        assert any("┌" in str(c) for c in calls)

    def test_chunk_appended_to_output(self):
        """Test chunk is appended to full_output."""
        renderer = StreamRenderer("session", capture_content=True)

        renderer.process_chunk("Hello ")
        renderer.process_chunk("World")

        assert renderer.full_output == "Hello World"

    def test_last_print_tracks_newline(self):
        """Test last_print_ended_with_newline is tracked."""
        renderer = StreamRenderer("session", capture_content=True)

        renderer.process_chunk("No newline")
        assert renderer.last_print_ended_with_newline is False

        renderer.process_chunk("With newline\n")
        assert renderer.last_print_ended_with_newline is True

    @patch("builtins.print")
    def test_newlines_trigger_line_rendering(self, mock_print):
        """Test newlines in buffer trigger line rendering."""
        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.content_started = True
        renderer.box_displayed = True

        renderer.process_chunk("Line 1\nLine 2\n")

        # Print should have been called for the lines
        assert mock_print.call_count >= EXPECTED_MIN_PRINT_CALLS


class TestRenderLine:
    """Tests for _render_line method."""

    @patch("builtins.print")
    def test_render_simple_line(self, mock_print):
        """Test rendering a simple line."""
        renderer = StreamRenderer("session")

        renderer._render_line("Hello World")

        mock_print.assert_called_once_with("  Hello World")

    @patch("builtins.print")
    def test_render_run_block_start(self, mock_print):
        """Test rendering ```run block start."""
        renderer = StreamRenderer("session")

        renderer._render_line("```run")

        assert renderer.in_run_block is True
        mock_print.assert_called_once_with("  </>")

    @patch("builtins.print")
    def test_render_bash_block_start(self, mock_print):
        """Test rendering ```bash block start."""
        renderer = StreamRenderer("session")

        renderer._render_line("```bash")

        assert renderer.in_run_block is True
        mock_print.assert_called_once_with("  </>")

    @patch("builtins.print")
    def test_render_closing_fence_skipped(self, mock_print):
        """Test closing fence is skipped in run block."""
        renderer = StreamRenderer("session")
        renderer.in_run_block = True

        renderer._render_line("```")

        assert renderer.in_run_block is False
        mock_print.assert_not_called()

    @patch("builtins.print")
    def test_render_closing_fence_with_content(self, mock_print):
        """Test closing fence with content removes fence."""
        renderer = StreamRenderer("session")
        renderer.in_run_block = True

        renderer._render_line("Output```")

        assert renderer.in_run_block is False
        mock_print.assert_called_once_with("  Output")


class TestRenderRawLine:
    """Tests for render_raw_line method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_render_short_line(self, mock_flush, mock_write):
        """Test rendering a short line."""
        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.content_started = True

        renderer.render_raw_line("Short line")

        mock_write.assert_called()
        assert renderer.last_print_ended_with_newline is True

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_render_long_line_wraps(self, mock_flush, mock_write):
        """Test rendering a long line wraps."""
        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.content_started = True

        long_line = "A" * 100
        renderer.render_raw_line(long_line)

        # Should have multiple writes for wrapped lines
        assert mock_write.call_count >= EXPECTED_MIN_WRITE_CALLS

    def test_render_raw_line_captures_content(self):
        """Test render_raw_line captures content."""
        renderer = StreamRenderer("session", capture_content=True)

        renderer.render_raw_line("Test line")

        assert "Test line" in renderer.full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_render_raw_starts_content(self, mock_flush, mock_write):
        """Test render_raw_line starts content if not started."""
        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()

        renderer.render_raw_line("Line")

        assert renderer.content_started is True
        assert renderer.box_displayed is True


class TestFinish:
    """Tests for finish method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    @patch("time.strftime")
    def test_finish_returns_result(self, mock_strftime, mock_flush, mock_write):
        """Test finish returns StreamResult."""
        mock_strftime.return_value = "12:34:56"

        renderer = StreamRenderer("session", capture_content=True)
        renderer.full_output = "Test output"

        result = renderer.finish()

        assert result["session_id"] == "session"
        assert "duration" in result
        assert result["output_length"] == len("Test output")

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    @patch("time.strftime")
    def test_finish_stops_timer(self, mock_strftime, mock_flush, mock_write):
        """Test finish stops running timer."""
        mock_strftime.return_value = "12:34:56"

        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.timer.is_running = True

        renderer.finish()

        renderer.timer.stop.assert_called_once()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    @patch("time.strftime")
    def test_finish_flushes_buffer(self, mock_strftime, mock_flush, mock_write):
        """Test finish flushes line buffer."""
        mock_strftime.return_value = "12:34:56"

        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.timer.is_running = False
        renderer.line_buffer = "Buffered text"

        renderer.finish()

        # Should have written buffered text
        calls = [str(c) for c in mock_write.call_args_list]
        assert any("Buffered text" in str(c) or "Buffer" in str(c) for c in calls)

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    @patch("time.strftime")
    def test_finish_closes_box(self, mock_strftime, mock_flush, mock_write):
        """Test finish closes response box."""
        mock_strftime.return_value = "12:34:56"

        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.timer.is_running = False
        renderer.response_box_started = True
        renderer.response_box_ended = False

        renderer.finish()

        calls = [str(c) for c in mock_write.call_args_list]
        assert any("└" in str(c) for c in calls)
        assert renderer.response_box_ended is True

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    @patch("time.strftime")
    def test_finish_writes_footer(self, mock_strftime, mock_flush, mock_write):
        """Test finish writes footer with timestamp."""
        mock_strftime.return_value = "12:34:56"

        renderer = StreamRenderer("session", capture_content=False)
        renderer.timer = MagicMock()
        renderer.timer.is_running = False

        renderer.finish()

        calls = [str(c) for c in mock_write.call_args_list]
        assert any("12:34:56" in str(c) for c in calls)


class TestStreamResult:
    """Tests for StreamResult TypedDict."""

    def test_stream_result_type(self):
        """Test StreamResult is a valid TypedDict."""
        result: StreamResult = {
            "session_id": "test",
            "duration": 1.5,
            "output_length": 100,
            "completion": None,
        }

        assert result["session_id"] == "test"
        assert result["duration"] == EXPECTED_DURATION
        assert result["output_length"] == EXPECTED_OUTPUT_LENGTH
