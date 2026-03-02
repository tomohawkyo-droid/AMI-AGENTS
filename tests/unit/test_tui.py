"""Unit tests for cli_components/tui module."""

import sys
from io import StringIO
from unittest.mock import patch

from ami.cli_components.text_input_utils import Colors
from ami.cli_components.tui import (
    TUI,
    BoxStyle,
    visible_len,
)

EXPECTED_PLAIN_TEXT_LEN = 5
EXPECTED_ANSI_STRIPPED_LEN = 5
EXPECTED_MULTI_COLOR_LEN = 8
EXPECTED_DEFAULT_BOX_WIDTH = 60
EXPECTED_CUSTOM_BOX_WIDTH = 80
EXPECTED_CLEAR_LINE_COUNT = 3
EXPECTED_BOX_LINE_COUNT = 6
MIN_EMPTY_BOX_LINES = 4
MAX_WRAP_LINE_WIDTH = 20


class TestVisibleLen:
    """Tests for visible_len function."""

    def test_plain_text(self) -> None:
        """Test length of plain text."""
        assert visible_len("hello") == EXPECTED_PLAIN_TEXT_LEN

    def test_strips_ansi_codes(self) -> None:
        """Test strips ANSI escape codes."""
        colored = f"{Colors.RED}hello{Colors.RESET}"
        assert visible_len(colored) == EXPECTED_ANSI_STRIPPED_LEN

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert visible_len("") == 0

    def test_multiple_colors(self) -> None:
        """Test text with multiple color codes."""
        text = f"{Colors.RED}red{Colors.GREEN}green{Colors.RESET}"
        assert visible_len(text) == EXPECTED_MULTI_COLOR_LEN  # "redgreen"


class TestBoxStyle:
    """Tests for BoxStyle model."""

    def test_default_values(self) -> None:
        """Test default values."""
        style = BoxStyle()

        assert style.width == EXPECTED_DEFAULT_BOX_WIDTH
        assert style.border_color == Colors.CYAN
        assert style.text_color == Colors.RESET
        assert style.center_content is False

    def test_custom_values(self) -> None:
        """Test custom values."""
        style = BoxStyle(
            width=80,
            border_color=Colors.GREEN,
            text_color=Colors.YELLOW,
            center_content=True,
        )

        assert style.width == EXPECTED_CUSTOM_BOX_WIDTH
        assert style.border_color == Colors.GREEN
        assert style.center_content is True


class TestTUIClearLines:
    """Tests for TUI.clear_lines method."""

    def test_clear_zero_lines(self, capsys) -> None:
        """Test clearing zero lines does nothing."""
        TUI.clear_lines(0)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_clear_multiple_lines(self) -> None:
        """Test clearing multiple lines."""
        output = StringIO()
        with (
            patch.object(sys.stdout, "write", output.write),
            patch.object(sys.stdout, "flush"),
        ):
            TUI.clear_lines(3)

        # Should have 3 pairs of move-up + clear-line
        result = output.getvalue()
        assert result.count("\033[1A") == EXPECTED_CLEAR_LINE_COUNT
        assert result.count("\033[2K") == EXPECTED_CLEAR_LINE_COUNT


class TestTUIDrawBox:
    """Tests for TUI.draw_box method."""

    def test_draws_simple_box(self, capsys) -> None:
        """Test draws simple box without title."""
        lines = TUI.draw_box(["Hello", "World"])

        captured = capsys.readouterr()
        assert "┌" in captured.out
        assert "└" in captured.out
        assert "Hello" in captured.out
        assert "World" in captured.out
        assert lines > 0

    def test_draws_box_with_title(self, capsys) -> None:
        """Test draws box with title."""
        TUI.draw_box(["Content"], title="Test Title")

        captured = capsys.readouterr()
        assert "Test Title" in captured.out

    def test_draws_box_with_footer(self, capsys) -> None:
        """Test draws box with footer."""
        TUI.draw_box(["Content"], footer="Press Enter")

        captured = capsys.readouterr()
        assert "Press Enter" in captured.out

    def test_draws_box_with_custom_style(self, capsys) -> None:
        """Test draws box with custom style."""
        style = BoxStyle(width=40)
        lines = TUI.draw_box(["Short"], style=style)

        captured = capsys.readouterr()
        # Box should be drawn
        assert "┌" in captured.out
        assert lines > 0

    def test_draws_centered_content(self, capsys) -> None:
        """Test draws centered content."""
        style = BoxStyle(center_content=True)
        TUI.draw_box(["Test"], style=style)

        captured = capsys.readouterr()
        assert "Test" in captured.out

    def test_returns_line_count(self) -> None:
        """Test returns correct line count."""
        # Capture output to not pollute test output
        output = StringIO()
        with (
            patch.object(sys.stdout, "write", output.write),
            patch.object(sys.stdout, "flush"),
        ):
            lines = TUI.draw_box(["Line1", "Line2"])

        # Should be: top border + padding + 2 content + padding + bottom = 6
        assert lines == EXPECTED_BOX_LINE_COUNT

    def test_handles_empty_content(self, capsys) -> None:
        """Test handles empty content list."""
        lines = TUI.draw_box([])

        captured = capsys.readouterr()
        assert "┌" in captured.out
        assert "└" in captured.out
        # Should have borders and padding
        assert lines >= MIN_EMPTY_BOX_LINES

    def test_truncates_long_title(self, capsys) -> None:
        """Test truncates title that's too long."""
        long_title = "A" * 100
        TUI.draw_box(["Content"], title=long_title)

        captured = capsys.readouterr()
        # Should still draw the box
        assert "┌" in captured.out


class TestTUIWrapText:
    """Tests for TUI.wrap_text method."""

    def test_wraps_long_text(self) -> None:
        """Test wraps text at word boundaries."""
        text = "The five boxing wizards jump quickly today"
        lines = TUI.wrap_text(text, 20)

        assert len(lines) > 1
        for line in lines:
            assert len(line) <= MAX_WRAP_LINE_WIDTH

    def test_short_text_no_wrap(self) -> None:
        """Test short text doesn't wrap."""
        text = "Hello"
        lines = TUI.wrap_text(text, 20)

        assert lines == ["Hello"]

    def test_empty_text(self) -> None:
        """Test empty text."""
        lines = TUI.wrap_text("", 20)

        assert lines == []

    def test_single_long_word(self) -> None:
        """Test single word longer than width."""
        text = "supercalifragilisticexpialidocious"
        lines = TUI.wrap_text(text, 10)

        # Long word should be on its own line
        assert len(lines) == 1
        assert text in lines[0]

    def test_preserves_word_order(self) -> None:
        """Test preserves word order."""
        text = "one two three four five"
        lines = TUI.wrap_text(text, 15)

        rejoined = " ".join(lines)
        assert rejoined == text

    def test_multiple_spaces_collapsed(self) -> None:
        """Test multiple spaces are collapsed."""
        text = "one   two    three"
        lines = TUI.wrap_text(text, 50)

        assert lines == ["one two three"]
