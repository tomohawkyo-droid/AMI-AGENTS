"""Unit tests for the backup utils module (create/utils.py)."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.scripts.backup.create import utils


class TestBackupUtils:
    """Unit tests for the backup utils functions."""

    @patch.object(Path, "exists")
    def test_cleanup_local_zip_already_cleaned_up(self, mock_exists):
        """Test cleanup when zip file already doesn't exist."""
        mock_exists.return_value = False  # File doesn't exist

        zip_path = Path("/tmp/test.zip")
        result = asyncio.run(utils.cleanup_local_zip(zip_path, keep_local=False))

        assert result is True  # Should return True (no cleanup needed)

    @patch.object(Path, "exists")
    @patch.object(Path, "unlink")
    def test_cleanup_local_zip_keep_local(self, mock_unlink, mock_exists):
        """Test cleanup when keep_local is True."""
        mock_exists.return_value = True  # File exists

        zip_path = Path("/tmp/test.zip")
        result = asyncio.run(utils.cleanup_local_zip(zip_path, keep_local=True))

        assert result is True  # Should return True (kept the file)
        mock_unlink.assert_not_called()  # Should not have deleted the file

    @patch.object(Path, "exists")
    @patch.object(Path, "unlink")
    def test_cleanup_local_zip_delete_success(self, mock_unlink, mock_exists):
        """Test successful deletion of local zip."""
        mock_exists.return_value = True  # File exists
        mock_unlink.return_value = None  # No error on delete

        zip_path = Path("/tmp/test.zip")
        result = asyncio.run(utils.cleanup_local_zip(zip_path, keep_local=False))

        assert result is True  # Should return True (deleted successfully)
        mock_unlink.assert_called_once()

    @patch.object(Path, "exists")
    @patch.object(Path, "unlink", side_effect=Exception("Permission denied"))
    def test_cleanup_local_zip_delete_failure(self, mock_unlink, mock_exists):
        """Test cleanup when deletion fails."""
        mock_exists.return_value = True  # File exists

        zip_path = Path("/tmp/test.zip")
        result = asyncio.run(utils.cleanup_local_zip(zip_path, keep_local=False))

        assert result is False  # Should return False (deletion failed)

    @patch.object(Path, "iterdir")
    def test_cleanup_old_backups(self, mock_iterdir):
        """Test cleaning up old backups keeping most recent ones."""
        # Create mock files with proper stat() mock
        mock_file1 = MagicMock(spec=Path)
        mock_file1.name = "backup_20230101.tar.zst"
        mock_file1.suffixes = [".tar", ".zst"]
        mock_file1.is_file.return_value = True  # Mock is_file for the Path object

        # Create mock stat objects with mtime attributes
        mock_stat1 = MagicMock()
        mock_stat1.st_mtime = 1  # Oldest

        # Mock the stat method to return the stat object
        mock_file1.stat.return_value = mock_stat1

        mock_file2 = MagicMock(spec=Path)
        mock_file2.name = "backup_20230102.tar.zst"
        mock_file2.suffixes = [".tar", ".zst"]
        mock_file2.is_file.return_value = True

        mock_stat2 = MagicMock()
        mock_stat2.st_mtime = 3  # Newest
        mock_file2.stat.return_value = mock_stat2

        mock_file3 = MagicMock(spec=Path)
        mock_file3.name = "backup_20230103.tar.zst"
        mock_file3.suffixes = [".tar", ".zst"]
        mock_file3.is_file.return_value = True

        mock_stat3 = MagicMock()
        mock_stat3.st_mtime = 2  # Middle
        mock_file3.stat.return_value = mock_stat3

        mock_iterdir.return_value = [mock_file1, mock_file2, mock_file3]

        # Mock the unlink method for the files to be deleted
        with (
            patch.object(mock_file1, "unlink", return_value=None),
            patch.object(mock_file2, "unlink", return_value=None),
            patch.object(mock_file3, "unlink", return_value=None),
        ):
            directory = Path("/tmp/backups")
            result = asyncio.run(utils.cleanup_old_backups(directory, keep_count=1))

            assert result is True
            # When keeping 1 file, the 2 oldest should be deleted
            mock_file1.unlink.assert_called_once()  # Oldest (mtime=1)
            mock_file3.unlink.assert_called_once()  # Middle (mtime=2)
            mock_file2.unlink.assert_not_called()  # Newest (mtime=3)

    @patch.object(Path, "exists")
    @patch("subprocess.run")
    def test_validate_backup_file_success(self, mock_subprocess_run, mock_exists):
        """Test backup file validation succeeds for valid file."""
        mock_exists.return_value = True  # File exists

        # Mock successful subprocess calls
        zstd_test_result = MagicMock()
        zstd_test_result.returncode = 0
        zstd_decomp_result = MagicMock()
        zstd_decomp_result.returncode = 0
        zstd_decomp_result.stdout = b"mock tar data"
        tar_test_result = MagicMock()
        tar_test_result.returncode = 0

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            if isinstance(cmd, list) and "zstd" in cmd and "--test" in cmd:
                return zstd_test_result
            elif isinstance(cmd, list) and "zstd" in cmd and "-d" in cmd:
                return zstd_decomp_result
            elif isinstance(cmd, list) and "tar" in cmd and "-t" in cmd:
                return tar_test_result
            return MagicMock()  # Default return

        mock_subprocess_run.side_effect = subprocess_side_effect

        zip_path = Path("/tmp/backup.tar.zst")
        result = asyncio.run(utils.validate_backup_file(zip_path))

        assert result is True

    @patch.object(Path, "exists")
    def test_validate_backup_file_not_exists(self, mock_exists):
        """Test backup file validation fails for non-existent file."""
        mock_exists.return_value = False  # File doesn't exist

        zip_path = Path("/tmp/backup.tar.zst")
        result = asyncio.run(utils.validate_backup_file(zip_path))

        assert result is False
