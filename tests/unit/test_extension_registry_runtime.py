"""Unit tests for ami.scripts.shell.extension_registry."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml

import ami.scripts.shell.extension_registry as reg
from ami.scripts.shell.extension_registry import (
    DEFAULT_CATEGORY_ORDER,
    DEFAULT_CATEGORY_PROPS,
    EXCLUDE_DIRS,
    KNOWN_FIELDS,
    REQUIRED_FIELDS,
    ExtensionEntry,
    ResolvedExtension,
    Status,
    get_container_runtime,
    group_by_category,
    resolve_extensions,
    run_check,
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


_RUN_PATH = "ami.scripts.shell.extension_registry.subprocess.run"


class TestRunCheck:
    def test_no_check_block(self, tmp_path: Path) -> None:
        entry = _valid_entry()
        ok, version = run_check(entry, tmp_path)
        assert ok is True
        assert version is None

    def test_healthy_with_version(self, tmp_path: Path) -> None:
        entry = _valid_entry(
            check={
                "command": ["{binary}", "--version"],
                "healthExpect": "myapp",
                "versionPattern": r"v(\d+\.\d+\.\d+)",
            }
        )
        with patch(_RUN_PATH) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="myapp v1.2.3\n",
                stderr="",
            )
            ok, version = run_check(entry, tmp_path)

        assert ok is True
        assert version == "1.2.3"

    def test_unhealthy(self, tmp_path: Path) -> None:
        entry = _valid_entry(
            check={
                "command": ["{binary}"],
                "healthExpect": "expected-string",
            }
        )
        with patch(_RUN_PATH) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="something else\n",
                stderr="",
            )
            ok, _version = run_check(entry, tmp_path)

        assert ok is False

    def test_timeout(self, tmp_path: Path) -> None:
        entry = _valid_entry(check={"command": ["{binary}"], "timeout": 1})
        with patch(
            _RUN_PATH,
            side_effect=subprocess.TimeoutExpired(cmd=["x"], timeout=1),
        ):
            ok, version = run_check(entry, tmp_path)

        assert ok is False
        assert version is None

    def test_os_error(self, tmp_path: Path) -> None:
        entry = _valid_entry(check={"command": ["{binary}"]})
        with patch(
            _RUN_PATH,
            side_effect=OSError("no such file"),
        ):
            ok, version = run_check(entry, tmp_path)

        assert ok is False
        assert version is None

    def test_version_extraction_no_match(self, tmp_path: Path) -> None:
        entry = _valid_entry(
            check={
                "command": ["{binary}"],
                "versionPattern": r"v(\d+\.\d+)",
            }
        )
        with patch(_RUN_PATH) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="no version here\n",
                stderr="",
            )
            ok, version = run_check(entry, tmp_path)

        assert ok is True
        assert version is None

    def test_binary_placeholder_replaced(self, tmp_path: Path) -> None:
        entry = _valid_entry(
            binary="bin/tool",
            check={"command": ["{binary}", "--help"]},
        )
        with patch(_RUN_PATH) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_check(entry, tmp_path)

        called_cmd = mock_run.call_args[0][0]
        expected = str(tmp_path / "bin" / "tool")
        assert called_cmd[0] == expected

    def test_timeout_capped_at_five(self, tmp_path: Path) -> None:
        entry = _valid_entry(check={"command": ["{binary}"], "timeout": 99})
        with patch(_RUN_PATH) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_check(entry, tmp_path)

        max_timeout = reg._MAX_CHECK_TIMEOUT
        assert mock_run.call_args[1]["timeout"] == max_timeout


# ---------------------------------------------------------------------------
# resolve_extensions
# ---------------------------------------------------------------------------


class TestResolveExtensions:
    def test_valid_manifest(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "tool")
        manifest = _write_manifest(
            tmp_path / "ext",
            {"extensions": [_valid_entry(binary="bin/tool")]},
        )
        result = resolve_extensions([manifest], tmp_path)
        assert len(result) == 1
        assert result[0].status == Status.READY
        assert result[0].entry["name"] == "ami-test"

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        manifest = tmp_path / "bad" / "extension.manifest.yaml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{{invalid yaml::")
        result = resolve_extensions([manifest], tmp_path)
        assert result == []

    def test_duplicate_names(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "tool")
        m1 = _write_manifest(
            tmp_path / "a",
            {"extensions": [_valid_entry(binary="bin/tool")]},
        )
        m2 = _write_manifest(
            tmp_path / "b",
            {"extensions": [_valid_entry(binary="bin/tool")]},
        )
        result = resolve_extensions([m1, m2], tmp_path)
        assert len(result) == 1

    def test_missing_binary(self, tmp_path: Path) -> None:
        manifest = _write_manifest(
            tmp_path / "ext",
            {"extensions": [_valid_entry(binary="bin/missing")]},
        )
        result = resolve_extensions([manifest], tmp_path)
        assert len(result) == 1
        assert result[0].status == Status.UNAVAILABLE
        assert "binary not found" in result[0].reason

    def test_missing_binary_with_install_hint(self, tmp_path: Path) -> None:
        manifest = _write_manifest(
            tmp_path / "ext",
            {
                "extensions": [
                    _valid_entry(
                        binary="bin/missing",
                        installHint="make it",
                    )
                ]
            },
        )
        result = resolve_extensions([manifest], tmp_path)
        assert result[0].status == Status.UNAVAILABLE
        assert "install: make it" in result[0].reason

    def test_hidden_extension(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "tool")
        manifest = _write_manifest(
            tmp_path / "ext",
            {"extensions": [_valid_entry(binary="bin/tool", hidden=True)]},
        )
        result = resolve_extensions([manifest], tmp_path)
        assert len(result) == 1
        assert result[0].status == Status.HIDDEN

    def test_py_binary_check(self, tmp_path: Path) -> None:
        py_file = tmp_path / "scripts" / "tool.py"
        py_file.parent.mkdir(parents=True)
        py_file.touch()
        manifest = _write_manifest(
            tmp_path / "ext",
            {"extensions": [_valid_entry(binary="scripts/tool.py")]},
        )
        result = resolve_extensions([manifest], tmp_path)
        assert result[0].status == Status.READY

    def test_empty_extensions_list(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "ext", {"extensions": []})
        result = resolve_extensions([manifest], tmp_path)
        assert result == []

    def test_no_extensions_key(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "ext", {"other": "data"})
        result = resolve_extensions([manifest], tmp_path)
        assert result == []

    def test_invalid_entry_skipped(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "good")
        manifest = _write_manifest(
            tmp_path / "ext",
            {
                "extensions": [
                    {"name": "bad"},
                    _valid_entry(name="ami-good", binary="bin/good"),
                ]
            },
        )
        result = resolve_extensions([manifest], tmp_path)
        assert len(result) == 1
        assert result[0].entry["name"] == "ami-good"

    def test_required_dep_missing_is_unavailable(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "tool")
        deps = [
            {
                "name": "needed",
                "type": "file",
                "path": "nope",
                "required": True,
            }
        ]
        manifest = _write_manifest(
            tmp_path / "ext",
            {"extensions": [_valid_entry(binary="bin/tool", deps=deps)]},
        )
        result = resolve_extensions([manifest], tmp_path)
        assert result[0].status == Status.UNAVAILABLE

    def test_optional_dep_missing_is_degraded(self, tmp_path: Path) -> None:
        _make_executable(tmp_path / "bin" / "tool")
        deps = [
            {
                "name": "opt",
                "type": "file",
                "path": "nope",
                "required": False,
            }
        ]
        manifest = _write_manifest(
            tmp_path / "ext",
            {"extensions": [_valid_entry(binary="bin/tool", deps=deps)]},
        )
        result = resolve_extensions([manifest], tmp_path)
        assert result[0].status == Status.DEGRADED


# ---------------------------------------------------------------------------
# get_container_runtime
# ---------------------------------------------------------------------------


class TestGetContainerRuntime:
    def setup_method(self) -> None:
        reg._container_runtime_cache.clear()

    def test_podman_found(self) -> None:
        def _which(x: str) -> str | None:
            return "/usr/bin/podman" if x == "podman" else None

        mod_path = "ami.scripts.shell.extension_registry.shutil.which"
        with patch(mod_path, side_effect=_which):
            assert get_container_runtime() == "podman"

    def test_docker_fallback(self) -> None:
        def _which(x: str) -> str | None:
            return "/usr/bin/docker" if x == "docker" else None

        mod_path = "ami.scripts.shell.extension_registry.shutil.which"
        with patch(mod_path, side_effect=_which):
            assert get_container_runtime() == "docker"

    def test_none_found(self) -> None:
        mod_path = "ami.scripts.shell.extension_registry.shutil.which"
        with patch(mod_path, return_value=None):
            assert get_container_runtime() is None

    def test_cached(self) -> None:
        reg._container_runtime_cache.clear()
        reg._container_runtime_cache.append("cached-runtime")
        assert get_container_runtime() == "cached-runtime"


# ---------------------------------------------------------------------------
# group_by_category
# ---------------------------------------------------------------------------


class TestGroupByCategory:
    def test_known_categories_ordered(self) -> None:
        exts = [
            ResolvedExtension(
                _valid_entry(category="agents"),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(category="core"),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(category="dev"),
                Path("m"),
                Status.READY,
            ),
        ]
        result = group_by_category(exts)
        categories = [c for c, _ in result]
        assert categories == ["core", "dev", "agents"]

    def test_unknown_categories_appended(self) -> None:
        exts = [
            ResolvedExtension(
                _valid_entry(category="zzz"),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(category="aaa"),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(category="core"),
                Path("m"),
                Status.READY,
            ),
        ]
        result = group_by_category(exts)
        categories = [c for c, _ in result]
        assert categories == ["core", "aaa", "zzz"]

    def test_priority_sorting(self) -> None:
        exts = [
            ResolvedExtension(
                _valid_entry(name="z-high", bannerPriority=900),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(name="a-low", bannerPriority=10),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(name="m-default"),
                Path("m"),
                Status.READY,
            ),
        ]
        result = group_by_category(exts)
        names = [e.entry["name"] for e in result[0][1]]
        assert names == ["a-low", "m-default", "z-high"]

    def test_empty_input(self) -> None:
        assert group_by_category([]) == []

    def test_default_priority_is_500(self) -> None:
        exts = [
            ResolvedExtension(
                _valid_entry(name="explicit", bannerPriority=500),
                Path("m"),
                Status.READY,
            ),
            ResolvedExtension(
                _valid_entry(name="default"),
                Path("m"),
                Status.READY,
            ),
        ]
        result = group_by_category(exts)
        assert len(result[0][1]) == len(exts)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_required_fields(self) -> None:
        expected = {"name", "binary", "description", "category"}
        assert expected == REQUIRED_FIELDS

    def test_known_fields_superset(self) -> None:
        assert REQUIRED_FIELDS.issubset(KNOWN_FIELDS)

    def test_exclude_dirs_has_expected(self) -> None:
        for d in (".git", "node_modules", "target"):
            assert d in EXCLUDE_DIRS

    def test_default_category_order(self) -> None:
        assert DEFAULT_CATEGORY_ORDER == _EXPECTED_CATEGORIES

    def test_default_category_props_keys(self) -> None:
        assert set(DEFAULT_CATEGORY_PROPS.keys()) == set(DEFAULT_CATEGORY_ORDER)
