"""Unit tests for the backup common paths module (common/paths.py)."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.backup.common import paths


class TestPaths:
    """Unit tests for the path utility functions."""

    def test_get_project_root(self):
        """Test finding project root via environment variable."""
        # Test with environment variable (cleanest approach)
        test_root = "/fake/project/root"
        with patch.dict(os.environ, {"AMI_PROJECT_ROOT": test_root}):
            root = paths.get_project_root()
            assert str(root) == test_root

    def test_get_project_root_from_file(self):
        """Test finding project root from file location works in real environment."""
        # Without env var, should find real project root
        # This works because we're running from within the project
        root = paths.get_project_root()
        # Should find a directory with pyproject.toml
        assert (root / "pyproject.toml").exists()

    @patch("ami.scripts.backup.common.paths.get_project_root")
    def test_setup_sys_path(self, mock_get_root):
        """Test that project root is added to sys.path."""
        mock_root = Path("/fake/root")
        mock_get_root.return_value = mock_root

        # Save original sys.path
        original_path = sys.path[:]
        try:
            paths.setup_sys_path()
            assert str(mock_root) in sys.path
            assert sys.path[0] == str(mock_root)
        finally:
            sys.path = original_path

    @patch("ami.scripts.backup.common.paths.get_project_root")
    @patch("pathlib.Path.exists")
    def test_find_gcloud_local(self, mock_exists, mock_get_root):
        """Test finding local gcloud binary."""
        mock_root = Path("/fake/root")
        mock_get_root.return_value = mock_root

        # Mock local gcloud existence
        mock_exists.return_value = True

        result = paths.find_gcloud()
        assert "/fake/root/.gcloud/google-cloud-sdk/bin/gcloud" in str(result)

    @patch("ami.scripts.backup.common.paths.get_project_root")
    @patch("shutil.which")
    def test_find_gcloud_system(self, mock_which, mock_get_root):
        """Test finding system gcloud binary when local is missing."""
        mock_root = Path("/fake/root")
        mock_get_root.return_value = mock_root

        # Use a real Path object for the check
        with patch.object(Path, "exists", return_value=False):
            mock_which.return_value = "/usr/bin/gcloud"
            result = paths.find_gcloud()
            assert result == "/usr/bin/gcloud"

    @patch("ami.scripts.backup.common.paths.get_project_root")
    @patch("shutil.which")
    def test_find_gcloud_not_found(self, mock_which, mock_get_root):
        """Test find_gcloud returns None when not found anywhere."""
        mock_root = Path("/fake/root")
        mock_get_root.return_value = mock_root

        with patch.object(Path, "exists", return_value=False):
            mock_which.return_value = None
            result = paths.find_gcloud()
            assert result is None


class TestIsProjectRootMarker:
    """Tests for _is_project_root_marker function."""

    def test_base_and_scripts_markers(self, tmp_path: Path):
        """Test returns True when base and scripts dirs exist."""
        (tmp_path / "base").mkdir()
        (tmp_path / "scripts").mkdir()

        result = paths._is_project_root_marker(tmp_path)

        assert result is True

    def test_pyproject_marker(self, tmp_path: Path):
        """Test returns True when pyproject.toml exists."""
        (tmp_path / "pyproject.toml").touch()

        result = paths._is_project_root_marker(tmp_path)

        assert result is True

    def test_no_markers(self, tmp_path: Path):
        """Test returns False when no markers exist."""
        result = paths._is_project_root_marker(tmp_path)

        assert result is False


class TestFindRootFromPath:
    """Tests for _find_root_from_path function."""

    def test_finds_root_in_parent(self, tmp_path: Path):
        """Test finds root when marker is in parent directory."""
        (tmp_path / "pyproject.toml").touch()
        child = tmp_path / "subdir" / "nested"
        child.mkdir(parents=True)

        result = paths._find_root_from_path(child)

        assert result == tmp_path

    def test_returns_none_when_no_root(self, tmp_path: Path):
        """Test returns None when no root markers found."""
        # tmp_path has no markers and walking up won't find any
        # We need to test this with an isolated path
        result = paths._find_root_from_path(Path("/"))

        assert result is None


class TestGetProjectRootEdgeCases:
    """Tests for edge cases in get_project_root function."""

    @patch("ami.scripts.backup.common.paths._find_root_from_path")
    def test_falls_back_to_cwd(self, mock_find_root, tmp_path: Path):
        """Test falls back to CWD when file location fails."""
        # Remove env var if set
        env_backup = os.environ.pop("AMI_PROJECT_ROOT", None)

        # Create marker in tmp_path
        (tmp_path / "pyproject.toml").touch()

        # First call (from __file__) fails, second (from cwd) succeeds
        mock_find_root.side_effect = [None, tmp_path]

        try:
            with patch.object(Path, "cwd", return_value=tmp_path):
                result = paths.get_project_root()
                # Should return tmp_path from the CWD fallback
                assert result == tmp_path
        finally:
            if env_backup:
                os.environ["AMI_PROJECT_ROOT"] = env_backup

    @patch("ami.scripts.backup.common.paths._find_root_from_path")
    def test_raises_when_not_found(self, mock_find_root):
        """Test raises RuntimeError when root not found anywhere."""
        env_backup = os.environ.pop("AMI_PROJECT_ROOT", None)

        # Both attempts return None
        mock_find_root.return_value = None

        try:
            with pytest.raises(RuntimeError) as exc_info:
                paths.get_project_root()

            assert "Could not find project root" in str(exc_info.value)
        finally:
            if env_backup:
                os.environ["AMI_PROJECT_ROOT"] = env_backup

    @patch("ami.scripts.backup.common.paths._find_root_from_path")
    def test_handles_exception_from_file_path(self, mock_find_root):
        """Test handles exception when finding root from __file__."""
        env_backup = os.environ.pop("AMI_PROJECT_ROOT", None)

        # First call raises, second returns valid path
        mock_find_root.side_effect = [Exception("Path error"), Path("/valid/root")]

        try:
            result = paths.get_project_root()
            assert result == Path("/valid/root")
        finally:
            if env_backup:
                os.environ["AMI_PROJECT_ROOT"] = env_backup

    @patch("ami.scripts.backup.common.paths._find_root_from_path")
    def test_handles_exception_from_cwd(self, mock_find_root):
        """Test handles exception when finding root from CWD."""
        env_backup = os.environ.pop("AMI_PROJECT_ROOT", None)

        # Both calls raise exceptions
        mock_find_root.side_effect = [Exception("First error"), Exception("CWD error")]

        try:
            with pytest.raises(RuntimeError):
                paths.get_project_root()
        finally:
            if env_backup:
                os.environ["AMI_PROJECT_ROOT"] = env_backup
