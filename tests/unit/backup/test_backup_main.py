"""Unit tests for backup main entry points."""

import os
from unittest.mock import patch

from ami.scripts.backup.create.main import main as backup_main
from ami.scripts.backup.restore.main import main as restore_main


class TestBackupMain:
    """Test backup main entry point."""

    def test_help_works_without_env(self, tmp_path):
        """Test that --help works even without .env file."""
        os.chdir(tmp_path)
        with patch("sys.argv", ["ami-backup", "--help"]):
            result = backup_main()
            assert result == 0

    def test_help_flag_short(self, tmp_path):
        """Test that -h works even without .env file."""
        os.chdir(tmp_path)
        with patch("sys.argv", ["ami-backup", "-h"]):
            result = backup_main()
            assert result == 0

    def test_missing_env_returns_error(self, tmp_path):
        """Test that missing .env file returns error code 1."""
        os.chdir(tmp_path)
        with patch("sys.argv", ["ami-backup"]):
            result = backup_main()
            assert result == 1


class TestRestoreMain:
    """Test restore main entry point."""

    def test_help_works_without_env(self, tmp_path):
        """Test that --help works even without .env file."""
        os.chdir(tmp_path)
        with patch("sys.argv", ["ami-restore", "--help"]):
            result = restore_main()
            assert result == 0

    def test_help_flag_short(self, tmp_path):
        """Test that -h works even without .env file."""
        os.chdir(tmp_path)
        with patch("sys.argv", ["ami-restore", "-h"]):
            result = restore_main()
            assert result == 0

    def test_missing_env_returns_error(self, tmp_path):
        """Test that missing .env file returns error code 1."""
        os.chdir(tmp_path)
        with patch("sys.argv", ["ami-restore", "--latest-local"]):
            result = restore_main()
            assert result == 1
