"""Unit tests for ami/cli_components/cursor_manager.py."""

from ami.cli_components.cursor_manager import CursorManager

EXPECTED_COL_END_OF_HELLO = 5
EXPECTED_LINE_LAST_OF_THREE = 2
EXPECTED_COL_END_OF_THIRD = 5
EXPECTED_COL_PRESERVED = 3
EXPECTED_COL_UNCHANGED = 2
EXPECTED_COL_ADJUSTED_TO_SHORT_LINE = 2
EXPECTED_COL_AFTER_MOVE_DOWN = 3
EXPECTED_COL_AFTER_MOVE_DOWN_UNCHANGED = 2
EXPECTED_COL_AFTER_MOVE_DOWN_ADJUSTED = 2
EXPECTED_COL_AFTER_LEFT = 2
EXPECTED_COL_END_OF_FIRST = 5
EXPECTED_COL_AFTER_RIGHT = 3
EXPECTED_COL_AT_END_OF_LINE = 5
EXPECTED_COL_PREVIOUS_WORD = 6
EXPECTED_COL_NEXT_WORD = 6
EXPECTED_COL_AT_END = 5
EXPECTED_LINE_NEXT_PARAGRAPH = 2
EXPECTED_COL_END_OF_SECOND = 6


class TestCursorManagerInit:
    """Tests for CursorManager initialization."""

    def test_init_with_empty_lines(self):
        """Test initialization with empty lines list."""
        cursor = CursorManager([])

        assert cursor.current_line == 0
        assert cursor.current_col == 0

    def test_init_with_single_line(self):
        """Test initialization with single line."""
        cursor = CursorManager(["hello"])

        assert cursor.current_line == 0
        assert cursor.current_col == EXPECTED_COL_END_OF_HELLO  # At end of line

    def test_init_with_multiple_lines(self):
        """Test initialization with multiple lines."""
        cursor = CursorManager(["first", "second", "third"])

        # Should be at end of last line
        assert cursor.current_line == EXPECTED_LINE_LAST_OF_THREE
        assert cursor.current_col == EXPECTED_COL_END_OF_THIRD  # len("third")

    def test_init_with_empty_last_line(self):
        """Test initialization when last line is empty."""
        cursor = CursorManager(["hello", ""])

        assert cursor.current_line == 1
        assert cursor.current_col == 0


class TestMoveCursorUp:
    """Tests for move_cursor_up method."""

    def test_move_up_from_second_line(self):
        """Test moving up from second line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 1
        cursor.current_col = 3

        cursor.move_cursor_up()

        assert cursor.current_line == 0
        assert cursor.current_col == EXPECTED_COL_PRESERVED  # Preserved

    def test_move_up_from_first_line(self):
        """Test moving up from first line stays at first line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 0
        cursor.current_col = 2

        cursor.move_cursor_up()

        assert cursor.current_line == 0
        assert cursor.current_col == EXPECTED_COL_UNCHANGED

    def test_move_up_adjusts_col_for_shorter_line(self):
        """Test column is adjusted when moving to shorter line."""
        cursor = CursorManager(["hi", "hello world"])
        cursor.current_line = 1
        cursor.current_col = 10

        cursor.move_cursor_up()

        assert cursor.current_line == 0
        # Adjusted to line length
        assert cursor.current_col == EXPECTED_COL_ADJUSTED_TO_SHORT_LINE


class TestMoveCursorDown:
    """Tests for move_cursor_down method."""

    def test_move_down_from_first_line(self):
        """Test moving down from first line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 0
        cursor.current_col = 3

        cursor.move_cursor_down()

        assert cursor.current_line == 1
        assert cursor.current_col == EXPECTED_COL_AFTER_MOVE_DOWN

    def test_move_down_from_last_line(self):
        """Test moving down from last line stays at last line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 1
        cursor.current_col = 2

        cursor.move_cursor_down()

        assert cursor.current_line == 1
        assert cursor.current_col == EXPECTED_COL_AFTER_MOVE_DOWN_UNCHANGED

    def test_move_down_adjusts_col_for_shorter_line(self):
        """Test column is adjusted when moving to shorter line."""
        cursor = CursorManager(["hello world", "hi"])
        cursor.current_line = 0
        cursor.current_col = 10

        cursor.move_cursor_down()

        assert cursor.current_line == 1
        assert cursor.current_col == EXPECTED_COL_AFTER_MOVE_DOWN_ADJUSTED


