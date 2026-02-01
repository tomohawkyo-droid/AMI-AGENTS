#!/usr/bin/env python3
"""
AST-based dead code analysis engine.

Parses Python source files to find unreferenced modules, functions, classes,
methods, and constants. Uses conservative name matching to minimize false
positives -- better to miss dead code than to flag live code.
"""

import ast
import os
import re
from fnmatch import fnmatch
from typing import NamedTuple

# Type alias for compiled regex pattern
CompiledPattern = re.Pattern[str]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Definition(NamedTuple):
    """A code definition (function, class, method, or constant)."""

    name: str  # Qualified within module: "Class.method"
    kind: str  # "function" | "class" | "method" | "constant"
    file: str  # Relative path
    line: int
    is_dunder: bool  # __init__, __str__, etc.
    is_exported: bool  # Listed in __all__


class Reference(NamedTuple):
    """A reference to a name in source code."""

    name: str
    file: str
    line: int


class ModuleInfo(NamedTuple):
    """Analysis results for a single Python module."""

    path: str  # Relative file path
    module_name: str  # Dotted module name (e.g. ami.cli.base_provider)
    definitions: list[Definition]
    references: list[Reference]
    imports: list[str]  # Module names imported from
    all_exports: list[str] | None  # __all__ contents, or None if absent


class DeadCodeItem(NamedTuple):
    """A detected piece of dead code."""

    definition: Definition
    reason: str


class DeadCodeConfig(NamedTuple):
    """Processed configuration for dead code detection."""

    entry_point_patterns: list[str]
    ignored_names: set[str]
    ignored_name_regexes: list[CompiledPattern]
    reference_only_patterns: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def path_to_module_name(path: str) -> str:
    """Convert a file path to a dotted Python module name."""
    if path.endswith("/__init__.py"):
        path = path[: -len("/__init__.py")]
    elif path.endswith(".py"):
        path = path[:-3]
    return path.replace(os.sep, ".").replace("/", ".")


def _extract_all_exports(tree: ast.Module) -> list[str] | None:
    """Extract names from ``__all__`` if defined in the module."""
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == "__all__"):
                continue
            if isinstance(node.value, ast.List | ast.Tuple):
                names: list[str] = [
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
                return names
    return None


# ---------------------------------------------------------------------------
# AST visitors
# ---------------------------------------------------------------------------


class DefinitionCollector(ast.NodeVisitor):
    """Collects function, class, method, and constant definitions from an AST."""

    def __init__(self, file_path: str, all_exports: list[str] | None) -> None:
        self.file_path = file_path
        self.all_exports = all_exports
        self.definitions: list[Definition] = []
        self._scope_stack: list[str] = []

    # -- internal helpers --------------------------------------------------

    def _qualified_name(self, name: str) -> str:
        if self._scope_stack:
            return ".".join(self._scope_stack) + "." + name
        return name

    _MIN_DUNDER_LEN = 5  # e.g. "__x__" is the shortest valid dunder

    def _add(self, name: str, kind: str, line: int) -> None:
        qualified = self._qualified_name(name)
        is_dunder = (
            name.startswith("__")
            and name.endswith("__")
            and len(name) >= self._MIN_DUNDER_LEN
        )
        is_exported = self.all_exports is not None and name in self.all_exports
        self.definitions.append(
            Definition(
                name=qualified,
                kind=kind,
                file=self.file_path,
                line=line,
                is_dunder=is_dunder,
                is_exported=is_exported,
            )
        )

    # -- visitor methods ---------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind = "method" if self._scope_stack else "function"
        self._add(node.name, kind, node.lineno)
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind = "method" if self._scope_stack else "function"
        self._add(node.name, kind, node.lineno)
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node.name, "class", node.lineno)
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        if not self._scope_stack:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    self._add(target.id, "constant", node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            not self._scope_stack
            and isinstance(node.target, ast.Name)
            and node.target.id.isupper()
        ):
            self._add(node.target.id, "constant", node.lineno)
        self.generic_visit(node)


