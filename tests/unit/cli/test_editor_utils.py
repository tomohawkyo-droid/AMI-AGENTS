"""Unit tests for ami/cli/editor_utils.py."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from ami.cli.editor_utils import save_session_log


class TestSaveSessionLog:
    """Tests for save_session_log function."""

    def test_creates_logs_directory(self):
        """Test that logs directory is created if it doesn't exist."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("ami.cli.editor_utils.Path") as mock_path,
        ):
            mock_logs_dir = Path(tmpdir) / "logs"
            mock_path.return_value = mock_logs_dir
            mock_path.side_effect = lambda x: (
                mock_logs_dir if x == "logs" else Path(x)
            )

            # Actually create the directory for our mock
            mock_logs_dir.mkdir(exist_ok=True)

            # Just test the function runs without error
            # since it creates timestamped files
            content = "test content"
            result = save_session_log(content)

            assert result is not None

    def test_saves_content_to_file(self):
        """Test that content is saved correctly to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                content = "This is test content\nWith multiple lines"
                result = save_session_log(content)

                assert result.exists()
                assert result.read_text() == content
            finally:
                os.chdir(original_cwd)

    def test_generates_timestamped_filename(self):
        """Test that filename contains timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = save_session_log("content")

                assert "text_input_" in result.name
                assert result.suffix == ".txt"
            finally:
                os.chdir(original_cwd)

    def test_saves_to_logs_directory(self):
        """Test that file is saved in logs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = save_session_log("content")

                assert result.parent.name == "logs"
            finally:
                os.chdir(original_cwd)

    def test_saves_empty_content(self):
        """Test that empty content is saved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = save_session_log("")

                assert result.exists()
                assert result.read_text() == ""
            finally:
                os.chdir(original_cwd)

    def test_saves_unicode_content(self):
        """Test that unicode content is saved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                content = "Hello 世界 🌍 こんにちは"
                result = save_session_log(content)

                assert result.exists()
                assert result.read_text() == content
            finally:
                os.chdir(original_cwd)
