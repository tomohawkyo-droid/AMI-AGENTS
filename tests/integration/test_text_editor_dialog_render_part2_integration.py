"""Integration tests for editor and dialog render methods (part 2)."""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from ami.cli_components.dialogs import AlertDialog, ConfirmationDialog
from ami.cli_components.editor_display import EditorDisplay
from ami.cli_components.text_editor import TextEditor
from ami.cli_components.text_input_utils import Colors
from ami.cli_components.tui import TUI
from ami.core.config import _ConfigSingleton

# Named constants for magic numbers used in assertions
EXPECTED_RENDER_LINES_7 = 7
EXPECTED_CONTENT_WIDTH = 76
EXPECTED_CUSTOM_WIDTH = 60
EXPECTED_LINE_COUNT_AFTER_NEWLINE = 2
EXPECTED_COL_AFTER_INSERT = 2
EXPECTED_EDITOR_LINE_COUNT_3_LINES = 6
EXPECTED_EDITOR_LINE_COUNT_2_LINES_HELP = 6
EXPECTED_CLEAR_LINE_COUNT = 3


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    _ConfigSingleton.instance = None
    os.environ["AMI_TEST_MODE"] = "1"
    yield
    _ConfigSingleton.instance = None
    os.environ.pop("AMI_TEST_MODE", None)


def _md():
    d = MagicMock(spec=EditorDisplay)
    d.show_help = False
    return d


class TestTextEditorProcessKey:
    def test_paste_mode(self):
        e = TextEditor("abc")
        e.in_paste_mode = True
        assert e._process_key("x", _md()) is False
        assert e.paste_buffer == "x"

    def test_normal_mode(self):
        e = TextEditor("abc")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 0
        assert e._process_key("x", _md()) is False
        assert e.lines[0].startswith("x")


class TestTextEditorPasteModeKey:
    def test_accumulate(self):
        e = TextEditor("")
        e.in_paste_mode = True
        d = _md()
        e._process_paste_mode_key("a", d)
        e._process_paste_mode_key("b", d)
        assert e.paste_buffer == "ab"

    def test_enter_newline(self):
        e = TextEditor("")
        e.in_paste_mode = True
        e._process_paste_mode_key("ENTER", _md())
        assert e.paste_buffer == "\n"

    @pytest.mark.parametrize("end", ["PASTE_END", "PASTE_END_ALT"])
    def test_end_inserts(self, end):
        e = TextEditor("XY")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 1
        e.in_paste_mode = True
        e.paste_buffer = "Z"
        result = e._process_paste_mode_key(end, _md())
        assert result is False
        assert not e.in_paste_mode
        assert e.paste_buffer == ""
        assert e.lines == ["XZY"]

    def test_returns_false(self):
        e = TextEditor("")
        e.in_paste_mode = True
        d = _md()
        assert e._process_paste_mode_key("x", d) is False
        result = e._process_paste_mode_key("PASTE_END", d)
        assert result is False


class TestTextEditorNormalModeKey:
    @pytest.mark.parametrize("key", ["PASTE_START", "PASTE_START_ALT"])
    def test_paste_start(self, key):
        e = TextEditor("")
        assert e._process_normal_mode_key(key, _md()) is False
        assert e.in_paste_mode is True

    def test_navigation(self):
        e = TextEditor("aaa\nbbb")
        e.cursor_manager.current_line = 1
        e.cursor_manager.current_col = 0
        assert e._process_normal_mode_key("UP", _md()) is False
        assert e.cursor_manager.current_line == 0

    def test_char_input(self):
        e = TextEditor("")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 0
        assert e._process_normal_mode_key("z", _md()) is False
        assert e.lines[0] == "z"


class TestTextEditorNavigationCommands:
    @pytest.mark.parametrize("key", ["ENTER", "SUBMIT"])
    def test_exit(self, key):
        result = TextEditor("h")._handle_navigation_command_keys(key, _md())
        assert result is True

    @pytest.mark.parametrize("key", ["ALT_ENTER"])
    def test_newline(self, key):
        e = TextEditor("hello")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 5
        result = e._handle_navigation_command_keys(key, _md())
        assert result is False
        assert len(e.lines) == EXPECTED_LINE_COUNT_AFTER_NEWLINE

    def test_f1_toggle(self):
        e, d = TextEditor(""), _md()
        d.show_help = False
        e._handle_navigation_command_keys("F1", d)
        assert d.show_help is True
        e._handle_navigation_command_keys("F1", d)
        assert d.show_help is False

    def test_nav_redraw(self):
        e = TextEditor("abc\ndef")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 0
        d = _md()
        e._handle_navigation_command_keys("DOWN", d)
        d.display_editor.assert_called()

    def test_text_mod(self):
        e = TextEditor("abc")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 2
        result = e._handle_navigation_command_keys("BACKSPACE", _md())
        assert result is False
        assert e.lines == ["ac"]


