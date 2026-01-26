"""Unit tests for the backup service orchestration (create/service.py)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ami.scripts.backup.backup_exceptions import UploadError
from ami.scripts.backup.create.service import BackupService


class TestBackupService:
    """Unit tests for the BackupService class."""

    def test_initialization(self):
        """Test that BackupService initializes with required services."""
        mock_uploader = MagicMock()
        mock_auth_manager = MagicMock()

        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        assert service.uploader == mock_uploader
        assert service.auth_manager == mock_auth_manager

    @patch("scripts.backup.create.service.BackupConfig")
    @patch("scripts.backup.create.service.create_zip_archive")
    @patch("scripts.backup.create.service.copy_to_secondary_backup")
    @patch("scripts.backup.create.service.cleanup_local_zip")
    @patch("pathlib.Path.cwd")
    def test_run_backup_success(
        self, mock_cwd, mock_cleanup, mock_secondary, mock_archiver, mock_config_class
    ):
        """Test successful backup run."""
        # Setup mocks
        mock_uploader = AsyncMock()
        mock_auth_manager = MagicMock()

        # Mock the config loading
        mock_config = MagicMock()
        mock_config_class.load.return_value = mock_config

        mock_cwd.return_value = Path("/tmp/test")

        # Mock archiver to return a zip path
        mock_archiver.return_value = Path("/tmp/test/backup.tar.zst")

        # Mock uploader to return a file ID
        mock_uploader.upload_to_gdrive.return_value = "test_file_id_123"

        # Mock secondary service and cleanup
        mock_secondary.return_value = True
        mock_cleanup.return_value = True

        # Create service
        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        # Run backup
        result = asyncio.run(service.run_backup(keep_local=False, retry_auth=True))

        # Verify result
        assert result == "test_file_id_123"

        # Verify all steps were called
        mock_archiver.assert_called_once()
        mock_uploader.upload_to_gdrive.assert_called_once()
        mock_secondary.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("scripts.backup.create.service.BackupConfig")
    @patch("scripts.backup.create.service.create_zip_archive")
    @patch("scripts.backup.create.service.copy_to_secondary_backup")
    @patch("scripts.backup.create.service.cleanup_local_zip")
    @patch("pathlib.Path.cwd")
    def test_run_backup_auth_retry_success(
        self, mock_cwd, mock_cleanup, mock_secondary, mock_archiver, mock_config_class
    ):
        """Test backup with auth retry that succeeds."""
        # Setup mocks
        mock_uploader = AsyncMock()
        mock_auth_manager = MagicMock()

        mock_archiver.return_value = Path("/tmp/test/backup.tar.zst")
        mock_secondary.return_value = True
        mock_cleanup.return_value = True

        # Mock the config loading
        mock_config = MagicMock()
        mock_config_class.load.return_value = mock_config

        mock_cwd.return_value = Path("/tmp/test")

        # First call raises UploadError, second succeeds
        mock_uploader.upload_to_gdrive.side_effect = [
            UploadError("Authentication required: reauthentication needed"),
            "test_file_id_456",
        ]

        # Create service
        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        # Mock _refresh_adc_credentials to return True
        with patch.object(
            service,
            "_refresh_adc_credentials",
            return_value=AsyncMock(return_value=True),
        ) as mock_refresh:
            # We need to make mock_refresh an awaitable that returns True
            mock_refresh.return_value = True

            # Since _refresh_adc_credentials is async, we mock it as such
            service._refresh_adc_credentials = AsyncMock(return_value=True)

            result = asyncio.run(service.run_backup(keep_local=False, retry_auth=True))
            # Should succeed after retry
            assert result == "test_file_id_456"
            assert service._refresh_adc_credentials.called

    @patch("scripts.backup.create.service.BackupConfig")
    @patch("scripts.backup.create.service.create_zip_archive")
    @patch("scripts.backup.create.service.copy_to_secondary_backup")
    @patch("scripts.backup.create.service.cleanup_local_zip")
    @patch("pathlib.Path.cwd")
    def test_run_backup_upload_error_no_retry(
        self, mock_cwd, mock_cleanup, mock_secondary, mock_archiver, mock_config_class
    ):
        """Test backup with upload error when retry is disabled."""
        # Setup mocks
        mock_uploader = AsyncMock()
        mock_auth_manager = MagicMock()

        mock_archiver.return_value = Path("/tmp/test/backup.tar.zst")
        mock_secondary.return_value = True
        mock_cleanup.return_value = True

        mock_config = MagicMock()
        mock_config_class.load.return_value = mock_config
        mock_cwd.return_value = Path("/tmp/test")

        # Mock uploader to raise UploadError
        mock_uploader.upload_to_gdrive.side_effect = UploadError("Upload failed")

        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        # Should raise UploadError when retry_auth=False
        with pytest.raises(UploadError):
            asyncio.run(service.run_backup(keep_local=False, retry_auth=False))
