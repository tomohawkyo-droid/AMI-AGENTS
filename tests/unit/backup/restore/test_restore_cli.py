"""Tests for restore CLI: format, init, parser, args, run."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ami.scripts.backup.restore.cli import (
    BYTES_PER_GB,
    BYTES_PER_KB,
    BYTES_PER_MB,
    RestoreCLI,
    _format_file_size,
)

EXPECTED_PARSED_REVISION = 2
MINIMUM_SUCCESS_LOG_CALL_COUNT = 3


class TestFormatFileSize:
    """Tests for _format_file_size function."""

    def test_formats_bytes(self) -> None:
        """Test formats bytes."""
        assert _format_file_size(500) == "500B"

    def test_formats_kilobytes(self) -> None:
        """Test formats kilobytes."""
        assert _format_file_size(BYTES_PER_KB * 5) == "5.0KB"

    def test_formats_megabytes(self) -> None:
        """Test formats megabytes."""
        assert _format_file_size(BYTES_PER_MB * 5) == "5.0MB"

    def test_formats_gigabytes(self) -> None:
        """Test formats gigabytes."""
        assert _format_file_size(BYTES_PER_GB * 5) == "5.0GB"


class TestRestoreCLIInit:
    """Tests for RestoreCLI initialization."""

    def test_initialization_with_service(self) -> None:
        """Test initialization with service."""
        service = MagicMock()
        cli = RestoreCLI(service=service)
        assert cli.service == service

    def test_initialization_without_service(self) -> None:
        """Test initialization without service."""
        cli = RestoreCLI()
        assert cli.service is None


class TestRestoreCLIRequireService:
    """Tests for RestoreCLI._require_service method."""

    def test_returns_service_when_set(self) -> None:
        """Test returns service when initialized."""
        service = MagicMock()
        cli = RestoreCLI(service=service)
        assert cli._require_service() == service

    def test_raises_when_service_not_set(self) -> None:
        """Test raises RuntimeError when service not set."""
        cli = RestoreCLI()
        with pytest.raises(RuntimeError, match="not initialized"):
            cli._require_service()


class TestRestoreCLICreateParser:
    """Tests for RestoreCLI.create_parser method."""

    def test_creates_parser(self) -> None:
        """Test creates argument parser."""
        cli = RestoreCLI()
        parser = cli.create_parser()

        assert parser.prog == "backup_restore"

    def test_parser_has_required_arguments(self) -> None:
        """Test parser has all required arguments."""
        cli = RestoreCLI()
        parser = cli.create_parser()

        # Parse with minimal args
        args = parser.parse_args([])

        assert hasattr(args, "config_path")
        assert hasattr(args, "file_id")
        assert hasattr(args, "local_path")
        assert hasattr(args, "latest_local")
        assert hasattr(args, "interactive")
        assert hasattr(args, "revision")
        assert hasattr(args, "list_revisions")
        assert hasattr(args, "restore_path")
        assert hasattr(args, "verbose")
        assert hasattr(args, "paths")


class TestRestoreCLIParseArguments:
    """Tests for RestoreCLI.parse_arguments method."""

    def test_parses_file_id(self) -> None:
        """Test parses --file-id argument."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--file-id", "abc123"])

        assert args.file_id == "abc123"

    def test_parses_local_path(self) -> None:
        """Test parses --local-path argument."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--local-path", "/path/to/backup.tar.zst"])

        assert args.local_path == Path("/path/to/backup.tar.zst")

    def test_parses_latest_local(self) -> None:
        """Test parses --latest-local flag."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--latest-local"])

        assert args.latest_local is True

    def test_parses_interactive(self) -> None:
        """Test parses --interactive flag."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--interactive"])

        assert args.interactive is True

    def test_parses_revision(self) -> None:
        """Test parses --revision argument."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--revision", "2"])

        assert args.revision == EXPECTED_PARSED_REVISION

    def test_parses_list_revisions(self) -> None:
        """Test parses --list-revisions flag."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--list-revisions"])

        assert args.list_revisions is True

    def test_parses_restore_path(self) -> None:
        """Test parses --restore-path argument."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--restore-path", "/tmp/restore"])

        assert args.restore_path == Path("/tmp/restore")

    def test_parses_verbose(self) -> None:
        """Test parses --verbose flag."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--verbose"])

        assert args.verbose is True

    def test_parses_paths(self) -> None:
        """Test parses positional paths."""
        cli = RestoreCLI()
        args = cli.parse_arguments(["--file-id", "abc", "path1", "path2"])

        assert args.paths == [Path("path1"), Path("path2")]


class TestRestoreCLIRunMethods:
    """Tests for RestoreCLI run methods."""

    @pytest.mark.asyncio
    async def test_run_restore_by_revision(self, tmp_path: Path) -> None:
        """Test run_restore_by_revision delegates to service."""
        service = MagicMock()
        service.restore_from_drive_by_revision = AsyncMock(return_value=True)
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_restore_by_revision(0, tmp_path, config)

        assert result is True
        service.restore_from_drive_by_revision.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_restore_by_file_id(self, tmp_path: Path) -> None:
        """Test run_restore_by_file_id delegates to service."""
        service = MagicMock()
        service.restore_from_drive_by_file_id = AsyncMock(return_value=True)
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_restore_by_file_id("file123", tmp_path, config)

        assert result is True
        service.restore_from_drive_by_file_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_restore_local(self, tmp_path: Path) -> None:
        """Test run_restore_local delegates to service."""
        service = MagicMock()
        service.restore_local_backup = AsyncMock(return_value=True)

        cli = RestoreCLI(service=service)
        result = await cli.run_restore_local(tmp_path / "backup.tar.zst", tmp_path)

        assert result is True
        service.restore_local_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_restore_latest_local(self, tmp_path: Path) -> None:
        """Test run_restore_latest_local delegates to service."""
        service = MagicMock()
        service.restore_latest_local = AsyncMock(return_value=True)

        cli = RestoreCLI(service=service)
        result = await cli.run_restore_latest_local(tmp_path)

        assert result is True
        service.restore_latest_local.assert_called_once()


class TestRestoreCLIInteractiveSelection:
    """Tests for RestoreCLI.run_interactive_selection method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_files(self, tmp_path: Path) -> None:
        """Test returns False when no backup files found."""
        service = MagicMock()
        service.list_available_drive_backups = AsyncMock(return_value=[])
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_interactive_selection(config, tmp_path)

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.restore.cli.select_backup_interactive")
    async def test_returns_false_when_nothing_selected(
        self, mock_select, tmp_path: Path
    ) -> None:
        """Test returns False when user doesn't select anything."""
        service = MagicMock()
        service.list_available_drive_backups = AsyncMock(
            return_value=[{"id": "1", "name": "backup1"}]
        )
        mock_select.return_value = None
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_interactive_selection(config, tmp_path)

        assert result is False

    @pytest.mark.asyncio
    @patch("ami.scripts.backup.restore.cli.select_backup_interactive")
    async def test_restores_selected_backup(self, mock_select, tmp_path: Path) -> None:
        """Test restores selected backup."""
        service = MagicMock()
        service.list_available_drive_backups = AsyncMock(
            return_value=[{"id": "file123", "name": "backup1"}]
        )
        service.restore_from_drive_by_file_id = AsyncMock(return_value=True)
        mock_select.return_value = "file123"
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_interactive_selection(config, tmp_path)

        assert result is True
        service.restore_from_drive_by_file_id.assert_called_once()


