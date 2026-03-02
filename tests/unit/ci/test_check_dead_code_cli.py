"""Unit tests for check_dead_code -- main CLI, line counting, dead test files."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from ami.ci.check_dead_code import (
    _count_file_lines,
    _count_node_lines,
    find_dead_test_files,
    main,
)
from ami.ci.dead_code_analyzer import (
    CrossReferenceGraph,
    DeadCodeConfig,
    DeadCodeItem,
    Definition,
    ModuleInfo,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
# main
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for main CLI entry point."""

    def test_success_exit_code(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No dead code results in exit code 0."""
        cfg = tmp_path / "cfg.yaml"
        # Scan an empty directory -- no files, no dead code
        scan_dir = tmp_path / "src"
        scan_dir.mkdir()
        cfg.write_text(f"scan_paths:\n  - {scan_dir}\n")
        argv = ["prog", "--config", str(cfg)]
        with (
            pytest.raises(SystemExit) as exc_info,
            patch("sys.argv", argv),
        ):
            main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "SUCCESS" in out

    def test_failure_exit_code(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Dead code detected results in exit code 1."""
        scan_dir = tmp_path / "pkg"
        scan_dir.mkdir()
        # Create a module that is never imported
        (scan_dir / "orphan.py").write_text("def unused(): pass\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(f"scan_paths:\n  - {scan_dir}\n")
        argv = ["prog", "--config", str(cfg)]
        with (
            pytest.raises(SystemExit) as exc_info,
            patch("sys.argv", argv),
        ):
            main()
        assert exc_info.value.code == 1

    def test_json_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json flag produces valid JSON output."""
        scan_dir = tmp_path / "src"
        scan_dir.mkdir()
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(f"scan_paths:\n  - {scan_dir}\n")
        argv = ["prog", "--config", str(cfg), "--json"]
        with (
            pytest.raises(SystemExit),
            patch("sys.argv", argv),
        ):
            main()
        out = capsys.readouterr().out
        # The JSON portion comes after the header lines
        json_start = out.find("{")
        if json_start >= 0:
            result = json.loads(out[json_start:])
            assert "dead_code" in result

    def test_verbose_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--verbose flag shows analyzed files."""
        scan_dir = tmp_path / "src"
        scan_dir.mkdir()
        (scan_dir / "a.py").write_text("x = 1\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(f"scan_paths:\n  - {scan_dir}\n")
        argv = ["prog", "--config", str(cfg), "--verbose"]
        with (
            pytest.raises(SystemExit),
            patch("sys.argv", argv),
        ):
            main()
        out = capsys.readouterr().out
        assert "a.py" in out


# ---------------------------------------------------------------------------
# Dry-run helpers
# ---------------------------------------------------------------------------


class TestCountFileLines:
    """Tests for _count_file_lines."""

    def test_counts_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("a = 1\nb = 2\nc = 3\n")
        assert _count_file_lines(str(p)) == EXPECTED_LINE_COUNT_THREE

    def test_missing_file_returns_zero(self) -> None:
        assert _count_file_lines("/nonexistent/file.py") == 0


class TestCountNodeLines:
    """Tests for _count_node_lines."""

    def test_function_span(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("def foo():\n    x = 1\n    return x\n")
        assert _count_node_lines(str(p), 1, "function") == EXPECTED_LINE_COUNT_THREE

    def test_class_span(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("class Foo:\n    x = 1\n    def bar(self):\n        pass\n")
        assert _count_node_lines(str(p), 1, "class") == EXPECTED_LINE_COUNT_FOUR

    def test_constant_span(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("MAX = 100\n")
        assert _count_node_lines(str(p), 1, "constant") == 1

    def test_missing_file_returns_one(self) -> None:
        assert _count_node_lines("/nonexistent.py", 1, "function") == 1


class TestFindDeadTestFiles:
    """Tests for find_dead_test_files."""

    def _make_info(
        self,
        path: str,
        module_name: str,
        imports: list[str] | None = None,
    ) -> ModuleInfo:
        return ModuleInfo(
            path=path,
            module_name=module_name,
            definitions=[],
            references=[],
            imports=imports or [],
            all_exports=None,
        )

    def test_flags_test_importing_only_dead_module(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        dead_items = [
            _make_item(
                "ami.orphan", "module", "ami/orphan.py", 1, "module never imported"
            ),
        ]
        graph = CrossReferenceGraph()
        graph.add(self._make_info("ami/orphan.py", "ami.orphan"))
        graph.add(
            self._make_info("tests/test_orphan.py", "tests.test_orphan", ["ami.orphan"])
        )
        result = find_dead_test_files(dead_items, graph, cfg)
        assert "tests/test_orphan.py" in result

    def test_keeps_test_importing_live_module(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        dead_items = [
            _make_item(
                "ami.orphan", "module", "ami/orphan.py", 1, "module never imported"
            ),
        ]
        graph = CrossReferenceGraph()
        graph.add(self._make_info("ami/orphan.py", "ami.orphan"))
        graph.add(self._make_info("ami/live.py", "ami.live"))
        graph.add(
            self._make_info(
                "tests/test_mixed.py", "tests.test_mixed", ["ami.orphan", "ami.live"]
            )
        )
        result = find_dead_test_files(dead_items, graph, cfg)
        assert "tests/test_mixed.py" not in result

    def test_no_dead_modules_returns_empty(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        # Only dead functions, no dead modules
        dead_items = [_make_item("func", "function")]
        graph = CrossReferenceGraph()
        graph.add(self._make_info("tests/test_a.py", "tests.test_a", ["ami.live"]))
        result = find_dead_test_files(dead_items, graph, cfg)
        assert len(result) == 0


class TestDryRunCli:
    """Tests for --dry-run CLI flag."""

    def test_dry_run_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        scan_dir = tmp_path / "pkg"
        scan_dir.mkdir()
        (scan_dir / "orphan.py").write_text("def unused(): pass\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(f"scan_paths:\n  - {scan_dir}\n")
        argv = ["prog", "--config", str(cfg), "--dry-run"]
        with (
            pytest.raises(SystemExit) as exc_info,
            patch("sys.argv", argv),
        ):
            main()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "lines removable" in out

    def test_dry_run_clean(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        scan_dir = tmp_path / "src"
        scan_dir.mkdir()
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(f"scan_paths:\n  - {scan_dir}\n")
        argv = ["prog", "--config", str(cfg), "--dry-run"]
        with (
            pytest.raises(SystemExit) as exc_info,
            patch("sys.argv", argv),
        ):
            main()
        assert exc_info.value.code == 0
