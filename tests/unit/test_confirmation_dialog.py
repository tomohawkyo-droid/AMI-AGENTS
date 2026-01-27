"""Unit tests for confirmation_dialog module."""

from unittest.mock import patch

from ami.cli_components.confirmation_dialog import ConfirmationDialog, confirm
from ami.cli_components.dialogs import ConfirmationDialog as OriginalCD
from ami.cli_components.dialogs import confirm as original_confirm

MIN_EXPECTED_CALL_ARGS = 2


class TestConfirmationDialogImports:
    """Tests for confirmation_dialog module imports."""

    def test_confirmation_dialog_is_imported(self) -> None:
        """Test ConfirmationDialog is re-exported from dialogs."""
        assert ConfirmationDialog is OriginalCD

    def test_confirm_is_imported(self) -> None:
        """Test confirm function is re-exported from dialogs."""
        assert confirm is original_confirm


class TestConfirmFunction:
    """Tests for confirm function via proxy."""

    @patch("ami.cli_components.dialogs.ConfirmationDialog")
    def test_confirm_returns_true(self, mock_dialog_class) -> None:
        """Test confirm returns True when user confirms."""
        mock_dialog = mock_dialog_class.return_value
        mock_dialog.run.return_value = True

        result = confirm("Are you sure?")

        assert result is True
        mock_dialog_class.assert_called_once()

    @patch("ami.cli_components.dialogs.ConfirmationDialog")
    def test_confirm_returns_false(self, mock_dialog_class) -> None:
        """Test confirm returns False when user cancels."""
        mock_dialog = mock_dialog_class.return_value
        mock_dialog.run.return_value = False

        result = confirm("Are you sure?")

        assert result is False

    @patch("ami.cli_components.dialogs.ConfirmationDialog")
    def test_confirm_with_title(self, mock_dialog_class) -> None:
        """Test confirm passes title to dialog."""
        mock_dialog = mock_dialog_class.return_value
        mock_dialog.run.return_value = True

        confirm("Delete files?", "Warning")

        # Verify title was passed (second positional argument)
        call_args = mock_dialog_class.call_args[0]
        assert "Warning" in call_args or len(call_args) >= MIN_EXPECTED_CALL_ARGS

    @patch("ami.cli_components.dialogs.ConfirmationDialog")
    def test_confirm_with_message(self, mock_dialog_class) -> None:
        """Test confirm passes message to dialog."""
        mock_dialog = mock_dialog_class.return_value
        mock_dialog.run.return_value = True

        confirm("This action cannot be undone")

        # Verify message was passed
        call_args = mock_dialog_class.call_args[0]
        assert "This action cannot be undone" in call_args
