"""Unit tests for ami.scripts.register_extensions."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ami.scripts.register_extensions import (
    create_symlink,
    create_wrapper,
    fix_stale_shebang,
    register_extensions,
)


class TestCreateWrapper:
    """Test wrapper script creation."""

    def test_creates_executable_wrapper(self, tmp_path: Path) -> None:
        target = tmp_path / "test-cmd"
        create_wrapper(target, tmp_path, "scripts/test.py")
        assert target.exists()
        assert os.access(target, os.X_OK)
        content = target.read_text()
        assert "ami-run" in content
        assert "scripts/test.py" in content

    def test_wrapper_is_bash_script(self, tmp_path: Path) -> None:
        target = tmp_path / "cmd"
        create_wrapper(target, tmp_path, "s.py")
        content = target.read_text()
        assert content.startswith("#!/usr/bin/env bash")


class TestCreateSymlink:
    """Test symlink creation."""

    def test_creates_symlink(self, tmp_path: Path) -> None:
        target = tmp_path / "real-binary"
        target.write_text("binary")
        link = tmp_path / "link"
        create_symlink(link, target)
        assert link.is_symlink()
        assert link.resolve() == target.resolve()

    def test_replaces_existing_symlink(self, tmp_path: Path) -> None:
        target1 = tmp_path / "bin1"
        target2 = tmp_path / "bin2"
        target1.write_text("1")
        target2.write_text("2")
        link = tmp_path / "link"
        create_symlink(link, target1)
        create_symlink(link, target2)
        assert link.resolve() == target2.resolve()


class TestFixStaleShebang:
    """Test stale shebang fixing."""

    def test_fixes_nonexistent_python_path(self, tmp_path: Path) -> None:
        script = tmp_path / "script"
        script.write_text("#!/nonexistent/python3\nimport sys\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        fix_stale_shebang(script, tmp_path)
        content = script.read_text()
        assert str(tmp_path / ".venv" / "bin" / "python3") in content

    def test_skips_valid_shebang(self, tmp_path: Path) -> None:
        venv_python = tmp_path / ".venv" / "bin" / "python3"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("")
        script = tmp_path / "script"
        original = f"#!{venv_python}\nimport sys\n"
        script.write_text(original)
        fix_stale_shebang(script, tmp_path)
        assert script.read_text() == original

    def test_skips_nonexistent_file(self, tmp_path: Path) -> None:
        fix_stale_shebang(tmp_path / "nope", tmp_path)

    def test_skips_non_python_shebang(self, tmp_path: Path) -> None:
        script = tmp_path / "script"
        original = "#!/usr/bin/env bash\necho hi\n"
        script.write_text(original)
        fix_stale_shebang(script, tmp_path)
        assert script.read_text() == original


class TestRegisterExtensions:
    """Test the full registration pipeline."""

    def test_discovers_and_registers(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that manifests are discovered and extensions registered."""
        # Create a manifest
        manifest_dir = tmp_path / "ami" / "scripts" / "bin"
        manifest_dir.mkdir(parents=True)
        manifest = {
            "extensions": [
                {
                    "name": "test-ext",
                    "binary": "ami/scripts/bin/test-ext",
                    "description": "A test extension",
                    "category": "core",
                },
            ],
        }
        (manifest_dir / "extension.manifest.yaml").write_text(yaml.dump(manifest))

        # Create the binary
        binary = tmp_path / "ami" / "scripts" / "bin" / "test-ext"
        binary.write_text("#!/bin/bash\necho hi")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        # Create pyproject.toml so find_ami_root works
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")

        # Create .boot-linux/bin
        boot_bin = tmp_path / ".boot-linux" / "bin"
        boot_bin.mkdir(parents=True)

        # Create bashrc
        (tmp_path / ".bashrc").write_text("")

        with (
            patch.dict(os.environ, {"AMI_ROOT": str(tmp_path)}),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            register_extensions()

        captured = capsys.readouterr()
        assert "test-ext" in captured.out

    def test_warns_when_no_manifests(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test warning when no manifests found."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")
        boot_bin = tmp_path / ".boot-linux" / "bin"
        boot_bin.mkdir(parents=True)

        with patch.dict(os.environ, {"AMI_ROOT": str(tmp_path)}):
            register_extensions()

        captured = capsys.readouterr()
        assert "no extension" in captured.out.lower()
