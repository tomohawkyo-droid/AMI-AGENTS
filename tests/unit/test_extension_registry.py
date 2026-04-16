"""Unit tests for ami.scripts.shell.extension_registry."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import ami.scripts.shell.extension_registry as reg
from ami.scripts.shell.extension_registry import (
    ExtensionEntry,
    Status,
    check_additional_deps,
    check_dep,
    discover_manifests,
    find_ami_root,
    validate_entry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_CATEGORIES = [
    "core",
    "enterprise",
    "dev",
    "infra",
    "docs",
    "agents",
]


def _make_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_manifest(directory: Path, data: dict) -> Path:
    manifest = directory / "extension.manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(yaml.dump(data, default_flow_style=False))
    return manifest


def _valid_entry(**overrides: object) -> ExtensionEntry:
    base: ExtensionEntry = {
        "name": "ami-test",
        "binary": "bin/test",
        "description": "A test extension",
        "category": "core",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class TestStatus:
    def test_values(self) -> None:
        assert Status.READY.value == "ready"
        assert Status.DEGRADED.value == "degraded"
        assert Status.UNAVAILABLE.value == "unavailable"
        assert Status.HIDDEN.value == "hidden"

    def test_members(self) -> None:
        expected = {
            Status.READY,
            Status.DEGRADED,
            Status.UNAVAILABLE,
            Status.HIDDEN,
        }
        assert set(Status) == expected


# ---------------------------------------------------------------------------
# find_ami_root
# ---------------------------------------------------------------------------


class TestFindAmiRoot:
    def test_uses_env_var(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"AMI_ROOT": str(tmp_path)}):
            assert find_ami_root() == tmp_path

    def test_walks_up_to_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").touch()
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        fake_file = nested / "fake.py"
        fake_file.touch()

        env = os.environ.copy()
        env.pop("AMI_ROOT", None)
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(reg, "__file__", str(fake_file)),
        ):
            result = find_ami_root()
            assert result == tmp_path

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        fake_file = tmp_path / "isolated" / "script.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.touch()

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(reg, "__file__", str(fake_file)),
            pytest.raises(
                RuntimeError,
                match="Cannot determine AMI_ROOT",
            ),
        ):
            find_ami_root()


# ---------------------------------------------------------------------------
# discover_manifests
# ---------------------------------------------------------------------------


class TestDiscoverManifests:
    def test_finds_manifests(self, tmp_path: Path) -> None:
        m1 = tmp_path / "a" / "extension.manifest.yaml"
        m2 = tmp_path / "b" / "extension.manifest.yaml"
        m1.parent.mkdir()
        m2.parent.mkdir()
        m1.touch()
        m2.touch()

        result = discover_manifests(tmp_path)
        assert result == sorted([m1, m2])

    def test_prunes_excluded_dirs(self, tmp_path: Path) -> None:
        for d in (".git", "node_modules", "target"):
            hidden = tmp_path / d
            hidden.mkdir()
            (hidden / "extension.manifest.yaml").touch()

        assert discover_manifests(tmp_path) == []

    def test_prunes_dot_prefixed_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden-dir"
        hidden.mkdir()
        (hidden / "extension.manifest.yaml").touch()

        assert discover_manifests(tmp_path) == []

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert discover_manifests(tmp_path) == []

    def test_nested_manifest(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        m = deep / "extension.manifest.yaml"
        m.touch()

        assert discover_manifests(tmp_path) == [m]

    def test_returns_sorted(self, tmp_path: Path) -> None:
        for name in ("z", "a", "m"):
            d = tmp_path / name
            d.mkdir()
            (d / "extension.manifest.yaml").touch()

        result = discover_manifests(tmp_path)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# validate_entry
# ---------------------------------------------------------------------------


class TestValidateEntry:
    def test_valid_entry(self, tmp_path: Path) -> None:
        entry = _valid_entry()
        path = tmp_path / "manifest.yaml"
        assert validate_entry(entry, path) == []

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        entry = {"name": "x"}
        errors = validate_entry(entry, tmp_path / "m.yaml")
        assert len(errors) >= 1
        assert "missing required fields" in errors[0]

    def test_unknown_fields(self, tmp_path: Path) -> None:
        entry = _valid_entry(bogus="wat")
        errors = validate_entry(entry, tmp_path / "m.yaml")
        assert len(errors) >= 1
        assert "unknown fields" in errors[0]
        assert "bogus" in errors[0]

    def test_short_description(self, tmp_path: Path) -> None:
        entry = _valid_entry(description="abc")
        errors = validate_entry(entry, tmp_path / "m.yaml")
        assert any("description too short" in e for e in errors)

    def test_timeout_exceeds_max(self, tmp_path: Path) -> None:
        entry = _valid_entry(check={"command": ["true"], "timeout": 10})
        errors = validate_entry(entry, tmp_path / "m.yaml")
        assert any("exceeds max" in e for e in errors)

    def test_timeout_at_max_is_ok(self, tmp_path: Path) -> None:
        entry = _valid_entry(check={"command": ["true"], "timeout": 5})
        errors = validate_entry(entry, tmp_path / "m.yaml")
        assert errors == []

    def test_all_known_optional_fields(self, tmp_path: Path) -> None:
        entry = _valid_entry(
            features=["a"],
            bannerPriority=100,
            hidden=False,
            container=None,
            installHint="make it",
            check={"command": ["true"]},
            deps=[],
        )
        path = tmp_path / "m.yaml"
        assert validate_entry(entry, path) == []


# ---------------------------------------------------------------------------
# check_dep
# ---------------------------------------------------------------------------


class TestCheckDep:
    def test_binary_exists(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "tool")
        dep = {"type": "binary", "path": "bin/tool"}
        assert check_dep(dep, tmp_path)

    def test_binary_missing(self, tmp_path: Path) -> None:
        dep = {"type": "binary", "path": "bin/nope"}
        assert not check_dep(dep, tmp_path)

    def test_binary_not_executable(self, tmp_path: Path) -> None:
        f = tmp_path / "bin" / "tool"
        f.parent.mkdir(parents=True)
        f.touch()
        f.chmod(0o644)
        dep = {"type": "binary", "path": "bin/tool"}
        assert not check_dep(dep, tmp_path)

    def test_submodule_exists(self, tmp_path: Path) -> None:
        sub = tmp_path / "projects" / "foo"
        sub.mkdir(parents=True)
        (sub / "file.txt").touch()
        dep = {"type": "submodule", "path": "projects/foo"}
        assert check_dep(dep, tmp_path)

    def test_submodule_empty(self, tmp_path: Path) -> None:
        sub = tmp_path / "projects" / "foo"
        sub.mkdir(parents=True)
        dep = {"type": "submodule", "path": "projects/foo"}
        assert not check_dep(dep, tmp_path)

    def test_submodule_missing(self, tmp_path: Path) -> None:
        dep = {"type": "submodule", "path": "nope"}
        assert not check_dep(dep, tmp_path)

    def test_file_exists(self, tmp_path: Path) -> None:
        (tmp_path / "data.txt").touch()
        dep = {"type": "file", "path": "data.txt"}
        assert check_dep(dep, tmp_path)

    def test_file_missing(self, tmp_path: Path) -> None:
        dep = {"type": "file", "path": "nope.txt"}
        assert not check_dep(dep, tmp_path)

    def test_system_package_found(self) -> None:
        mod_path = "ami.scripts.shell.extension_registry.shutil.which"
        with patch(mod_path, return_value="/usr/bin/ls"):
            dep = {"type": "system-package", "name": "ls"}
            assert check_dep(dep, Path("/"))

    def test_system_package_missing(self) -> None:
        mod_path = "ami.scripts.shell.extension_registry.shutil.which"
        with patch(mod_path, return_value=None):
            dep = {"type": "system-package", "name": "nope"}
            assert not check_dep(dep, Path("/"))

    def test_container_calls_check_container(self) -> None:
        mod_path = "ami.scripts.shell.extension_registry.check_container"
        with patch(mod_path, return_value=True):
            dep = {
                "type": "container",
                "name": "db",
                "container": "my-db",
            }
            assert check_dep(dep, Path("/"))

    def test_unknown_type(self, tmp_path: Path) -> None:
        dep = {"type": "magic", "path": "x"}
        assert not check_dep(dep, tmp_path)


# ---------------------------------------------------------------------------
# check_additional_deps
# ---------------------------------------------------------------------------


class TestCheckAdditionalDeps:
    def test_no_deps(self, tmp_path: Path) -> None:
        status, reason = check_additional_deps([], tmp_path)
        assert status == Status.READY
        assert reason == ""

    def test_required_missing(self, tmp_path: Path) -> None:
        deps = [
            {
                "name": "foo",
                "type": "file",
                "path": "nope",
                "required": True,
            }
        ]
        status, reason = check_additional_deps(deps, tmp_path)
        assert status == Status.UNAVAILABLE
        assert "foo" in reason

    def test_optional_missing(self, tmp_path: Path) -> None:
        deps = [
            {
                "name": "bar",
                "type": "file",
                "path": "nope",
                "required": False,
            }
        ]
        status, reason = check_additional_deps(deps, tmp_path)
        assert status == Status.DEGRADED
        assert "bar" in reason

    def test_all_present(self, tmp_path: Path) -> None:
        (tmp_path / "x").touch()
        deps = [
            {
                "name": "x",
                "type": "file",
                "path": "x",
                "required": True,
            }
        ]
        status, reason = check_additional_deps(deps, tmp_path)
        assert status == Status.READY
        assert reason == ""

    def test_multiple_optional_missing(self, tmp_path: Path) -> None:
        deps = [
            {
                "name": "a",
                "type": "file",
                "path": "nope-a",
                "required": False,
            },
            {
                "name": "b",
                "type": "file",
                "path": "nope-b",
                "required": False,
            },
        ]
        status, reason = check_additional_deps(deps, tmp_path)
        assert status == Status.DEGRADED
        assert "a" in reason
        assert "b" in reason


# ---------------------------------------------------------------------------
# run_check
