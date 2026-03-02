"""Deep integration tests for terminal UI components.

Tests ami/cli_components/terminal/ansi.py, ami/cli_components/dialogs.py,
ami/cli_components/editor_display.py, and ami/cli_components/text_input_utils.py.
"""

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from ami.cli_components.dialogs import (
    AlertDialog,
    BaseDialog,
    ConfirmationDialog,
    strip_ansi,
    visible_len,
)
from ami.cli_components.editor_display import EditorDisplay
from ami.cli_components.terminal.ansi import AnsiTerminal
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
    _handle_control_characters,
    display_final_output,
)
from ami.core.config import _ConfigSingleton

# Named constants for magic numbers used in assertions
DEFAULT_DIALOG_WIDTH = 80
CUSTOM_DIALOG_WIDTH = 120
DISPLAY_LINE_WIDTH = 78
VISIBLE_LEN_HELLO = 5


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Reset the config singleton before and after each test."""
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# -- 1. AnsiTerminal static methods -----------------------------------------


class TestAnsiTerminalStaticMethods:
    """Cursor / screen methods emit correct ANSI escape sequences."""

    @pytest.mark.parametrize(
        ("method", "args", "expected"),
        [
            ("move_up", (3,), "\033[3A"),
            ("move_down", (2,), "\033[2B"),
            ("move_right", (5,), "\033[5C"),
            ("move_left", (4,), "\033[4D"),
            ("move_to_column", (10,), "\033[10G"),
            ("clear_line", (), "\033[2K"),
            ("clear_screen", (), "\033[2J\033[H"),
            ("hide_cursor", (), "\033[?25l"),
            ("show_cursor", (), "\033[?25h"),
            ("move_up", (), "\033[1A"),  # default n=1
        ],
    )
    def test_write_escape(self, method, args, expected):
        mock_stdout = MagicMock()
        with patch.object(sys, "stdout", mock_stdout):
            getattr(AnsiTerminal, method)(*args)
        mock_stdout.write.assert_called_once_with(expected)
        mock_stdout.flush.assert_called_once()

    @pytest.mark.parametrize(
        "method",
        [
            "move_up",
            "move_down",
            "move_right",
            "move_left",
        ],
    )
    def test_zero_does_not_write(self, method):
        mock_stdout = MagicMock()
        with patch.object(sys, "stdout", mock_stdout):
            getattr(AnsiTerminal, method)(0)
        mock_stdout.write.assert_not_called()

    def test_negative_does_not_write(self):
        mock_stdout = MagicMock()
        with patch.object(sys, "stdout", mock_stdout):
            AnsiTerminal.move_up(-1)
        mock_stdout.write.assert_not_called()

    def test_colorize_red(self):
        assert (
            AnsiTerminal.colorize("hello", AnsiTerminal.RED) == "\033[31mhello\033[0m"
        )

    def test_colorize_bold(self):
        assert (
            AnsiTerminal.colorize("world", AnsiTerminal.BOLD) == "\033[1mworld\033[0m"
        )

    def test_colorize_empty(self):
        assert AnsiTerminal.colorize("", AnsiTerminal.GREEN) == "\033[32m\033[0m"


# -- 2. AnsiTerminal constants ----------------------------------------------


class TestAnsiTerminalConstants:
    """All ANSI constant values match expected escape sequences."""

    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            ("RESET", "\033[0m"),
            ("BOLD", "\033[1m"),
            ("DIM", "\033[2m"),
            ("ITALIC", "\033[3m"),
            ("UNDERLINE", "\033[4m"),
            ("REVERSE", "\033[7m"),
            ("HIDDEN", "\033[8m"),
            ("STRIKETHROUGH", "\033[9m"),
        ],
    )
    def test_formatting(self, attr, expected):
        assert getattr(AnsiTerminal, attr) == expected

    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            ("BLACK", "\033[30m"),
            ("RED", "\033[31m"),
            ("GREEN", "\033[32m"),
            ("YELLOW", "\033[33m"),
            ("BLUE", "\033[34m"),
            ("MAGENTA", "\033[35m"),
            ("CYAN", "\033[36m"),
            ("WHITE", "\033[37m"),
        ],
    )
    def test_foreground(self, attr, expected):
        assert getattr(AnsiTerminal, attr) == expected

    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            ("BG_BLACK", "\033[40m"),
            ("BG_RED", "\033[41m"),
            ("BG_GREEN", "\033[42m"),
            ("BG_YELLOW", "\033[43m"),
            ("BG_BLUE", "\033[44m"),
            ("BG_MAGENTA", "\033[45m"),
            ("BG_CYAN", "\033[46m"),
            ("BG_WHITE", "\033[47m"),
        ],
    )
    def test_background(self, attr, expected):
        assert getattr(AnsiTerminal, attr) == expected

    def test_foreground_and_background_disjoint(self):
        fg = {
            getattr(AnsiTerminal, c)
            for c in (
                "BLACK",
                "RED",
                "GREEN",
                "YELLOW",
                "BLUE",
                "MAGENTA",
                "CYAN",
                "WHITE",
            )
        }
        bg = {
            getattr(AnsiTerminal, c)
            for c in (
                "BG_BLACK",
                "BG_RED",
                "BG_GREEN",
                "BG_YELLOW",
                "BG_BLUE",
                "BG_MAGENTA",
                "BG_CYAN",
                "BG_WHITE",
            )
        }
        assert fg.isdisjoint(bg)


# -- 3. AlertDialog construction --------------------------------------------


class TestAlertDialogConstruction:
    """AlertDialog initializes with correct defaults and overrides."""

    def test_default_title(self):
        assert AlertDialog("msg").title == "Alert"

    def test_custom_title(self):
        assert AlertDialog("msg", title="Warning").title == "Warning"

    def test_message(self):
        assert AlertDialog("File not found").message == "File not found"

    def test_default_width(self):
        assert AlertDialog("text").width == DEFAULT_DIALOG_WIDTH

    def test_custom_width(self):
        dlg = AlertDialog("text", width=CUSTOM_DIALOG_WIDTH)
        assert dlg.width == CUSTOM_DIALOG_WIDTH

    def test_last_render_lines_zero(self):
        assert AlertDialog("text")._last_render_lines == 0


# -- 4. ConfirmationDialog construction -------------------------------------


class TestConfirmationDialogConstruction:
    """ConfirmationDialog initializes with correct defaults."""

    def test_default_title(self):
        assert ConfirmationDialog("sure?").title == "Confirmation"

    def test_selected_yes_default(self):
        assert ConfirmationDialog("sure?").selected_yes is True

    def test_message(self):
        assert ConfirmationDialog("Delete?").message == "Delete?"

    def test_custom_title(self):
        assert ConfirmationDialog("msg", title="Rm?").title == "Rm?"

    def test_default_width(self):
        assert ConfirmationDialog("msg").width == DEFAULT_DIALOG_WIDTH

    def test_last_render_lines_zero(self):
        assert ConfirmationDialog("msg")._last_render_lines == 0


# -- 5. EditorDisplay construction ------------------------------------------


class TestEditorDisplayConstruction:
    """EditorDisplay initializes with correct defaults."""

    def test_editor_line_count_zero(self):
        assert EditorDisplay().editor_line_count == 0

    def test_previous_display_lines_zero(self):
        assert EditorDisplay().previous_display_lines == 0

    def test_show_help_false(self):
        assert EditorDisplay().show_help is False

    def test_all_defaults(self):
        ed = EditorDisplay()
        assert (ed.editor_line_count, ed.previous_display_lines, ed.show_help) == (
            0,
            0,
            False,
        )


# -- 6. _handle_control_characters ------------------------------------------


class TestHandleControlCharacters:
    """_handle_control_characters maps ordinals to action strings."""

    def test_ctrl_c_raises(self):
        with pytest.raises(KeyboardInterrupt):
            _handle_control_characters(3)

    @pytest.mark.parametrize(
        ("ordinal", "expected"),
        [
            (19, "SUBMIT"),
            (127, "BACKSPACE"),
            (13, "ENTER"),
            (10, "ALT_ENTER"),
            (9, "\t"),
            (21, "DELETE_LINE"),
            (1, "HOME"),
            (23, "DELETE_WORD"),
            (8, "BACKSPACE_WORD"),
        ],
    )
    def test_control_map(self, ordinal, expected):
        assert _handle_control_characters(ordinal) == expected

    @pytest.mark.parametrize("ordinal", [0, 99, 200])
    def test_unknown_returns_none(self, ordinal):
        assert _handle_control_characters(ordinal) is None


# -- 7. display_final_output ------------------------------------------------


class TestDisplayFinalOutput:
    """display_final_output writes correct bordered output."""

    def test_borders_and_timestamp_for_sent(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output(["hello world"], "Sent")
        output = buf.getvalue()
        assert "\u250c" in output  # top-left
        assert "\u2510" in output  # top-right
        assert "\u2514" in output  # bottom-left
        assert "\u2518" in output  # bottom-right
        assert "  hello world" in output
        assert "\U0001f4ac" in output  # speech balloon emoji

    def test_empty_lines_placeholder(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output([], "Sent")
        output = buf.getvalue()
        assert "\u250c" in output
        assert "\u2514" in output
        lines = output.split("\n")
        top = next(i for i, ln in enumerate(lines) if "\u250c" in ln)
        bot = next(i for i, ln in enumerate(lines) if "\u2514" in ln)
        content = lines[top + 1 : bot]
        assert len(content) >= 1
        assert content[0] == " " * 78

    def test_non_sent_message(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output(["test"], "Cancelled")
        assert "Cancelled" in buf.getvalue()

    def test_multiple_lines(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output(["line one", "line two", "line three"], "Sent")
        output = buf.getvalue()
        for text in ("  line one", "  line two", "  line three"):
            assert text in output

    def test_long_line_truncated(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output(["x" * 200], "Sent")
        for ln in buf.getvalue().split("\n"):
            if "x" in ln:
                assert len(ln) == DISPLAY_LINE_WIDTH

    def test_sent_substring_triggers_emoji(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output(["data"], "Message Sent successfully")
        assert "\U0001f4ac" in buf.getvalue()

    def test_trailing_newline(self):
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            display_final_output(["test"], "Sent")
        assert buf.getvalue().endswith("\n")


# -- 8. text_input_utils constants ------------------------------------------


class TestTextInputUtilsConstants:
    """All key-code constants have their expected integer / string values."""

    @pytest.mark.parametrize(
        ("const", "value"),
        [
            (ESC, 27),
            (CTRL_C, 3),
            (CTRL_S, 19),
            (BACKSPACE, 127),
            (ENTER_CR, 13),
            (ENTER_LF, 10),
            (TAB, 9),
            (CTRL_U, 21),
            (CTRL_A, 1),
            (CTRL_W, 23),
            (CTRL_H_CODE, 8),
            (PRINTABLE_MIN, 32),
            (PRINTABLE_MAX, 126),
            (CONTROL_MAX, 31),
            (BRACKET, 91),
            (OSC_PREFIX, 79),
            (UP_ARROW, 65),
            (DOWN_ARROW, 66),
            (RIGHT_ARROW, 67),
            (LEFT_ARROW, 68),
            (ONE, 49),
            (SEMICOLON, 59),
            (FIVE, 53),
            (TILDE, 126),
        ],
    )
    def test_integer_constants(self, const, value):
        assert const == value

    def test_bracketed_paste_start(self):
        assert BRACKETED_PASTE_START == "\033[200~"

    def test_bracketed_paste_end(self):
        assert BRACKETED_PASTE_END == "\033[201~"

    def test_bracketed_paste_enable(self):
        assert BRACKETED_PASTE_ENABLE == "\033[?2004h"

    def test_bracketed_paste_disable(self):
        assert BRACKETED_PASTE_DISABLE == "\033[?2004l"


# -- Extra: dialogs utility functions ----------------------------------------


class TestDialogsUtilities:
    """Helper functions in the dialogs module."""

    def test_strip_ansi_removes_codes(self):
        assert strip_ansi("\033[31mhello\033[0m") == "hello"

    def test_strip_ansi_noop_plain(self):
        assert strip_ansi("plain text") == "plain text"

    def test_visible_len_excludes_ansi(self):
        assert visible_len("\033[1m\033[31mbold red\033[0m") == len("bold red")

    def test_visible_len_plain(self):
        assert visible_len("hello") == VISIBLE_LEN_HELLO

    def test_base_dialog_defaults(self):
        d = BaseDialog()
        assert (d.title, d.width, d._last_render_lines) == ("Dialog", 80, 0)

    def test_base_dialog_custom(self):
        d = BaseDialog(title="Custom", width=100)
        assert (d.title, d.width) == ("Custom", 100)

    def test_base_dialog_render_not_implemented(self):
        with pytest.raises(NotImplementedError):
            BaseDialog().render()
