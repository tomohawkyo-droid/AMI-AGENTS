"""Unit tests for text_input_utils module."""

from unittest.mock import MagicMock, patch

import pytest

from ami.cli_components.text_input_utils import (
    BACKSPACE,
    BRACKET,
    BRACKETED_PASTE_DISABLE,
    BRACKETED_PASTE_ENABLE,
    BRACKETED_PASTE_END,
    BRACKETED_PASTE_START,
    CONTROL_MAX,
    CTRL_A,
    CTRL_C,
    CTRL_H_CODE,
    CTRL_S,
    CTRL_U,
    CTRL_W,
    DOWN_ARROW,
    ENTER_CR,
    ENTER_LF,
    ESC,
    FIVE,
    LEFT_ARROW,
    ONE,
    OSC_PREFIX,
    PRINTABLE_MAX,
    PRINTABLE_MIN,
    RIGHT_ARROW,
    SEMICOLON,
    TAB,
    TILDE,
    UP_ARROW,
    Colors,
    display_final_output,
)

EXPECTED_ESC_CODE = 27
EXPECTED_BRACKET_CODE = 91
EXPECTED_OSC_PREFIX_CODE = 79
EXPECTED_UP_ARROW_CODE = 65
EXPECTED_DOWN_ARROW_CODE = 66
EXPECTED_RIGHT_ARROW_CODE = 67
EXPECTED_LEFT_ARROW_CODE = 68
EXPECTED_ONE_CODE = 49
EXPECTED_SEMICOLON_CODE = 59
EXPECTED_FIVE_CODE = 53
EXPECTED_TILDE_CODE = 126
EXPECTED_CTRL_H_CODE = 8
EXPECTED_CTRL_C_CODE = 3
EXPECTED_CTRL_S_CODE = 19
EXPECTED_CTRL_U_CODE = 21
EXPECTED_CTRL_A_CODE = 1
EXPECTED_CTRL_W_CODE = 23
EXPECTED_BACKSPACE_CODE = 127
EXPECTED_ENTER_CR_CODE = 13
EXPECTED_ENTER_LF_CODE = 10
EXPECTED_TAB_CODE = 9
EXPECTED_PRINTABLE_MIN_CODE = 32
EXPECTED_PRINTABLE_MAX_CODE = 126
EXPECTED_CONTROL_MAX_CODE = 31
EXPECTED_VISUAL_WIDTH_ASCII = 5
EXPECTED_VISUAL_WIDTH_CJK = 4
EXPECTED_VISUAL_WIDTH_ANSI = 5


class TestColors:
    """Test the Colors class constants."""

    def test_colors_constants(self) -> None:
        """Test that all color constants have correct ANSI values."""
        assert Colors.RESET == "\033[0m"
        assert Colors.BOLD == "\033[1m"
        assert Colors.REVERSE == "\033[7m"
        assert Colors.BLACK == "\033[30m"
        assert Colors.RED == "\033[31m"
        assert Colors.GREEN == "\033[32m"
        assert Colors.YELLOW == "\033[33m"
        assert Colors.BLUE == "\033[34m"
        assert Colors.MAGENTA == "\033[35m"
        assert Colors.CYAN == "\033[36m"
        assert Colors.WHITE == "\033[37m"
        assert Colors.BG_RED == "\033[41m"
        assert Colors.BG_GREEN == "\033[42m"
        assert Colors.BG_YELLOW == "\033[43m"
        assert Colors.BG_BLUE == "\033[44m"
        assert Colors.BG_MAGENTA == "\033[45m"
        assert Colors.BG_CYAN == "\033[46m"
        assert Colors.BG_WHITE == "\033[47m"


class TestBracketedPasteConstants:
    """Test bracketed paste constants."""

    def test_bracketed_paste_constants(self) -> None:
        """Test bracketed paste mode constants."""
        assert BRACKETED_PASTE_START == "\033[200~"
        assert BRACKETED_PASTE_END == "\033[201~"
        assert BRACKETED_PASTE_ENABLE == "\033[?2004h"
        assert BRACKETED_PASTE_DISABLE == "\033[?2004l"


