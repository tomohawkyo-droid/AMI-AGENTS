"""Unit tests for ami/cli_components/legend.py."""

import pytest

from ami.cli_components.legend import (
    C_DIM,
    C_RESET,
    WIDE_EMOJI,
    Legend,
    LegendGroup,
    LegendItem,
    get_visual_width,
    pad_center,
)

EXPECTED_ASCII_WIDTH_HELLO = 5
EXPECTED_ANSI_BOLD_WIDTH = 5
EXPECTED_ANSI_COLOR_WIDTH = 5
EXPECTED_ANSI_MULTI_WIDTH = 4
EXPECTED_EMOJI_WIDTH = 2
EXPECTED_EMOJI_VARIATION_WIDTH = 2
EXPECTED_MIXED_CONTENT_WIDTH = 5
EXPECTED_CJK_SINGLE_WIDTH = 2
EXPECTED_CJK_THREE_CHARS_WIDTH = 6
EXPECTED_PAD_CENTER_LEN_6 = 6
EXPECTED_PAD_CENTER_LEN_5 = 5


class TestGetVisualWidth:
    """Tests for get_visual_width function."""

    def test_simple_ascii(self):
        """Test width of simple ASCII text."""
        assert get_visual_width("hello") == EXPECTED_ASCII_WIDTH_HELLO
        assert get_visual_width("") == 0
        assert get_visual_width("a") == 1

    def test_strips_ansi_codes(self):
        """Test ANSI escape codes are not counted."""
        # Bold text
        assert get_visual_width("\033[1mhello\033[0m") == EXPECTED_ANSI_BOLD_WIDTH
        # Colored text
        assert get_visual_width("\033[32mgreen\033[0m") == EXPECTED_ANSI_COLOR_WIDTH
        # Multiple codes
        width = get_visual_width("\033[1m\033[32mtext\033[0m")
        assert width == EXPECTED_ANSI_MULTI_WIDTH

    def test_wide_emoji_single_char(self):
        """Test single character wide emoji."""
        for emoji in ["🟢", "🟡", "🔴"]:
            # These emoji take 2 terminal cells
            assert get_visual_width(emoji) == EXPECTED_EMOJI_WIDTH

    def test_wide_emoji_with_variation_selector(self):
        """Test emoji with variation selector (2 chars)."""
        # ⚙️ is a variation selector sequence
        assert get_visual_width("⚙️") == EXPECTED_EMOJI_VARIATION_WIDTH
        assert get_visual_width("⚠️") == EXPECTED_EMOJI_VARIATION_WIDTH

    def test_mixed_content(self):
        """Test mixed ASCII and emoji."""
        # "🟢 ok" = 2 (emoji) + 1 (space) + 2 (ok) = 5
        assert get_visual_width("🟢 ok") == EXPECTED_MIXED_CONTENT_WIDTH

    def test_east_asian_wide_chars(self):
        """Test East Asian wide characters."""
        # CJK characters are typically 2 cells wide
        assert get_visual_width("中") == EXPECTED_CJK_SINGLE_WIDTH
        # 3 CJK chars x 2 width each
        width = get_visual_width("日本語")
        assert width == EXPECTED_CJK_THREE_CHARS_WIDTH


class TestPadCenter:
    """Tests for pad_center function."""

    def test_pads_short_text(self):
        """Test padding shorter text to target width."""
        result = pad_center("hi", 6)
        assert len(result) == EXPECTED_PAD_CENTER_LEN_6
        assert result == "  hi  "

    def test_odd_padding(self):
        """Test odd amount of padding (left gets less)."""
        result = pad_center("hi", 5)
        assert len(result) == EXPECTED_PAD_CENTER_LEN_5
        assert result == " hi  "

    def test_no_padding_needed(self):
        """Test when text already equals target width."""
        result = pad_center("hello", 5)
        assert result == "hello"

    def test_text_exceeds_width(self):
        """Test when text exceeds target width."""
        result = pad_center("hello world", 5)
        assert result == "hello world"

    def test_accounts_for_emoji_width(self):
        """Test padding accounts for emoji visual width."""
        # Emoji "🟢" has visual width 2
        result = pad_center("🟢", 4)
        # Should add 2 chars of padding (1 left, 1 right)
        assert result == " 🟢 "


