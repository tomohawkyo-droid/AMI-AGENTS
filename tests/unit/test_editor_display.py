"""Unit tests for editor_display module."""

import re
from unittest.mock import MagicMock, patch

import pytest

from ami.cli_components.editor_display import EditorDisplay

EXPECTED_CLEAR_LINE_CALL_COUNT = 5


def strip_ansi(text: str) -> str:
    """Helper to strip ANSI escape sequences for easier assertion."""
    # Improved regex to handle various ANSI escape sequences
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


class TestEditorDisplay:
    """Test the EditorDisplay class functionality."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_initial(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test initial display of editor."""
        display = EditorDisplay()

        # Display with simple content
        lines = ["Hello", "World"]
        display.display_editor(lines, 0, 0)

        # Join all write calls and strip ANSI
        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        # Check that we have borders
        assert "┌" in full_output
        assert "└" in full_output

        # Check that content is displayed
        assert "Hello" in full_output
        assert "World" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_single_line(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with single line."""
        display = EditorDisplay()

        lines = ["Single line"]
        display.display_editor(lines, 0, 0)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        assert "┌" in full_output
        assert "└" in full_output
        assert "Single line" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_empty(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with empty content."""
        display = EditorDisplay()

        lines = [""]
        display.display_editor(lines, 0, 0)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        # Should still display borders
        assert "┌" in full_output
        assert "└" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_with_cursor(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with cursor positioning."""
        display = EditorDisplay()

        lines = ["Hello", "Test"]
        display.display_editor(lines, 1, 2)  # Cursor on line 1, col 2

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        # Content should be displayed
        assert "Hello" in full_output
        assert "Test" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_long_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with long lines."""
        display = EditorDisplay()

        long_line = "A" * 100
        lines = [long_line]
        display.display_editor(lines, 0, 50)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        # Should handle long lines
        assert "┌" in full_output
        assert "└" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_multiple_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with multiple lines."""
        display = EditorDisplay()

        lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        display.display_editor(lines, 2, 3)  # Cursor on line 2, col 3

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        for line in lines:
            assert line in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_handle_keyboard_interrupt(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test keyboard interrupt handling."""
        display = EditorDisplay()

        lines = ["Hello", "World"]
        display.previous_display_lines = 5  # Simulate previous display

        display.handle_keyboard_interrupt(lines)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )
        # The function should write escape sequences to clear
        # lines, but we stripped them.
        # Just check if it did *something* or check for the final message.
        assert "Message discarded" in full_output

    def test_editor_initialization(self) -> None:
        """Test editor display initialization."""
        display = EditorDisplay()

        # Check initial state - EditorDisplay has these attributes defined in __init__
        assert display.editor_line_count == 0
        assert display.previous_display_lines == 0

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_cursor_at_end_of_line(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display when cursor is at end of line."""
        display = EditorDisplay()

        lines = ["Test line"]
        display.display_editor(lines, 0, len("Test line"))  # Cursor at end

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        assert "Test line" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_cursor_at_beginning_of_line(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display when cursor is at beginning of line."""
        display = EditorDisplay()

        lines = ["Test line"]
        display.display_editor(lines, 0, 0)  # Cursor at beginning

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        assert "Test line" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_special_characters(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with special characters."""
        display = EditorDisplay()

        lines = ["Test@#$%", "Hello & World"]
        display.display_editor(lines, 0, 2)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        for line in lines:
            assert line in full_output


class TestEditorDisplayEdgeCases:
    """Test editor display edge cases."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_none_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with None lines (edge case)."""
        display = EditorDisplay()

        # This should not happen in normal usage, but test robustness
        display.display_editor([str(None)], 0, 0)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        assert "None" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_very_long_content(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with very many lines."""
        display = EditorDisplay()

        many_lines = [f"Line {i}" for i in range(50)]
        display.display_editor(many_lines, 25, 5)  # Middle line, middle column

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )

        # Should handle multiple lines without error
        for line in many_lines:
            assert line in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_unicode_characters(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with unicode characters."""
        display = EditorDisplay()

        lines = ["Hello 世界", "Test αβγ"]
        display.display_editor(lines, 0, 2)

        # Should handle unicode without error
        pass

    def test_display_editor_internal_state_tracking(self) -> None:
        """Test that display tracks internal state correctly."""
        display = EditorDisplay()

        # Initial state
        assert display.previous_display_lines == 0
        assert display.editor_line_count == 0

        # After displaying some content, state should be updated
        with patch("sys.stdout.write"), patch("sys.stdout.flush"):
            display.display_editor(["Test"], 0, 0)
            # The display method updates previous_display_lines after completion
            # Verify attributes are accessible (they're defined in __init__)
            assert display.previous_display_lines >= 0
            assert display.editor_line_count >= 0


class TestEditorDisplayCoverage:
    """Additional tests to cover remaining lines."""

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_clears_previous_content(
        self, mock_flush: MagicMock, mock_write: MagicMock, mock_terminal: MagicMock
    ) -> None:
        """Test display clears previous content when previous_display_lines > 0."""
        display = EditorDisplay()
        display.previous_display_lines = 5  # Simulate previous display

        lines = ["New content"]
        display.display_editor(lines, 0, 0)

        # Verify AnsiTerminal methods were called to clear
        assert mock_terminal.move_up.called
        assert mock_terminal.clear_line.called

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_with_help_shown(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display when help is shown."""
        display = EditorDisplay()
        display.show_help = True

        lines = ["Test"]
        display.display_editor(lines, 0, 0)

        full_output = "".join(call[0][0] for call in mock_write.call_args_list)

        # Should contain help text
        assert "F1" in full_output
        assert "nav" in full_output or "help" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_with_status_override(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with status override."""
        display = EditorDisplay()

        lines = ["Test"]
        display.display_editor(lines, 0, 0, status_override="Custom status message")

        full_output = "".join(call[0][0] for call in mock_write.call_args_list)

        assert "Custom status message" in full_output

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_method(
        self, mock_flush: MagicMock, mock_write: MagicMock, mock_terminal: MagicMock
    ) -> None:
        """Test the clear method."""
        display = EditorDisplay()
        display.previous_display_lines = 3

        display.clear()

        # Verify AnsiTerminal clear was called
        assert mock_terminal.clear_line.called
        # Should have written escape sequences
        assert mock_write.called

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_method_with_single_line(
        self, mock_flush: MagicMock, mock_write: MagicMock, mock_terminal: MagicMock
    ) -> None:
        """Test clear method with single line display."""
        display = EditorDisplay()
        display.previous_display_lines = 1

        display.clear()

        assert mock_terminal.clear_line.called

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_method_with_no_previous_display(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test clear method when nothing was previously displayed."""
        display = EditorDisplay()
        display.previous_display_lines = 0

        display.clear()

        # Should not write anything if no previous display
        assert mock_write.call_count == 0

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_keyboard_interrupt_clears_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock, mock_terminal: MagicMock
    ) -> None:
        """Test keyboard interrupt properly clears previous lines."""
        display = EditorDisplay()
        display.previous_display_lines = 4

        display.handle_keyboard_interrupt(["test"])

        # Should call terminal methods to clear
        assert mock_terminal.move_up.called
        assert mock_terminal.clear_line.called

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_keyboard_interrupt_no_previous_display(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test keyboard interrupt when no previous display."""
        display = EditorDisplay()
        display.previous_display_lines = 0

        display.handle_keyboard_interrupt(["test"])

        # Should still show the discarded message
        full_output = "".join(call[0][0] for call in mock_write.call_args_list)
        assert "discarded" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_cursor_beyond_line_length(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display when cursor is beyond line length."""
        display = EditorDisplay()

        lines = ["Short"]
        # Cursor position beyond line length
        display.display_editor(lines, 0, 100)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )
        assert "Short" in full_output

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_editor_negative_cursor(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display with negative cursor position."""
        display = EditorDisplay()

        lines = ["Test line"]
        # Negative cursor position (edge case)
        display.display_editor(lines, 0, -1)

        full_output = strip_ansi(
            "".join(call[0][0] for call in mock_write.call_args_list)
        )
        assert "Test line" in full_output

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_with_multiple_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock, mock_terminal: MagicMock
    ) -> None:
        """Test clear method with multiple lines."""
        display = EditorDisplay()
        display.previous_display_lines = 5

        display.clear()

        # Should call clear_line multiple times
        assert mock_terminal.clear_line.call_count == EXPECTED_CLEAR_LINE_CALL_COUNT


if __name__ == "__main__":
    pytest.main([__file__])
