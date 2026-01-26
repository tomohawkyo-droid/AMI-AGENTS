"""Unit tests for backup CLI functionality."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ami.scripts.backup.create.cli import BackupCLI
from ami.scripts.backup.restore.cli import RestoreCLI


class TestBackupCLI:
    """Test backup CLI argument parsing and initialization."""

    def test_create_parser(self):
        """Test that parser is created with all required options."""
        service = MagicMock()
        cli = BackupCLI(service)
        parser = cli.create_parser()

        assert parser is not None
        assert parser.prog == "backup_to_gdrive"

    def test_parse_help_flag(self):
        """Test parsing --help doesn't raise."""
        service = MagicMock()
        cli = BackupCLI(service)

        with pytest.raises(SystemExit) as exc_info:
            cli.parse_arguments(["--help"])
        assert exc_info.value.code == 0

    def test_parse_name_argument(self):
        """Test parsing --name argument."""
        service = MagicMock()
        cli = BackupCLI(service)

        args = cli.parse_arguments(["--name", "my-backup"])
        assert args.name == "my-backup"

    def test_parse_keep_local_flag(self):
        """Test parsing --keep-local flag."""
        service = MagicMock()
        cli = BackupCLI(service)

        args = cli.parse_arguments(["--keep-local"])
        assert args.keep_local is True

    def test_parse_verbose_flag(self):
        """Test parsing --verbose flag."""
        service = MagicMock()
        cli = BackupCLI(service)

        args = cli.parse_arguments(["-v"])
        assert args.verbose is True

    def test_parse_source_directory(self):
        """Test parsing source directory argument."""
        service = MagicMock()
        cli = BackupCLI(service)

        args = cli.parse_arguments(["/tmp/test"])
        assert args.source == Path("/tmp/test")

    def test_default_source_is_cwd(self):
        """Test default source is current working directory."""
        service = MagicMock()
        cli = BackupCLI(service)

        args = cli.parse_arguments([])
        assert args.source == Path.cwd()


class TestRestoreCLI:
    """Test restore CLI argument parsing and initialization."""

    def test_create_parser(self):
        """Test that parser is created with all required options."""
        service = MagicMock()
        cli = RestoreCLI(service)
        parser = cli.create_parser()

        assert parser is not None
        assert parser.prog == "backup_restore"

    def test_parse_help_flag(self):
        """Test parsing --help doesn't raise."""
        service = MagicMock()
        cli = RestoreCLI(service)

        with pytest.raises(SystemExit) as exc_info:
            cli.parse_arguments(["--help"])
        assert exc_info.value.code == 0

    def test_parse_file_id_argument(self):
        """Test parsing --file-id argument."""
        service = MagicMock()
        cli = RestoreCLI(service)

        args = cli.parse_arguments(["--file-id", "abc123"])
        assert args.file_id == "abc123"

    def test_parse_latest_local_flag(self):
        """Test parsing --latest-local flag."""
        service = MagicMock()
        cli = RestoreCLI(service)

        args = cli.parse_arguments(["--latest-local"])
        assert args.latest_local is True

    def test_parse_local_path_argument(self):
        """Test parsing --local-path argument."""
        service = MagicMock()
        cli = RestoreCLI(service)

        args = cli.parse_arguments(["--local-path", "/tmp/backup.tar.zst"])
        assert args.local_path == Path("/tmp/backup.tar.zst")

    def test_mutually_exclusive_sources(self):
        """Test that source options are mutually exclusive."""
        service = MagicMock()
        cli = RestoreCLI(service)

        with pytest.raises(SystemExit):
            cli.parse_arguments(["--file-id", "abc", "--latest-local"])
