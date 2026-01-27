"""Unit tests for TextEditor initialization, navigation, and text editing operations."""

from ami.cli_components.text_editor import TextEditor

EXPECTED_SINGLE_LINE_CURSOR_COL = 11
EXPECTED_INSERT_PASTE_CURSOR_COL = 16
EXPECTED_PASTE_LINE_COUNT = 3
EXPECTED_DELETE_WORD_CURSOR_COL = 6
EXPECTED_BACKSPACE_CURSOR_COL = 2
EXPECTED_JOIN_LINE_CURSOR_COL = 5
EXPECTED_RIGHT_CURSOR_COL = 1
EXPECTED_LEFT_CURSOR_COL = 2
EXPECTED_CHAR_INSERT_CURSOR_COL = 2
EXPECTED_CTRL_UP_START_LINE = 2


class TestTextEditorInit:
    """Tests for TextEditor initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization with empty text."""
        editor = TextEditor()

        assert editor.lines == [""]
        assert editor.in_paste_mode is False
        assert editor.paste_buffer == ""
        assert editor.ctrl_c_pressed_count == 0

    def test_initialization_with_single_line(self) -> None:
        """Test initialization with single line text."""
        editor = TextEditor("hello world")

        assert editor.lines == ["hello world"]
        assert editor.cursor_manager.current_line == 0
        # Cursor is initialized at end of text
        assert editor.cursor_manager.current_col == EXPECTED_SINGLE_LINE_CURSOR_COL

    def test_initialization_with_multiline(self) -> None:
        """Test initialization with multiline text."""
        editor = TextEditor("line1\nline2\nline3")

        assert editor.lines == ["line1", "line2", "line3"]


class TestKeyNavigation:
    """Tests for TextEditor.handle_key_navigation method."""

    def test_move_cursor_up(self) -> None:
        """Test moving cursor up."""
        editor = TextEditor("line1\nline2")
        editor.cursor_manager.current_line = 1

        editor.handle_key_navigation("UP")

        assert editor.cursor_manager.current_line == 0

    def test_move_cursor_down(self) -> None:
        """Test moving cursor down."""
        editor = TextEditor("line1\nline2")

        editor.handle_key_navigation("DOWN")

        assert editor.cursor_manager.current_line == 1

    def test_move_cursor_left(self) -> None:
        """Test moving cursor left."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 3

        editor.handle_key_navigation("LEFT")

        assert editor.cursor_manager.current_col == EXPECTED_LEFT_CURSOR_COL

    def test_move_cursor_right(self) -> None:
        """Test moving cursor right."""
        editor = TextEditor("hello")
        # Cursor starts at end (col 5), move left first
        editor.cursor_manager.current_col = 0

        editor.handle_key_navigation("RIGHT")

        assert editor.cursor_manager.current_col == EXPECTED_RIGHT_CURSOR_COL

    def test_ctrl_left_moves_to_previous_word(self) -> None:
        """Test Ctrl+Left moves to previous word."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 11

        editor.handle_key_navigation("CTRL_LEFT")

        # Should move to start of "world" or before
        assert editor.cursor_manager.current_col < EXPECTED_SINGLE_LINE_CURSOR_COL

    def test_ctrl_right_moves_to_next_word(self) -> None:
        """Test Ctrl+Right moves to next word."""
        editor = TextEditor("hello world")

        editor.handle_key_navigation("CTRL_RIGHT")

        # Should move past "hello"
        assert editor.cursor_manager.current_col > 0

    def test_ctrl_up_moves_to_previous_paragraph(self) -> None:
        """Test Ctrl+Up moves to previous paragraph."""
        editor = TextEditor("line1\n\nline3")
        editor.cursor_manager.current_line = 2

        editor.handle_key_navigation("CTRL_UP")

        assert editor.cursor_manager.current_line < EXPECTED_CTRL_UP_START_LINE

    def test_ctrl_down_moves_to_next_paragraph(self) -> None:
        """Test Ctrl+Down moves to next paragraph."""
        editor = TextEditor("line1\n\nline3")

        editor.handle_key_navigation("CTRL_DOWN")

        assert editor.cursor_manager.current_line > 0


class TestProcessEnterKey:
    """Tests for TextEditor.process_enter_key method."""

    def test_splits_line_at_cursor(self) -> None:
        """Test Enter splits line at cursor position."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 5

        editor.process_enter_key()

        assert editor.lines == ["hello", " world"]
        assert editor.cursor_manager.current_line == 1
        assert editor.cursor_manager.current_col == 0

    def test_splits_at_beginning(self) -> None:
        """Test Enter at beginning creates empty line above."""
        editor = TextEditor("hello")
        # Set cursor to beginning
        editor.cursor_manager.current_col = 0

        editor.process_enter_key()

        assert editor.lines == ["", "hello"]
        assert editor.cursor_manager.current_line == 1

    def test_splits_at_end(self) -> None:
        """Test Enter at end creates empty line below."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 5

        editor.process_enter_key()

        assert editor.lines == ["hello", ""]
        assert editor.cursor_manager.current_line == 1


