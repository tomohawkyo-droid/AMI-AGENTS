"""Unit tests for scripts/register_extensions module."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from ami.scripts.register_extensions import register_extensions


class TestRegisterExtensions:
    """Tests for register_extensions function."""

    @patch("ami.scripts.register_extensions.Path")
    def test_returns_early_when_config_not_found(self, mock_path, capsys) -> None:
        """Test returns early when extensions config not found."""
        mock_ext_config = MagicMock()
        mock_ext_config.exists.return_value = False

        mock_path.return_value = mock_ext_config
        mock_path.side_effect = (
            lambda x: mock_ext_config if "extensions" in str(x) else MagicMock()
        )

        # Need to patch Path for both config check and home
        with patch.object(Path, "home", return_value=Path("/tmp/test")):
            register_extensions()

        captured = capsys.readouterr()
        assert "not found" in captured.out

    @patch("ami.scripts.register_extensions.yaml")
    @patch("ami.scripts.register_extensions.Path")
    @patch("builtins.open", mock_open(read_data="extensions: []"))
    def test_returns_early_when_no_extensions(
        self, mock_path, mock_yaml, capsys
    ) -> None:
        """Test returns early when no extensions in config."""
        mock_ext_config = MagicMock()
        mock_ext_config.exists.return_value = True

        mock_path.return_value = mock_ext_config
        mock_path.cwd.return_value = Path("/test")
        mock_path.home.return_value = Path("/tmp/test")

        mock_yaml.safe_load.return_value = {"extensions": []}

        register_extensions()

        captured = capsys.readouterr()
        assert "No extensions found" in captured.out

    @patch("ami.scripts.register_extensions.subprocess.run")
    @patch("ami.scripts.register_extensions.yaml")
    @patch("ami.scripts.register_extensions.Path")
    def test_executes_extension_commands(
        self, mock_path, mock_yaml, mock_run, capsys, tmp_path
    ) -> None:
        """Test executes extension commands."""
        # Setup mocks
        mock_ext_config = MagicMock()
        mock_ext_config.exists.return_value = True

        bashrc = tmp_path / ".bashrc"
        bashrc.touch()

        mock_path.return_value = mock_ext_config
        mock_path.cwd.return_value = Path("/test")
        mock_path.home.return_value = tmp_path

        mock_yaml.safe_load.return_value = {"extensions": ["echo 'export FOO=bar'"]}

        mock_run.return_value = MagicMock(
            returncode=0, stdout="export FOO=bar", stderr=""
        )

        # Create a mock file handler
        file_content = {"content": ""}

        def mock_file_open(path, mode="r"):
            if "extensions" in str(path):
                return mock_open(read_data="extensions:\n  - echo 'export FOO=bar'")()
            elif mode == "r":
                return mock_open(read_data=file_content["content"])()
            else:  # write mode
                m = mock_open()()
                m.write = lambda x: file_content.update({"content": x})
                return m

        with patch("builtins.open", mock_file_open):
            register_extensions()

        # Verify subprocess was called
        mock_run.assert_called()

    @patch("ami.scripts.register_extensions.subprocess.run")
    @patch("ami.scripts.register_extensions.yaml")
    @patch("ami.scripts.register_extensions.Path")
    def test_handles_extension_error(
        self, mock_path, mock_yaml, mock_run, capsys
    ) -> None:
        """Test handles extension command error."""
        mock_ext_config = MagicMock()
        mock_ext_config.exists.return_value = True

        mock_path.return_value = mock_ext_config
        mock_path.cwd.return_value = Path("/test")
        mock_path.home.return_value = Path("/tmp/test")

        mock_yaml.safe_load.return_value = {"extensions": ["failing_command"]}

        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="command not found"
        )

        with patch(
            "builtins.open", mock_open(read_data="extensions:\n  - failing_command")
        ):
            register_extensions()

        captured = capsys.readouterr()
        assert "error" in captured.out.lower() or "No extensions found" in captured.out

    @patch("ami.scripts.register_extensions.subprocess.run")
    @patch("ami.scripts.register_extensions.yaml")
    @patch("ami.scripts.register_extensions.Path")
    def test_handles_exception_in_extension(
        self, mock_path, mock_yaml, mock_run, capsys
    ) -> None:
        """Test handles exception when executing extension."""
        mock_ext_config = MagicMock()
        mock_ext_config.exists.return_value = True

        mock_path.return_value = mock_ext_config
        mock_path.cwd.return_value = Path("/test")
        mock_path.home.return_value = Path("/tmp/test")

        mock_yaml.safe_load.return_value = {"extensions": ["bad_command"]}

        mock_run.side_effect = Exception("Subprocess failed")

        with patch(
            "builtins.open", mock_open(read_data="extensions:\n  - bad_command")
        ):
            register_extensions()

        captured = capsys.readouterr()
        assert "Error" in captured.out or "No extensions found" in captured.out

    @patch("ami.scripts.register_extensions.subprocess.run")
    @patch("ami.scripts.register_extensions.yaml")
    def test_removes_existing_block(self, mock_yaml, mock_run, tmp_path) -> None:
        """Test removes existing AMI block from bashrc."""
        mock_yaml.safe_load.return_value = {"extensions": ["echo 'export FOO=bar'"]}

        mock_run.return_value = MagicMock(
            returncode=0, stdout="export FOO=bar", stderr=""
        )

        # Create bashrc with existing block
        bashrc = tmp_path / ".bashrc"
        existing_content = """# Existing content
