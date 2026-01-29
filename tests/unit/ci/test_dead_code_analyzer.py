"""Unit tests for ci/dead_code_analyzer module."""

import ast
import textwrap
from pathlib import Path

from ami.scripts.ci.dead_code_analyzer import (
    CrossReferenceGraph,
    Definition,
    DefinitionCollector,
    ModuleInfo,
    Reference,
    ReferenceCollector,
    _extract_all_exports,
    analyze_module,
    path_to_module_name,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


EXPECTED_DUNDER_COUNT = 2
EXPECTED_DEFINITION_COUNT = 2


def _parse(source: str) -> ast.Module:
    return ast.parse(textwrap.dedent(source))


def _make_def(
    name: str = "foo",
    kind: str = "function",
    file: str = "a.py",
    line: int = 1,
    is_dunder: bool = False,
    is_exported: bool = False,
) -> Definition:
    """Create a Definition for testing."""
    return Definition(
        name=name,
        kind=kind,
        file=file,
        line=line,
        is_dunder=is_dunder,
        is_exported=is_exported,
    )


# ---------------------------------------------------------------------------
# path_to_module_name
# ---------------------------------------------------------------------------


class TestPathToModuleName:
    """Tests for path_to_module_name."""

    def test_simple_module(self) -> None:
        assert path_to_module_name("ami/core/utils.py") == "ami.core.utils"

    def test_init_file(self) -> None:
        assert path_to_module_name("ami/core/__init__.py") == "ami.core"

    def test_top_level(self) -> None:
        assert path_to_module_name("setup.py") == "setup"

    def test_nested_path(self) -> None:
        result = path_to_module_name("ami/scripts/ci/check_dead_code.py")
        assert result == "ami.scripts.ci.check_dead_code"


# ---------------------------------------------------------------------------
# _extract_all_exports
# ---------------------------------------------------------------------------


class TestExtractAllExports:
    """Tests for _extract_all_exports."""

    def test_list_all(self) -> None:
        tree = _parse('__all__ = ["foo", "bar"]')
        assert _extract_all_exports(tree) == ["foo", "bar"]

    def test_tuple_all(self) -> None:
        tree = _parse('__all__ = ("alpha", "beta")')
        assert _extract_all_exports(tree) == ["alpha", "beta"]

    def test_no_all(self) -> None:
        tree = _parse("x = 1")
        assert _extract_all_exports(tree) is None

    def test_non_string_elements_skipped(self) -> None:
        tree = _parse('__all__ = ["ok", 123]')
        assert _extract_all_exports(tree) == ["ok"]


# ---------------------------------------------------------------------------
# DefinitionCollector
# ---------------------------------------------------------------------------


class TestDefinitionCollector:
    """Tests for DefinitionCollector."""

    def _collect(
        self, source: str, all_exports: list[str] | None = None
    ) -> list[Definition]:
        tree = _parse(source)
        c = DefinitionCollector("test.py", all_exports)
        c.visit(tree)
        return c.definitions

    def test_function_def(self) -> None:
        defs = self._collect("def greet(): pass")
        assert len(defs) == 1
        assert defs[0].name == "greet"
        assert defs[0].kind == "function"

    def test_async_function_def(self) -> None:
        defs = self._collect("async def fetch(): pass")
        assert len(defs) == 1
        assert defs[0].name == "fetch"
        assert defs[0].kind == "function"

    def test_class_def(self) -> None:
        defs = self._collect("class Foo: pass")
        assert len(defs) == 1
        assert defs[0].name == "Foo"
        assert defs[0].kind == "class"

    def test_method_inside_class(self) -> None:
        source = """\
        class Foo:
            def bar(self): pass
        """
        defs = self._collect(source)
        names = {d.name for d in defs}
        assert "Foo" in names
        assert "Foo.bar" in names
        assert defs[1].kind == "method"

    def test_constant_uppercase(self) -> None:
        defs = self._collect("MAX_SIZE = 100")
        assert len(defs) == 1
        assert defs[0].name == "MAX_SIZE"
        assert defs[0].kind == "constant"

    def test_lowercase_assignment_not_collected(self) -> None:
        defs = self._collect("value = 42")
        assert len(defs) == 0

    def test_annotated_constant(self) -> None:
        defs = self._collect("TIMEOUT: int = 30")
        assert len(defs) == 1
        assert defs[0].name == "TIMEOUT"
        assert defs[0].kind == "constant"

    def test_dunder_detection(self) -> None:
        source = """\
        class Foo:
            def __init__(self): pass
            def __str__(self): pass
        """
        defs = self._collect(source)
        dunders = [d for d in defs if d.is_dunder]
        assert len(dunders) == EXPECTED_DUNDER_COUNT

    def test_exported_detection(self) -> None:
        defs = self._collect("def hello(): pass", all_exports=["hello"])
        assert defs[0].is_exported is True

    def test_not_exported(self) -> None:
        defs = self._collect("def hello(): pass", all_exports=["other"])
        assert defs[0].is_exported is False

    def test_nested_class_method(self) -> None:
        source = """\
        class Outer:
            class Inner:
                def deep(self): pass
        """
        defs = self._collect(source)
        names = {d.name for d in defs}
        assert "Outer.Inner.deep" in names

    def test_class_level_constant_not_collected(self) -> None:
        """Only module-level UPPER_CASE constants are collected."""
        source = """\
        class Foo:
            MAX = 10
        """
        defs = self._collect(source)
        constant_defs = [d for d in defs if d.kind == "constant"]
        assert len(constant_defs) == 0


# ---------------------------------------------------------------------------
# ReferenceCollector
# ---------------------------------------------------------------------------


class TestReferenceCollector:
    """Tests for ReferenceCollector."""

    def _collect(self, source: str) -> ReferenceCollector:
        tree = _parse(source)
        c = ReferenceCollector("test.py")
        c.visit(tree)
        return c

    def test_import(self) -> None:
        c = self._collect("import os")
        assert "os" in c.imports
        ref_names = {r.name for r in c.references}
        assert "os" in ref_names

    def test_import_as(self) -> None:
        c = self._collect("import numpy as np")
        assert "numpy" in c.imports
        ref_names = {r.name for r in c.references}
        assert "np" in ref_names

    def test_from_import(self) -> None:
        c = self._collect("from os.path import join")
        assert "os.path" in c.imports
        assert "os.path.join" in c.imports
        ref_names = {r.name for r in c.references}
        assert "join" in ref_names

    def test_name_reference(self) -> None:
        c = self._collect("x = foo()")
        ref_names = {r.name for r in c.references}
        assert "foo" in ref_names

    def test_attribute_reference(self) -> None:
        c = self._collect("x = obj.method()")
        ref_names = {r.name for r in c.references}
        assert "method" in ref_names
        assert "obj" in ref_names

    def test_decorator_reference(self) -> None:
        source = """\
        @my_decorator
        def func(): pass
        """
        c = self._collect(source)
        ref_names = {r.name for r in c.references}
        assert "my_decorator" in ref_names

    def test_submodule_import_tracking(self) -> None:
        c = self._collect("from ami.core import utils")
        assert "ami.core" in c.imports
        assert "ami.core.utils" in c.imports


# ---------------------------------------------------------------------------
# analyze_module
# ---------------------------------------------------------------------------


class TestAnalyzeModule:
    """Tests for analyze_module."""

    def test_normal_file(self, tmp_path: Path) -> None:
        p = tmp_path / "sample.py"
        p.write_text("def hello(): pass\nMAX = 10\n")
        info = analyze_module(str(p))
        assert info is not None
        assert len(info.definitions) == EXPECTED_DEFINITION_COUNT
        def_names = {d.name for d in info.definitions}
        assert "hello" in def_names
        assert "MAX" in def_names

    def test_init_file_no_definitions(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text("def should_skip(): pass\n")
        info = analyze_module(str(p))
        assert info is not None
        assert len(info.definitions) == 0

    def test_test_file_no_definitions(self, tmp_path: Path) -> None:
        p = tmp_path / "test_something.py"
        p.write_text("import os\ndef test_case(): pass\n")
        info = analyze_module(str(p))
        assert info is not None
        assert len(info.definitions) == 0
        assert len(info.references) > 0  # references still collected

    def test_conftest_no_definitions(self, tmp_path: Path) -> None:
        p = tmp_path / "conftest.py"
        p.write_text("def some_fixture(): pass\n")
        info = analyze_module(str(p))
        assert info is not None
        assert len(info.definitions) == 0

    def test_syntax_error_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "broken.py"
        p.write_text("def ???(): pass\n")
        assert analyze_module(str(p)) is None

    def test_missing_file_returns_none(self) -> None:
        assert analyze_module("/nonexistent/file.py") is None

    def test_all_exports_extracted(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text('__all__ = ["foo"]\ndef foo(): pass\n')
        info = analyze_module(str(p))
        assert info is not None
        assert info.all_exports == ["foo"]

    def test_references_collected(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("import os\nx = os.path.join('a', 'b')\n")
        info = analyze_module(str(p))
        assert info is not None
        ref_names = {r.name for r in info.references}
        assert "os" in ref_names
        assert "path" in ref_names
        assert "join" in ref_names


# ---------------------------------------------------------------------------
# CrossReferenceGraph
# ---------------------------------------------------------------------------


class TestCrossReferenceGraph:
    """Tests for CrossReferenceGraph."""

    def _make_info(
        self,
        path: str = "a.py",
        module_name: str = "a",
        definitions: list[Definition] | None = None,
        references: list[Reference] | None = None,
        imports: list[str] | None = None,
    ) -> ModuleInfo:
        return ModuleInfo(
            path=path,
            module_name=module_name,
            definitions=definitions or [],
            references=references or [],
            imports=imports or [],
            all_exports=None,
        )

    def test_add_module(self) -> None:
        graph = CrossReferenceGraph()
        info = self._make_info()
        graph.add(info)
        assert "a.py" in graph.modules

    def test_is_name_referenced_externally_true(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info("a.py", "a", definitions=[_make_def("foo", file="a.py")])
        )
        graph.add(
            self._make_info(
                "b.py",
                "b",
                references=[Reference(name="foo", file="b.py", line=1)],
            )
        )
        assert graph.is_name_referenced_externally("foo", "a.py") is True

    def test_is_name_referenced_externally_false_self_only(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "a.py",
                "a",
                definitions=[_make_def("foo", file="a.py")],
                references=[Reference(name="foo", file="a.py", line=5)],
            )
        )
        assert graph.is_name_referenced_externally("foo", "a.py") is False

    def test_is_name_referenced_externally_false_no_refs(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info("a.py", "a", definitions=[_make_def("foo", file="a.py")])
        )
        assert graph.is_name_referenced_externally("foo", "a.py") is False

    def test_is_module_imported_exact(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(self._make_info("b.py", "b", imports=["ami.core.utils"]))
        assert graph.is_module_imported("ami.core.utils") is True

    def test_is_module_imported_prefix(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(self._make_info("b.py", "b", imports=["ami.core.utils.helpers"]))
        assert graph.is_module_imported("ami.core.utils") is True

    def test_is_module_not_imported(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(self._make_info("b.py", "b", imports=["ami.other"]))
        assert graph.is_module_imported("ami.core.utils") is False

    def test_is_name_referenced_anywhere_true(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "a.py",
                "a",
                definitions=[_make_def("foo", file="a.py")],
                references=[Reference(name="foo", file="a.py", line=5)],
            )
        )
        assert graph.is_name_referenced_anywhere("foo") is True

    def test_is_name_referenced_anywhere_false(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info("a.py", "a", definitions=[_make_def("bar", file="a.py")])
        )
        assert graph.is_name_referenced_anywhere("bar") is False

    def test_is_name_referenced_excluding_filters_test_files(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info("a.py", "a", definitions=[_make_def("foo", file="a.py")])
        )
        graph.add(
            self._make_info(
                "tests/test_a.py",
                "tests.test_a",
                references=[Reference(name="foo", file="tests/test_a.py", line=1)],
            )
        )
        # Referenced overall
        assert graph.is_name_referenced_anywhere("foo") is True
        # But not when excluding test files
        assert graph.is_name_referenced_excluding("foo", {"tests/test_a.py"}) is False

    def test_is_name_referenced_excluding_keeps_prod_refs(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "a.py",
                "a",
                definitions=[_make_def("foo", file="a.py")],
                references=[Reference(name="foo", file="a.py", line=5)],
            )
        )
        graph.add(
            self._make_info(
                "tests/test_a.py",
                "tests.test_a",
                references=[Reference(name="foo", file="tests/test_a.py", line=1)],
            )
        )
        # Still referenced in a.py after excluding tests
        assert graph.is_name_referenced_excluding("foo", {"tests/test_a.py"}) is True

    def test_is_module_imported_excluding_filters_test_imports(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info("tests/test_a.py", "tests.test_a", imports=["ami.orphan"])
        )
        # Imported overall
        assert graph.is_module_imported("ami.orphan") is True
        # But not when excluding test files
        assert (
            graph.is_module_imported_excluding("ami.orphan", {"tests/test_a.py"})
            is False
        )

    def test_is_module_imported_excluding_keeps_prod_imports(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(self._make_info("b.py", "b", imports=["ami.core"]))
        graph.add(
            self._make_info("tests/test_a.py", "tests.test_a", imports=["ami.core"])
        )
        # Still imported by b.py after excluding tests
        assert (
            graph.is_module_imported_excluding("ami.core", {"tests/test_a.py"}) is True
        )

    def test_is_module_imported_excluding_prefix_match(self) -> None:
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "tests/test_a.py", "tests.test_a", imports=["ami.core.utils"]
            )
        )
        # Prefix match works overall
        assert graph.is_module_imported("ami.core") is True
        # But excluded when only test files import it
        assert (
            graph.is_module_imported_excluding("ami.core", {"tests/test_a.py"}) is False
        )
