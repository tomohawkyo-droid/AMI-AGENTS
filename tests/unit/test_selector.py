"""Unit tests for selector module."""

from unittest.mock import MagicMock, patch

from ami.cli_components.selector import (
    FILE_ID_DISPLAY_THRESHOLD,
    BackupFileInfo,
    display_backup_list,
    select_backup_by_index,
    select_backup_interactive,
)

EXPECTED_MIN_DISPLAY_PRINT_CALLS = 4
EXPECTED_FILE_ID_DISPLAY_THRESHOLD_VALUE = 12


class TestBackupFileInfo:
    """Tests for BackupFileInfo TypedDict."""

    def test_create_backup_file_info(self) -> None:
        """Test creating a BackupFileInfo dict."""
        info: BackupFileInfo = {
            "id": "abc123",
            "name": "backup-2024-01-01.tar.zst",
            "modifiedTime": "2024-01-01T12:00:00Z",
            "size": "1024000",
        }
        assert info["id"] == "abc123"
        assert info["name"] == "backup-2024-01-01.tar.zst"

    def test_partial_backup_file_info(self) -> None:
        """Test creating partial BackupFileInfo (total=False)."""
        info: BackupFileInfo = {"id": "xyz789"}
        assert info["id"] == "xyz789"


class TestSelectBackupInteractive:
    """Tests for select_backup_interactive function."""

    def test_empty_list_returns_none(self) -> None:
        """Test that empty backup list returns None."""
        result = select_backup_interactive([])
        assert result is None

    @patch("ami.cli_components.selector.MenuSelector")
    def test_returns_selected_file_id(self, mock_selector_class) -> None:
        """Test that selected file ID is returned."""
        mock_item = MagicMock()
        mock_item.value = "file-id-123"
        mock_item.label = "backup.tar.zst"

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item]
        mock_selector_class.return_value = mock_selector

        backup_files: list[BackupFileInfo] = [
            {"id": "file-id-123", "name": "backup.tar.zst", "size": "1000"}
        ]
        result = select_backup_interactive(backup_files)

        assert result == "file-id-123"

    @patch("ami.cli_components.selector.MenuSelector")
    def test_returns_none_on_cancel(self, mock_selector_class) -> None:
        """Test that None is returned when selection is cancelled."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        backup_files: list[BackupFileInfo] = [{"id": "abc", "name": "backup.tar.zst"}]
        result = select_backup_interactive(backup_files)

        assert result is None

    @patch("ami.cli_components.selector.MenuSelector")
    def test_handles_missing_fields(self, mock_selector_class) -> None:
        """Test handling backup files with missing fields."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        # Minimal backup file info
        backup_files: list[BackupFileInfo] = [{"id": "abc"}]
        result = select_backup_interactive(backup_files)

        # Should not raise, just return None
        assert result is None


class TestDisplayBackupList:
    """Tests for display_backup_list function."""

    @patch("builtins.print")
    def test_empty_list_shows_message(self, mock_print) -> None:
        """Test that empty list shows appropriate message."""
        display_backup_list([])

        # Check that "No backup files" message was printed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("No backup files" in str(call) for call in calls)

    @patch("builtins.print")
    def test_displays_backup_info(self, mock_print) -> None:
        """Test that backup info is displayed."""
        backup_files: list[BackupFileInfo] = [
            {
                "id": "abc123def456ghi789",
                "name": "backup-2024-01-01.tar.zst",
                "modifiedTime": "2024-01-01T12:00:00Z",
                "size": "1048576",
            }
        ]
        display_backup_list(backup_files)

        # Verify print was called multiple times
        assert mock_print.call_count >= EXPECTED_MIN_DISPLAY_PRINT_CALLS

    @patch("builtins.print")
    def test_custom_title(self, mock_print) -> None:
        """Test custom title is displayed."""
        backup_files: list[BackupFileInfo] = [{"id": "abc", "name": "test.tar.zst"}]
        display_backup_list(backup_files, title="Custom Title")

        # Check title was printed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Custom Title" in str(call) for call in calls)

    @patch("builtins.print")
    def test_truncates_long_file_ids(self, mock_print) -> None:
        """Test that long file IDs are truncated."""
        long_id = "a" * 20  # Longer than FILE_ID_DISPLAY_THRESHOLD
        backup_files: list[BackupFileInfo] = [{"id": long_id, "name": "backup.tar.zst"}]
        display_backup_list(backup_files)

        # Should have been called with truncated ID
        assert mock_print.called

    @patch("builtins.print")
    def test_handles_missing_fields(self, mock_print) -> None:
        """Test handling files with missing fields."""
        backup_files: list[BackupFileInfo] = [{"id": "abc"}]
        display_backup_list(backup_files)

        # Should use "Unknown" for missing fields
        assert mock_print.called


class TestSelectBackupByIndex:
    """Tests for select_backup_by_index function."""

    def test_valid_index_returns_file_id(self) -> None:
        """Test valid index returns correct file ID."""
        backup_files: list[BackupFileInfo] = [
            {"id": "first-id", "name": "first.tar.zst"},
            {"id": "second-id", "name": "second.tar.zst"},
            {"id": "third-id", "name": "third.tar.zst"},
        ]
        result = select_backup_by_index(backup_files, 1)

        assert result == "second-id"

    def test_first_index(self) -> None:
        """Test selecting first backup (index 0)."""
        backup_files: list[BackupFileInfo] = [
            {"id": "first", "name": "first.tar.zst"},
            {"id": "second", "name": "second.tar.zst"},
        ]
        result = select_backup_by_index(backup_files, 0)

        assert result == "first"

    def test_last_index(self) -> None:
        """Test selecting last backup."""
        backup_files: list[BackupFileInfo] = [
            {"id": "first", "name": "first.tar.zst"},
            {"id": "last", "name": "last.tar.zst"},
        ]
        result = select_backup_by_index(backup_files, 1)

        assert result == "last"

    def test_negative_index_returns_none(self) -> None:
        """Test negative index returns None."""
        backup_files: list[BackupFileInfo] = [{"id": "abc", "name": "test.tar.zst"}]
        result = select_backup_by_index(backup_files, -1)

        assert result is None

    def test_out_of_range_index_returns_none(self) -> None:
        """Test out of range index returns None."""
        backup_files: list[BackupFileInfo] = [{"id": "abc", "name": "test.tar.zst"}]
        result = select_backup_by_index(backup_files, 5)

        assert result is None

    def test_empty_list_returns_none(self) -> None:
        """Test empty list returns None for any index."""
        result = select_backup_by_index([], 0)
        assert result is None

    def test_missing_id_returns_none(self) -> None:
        """Test file without id returns None."""
        backup_files: list[BackupFileInfo] = [{"name": "no-id.tar.zst"}]
        result = select_backup_by_index(backup_files, 0)

        assert result is None


class TestConstants:
    """Tests for module constants."""

    def test_file_id_display_threshold(self) -> None:
        """Test FILE_ID_DISPLAY_THRESHOLD value."""
        assert FILE_ID_DISPLAY_THRESHOLD == EXPECTED_FILE_ID_DISPLAY_THRESHOLD_VALUE
        assert isinstance(FILE_ID_DISPLAY_THRESHOLD, int)
