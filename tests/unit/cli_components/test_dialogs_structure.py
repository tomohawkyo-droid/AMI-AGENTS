"""Tests for dialog structure, utilities, and constants."""

from unittest.mock import patch

import pytest

from ami.cli_components import dialogs
from ami.cli_components.dialogs import (
    ANSI_ESCAPE,
    DEFAULT_DIALOG_WIDTH,
    DOWN,
    ENTER,
    ESC,
    LEFT,
    RIGHT,
    UP,
    AlertDialog,
    BaseDialog,
    ConfirmationDialog,
    alert,
    confirm,
    multiselect,
    select,
    strip_ansi,
    visible_len,
)

EXPECTED_VISIBLE_LEN_HELLO = 5
EXPECTED_VISIBLE_LEN_ANSI = 5
EXPECTED_VISIBLE_LEN_MULTI_COLOR = 9
EXPECTED_DEFAULT_WIDTH = 80
EXPECTED_DEFAULT_BASE_WIDTH = 80
EXPECTED_CUSTOM_BASE_WIDTH = 100
EXPECTED_ALERT_WIDTH = 60
EXPECTED_CONFIRM_WIDTH = 70
EXPECTED_READ_KEY_CALL_COUNT = 3
EXPECTED_ALERT_RENDER_LINES = 7


class TestStripAnsi:
    """Tests for strip_ansi function."""

    def test_removes_color_codes(self):
        """Test removes ANSI color codes."""
        text = "\033[31mred\033[0m"
        assert strip_ansi(text) == "red"

    def test_removes_bold(self):
        """Test removes ANSI bold codes."""
        text = "\033[1mbold\033[0m"
        assert strip_ansi(text) == "bold"

    def test_removes_multiple_codes(self):
        """Test removes multiple ANSI codes."""
        text = "\033[1m\033[32mgreen bold\033[0m"
        assert strip_ansi(text) == "green bold"

    def test_plain_text_unchanged(self):
        """Test plain text is unchanged."""
        text = "plain text"
        assert strip_ansi(text) == "plain text"

    def test_empty_string(self):
        """Test empty string returns empty."""
        assert strip_ansi("") == ""


class TestVisibleLen:
    """Tests for visible_len function."""

    def test_plain_text(self):
        """Test visible length of plain text."""
        assert visible_len("hello") == EXPECTED_VISIBLE_LEN_HELLO
        assert visible_len("") == 0

    def test_with_ansi_codes(self):
        """Test visible length excludes ANSI codes."""
        text = "\033[31mhello\033[0m"
        assert visible_len(text) == EXPECTED_VISIBLE_LEN_ANSI

    def test_multiple_colors(self):
        """Test visible length with multiple color codes."""
        text = "\033[31mred\033[0m \033[32mgreen\033[0m"
        assert visible_len(text) == EXPECTED_VISIBLE_LEN_MULTI_COLOR  # "red green"


class TestConstants:
    """Tests for module constants."""

    def test_key_constants(self):
        """Test key constants are defined."""
        assert UP == "UP"
        assert DOWN == "DOWN"
        assert LEFT == "LEFT"
        assert RIGHT == "RIGHT"
        assert ENTER == "ENTER"
        assert ESC == "ESC"

    def test_default_width(self):
        """Test default dialog width."""
        assert DEFAULT_DIALOG_WIDTH == EXPECTED_DEFAULT_WIDTH

    def test_ansi_escape_pattern(self):
        """Test ANSI escape regex pattern matches correctly."""

        assert ANSI_ESCAPE.search("\033[31mtext")
        assert not ANSI_ESCAPE.search("plain text")


class TestBaseDialog:
    """Tests for BaseDialog class."""

    def test_init_defaults(self):
        """Test BaseDialog initialization with defaults."""
        dialog = BaseDialog()
        assert dialog.title == "Dialog"
        assert dialog.width == EXPECTED_DEFAULT_BASE_WIDTH
        assert dialog._last_render_lines == 0

    def test_init_custom(self):
        """Test BaseDialog initialization with custom values."""
        dialog = BaseDialog(title="Test Title", width=100)
        assert dialog.title == "Test Title"
        assert dialog.width == EXPECTED_CUSTOM_BASE_WIDTH

    def test_render_not_implemented(self):
        """Test render raises NotImplementedError."""
        dialog = BaseDialog()
        with pytest.raises(NotImplementedError):
            dialog.render()

    def test_format_shortcut_found_in_label(self):
        """Test _format_shortcut when shortcut is in label."""
        dialog = BaseDialog()
        result = dialog._format_shortcut("Save", "S", selected=False)
        # Should contain underline codes around 'S'
        assert "Save" in result or "s" in result.lower()
        assert "\033[4m" in result  # underline code

    def test_format_shortcut_not_found_in_label(self):
        """Test _format_shortcut when shortcut not in label."""
        dialog = BaseDialog()
        result = dialog._format_shortcut("Delete", "X", selected=False)
        # Should contain parentheses and the shortcut (with ANSI codes)
        assert "Delete" in result
        assert "X" in result
        # The result contains underlined X in parentheses
        assert "(" in result
        assert ")" in result

    def test_format_shortcut_selected(self):
        """Test _format_shortcut with selected=True."""
        dialog = BaseDialog()
        result = dialog._format_shortcut("Yes", "Y", selected=True)
        # Should contain reverse video code
        assert "\033[7m" in result

    def test_format_shortcut_not_selected(self):
        """Test _format_shortcut with selected=False."""
        dialog = BaseDialog()
        result = dialog._format_shortcut("No", "N", selected=False)
        # Should not start with reverse video
        assert not result.startswith("\033[7m")


