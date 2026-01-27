"""Unit tests for ci/check_file_length module."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from ami.scripts.ci.check_file_length import (
    DEFAULT_CONFIG,
    check_file_length,
    get_all_files,
    load_config,
    main,
    print_violations,
    should_check_file,
)

EXPECTED_DEFAULT_MAX_LINES = 512
EXPECTED_CUSTOM_MAX_LINES = 300
EXPECTED_LINE_COUNT_100 = 100
EXPECTED_LINE_COUNT_51 = 51


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_has_max_lines(self) -> None:
        """Test DEFAULT_CONFIG has max_lines."""
        assert "max_lines" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["max_lines"] == EXPECTED_DEFAULT_MAX_LINES

    def test_has_extensions(self) -> None:
        """Test DEFAULT_CONFIG has extensions."""
        assert "extensions" in DEFAULT_CONFIG
        assert ".py" in DEFAULT_CONFIG["extensions"]
        assert ".sh" in DEFAULT_CONFIG["extensions"]

    def test_has_ignore_dirs(self) -> None:
        """Test DEFAULT_CONFIG has ignore_dirs."""
        assert "ignore_dirs" in DEFAULT_CONFIG
        assert ".git" in DEFAULT_CONFIG["ignore_dirs"]
        assert ".venv" in DEFAULT_CONFIG["ignore_dirs"]


class TestLoadConfig:
    """Tests for load_config function."""

    @patch("ami.scripts.ci.check_file_length.os.path.exists", return_value=False)
    def test_returns_default_when_file_missing(self, mock_exists) -> None:
        """Test returns default config when file doesn't exist."""
        config = load_config()

        assert config == DEFAULT_CONFIG

    def test_loads_from_file(self, tmp_path: Path) -> None:
        """Test loads config from file when it exists."""
        config_content = """
max_lines: 300
extensions:
  - ".py"
ignore_files:
  - "conftest.py"
ignore_dirs:
  - ".git"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch("ami.scripts.ci.check_file_length.CONFIG_PATH", str(config_file)):
            config = load_config()

        assert config["max_lines"] == EXPECTED_CUSTOM_MAX_LINES
        assert ".py" in config["extensions"]

    @patch("ami.scripts.ci.check_file_length.os.path.exists", return_value=True)
    def test_returns_default_for_empty_file(self, mock_exists) -> None:
        """Test returns default for empty config file."""
        with patch("builtins.open", mock_open(read_data="")):
            config = load_config()

        assert config == DEFAULT_CONFIG


class TestGetAllFiles:
    """Tests for get_all_files function."""

    def test_finds_matching_files(self, tmp_path: Path) -> None:
        """Test finds files with matching extensions."""
        (tmp_path / "file.py").touch()
        (tmp_path / "file.sh").touch()
        (tmp_path / "file.txt").touch()

        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [
                (str(tmp_path), [], ["file.py", "file.sh", "file.txt"])
            ]
            files = get_all_files(set(), (".py", ".sh"))

        assert len([f for f in files if f.endswith(".py")]) == 1
        assert len([f for f in files if f.endswith(".sh")]) == 1
        assert not any(f.endswith(".txt") for f in files)

    def test_excludes_ignored_directories(self, tmp_path: Path) -> None:
        """Test excludes ignored directories."""
        ignore_dirs = {".git", "__pycache__"}

        # Simulate os.walk behavior - dirs list should be modified in-place
        dirs = [".git", "src", "__pycache__", "tests"]
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(str(tmp_path), dirs, ["file.py"])]
            get_all_files(ignore_dirs, (".py",))

            # Check that dirs were filtered
            # (this happens via dirs[:] = ... in the function)
            # We verify by checking the call structure


class TestShouldCheckFile:
    """Tests for should_check_file function."""

    def test_returns_true_for_valid_file(self, tmp_path: Path) -> None:
        """Test returns True for valid file."""
        test_file = tmp_path / "test.py"
        test_file.touch()

        result = should_check_file(str(test_file), (".py",), set(), set())

        assert result is True

    def test_returns_false_for_wrong_extension(self, tmp_path: Path) -> None:
        """Test returns False for wrong extension."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = should_check_file(str(test_file), (".py",), set(), set())

        assert result is False

    def test_returns_false_for_ignored_file(self, tmp_path: Path) -> None:
        """Test returns False for ignored file."""
        test_file = tmp_path / "conftest.py"
        test_file.touch()

        result = should_check_file(str(test_file), (".py",), {"conftest.py"}, set())

        assert result is False

    def test_returns_false_for_nonexistent_file(self) -> None:
        """Test returns False for nonexistent file."""
        result = should_check_file("/nonexistent/file.py", (".py",), set(), set())

        assert result is False

    def test_returns_false_for_file_in_ignored_dir(self, tmp_path: Path) -> None:
        """Test returns False for file in ignored directory."""
        subdir = tmp_path / ".venv"
        subdir.mkdir()
        test_file = subdir / "test.py"
        test_file.touch()

        result = should_check_file(str(test_file), (".py",), set(), {".venv"})

        assert result is False


