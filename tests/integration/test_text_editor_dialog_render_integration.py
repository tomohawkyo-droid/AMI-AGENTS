"""Integration tests for TextEditor and EditorDisplay (part 1)."""

import os
from unittest.mock import MagicMock

import pytest

from ami.cli_components.editor_display import EditorDisplay
from ami.cli_components.text_editor import TextEditor
from ami.core.config import _ConfigSingleton

# Constants for expected test values

EXPECTED_COL_HELLO_WORLD = 11
EXPECTED_LINE_MULTILINE_END = 2
EXPECTED_COL_AFTER_INSERT = 2
EXPECTED_COL_AFTER_JOIN = 3
EXPECTED_LINE_COUNT_AFTER_NEWLINE = 2
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


class TestTextEditorInit:
    def test_empty(self):
        e = TextEditor()
        assert e.lines == [""]
        assert e.in_paste_mode is False
        assert e.paste_buffer == ""
        assert e.ctrl_c_pressed_count == 0

    def test_single_line(self):
        e = TextEditor("hello world")
        assert e.lines == ["hello world"]
        assert e.cursor_manager.current_col == EXPECTED_COL_HELLO_WORLD

    def test_multiline(self):
        e = TextEditor("a\nb\nc")
        assert e.lines == ["a", "b", "c"]
        assert e.cursor_manager.current_line == EXPECTED_LINE_MULTILINE_END

    def test_empty_string(self):
        assert TextEditor("").lines == [""]


class TestTextEditorNavigation:
    @pytest.mark.parametrize(
        ("key", "il", "ic", "el"),
        [("UP", 1, 0, 0), ("DOWN", 0, 0, 1)],
    )
    def test_vertical(self, key, il, ic, el):
        e = TextEditor("aaa\nbbb")
        e.cursor_manager.current_line = il
        e.cursor_manager.current_col = ic
        e.handle_key_navigation(key)
        assert e.cursor_manager.current_line == el

    @pytest.mark.parametrize(
        ("key", "ic", "ec"),
        [("LEFT", 2, 1), ("RIGHT", 1, 2)],
    )
    def test_horizontal(self, key, ic, ec):
        e = TextEditor("abc")
        e.cursor_manager.current_col = ic
        e.handle_key_navigation(key)
        assert e.cursor_manager.current_col == ec

    @pytest.mark.parametrize(
        ("key", "ic", "ec"),
        [("CTRL_LEFT", 11, 6), ("CTRL_RIGHT", 0, 6)],
    )
    def test_ctrl_horizontal(self, key, ic, ec):
        e = TextEditor("hello world")
        e.cursor_manager.current_col = ic
        e.handle_key_navigation(key)
        assert e.cursor_manager.current_col == ec

    @pytest.mark.parametrize(
        ("key", "il", "el"),
        [("CTRL_UP", 2, 1), ("CTRL_DOWN", 0, 1)],
    )
    def test_ctrl_vertical(self, key, il, el):
        e = TextEditor("aaa\n\nbbb")
        e.cursor_manager.current_line = il
        e.cursor_manager.current_col = 0
        e.handle_key_navigation(key)
        assert e.cursor_manager.current_line == el


class TestTextEditorEnterKey:
    @pytest.mark.parametrize(
        ("col", "exp"),
        [
            (3, ["abc", "def"]),
            (0, ["", "abcdef"]),
            (6, ["abcdef", ""]),
        ],
    )
    def test_split(self, col, exp):
        e = TextEditor("abcdef")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = col
        e.process_enter_key()
        assert e.lines == exp
        assert e.cursor_manager.current_line == 1
        assert e.cursor_manager.current_col == 0

    def test_empty(self):
        e = TextEditor("")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 0
        e.process_enter_key()
        assert e.lines == ["", ""]


class TestTextEditorBackspaceKey:
    def test_delete_char(self):
        e = TextEditor("abc")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 2
        e.process_backspace_key()
        assert e.lines == ["ac"]
        assert e.cursor_manager.current_col == 1

    def test_join_lines(self):
        e = TextEditor("abc\ndef")
        e.cursor_manager.current_line = 1
        e.cursor_manager.current_col = 0
        e.process_backspace_key()
        assert e.lines == ["abcdef"]
        assert e.cursor_manager.current_col == EXPECTED_COL_AFTER_JOIN

    def test_at_start_noop(self):
        e = TextEditor("abc")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 0
        e.process_backspace_key()
        assert e.lines == ["abc"]
        assert e.cursor_manager.current_col == 0


class TestTextEditorHomeKey:
    @pytest.mark.parametrize("c", [3, 0])
    def test_to_zero(self, c):
        e = TextEditor("hello")
        e.cursor_manager.current_col = c
        e.process_home_key()
        assert e.cursor_manager.current_col == 0


class TestTextEditorDeleteWord:
    @pytest.mark.parametrize(
        ("text", "col", "exp", "ec"),
        [
            ("hello world", 11, "hello ", 6),
            ("hello", 0, "hello", 0),
            ("foo   bar", 9, "foo   ", 6),
            ("word", 4, "", 0),
        ],
    )
    def test_cases(self, text, col, exp, ec):
        e = TextEditor(text)
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = col
        e.process_delete_word()
        assert e.lines == [exp]
        assert e.cursor_manager.current_col == ec


class TestTextEditorInsertPastedContent:
    def test_empty_noop(self):
        e = TextEditor("abc")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 1
        e._insert_pasted_content("")
        assert e.lines == ["abc"]
        assert e.cursor_manager.current_col == 1

    def test_single_line(self):
        e = TextEditor("ac")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 1
        e._insert_pasted_content("b")
        assert e.lines == ["abc"]
        assert e.cursor_manager.current_col == EXPECTED_COL_AFTER_INSERT

    @pytest.mark.parametrize(
        ("content", "exp", "el", "ec"),
        [
            ("X\nY", ["aX", "Yc"], 1, 1),
            (
                "X\nMIDDLE\nY",
                ["aX", "MIDDLE", "Yc"],
                2,
                1,
            ),
        ],
    )
    def test_multi(self, content, exp, el, ec):
        e = TextEditor("ac")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 1
        e._insert_pasted_content(content)
        assert e.lines == exp
        assert e.cursor_manager.current_line == el
        assert e.cursor_manager.current_col == ec


class TestTextEditorHandleTextModification:
    @pytest.mark.parametrize(
        ("key", "text", "col", "exp"),
        [
            ("ENTER", "hello", 3, ["hel", "lo"]),
            ("BACKSPACE", "abc", 2, ["ac"]),
        ],
    )
    def test_dispatch(self, key, text, col, exp):
        e = TextEditor(text)
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = col
        e.handle_text_modification(key)
        assert e.lines == exp

    def test_home(self):
        e = TextEditor("abc")
        e.cursor_manager.current_col = 3
        e.handle_text_modification("HOME")
        assert e.cursor_manager.current_col == 0

    @pytest.mark.parametrize("key", ["DELETE_WORD", "BACKSPACE_WORD"])
    def test_word_keys(self, key):
        e = TextEditor("hello world")
        e.cursor_manager.current_line = 0
        e.cursor_manager.current_col = 11
        e.handle_text_modification(key)
        assert e.lines == ["hello "]

    def test_unknown_noop(self):
        e = TextEditor("abc")
        e.handle_text_modification("UNKNOWN")
        assert e.lines == ["abc"]
