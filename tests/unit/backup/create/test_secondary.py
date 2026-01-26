"""Unit tests for the secondary backup module (create/secondary.py)."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from ami.scripts.backup.create import secondary


class TestSecondaryBackup:
    """Unit tests for the secondary backup functions."""

    @patch("ami.scripts.backup.create.secondary._get_secondary_locations")
    @patch("ami.scripts.backup.create.secondary._is_backup_location_available")
    @patch("shutil.copy2")
    @patch.object(Path, "exists")
    def test_copy_to_secondary_backup_success(
        self, mock_exists, mock_copy, mock_available, mock_locations
    ):
        """Test successful copy to secondary location."""
        mock_exists.return_value = True  # Source file exists

        # Mock locations and availability
        location = Path("/Volumes/AMI-BACKUP")
        mock_locations.return_value = [location]
        mock_available.return_value = True

        zip_path = Path("/tmp/backup.tar.zst")
        result = asyncio.run(secondary.copy_to_secondary_backup(zip_path))

        assert result is True
        mock_copy.assert_called_once_with(str(zip_path), str(location / zip_path.name))

    @patch("ami.scripts.backup.create.secondary._get_secondary_locations")
    @patch("ami.scripts.backup.create.secondary._is_backup_location_available")
    @patch.object(Path, "exists")
    def test_copy_to_secondary_backup_no_locations(
        self, mock_exists, mock_available, mock_locations
    ):
        """Test behavior when no secondary locations are available."""
        mock_exists.return_value = True
        mock_locations.return_value = [Path("/non/existent")]
        mock_available.return_value = False

        zip_path = Path("/tmp/backup.tar.zst")
        result = asyncio.run(secondary.copy_to_secondary_backup(zip_path))

        assert result is False

    @patch("os.getenv")
    @patch.object(Path, "exists")
    def test_get_secondary_locations(self, mock_exists, mock_getenv):
        """Test location discovery via env var and defaults."""
        mock_getenv.return_value = "/mnt/ext-backup"
        mock_exists.side_effect = lambda: True  # Pretend /media/backup exists

        # We need to mock Path("/media/backup").exists() specifically
        with patch.object(Path, "exists", return_value=True):
            locations = secondary._get_secondary_locations()

            assert Path("/mnt/ext-backup") in locations
            assert Path("/media/backup") in locations

    @patch.object(Path, "exists")
    @patch.object(Path, "is_dir")
    @patch.object(Path, "touch")
    @patch.object(Path, "unlink")
    def test_is_backup_location_available_success(
        self, mock_unlink, mock_touch, mock_is_dir, mock_exists
    ):
        """Test availability check for a valid location."""
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        mock_touch.return_value = None
        mock_unlink.return_value = None

        location = Path("/valid/backup")
        result = asyncio.run(secondary._is_backup_location_available(location))

        assert result is True
        mock_touch.assert_called_once()
