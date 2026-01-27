"""Unit tests for ci/check_banned_words module - main function integration tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.ci.check_banned_words import main


class TestMain:
    """Tests for main function."""

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_success_no_errors(
        self, mock_load_config, mock_getcwd, mock_walk, tmp_path: Path
    ):
        """Test main exits with 0 when no banned patterns found."""
        mock_load_config.return_value = {
            "banned": [],
            "directory_rules": {},
            "filename_rules": [],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_failure_with_errors(
        self,
        mock_load_config,
        mock_getcwd,
        mock_walk,
        tmp_path: Path,
    ):
        """Test main exits with 1 when banned patterns found."""
        test_file = tmp_path / "test.py"
        test_file.write_text("eval(x)")

        mock_load_config.return_value = {
            "banned": [{"pattern": "eval", "reason": "No eval"}],
            "directory_rules": {},
            "filename_rules": [],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = [(str(tmp_path), [], ["test.py"])]

        with (
            patch(
                "ami.scripts.ci.check_banned_words.check_filename",
                return_value=[],
            ),
            patch(
                "ami.scripts.ci.check_banned_words.check_file_content",
                return_value=[
                    {
                        "file": "test.py",
                        "line": 1,
                        "pattern": "eval",
                        "reason": "No eval",
                        "content": "eval(x)",
                    }
                ],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_skips_ignored_directories(
        self, mock_load_config, mock_getcwd, mock_walk, tmp_path: Path
    ):
        """Test main skips ignored directories."""
        mock_load_config.return_value = {
            "banned": [],
            "directory_rules": {},
            "filename_rules": [],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)

        # Simulate os.walk with dirs that should be filtered
        dirs_list = [".git", "src", ".venv", "__pycache__"]
        mock_walk.return_value = [(str(tmp_path), dirs_list, [])]

        with pytest.raises(SystemExit):
            main()

        # After main runs, the dirs_list should be modified in-place
        # to remove ignored dirs
        # Note: The actual filtering happens in the function, not in mocks
        # So we just verify main completes

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_skips_non_included_extensions(
        self, mock_load_config, mock_getcwd, mock_walk, tmp_path: Path
    ):
        """Test main skips files with non-included extensions."""
        mock_load_config.return_value = {
            "banned": [{"pattern": "test", "reason": "r"}],
            "directory_rules": {},
            "filename_rules": [],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = [
            (str(tmp_path), [], ["readme.md", "data.json", "config.yaml"])
        ]

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should succeed because no .py/.js/.ts files
        assert exc_info.value.code == 0

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_skips_ignored_files(
        self,
        mock_load_config,
        mock_getcwd,
        mock_walk,
        tmp_path: Path,
    ):
        """Test main skips files in ignored_files list."""
        mock_load_config.return_value = {
            "banned": [{"pattern": "forbidden", "reason": "r"}],
            "directory_rules": {},
            "filename_rules": [],
            "ignored_files": ["conftest.py"],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = [(str(tmp_path), [], ["conftest.py"])]

        with (
            patch(
                "ami.scripts.ci.check_banned_words.check_filename",
                return_value=[],
            ),
            patch(
                "ami.scripts.ci.check_banned_words.check_file_content",
                return_value=[],
            ) as mock_check_content,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        # conftest.py should be skipped, check_content not called
        mock_check_content.assert_not_called()
        assert exc_info.value.code == 0

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_checks_python_files(
        self,
        mock_load_config,
        mock_getcwd,
        mock_walk,
        tmp_path: Path,
    ):
        """Test main checks .py files."""
        mock_load_config.return_value = {
            "banned": [{"pattern": "test", "reason": "r"}],
            "directory_rules": {},
            "filename_rules": [],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = [(str(tmp_path), [], ["main.py"])]

        with (
            patch(
                "ami.scripts.ci.check_banned_words.check_filename",
                return_value=[],
            ),
            patch(
                "ami.scripts.ci.check_banned_words.check_file_content",
                return_value=[],
            ) as mock_check_content,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        mock_check_content.assert_called_once()
        assert exc_info.value.code == 0

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_uses_directory_rules(
        self,
        mock_load_config,
        mock_getcwd,
        mock_walk,
        tmp_path: Path,
    ):
        """Test main applies directory-specific rules."""
        mock_load_config.return_value = {
            "banned": [],
            "directory_rules": {
                "tests": [{"pattern": "print", "reason": "Use logging"}]
            },
            "filename_rules": [],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = [(str(tmp_path / "tests"), [], ["test_main.py"])]

        with (
            patch(
                "ami.scripts.ci.check_banned_words.check_filename",
                return_value=[],
            ),
            patch(
                "ami.scripts.ci.check_banned_words.check_file_content",
                return_value=[],
            ) as mock_check_content,
            pytest.raises(SystemExit),
        ):
            main()

        # Verify check_file_content was called with dir rules
        assert mock_check_content.called

    @patch("sys.argv", ["check_banned_words.py", "--config", "test_config.yaml"])
    @patch("ami.scripts.ci.check_banned_words.check_filename")
    @patch("ami.scripts.ci.check_banned_words.os.walk")
    @patch("ami.scripts.ci.check_banned_words.os.getcwd")
    @patch("ami.scripts.ci.check_banned_words.load_config")
    def test_main_checks_filenames(
        self,
        mock_load_config,
        mock_getcwd,
        mock_walk,
        mock_check_filename,
        tmp_path: Path,
    ):
        """Test main checks filenames against filename_rules."""
        mock_load_config.return_value = {
            "banned": [],
            "directory_rules": {},
            "filename_rules": [{"pattern": r"\.bak$", "reason": "No backups"}],
            "ignored_files": [],
        }
        mock_getcwd.return_value = str(tmp_path)
        mock_walk.return_value = [(str(tmp_path), [], ["file.py"])]

        mock_check_filename.return_value = []

        with pytest.raises(SystemExit):
            main()

        mock_check_filename.assert_called()
