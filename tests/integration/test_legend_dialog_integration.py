"""Integration tests for legend and dialog components.

Exercises: cli_components/legend.py,
cli_components/dialogs.py,
cli_components/tui.py (BoxStyle)
"""

import pytest

from ami.cli_components.dialogs import (
    DEFAULT_DIALOG_WIDTH,
    BaseDialog,
    strip_ansi,
    visible_len,
)
from ami.cli_components.keys import DOWN, ENTER, ESC, LEFT, RIGHT, UP
from ami.cli_components.legend import (
    Legend,
    LegendGroup,
    LegendItem,
    get_visual_width,
    pad_center,
)
from ami.cli_components.tui import BoxStyle
from ami.core.config import _ConfigSingleton

# -- Constants for expected test values --------------------------------------

EXPECTED_ASCII_WIDTH = 5
EXPECTED_WIDE_EMOJI_WIDTH = 2
EXPECTED_DOUBLE_EMOJI_WIDTH = 4
EXPECTED_MIXED_CONTENT_WIDTH = 5
EXPECTED_PAD_WIDTH = 10
EXPECTED_PAD_ODD_WIDTH = 4
EXPECTED_DEFAULT_DIALOG_WIDTH = 80
EXPECTED_CUSTOM_DIALOG_WIDTH = 60
EXPECTED_DEFAULT_BOX_WIDTH = 60
EXPECTED_CUSTOM_BOX_WIDTH = 100


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# -------------------------------------------------------------------
# Legend: get_visual_width
# -------------------------------------------------------------------


class TestLegendVisualWidth:
    """Test get_visual_width from legend module."""

    def test_ascii_text(self):
        assert get_visual_width("hello") == EXPECTED_ASCII_WIDTH

    def test_empty_string(self):
        assert get_visual_width("") == 0

    def test_ansi_stripped(self):
        assert get_visual_width("\033[31mhello\033[0m") == EXPECTED_ASCII_WIDTH

    def test_wide_emoji(self):
        assert get_visual_width("\N{LARGE GREEN CIRCLE}") == EXPECTED_WIDE_EMOJI_WIDTH

    def test_mixed_content(self):
        # "ok" = 2, green circle = 2, space = 1 => 5
        assert (
            get_visual_width("\N{LARGE GREEN CIRCLE} ok")
            == EXPECTED_MIXED_CONTENT_WIDTH
        )

    def test_multiple_emoji(self):
        result = get_visual_width("\N{LARGE GREEN CIRCLE}\N{LARGE RED CIRCLE}")
        assert result == EXPECTED_DOUBLE_EMOJI_WIDTH

    def test_variation_selector_emoji(self):
        assert get_visual_width("\u2699\ufe0f") == EXPECTED_WIDE_EMOJI_WIDTH


# -------------------------------------------------------------------
# Legend: pad_center
# -------------------------------------------------------------------


class TestPadCenter:
    """Test pad_center function."""

    def test_basic_centering(self):
        result = pad_center("hi", EXPECTED_PAD_WIDTH)
        assert len(result) == EXPECTED_PAD_WIDTH
        assert "hi" in result

    def test_already_wide_enough(self):
        result = pad_center("hello world", EXPECTED_ASCII_WIDTH)
        assert result == "hello world"

    def test_exact_width(self):
        result = pad_center("abc", 3)
        assert result == "abc"

    def test_odd_padding(self):
        result = pad_center("a", EXPECTED_PAD_ODD_WIDTH)
        assert len(result) == EXPECTED_PAD_ODD_WIDTH
        assert "a" in result


# -------------------------------------------------------------------
# Legend: LegendItem and Legend
# -------------------------------------------------------------------


class TestLegendItem:
    """Test LegendItem construction."""

    def test_basic_item(self):
        item = LegendItem("\N{LARGE GREEN CIRCLE}", "ok")
        assert item.icon == "\N{LARGE GREEN CIRCLE}"
        assert item.label == "ok"