class TestRestoreCLIListRevisions:
    """Tests for RestoreCLI.run_list_revisions method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_files(self) -> None:
        """Test returns False when no backup files found."""
        service = MagicMock()
        service.list_available_drive_backups = AsyncMock(return_value=[])
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_list_revisions(config)

        assert result is False

    @pytest.mark.asyncio
    async def test_prints_revision_table(self, capsys) -> None:
        """Test prints revision table."""
        service = MagicMock()
        service.list_available_drive_backups = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "name": "backup1.tar.zst",
                    "modifiedTime": "2024-01-01T00:00:00",
                    "size": "1048576",
                }
            ]
        )
        config = MagicMock()

        cli = RestoreCLI(service=service)
        result = await cli.run_list_revisions(config)

        assert result is True
        captured = capsys.readouterr()
        assert "backup1.tar.zst" in captured.out


class TestRestoreCLIPrintRevisionTable:
    """Tests for RestoreCLI._print_revision_table method."""

    def test_prints_formatted_table(self, capsys) -> None:
        """Test prints formatted table."""
        cli = RestoreCLI()
        backup_files = [
            {
                "id": "1",
                "name": "backup1.tar.zst",
                "modifiedTime": "2024-01-01T12:00:00",
                "size": "1048576",
            },
            {
                "id": "2",
                "name": "backup2.tar.zst",
                "modifiedTime": "2024-01-02T12:00:00",
                "size": "2097152",
            },
        ]

        cli._print_revision_table(backup_files)

        captured = capsys.readouterr()
        assert "File Name" in captured.out
        assert "Modified Time" in captured.out
        assert "Size" in captured.out
        assert "backup1.tar.zst" in captured.out
        assert "backup2.tar.zst" in captured.out
        assert "Total backups found: 2" in captured.out

    def test_truncates_long_names(self, capsys) -> None:
        """Test truncates long file names."""
        cli = RestoreCLI()
        long_name = "a" * 60 + ".tar.zst"
        backup_files = [
            {
                "id": "1",
                "name": long_name,
                "modifiedTime": "2024-01-01T00:00:00",
                "size": "1024",
            }
        ]

        cli._print_revision_table(backup_files)

        captured = capsys.readouterr()
        assert "..." in captured.out


class TestRestoreCLIFormatSize:
    """Tests for RestoreCLI._format_size method."""

    def test_formats_unknown(self) -> None:
        """Test returns Unknown as-is."""
        cli = RestoreCLI()
        assert cli._format_size("Unknown") == "Unknown"

    def test_formats_valid_size(self) -> None:
        """Test formats valid size string."""
        cli = RestoreCLI()
        # 2MB = 2097152 bytes (> 1MB threshold)
        assert cli._format_size("2097152") == "2.0MB"

    def test_handles_invalid_size(self) -> None:
        """Test handles invalid size string."""
        cli = RestoreCLI()
        assert cli._format_size("invalid") == "invalid"
