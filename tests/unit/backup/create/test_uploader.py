"""Unit tests for the backup uploader module (create/uploader.py)."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.scripts.backup.backup_exceptions import UploadError
from ami.scripts.backup.create.uploader import BackupUploader


class TestBackupUploader:
    """Unit tests for the BackupUploader class."""

    def test_initialization(self):
        """Test that BackupUploader initializes correctly with auth_manager."""
        mock_auth_manager = MagicMock()
        uploader = BackupUploader(mock_auth_manager)

        assert uploader.auth_manager == mock_auth_manager
        assert uploader._service is None

    @patch("googleapiclient.discovery.build")
    def test_get_service_creates_google_service(self, mock_build):
        """Test that _get_service creates the Google Drive service."""
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        uploader = BackupUploader(mock_auth_manager)

        # Call the async method using asyncio.run
        service = asyncio.run(uploader._get_service())

        assert service == mock_service
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_credentials)
        # Verify it's cached
        assert uploader._service == mock_service

    @patch("scripts.backup.create.uploader.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_upload_to_gdrive_new_file(self, mock_build, mock_loop):
        """Test uploading a file that doesn't already exist."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_drive_files = MagicMock()
        mock_list_request = MagicMock()
        mock_service.files.return_value = mock_drive_files
        mock_drive_files.list.return_value = mock_list_request
        mock_list_request.execute.return_value = {"files": []}  # No existing files

        # Setup create response
        mock_create_request = MagicMock()
        mock_drive_files.create.return_value = mock_create_request
        mock_create_request.execute.return_value = {
            "id": "test_file_id_123",
            "name": "test-archive.tar.zst",
            "webViewLink": "https://drive.google.com/file/d/test_file_id_123/view",
        }

        mock_build.return_value = mock_service

        # Mock the event loop's run_in_executor to return an awaitable
        loop_instance = MagicMock()

        async def run_in_executor_side_effect(*args, **kwargs):
            if args and callable(args[-1]):
                return args[-1]()
            else:
                func = args[-1]
                return func()

        loop_instance.run_in_executor.side_effect = (
            lambda *args, **kwargs: asyncio.ensure_future(
                run_in_executor_side_effect(*args, **kwargs)
            )
        )
        mock_loop.return_value = loop_instance

        # Create uploader and config
        uploader = BackupUploader(mock_auth_manager)
        config = MagicMock()
        config.auth_method = "oauth"
        config.folder_id = "test_folder_id"
        zip_path = Path("/tmp/test-archive.tar.zst")

        # Mock MediaFileUpload separately
        with patch("googleapiclient.http.MediaFileUpload") as mock_media:
            mock_media_instance = MagicMock()
            mock_media.return_value = mock_media_instance

            # Perform upload using asyncio.run
            file_id = asyncio.run(uploader.upload_to_gdrive(zip_path, config))

            # Verify the results
            assert file_id == "test_file_id_123"
            mock_drive_files.create.assert_called_once()
            # Verify the file was created with correct metadata
            called_args = mock_drive_files.create.call_args
            # The body parameter should contain the expected values
            body_arg = called_args[1]["body"]
            assert body_arg["name"] == "test-archive.tar.zst"
            assert body_arg["parents"] == ["test_folder_id"]

    @patch("scripts.backup.create.uploader.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_upload_to_gdrive_existing_file_update(self, mock_build, mock_loop):
        """Test uploading when a file with same name already exists (updates existing)."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()

        # Mock the files() method to return the files service object
        mock_drive_files = MagicMock()
        mock_service.files.return_value = mock_drive_files

        # Mock list operation - since there's an existing file, it should return it
        mock_list_request = MagicMock()
        mock_drive_files.list.return_value = mock_list_request
        mock_list_request.execute.return_value = {
            "files": [{"id": "existing_file_id_456", "name": "test-archive.tar.zst"}]
        }

        # Mock update operation for existing file case
        mock_update_request = MagicMock()
        mock_drive_files.update.return_value = mock_update_request
        mock_update_request.execute.return_value = {
            "id": "existing_file_id_456",
            "name": "test-archive.tar.zst",
            "webViewLink": "https://drive.google.com/file/d/existing_file_id_456/view",
        }

        mock_build.return_value = mock_service

        # Mock the event loop's run_in_executor
        loop_instance = MagicMock()

        async def run_in_executor_side_effect(*args, **kwargs):
            if args and callable(args[-1]):
                return args[-1]()
            else:
                func = args[-1]
                return func()

        loop_instance.run_in_executor.side_effect = (
            lambda *args, **kwargs: asyncio.ensure_future(
                run_in_executor_side_effect(*args, **kwargs)
            )
        )
        mock_loop.value = loop_instance
        mock_loop.return_value = loop_instance

        # Create uploader and config
        uploader = BackupUploader(mock_auth_manager)
        config = MagicMock()
        config.auth_method = "oauth"
        config.folder_id = "test_folder_id"
        zip_path = Path("/tmp/test-archive.tar.zst")

        # Mock MediaFileUpload
        with patch("googleapiclient.http.MediaFileUpload") as mock_media:
            mock_media_instance = MagicMock()
            mock_media.return_value = mock_media_instance

            # Perform upload
            file_id = asyncio.run(uploader.upload_to_gdrive(zip_path, config))

            # Verify the results - should have updated existing file
            assert file_id == "existing_file_id_456"
            mock_drive_files.update.assert_called_once()
            mock_drive_files.create.assert_not_called()
            # Verify the file was updated with the correct ID
            called_args = mock_drive_files.update.call_args
            assert called_args[1]["fileId"] == "existing_file_id_456"

    @patch("scripts.backup.create.uploader.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_upload_to_gdrive_error_handling(self, mock_build, mock_loop):
        """Test that upload handles errors properly."""
        # Setup mocks that will raise an exception
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_drive_files = MagicMock()
        mock_service.files.return_value = mock_drive_files

        # Make the create operation raise an exception
        mock_create_request = MagicMock()
        mock_drive_files.create.return_value = mock_create_request
        mock_create_request.execute.side_effect = Exception("API Error")

        # Setup list to return no existing files (so it tries to create)
        mock_list_request = MagicMock()
        mock_drive_files.list.return_value = mock_list_request
        mock_list_request.execute.return_value = {"files": []}

        mock_build.return_value = mock_service

        # Mock the event loop's run_in_executor
        loop_instance = MagicMock()

        async def run_in_executor_side_effect(*args, **kwargs):
            if args and callable(args[-1]):
                return args[-1]()
            else:
                func = args[-1]
                return func()

        loop_instance.run_in_executor.side_effect = (
            lambda *args, **kwargs: asyncio.ensure_future(
                run_in_executor_side_effect(*args, **kwargs)
            )
        )
        mock_loop.return_value = loop_instance

        # Create uploader and config
        uploader = BackupUploader(mock_auth_manager)
        config = MagicMock()
        config.auth_method = "oauth"
        config.folder_id = "test_folder_id"
        zip_path = Path("/tmp/test-archive.tar.zst")

        # Mock MediaFileUpload and check for exception
        with (
            patch("googleapiclient.http.MediaFileUpload"),
            pytest.raises(UploadError, match="Upload failed:"),
        ):
            asyncio.run(uploader.upload_to_gdrive(zip_path, config))

    @patch("scripts.backup.create.uploader.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_upload_to_gdrive_no_file_id_returned(self, mock_build, mock_loop):
        """Test that upload raises error when no file ID is returned."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_drive_files = MagicMock()
        mock_list_request = MagicMock()
        mock_service.files.return_value = mock_drive_files
        mock_drive_files.list.return_value = mock_list_request
        mock_list_request.execute.return_value = {"files": []}  # No existing files

        # Setup create response with no ID
        mock_create_request = MagicMock()
        mock_drive_files.create.return_value = mock_create_request
        mock_create_request.execute.return_value = {
            "name": "test-archive.tar.zst"  # No ID field
        }

        mock_build.return_value = mock_service

        # Mock the event loop's run_in_executor
        loop_instance = MagicMock()

        async def run_in_executor_side_effect(*args, **kwargs):
            if args and callable(args[-1]):
                return args[-1]()
            else:
                func = args[-1]
                return func()

        loop_instance.run_in_executor.side_effect = (
            lambda *args, **kwargs: asyncio.ensure_future(
                run_in_executor_side_effect(*args, **kwargs)
            )
        )
        mock_loop.return_value = loop_instance

        # Create uploader and config
        uploader = BackupUploader(mock_auth_manager)
        config = MagicMock()
        config.auth_method = "oauth"
        config.folder_id = "test_folder_id"
        zip_path = Path("/tmp/test-archive.tar.zst")

        # Mock MediaFileUpload
        with patch("googleapiclient.http.MediaFileUpload") as mock_media:
            mock_media_instance = MagicMock()
            mock_media.return_value = mock_media_instance

            # Should raise UploadError when no file ID is returned
            with pytest.raises(
                UploadError, match="Upload succeeded but no file ID returned"
            ):
                asyncio.run(uploader.upload_to_gdrive(zip_path, config))
