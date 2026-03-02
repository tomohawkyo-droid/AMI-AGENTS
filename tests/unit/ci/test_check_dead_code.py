"""Unit tests for ci/check_dead_code module -- config, discovery, reporting, CLI."""

import json
import os
from pathlib import Path
from typing import cast

import pytest
from ami.ci.check_dead_code import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_RAW,
    IGNORE_DIRS,
    KIND_LABELS,
    KIND_ORDER,
    RawConfig,
    _is_ignored,
    discover_files,
    format_json_output,
    load_config,
    print_report,
)
from ami.ci.dead_code_analyzer import (
    DeadCodeConfig,
    DeadCodeItem,
    Definition,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_KIND_COUNT = 5
EXPECTED_DEFAULT_SCAN = ["ami"]
EXPECTED_LINE_NUMBER = 10
EXPECTED_ITEM_COUNT_TWO = 2
EXPECTED_LINE_COUNT_THREE = 3
EXPECTED_LINE_COUNT_FOUR = 4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    name: str = "unused",
    kind: str = "function",
    file: str = "ami/mod.py",
    line: int = 10,
    reason: str = "no external references",
) -> DeadCodeItem:
    return DeadCodeItem(
        definition=Definition(
            name=name,
            kind=kind,
            file=file,
            line=line,
            is_dunder=False,
            is_exported=False,
        ),
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Constants / module-level
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_default_config_path(self) -> None:
        assert DEFAULT_CONFIG_PATH == "projects/AMI-CI/config/dead_code.yaml"

    def test_kind_order_length(self) -> None:
        assert len(KIND_ORDER) == EXPECTED_KIND_COUNT

    def test_kind_labels_match_order(self) -> None:
        for kind in KIND_ORDER:
            assert kind in KIND_LABELS

    def test_ignore_dirs_contains_pycache(self) -> None:
        assert "__pycache__" in IGNORE_DIRS

    def test_default_raw_has_scan_paths(self) -> None:
        assert "scan_paths" in DEFAULT_RAW


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "dead_code.yaml"
        cfg_file.write_text("scan_paths:\n  - src\nignored_names:\n  - main\n")
        loaded = load_config(str(cfg_file))
        raw = cast(RawConfig, loaded.raw)
        config = cast(DeadCodeConfig, loaded.config)
        assert raw["scan_paths"] == ["src"]
        assert "main" in config.ignored_names

    def test_missing_file_uses_defaults(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        loaded = load_config("/nonexistent/config.yaml")
        raw = cast(RawConfig, loaded.raw)
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert raw.get("scan_paths") == EXPECTED_DEFAULT_SCAN

    def test_empty_file_uses_defaults(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "empty.yaml"
        cfg_file.write_text("")
        loaded = load_config(str(cfg_file))
        raw = cast(RawConfig, loaded.raw)
        assert raw.get("scan_paths") == EXPECTED_DEFAULT_SCAN

    def test_regex_patterns_compiled(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "cfg.yaml"
        cfg_file.write_text('ignored_name_patterns:\n  - "^test_"\n')
        loaded = load_config(str(cfg_file))
        config = cast(DeadCodeConfig, loaded.config)
        assert len(config.ignored_name_regexes) == 1
        assert config.ignored_name_regexes[0].search("test_foo")

    def test_invalid_regex_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg_file = tmp_path / "bad.yaml"
        cfg_file.write_text('ignored_name_patterns:\n  - "[invalid"\n')
        loaded = load_config(str(cfg_file))
        config = cast(DeadCodeConfig, loaded.config)
        captured = capsys.readouterr()
        assert "invalid regex" in captured.out
        assert len(config.ignored_name_regexes) == 0

    def test_entry_points_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "cfg.yaml"
        cfg_file.write_text("entry_points:\n  - ami/scripts/*.py\n")
        loaded = load_config(str(cfg_file))
        config = cast(DeadCodeConfig, loaded.config)
        assert "ami/scripts/*.py" in config.entry_point_patterns

    def test_reference_only_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "cfg.yaml"
        cfg_file.write_text("reference_only_paths:\n  - tests/\n")
        loaded = load_config(str(cfg_file))
        config = cast(DeadCodeConfig, loaded.config)
        assert "tests/" in config.reference_only_patterns


# ---------------------------------------------------------------------------
# _is_ignored / discover_files
# ---------------------------------------------------------------------------


class TestIsIgnored:
    """Tests for _is_ignored helper."""

    def test_exact_match(self) -> None:
        assert _is_ignored("ami/foo.py", ["ami/foo.py"]) is True

    def test_prefix_match(self) -> None:
        assert _is_ignored("ami/__pycache__/mod.pyc", ["ami/__pycache__"]) is True

    def test_no_match(self) -> None:
        assert _is_ignored("ami/core/utils.py", ["ami/__pycache__"]) is False

    def test_empty_patterns(self) -> None:
        assert _is_ignored("anything.py", []) is False


class TestDiscoverFiles:
    """Tests for discover_files."""

    def test_discovers_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text("x = 1")
        (tmp_path / "readme.md").write_text("# hi")
        files = discover_files([str(tmp_path)], [])
        assert len(files) == 1
        assert files[0].endswith("mod.py")

    def test_excludes_ignored_paths(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        a_path = str(tmp_path / "a.py").replace("\\", "/")
        files = discover_files([str(tmp_path)], [a_path])
        assert len(files) == 1
        assert files[0].endswith("b.py")

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "mod.cpython-311.pyc").write_text("")
        (tmp_path / "real.py").write_text("x = 1")
        files = discover_files([str(tmp_path)], [])
        assert len(files) == 1

    def test_returns_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "z.py").write_text("")
        (tmp_path / "a.py").write_text("")
        files = discover_files([str(tmp_path)], [])
        basenames = [os.path.basename(f) for f in files]
        assert basenames == sorted(basenames)


# ---------------------------------------------------------------------------
# print_report
# ---------------------------------------------------------------------------


class TestPrintReport:
    """Tests for print_report."""

    def test_report_groups_by_kind(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [
            _make_item("mod_a", "module", reason="module never imported"),
            _make_item("func_a", "function"),
            _make_item("ClassA", "class"),
        ]
        print_report(items)
        out = capsys.readouterr().out
        assert "UNREFERENCED MODULES" in out
        assert "UNREFERENCED FUNCTIONS" in out
        assert "UNREFERENCED CLASSES" in out

    def test_report_shows_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item(), _make_item("bar")]
        print_report(items)
        out = capsys.readouterr().out
        assert "Total: 2" in out

    def test_report_shows_file_and_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        items = [_make_item("func", "function", "ami/core.py", 42)]
        print_report(items)
        out = capsys.readouterr().out
        assert "ami/core.py:42" in out

    def test_report_empty_kind_skipped(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        items = [_make_item("func", "function")]
        print_report(items)
        out = capsys.readouterr().out
        assert "UNREFERENCED MODULES" not in out
        assert "UNREFERENCED FUNCTIONS" in out

    def test_singular_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item("f", "function")]
        print_report(items)
        out = capsys.readouterr().out
        assert "1 function)" in out or "1 function" in out


# ---------------------------------------------------------------------------
# format_json_output
# ---------------------------------------------------------------------------


class TestFormatJsonOutput:
    """Tests for format_json_output."""

    def test_valid_json(self) -> None:
        items = [_make_item("foo", "function", "a.py", 10)]
        result = json.loads(format_json_output(items))
        assert result["count"] == 1
        assert result["dead_code"][0]["name"] == "foo"
        assert result["dead_code"][0]["kind"] == "function"
        assert result["dead_code"][0]["file"] == "a.py"
        assert result["dead_code"][0]["line"] == EXPECTED_LINE_NUMBER
        assert result["dead_code"][0]["reason"] == "no external references"

    def test_empty_list(self) -> None:
        result = json.loads(format_json_output([]))
        assert result["count"] == 0
        assert result["dead_code"] == []

    def test_multiple_items(self) -> None:
        items = [_make_item("a"), _make_item("b")]
        result = json.loads(format_json_output(items))
        assert result["count"] == EXPECTED_ITEM_COUNT_TWO
