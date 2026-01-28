"""Integration tests for TUI primitives and selection dialog.

Exercises: cli_components/tui.py, cli_components/selection_dialog.py,
cli_components/text_input_utils.py (Colors, constants, display_final_output),
cli/timer_utils.py
"""

import pytest

from ami.cli.timer_utils import wrap_text_in_box
from ami.cli_components.selection_dialog import (
    DEFAULT_DIALOG_WIDTH,
    DEFAULT_MAX_HEIGHT,
    INDENT_CHILD,
    TRUNCATION_SUFFIX,
    SelectionDialog,
    SelectionDialogConfig,
)
from ami.cli_components.text_input_utils import (
    BACKSPACE,
    BRACKETED_PASTE_DISABLE,
    BRACKETED_PASTE_ENABLE,
    BRACKETED_PASTE_END,
    BRACKETED_PASTE_START,
    CTRL_A,
    CTRL_C,
    CTRL_S,
    CTRL_U,
    CTRL_W,
    DOWN_ARROW,
    ENTER_CR,
    ENTER_LF,
    ESC,
    LEFT_ARROW,
    RIGHT_ARROW,
    TAB,
    UP_ARROW,
    Colors,
    display_final_output,
)
from ami.cli_components.tui import TUI, _format_box_row, _visible_len
from ami.core.config import _ConfigSingleton

# --- Named constants for magic numbers used in assertions ---
EXPECTED_HELLO_LEN = 5
EXPECTED_RED_ANSI_LEN = 3
EXPECTED_EMPTY_LEN = 0
EXPECTED_WRAP_MAX_LINE_LEN = 21
EXPECTED_MIN_BOX_LINES = 4
EXPECTED_DIALOG_ITEM_COUNT_3 = 3
EXPECTED_DIALOG_ITEM_COUNT_2 = 2
EXPECTED_MULTI_SELECT_NONE = 0

EXPECTED_ESC_CODE = 27
EXPECTED_CTRL_C_CODE = 3
EXPECTED_CTRL_S_CODE = 19
EXPECTED_BACKSPACE_CODE = 127
EXPECTED_ENTER_CR_CODE = 13
EXPECTED_ENTER_LF_CODE = 10
EXPECTED_TAB_CODE = 9
EXPECTED_CTRL_U_CODE = 21
EXPECTED_CTRL_A_CODE = 1
EXPECTED_CTRL_W_CODE = 23
EXPECTED_UP_ARROW_CODE = 65
EXPECTED_DOWN_ARROW_CODE = 66
EXPECTED_RIGHT_ARROW_CODE = 67
EXPECTED_LEFT_ARROW_CODE = 68

EXPECTED_DEFAULT_DIALOG_WIDTH = 80
EXPECTED_DEFAULT_MAX_HEIGHT = 10


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# TUI: _visible_len
# ---------------------------------------------------------------------------


class TestTUIVisibleLen:
    """Test _visible_len utility."""

    def test_plain_text(self):
        assert _visible_len("hello") == EXPECTED_HELLO_LEN

    def test_with_ansi(self):
        assert _visible_len("\033[31mred\033[0m") == EXPECTED_RED_ANSI_LEN

    def test_empty(self):
        assert _visible_len("") == EXPECTED_EMPTY_LEN


# ---------------------------------------------------------------------------
# TUI: _format_box_row
# ---------------------------------------------------------------------------


class TestFormatBoxRow:
    """Test _format_box_row function."""

    def test_centered(self):
        row = _format_box_row("hi", 20, "\033[36m", "\033[0m", center=True)
        assert "hi" in row
        assert "\u2502" in row

    def test_left_aligned(self):
        row = _format_box_row("test", 20, "\033[36m", "\033[0m", center=False)
        assert "test" in row
        assert "\u2502" in row


# ---------------------------------------------------------------------------
# TUI: wrap_text
# ---------------------------------------------------------------------------


class TestTUIWrapText:
    """Test TUI.wrap_text word wrapping."""

    def test_short_text(self):
        lines = TUI.wrap_text("hello world", 80)
        assert lines == ["hello world"]

    def test_wraps_long_text(self):
        text = "a " * 50  # 100 chars
        lines = TUI.wrap_text(text, 20)
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= EXPECTED_WRAP_MAX_LINE_LEN

    def test_empty_text(self):
        lines = TUI.wrap_text("", 80)
        assert lines == []

    def test_single_long_word(self):
        lines = TUI.wrap_text("superlongword", 5)
        assert lines == ["superlongword"]  # Can't break mid-word