class TestProcessBackspaceKey:
    """Tests for TextEditor.process_backspace_key method."""

    def test_deletes_character_before_cursor(self) -> None:
        """Test Backspace deletes character before cursor."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 3

        editor.process_backspace_key()

        assert editor.lines == ["helo"]
        assert editor.cursor_manager.current_col == EXPECTED_BACKSPACE_CURSOR_COL

    def test_joins_with_previous_line(self) -> None:
        """Test Backspace at start of line joins with previous."""
        editor = TextEditor("hello\nworld")
        editor.cursor_manager.current_line = 1
        editor.cursor_manager.current_col = 0

        editor.process_backspace_key()

        assert editor.lines == ["helloworld"]
        assert editor.cursor_manager.current_line == 0
        assert editor.cursor_manager.current_col == EXPECTED_JOIN_LINE_CURSOR_COL

    def test_does_nothing_at_start_of_first_line(self) -> None:
        """Test Backspace at very start does nothing."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 0

        editor.process_backspace_key()

        assert editor.lines == ["hello"]
        assert editor.cursor_manager.current_col == 0


class TestProcessHomeKey:
    """Tests for TextEditor.process_home_key method."""

    def test_moves_to_beginning_of_line(self) -> None:
        """Test Home moves cursor to beginning of line."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 7

        editor.process_home_key()

        assert editor.cursor_manager.current_col == 0


class TestProcessDeleteWord:
    """Tests for TextEditor.process_delete_word method."""

    def test_deletes_word_before_cursor(self) -> None:
        """Test deletes word before cursor."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 11

        editor.process_delete_word()

        assert editor.lines == ["hello "]
        assert editor.cursor_manager.current_col == EXPECTED_DELETE_WORD_CURSOR_COL

    def test_deletes_with_whitespace(self) -> None:
        """Test deletes word and preceding whitespace."""
        editor = TextEditor("hello   world")
        editor.cursor_manager.current_col = 8  # After spaces

        editor.process_delete_word()

        # Should delete "hello   "
        assert editor.cursor_manager.current_col == 0

    def test_does_nothing_at_start(self) -> None:
        """Test does nothing at start of line."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 0

        editor.process_delete_word()

        assert editor.lines == ["hello"]


class TestInsertPastedContent:
    """Tests for TextEditor._insert_pasted_content method."""

    def test_inserts_single_line(self) -> None:
        """Test inserts single line paste."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 6

        editor._insert_pasted_content("beautiful ")

        assert editor.lines == ["hello beautiful world"]
        assert editor.cursor_manager.current_col == EXPECTED_INSERT_PASTE_CURSOR_COL

    def test_inserts_multiline(self) -> None:
        """Test inserts multiline paste."""
        editor = TextEditor("start end")
        editor.cursor_manager.current_col = 6

        editor._insert_pasted_content("line1\nline2\nline3")

        assert len(editor.lines) == EXPECTED_PASTE_LINE_COUNT
        assert editor.lines[0] == "start line1"
        assert editor.lines[1] == "line2"
        assert editor.lines[2] == "line3end"

    def test_handles_empty_paste(self) -> None:
        """Test handles empty paste."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 2

        editor._insert_pasted_content("")

        assert editor.lines == ["hello"]


class TestHandleTextModification:
    """Tests for TextEditor.handle_text_modification method."""

    def test_handles_enter(self) -> None:
        """Test handles ENTER key."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 2

        editor.handle_text_modification("ENTER")

        assert editor.lines == ["he", "llo"]

    def test_handles_backspace(self) -> None:
        """Test handles BACKSPACE key."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 5

        editor.handle_text_modification("BACKSPACE")

        assert editor.lines == ["hell"]

    def test_handles_home(self) -> None:
        """Test handles HOME key."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 5

        editor.handle_text_modification("HOME")

        assert editor.cursor_manager.current_col == 0

    def test_handles_delete_word(self) -> None:
        """Test handles DELETE_WORD key."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 11

        editor.handle_text_modification("DELETE_WORD")

        assert editor.lines == ["hello "]

    def test_handles_backspace_word(self) -> None:
        """Test handles BACKSPACE_WORD key."""
        editor = TextEditor("hello world")
        editor.cursor_manager.current_col = 11

        editor.handle_text_modification("BACKSPACE_WORD")

        assert editor.lines == ["hello "]
