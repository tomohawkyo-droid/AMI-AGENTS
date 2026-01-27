"""Comprehensive unit tests for ami/cli_components/terminal/ansi.py."""

from unittest.mock import patch

from ami.cli_components.terminal.ansi import AnsiTerminal


class TestAnsiConstants:
    """Tests for AnsiTerminal constants."""

    def test_formatting_constants(self):
        """Test formatting constants are defined."""
        assert AnsiTerminal.RESET == "\033[0m"
        assert AnsiTerminal.BOLD == "\033[1m"
        assert AnsiTerminal.DIM == "\033[2m"
        assert AnsiTerminal.ITALIC == "\033[3m"
        assert AnsiTerminal.UNDERLINE == "\033[4m"
        assert AnsiTerminal.REVERSE == "\033[7m"
        assert AnsiTerminal.HIDDEN == "\033[8m"
        assert AnsiTerminal.STRIKETHROUGH == "\033[9m"

    def test_foreground_colors(self):
        """Test foreground color constants."""
        assert AnsiTerminal.BLACK == "\033[30m"
        assert AnsiTerminal.RED == "\033[31m"
        assert AnsiTerminal.GREEN == "\033[32m"
        assert AnsiTerminal.YELLOW == "\033[33m"
        assert AnsiTerminal.BLUE == "\033[34m"
        assert AnsiTerminal.MAGENTA == "\033[35m"
        assert AnsiTerminal.CYAN == "\033[36m"
        assert AnsiTerminal.WHITE == "\033[37m"

    def test_background_colors(self):
        """Test background color constants."""
        assert AnsiTerminal.BG_BLACK == "\033[40m"
        assert AnsiTerminal.BG_RED == "\033[41m"
        assert AnsiTerminal.BG_GREEN == "\033[42m"
        assert AnsiTerminal.BG_YELLOW == "\033[43m"
        assert AnsiTerminal.BG_BLUE == "\033[44m"
        assert AnsiTerminal.BG_MAGENTA == "\033[45m"
        assert AnsiTerminal.BG_CYAN == "\033[46m"
        assert AnsiTerminal.BG_WHITE == "\033[47m"


class TestMoveUp:
    """Tests for move_up method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_up_one_line(self, mock_flush, mock_write):
        """Test moving cursor up one line."""
        AnsiTerminal.move_up(1)

        mock_write.assert_called_once_with("\033[1A")
        mock_flush.assert_called_once()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_up_multiple_lines(self, mock_flush, mock_write):
        """Test moving cursor up multiple lines."""
        AnsiTerminal.move_up(5)

        mock_write.assert_called_once_with("\033[5A")

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_up_zero_lines(self, mock_flush, mock_write):
        """Test moving cursor up zero lines does nothing."""
        AnsiTerminal.move_up(0)

        mock_write.assert_not_called()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_up_default(self, mock_flush, mock_write):
        """Test move_up with default value."""
        AnsiTerminal.move_up()

        mock_write.assert_called_once_with("\033[1A")


class TestMoveDown:
    """Tests for move_down method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_down_one_line(self, mock_flush, mock_write):
        """Test moving cursor down one line."""
        AnsiTerminal.move_down(1)

        mock_write.assert_called_once_with("\033[1B")
        mock_flush.assert_called_once()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_down_multiple_lines(self, mock_flush, mock_write):
        """Test moving cursor down multiple lines."""
        AnsiTerminal.move_down(3)

        mock_write.assert_called_once_with("\033[3B")

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_down_zero_lines(self, mock_flush, mock_write):
        """Test moving cursor down zero lines does nothing."""
        AnsiTerminal.move_down(0)

        mock_write.assert_not_called()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_down_default(self, mock_flush, mock_write):
        """Test move_down with default value."""
        AnsiTerminal.move_down()

        mock_write.assert_called_once_with("\033[1B")