class TestAlertDialogStructure:
    """Tests for AlertDialog class structure."""

    def test_inherits_base_dialog(self):
        """Test AlertDialog inherits from BaseDialog."""

        assert issubclass(AlertDialog, BaseDialog)

    def test_init(self):
        """Test AlertDialog initialization."""

        alert_dlg = AlertDialog(message="Test message", title="Test Alert", width=60)
        assert alert_dlg.message == "Test message"
        assert alert_dlg.title == "Test Alert"
        assert alert_dlg.width == EXPECTED_ALERT_WIDTH


class TestConfirmationDialogStructure:
    """Tests for ConfirmationDialog class structure."""

    def test_inherits_base_dialog(self):
        """Test ConfirmationDialog inherits from BaseDialog."""

        assert issubclass(ConfirmationDialog, BaseDialog)

    def test_init(self):
        """Test ConfirmationDialog initialization."""

        dialog = ConfirmationDialog(message="Are you sure?", title="Confirm", width=70)
        assert dialog.message == "Are you sure?"
        assert dialog.title == "Confirm"
        assert dialog.width == EXPECTED_CONFIRM_WIDTH
        assert dialog.selected_yes is True  # Default


class TestFacadeFunctions:
    """Tests for facade function signatures."""

    def test_confirm_exists(self):
        """Test confirm function exists."""

        assert callable(confirm)

    def test_alert_exists(self):
        """Test alert function exists."""

        assert callable(alert)

    def test_select_exists(self):
        """Test select function exists."""

        assert callable(select)

    def test_multiselect_exists(self):
        """Test multiselect function exists."""

        assert callable(multiselect)


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_exports(self):
        """Test __all__ contains expected exports."""

        expected_exports = [
            "AlertDialog",
            "BaseDialog",
            "ConfirmationDialog",
            "SelectionDialog",
            "SelectionDialogConfig",
            "alert",
            "confirm",
            "multiselect",
            "select",
            "strip_ansi",
            "visible_len",
        ]
        for export in expected_exports:
            assert export in dialogs.__all__


class TestBaseDialogClear:
    """Tests for BaseDialog.clear method."""

    @patch("ami.cli_components.dialogs.TUI")
    def test_clear_calls_tui_clear_lines(self, mock_tui):
        """Test clear calls TUI.clear_lines with correct count."""
        dialog = BaseDialog()
        dialog._last_render_lines = 5

        dialog.clear()

        mock_tui.clear_lines.assert_called_once_with(5)
        assert dialog._last_render_lines == 0


class TestAlertDialogBehavior:
    """Tests for AlertDialog show and render behavior."""

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_show_waits_for_enter(self, mock_tui, mock_read_key):
        """Test show waits for Enter key."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Test message"]
        mock_read_key.return_value = ENTER

        alert_dlg = AlertDialog("Test message")
        alert_dlg.show()

        mock_read_key.assert_called()

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_show_waits_for_esc(self, mock_tui, mock_read_key):
        """Test show accepts Esc key."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Test"]
        mock_read_key.return_value = ESC

        alert_dlg = AlertDialog("Test")
        alert_dlg.show()

        mock_read_key.assert_called()

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_show_ignores_other_keys(self, mock_tui, mock_read_key):
        """Test show ignores other keys until Enter/Esc."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Test"]
        # Return 'x' first, then Enter
        mock_read_key.side_effect = ["x", "y", ENTER]

        alert_dlg = AlertDialog("Test")
        alert_dlg.show()

        assert mock_read_key.call_count == EXPECTED_READ_KEY_CALL_COUNT

    @patch("ami.cli_components.dialogs.TUI")
    def test_render_draws_box(self, mock_tui):
        """Test _render draws box with content."""

        mock_tui.draw_box.return_value = 7
        mock_tui.wrap_text.return_value = ["Line 1", "Line 2"]

        alert_dlg = AlertDialog("Line 1\nLine 2", title="Test Alert")
        alert_dlg._render()

        mock_tui.draw_box.assert_called_once()
        assert alert_dlg._last_render_lines == EXPECTED_ALERT_RENDER_LINES
