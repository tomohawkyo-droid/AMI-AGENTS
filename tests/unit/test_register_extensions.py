"""Unit tests for scripts/register_extensions module."""

import stat
from pathlib import Path
from unittest.mock import patch

import yaml

from ami.scripts.register_extensions import (
    create_symlink,
    create_wrapper,
    register_extensions,
    remove_bashrc_functions,
    update_bashrc_path,
)


class TestCreateWrapper:
    """Tests for create_wrapper function."""

    def test_creates_executable_wrapper(self, tmp_path) -> None:
        """Test wrapper script is created with correct content and permissions."""
        target = tmp_path / "my-cmd"
        ami_root = Path("/opt/ami")
        create_wrapper(target, ami_root, "ami/scripts/bin/my_script.py")

        assert target.exists()
        content = target.read_text()
        assert "#!/usr/bin/env bash" in content
        assert "ami-run" in content
        assert "ami/scripts/bin/my_script.py" in content
        assert target.stat().st_mode & stat.S_IXUSR


class TestCreateSymlink:
    """Tests for create_symlink function."""

    def test_creates_symlink(self, tmp_path) -> None:
        """Test symlink is created pointing to target."""
        target = tmp_path / "real-binary"
        target.write_text("binary")
        link = tmp_path / "my-link"

        create_symlink(link, target)

        assert link.is_symlink()
        assert link.resolve() == target.resolve()

    def test_replaces_existing_symlink(self, tmp_path) -> None:
        """Test existing symlink is replaced."""
        old_target = tmp_path / "old"
        old_target.write_text("old")
        new_target = tmp_path / "new"
        new_target.write_text("new")
        link = tmp_path / "my-link"

        create_symlink(link, old_target)
        create_symlink(link, new_target)

        assert link.resolve() == new_target.resolve()


class TestRegisterExtensions:
    """Tests for register_extensions function."""

    def test_returns_early_when_config_not_found(self, tmp_path, capsys) -> None:
        """Test returns early when extensions config not found."""
        with patch("ami.scripts.register_extensions.Path") as mock_path:
            mock_path.cwd.return_value = tmp_path
            mock_path.home.return_value = tmp_path
            # ext_config won't exist because tmp_path has no ami/config/extensions.yaml
            # But Path is mocked, so we need the / operator to return real paths
            mock_path.__truediv__ = Path.__truediv__

        # Use real paths - config file doesn't exist in tmp_path
        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            register_extensions()

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_creates_symlinks_for_binaries(self, tmp_path, capsys) -> None:
        """Test creates symlinks for non-.py binaries."""
        # Setup extensions config
        config_dir = tmp_path / "ami" / "config"
        config_dir.mkdir(parents=True)
        config = {
            "extensions": [
                {"name": "test-cmd", "binary": "some/binary"},
            ]
        }
        (config_dir / "extensions.yaml").write_text(yaml.dump(config))

        # Create the binary target
        binary = tmp_path / "some" / "binary"
        binary.parent.mkdir(parents=True)
        binary.write_text("binary")

        # Create bashrc so update_bashrc_path works
        (tmp_path / ".bashrc").write_text("")

        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            register_extensions()

        bin_dir = tmp_path / ".boot-linux" / "bin"
        link = bin_dir / "test-cmd"
        assert link.is_symlink()

    def test_creates_wrappers_for_python_scripts(self, tmp_path, capsys) -> None:
        """Test creates wrapper scripts for .py binaries."""
        config_dir = tmp_path / "ami" / "config"
        config_dir.mkdir(parents=True)
        config = {
            "extensions": [
                {"name": "test-py", "binary": "ami/scripts/test.py"},
            ]
        }
        (config_dir / "extensions.yaml").write_text(yaml.dump(config))
        (tmp_path / ".bashrc").write_text("")

        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            register_extensions()

        wrapper = tmp_path / ".boot-linux" / "bin" / "test-py"
        assert wrapper.exists()
        assert "ami-run" in wrapper.read_text()

    def test_skips_invalid_entries(self, tmp_path, capsys) -> None:
        """Test skips entries missing name or binary."""
        config_dir = tmp_path / "ami" / "config"
        config_dir.mkdir(parents=True)
        config = {
            "extensions": [
                {"name": "valid", "binary": "bin/valid"},
                {"name": "no-binary"},
                {"binary": "no-name"},
            ]
        }
        (config_dir / "extensions.yaml").write_text(yaml.dump(config))
        (tmp_path / ".bashrc").write_text("")

        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            register_extensions()

        captured = capsys.readouterr()
        assert "Invalid" in captured.out


class TestUpdateBashrcPath:
    """Tests for update_bashrc_path function."""

    def test_adds_path_to_bashrc(self, tmp_path) -> None:
        """Test PATH export is added to bashrc."""
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("# existing content\n")
        bin_dir = tmp_path / ".boot-linux" / "bin"

        with patch.object(Path, "home", return_value=tmp_path):
            update_bashrc_path(bin_dir)

        content = bashrc.read_text()
        assert "# AMI PATH" in content
        assert str(bin_dir) in content

    def test_replaces_existing_path_marker(self, tmp_path) -> None:
        """Test existing AMI PATH marker is replaced, not duplicated."""
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text('export PATH="/old/path:$PATH"  # AMI PATH\n# other\n')
        bin_dir = tmp_path / ".boot-linux" / "bin"

        with patch.object(Path, "home", return_value=tmp_path):
            update_bashrc_path(bin_dir)

        content = bashrc.read_text()
        assert content.count("# AMI PATH") == 1
        assert "/old/path" not in content
        assert str(bin_dir) in content

    def test_skips_if_no_bashrc(self, tmp_path) -> None:
        """Test does nothing when bashrc doesn't exist."""
        bin_dir = tmp_path / ".boot-linux" / "bin"

        with patch.object(Path, "home", return_value=tmp_path):
            update_bashrc_path(bin_dir)

        assert not (tmp_path / ".bashrc").exists()


class TestRemoveBashrcFunctions:
    """Tests for remove_bashrc_functions function."""

    def test_removes_existing_block(self, tmp_path) -> None:
        """Test removes AMI AGENT EXTENSIONS block from bashrc."""
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text(
            "# before\n"
            "# --- AMI AGENT EXTENSIONS START ---\n"
            "export OLD=value\n"
            "# --- AMI AGENT EXTENSIONS END ---\n"
            "# after\n"
        )

        with patch.object(Path, "home", return_value=tmp_path):
            remove_bashrc_functions()

        content = bashrc.read_text()
        assert "AMI AGENT EXTENSIONS" not in content
        assert "# before" in content
        assert "# after" in content

    def test_noop_when_no_block(self, tmp_path) -> None:
        """Test does nothing when no AMI block exists."""
        bashrc = tmp_path / ".bashrc"
        original = "# just normal content\nexport FOO=bar\n"
        bashrc.write_text(original)

        with patch.object(Path, "home", return_value=tmp_path):
            remove_bashrc_functions()

        assert bashrc.read_text() == original

    def test_skips_if_no_bashrc(self, tmp_path) -> None:
        """Test does nothing when bashrc doesn't exist."""
        with patch.object(Path, "home", return_value=tmp_path):
            remove_bashrc_functions()

        assert not (tmp_path / ".bashrc").exists()
