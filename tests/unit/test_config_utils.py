"""Unit tests for config_utils module."""

from pathlib import Path
from unittest.mock import patch

from ami.config_utils import get_config_path, get_vendor_config_path


class TestGetConfigPath:
    """Tests for get_config_path function."""

    @patch("ami.config_utils.get_project_root")
    def test_get_config_path_returns_correct_path(self, mock_root) -> None:
        """Test that config path is constructed correctly."""
        mock_root.return_value = Path("/project")

        result = get_config_path("ruff.toml")

        assert result == Path("/project/res/config/ruff.toml")

    @patch("ami.config_utils.get_project_root")
    def test_get_config_path_mypy(self, mock_root) -> None:
        """Test getting mypy config path."""
        mock_root.return_value = Path("/opt/user/project")

        result = get_config_path("mypy.toml")

        assert result == Path("/opt/user/project/res/config/mypy.toml")

    @patch("ami.config_utils.get_project_root")
    def test_get_config_path_with_subdirectory(self, mock_root) -> None:
        """Test config path preserves filename with path separators."""
        mock_root.return_value = Path("/project")

        # Note: This passes filename as-is, doesn't handle subdirs
        result = get_config_path("patterns/banned_words.yaml")

        assert result == Path("/project/res/config/patterns/banned_words.yaml")


class TestGetVendorConfigPath:
    """Tests for get_vendor_config_path function."""

    @patch("ami.config_utils.get_project_root")
    def test_get_vendor_config_path_cuda(self, mock_root) -> None:
        """Test getting CUDA vendor config path."""
        mock_root.return_value = Path("/project")

        result = get_vendor_config_path("sources-cuda.toml")

        assert result == Path("/project/res/config/vendor/sources-cuda.toml")

    @patch("ami.config_utils.get_project_root")
    def test_get_vendor_config_path_rocm(self, mock_root) -> None:
        """Test getting ROCm vendor config path."""
        mock_root.return_value = Path("/opt/user/project")

        result = get_vendor_config_path("requirements-rocm.txt")

        assert result == Path(
            "/opt/user/project/res/config/vendor/requirements-rocm.txt"
        )

    @patch("ami.config_utils.get_project_root")
    def test_get_vendor_config_path_mps(self, mock_root) -> None:
        """Test getting MPS (Apple Silicon) vendor config path."""
        mock_root.return_value = Path("/project")

        result = get_vendor_config_path("sources-mps.toml")

        assert result == Path("/project/res/config/vendor/sources-mps.toml")
