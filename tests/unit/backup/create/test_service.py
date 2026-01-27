"""Unit tests for the backup service orchestration (create/service.py)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ami.scripts.backup.backup_exceptions import UploadError
from ami.scripts.backup.create.service import BackupOptions, BackupService


class TestBackupService:
    """Unit tests for the BackupService class."""

    def test_initialization(self):
        """Test that BackupService initializes with required services."""
        mock_uploader = MagicMock()
        mock_auth_manager = MagicMock()

        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        assert service.uploader == mock_uploader
        assert service.auth_manager == mock_auth_manager

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.BackupConfig")
    @patch("ami.scripts.backup.create.service.create_zip_archive")
    @patch("ami.scripts.backup.create.service.copy_to_secondary_backup")
    @patch("ami.scripts.backup.create.service.cleanup_local_zip")
    @patch("pathlib.Path.cwd")
    async def test_run_backup_success(
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

        # Mock secondary service and cleanup (they are awaited)
        mock_secondary.return_value = None
        mock_cleanup.return_value = None

        # Create service
        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        # Create options
        options = BackupOptions(keep_local=False, retry_auth=True)

        # Run backup
        result = await service.run_backup(options)

        # Verify result
        assert result == "test_file_id_123"

        # Verify all steps were called
        mock_archiver.assert_called_once()
        mock_uploader.upload_to_gdrive.assert_called_once()
        mock_secondary.assert_called_once()
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.BackupConfig")
    @patch("ami.scripts.backup.create.service.create_zip_archive")
    @patch("ami.scripts.backup.create.service.copy_to_secondary_backup")
    @patch("ami.scripts.backup.create.service.cleanup_local_zip")
    @patch("pathlib.Path.cwd")
    async def test_run_backup_auth_retry_success(
        self, mock_cwd, mock_cleanup, mock_secondary, mock_archiver, mock_config_class
    ):
        """Test backup with auth retry that succeeds."""
        # Setup mocks
        mock_uploader = AsyncMock()
        mock_auth_manager = MagicMock()

        mock_archiver.return_value = Path("/tmp/test/backup.tar.zst")
        mock_secondary.return_value = None
        mock_cleanup.return_value = None

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
        service._refresh_adc_credentials = AsyncMock(return_value=True)

        # Create options
        options = BackupOptions(keep_local=False, retry_auth=True)

        result = await service.run_backup(options)
        # Should succeed after retry
        assert result == "test_file_id_456"
        assert service._refresh_adc_credentials.called

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.BackupConfig")
    @patch("ami.scripts.backup.create.service.create_zip_archive")
    @patch("ami.scripts.backup.create.service.copy_to_secondary_backup")
    @patch("ami.scripts.backup.create.service.cleanup_local_zip")
    @patch("pathlib.Path.cwd")
    async def test_run_backup_upload_error_no_retry(
        self, mock_cwd, mock_cleanup, mock_secondary, mock_archiver, mock_config_class
    ):
        """Test backup with upload error when retry is disabled."""
        # Setup mocks
        mock_uploader = AsyncMock()
        mock_auth_manager = MagicMock()

        mock_archiver.return_value = Path("/tmp/test/backup.tar.zst")
        mock_secondary.return_value = None
        mock_cleanup.return_value = None

        mock_config = MagicMock()
        mock_config_class.load.return_value = mock_config
        mock_cwd.return_value = Path("/tmp/test")

        # Mock uploader to raise UploadError
        mock_uploader.upload_to_gdrive.side_effect = UploadError("Upload failed")

        service = BackupService(uploader=mock_uploader, auth_manager=mock_auth_manager)

        # Create options with retry_auth=False
        options = BackupOptions(keep_local=False, retry_auth=False)

        # Should raise UploadError when retry_auth=False
        with pytest.raises(UploadError):
            await service.run_backup(options)

    def test_is_auth_error_reauthentication(self):
        """Test _is_auth_error detects reauthentication errors."""
        service = BackupService(MagicMock(), MagicMock())
        error = UploadError("reauthentication required")

        assert service._is_auth_error(error) is True

    def test_is_auth_error_authenticated(self):
        """Test _is_auth_error detects authenticated errors."""
        service = BackupService(MagicMock(), MagicMock())
        error = UploadError("Not authenticated")

        assert service._is_auth_error(error) is True

    def test_is_auth_error_credentials(self):
        """Test _is_auth_error detects credentials errors."""
        service = BackupService(MagicMock(), MagicMock())
        error = UploadError("Invalid credentials")

        assert service._is_auth_error(error) is True

    def test_is_auth_error_invalid_grant(self):
        """Test _is_auth_error detects invalid_grant errors."""
        service = BackupService(MagicMock(), MagicMock())
        error = UploadError("Error: invalid_grant")

        assert service._is_auth_error(error) is True

    def test_is_auth_error_impersonated_credentials_not_auth_error(self):
        """Test _is_auth_error ignores impersonated credentials errors."""
        service = BackupService(MagicMock(), MagicMock())
        # impersonated credentials errors should not trigger retry
        error = UploadError("impersonated credentials failed")

        assert service._is_auth_error(error) is False

    def test_is_auth_error_other_error(self):
        """Test _is_auth_error returns False for other errors."""
        service = BackupService(MagicMock(), MagicMock())
        error = UploadError("Network timeout")

        assert service._is_auth_error(error) is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_setup_auth_no_gcloud(self, mock_find_gcloud):
        """Test setup_auth returns 1 when gcloud not found."""
        mock_find_gcloud.return_value = None

        service = BackupService(MagicMock(), MagicMock())
        result = await service.setup_auth()

        assert result == 1

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_setup_auth_success(self, mock_find_gcloud, mock_subprocess):
        """Test setup_auth succeeds when gcloud auth succeeds."""
        mock_find_gcloud.return_value = "/usr/bin/gcloud"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        result = await service.setup_auth()

        assert result == 0

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_setup_auth_failure(self, mock_find_gcloud, mock_subprocess):
        """Test setup_auth returns error code when gcloud auth fails."""
        mock_find_gcloud.return_value = "/usr/bin/gcloud"

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Auth failed")
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        result = await service.setup_auth()

        assert result == 1

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_setup_auth_exception(self, mock_find_gcloud, mock_subprocess):
        """Test setup_auth returns 1 on exception."""
        mock_find_gcloud.return_value = "/usr/bin/gcloud"
        mock_subprocess.side_effect = Exception("Unexpected error")

        service = BackupService(MagicMock(), MagicMock())
        result = await service.setup_auth()

        assert result == 1

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_refresh_adc_credentials_no_gcloud(self, mock_find_gcloud):
        """Test _refresh_adc_credentials returns False when no gcloud."""
        mock_find_gcloud.return_value = None

        service = BackupService(MagicMock(), MagicMock())
        result = await service._refresh_adc_credentials()

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.Path")
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_refresh_adc_credentials_no_adc_file(
        self, mock_find_gcloud, mock_path
    ):
        """Test _refresh_adc_credentials returns False when no ADC file."""
        mock_find_gcloud.return_value = "/usr/bin/gcloud"
        mock_path.home.return_value.__truediv__.return_value.exists.return_value = False

        service = BackupService(MagicMock(), MagicMock())
        result = await service._refresh_adc_credentials()

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.Path")
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_refresh_adc_credentials_timeout(self, mock_find_gcloud, mock_path):
        """Test _refresh_adc_credentials returns False on timeout."""
        mock_find_gcloud.return_value = "/usr/bin/gcloud"
        mock_path.home.return_value.__truediv__.return_value.exists.return_value = True

        service = BackupService(MagicMock(), MagicMock())
        service._check_and_refresh_token = AsyncMock(side_effect=TimeoutError())

        result = await service._refresh_adc_credentials()

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.Path")
    @patch("ami.scripts.backup.create.service.find_gcloud")
    async def test_refresh_adc_credentials_exception(self, mock_find_gcloud, mock_path):
        """Test _refresh_adc_credentials returns False on exception."""
        mock_find_gcloud.return_value = "/usr/bin/gcloud"
        mock_path.home.return_value.__truediv__.return_value.exists.return_value = True

        service = BackupService(MagicMock(), MagicMock())
        service._check_and_refresh_token = AsyncMock(side_effect=Exception("Error"))

        result = await service._refresh_adc_credentials()

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    async def test_check_and_refresh_token_valid(self, mock_subprocess):
        """Test _check_and_refresh_token returns True when token valid."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"token", b""))
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        result = await service._check_and_refresh_token("/usr/bin/gcloud")

        assert result is True

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.wait_for")
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    async def test_check_and_refresh_token_timeout(
        self, mock_subprocess, mock_wait_for
    ):
        """Test _check_and_refresh_token handles timeout."""
        mock_process = AsyncMock()
        mock_process.kill = MagicMock()
        mock_subprocess.return_value = mock_process
        mock_wait_for.side_effect = TimeoutError()

        service = BackupService(MagicMock(), MagicMock())

        with pytest.raises(TimeoutError):
            await service._check_and_refresh_token("/usr/bin/gcloud")

        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.wait_for")
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    async def test_check_and_refresh_token_invalid_then_refresh(
        self, mock_subprocess, mock_wait_for
    ):
        """Test _check_and_refresh_token refreshes invalid token."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_wait_for.return_value = (b"", b"Token expired")
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        service._run_gcloud_login = AsyncMock(return_value=True)

        result = await service._check_and_refresh_token("/usr/bin/gcloud")

        assert result is True
        service._run_gcloud_login.assert_called_once_with("/usr/bin/gcloud")

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.wait_for")
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    async def test_run_gcloud_login_success(self, mock_subprocess, mock_wait_for):
        """Test _run_gcloud_login returns True on success."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_wait_for.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        result = await service._run_gcloud_login("/usr/bin/gcloud")

        assert result is True

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.wait_for")
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    async def test_run_gcloud_login_failure(self, mock_subprocess, mock_wait_for):
        """Test _run_gcloud_login returns False on failure."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_wait_for.return_value = (b"", b"Login failed")
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        result = await service._run_gcloud_login("/usr/bin/gcloud")

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.create.service.asyncio.wait_for")
    @patch("ami.scripts.backup.create.service.asyncio.create_subprocess_exec")
    async def test_run_gcloud_login_timeout(self, mock_subprocess, mock_wait_for):
        """Test _run_gcloud_login returns False on timeout."""
        mock_process = AsyncMock()
        mock_process.kill = MagicMock()
        mock_wait_for.side_effect = TimeoutError()
        mock_subprocess.return_value = mock_process

        service = BackupService(MagicMock(), MagicMock())
        result = await service._run_gcloud_login("/usr/bin/gcloud")

        assert result is False
        mock_process.kill.assert_called_once()


class TestBackupOptions:
    """Tests for BackupOptions model."""

    def test_default_values(self):
        """Test BackupOptions has correct defaults."""
        options = BackupOptions()

        assert options.keep_local is False
        assert options.retry_auth is True
        assert options.source_dir is None
        assert options.output_filename is None
        assert options.ignore_exclusions is False
        assert options.config_path is None

    def test_custom_values(self):
        """Test BackupOptions accepts custom values."""
        options = BackupOptions(
            keep_local=True,
            retry_auth=False,
            source_dir=Path("/custom/source"),
            output_filename="custom-backup",
            ignore_exclusions=True,
            config_path=Path("/custom/config"),
        )

        assert options.keep_local is True
        assert options.retry_auth is False
        assert options.source_dir == Path("/custom/source")
        assert options.output_filename == "custom-backup"
        assert options.ignore_exclusions is True
        assert options.config_path == Path("/custom/config")
