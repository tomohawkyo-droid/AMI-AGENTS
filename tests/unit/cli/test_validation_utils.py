"""Unit tests for ami/cli/validation_utils.py."""

import tempfile
from pathlib import Path

from ami.cli.validation_utils import validate_path_and_return_code, validate_path_exists


class TestValidatePathExists:
    """Tests for validate_path_exists function."""

    def test_path_exists_with_string(self):
        """Test returns True for existing path as string."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_path_exists(f.name)
            assert result is True

    def test_path_exists_with_path_object(self):
        """Test returns True for existing path as Path object."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_path_exists(Path(f.name))
            assert result is True

    def test_path_not_exists(self):
        """Test returns False for non-existing path."""
        result = validate_path_exists("/nonexistent/path/to/file")
        assert result is False

    def test_directory_exists(self):
        """Test returns True for existing directory."""
        with tempfile.TemporaryDirectory() as d:
            result = validate_path_exists(d)
            assert result is True


class TestValidatePathAndReturnCode:
    """Tests for validate_path_and_return_code function."""

    def test_none_path_returns_1(self):
        """Test returns 1 for None path."""
        result = validate_path_and_return_code(None)
        assert result == 1

    def test_existing_path_returns_0(self):
        """Test returns 0 for existing path."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_path_and_return_code(f.name)
            assert result == 0

    def test_nonexistent_path_returns_1(self):
        """Test returns 1 for non-existing path."""
        result = validate_path_and_return_code("/nonexistent/path")
        assert result == 1

    def test_path_object_works(self):
        """Test works with Path objects."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_path_and_return_code(Path(f.name))
            assert result == 0

    def test_existing_directory_returns_0(self):
        """Test returns 0 for existing directory."""
        with tempfile.TemporaryDirectory() as d:
            result = validate_path_and_return_code(d)
            assert result == 0
