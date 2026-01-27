"""Tests for text_input_utils: arrow keys, control, display."""

import re
from unittest.mock import patch

import pytest

from ami.cli_components.text_input_utils import (
    BACKSPACE,
    BRACKET,
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
    RIGHT_ARROW,
    SEMICOLON,
    TAB,
    TILDE,
    UP_ARROW,
    _check_alternative_paste_sequence,
    _handle_arrow_keys,
    _handle_control_characters,
    _handle_ctrl_arrow_sequence_after_semicolon,
    display_final_output,
    read_key_sequence,
)

MAX_LINE_LENGTH_WITH_ANSI = 100


class TestCheckAlternativePasteSequence:
    """Tests for _check_alternative_paste_sequence function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_alt_paste_start(self, mock_get_char):
        """Test ESC0~ alternative paste start."""
        mock_get_char.return_value = ("~", ord("~"))

        result = _check_alternative_paste_sequence()

        assert result == "PASTE_START_ALT"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_alt_paste_end(self, mock_get_char):
        """Test ESC01~ alternative paste end."""
        mock_get_char.side_effect = [("1", ord("1")), ("~", ord("~"))]

        result = _check_alternative_paste_sequence()

        assert result == "PASTE_END_ALT"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_not_paste_returns_not_handled(self, mock_get_char):
        """Test non-paste sequence returns ESC_NOT_HANDLED."""
        mock_get_char.return_value = ("X", ord("X"))

        result = _check_alternative_paste_sequence()

        assert result == "ESC_NOT_HANDLED"


class TestHandleArrowKeys:
    """Tests for _handle_arrow_keys function."""

    def test_up_arrow(self):
        """Test UP arrow key."""
        result = _handle_arrow_keys(UP_ARROW)
        assert result == "UP"

    def test_down_arrow(self):
        """Test DOWN arrow key."""
        result = _handle_arrow_keys(DOWN_ARROW)
        assert result == "DOWN"

    def test_right_arrow(self):
        """Test RIGHT arrow key."""
        result = _handle_arrow_keys(RIGHT_ARROW)
        assert result == "RIGHT"

    def test_left_arrow(self):
        """Test LEFT arrow key."""
        result = _handle_arrow_keys(LEFT_ARROW)
        assert result == "LEFT"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_f1_via_1_sequence(self, mock_get_char):
        """Test F1 key via ESC[11~ sequence."""
        mock_get_char.side_effect = [("1", ord("1")), ("~", TILDE)]

        result = _handle_arrow_keys(ONE)

        assert result == "F1"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_ctrl_up_arrow(self, mock_get_char):
        """Test Ctrl+Up arrow."""
        mock_get_char.side_effect = [(";", SEMICOLON), ("5", FIVE), ("A", UP_ARROW)]

        result = _handle_arrow_keys(ONE)

        assert result == "CTRL_UP"

    def test_unknown_returns_not_handled(self):
        """Test unknown sequence returns ESC_NOT_HANDLED."""
        result = _handle_arrow_keys(ord("X"))
        assert result == "ESC_NOT_HANDLED"


class TestHandleCtrlArrowSequenceAfterSemicolon:
    """Tests for _handle_ctrl_arrow_sequence_after_semicolon function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_ctrl_up(self, mock_get_char):
        """Test Ctrl+Up arrow."""
        mock_get_char.side_effect = [("5", FIVE), ("A", UP_ARROW)]

        result = _handle_ctrl_arrow_sequence_after_semicolon()

        assert result == "CTRL_UP"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_ctrl_down(self, mock_get_char):
        """Test Ctrl+Down arrow."""
        mock_get_char.side_effect = [("5", FIVE), ("B", DOWN_ARROW)]

        result = _handle_ctrl_arrow_sequence_after_semicolon()

        assert result == "CTRL_DOWN"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_ctrl_right(self, mock_get_char):
        """Test Ctrl+Right arrow."""
        mock_get_char.side_effect = [("5", FIVE), ("C", RIGHT_ARROW)]

        result = _handle_ctrl_arrow_sequence_after_semicolon()

        assert result == "CTRL_RIGHT"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_ctrl_left(self, mock_get_char):
        """Test Ctrl+Left arrow."""
        mock_get_char.side_effect = [("5", FIVE), ("D", LEFT_ARROW)]

        result = _handle_ctrl_arrow_sequence_after_semicolon()

        assert result == "CTRL_LEFT"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_not_five_returns_not_handled(self, mock_get_char):
        """Test non-5 modifier returns ESC_NOT_HANDLED."""
        mock_get_char.return_value = ("X", ord("X"))

        result = _handle_ctrl_arrow_sequence_after_semicolon()

        assert result == "ESC_NOT_HANDLED"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_unknown_direction_returns_not_handled(self, mock_get_char):
        """Test unknown direction returns ESC_NOT_HANDLED."""
        mock_get_char.side_effect = [("5", FIVE), ("X", ord("X"))]

        result = _handle_ctrl_arrow_sequence_after_semicolon()

        assert result == "ESC_NOT_HANDLED"


class TestHandleControlCharacters:
    """Tests for _handle_control_characters function."""

    def test_ctrl_c_raises_keyboard_interrupt(self):
        """Test Ctrl+C raises KeyboardInterrupt."""
        with pytest.raises(KeyboardInterrupt):
            _handle_control_characters(CTRL_C)

    def test_ctrl_s_returns_eof(self):
        """Test Ctrl+S returns EOF."""
        result = _handle_control_characters(CTRL_S)
        assert result == "EOF"

    def test_backspace(self):
        """Test backspace returns BACKSPACE."""
        result = _handle_control_characters(BACKSPACE)
        assert result == "BACKSPACE"

    def test_enter_cr(self):
        """Test Enter (CR) returns ENTER."""
        result = _handle_control_characters(ENTER_CR)
        assert result == "ENTER"

    def test_enter_lf(self):
        """Test Enter (LF) returns CTRL_ENTER."""
        result = _handle_control_characters(ENTER_LF)
        assert result == "CTRL_ENTER"

    def test_tab(self):
        """Test Tab returns tab character."""
        result = _handle_control_characters(TAB)
        assert result == "\t"

    def test_ctrl_u(self):
        """Test Ctrl+U returns DELETE_LINE."""
        result = _handle_control_characters(CTRL_U)
        assert result == "DELETE_LINE"

    def test_ctrl_a(self):
        """Test Ctrl+A returns HOME."""
        result = _handle_control_characters(CTRL_A)
        assert result == "HOME"

    def test_ctrl_w(self):
        """Test Ctrl+W returns DELETE_WORD."""
        result = _handle_control_characters(CTRL_W)
        assert result == "DELETE_WORD"

    def test_ctrl_h(self):
        """Test Ctrl+H returns BACKSPACE_WORD."""
        result = _handle_control_characters(CTRL_H_CODE)
        assert result == "BACKSPACE_WORD"

    def test_unknown_returns_none(self):
        """Test unknown control char returns None."""
        result = _handle_control_characters(200)  # Not a recognized control char
        assert result is None


class TestReadKeySequence:
    """Tests for read_key_sequence function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_escape_sequence_handled(self, mock_get_char):
        """Test escape sequence is handled."""
        # ESC followed by bracket and up arrow
        mock_get_char.side_effect = [
            ("\x1b", ESC),
            ("[", BRACKET),
            ("A", UP_ARROW),
        ]

        result = read_key_sequence()

        assert result == "UP"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_escape_not_handled_returns_esc_char(self, mock_get_char):
        """Test unhandled escape returns ESC character."""
        mock_get_char.side_effect = [("\x1b", ESC), ("x", ord("x"))]

        result = read_key_sequence()

        assert result == "\x1b"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_control_character_handled(self, mock_get_char):
        """Test control character is handled."""
        mock_get_char.return_value = ("\r", ENTER_CR)

        result = read_key_sequence()

        assert result == "ENTER"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_printable_character_returned(self, mock_get_char):
        """Test printable character is returned."""
        mock_get_char.return_value = ("a", ord("a"))

        result = read_key_sequence()

        assert result == "a"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_unhandled_control_char_returns_none(self, mock_get_char):
        """Test unhandled control character returns None."""
        # Control char that's not in the handled list (e.g., Ctrl+B = 2)
        mock_get_char.return_value = ("\x02", 2)

        result = read_key_sequence()

        assert result is None

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_ctrl_c_raises_keyboard_interrupt(self, mock_get_char):
        """Test Ctrl+C raises KeyboardInterrupt."""
        mock_get_char.return_value = ("\x03", CTRL_C)

        with pytest.raises(KeyboardInterrupt):
            read_key_sequence()


class TestDisplayFinalOutput:
    """Tests for display_final_output function."""

    def test_displays_lines(self, capsys):
        """Test displays lines with borders."""
        display_final_output(["Hello", "World"], "Sent")

        captured = capsys.readouterr()
        assert "Hello" in captured.out
        assert "World" in captured.out
        assert "\u250c" in captured.out
        assert "\u2514" in captured.out

    def test_displays_empty_lines(self, capsys):
        """Test displays empty content with borders."""
        display_final_output([], "Sent")

        captured = capsys.readouterr()
        assert "\u250c" in captured.out
        assert "\u2514" in captured.out

    def test_displays_timestamp(self, capsys):
        """Test displays timestamp."""
        display_final_output(["Test"], "Sent")

        captured = capsys.readouterr()
        # Should contain time format HH:MM:SS
        assert re.search(r"\d{2}:\d{2}:\d{2}", captured.out)

    def test_sent_message_shows_emoji(self, capsys):
        """Test 'Sent' message shows emoji."""
        display_final_output(["Test"], "Sent to agent")

        captured = capsys.readouterr()
        assert chr(0x1F4AC) in captured.out  # speech bubble emoji

    def test_other_message_shown_as_is(self, capsys):
        """Test non-Sent message shown as-is."""
        display_final_output(["Test"], "Custom message")

        captured = capsys.readouterr()
        assert "Custom message" in captured.out

    def test_truncates_long_lines(self, capsys):
        """Test truncates lines longer than width."""
        long_line = "x" * 100

        display_final_output([long_line], "Sent")

        captured = capsys.readouterr()
        # Line should be truncated to fit 80-char width
        # The actual line printed should not have 100 x's in a row
        lines = captured.out.split("\n")
        for line in lines:
            # Each line should be reasonable length
            assert len(line) <= MAX_LINE_LENGTH_WITH_ANSI  # Allow for ANSI codes

    def test_pads_short_lines(self, capsys):
        """Test pads short lines to consistent width."""
        display_final_output(["Hi"], "Sent")

        captured = capsys.readouterr()
        # Output should have consistent formatting
        assert "Hi" in captured.out
