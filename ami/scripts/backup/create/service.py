"""
Backup service module.

Main business logic for backup operations.
"""

import asyncio
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from ami.scripts.backup.backup_config import BackupConfig
from ami.scripts.backup.backup_exceptions import UploadError
from ami.scripts.backup.common.auth import AuthenticationManager
from ami.scripts.backup.common.constants import DEFAULT_BACKUP_NAME
from ami.scripts.backup.common.paths import find_gcloud
from ami.scripts.backup.create.archiver import create_zip_archive
from ami.scripts.backup.create.secondary import copy_to_secondary_backup
from ami.scripts.backup.create.uploader import BackupUploader
from ami.scripts.backup.create.utils import cleanup_local_zip


class BackupOptions(BaseModel):
    """Options for backup operations."""

    keep_local: bool = False
    retry_auth: bool = True
    source_dir: Path | None = None
    output_filename: str | None = None
    ignore_exclusions: bool = False
    config_path: Path | None = None


class BackupService:
    """Main service for backup operations."""

    def __init__(self, uploader: BackupUploader, auth_manager: AuthenticationManager):
        self.uploader = uploader
        self.auth_manager = auth_manager

    async def run_backup(self, options: BackupOptions) -> str:
        """
        Run the backup process.

        Args:
            options: BackupOptions containing all backup configuration.

        Returns:
            Google Drive file ID

        Raises:
            BackupError: If any step fails
        """
        # Determine paths
        source_dir = (
            Path.cwd() if options.source_dir is None else options.source_dir.resolve()
        )
        config_path = (
            Path.cwd() if options.config_path is None else options.config_path.resolve()
        )

        # Load configuration
        config = BackupConfig.load(config_path)

        # Update auth manager with new config
        self.auth_manager.update_config(config)

        # Create zip archive from source_dir
        # Use CWD as output directory for the zip file to avoid polluting source or permission issues
        output_dir = Path.cwd()

        # Use default backup name if not specified
        backup_name = options.output_filename or DEFAULT_BACKUP_NAME

        zip_path = await create_zip_archive(
            source_dir,
            backup_name,
            options.ignore_exclusions,
            output_dir=output_dir,
        )

        # Upload to Google Drive
        try:
            file_id = await self.uploader.upload_to_gdrive(zip_path, config)
        except UploadError as e:
            file_id = await self._handle_upload_error(
                e, zip_path, config, options.retry_auth
            )

        # Copy to secondary backup location if AMI-BACKUP drives are mounted
        await copy_to_secondary_backup(zip_path)

        # Cleanup
        await cleanup_local_zip(zip_path, options.keep_local)

        return file_id

    def _is_auth_error(self, error: UploadError) -> bool:
        """Check if an upload error is authentication-related."""
        error_str = str(error).lower()
        return (
            "reauthentication" in error_str
            or "authenticated" in error_str
            or ("credentials" in error_str and "impersonated" not in error_str)
            or "invalid_grant" in error_str
        )

    async def _handle_upload_error(
        self, error: UploadError, zip_path: Path, config: BackupConfig, retry_auth: bool
    ) -> str:
        """Handle upload error with potential credential refresh."""
        if not (retry_auth and self._is_auth_error(error)):
            raise error

        logger.warning(f"Authentication error detected: {error}")
        logger.info("Attempting to refresh credentials...")

        if not await self._refresh_adc_credentials():
            logger.error("Failed to refresh credentials.")
            raise error

        logger.info("Credentials refreshed successfully, retrying upload...")
        return await self.uploader.upload_to_gdrive(zip_path, config)

    async def setup_auth(self) -> int:
        """
        Set up Google Cloud authentication using local gcloud binary.

        Returns:
            Exit code from the gcloud auth command
        """
        logger.info("Setting up Google Cloud authentication...")

        gcloud_path = find_gcloud()
        if not gcloud_path:
            logger.error(
                "gcloud CLI not found! Please install with the appropriate script"
            )
            return 1

        logger.info(f"Using gcloud binary: {gcloud_path}")
        logger.info(
            "Please follow the instructions in your browser to complete authentication..."
        )

        try:
            # Run the gcloud auth command
            process = await asyncio.create_subprocess_exec(
                str(gcloud_path),
                "auth",
                "application-default",
                "login",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("✓ Authentication setup completed successfully!")
                logger.info("You can now run the backup script.")
                return 0
            else:
                logger.error(
                    f"Authentication setup failed with return code: {process.returncode}"
                )
                if stderr:
                    logger.error(f"Error output: {stderr.decode()}")
                return process.returncode or 1
        except Exception as e:
            logger.error(f"Unexpected error during authentication setup: {e}")
            return 1

    async def _refresh_adc_credentials(self) -> bool:
        """Attempt to refresh Application Default Credentials using gcloud."""
        gcloud_path = find_gcloud()
        if not gcloud_path:
            logger.error("gcloud CLI not found! Cannot refresh credentials.")
            return False

        adc_path = Path.home() / ".config/gcloud/application_default_credentials.json"
        if not adc_path.exists():
            logger.warning(
                "Application Default Credentials file not found, need to set up auth first."
            )
            return False

        try:
            return await self._check_and_refresh_token(gcloud_path)
        except TimeoutError:
            logger.error("Timeout while checking credentials with gcloud.")
            return False
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            return False

    async def _check_and_refresh_token(self, gcloud_path: str) -> bool:
        """Check token status and refresh if needed."""
        process = await asyncio.create_subprocess_exec(
            gcloud_path,
            "auth",
            "application-default",
            "print-access-token",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        except TimeoutError:
            process.kill()
            raise TimeoutError("gcloud auth timed out") from None

        if process.returncode == 0:
            logger.info("Access token is still valid.")
            return True

        logger.info("Current access token is invalid or expired, attempting refresh...")
        logger.debug(f"gcloud error output: {stderr.decode()}")
        return await self._run_gcloud_login(gcloud_path)

    async def _run_gcloud_login(self, gcloud_path: str) -> bool:
        """Run gcloud login to refresh credentials."""
        refresh_process = await asyncio.create_subprocess_exec(
            gcloud_path,
            "auth",
            "application-default",
            "login",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _stdout_refresh, stderr_refresh = await asyncio.wait_for(
                refresh_process.communicate(), timeout=30
            )
        except TimeoutError:
            refresh_process.kill()
            logger.error("gcloud login timed out")
            return False

        if refresh_process.returncode == 0:
            logger.info("Credentials successfully refreshed.")
            return True

        logger.error(f"Failed to refresh credentials: {stderr_refresh.decode()}")
        return False
