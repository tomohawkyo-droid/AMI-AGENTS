"""Unit tests for ami/cli/exec_utils.py."""

from unittest.mock import patch

from ami.cli.exec_utils import validate_executable_exists


class TestValidateExecutableExists:
    """Tests for validate_executable_exists function."""

    def test_empty_command_returns_none(self):
        """Test returns None for empty command list."""
        result = validate_executable_exists([])
        assert result is None

    def test_none_executable_returns_none(self):
        """Test returns None when first element is empty."""
        result = validate_executable_exists([""])
        assert result is None

    @patch("shutil.which")
    def test_executable_not_found_returns_none(self, mock_which):
        """Test returns None when executable not in PATH."""
        mock_which.return_value = None

        result = validate_executable_exists(["nonexistent_cmd"])

        assert result is None
        mock_which.assert_called_once_with("nonexistent_cmd")

    @patch("shutil.which")
    def test_executable_found_returns_updated_command(self, mock_which):
        """Test returns updated command with full path."""
        mock_which.return_value = "/usr/bin/python"

        result = validate_executable_exists(["python", "-c", "print('hello')"])

        assert result is not None
        assert result[0] == "/usr/bin/python"
        assert result[1] == "-c"
        assert result[2] == "print('hello')"

    @patch("shutil.which")
    def test_original_command_not_modified(self, mock_which):
        """Test original command list is not modified."""
        mock_which.return_value = "/usr/bin/python"

        original_cmd = ["python", "script.py"]
        result = validate_executable_exists(original_cmd)

        assert original_cmd[0] == "python"  # Original unchanged
        assert result[0] == "/usr/bin/python"  # Result has full path

    @patch("shutil.which")
    def test_single_element_command(self, mock_which):
        """Test works with single-element command."""
        mock_which.return_value = "/usr/bin/ls"

        result = validate_executable_exists(["ls"])

        assert result == ["/usr/bin/ls"]

    @patch("shutil.which")
    def test_command_with_spaces_in_args(self, mock_which):
        """Test handles command with spaces in arguments."""
        mock_which.return_value = "/usr/bin/echo"

        result = validate_executable_exists(["echo", "hello world", "test"])

        assert result is not None
        assert result[0] == "/usr/bin/echo"
        assert result[1] == "hello world"
        assert result[2] == "test"