class TestMoveRight:
    """Tests for move_right method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_right_one_column(self, mock_flush, mock_write):
        """Test moving cursor right one column."""
        AnsiTerminal.move_right(1)

        mock_write.assert_called_once_with("\033[1C")
        mock_flush.assert_called_once()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_right_multiple_columns(self, mock_flush, mock_write):
        """Test moving cursor right multiple columns."""
        AnsiTerminal.move_right(10)

        mock_write.assert_called_once_with("\033[10C")

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_right_zero_columns(self, mock_flush, mock_write):
        """Test moving cursor right zero columns does nothing."""
        AnsiTerminal.move_right(0)

        mock_write.assert_not_called()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_right_default(self, mock_flush, mock_write):
        """Test move_right with default value."""
        AnsiTerminal.move_right()

        mock_write.assert_called_once_with("\033[1C")


class TestMoveLeft:
    """Tests for move_left method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_left_one_column(self, mock_flush, mock_write):
        """Test moving cursor left one column."""
        AnsiTerminal.move_left(1)

        mock_write.assert_called_once_with("\033[1D")
        mock_flush.assert_called_once()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_left_multiple_columns(self, mock_flush, mock_write):
        """Test moving cursor left multiple columns."""
        AnsiTerminal.move_left(7)

        mock_write.assert_called_once_with("\033[7D")

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_left_zero_columns(self, mock_flush, mock_write):
        """Test moving cursor left zero columns does nothing."""
        AnsiTerminal.move_left(0)

        mock_write.assert_not_called()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_left_default(self, mock_flush, mock_write):
        """Test move_left with default value."""
        AnsiTerminal.move_left()

        mock_write.assert_called_once_with("\033[1D")


class TestMoveToColumn:
    """Tests for move_to_column method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_to_column_1(self, mock_flush, mock_write):
        """Test moving cursor to column 1."""
        AnsiTerminal.move_to_column(1)

        mock_write.assert_called_once_with("\033[1G")
        mock_flush.assert_called_once()

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_to_column_80(self, mock_flush, mock_write):
        """Test moving cursor to column 80."""
        AnsiTerminal.move_to_column(80)

        mock_write.assert_called_once_with("\033[80G")

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_move_to_column_default(self, mock_flush, mock_write):
        """Test move_to_column with default value."""
        AnsiTerminal.move_to_column()

        mock_write.assert_called_once_with("\033[1G")


class TestClearLine:
    """Tests for clear_line method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_line(self, mock_flush, mock_write):
        """Test clearing current line."""
        AnsiTerminal.clear_line()

        mock_write.assert_called_once_with("\033[2K")
        mock_flush.assert_called_once()


class TestClearScreen:
    """Tests for clear_screen method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_screen(self, mock_flush, mock_write):
        """Test clearing entire screen."""
        AnsiTerminal.clear_screen()

        mock_write.assert_called_once_with("\033[2J\033[H")
        mock_flush.assert_called_once()


class TestHideCursor:
    """Tests for hide_cursor method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_hide_cursor(self, mock_flush, mock_write):
        """Test hiding cursor."""
        AnsiTerminal.hide_cursor()

        mock_write.assert_called_once_with("\033[?25l")
        mock_flush.assert_called_once()


class TestShowCursor:
    """Tests for show_cursor method."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_show_cursor(self, mock_flush, mock_write):
        """Test showing cursor."""
        AnsiTerminal.show_cursor()

        mock_write.assert_called_once_with("\033[?25h")
        mock_flush.assert_called_once()


class TestColorize:
    """Tests for colorize method."""

    def test_colorize_red(self):
        """Test colorizing text with red."""
        result = AnsiTerminal.colorize("Hello", AnsiTerminal.RED)

        assert result == "\033[31mHello\033[0m"

    def test_colorize_blue(self):
        """Test colorizing text with blue."""
        result = AnsiTerminal.colorize("World", AnsiTerminal.BLUE)

        assert result == "\033[34mWorld\033[0m"

    def test_colorize_bold(self):
        """Test colorizing text with bold."""
        result = AnsiTerminal.colorize("Bold", AnsiTerminal.BOLD)

        assert result == "\033[1mBold\033[0m"

    def test_colorize_empty_string(self):
        """Test colorizing empty string."""
        result = AnsiTerminal.colorize("", AnsiTerminal.GREEN)

        assert result == "\033[32m\033[0m"

    def test_colorize_with_background(self):
        """Test colorizing with background color."""
        result = AnsiTerminal.colorize("BG", AnsiTerminal.BG_YELLOW)

        assert result == "\033[43mBG\033[0m"