class TestLegendRender:
    """Test Legend.render method."""

    def test_single_group(self):
        legend = Legend(
            [
                LegendGroup(
                    [
                        LegendItem(
                            "\N{LARGE GREEN CIRCLE}",
                            "ok",
                        ),
                        LegendItem(
                            "\N{LARGE RED CIRCLE}",
                            "fail",
                        ),
                    ]
                )
            ]
        )
        icons_line, labels_line = legend.render(width=EXPECTED_DEFAULT_DIALOG_WIDTH)
        assert "\N{LARGE GREEN CIRCLE}" in icons_line
        assert "\N{LARGE RED CIRCLE}" in icons_line
        assert "ok" in labels_line
        assert "fail" in labels_line

    def test_multiple_groups(self):
        legend = Legend(
            [
                LegendGroup(
                    [
                        LegendItem(
                            "\N{LARGE GREEN CIRCLE}",
                            "ok",
                        )
                    ]
                ),
                LegendGroup([LegendItem("\N{ROCKET}", "boot")]),
            ]
        )
        icons_line, _labels_line = legend.render(width=EXPECTED_DEFAULT_DIALOG_WIDTH)
        # separator between groups
        assert "\u2502" in icons_line

    def test_dim_styling(self):
        legend = Legend(
            [
                LegendGroup(
                    [
                        LegendItem(
                            "\N{LARGE GREEN CIRCLE}",
                            "ok",
                        )
                    ]
                )
            ],
            dim=True,
        )
        icons_line, _ = legend.render(width=EXPECTED_DEFAULT_DIALOG_WIDTH)
        assert "\033[2m" in icons_line  # dim code

    def test_no_dim_styling(self):
        legend = Legend(
            [
                LegendGroup(
                    [
                        LegendItem(
                            "\N{LARGE GREEN CIRCLE}",
                            "ok",
                        )
                    ]
                )
            ],
            dim=False,
        )
        icons_line, _ = legend.render(width=EXPECTED_DEFAULT_DIALOG_WIDTH)
        assert "\033[2m" not in icons_line

    def test_custom_separator(self):
        legend = Legend(
            [
                LegendGroup([LegendItem("A", "a")]),
                LegendGroup([LegendItem("B", "b")]),
            ],
            separator="|",
            dim=False,
        )
        icons_line, _ = legend.render(width=EXPECTED_DEFAULT_DIALOG_WIDTH)
        assert "|" in icons_line


# -------------------------------------------------------------------
# Dialogs: strip_ansi and visible_len
# -------------------------------------------------------------------


class TestDialogUtils:
    """Test dialog utility functions."""

    def test_strip_ansi(self):
        assert strip_ansi("\033[31mred\033[0m") == "red"

    def test_strip_ansi_no_codes(self):
        assert strip_ansi("plain text") == "plain text"

    def test_strip_ansi_empty(self):
        assert strip_ansi("") == ""

    def test_visible_len(self):
        assert visible_len("\033[31mhello\033[0m") == EXPECTED_ASCII_WIDTH

    def test_visible_len_plain(self):
        assert visible_len("hello") == EXPECTED_ASCII_WIDTH


# -------------------------------------------------------------------
# Dialogs: BaseDialog construction
# -------------------------------------------------------------------


class TestBaseDialogConstruction:
    """Test BaseDialog basic construction."""

    def test_default_construction(self):
        dialog = BaseDialog()
        assert dialog.title == "Dialog"
        assert dialog.width == EXPECTED_DEFAULT_DIALOG_WIDTH
        assert dialog._last_render_lines == 0

    def test_custom_construction(self):
        dialog = BaseDialog(
            title="Custom",
            width=EXPECTED_CUSTOM_DIALOG_WIDTH,
        )
        assert dialog.title == "Custom"
        assert dialog.width == EXPECTED_CUSTOM_DIALOG_WIDTH

    def test_format_shortcut_found(self):
        dialog = BaseDialog()
        result = dialog._format_shortcut("Yes", "Y", selected=False)
        assert "Y" in result
        assert "es" in result

    def test_format_shortcut_not_found(self):
        dialog = BaseDialog()
        result = dialog._format_shortcut("OK", "x", selected=False)
        assert "x" in result
        assert "OK" in result

    def test_format_shortcut_selected(self):
        dialog = BaseDialog()
        result = dialog._format_shortcut("No", "N", selected=True)
        # Should contain reverse video escape
        assert "\033[7m" in result or "N" in result


# -------------------------------------------------------------------
# TUI BoxStyle
# -------------------------------------------------------------------


class TestTUIBoxStyle:
    """Test TUI BoxStyle construction."""

    def test_default_box_style(self):
        style = BoxStyle()
        assert style.width == EXPECTED_DEFAULT_BOX_WIDTH
        assert style.center_content is False

    def test_custom_box_style(self):
        style = BoxStyle(
            width=EXPECTED_CUSTOM_BOX_WIDTH,
            center_content=True,
        )
        assert style.width == EXPECTED_CUSTOM_BOX_WIDTH
        assert style.center_content is True


# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------


class TestDialogConstants:
    """Test dialog constants."""

    def test_default_dialog_width(self):
        assert DEFAULT_DIALOG_WIDTH == EXPECTED_DEFAULT_DIALOG_WIDTH

    def test_key_constants(self):
        assert UP == "UP"
        assert DOWN == "DOWN"
        assert LEFT == "LEFT"
        assert RIGHT == "RIGHT"
        assert ENTER == "ENTER"
        assert ESC == "ESC"
