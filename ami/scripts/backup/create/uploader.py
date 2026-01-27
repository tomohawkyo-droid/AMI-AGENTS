"""
Backup uploader module.

Handles uploading archives to Google Drive using configured authentication.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from loguru import logger

from ami.scripts.backup.backup_config import BackupConfig
from ami.scripts.backup.backup_exceptions import UploadError

if TYPE_CHECKING:
    from ami.scripts.backup.common.auth import AuthenticationManager


class DriveFilesResource(Protocol):
    """Protocol for Google Drive files() resource."""

    def list(self, **kwargs: object) -> "DriveRequest":
        """List files."""
        ...

    def create(self, **kwargs: object) -> "DriveRequest":
        """Create file."""
        ...

    def update(self, **kwargs: object) -> "DriveRequest":
        """Update file."""
        ...


class DriveRequest(Protocol):
    """Protocol for Google Drive request objects."""

    def execute(self) -> dict[str, object]:
        """Execute the request."""
        ...


class DriveService(Protocol):
    """Protocol for Google Drive service."""

    def files(self) -> DriveFilesResource:
        """Get files resource."""
        ...


class BackupUploader:
    """Uploads backup archives to Google Drive."""

    def __init__(self, auth_manager: "AuthenticationManager") -> None:
        self.auth_manager = auth_manager
        self._service: DriveService | None = None

    async def _get_service(self) -> DriveService:
        """Get or create the Google Drive service client."""
        if self._service is None:
            credentials = self.auth_manager.get_credentials()
            self._service = cast(
                DriveService, build("drive", "v3", credentials=credentials)
            )
        return self._service

    async def _search_existing_file(
        self, service: DriveService, search_query: str
    ) -> str | None:
        """Search for an existing file and return its ID if found."""
        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.files()
                .list(
                    q=search_query,
                    spaces="drive",
                    fields="files(id, name)",
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                )
                .execute(),
            )

            files = results.get("files")
            if isinstance(files, list) and files and isinstance(files[0], dict):
                file_id_val = files[0].get("id")
                if isinstance(file_id_val, str):
                    return file_id_val
        except Exception as e:
            logger.warning(f"File search failed, proceeding with upload: {e}")
        return None

    async def upload_to_gdrive(self, zip_path: Path, config: BackupConfig) -> str:
        """
        Upload archive file to Google Drive using configured authentication.

        Args:
            zip_path: Path to archive file to upload
            config: Backup configuration with auth method

        Returns:
            Google Drive file ID

        Raises:
            UploadError: If upload fails
        """
        logger.info("Uploading to Google Drive...")

        try:
            service = await self._get_service()

            # Build search query for existing files
            search_query = f"name = '{zip_path.name}' and trashed = false"
            if config.folder_id:
                search_query += f" and '{config.folder_id}' in parents"

            # Build file metadata for new uploads
            file_metadata: dict[str, str | list[str]] = {"name": zip_path.name}
            if config.folder_id:
                file_metadata["parents"] = [config.folder_id]

            existing_file_id = await self._search_existing_file(service, search_query)

            # Upload with resumable flag for large files
            media = MediaFileUpload(
                str(zip_path),
                mimetype="application/zstd",
                resumable=True,
            )

            if existing_file_id:
                file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.files()
                    .update(
                        fileId=existing_file_id,
                        media_body=media,
                        fields="id,name,webViewLink",
                        supportsAllDrives=True,
                    )
                    .execute(),
                )
            else:
                file = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.files()
                    .create(
                        body=file_metadata,
                        media_body=media,
                        fields="id,name,webViewLink",
                        supportsAllDrives=True,
                    )
                    .execute(),
                )

        except Exception as e:
            msg = f"Upload failed: {e}"
            raise UploadError(msg) from e

        raw_file_id = file.get("id")
        if not raw_file_id or not isinstance(raw_file_id, str):
            msg = "Upload succeeded but no file ID returned"
            raise UploadError(msg)
        file_id: str = raw_file_id

        # Log success
        logger.info("✓ Upload complete")
        logger.info(f"  File ID: {file_id}")
        if file.get("name"):
            logger.info(f"  Name: {file.get('name')}")
        if file.get("webViewLink"):
            logger.info(f"  Link: {file.get('webViewLink')}")

        return file_id