# --- AMI AGENT EXTENSIONS START ---
export OLD=value
# --- AMI AGENT EXTENSIONS END ---
# More content
"""
        bashrc.write_text(existing_content)

        # Create extensions config
        ext_config = tmp_path / "extensions.yaml"
        ext_config.write_text("extensions:\n  - echo 'export FOO=bar'")

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("ami.scripts.register_extensions.Path") as mock_path,
        ):
            mock_ext_config = MagicMock()
            mock_ext_config.exists.return_value = True

            # Configure path behavior
            def path_side_effect(arg):
                if "extensions" in str(arg):
                    return mock_ext_config
                return MagicMock()

            mock_path.side_effect = path_side_effect
            mock_path.home.return_value = tmp_path
            mock_path.cwd.return_value = tmp_path

            with patch("builtins.open") as mock_file:
                mock_file.return_value.__enter__ = lambda s: s
                mock_file.return_value.__exit__ = MagicMock(return_value=False)
                mock_file.return_value.read.return_value = existing_content

                register_extensions()

    @patch("ami.scripts.register_extensions.subprocess.run")
    @patch("ami.scripts.register_extensions.yaml")
    @patch("ami.scripts.register_extensions.Path")
    def test_creates_bashrc_if_not_exists(
        self, mock_path, mock_yaml, mock_run, tmp_path
    ) -> None:
        """Test creates bashrc content when file doesn't exist."""
        mock_ext_config = MagicMock()
        mock_ext_config.exists.return_value = True

        mock_bashrc = MagicMock()
        mock_bashrc.exists.return_value = False

        def path_side_effect(arg):
            if "extensions" in str(arg):
                return mock_ext_config
            return mock_bashrc

        mock_path.side_effect = path_side_effect
        mock_path.home.return_value = tmp_path
        mock_path.cwd.return_value = tmp_path

        mock_yaml.safe_load.return_value = {"extensions": ["echo 'test'"]}
        mock_run.return_value = MagicMock(returncode=0, stdout="test", stderr="")

        written_content = []

        def mock_open_func(path, mode="r"):
            m = MagicMock()
            m.__enter__ = lambda s: s
            m.__exit__ = MagicMock(return_value=False)
            if mode == "w":
                m.write = lambda x: written_content.append(x)
            else:
                m.read.return_value = ""
            return m

        with patch("builtins.open", mock_open_func):
            register_extensions()
