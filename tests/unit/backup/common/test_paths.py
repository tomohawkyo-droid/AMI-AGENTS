"""Unit tests for the backup common paths module (common/paths.py)."""

import sys
from pathlib import Path
from unittest.mock import patch

from ami.scripts.backup.common import paths


class TestPaths:
    """Unit tests for the path utility functions."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.resolve")
    def test_get_project_root(self, mock_resolve, mock_exists):
        """Test finding project root via 'base' directory marker."""
        # Mocking complex path traversal is tricky, so we'll mock the internal logic
        # if needed, but let's try to mock the specific check

        # Scenario: current path is scripts/backup/common/paths.py
        # root is 4 levels up
        mock_resolve.return_value = Path(
            "/home/ami/Projects/AMI-ORCHESTRATOR/scripts/backup/common/paths.py"
        )

        # mock_exists should return True when checking /home/ami/Projects/AMI-ORCHESTRATOR/base
        def side_effect_exists(path_obj):
            return (
                str(path_obj) == "/home/ami/Projects/AMI-ORCHESTRATOR/base"
                or str(path_obj) == "/home/ami/Projects/AMI-ORCHESTRATOR/scripts"
            )

        # Path objects are sometimes compared by identity or wrapped, so we use side_effect on the mock
        with patch.object(Path, "exists", side_effect=side_effect_exists):
            root = paths.get_project_root()
            assert str(root) == "/home/ami/Projects/AMI-ORCHESTRATOR"

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