# ---------------------------------------------------------------------------
# TUI: draw_box
# ---------------------------------------------------------------------------


class TestTUIDrawBox:
    """Test TUI.draw_box output."""

    def test_basic_box(self, capsys):
        lines_printed = TUI.draw_box(content=["hello", "world"])
        out = capsys.readouterr().out
        assert "hello" in out
        assert "world" in out
        assert "\u250c" in out
        assert "\u2514" in out
        assert lines_printed >= EXPECTED_MIN_BOX_LINES

    def test_box_with_title(self, capsys):
        TUI.draw_box(content=["test"], title="My Title")
        out = capsys.readouterr().out
        assert "My Title" in out

    def test_box_with_footer(self, capsys):
        TUI.draw_box(content=["test"], footer="Press Enter")
        out = capsys.readouterr().out
        assert "Press Enter" in out


# ---------------------------------------------------------------------------
# Colors constants
# ---------------------------------------------------------------------------


class TestColorsConstants:
    """Test Colors class has expected attributes."""

    def test_basic_colors(self):
        assert Colors.RESET is not None
        assert Colors.BOLD is not None
        assert Colors.RED is not None
        assert Colors.GREEN is not None
        assert Colors.CYAN is not None
        assert Colors.YELLOW is not None

    def test_background_colors(self):
        assert Colors.BG_RED is not None
        assert Colors.BG_GREEN is not None

    def test_reverse(self):
        assert Colors.REVERSE is not None


# ---------------------------------------------------------------------------
# Text input constants
# ---------------------------------------------------------------------------


class TestTextInputConstants:
    """Test text_input_utils constants."""

    def test_key_codes(self):
        assert ESC == EXPECTED_ESC_CODE
        assert CTRL_C == EXPECTED_CTRL_C_CODE
        assert CTRL_S == EXPECTED_CTRL_S_CODE
        assert BACKSPACE == EXPECTED_BACKSPACE_CODE
        assert ENTER_CR == EXPECTED_ENTER_CR_CODE
        assert ENTER_LF == EXPECTED_ENTER_LF_CODE
        assert TAB == EXPECTED_TAB_CODE
        assert CTRL_U == EXPECTED_CTRL_U_CODE
        assert CTRL_A == EXPECTED_CTRL_A_CODE
        assert CTRL_W == EXPECTED_CTRL_W_CODE

    def test_arrow_codes(self):
        assert UP_ARROW == EXPECTED_UP_ARROW_CODE
        assert DOWN_ARROW == EXPECTED_DOWN_ARROW_CODE
        assert RIGHT_ARROW == EXPECTED_RIGHT_ARROW_CODE
        assert LEFT_ARROW == EXPECTED_LEFT_ARROW_CODE

    def test_paste_constants(self):
        assert "200" in BRACKETED_PASTE_START
        assert "201" in BRACKETED_PASTE_END
        assert "2004h" in BRACKETED_PASTE_ENABLE
        assert "2004l" in BRACKETED_PASTE_DISABLE


# ---------------------------------------------------------------------------
# display_final_output
# ---------------------------------------------------------------------------


class TestDisplayFinalOutput:
    """Test display_final_output function."""

    def test_with_lines(self, capsys):
        display_final_output(["line1", "line2"], "Sent to agent")
        out = capsys.readouterr().out
        assert "line1" in out
        assert "line2" in out
        assert "\u250c" in out
        assert "\u2514" in out

    def test_empty_lines(self, capsys):
        display_final_output([], "discarded")
        out = capsys.readouterr().out
        assert "\u250c" in out
        assert "discarded" in out

    def test_sent_message(self, capsys):
        display_final_output(["hi"], "Sent")
        out = capsys.readouterr().out
        assert "\U0001f4ac" in out  # Sent messages use chat emoji


# ---------------------------------------------------------------------------
# SelectionDialogConfig
# ---------------------------------------------------------------------------


class TestSelectionDialogConfig:
    """Test SelectionDialogConfig construction."""

    def test_defaults(self):
        cfg = SelectionDialogConfig()
        assert cfg.title == "Select"
        assert cfg.width == EXPECTED_DEFAULT_DIALOG_WIDTH
        assert cfg.multi is False
        assert cfg.max_height == EXPECTED_DEFAULT_MAX_HEIGHT
        assert cfg.preselected == set()

    def test_custom(self):
        cfg = SelectionDialogConfig(
            title="Pick one",
            width=60,
            multi=True,
            max_height=20,
            preselected={"item1"},
        )
        assert cfg.title == "Pick one"
        assert cfg.multi is True
        assert cfg.preselected == {"item1"}