class ReferenceCollector(ast.NodeVisitor):
    """Collects name references and import information from an AST."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.references: list[Reference] = []
        self.imports: list[str] = []

    def _add_ref(self, name: str, line: int) -> None:
        self.references.append(Reference(name=name, file=self.file_path, line=line))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
            self._add_ref(alias.asname or alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.append(node.module)
            for alias in node.names:
                # "from X import Y" may import sub-module X.Y
                self.imports.append(f"{node.module}.{alias.name}")
                self._add_ref(alias.asname or alias.name, node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self._add_ref(node.id, node.lineno)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._add_ref(node.attr, node.lineno)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Module analysis
# ---------------------------------------------------------------------------


def analyze_module(path: str) -> ModuleInfo | None:
    """Parse and analyze a single Python module.

    Returns ``ModuleInfo`` with definitions, references, and imports.
    Returns ``None`` if the file cannot be read or parsed.
    """
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return None

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return None

    module_name = path_to_module_name(path)
    all_exports = _extract_all_exports(tree)

    # Skip definitions for __init__.py, test files, and conftest.py
    basename = os.path.basename(path)
    skip_defs = (
        basename in {"__init__.py", "conftest.py"}
        or basename.startswith("test_")
        or "/tests/" in path
        or path.startswith("tests/")
    )

    definitions: list[Definition] = []
    if not skip_defs:
        collector = DefinitionCollector(path, all_exports)
        collector.visit(tree)
        definitions = collector.definitions

    # Always collect references
    ref_collector = ReferenceCollector(path)
    ref_collector.visit(tree)

    return ModuleInfo(
        path=path,
        module_name=module_name,
        definitions=definitions,
        references=ref_collector.references,
        imports=ref_collector.imports,
        all_exports=all_exports,
    )


# ---------------------------------------------------------------------------
# Cross-reference graph
# ---------------------------------------------------------------------------


class CrossReferenceGraph:
    """Aggregates module analysis results and resolves cross-references."""

    def __init__(self) -> None:
        self.modules: dict[str, ModuleInfo] = {}
        self._refs_by_name: dict[str, set[str]] = {}
        self._import_sources: dict[str, set[str]] = {}

    def add(self, info: ModuleInfo) -> None:
        """Add a module's analysis results to the graph."""
        self.modules[info.path] = info

        for ref in info.references:
            if ref.name not in self._refs_by_name:
                self._refs_by_name[ref.name] = set()
            self._refs_by_name[ref.name].add(info.path)

        for imp in info.imports:
            if imp not in self._import_sources:
                self._import_sources[imp] = set()
            self._import_sources[imp].add(info.path)

    def is_name_referenced_externally(self, name: str, defining_file: str) -> bool:
        """Check if *name* is referenced in any file other than *defining_file*."""
        refs = self._refs_by_name.get(name, set())
        return any(f != defining_file for f in refs)

    def is_name_referenced_anywhere(self, name: str) -> bool:
        """Check if *name* is referenced in any file at all."""
        return bool(self._refs_by_name.get(name))

    def is_name_referenced_excluding(self, name: str, excluded: set[str]) -> bool:
        """Check if *name* is referenced in any file not in *excluded*."""
        refs = self._refs_by_name.get(name, set())
        return bool(refs - excluded)

    def is_module_imported(self, module_name: str) -> bool:
        """Check if a module is imported anywhere."""
        if module_name in self._import_sources:
            return True
        prefix = module_name + "."
        return any(m.startswith(prefix) for m in self._import_sources)

    def is_module_imported_excluding(
        self, module_name: str, excluded: set[str]
    ) -> bool:
        """Check if a module is imported by any file not in *excluded*."""
        importers = self._import_sources.get(module_name, set())
        if importers - excluded:
            return True
        prefix = module_name + "."
        for mod, files in self._import_sources.items():
            if mod.startswith(prefix) and (files - excluded):
                return True
        return False


# ---------------------------------------------------------------------------
# Dead code detection
# ---------------------------------------------------------------------------


def is_entry_point(path: str, config: DeadCodeConfig) -> bool:
    """Check if *path* matches any configured entry-point pattern."""
    return any(fnmatch(path, pat) for pat in config.entry_point_patterns)


def is_reference_only(path: str, config: DeadCodeConfig) -> bool:
    """Check if *path* is reference-only (scanned but not reported)."""
    for pat in config.reference_only_patterns:
        if path.startswith(pat) or os.path.basename(path) == pat:
            return True
    return False


def should_ignore_definition(defn: Definition, config: DeadCodeConfig) -> bool:
    """Check if a definition should be excluded from dead-code reporting."""
    if defn.is_dunder:
        return True
    if defn.is_exported:
        return True

    short_name = defn.name.split(".")[-1]
    if short_name in config.ignored_names:
        return True

    return any(rx.search(short_name) for rx in config.ignored_name_regexes)


def _check_definitions(
    info: ModuleInfo,
    graph: CrossReferenceGraph,
    config: DeadCodeConfig,
    ref_only_files: set[str],
) -> list[DeadCodeItem]:
    """Check individual definitions in a module for dead code (Phase 2 & 3)."""
    dead: list[DeadCodeItem] = []
    for defn in info.definitions:
        if should_ignore_definition(defn, config):
            continue

        # Methods are called via self.method() within their own file;
        # flagging them for "no external references" yields only false
        # positives, so skip them entirely.
        if defn.kind == "method":
            continue

        short_name = defn.name.split(".")[-1]

        # Private names (leading underscore) are internal by convention.
        # They are used within their own file and are not expected to
        # have external references.
        if short_name.startswith("_"):
            continue

        # For public names, flag only if never referenced in any
        # non-test file (including the defining file itself).
        if not graph.is_name_referenced_excluding(short_name, ref_only_files):
            dead.append(
                DeadCodeItem(
                    definition=defn,
                    reason="no references found",
                )
            )
    return dead


def find_dead_code(
    graph: CrossReferenceGraph,
    config: DeadCodeConfig,
) -> list[DeadCodeItem]:
    """Find unreferenced code across all analyzed modules.

    References from test/reference-only files (e.g. tests/) are excluded
    so that dead code kept alive only by its own tests is still flagged.

    Phase 1: Find modules never imported (unless entry point).
    Phase 2: Find functions/classes never referenced externally.
    Phase 3: Find constants never referenced externally.
    """
    dead: list[DeadCodeItem] = []

    # Build set of reference-only file paths whose references should not
    # count toward keeping production code alive.
    ref_only_files: set[str] = {
        p for p in graph.modules if is_reference_only(p, config)
    }

    for path, info in sorted(graph.modules.items()):
        # Skip reference-only paths (e.g. tests/, conftest.py)
        if path in ref_only_files:
            continue

        # Skip __init__.py (no definitions collected)
        if os.path.basename(path) == "__init__.py":
            continue

        # Phase 1 -- module import check (ignore test-only imports)
        if not is_entry_point(path, config) and not graph.is_module_imported_excluding(
            info.module_name, ref_only_files
        ):
            dead.append(
                DeadCodeItem(
                    definition=Definition(
                        name=info.module_name,
                        kind="module",
                        file=path,
                        line=1,
                        is_dunder=False,
                        is_exported=False,
                    ),
                    reason="module never imported",
                )
            )
            # Don't also report individual items from unimported modules
            continue

        # Phase 2 & 3 -- individual definition checks
        dead.extend(_check_definitions(info, graph, config, ref_only_files))

    return dead
