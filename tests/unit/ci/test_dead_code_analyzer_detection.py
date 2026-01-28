"""Unit tests for dead_code_analyzer detection logic -- helpers and find_dead_code."""

import re

from pydantic import BaseModel

from ami.scripts.ci.dead_code_analyzer import (
    CrossReferenceGraph,
    DeadCodeConfig,
    Definition,
    ModuleInfo,
    Reference,
    find_dead_code,
    is_entry_point,
    is_reference_only,
    should_ignore_definition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMPTY_CONFIG = DeadCodeConfig(
    entry_point_patterns=[],
    ignored_names=set(),
    ignored_name_regexes=[],
    reference_only_patterns=[],
)


class DefParams(BaseModel):
    """Parameters for constructing a Definition in tests."""

    name: str = "foo"
    kind: str = "function"
    file: str = "a.py"
    line: int = 1
    is_dunder: bool = False
    is_exported: bool = False


def _make_def(name: str = "foo", **kwargs: object) -> Definition:
    params = DefParams(name=name, **kwargs)
    return Definition(
        name=params.name,
        kind=params.kind,
        file=params.file,
        line=params.line,
        is_dunder=params.is_dunder,
        is_exported=params.is_exported,
    )


# ---------------------------------------------------------------------------
# Entry point / reference-only / ignore helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for is_entry_point, is_reference_only, should_ignore_definition."""

    def test_is_entry_point_match(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=["ami/scripts/ci/*.py"],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=[],
        )
        assert is_entry_point("ami/scripts/ci/check_dead_code.py", cfg) is True

    def test_is_entry_point_no_match(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=["ami/scripts/ci/*.py"],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=[],
        )
        assert is_entry_point("ami/core/utils.py", cfg) is False

    def test_is_reference_only_prefix(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        assert is_reference_only("tests/unit/test_foo.py", cfg) is True

    def test_is_reference_only_basename(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["conftest.py"],
        )
        assert is_reference_only("conftest.py", cfg) is True

    def test_is_reference_only_false(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        assert is_reference_only("ami/core/utils.py", cfg) is False

    def test_ignore_dunder(self) -> None:
        defn = _make_def("__init__", is_dunder=True)
        assert should_ignore_definition(defn, EMPTY_CONFIG) is True

    def test_ignore_exported(self) -> None:
        defn = _make_def("foo", is_exported=True)
        assert should_ignore_definition(defn, EMPTY_CONFIG) is True

    def test_ignore_by_name(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names={"main"},
            ignored_name_regexes=[],
            reference_only_patterns=[],
        )
        defn = _make_def("main")
        assert should_ignore_definition(defn, cfg) is True

    def test_ignore_by_regex(self) -> None:
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[re.compile(r"^test_")],
            reference_only_patterns=[],
        )
        defn = _make_def("test_something")
        assert should_ignore_definition(defn, cfg) is True

    def test_not_ignored(self) -> None:
        defn = _make_def("regular_func")
        assert should_ignore_definition(defn, EMPTY_CONFIG) is False


# ---------------------------------------------------------------------------
# find_dead_code
# ---------------------------------------------------------------------------


class TestFindDeadCode:
    """Tests for find_dead_code."""

    def _make_info(
        self,
        path: str,
        module_name: str,
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

    def test_dead_module(self) -> None:
        """A module not imported anywhere is reported as dead."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/orphan.py",
                "ami.orphan",
                definitions=[_make_def("func", file="ami/orphan.py")],
            )
        )
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 1
        assert dead[0].definition.kind == "module"
        assert dead[0].reason == "module never imported"

    def test_entry_point_not_dead(self) -> None:
        """Entry points are not reported even if never imported."""
        cfg = DeadCodeConfig(
            entry_point_patterns=["ami/scripts/*.py"],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=[],
        )
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/scripts/run.py",
                "ami.scripts.run",
                definitions=[_make_def("func", file="ami/scripts/run.py")],
            )
        )
        dead = find_dead_code(graph, cfg)
        # func is not referenced externally, so it's flagged
        assert all(d.definition.kind != "module" for d in dead)

    def test_dead_function(self) -> None:
        """A function not referenced externally is reported."""
        graph = CrossReferenceGraph()
        # Module A defines foo, Module B imports A but never references foo
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[_make_def("unused_func", file="ami/a.py")],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        func_dead = [d for d in dead if d.definition.kind == "function"]
        assert len(func_dead) == 1
        assert func_dead[0].definition.name == "unused_func"

    def test_live_function(self) -> None:
        """A function referenced externally is not reported."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[_make_def("used_func", file="ami/a.py")],
                imports=["ami.b"],  # bidirectional import so b is not dead
            )
        )
        graph.add(
            self._make_info(
                "ami/b.py",
                "ami.b",
                imports=["ami.a"],
                references=[Reference(name="used_func", file="ami/b.py", line=1)],
            )
        )
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_reference_only_excluded(self) -> None:
        """Files matching reference_only_patterns are not reported."""
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "tests/test_foo.py",
                "tests.test_foo",
                definitions=[_make_def("test_func", file="tests/test_foo.py")],
            )
        )
        dead = find_dead_code(graph, cfg)
        assert len(dead) == 0

    def test_init_files_excluded(self) -> None:
        """__init__.py files are always excluded from dead code reporting."""
        graph = CrossReferenceGraph()
        graph.add(self._make_info("ami/__init__.py", "ami"))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_dunder_methods_excluded(self) -> None:
        """Dunder methods are excluded from dead code reporting."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[
                    _make_def(
                        "__init__", kind="method", file="ami/a.py", is_dunder=True
                    ),
                ],
                imports=["ami.b"],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_exported_names_excluded(self) -> None:
        """Names in __all__ are excluded from dead code reporting."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[
                    _make_def("public_api", file="ami/a.py", is_exported=True),
                ],
                imports=["ami.b"],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_unimported_module_skips_individual_defs(self) -> None:
        """When a module is unimported, only the module is flagged, not its defs."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/orphan.py",
                "ami.orphan",
                definitions=[
                    _make_def("func_a", file="ami/orphan.py"),
                    _make_def("func_b", file="ami/orphan.py"),
                ],
            )
        )
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 1
        assert dead[0].definition.kind == "module"

    def test_methods_always_skipped(self) -> None:
        """Methods are never flagged (called via self within their own file)."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[
                    _make_def("MyClass.do_work", kind="method", file="ami/a.py"),
                ],
                imports=["ami.b"],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_private_names_skipped(self) -> None:
        """Private names (leading underscore) are never flagged."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[
                    _make_def("_helper", kind="function", file="ami/a.py"),
                ],
                imports=["ami.b"],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_public_name_used_internally_not_dead(self) -> None:
        """A public name referenced within its own file is not dead."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[_make_def("helper", kind="function", file="ami/a.py")],
                references=[Reference(name="helper", file="ami/a.py", line=20)],
                imports=["ami.b"],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        assert len(dead) == 0

    def test_public_name_never_referenced_is_dead(self) -> None:
        """A public name never referenced anywhere is dead."""
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[_make_def("OrphanClass", kind="class", file="ami/a.py")],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        dead = find_dead_code(graph, EMPTY_CONFIG)
        cls_dead = [d for d in dead if d.definition.kind == "class"]
        assert len(cls_dead) == 1
        assert cls_dead[0].reason == "no references found"

    def test_module_only_imported_by_tests_is_dead(self) -> None:
        """A module imported only by test files is dead."""
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/orphan.py",
                "ami.orphan",
                definitions=[_make_def("func", file="ami/orphan.py")],
            )
        )
        # Only a test file imports it
        graph.add(
            self._make_info(
                "tests/test_orphan.py",
                "tests.test_orphan",
                imports=["ami.orphan"],
                references=[
                    Reference(name="func", file="tests/test_orphan.py", line=5)
                ],
            )
        )
        dead = find_dead_code(graph, cfg)
        mod_dead = [d for d in dead if d.definition.kind == "module"]
        assert len(mod_dead) == 1
        assert mod_dead[0].definition.name == "ami.orphan"

    def test_name_only_referenced_by_tests_is_dead(self) -> None:
        """A name referenced only in test files is dead."""
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        graph = CrossReferenceGraph()
        # Module is imported by production code (so not dead as module)
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[_make_def("DeadFunc", kind="function", file="ami/a.py")],
                imports=["ami.b"],
            )
        )
        graph.add(self._make_info("ami/b.py", "ami.b", imports=["ami.a"]))
        # Only a test references the function name
        graph.add(
            self._make_info(
                "tests/test_a.py",
                "tests.test_a",
                references=[
                    Reference(name="DeadFunc", file="tests/test_a.py", line=10)
                ],
            )
        )
        dead = find_dead_code(graph, cfg)
        func_dead = [d for d in dead if d.definition.kind == "function"]
        assert len(func_dead) == 1
        assert func_dead[0].definition.name == "DeadFunc"

    def test_name_referenced_by_prod_and_tests_is_alive(self) -> None:
        """A name referenced by both production and test files is alive."""
        cfg = DeadCodeConfig(
            entry_point_patterns=[],
            ignored_names=set(),
            ignored_name_regexes=[],
            reference_only_patterns=["tests/"],
        )
        graph = CrossReferenceGraph()
        graph.add(
            self._make_info(
                "ami/a.py",
                "ami.a",
                definitions=[_make_def("LiveFunc", kind="function", file="ami/a.py")],
                imports=["ami.b"],
            )
        )
        graph.add(
            self._make_info(
                "ami/b.py",
                "ami.b",
                imports=["ami.a"],
                references=[Reference(name="LiveFunc", file="ami/b.py", line=3)],
            )
        )
        graph.add(
            self._make_info(
                "tests/test_a.py",
                "tests.test_a",
                references=[
                    Reference(name="LiveFunc", file="tests/test_a.py", line=10)
                ],
            )
        )
        dead = find_dead_code(graph, cfg)
        assert len(dead) == 0