# ---------------------------------------------------------------------------
# SelectionDialog construction and internal methods
# ---------------------------------------------------------------------------


class TestSelectionDialogConstruction:
    """Test SelectionDialog construction without running the event loop."""

    def test_string_items(self):
        dialog = SelectionDialog(["a", "b", "c"])
        assert len(dialog.items) == EXPECTED_DIALOG_ITEM_COUNT_3
        assert dialog.cursor == 0

    def test_dict_items(self):
        items = [
            {"label": "Option A", "value": "a", "is_header": False},
            {"label": "Option B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items)
        assert len(dialog.items) == EXPECTED_DIALOG_ITEM_COUNT_2

    def test_header_items(self):
        items = [
            {"id": "_header_group1", "label": "Group 1", "is_header": True},
            {"label": "Item 1", "value": "1", "is_header": False},
            {"label": "Item 2", "value": "2", "is_header": False},
        ]
        dialog = SelectionDialog(items)
        assert len(dialog.group_ranges) == 1

    def test_handle_key_down(self):
        dialog = SelectionDialog(["a", "b", "c"])
        dialog._handle_key("DOWN")
        assert dialog.cursor == 1

    def test_handle_key_up(self):
        dialog = SelectionDialog(["a", "b", "c"])
        dialog.cursor = 2
        dialog._handle_key("UP")
        assert dialog.cursor == 1

    def test_handle_key_enter(self):
        dialog = SelectionDialog(["a", "b", "c"])
        dialog.cursor = 1
        should_continue, result = dialog._handle_key("ENTER")
        assert should_continue is False
        assert result is not None

    def test_handle_key_escape(self):
        dialog = SelectionDialog(["a", "b"])
        should_continue, result = dialog._handle_key("ESC")
        assert should_continue is False
        assert result is None

    def test_multi_select_toggle(self):
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["a", "b", "c"], config)
        dialog._handle_key(" ")  # toggle first item
        assert 0 in dialog.selected

    def test_multi_select_all(self):
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["a", "b", "c"], config)
        dialog._handle_key("a")  # select all
        assert len(dialog.selected) == EXPECTED_DIALOG_ITEM_COUNT_3

    def test_multi_select_none(self):
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["a", "b", "c"], config)
        dialog._handle_key("a")  # select all
        dialog._handle_key("n")  # select none
        assert len(dialog.selected) == EXPECTED_MULTI_SELECT_NONE

    def test_get_selection_single(self):
        dialog = SelectionDialog(["a", "b"])
        dialog.cursor = 1
        result = dialog._get_selection()
        assert result["label"] == "b"

    def test_get_selection_multi(self):
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["a", "b", "c"], config)
        dialog.selected = {0, 2}
        result = dialog._get_selection()
        assert len(result) == EXPECTED_DIALOG_ITEM_COUNT_2

    def test_truncate_text(self):
        dialog = SelectionDialog(["a"])
        assert dialog._truncate_text("hello", 10) == "hello"
        assert dialog._truncate_text("hello world long", 10) == "hello w..."

    def test_scroll_down(self):
        config = SelectionDialogConfig(max_height=2)
        dialog = SelectionDialog(["a", "b", "c", "d"], config)
        dialog.cursor = 2
        dialog._scroll_down()
        assert dialog.scroll_offset == 1

    def test_build_footer_text(self):
        dialog = SelectionDialog(["a"])
        footer = dialog._build_footer_text()
        assert "navigate" in footer
        assert "Enter" in footer


# ---------------------------------------------------------------------------
# SelectionDialog constants
# ---------------------------------------------------------------------------


class TestSelectionDialogConstants:
    """Test selection_dialog constants."""

    def test_constants(self):
        assert DEFAULT_DIALOG_WIDTH == EXPECTED_DEFAULT_DIALOG_WIDTH
        assert DEFAULT_MAX_HEIGHT == EXPECTED_DEFAULT_MAX_HEIGHT
        assert TRUNCATION_SUFFIX == "..."
        assert INDENT_CHILD == "   "


# ---------------------------------------------------------------------------
# timer_utils
# ---------------------------------------------------------------------------


class TestTimerUtils:
    """Test timer utilities."""

    def test_wrap_text_in_box(self):
        result = wrap_text_in_box("hello world")
        assert "hello world" in result
        assert "\u250c" in result
        assert "\u2514" in result

    def test_wrap_text_in_box_multiline(self):
        result = wrap_text_in_box("line1\nline2")
        assert "line1" in result
        assert "line2" in result
