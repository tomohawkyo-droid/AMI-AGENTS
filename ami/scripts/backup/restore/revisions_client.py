"""
Google Drive Revisions API client for restore operations.

Fetches version history and downloads specific revisions of backup files.
"""

import asyncio
from pathlib import Path
from typing import Any, Protocol, cast

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from loguru import logger

from ami.scripts.backup.common.auth import AuthenticationManager
from ami.types.common import DriveRevisionInfo, DriveRevisionListResponse

DOWNLOAD_PROGRESS_MULTIPLIER = 100


class DriveRevisionRequest(Protocol):
    """Protocol for Google Drive revision request objects."""

    def execute(self) -> DriveRevisionListResponse:
        """Execute the request."""
        ...


class DriveRevisionsResource(Protocol):
    """Protocol for Google Drive revisions() resource."""

    def list(self, **kwargs: object) -> DriveRevisionRequest:
        """List revisions."""
        ...

    def get_media(self, **kwargs: object) -> Any:
        """Get revision media content for download."""
        ...


class DriveFilesResource(Protocol):
    """Protocol for Google Drive files() resource."""

    def get_media(self, **kwargs: object) -> Any:
        """Get file media content."""
        ...


class DriveServiceWithRevisions(Protocol):
    """Protocol for Google Drive service with revisions support."""

    def revisions(self) -> DriveRevisionsResource:
        """Get revisions resource."""
        ...

    def files(self) -> DriveFilesResource:
        """Get files resource."""
        ...


class RevisionsClient:
    """Client for Google Drive Revisions API operations."""

    def __init__(self, auth_manager: AuthenticationManager) -> None:
        self.auth_manager = auth_manager
        self._service: DriveServiceWithRevisions | None = None

    async def _get_service(self) -> DriveServiceWithRevisions:
        """Get or create the Google Drive service client."""
        if self._service is None:
            credentials = self.auth_manager.get_credentials()
            self._service = cast(
                DriveServiceWithRevisions,
                build("drive", "v3", credentials=credentials),
            )
        return self._service

    async def list_revisions(self, file_id: str) -> list[DriveRevisionInfo]:
        """List all revisions for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            List of revision metadata, newest first
        """
        try:
            service = await self._get_service()
            fields = "revisions(id,modifiedTime,size,originalFilename,keepForever)"
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: (
                    service.revisions().list(fileId=file_id, fields=fields).execute()
                ),
            )

            raw_revisions = results.get("revisions")
            if not raw_revisions or not isinstance(raw_revisions, list):
                logger.warning("No revisions found for file")
                return []

            revisions: list[DriveRevisionInfo] = [
                DriveRevisionInfo(
                    id=str(item.get("id", "")),
                    modifiedTime=str(item.get("modifiedTime", "")),
                    size=str(item.get("size", "")),
                    originalFilename=str(item.get("originalFilename", "")),
                    keepForever=bool(item.get("keepForever", False)),
                )
                for item in raw_revisions
                if isinstance(item, dict)
            ]
            # Return newest first
            revisions.reverse()

        except Exception as e:
            logger.error(f"Failed to list revisions: {e}")
            return []
        else:
            return revisions

    async def download_revision(
        self, file_id: str, revision_id: str, destination: Path
    ) -> bool:
        """Download a specific revision of a file.

        Args:
            file_id: Google Drive file ID
            revision_id: Revision ID to download
            destination: Local path to save the file

        Returns:
            True if download was successful
        """
        try:
            service = await self._get_service()
            destination.parent.mkdir(parents=True, exist_ok=True)

            request = service.revisions().get_media(
                fileId=file_id, revisionId=revision_id
            )

            def _do_download() -> bool:
                with open(destination, "wb") as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()
                        if status:
                            pct = int(status.progress() * DOWNLOAD_PROGRESS_MULTIPLIER)
                            logger.info(f"Download {pct}%.")
                return True

            result = await asyncio.get_event_loop().run_in_executor(None, _do_download)
            logger.info(f"Revision download completed: {destination}")

        except Exception as e:
            logger.error(f"Revision download failed: {e}")
            return False
        else:
            return result