class TestTextEditorCharacterInput:
    def test_single(self):
        e = TextEditor("ac")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 1
        d = _md()
        assert e._handle_character_input("b", d) is False
        assert e.lines == ["abc"]
        assert e.cursor_manager.current_col == EXPECTED_COL_AFTER_INSERT
        d.display_editor.assert_called_once()

    def test_multi_ignored(self):
        e = TextEditor("abc")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 0
        d = _md()
        assert e._handle_character_input("xy", d) is False
        assert e.lines == ["abc"]
        d.display_editor.assert_not_called()


class TestEditorDisplayInit:
    def test_defaults(self):
        d = EditorDisplay()
        assert d.editor_line_count == 0
        assert d.previous_display_lines == 0
        assert d.show_help is False


class TestEditorDisplayEditor:
    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_first_render(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.display_editor(["hello"], 0, 0)
        assert "ello" in b.getvalue()
        assert d.previous_display_lines > 0

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_subsequent_clears(self, ma):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.display_editor(["hello"], 0, 0)
            d.display_editor(["world"], 0, 0)
        ma.move_up.assert_called()
        ma.clear_line.assert_called()

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_help_header(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.show_help = True
            d.display_editor(["t"], 0, 0)
        assert "F1" in b.getvalue()

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_status_override(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            EditorDisplay().display_editor(["t"], 0, 0, status_override="CUS")
        assert "CUS" in b.getvalue()

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_count_no_help(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.display_editor(["a", "b", "c"], 0, 0)
        assert d.editor_line_count == EXPECTED_EDITOR_LINE_COUNT_3_LINES

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_count_with_help(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.show_help = True
            d.display_editor(["a", "b"], 0, 0)
        assert d.editor_line_count == EXPECTED_EDITOR_LINE_COUNT_2_LINES_HELP

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_cursor_in_text(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            EditorDisplay().display_editor(["abc"], 0, 1)
        assert Colors.REVERSE in b.getvalue()

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_cursor_beyond(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            EditorDisplay().display_editor(["abc"], 0, 3)
        assert Colors.REVERSE in b.getvalue()


class TestEditorDisplayClear:
    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_with_lines(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.previous_display_lines = 5
            d.clear()
        assert "\033[5A" in b.getvalue()

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_zero_noop(self, ansi_mock):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.previous_display_lines = 0
            d.clear()
        assert b.getvalue() == ""

    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_calls_clear_line(self, ma):
        b = io.StringIO()
        with patch.object(sys, "stdout", b):
            d = EditorDisplay()
            d.previous_display_lines = EXPECTED_CLEAR_LINE_COUNT
            d.clear()
        assert ma.clear_line.call_count == EXPECTED_CLEAR_LINE_COUNT


class TestEditorDisplayKeyboardInterrupt:
    @patch("ami.cli_components.editor_display.display_final_output")
    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_calls_final(self, ansi_mock, mf):
        d = EditorDisplay()
        d.previous_display_lines = 3
        d.handle_keyboard_interrupt(["some", "text"])
        mf.assert_called_once()
        assert mf.call_args[0][0] == ["some", "text"]
        assert "discarded" in mf.call_args[0][1].lower()

    @patch("ami.cli_components.editor_display.display_final_output")
    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_clears_first(self, ma, final_mock):
        d = EditorDisplay()
        d.previous_display_lines = 4
        d.handle_keyboard_interrupt(["x"])
        ma.move_up.assert_called()

    @patch("ami.cli_components.editor_display.display_final_output")
    @patch("ami.cli_components.editor_display.AnsiTerminal")
    def test_no_clear_zero(self, ma, mf):
        d = EditorDisplay()
        d.previous_display_lines = 0
        d.handle_keyboard_interrupt(["x"])
        ma.move_up.assert_not_called()
        mf.assert_called_once()


class TestAlertDialogRender:
    @patch.object(TUI, "draw_box", return_value=7)
    @patch.object(TUI, "wrap_text", return_value=["Hello"])
    def test_calls(self, mw, md):
        AlertDialog("Hello", title="T", width=80)._render()
        mw.assert_called_once()
        md.assert_called_once()

    @patch.object(TUI, "draw_box", return_value=7)
    @patch.object(TUI, "wrap_text", return_value=["Hello"])
    def test_lines(self, mock_wrap, mock_draw):
        dlg = AlertDialog("Hello")
        dlg._render()
        assert mock_wrap is not None
        assert mock_draw is not None
        assert dlg._last_render_lines == EXPECTED_RENDER_LINES_7

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["L1", "L2"])
    def test_ok_button(self, mock_wrap, md):
        assert mock_wrap is not None
        AlertDialog("msg")._render()
        assert "OK" in md.call_args[1]["content"][-1]

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["msg"])
    def test_blank(self, mock_wrap, md):
        assert mock_wrap is not None
        AlertDialog("msg")._render()
        assert "" in md.call_args[1]["content"]

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["c"])
    def test_center(self, mock_wrap, md):
        assert mock_wrap is not None
        AlertDialog("c", width=80)._render()
        assert len(md.call_args[1]["content"][0]) == EXPECTED_CONTENT_WIDTH

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_title(self, mock_wrap, md):
        assert mock_wrap is not None
        AlertDialog("m", title="T")._render()
        assert md.call_args[1]["title"] == "T"

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_footer(self, mock_wrap, md):
        assert mock_wrap is not None
        AlertDialog("m")._render()
        assert "Enter" in md.call_args[1]["footer"]

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_width(self, mock_wrap, md):
        assert mock_wrap is not None
        AlertDialog("m", width=EXPECTED_CUSTOM_WIDTH)._render()
        s = md.call_args[1]["style"]
        assert s.width == EXPECTED_CUSTOM_WIDTH
        assert s.center_content is False


class TestConfirmDialogRender:
    @patch.object(TUI, "draw_box", return_value=7)
    @patch.object(TUI, "wrap_text", return_value=["Q"])
    def test_calls(self, mw, md):
        ConfirmationDialog("Q")._render()
        mw.assert_called_once()
        md.assert_called_once()

    @patch.object(TUI, "draw_box", return_value=7)
    @patch.object(TUI, "wrap_text", return_value=["Q"])
    def test_lines(self, mock_wrap, mock_draw):
        dlg = ConfirmationDialog("Q")
        dlg._render()
        assert mock_wrap is not None
        assert mock_draw is not None
        assert dlg._last_render_lines == EXPECTED_RENDER_LINES_7

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["S"])
    def test_yes_no(self, mock_wrap, md):
        assert mock_wrap is not None
        ConfirmationDialog("S")._render()
        bl = md.call_args[1]["content"][-1]
        assert "Y" in bl
        assert "N" in bl
        assert "es" in bl

    @pytest.mark.parametrize("sy", [True, False])
    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_highlight(self, mock_wrap, md, sy):
        assert mock_wrap is not None
        dlg = ConfirmationDialog("m")
        dlg.selected_yes = sy
        dlg._render()
        assert Colors.REVERSE in md.call_args[1]["content"][-1]

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_blank(self, mock_wrap, md):
        assert mock_wrap is not None
        ConfirmationDialog("m")._render()
        assert "" in md.call_args[1]["content"]

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_title(self, mock_wrap, md):
        assert mock_wrap is not None
        ConfirmationDialog("m", title="C?")._render()
        assert md.call_args[1]["title"] == "C?"

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_footer(self, mock_wrap, md):
        assert mock_wrap is not None
        ConfirmationDialog("m")._render()
        assert "y/n" in md.call_args[1]["footer"]

    def test_default_yes(self):
        assert ConfirmationDialog("m").selected_yes is True

    @patch.object(TUI, "draw_box", return_value=5)
    @patch.object(TUI, "wrap_text", return_value=["m"])
    def test_width(self, mock_wrap, md):
        assert mock_wrap is not None
        ConfirmationDialog("m", width=EXPECTED_CUSTOM_WIDTH)._render()
        assert md.call_args[1]["style"].width == EXPECTED_CUSTOM_WIDTH
