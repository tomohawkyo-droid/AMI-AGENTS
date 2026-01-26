"""Unit tests for the archive extraction module (restore/extractor.py)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from ami.scripts.backup.restore import extractor


class TestArchiveExtractor:
    """Unit tests for the archive extraction functions."""

    @patch("scripts.backup.restore.extractor.asyncio.get_event_loop")
    async def test_extract_specific_paths_executor_call(self, mock_loop):
        """Test that extract_specific_paths calls run_in_executor."""
        loop_instance = MagicMock()
        mock_loop.return_value = loop_instance

        # Make run_in_executor return an awaitable
        loop_instance.run_in_executor = AsyncMock(return_value=True)

        archive_path = Path("/tmp/backup.tar.zst")
        paths = [Path("test.txt")]
        dest = Path("/tmp/restore")

        await extractor.extract_specific_paths(archive_path, paths, dest)

        loop_instance.run_in_executor.assert_called_once()

    @patch("scripts.backup.restore.extractor.zstd")
    @patch("scripts.backup.restore.extractor.tarfile")
    @patch("builtins.open", new_callable=mock_open)
    def test_extract_specific_paths_sync_logic(
        self,
        mock_file_open,
        mock_tarfile,
        mock_zstd,
    ):
        """Test the synchronous logic of extraction without triggering C-extension crashes."""
        # Mock zstd decompressor and stream
        mock_dctx = MagicMock()
        mock_zstd.ZstdDecompressor.return_value = mock_dctx
        mock_reader = MagicMock()
        mock_reader.read.side_effect = [b"data", b""]
        mock_dctx.stream_reader.return_value.__enter__.return_value = mock_reader

        # Setup tar member mocks
        mock_member = MagicMock()
        mock_member.name = "./test.txt"

        mock_tar = MagicMock()
        mock_tar.getmembers.return_value = [mock_member]
        mock_tarfile.open.return_value.__enter__.return_value = mock_tar

        archive_path = Path("/tmp/backup.tar.zst")
        paths = [Path("test.txt")]
        dest = Path("/tmp/restore")

        # Use nested patches inside the test body to reduce argument count
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("tempfile.NamedTemporaryFile") as mock_temp,
        ):
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/temp.tar"
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            result = extractor._extract_specific_paths_sync(archive_path, paths, dest)

            assert result is True
            mock_tar.extractall.assert_called_once()

    @patch("scripts.backup.restore.extractor.zstd")
    @patch("scripts.backup.restore.extractor.tarfile")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_list_archive_contents_sync(
        self, mock_exists, mock_file_open, mock_tarfile, mock_zstd
    ):
        """Test the synchronous logic of listing contents."""
        mock_exists.return_value = True

        mock_tar = MagicMock()
        mock_tar.getnames.return_value = ["file1.txt", "dir/file2.txt"]
        mock_tarfile.open.return_value.__enter__.return_value = mock_tar

        # Mock zstd reader
        mock_dctx = MagicMock()
        mock_zstd.ZstdDecompressor.return_value = mock_dctx
        mock_reader = MagicMock()
        mock_reader.readall.return_value = b"mock tar data"
        mock_dctx.stream_reader.return_value.__enter__.return_value = mock_reader

        archive_path = Path("/tmp/backup.tar.zst")
        result = extractor._list_archive_contents_sync(archive_path)

        assert "file1.txt" in result
        assert "dir/file2.txt" in result

    @patch("pathlib.Path.exists")
    def test_validate_archive_not_exists(self, mock_exists):
        """Test validation fails for non-existent archive."""
        mock_exists.return_value = False

        archive_path = Path("/tmp/missing.tar.zst")
        result = extractor.validate_archive(archive_path)

        assert result is False
