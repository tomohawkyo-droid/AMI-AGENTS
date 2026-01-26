"""Unit tests for the DriveRestoreClient service (restore/drive_client.py)."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.scripts.backup.restore.drive_client import DriveRestoreClient

# Test constants
EXPECTED_BACKUP_FILE_COUNT = 2


class TestDriveRestoreClient:
    """Unit tests for the DriveRestoreClient class."""

    def test_initialization(self):
        """Test that DriveRestoreClient initializes with auth manager."""
        mock_auth_manager = MagicMock()
        client = DriveRestoreClient(mock_auth_manager)

        assert client.auth_manager == mock_auth_manager
        assert client._service is None

    @patch("googleapiclient.discovery.build")
    def test_get_service_creates_google_service(self, mock_build):
        """Test that _get_service creates the Google Drive service."""
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        client = DriveRestoreClient(mock_auth_manager)

        # Call the async method using asyncio.run
        service = asyncio.run(client._get_service())

        assert service == mock_service
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_credentials)
        # Verify it's cached
        assert client._service == mock_service

    @patch("scripts.backup.restore.drive_client.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_list_backup_files_success(self, mock_build, mock_loop):
        """Test successful listing of backup files."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_files_resource = MagicMock()
        mock_service.files.return_value = mock_files_resource
        mock_list_request = MagicMock()
        mock_files_resource.list.return_value = mock_list_request
        mock_list_request.execute.return_value = {
            "files": [
                {
                    "id": "file1_id",
                    "name": "ami-orchestrator-backup_20231201_120000.tar.zst",
                    "modifiedTime": "2023-12-01T12:00:00Z",
                    "size": "1048576",
                },
                {
                    "id": "file2_id",
                    "name": "ami-orchestrator-backup_20231130_120000.tar.zst",
                    "modifiedTime": "2023-11-30T12:00:00Z",
                    "size": "2097152",
                },
            ]
        }

        mock_build.return_value = mock_service

        # Mock event loop's run_in_executor to return the result of the lambda as a completed future
        mock_loop_instance = MagicMock()

        def run_in_executor_side_effect(*args, **kwargs):
            func = args[-1]  # This should be the lambda

            # Return a coroutine that yields the result when awaited
            async def async_result():
                return func()

            return async_result()

        mock_loop_instance.run_in_executor.side_effect = run_in_executor_side_effect
        mock_loop.return_value = mock_loop_instance

        # Create client and config
        client = DriveRestoreClient(mock_auth_manager)
        config = MagicMock()
        config.folder_id = "test_folder_id"

        # Run the method
        result = asyncio.run(client.list_backup_files(config))

        # Verify results
        assert len(result) == EXPECTED_BACKUP_FILE_COUNT
        assert result[0]["id"] == "file1_id"  # Newest first due to ordering
        assert result[1]["id"] == "file2_id"

        # Verify the call was made correctly
        mock_files_resource.list.assert_called_once()
        call_args = mock_files_resource.list.call_args[1]
        assert "ami-orchestrator-backup.tar.zst" in call_args["q"]
        assert "test_folder_id" in call_args["q"]

    @patch("scripts.backup.restore.drive_client.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_list_backup_files_no_files(self, mock_build, mock_loop):
        """Test listing backup files when no files exist."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_files_resource = MagicMock()
        mock_service.files.return_value = mock_files_resource
        mock_list_request = MagicMock()
        mock_files_resource.list.return_value = mock_list_request
        mock_list_request.execute.return_value = {"files": []}  # No files

        mock_build.return_value = mock_service

        # Mock event loop's run_in_executor to return the result of the lambda as a completed future
        mock_loop_instance = MagicMock()

        def run_in_executor_side_effect(*args, **kwargs):
            func = args[-1]  # This should be the lambda

            # Return a coroutine that yields the result when awaited
            async def async_result():
                return func()

            return async_result()

        mock_loop_instance.run_in_executor.side_effect = run_in_executor_side_effect
        mock_loop.return_value = mock_loop_instance

        # Create client and config
        client = DriveRestoreClient(mock_auth_manager)
        config = MagicMock()
        config.folder_id = None  # No specific folder

        # Run the method
        result = asyncio.run(client.list_backup_files(config))

        # Verify results
        assert result == []  # Empty list

    @patch("scripts.backup.restore.drive_client.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    @patch("builtins.open")
    def test_download_file_success(self, mock_open_func, mock_build, mock_loop):
        """Test successful download of a file."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_files_resource = MagicMock()
        mock_service.files.return_value = mock_files_resource

        # Mock get file metadata request
        mock_get_request = MagicMock()
        mock_files_resource.get.return_value = mock_get_request
        mock_get_request.execute.return_value = {
            "name": "test_backup.tar.zst",
            "size": "1048576",
        }

        mock_build.return_value = mock_service

        # Mock event loop's run_in_executor to return the result of the lambda as a completed future
        mock_loop_instance = MagicMock()

        def run_in_executor_side_effect(*args, **kwargs):
            func = args[-1]  # This should be the lambda

            # Return a coroutine that yields the result when awaited
            async def async_result():
                return func()

            return async_result()

        mock_loop_instance.run_in_executor.side_effect = run_in_executor_side_effect
        mock_loop.return_value = mock_loop_instance

        # Mock MediaIoBaseDownload
        with patch("googleapiclient.http.MediaIoBaseDownload") as mock_downloader:
            mock_downloader_instance = MagicMock()
            mock_downloader_instance.next_chunk.return_value = (
                MagicMock(progress=lambda: 1.0),
                True,
            )  # 100%, done
            mock_downloader.return_value = mock_downloader_instance

            # Mock file context manager
            mock_file = MagicMock()
            mock_open_func.return_value.__enter__.return_value = mock_file

            # Create client and config
            client = DriveRestoreClient(mock_auth_manager)
            config = MagicMock()
            destination = Path("/tmp/test_backup.tar.zst")

            # Run the method
            result = asyncio.run(
                client.download_file("test_file_id", destination, config)
            )

            # Verify results
            assert result is True
            mock_files_resource.get.assert_called_once()
            mock_open_func.assert_called_once_with(destination, "wb")
            mock_downloader.assert_called_once()  # Called for download

    @patch("scripts.backup.restore.drive_client.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_get_file_metadata_success(self, mock_build, mock_loop):
        """Test getting file metadata successfully."""
        # Setup mocks
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_files_resource = MagicMock()
        mock_service.files.return_value = mock_files_resource

        # Mock get file metadata request
        mock_get_request = MagicMock()
        mock_files_resource.get.return_value = mock_get_request
        expected_metadata = {
            "id": "test_file_id",
            "name": "test_backup.tar.zst",
            "size": "1048576",
            "modifiedTime": "2023-12-01T12:00:00Z",
        }
        mock_get_request.execute.return_value = expected_metadata

        mock_build.return_value = mock_service

        # Mock event loop's run_in_executor to return the result of the lambda as a completed future
        mock_loop_instance = MagicMock()

        def run_in_executor_side_effect(*args, **kwargs):
            func = args[-1]  # This should be the lambda

            # Return a coroutine that yields the result when awaited
            async def async_result():
                return func()

            return async_result()

        mock_loop_instance.run_in_executor.side_effect = run_in_executor_side_effect
        mock_loop.return_value = mock_loop_instance

        # Create client
        client = DriveRestoreClient(mock_auth_manager)

        # Run the method
        result = asyncio.run(client.get_file_metadata("test_file_id"))

        # Verify results
        assert result == expected_metadata

    @patch("scripts.backup.restore.drive_client.asyncio.get_event_loop")
    @patch("googleapiclient.discovery.build")
    def test_verify_backup_exists_success(self, mock_build, mock_loop):
        """Test verifying backup exists when it does."""
        # Setup mocks - similar to get_file_metadata but testing the verify method
        mock_auth_manager = MagicMock()
        mock_credentials = MagicMock()
        mock_auth_manager.get_credentials.return_value = mock_credentials
        mock_service = MagicMock()
        mock_files_resource = MagicMock()
        mock_service.files.return_value = mock_files_resource

        # Mock get file metadata request to return metadata (exists)
        mock_get_request = MagicMock()
        mock_files_resource.get.return_value = mock_get_request
        mock_get_request.execute.return_value = {
            "id": "test_file_id",
            "name": "test_backup.tar.zst",
        }

        mock_build.return_value = mock_service

        # Mock event loop's run_in_executor to return the result of the lambda as a completed future
        mock_loop_instance = MagicMock()

        def run_in_executor_side_effect(*args, **kwargs):
            func = args[-1]  # This should be the lambda

            # Return a coroutine that yields the result when awaited
            async def async_result():
                return func()

            return async_result()

        mock_loop_instance.run_in_executor.side_effect = run_in_executor_side_effect
        mock_loop.return_value = mock_loop_instance

        # Create client
        client = DriveRestoreClient(mock_auth_manager)

        # Run the method
        result = asyncio.run(client.verify_backup_exists("test_file_id"))

        # Verify results
        assert result is True