class TestMoveCursorLeft:
    """Tests for move_cursor_left method."""

    def test_move_left_within_line(self):
        """Test moving left within a line."""
        cursor = CursorManager(["hello"])
        cursor.current_line = 0
        cursor.current_col = 3

        cursor.move_cursor_left()

        assert cursor.current_col == EXPECTED_COL_AFTER_LEFT

    def test_move_left_at_start_of_line(self):
        """Test moving left at start of line wraps to previous line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 1
        cursor.current_col = 0

        cursor.move_cursor_left()

        assert cursor.current_line == 0
        assert cursor.current_col == EXPECTED_COL_END_OF_FIRST  # End of "first"

    def test_move_left_at_start_of_first_line(self):
        """Test moving left at start of first line does nothing."""
        cursor = CursorManager(["hello"])
        cursor.current_line = 0
        cursor.current_col = 0

        cursor.move_cursor_left()

        assert cursor.current_line == 0
        assert cursor.current_col == 0


class TestMoveCursorRight:
    """Tests for move_cursor_right method."""

    def test_move_right_within_line(self):
        """Test moving right within a line."""
        cursor = CursorManager(["hello"])
        cursor.current_line = 0
        cursor.current_col = 2

        cursor.move_cursor_right()

        assert cursor.current_col == EXPECTED_COL_AFTER_RIGHT

    def test_move_right_at_end_of_line(self):
        """Test moving right at end of line wraps to next line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 0
        cursor.current_col = 5

        cursor.move_cursor_right()

        assert cursor.current_line == 1
        assert cursor.current_col == 0

    def test_move_right_at_end_of_last_line(self):
        """Test moving right at end of last line does nothing."""
        cursor = CursorManager(["hello"])
        cursor.current_line = 0
        cursor.current_col = 5

        cursor.move_cursor_right()

        assert cursor.current_line == 0
        assert cursor.current_col == EXPECTED_COL_AT_END_OF_LINE


class TestMoveToPreviousWord:
    """Tests for move_to_previous_word method."""

    def test_move_to_previous_word(self):
        """Test moving to previous word."""
        cursor = CursorManager(["hello world"])
        cursor.current_col = 11

        cursor.move_to_previous_word()

        assert cursor.current_col == EXPECTED_COL_PREVIOUS_WORD

    def test_move_to_previous_word_skips_spaces(self):
        """Test moving skips trailing spaces."""
        cursor = CursorManager(["hello   world"])
        cursor.current_col = 8

        cursor.move_to_previous_word()

        assert cursor.current_col == 0

    def test_move_at_start_of_line(self):
        """Test moving at start of line does nothing."""
        cursor = CursorManager(["hello"])
        cursor.current_col = 0

        cursor.move_to_previous_word()

        assert cursor.current_col == 0


class TestMoveToNextWord:
    """Tests for move_to_next_word method."""

    def test_move_to_next_word(self):
        """Test moving to next word."""
        cursor = CursorManager(["hello world"])
        cursor.current_col = 0

        cursor.move_to_next_word()

        assert cursor.current_col == EXPECTED_COL_NEXT_WORD

    def test_move_to_next_word_from_middle(self):
        """Test moving from middle of word."""
        cursor = CursorManager(["hello world"])
        cursor.current_col = 2

        cursor.move_to_next_word()

        assert cursor.current_col == EXPECTED_COL_NEXT_WORD

    def test_move_at_end_of_line(self):
        """Test moving at end of line."""
        cursor = CursorManager(["hello"])
        cursor.current_col = 5

        cursor.move_to_next_word()

        assert cursor.current_col == EXPECTED_COL_AT_END


class TestMoveToPreviousParagraph:
    """Tests for move_to_previous_paragraph method."""

    def test_move_to_previous_paragraph(self):
        """Test moving to previous paragraph."""
        cursor = CursorManager(["first", "", "second", "third"])
        cursor.current_line = 3

        cursor.move_to_previous_paragraph()

        assert cursor.current_line == 1
        assert cursor.current_col == 0

    def test_move_when_no_previous_paragraph(self):
        """Test moving when no previous paragraph goes to first line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 1

        cursor.move_to_previous_paragraph()

        assert cursor.current_line == 0
        assert cursor.current_col == 0


class TestMoveToNextParagraph:
    """Tests for move_to_next_paragraph method."""

    def test_move_to_next_paragraph(self):
        """Test moving to next paragraph."""
        cursor = CursorManager(["first", "second", "", "third"])
        cursor.current_line = 0

        cursor.move_to_next_paragraph()

        assert cursor.current_line == EXPECTED_LINE_NEXT_PARAGRAPH
        assert cursor.current_col == 0

    def test_move_when_no_next_paragraph(self):
        """Test moving when no next paragraph goes to last line."""
        cursor = CursorManager(["first", "second"])
        cursor.current_line = 0

        cursor.move_to_next_paragraph()

        assert cursor.current_line == 1
        assert cursor.current_col == EXPECTED_COL_END_OF_SECOND  # End of "second"
