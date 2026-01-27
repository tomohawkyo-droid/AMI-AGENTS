"""Tests for dialog behavior and facade functions."""

from unittest.mock import MagicMock, patch

from ami.cli_components.dialogs import (
    ENTER,
    ESC,
    LEFT,
    RIGHT,
    ConfirmationDialog,
    alert,
    confirm,
    multiselect,
    select,
)

EXPECTED_CONFIRM_RENDER_LINES = 6
EXPECTED_MULTISELECT_COUNT = 2
EXPECTED_MAX_HEIGHT_VALUE = 20


class TestConfirmationDialogBehavior:
    """Tests for ConfirmationDialog run and render behavior."""

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_returns_true_on_enter_with_yes_selected(self, mock_tui, mock_read_key):
        """Test run returns True when Enter pressed with Yes selected."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.return_value = ENTER

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is True

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_returns_false_on_esc(self, mock_tui, mock_read_key):
        """Test run returns False when Esc pressed."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.return_value = ESC

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is False

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_y_shortcut_returns_true(self, mock_tui, mock_read_key):
        """Test run returns True when 'y' pressed."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.return_value = "y"

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is True

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_Y_shortcut_returns_true(self, mock_tui, mock_read_key):
        """Test run returns True when 'Y' pressed."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.return_value = "Y"

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is True

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_n_shortcut_returns_false(self, mock_tui, mock_read_key):
        """Test run returns False when 'n' pressed."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.return_value = "n"

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is False

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_N_shortcut_returns_false(self, mock_tui, mock_read_key):
        """Test run returns False when 'N' pressed."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.return_value = "N"

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is False

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_left_right_toggles_selection(self, mock_tui, mock_read_key):
        """Test run toggles selection with Left/Right."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        # LEFT toggles to No, then Enter
        mock_read_key.side_effect = [LEFT, ENTER]

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is False  # No was selected after LEFT

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_right_toggles_back_to_yes(self, mock_tui, mock_read_key):
        """Test run toggles back with Right."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        # LEFT toggles to No, RIGHT back to Yes, then Enter
        mock_read_key.side_effect = [LEFT, RIGHT, ENTER]

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is True

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_run_returns_false_on_keyboard_interrupt(self, mock_tui, mock_read_key):
        """Test run returns False on KeyboardInterrupt."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Confirm?"]
        mock_read_key.side_effect = KeyboardInterrupt()

        dialog = ConfirmationDialog("Confirm?")
        result = dialog.run()

        assert result is False

    @patch("ami.cli_components.dialogs.TUI")
    def test_render_draws_box(self, mock_tui):
        """Test _render draws box with buttons."""

        mock_tui.draw_box.return_value = 6
        mock_tui.wrap_text.return_value = ["Are you sure?"]

        dialog = ConfirmationDialog("Are you sure?")
        dialog._render()

        mock_tui.draw_box.assert_called_once()
        assert dialog._last_render_lines == EXPECTED_CONFIRM_RENDER_LINES


class TestConfirmFacade:
    """Tests for confirm facade function."""

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_confirm_returns_true(self, mock_tui, mock_read_key):
        """Test confirm returns True on yes."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Test?"]
        mock_read_key.return_value = "y"

        result = confirm("Test?")

        assert result is True

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_confirm_returns_false(self, mock_tui, mock_read_key):
        """Test confirm returns False on no."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Test?"]
        mock_read_key.return_value = "n"

        result = confirm("Test?")

        assert result is False


class TestAlertFacade:
    """Tests for alert facade function."""

    @patch("ami.cli_components.dialogs.read_key_sequence")
    @patch("ami.cli_components.dialogs.TUI")
    def test_alert_shows_and_returns(self, mock_tui, mock_read_key):
        """Test alert shows message and returns."""

        mock_tui.draw_box.return_value = 5
        mock_tui.wrap_text.return_value = ["Alert!"]
        mock_read_key.return_value = ENTER

        # Should not raise, just return
        alert("Alert!")


class TestSelectFacade:
    """Tests for select facade function."""

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_select_returns_single_item(self, mock_dialog_class):
        """Test select returns single selected item."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = {"label": "Item 1", "value": "1"}
        mock_dialog_class.return_value = mock_dialog

        result = select(["Item 1", "Item 2"])

        assert result == {"label": "Item 1", "value": "1"}

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_select_returns_none_on_cancel(self, mock_dialog_class):
        """Test select returns None on cancel."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = None
        mock_dialog_class.return_value = mock_dialog

        result = select(["Item 1", "Item 2"])

        assert result is None

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_select_returns_first_from_list(self, mock_dialog_class):
        """Test select returns first item if list returned."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = [{"label": "A"}, {"label": "B"}]
        mock_dialog_class.return_value = mock_dialog

        result = select(["A", "B"])

        assert result == {"label": "A"}

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_select_returns_none_from_empty_list(self, mock_dialog_class):
        """Test select returns None if empty list returned."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = []
        mock_dialog_class.return_value = mock_dialog

        result = select(["A"])

        assert result is None


class TestMultiselectFacade:
    """Tests for multiselect facade function."""

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_multiselect_returns_list(self, mock_dialog_class):
        """Test multiselect returns list of selected items."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = [{"label": "A"}, {"label": "B"}]
        mock_dialog_class.return_value = mock_dialog

        result = multiselect(["A", "B", "C"])

        assert len(result) == EXPECTED_MULTISELECT_COUNT

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_multiselect_returns_empty_on_cancel(self, mock_dialog_class):
        """Test multiselect returns empty list on cancel."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = None
        mock_dialog_class.return_value = mock_dialog

        result = multiselect(["A", "B"])

        assert result == []

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_multiselect_wraps_single_item(self, mock_dialog_class):
        """Test multiselect wraps single item in list."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = {"label": "Single"}  # Not a list
        mock_dialog_class.return_value = mock_dialog

        result = multiselect(["Single"])

        assert result == [{"label": "Single"}]

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_multiselect_passes_preselected(self, mock_dialog_class):
        """Test multiselect passes preselected items."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = []
        mock_dialog_class.return_value = mock_dialog

        multiselect(["A", "B"], preselected={"a", "b"})

        # Verify config was created with preselected
        call_args = mock_dialog_class.call_args
        config = call_args[0][1]  # Second positional arg
        assert config.preselected == {"a", "b"}

    @patch("ami.cli_components.dialogs.SelectionDialog")
    def test_multiselect_passes_max_height(self, mock_dialog_class):
        """Test multiselect passes max_height."""

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = []
        mock_dialog_class.return_value = mock_dialog

        multiselect(["A", "B"], max_height=20)

        call_args = mock_dialog_class.call_args
        config = call_args[0][1]
        assert config.max_height == EXPECTED_MAX_HEIGHT_VALUE
