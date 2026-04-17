"""Unit tests for register_extensions bashrc + register_extensions flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.scripts.register_extensions import (
    _register_one,
    register_extensions,
    remove_bashrc_functions,
    update_bashrc_path,
)
from ami.scripts.shell.extension_registry import ResolvedExtension, Status


class TestUpdateBashrcPath:
    def test_noop_when_bashrc_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        update_bashrc_path(tmp_path / "bin")  # must not raise

    def test_adds_path_after_shebang(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".bashrc").write_text("#!/bin/bash\n# comment\nalias x=y\n")
        update_bashrc_path(tmp_path / "bin")
        content = (tmp_path / ".bashrc").read_text()
        assert "# AMI PATH" in content
        # PATH line placed after shebang/comments, before `alias`.
        lines = content.split("\n")
        ami_idx = next(i for i, ln in enumerate(lines) if "# AMI PATH" in ln)
        alias_idx = next(i for i, ln in enumerate(lines) if "alias x" in ln)
        assert ami_idx < alias_idx

    def test_replaces_existing_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".bashrc").write_text(
            '#!/bin/bash\nexport PATH="/old/bin:$PATH"  # AMI PATH\nalias x=y\n',
        )
        update_bashrc_path(tmp_path / "new-bin")
        content = (tmp_path / ".bashrc").read_text()
        assert "/old/bin" not in content
        assert "/new-bin" in content


class TestRemoveBashrcFunctions:
    def test_noop_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        remove_bashrc_functions()

    def test_removes_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".bashrc").write_text(
            "alias a=b\n"
            "# --- AMI AGENT EXTENSIONS START ---\n"
            "foo() { :; }\n"
            "# --- AMI AGENT EXTENSIONS END ---\n"
            "alias c=d\n",
        )
        remove_bashrc_functions()
        content = (tmp_path / ".bashrc").read_text()
        assert "AMI AGENT EXTENSIONS" not in content
        assert "foo()" not in content
        assert "alias a=b" in content
        assert "alias c=d" in content


class TestRegisterOne:
    def test_skips_when_already_in_place(self, tmp_path: Path) -> None:
        ami_root = tmp_path
        source = ami_root / "scripts" / "main.py"
        source.parent.mkdir(parents=True)
        source.write_text("x")
        bin_dir = ami_root / "bin"
        bin_dir.mkdir()
        # Pre-existing symlink pointing at source
        target = bin_dir / "my-cmd"
        target.symlink_to(source)

        ext = ResolvedExtension(
            entry={"name": "my-cmd", "binary": "scripts/main.py"},
            manifest_path=tmp_path / "manifest.yaml",
            status=Status.READY,
            reason="",
            version=None,
        )
        _register_one(ext, bin_dir, ami_root)
        # Still a symlink to the same source
        assert target.resolve() == source.resolve()

    def test_creates_symlink_for_non_py_binary(self, tmp_path: Path) -> None:
        ami_root = tmp_path
        source = ami_root / "scripts" / "main.sh"
        source.parent.mkdir(parents=True)
        source.write_text("#!/bin/sh\n")
        source.chmod(0o755)
        bin_dir = ami_root / "bin"
        bin_dir.mkdir()

        ext = ResolvedExtension(
            entry={"name": "my-cmd", "binary": "scripts/main.sh"},
            manifest_path=tmp_path / "manifest.yaml",
            status=Status.READY,
            reason="",
            version=None,
        )
        _register_one(ext, bin_dir, ami_root)
        assert (bin_dir / "my-cmd").is_symlink()


class TestRegisterExtensionsEntry:
    def test_handles_empty_manifests(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "pyproject.toml").touch()
        monkeypatch.setenv("AMI_ROOT", str(tmp_path))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with (
            patch(
                "ami.scripts.register_extensions.discover_manifests", return_value=[]
            ),
        ):
            register_extensions()
        out = capsys.readouterr().out
        assert "No extension.manifest.yaml files found" in out

    def test_counts_registered_and_skipped(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "pyproject.toml").touch()
        source_py = tmp_path / "scripts" / "main.py"
        source_py.parent.mkdir(parents=True)
        source_py.write_text("")
        monkeypatch.setenv("AMI_ROOT", str(tmp_path))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ready = ResolvedExtension(
            entry={"name": "go", "binary": "scripts/main.py"},
            manifest_path=tmp_path / "m.yaml",
            status=Status.READY,
            reason="",
            version=None,
        )
        unavail = ResolvedExtension(
            entry={"name": "skip", "binary": "scripts/skip.py"},
            manifest_path=tmp_path / "m.yaml",
            status=Status.UNAVAILABLE,
            reason="missing",
            version=None,
        )
        with (
            patch(
                "ami.scripts.register_extensions.discover_manifests",
                return_value=[MagicMock()],
            ),
            patch(
                "ami.scripts.register_extensions.resolve_extensions",
                return_value=[ready, unavail],
            ),
        ):
            register_extensions()
        out = capsys.readouterr().out
        assert "Registered 1" in out
        assert "Skipped 1" in out
