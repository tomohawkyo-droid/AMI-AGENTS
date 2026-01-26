"""Unit tests for the backup archiver module (create/archiver.py)."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ami.scripts.backup.create import archiver


class TestArchiver:
    """Unit tests for the archiver functions."""

    def test_should_exclude_path_git_directory(self):
        """Test that git directories are excluded."""
        root_dir = Path("/project")
        git_path = root_dir / ".git"
        assert archiver._should_exclude_path(git_path, root_dir) is True

    def test_should_exclude_path_subdir_venv(self):
        """Test that .venv in subdirectories are INCLUDED (no longer excluded)."""
        root_dir = Path("/project")
        sub_venv_path = root_dir / "subdir" / ".venv"
        assert archiver._should_exclude_path(sub_venv_path, root_dir) is False

    def test_should_include_root_venv(self):
        """Test that .venv at root is NOT excluded (only subdirectories)."""
        root_dir = Path("/project")
        root_venv_path = root_dir / ".venv"
        assert archiver._should_exclude_path(root_venv_path, root_dir) is False

    def test_should_exclude_path_node_modules(self):
        """Test that node_modules directories are INCLUDED (no longer excluded)."""
        root_dir = Path("/project")
        node_modules_path = root_dir / "node_modules"
        assert archiver._should_exclude_path(node_modules_path, root_dir) is False

    def test_should_exclude_path_pycache(self):
        """Test that __pycache__ directories are excluded."""
        root_dir = Path("/project")
        pycache_path = root_dir / "__pycache__"
        assert archiver._should_exclude_path(pycache_path, root_dir) is True

    def test_should_exclude_path_pyc_files(self):
        """Test that .pyc files are excluded."""
        root_dir = Path("/project")
        pyc_path = root_dir / "file.pyc"
        assert archiver._should_exclude_path(pyc_path, root_dir) is True

    def test_should_exclude_path_outside_root(self):
        """Test that paths outside root are excluded."""
        root_dir = Path("/project")
        other_path = Path("/other/file.txt")
        assert archiver._should_exclude_path(other_path, root_dir) is True

    def test_should_include_normal_file(self):
        """Test that normal files within root are included."""
        root_dir = Path("/project")
        normal_path = root_dir / "normal_file.txt"
        assert archiver._should_exclude_path(normal_path, root_dir) is False

    def test_illegal_filename_filtering(self):
        """Test that filenames with control characters are identified as illegal."""
        assert archiver._is_illegal_filename("normal.txt") is False
        assert archiver._is_illegal_filename("file\033.txt") is True
        assert archiver._is_illegal_filename("file\nname.txt") is True
        assert archiver._is_illegal_filename("file\r.txt") is True

    @patch("ami.scripts.backup.create.archiver.asyncio.create_subprocess_exec")
    @patch("ami.scripts.backup.create.archiver._get_files_to_backup")
    @patch("pathlib.Path.rename")
    async def test_create_zip_archive_success(
        self,
        mock_rename,
        mock_get_files,
        mock_exec,
    ):
        """Test successful archive creation."""
        mock_get_files.return_value = [Path("/repo/file1.txt")]

        # Mock process result correctly for asyncio
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process

        # Use nested patches to reduce argument count
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat_obj = MagicMock()
            mock_stat_obj.st_size = 1024
            mock_stat.return_value = mock_stat_obj

            # Use a real source directory from temp
            with tempfile.TemporaryDirectory() as source_dir:
                root = Path(source_dir)
                (root / "file1.txt").touch()
                mock_get_files.return_value = [root / "file1.txt"]

                result = await archiver.create_zip_archive(root)
                assert "backup.tar.zst" in str(result)
                assert mock_exec.called

    def test_complete_exclusion_logic(self):
        """Test the complete exclusion logic with various path types."""
        root_dir = Path("/project")

        # Test cases: (path, should_be_excluded)
        test_cases = [
            # Should be excluded
            (root_dir / ".git", True),
            (root_dir / "sub" / ".git", True),
            (root_dir / "__pycache__", True),
            (root_dir / "file.pyc", True),
            (Path("/other/location"), True),  # Outside root should be excluded
            # Should NOT be excluded
            (root_dir / ".venv", False),  # Root .venv should NOT be excluded
            (root_dir / "sub" / ".venv", False),  # Subdir .venv should now be INCLUDED
            (root_dir / "node_modules", False),  # node_modules should now be INCLUDED
            (root_dir / "normal_file.txt", False),
            (root_dir / "subdir" / "normal_file.txt", False),
            (
                root_dir / "subdir" / ".venv" / "file.txt",
                False,
            ),  # .venv subdirs should be INCLUDED
        ]

        for test_path, expected_exclusion in test_cases:
            result = archiver._should_exclude_path(test_path, root_dir)
            assert (
                result == expected_exclusion
            ), f"Path {test_path} exclusion check failed. Expected {expected_exclusion}, got {result}"
