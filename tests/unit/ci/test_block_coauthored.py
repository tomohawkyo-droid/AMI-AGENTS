"""Unit tests for ci/block_coauthored module."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from ami.scripts.ci.block_coauthored import DEFAULT_CONFIG, load_config, main


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_has_forbidden_patterns(self) -> None:
        """Test DEFAULT_CONFIG has forbidden_patterns."""
        assert "forbidden_patterns" in DEFAULT_CONFIG
        assert len(DEFAULT_CONFIG["forbidden_patterns"]) > 0

    def test_has_error_message(self) -> None:
        """Test DEFAULT_CONFIG has error_message."""
        assert "error_message" in DEFAULT_CONFIG
        assert "Co-authored" in DEFAULT_CONFIG["error_message"]

    def test_forbidden_patterns_include_coauthored(self) -> None:
        """Test forbidden patterns include co-authored variations."""
        patterns = DEFAULT_CONFIG["forbidden_patterns"]
        assert any("Co-authored-by" in p for p in patterns)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_default_when_file_missing(self) -> None:
        """Test returns default config when file doesn't exist."""
        with patch(
            "ami.scripts.ci.block_coauthored.os.path.exists", return_value=False
        ):
            config = load_config()

        assert config == DEFAULT_CONFIG

    def test_loads_from_file(self, tmp_path: Path) -> None:
        """Test loads config from file when it exists."""
        config_content = """
forbidden_patterns:
  - "custom-pattern"
error_message: "Custom error"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config["forbidden_patterns"] == ["custom-pattern"]
        assert config["error_message"] == "Custom error"

    @patch("ami.scripts.ci.block_coauthored.os.path.exists", return_value=True)
    def test_handles_empty_file(self, mock_exists) -> None:
        """Test handles empty config file."""
        with patch("builtins.open", mock_open(read_data="")):
            config = load_config()

        # yaml.safe_load returns None for empty file
        assert config is None


class TestMain:
    """Tests for main function."""

    @patch("ami.scripts.ci.block_coauthored.sys.argv", ["script"])
    def test_exits_without_commit_message_file(self) -> None:
        """Test exits with error when no commit message file provided."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("ami.scripts.ci.block_coauthored.sys.argv", ["script", "nonexistent.txt"])
    @patch("ami.scripts.ci.block_coauthored.load_config")
    def test_exits_when_file_not_found(self, mock_config) -> None:
        """Test exits with error when commit message file not found."""
        mock_config.return_value = DEFAULT_CONFIG

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_exits_zero_for_clean_commit(self, tmp_path: Path) -> None:
        """Test exits 0 for commit without forbidden patterns."""
        commit_file = tmp_path / "commit_msg.txt"
        commit_file.write_text(
            "feat: Add new feature\n\nThis is a clean commit message."
        )

        with (
            patch(
                "ami.scripts.ci.block_coauthored.sys.argv", ["script", str(commit_file)]
            ),
            patch(
                "ami.scripts.ci.block_coauthored.load_config",
                return_value=DEFAULT_CONFIG,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0

    def test_exits_one_for_coauthored_commit(self, tmp_path: Path) -> None:
        """Test exits 1 for commit with Co-authored-by."""
        commit_file = tmp_path / "commit_msg.txt"
        commit_file.write_text("feat: Add feature\n\nCo-authored-by: Someone")

        with (
            patch(
                "ami.scripts.ci.block_coauthored.sys.argv", ["script", str(commit_file)]
            ),
            patch(
                "ami.scripts.ci.block_coauthored.load_config",
                return_value=DEFAULT_CONFIG,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_detects_lowercase_coauthored(self, tmp_path: Path) -> None:
        """Test detects lowercase co-authored-by."""
        commit_file = tmp_path / "commit_msg.txt"
        commit_file.write_text("feat: Add feature\n\nco-authored-by: someone")

        with (
            patch(
                "ami.scripts.ci.block_coauthored.sys.argv", ["script", str(commit_file)]
            ),
            patch(
                "ami.scripts.ci.block_coauthored.load_config",
                return_value=DEFAULT_CONFIG,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_uses_custom_patterns(self, tmp_path: Path) -> None:
        """Test uses custom forbidden patterns from config."""
        commit_file = tmp_path / "commit_msg.txt"
        commit_file.write_text("feat: This contains FORBIDDEN text")

        custom_config = {
            "forbidden_patterns": ["FORBIDDEN"],
            "error_message": "Custom error",
        }

        with (
            patch(
                "ami.scripts.ci.block_coauthored.sys.argv", ["script", str(commit_file)]
            ),
            patch(
                "ami.scripts.ci.block_coauthored.load_config",
                return_value=custom_config,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