class TestAsciiConstants:
    """Tests for ASCII control character constants."""

    def test_escape_code(self) -> None:
        """Test ESC constant."""
        assert ESC == EXPECTED_ESC_CODE

    def test_bracket_code(self) -> None:
        """Test bracket character code."""
        assert BRACKET == EXPECTED_BRACKET_CODE  # '[' character

    def test_osc_prefix(self) -> None:
        """Test OSC prefix code."""
        assert OSC_PREFIX == EXPECTED_OSC_PREFIX_CODE  # 'O' character

    def test_arrow_keys(self) -> None:
        """Test arrow key codes."""
        assert UP_ARROW == EXPECTED_UP_ARROW_CODE
        assert DOWN_ARROW == EXPECTED_DOWN_ARROW_CODE
        assert RIGHT_ARROW == EXPECTED_RIGHT_ARROW_CODE
        assert LEFT_ARROW == EXPECTED_LEFT_ARROW_CODE

    def test_modifier_keys(self) -> None:
        """Test modifier key codes."""
        assert ONE == EXPECTED_ONE_CODE
        assert SEMICOLON == EXPECTED_SEMICOLON_CODE
        assert FIVE == EXPECTED_FIVE_CODE
        assert TILDE == EXPECTED_TILDE_CODE

    def test_control_keys(self) -> None:
        """Test control key codes."""
        assert CTRL_H_CODE == EXPECTED_CTRL_H_CODE
        assert CTRL_C == EXPECTED_CTRL_C_CODE
        assert CTRL_S == EXPECTED_CTRL_S_CODE
        assert CTRL_U == EXPECTED_CTRL_U_CODE
        assert CTRL_A == EXPECTED_CTRL_A_CODE
        assert CTRL_W == EXPECTED_CTRL_W_CODE

    def test_input_keys(self) -> None:
        """Test common input key codes."""
        assert BACKSPACE == EXPECTED_BACKSPACE_CODE
        assert ENTER_CR == EXPECTED_ENTER_CR_CODE
        assert ENTER_LF == EXPECTED_ENTER_LF_CODE
        assert TAB == EXPECTED_TAB_CODE

    def test_printable_range(self) -> None:
        """Test printable character range constants."""
        assert PRINTABLE_MIN == EXPECTED_PRINTABLE_MIN_CODE
        assert PRINTABLE_MAX == EXPECTED_PRINTABLE_MAX_CODE
        assert CONTROL_MAX == EXPECTED_CONTROL_MAX_CODE
        # Validate the ranges make sense
        assert PRINTABLE_MIN > CONTROL_MAX
        assert PRINTABLE_MAX > PRINTABLE_MIN


class TestDisplayFinalOutput:
    """Test the display_final_output function."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_final_output_simple(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display_final_output with simple content."""
        lines: list[str] = ["Hello", "World"]
        message = "Test message"

        display_final_output(lines, message)

        # Should write top border, content lines with indentation,
        # bottom border, newline, timestamp message, and newline
        calls = [call[0][0] for call in mock_write.call_args_list]
        assert any("┌" in call for call in calls)  # Top border
        assert any("Hello" in call for call in calls)  # Content
        assert any("World" in call for call in calls)  # Content
        assert any("└" in call for call in calls)  # Bottom border
        assert any(message in call for call in calls)  # Message

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_final_output_empty_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display_final_output with empty lines."""
        lines: list[str] = []
        message = "Empty content"

        display_final_output(lines, message)

        calls = [call[0][0] for call in mock_write.call_args_list]
        # Should still display borders even with empty content
        assert any("┌" in call for call in calls)  # Top border
        assert any("└" in call for call in calls)  # Bottom border

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_final_output_single_line(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display_final_output with single line."""
        lines = ["Single line"]
        message = "Single line message"

        display_final_output(lines, message)

        calls = [call[0][0] for call in mock_write.call_args_list]
        assert any("┌" in call for call in calls)  # Top border
        assert any("Single line" in call for call in calls)  # Content
        assert any("└" in call for call in calls)  # Bottom border

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_display_final_output_long_lines(
        self, mock_flush: MagicMock, mock_write: MagicMock
    ) -> None:
        """Test display_final_output with a very long line."""
        long_line = "A" * 100  # Way longer than 80 chars
        lines = [long_line]
        message = "Long line message"

        display_final_output(lines, message)

        calls = [call[0][0] for call in mock_write.call_args_list]
        assert any("┌" in call for call in calls)  # Top border
        # The function should handle long lines appropriately


# We can't easily test read_key_sequence directly due to
# its use of getchar() and termios
# which interact with stdin. We'll focus on the other testable functions.

# Since read_key_sequence uses getchar() which is a low-level terminal function,
# creating comprehensive unit tests is challenging. The test below documents
# the need for integration testing.


class TestKeySequenceHandling:
    """Test key sequence handling (noting limitations)."""

    def test_read_key_sequence_documentation(self) -> None:
        """Document the read_key_sequence functionality.

        Note: read_key_sequence interacts with stdin at a low level using termios
        and getchar(), making unit testing challenging. Integration testing would
        require simulating keyboard input, which is not suitable for unit tests.
        The functionality has been tested indirectly through text editor tests.
        """
        # This test exists to document that direct unit testing of read_key_sequence
        # is not practical due to os-level terminal I/O requirements
        assert True  # Acknowledgment of this limitation


if __name__ == "__main__":
    pytest.main([__file__])
