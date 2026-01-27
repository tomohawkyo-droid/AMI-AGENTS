"""Unit tests for ami/cli/timer_utils.py."""

import io
import sys
import time
from unittest.mock import patch

from ami.cli.timer_utils import TimerDisplay, wrap_text_in_box

EXPECTED_MIN_WRAPPED_LINES = 4
EXPECTED_MIN_LINES_WITH_EMPTY = 5
EXPECTED_DEFAULT_BOX_WIDTH = 80


class TestWrapTextInBox:
    """Tests for wrap_text_in_box function."""

    def test_basic_text_wrapping(self):
        """Test basic text is wrapped in box."""
        result = wrap_text_in_box("Hello World", width=40)

        assert "┌" in result
        assert "┐" in result
        assert "└" in result
        assert "┘" in result
        assert "Hello World" in result

    def test_multiline_text(self):
        """Test multiline text is handled correctly."""
        result = wrap_text_in_box("Line 1\nLine 2\nLine 3", width=40)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_long_line_wrapping(self):
        """Test long lines are wrapped."""
        long_text = "A" * 100
        result = wrap_text_in_box(long_text, width=40)

        # Line should be split across multiple lines
        lines = result.split("\n")
        # Should have more lines than just top, content, bottom
        assert len(lines) >= EXPECTED_MIN_WRAPPED_LINES

    def test_empty_line_handling(self):
        """Test empty lines are preserved."""
        result = wrap_text_in_box("Line 1\n\nLine 3", width=40)

        lines = result.split("\n")
        # Should have empty line in middle
        assert len(lines) >= EXPECTED_MIN_LINES_WITH_EMPTY

    def test_small_width_defaults(self):
        """Test very small width uses default content width."""
        result = wrap_text_in_box("Hello", width=2)

        # Should still produce output
        assert "Hello" in result
        assert "┌" in result

    def test_default_width(self):
        """Test default width is 80."""
        result = wrap_text_in_box("Test")

        lines = result.split("\n")
        # Top border should be 80 characters
        top_border = lines[0]
        assert len(top_border) == EXPECTED_DEFAULT_BOX_WIDTH


class TestTimerDisplay:
    """Tests for TimerDisplay class."""

    def test_init(self):
        """Test TimerDisplay initialization."""
        timer = TimerDisplay()

        assert timer.timer_thread is None
        assert timer.is_running is False
        assert timer.stop_event is not None

    def test_start_creates_thread(self):
        """Test start creates a timer thread."""
        timer = TimerDisplay()

        timer.start()

        assert timer.is_running is True
        assert timer.timer_thread is not None
        assert timer.timer_thread.is_alive()

        timer.stop()

    def test_start_idempotent(self):
        """Test calling start twice doesn't create two threads."""
        timer = TimerDisplay()

        timer.start()
        first_thread = timer.timer_thread

        timer.start()
        second_thread = timer.timer_thread

        assert first_thread is second_thread

        timer.stop()

    def test_stop_stops_thread(self):
        """Test stop stops the timer thread."""
        timer = TimerDisplay()

        timer.start()
        timer.stop()

        assert timer.is_running is False
        assert timer.timer_thread is None

    def test_stop_idempotent(self):
        """Test calling stop twice doesn't raise."""
        timer = TimerDisplay()

        timer.start()
        timer.stop()
        timer.stop()  # Should not raise

        assert timer.is_running is False

    def test_stop_without_start(self):
        """Test stop without start doesn't raise."""
        timer = TimerDisplay()
        timer.stop()  # Should not raise

        assert timer.is_running is False

    def test_update_timer_display_writes_output(self):
        """Test timer display writes to stdout."""
        timer = TimerDisplay()
        timer.start_time = time.time()
        timer.is_running = True
        timer.stop_event.clear()

        # Capture stdout
        captured_output = io.StringIO()

        def mock_write(text):
            captured_output.write(text)
            timer.stop_event.set()  # Stop after first write

        with (
            patch.object(sys.stdout, "write", side_effect=mock_write),
            patch.object(sys.stdout, "flush"),
        ):
            timer._update_timer_display()

        output = captured_output.getvalue()
        assert "⌛" in output or "\r" in output

    def test_update_timer_display_handles_write_exception(self):
        """Test timer display handles stdout write exceptions."""
        timer = TimerDisplay()
        timer.start_time = time.time()
        timer.is_running = True
        timer.stop_event.clear()

        with patch.object(sys.stdout, "write", side_effect=Exception("IO Error")):
            # Should not raise, should break gracefully
            timer._update_timer_display()

        assert True  # If we get here, no exception was raised

    def test_timer_display_stop_handles_write_exception(self):
        """Test stop handles stdout write exceptions."""
        timer = TimerDisplay()
        timer.is_running = True
        timer.stop_event.clear()

        with (
            patch.object(sys.stdout, "write", side_effect=Exception("IO Error")),
            patch.object(sys.stdout, "flush"),
        ):
            timer.stop()

        assert timer.is_running is False

    def test_timer_display_formats_time_correctly(self):
        """Test timer formats time as MM:SS."""
        timer = TimerDisplay()
        timer.start_time = time.time() - 65  # 1 minute 5 seconds ago
        timer.is_running = True
        timer.stop_event.clear()

        captured_output = io.StringIO()
        call_count = [0]

        def mock_write(text):
            captured_output.write(text)
            call_count[0] += 1
            if call_count[0] >= 1:
                timer.stop_event.set()

        with (
            patch.object(sys.stdout, "write", side_effect=mock_write),
            patch.object(sys.stdout, "flush"),
        ):
            timer._update_timer_display()

        output = captured_output.getvalue()
        assert "01:05" in output or "01:0" in output