class TestLegendItem:
    """Tests for LegendItem class."""

    def test_init(self):
        """Test LegendItem initialization."""
        item = LegendItem("🟢", "ok")
        assert item.icon == "🟢"
        assert item.label == "ok"

    def test_slots(self):
        """Test LegendItem uses __slots__."""
        item = LegendItem("🟢", "ok")
        assert hasattr(item, "__slots__")
        with pytest.raises(AttributeError):
            item.extra = "not allowed"


class TestLegend:
    """Tests for Legend class."""

    def test_init_defaults(self):
        """Test Legend initialization with defaults."""
        legend = Legend([LegendGroup([LegendItem("🟢", "ok")])])
        assert legend.separator == "│"
        assert legend.dim is True

    def test_init_custom(self):
        """Test Legend initialization with custom params."""
        legend = Legend(
            [LegendGroup([LegendItem("🟢", "ok")])], separator="|", dim=False
        )
        assert legend.separator == "|"
        assert legend.dim is False

    def test_render_single_group(self):
        """Test render with single group."""
        legend = Legend(
            [LegendGroup([LegendItem("🟢", "ok"), LegendItem("🔴", "fail")])], dim=False
        )
        icons_line, labels_line = legend.render(40)

        assert "🟢" in icons_line
        assert "🔴" in icons_line
        assert "ok" in labels_line
        assert "fail" in labels_line

    def test_render_multiple_groups(self):
        """Test render with multiple groups."""
        legend = Legend(
            [
                LegendGroup([LegendItem("🟢", "ok"), LegendItem("🔴", "fail")]),
                LegendGroup([LegendItem("🚀", "boot"), LegendItem("💤", "manual")]),
            ],
            dim=False,
        )
        icons_line, _labels_line = legend.render(80)

        # Both groups present
        assert "🟢" in icons_line
        assert "🚀" in icons_line
        assert "│" in icons_line  # Separator between groups

    def test_render_with_dim(self):
        """Test render applies dim styling when enabled."""
        legend = Legend([LegendGroup([LegendItem("🟢", "ok")])], dim=True)
        icons_line, labels_line = legend.render(40)

        assert icons_line.startswith(C_DIM)
        assert icons_line.endswith(C_RESET)
        assert labels_line.startswith(C_DIM)
        assert labels_line.endswith(C_RESET)

    def test_render_without_dim(self):
        """Test render skips dim styling when disabled."""
        legend = Legend([LegendGroup([LegendItem("🟢", "ok")])], dim=False)
        icons_line, labels_line = legend.render(40)

        assert not icons_line.startswith(C_DIM)
        assert not labels_line.startswith(C_DIM)

    def test_render_centering(self):
        """Test render centers content within width."""
        legend = Legend([LegendGroup([LegendItem("x", "y")])], dim=False)
        icons_line, labels_line = legend.render(80)

        # Content should be centered with spaces
        assert len(icons_line) > 1
        assert len(labels_line) > 1


class TestWideEmoji:
    """Tests for WIDE_EMOJI constant."""

    def test_contains_status_icons(self):
        """Test WIDE_EMOJI contains expected status icons."""
        assert "🟢" in WIDE_EMOJI
        assert "🟡" in WIDE_EMOJI
        assert "🔴" in WIDE_EMOJI
        assert "⚪" in WIDE_EMOJI

    def test_contains_functional_icons(self):
        """Test WIDE_EMOJI contains expected functional icons."""
        assert "🐳" in WIDE_EMOJI
        assert "🚀" in WIDE_EMOJI
        assert "💤" in WIDE_EMOJI

    def test_is_frozenset(self):
        """Test WIDE_EMOJI is immutable."""
        assert isinstance(WIDE_EMOJI, frozenset)