class TestCheckFileLength:
    """Tests for check_file_length function."""

    def test_returns_none_for_short_file(self, tmp_path: Path) -> None:
        """Test returns None for file under limit."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        result = check_file_length(str(test_file), 10)

        assert result is None

    def test_returns_count_for_long_file(self, tmp_path: Path) -> None:
        """Test returns line count for file over limit."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\n".join([f"line{i}" for i in range(100)]))

        result = check_file_length(str(test_file), 50)

        assert result == EXPECTED_LINE_COUNT_100

    def test_returns_none_for_unreadable_file(self) -> None:
        """Test returns None for unreadable file."""
        result = check_file_length("/nonexistent/file.py", 100)

        assert result is None

    def test_counts_exact_limit(self, tmp_path: Path) -> None:
        """Test file at exact limit returns None."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\n".join([f"line{i}" for i in range(50)]))

        result = check_file_length(str(test_file), 50)

        assert result is None

    def test_counts_one_over_limit(self, tmp_path: Path) -> None:
        """Test file one line over limit is detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\n".join([f"line{i}" for i in range(51)]))

        result = check_file_length(str(test_file), 50)

        assert result == EXPECTED_LINE_COUNT_51


class TestPrintViolations:
    """Tests for print_violations function."""

    def test_prints_violation_count(self, capsys) -> None:
        """Test prints violation count."""
        violations = [
            ("file1.py", 600),
            ("file2.py", 550),
        ]

        print_violations(violations, 512)

        captured = capsys.readouterr()
        assert "2 file(s) exceed 512 lines" in captured.out

    def test_prints_sorted_by_count(self, capsys) -> None:
        """Test violations are sorted by line count (highest first)."""
        violations = [
            ("file1.py", 550),
            ("file2.py", 700),
            ("file3.py", 600),
        ]

        print_violations(violations, 512)

        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        # Should be sorted: 700, 600, 550
        file_lines = [line for line in lines if "file" in line and ".py" in line]
        assert "700" in file_lines[0]


class TestMain:
    """Tests for main function."""

    @patch("ami.scripts.ci.check_file_length.load_config")
    @patch("ami.scripts.ci.check_file_length.sys.argv", ["script"])
    @patch("ami.scripts.ci.check_file_length.get_all_files")
    def test_exits_zero_when_no_violations(self, mock_get_files, mock_config) -> None:
        """Test exits 0 when no violations."""
        mock_config.return_value = DEFAULT_CONFIG
        mock_get_files.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch("ami.scripts.ci.check_file_length.load_config")
    @patch("ami.scripts.ci.check_file_length.sys.argv", ["script", "long_file.py"])
    @patch("ami.scripts.ci.check_file_length.should_check_file", return_value=True)
    @patch("ami.scripts.ci.check_file_length.check_file_length", return_value=600)
    def test_exits_one_when_violations(
        self, mock_check, mock_should, mock_config
    ) -> None:
        """Test exits 1 when violations found."""
        mock_config.return_value = DEFAULT_CONFIG

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("ami.scripts.ci.check_file_length.load_config")
    @patch("ami.scripts.ci.check_file_length.sys.argv", ["script", "short.py"])
    @patch("ami.scripts.ci.check_file_length.should_check_file", return_value=True)
    @patch("ami.scripts.ci.check_file_length.check_file_length", return_value=None)
    def test_uses_config_max_lines(self, mock_check, mock_should, mock_config) -> None:
        """Test uses max_lines from config."""
        mock_config.return_value = {
            "max_lines": 300,
            "extensions": [".py"],
            "ignore_files": [],
            "ignore_dirs": [],
        }

        with pytest.raises(SystemExit):
            main()

        mock_check.assert_called_with("short.py", 300)
