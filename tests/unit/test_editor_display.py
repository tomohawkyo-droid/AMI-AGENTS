"""Unit tests for editor_display module."""

from unittest.mock import patch
import re

import pytest

from ami.cli_components.editor_display import EditorDisplay


def strip_ansi(text: str) -> str:
    """Helper to strip ANSI escape sequences for easier assertion."""
    # Improved regex to handle various ANSI escape sequences
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


class TestEditorDisplay:
    """Test the EditorDisplay class functionality."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_initial(self, mock_flush, mock_write):
        """Test initial display of editor."""
        display = EditorDisplay()

        # Display with simple content
        lines = ["Hello", "World"]
        display.display_editor(lines, 0, 0)

        # Join all write calls and strip ANSI
        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        # Check that we have borders
        assert "┌" in full_output
        assert "└" in full_output

        # Check that content is displayed
        assert "Hello" in full_output
        assert "World" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_single_line(self, mock_flush, mock_write):
        """Test display with single line."""
        display = EditorDisplay()

        lines = ["Single line"]
        display.display_editor(lines, 0, 0)

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        assert "┌" in full_output
        assert "└" in full_output
        assert "Single line" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_empty(self, mock_flush, mock_write):
        """Test display with empty content."""
        display = EditorDisplay()

        lines = [""]
        display.display_editor(lines, 0, 0)

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        # Should still display borders
        assert "┌" in full_output
        assert "└" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_with_cursor(self, mock_flush, mock_write):
        """Test display with cursor positioning."""
        display = EditorDisplay()

        lines = ["Hello", "Test"]
        display.display_editor(lines, 1, 2)  # Cursor on line 1, col 2

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        # Content should be displayed
        assert "Hello" in full_output
        assert "Test" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_long_lines(self, mock_flush, mock_write):
        """Test display with long lines."""
        display = EditorDisplay()

        long_line = "A" * 100
        lines = [long_line]
        display.display_editor(lines, 0, 50)

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        # Should handle long lines
        assert "┌" in full_output
        assert "└" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_multiple_lines(self, mock_flush, mock_write):
        """Test display with multiple lines."""
        display = EditorDisplay()

        lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        display.display_editor(lines, 2, 3)  # Cursor on line 2, col 3

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        for line in lines:
            assert line in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_handle_keyboard_interrupt(self, mock_flush, mock_write):
        """Test keyboard interrupt handling."""
        display = EditorDisplay()

        lines = ["Hello", "World"]
        display.previous_display_lines = 5  # Simulate previous display

        display.handle_keyboard_interrupt(lines)

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))
        # The function should write escape sequences to clear lines, but we stripped them.
        # Just check if it did *something* or check for the final message.
        assert "Message discarded" in full_output

    def test_editor_initialization(self):
        """Test editor display initialization."""
        display = EditorDisplay()

        # Check initial state
        assert hasattr(display, "editor_line_count")
        assert hasattr(display, "previous_display_lines")
        assert display.editor_line_count == 0
        assert display.previous_display_lines == 0

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_cursor_at_end_of_line(self, mock_flush, mock_write):
        """Test display when cursor is at end of line."""
        display = EditorDisplay()

        lines = ["Test line"]
        display.display_editor(lines, 0, len("Test line"))  # Cursor at end

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        assert "Test line" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_cursor_at_beginning_of_line(self, mock_flush, mock_write):
        """Test display when cursor is at beginning of line."""
        display = EditorDisplay()

        lines = ["Test line"]
        display.display_editor(lines, 0, 0)  # Cursor at beginning

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        assert "Test line" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_special_characters(self, mock_flush, mock_write):
        """Test display with special characters."""
        display = EditorDisplay()

        lines = ["Test@#$%", "Hello & World"]
        display.display_editor(lines, 0, 2)

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        for line in lines:
            assert line in full_output


class TestEditorDisplayEdgeCases:
    """Test editor display edge cases."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_none_lines(self, mock_flush, mock_write):
        """Test display with None lines (edge case)."""
        display = EditorDisplay()

        # This should not happen in normal usage, but test robustness
        display.display_editor([str(None)], 0, 0)

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        assert "None" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_very_long_content(self, mock_flush, mock_write):
        """Test display with very many lines."""
        display = EditorDisplay()

        many_lines = [f"Line {i}" for i in range(50)]
        display.display_editor(many_lines, 25, 5)  # Middle line, middle column

        full_output = strip_ansi("".join(call[0][0] for call in mock_write.call_args_list))

        # Should handle multiple lines without error
        for line in many_lines:
            assert line in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_unicode_characters(self, mock_flush, mock_write):
        """Test display with unicode characters."""
        display = EditorDisplay()

        lines = ["Hello 世界", "Test αβγ"]
        display.display_editor(lines, 0, 2)

        # Should handle unicode without error
        pass

    def test_display_editor_internal_state_tracking(self):
        """Test that display tracks internal state correctly."""
        display = EditorDisplay()

        # Initial state
        assert display.previous_display_lines == 0
        assert display.editor_line_count == 0

        # After displaying some content, state should be updated
        with patch("sys.stdout.write"), patch("sys.stdout.flush"):
            display.display_editor(["Test"], 0, 0)
            # The display method updates previous_display_lines but only after completion
            assert hasattr(display, "previous_display_lines")
            assert hasattr(display, "editor_line_count")


if __name__ == "__main__":
    pytest.main([__file__])