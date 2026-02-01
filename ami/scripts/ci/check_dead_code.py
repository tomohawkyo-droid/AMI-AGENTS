#!/usr/bin/env python3
"""
AST-based dead code detection.

Scans Python modules for unreferenced definitions using AST analysis.
Configuration: res/config/dead_code.yaml
"""

import argparse
import ast
import json
import os
import re
import sys
from typing import TypedDict, cast

import yaml

from ami.scripts.ci.dead_code_analyzer import (
    CrossReferenceGraph,
    DeadCodeConfig,
    DeadCodeItem,
    analyze_module,
    find_dead_code,
    is_reference_only,
)
from ami.types.results import DeadCodeEntry, LoadedConfig

DEFAULT_CONFIG_PATH = "res/config/dead_code.yaml"

# ANSI colour codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


class RawConfig(TypedDict, total=False):
    """Raw YAML configuration structure."""

    scan_paths: list[str]
    ignore_paths: list[str]
    entry_points: list[str]
    ignored_names: list[str]
    ignored_name_patterns: list[str]
    reference_only_paths: list[str]


DEFAULT_RAW: RawConfig = {
    "scan_paths": ["ami"],
    "ignore_paths": [],
    "entry_points": [],
    "ignored_names": [],
    "ignored_name_patterns": [],
    "reference_only_paths": [],
}


def load_config(path: str) -> LoadedConfig:
    """Load and process configuration from a YAML file."""
    if os.path.exists(path):
        with open(path) as f:
            raw = yaml.safe_load(f) or {}  # dict being mutated, no type annotation
    else:
        print(f"Warning: {path} not found, using defaults")
        raw = {}

    # Merge with defaults
    default_raw = {  # dict being mutated, no type annotation
        "scan_paths": list(DEFAULT_RAW.get("scan_paths", [])),
        "ignore_paths": list(DEFAULT_RAW.get("ignore_paths", [])),
        "entry_points": list(DEFAULT_RAW.get("entry_points", [])),
        "ignored_names": list(DEFAULT_RAW.get("ignored_names", [])),
        "ignored_name_patterns": list(DEFAULT_RAW.get("ignored_name_patterns", [])),
        "reference_only_paths": list(DEFAULT_RAW.get("reference_only_paths", [])),
    }
    for key, default_val in default_raw.items():
        if key not in raw:
            raw[key] = default_val

    # Compile regex patterns
    compiled = []  # list being mutated, no type annotation
    for pat_str in raw.get("ignored_name_patterns", []):
        try:
            compiled.append(re.compile(pat_str))
        except re.error:
            print(f"Warning: invalid regex pattern: {pat_str}")

    config = DeadCodeConfig(
        entry_point_patterns=raw.get("entry_points", []),
        ignored_names=set(raw.get("ignored_names", [])),
        ignored_name_regexes=compiled,
        reference_only_patterns=raw.get("reference_only_paths", []),
    )
    return LoadedConfig(raw, config)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "projects",
}


def discover_files(scan_paths: list[str], ignore_paths: list[str]) -> list[str]:
    """Discover Python files in *scan_paths*, excluding *ignore_paths*."""
    files: list[str] = []
    for scan_path in scan_paths:
        for root, dirs, filenames in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(root, filename).replace("\\", "/")
                if not _is_ignored(path, ignore_paths):
                    files.append(path)
    return sorted(files)


def _is_ignored(path: str, ignore_paths: list[str]) -> bool:
    for pattern in ignore_paths:
        if path == pattern or path.startswith(pattern + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

KIND_ORDER = ["module", "function", "class", "method", "constant"]

KIND_LABELS = {
    "module": "UNREFERENCED MODULES",
    "function": "UNREFERENCED FUNCTIONS",
    "class": "UNREFERENCED CLASSES",
    "method": "UNREFERENCED METHODS",
    "constant": "UNREFERENCED CONSTANTS",
}


def print_report(dead_items: list[DeadCodeItem]) -> None:
    """Print a coloured report grouped by dead-code kind."""
    print(f"\n{RED}Dead Code Analysis Results{RESET}\n")

    by_kind: dict[str, list[DeadCodeItem]] = {}
    for item in dead_items:
        kind = item.definition.kind
        if kind not in by_kind:
            by_kind[kind] = []
        by_kind[kind].append(item)

    for kind in KIND_ORDER:
        items = by_kind.get(kind, [])
        if not items:
            continue
        label = KIND_LABELS.get(kind, f"UNREFERENCED {kind.upper()}S")
        print(f"{BOLD}{label} ({len(items)}):{RESET}")
        for item in sorted(items, key=lambda x: (x.definition.file, x.definition.line)):
            defn = item.definition
            short = defn.name.split(".")[-1]
            loc = f"  {defn.file}:{defn.line}"
            if kind == "module":
                print(f"{loc:<45} {YELLOW}-- {item.reason}{RESET}")
            else:
                print(f"{loc:<45} {YELLOW}-- {short}() -- {item.reason}{RESET}")
        print()

    # Summary line
    total = len(dead_items)
    parts = []
    for kind in KIND_ORDER:
        count = len(by_kind.get(kind, []))
        if count:
            plural = "es" if kind == "class" else "s"
            parts.append(f"{count} {kind}{plural if count != 1 else ''}")
    print(f"{BOLD}Total: {total} dead code items ({', '.join(parts)}){RESET}")


def format_json_output(dead_items: list[DeadCodeItem]) -> str:
    """Format dead-code items as JSON."""
    items = []
    for item in dead_items:
        defn = item.definition
        items.append(
            {
                "name": defn.name,
                "kind": defn.kind,
                "file": defn.file,
                "line": defn.line,
                "reason": item.reason,
            }
        )
    return json.dumps({"dead_code": items, "count": len(items)}, indent=2)


# ---------------------------------------------------------------------------
# Dry-run line counting
# ---------------------------------------------------------------------------


def _count_file_lines(path: str) -> int:
    """Count lines in a file. Returns 0 if the file cannot be read."""
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _count_node_lines(path: str, target_line: int, kind: str) -> int:
    """Count lines occupied by the AST node at *target_line*."""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except (OSError, SyntaxError):
        return 1

    node_types = {  # Mapping from kind to AST node types
        "function": (ast.FunctionDef, ast.AsyncFunctionDef),
        "class": (ast.ClassDef,),
        "constant": (ast.Assign, ast.AnnAssign),
    }
    targets = node_types.get(kind, ())
    for node in ast.walk(tree):
        if not isinstance(node, targets):
            continue
        # All matched node types are ast.stmt subclasses with lineno
        stmt = cast(ast.stmt, node)
        if stmt.lineno == target_line:
            end: int = stmt.end_lineno if stmt.end_lineno is not None else target_line
            return end - target_line + 1
    return 1


def find_dead_test_files(
    dead_items: list[DeadCodeItem],
    graph: CrossReferenceGraph,
    config: DeadCodeConfig,
) -> set[str]:
    """Find test files whose production imports are all to dead modules."""
    dead_module_names: set[str] = {
        item.definition.name for item in dead_items if item.definition.kind == "module"
    }
    if not dead_module_names:
        return set()

    dead_tests: set[str] = set()
    for path, info in graph.modules.items():
        if not is_reference_only(path, config):
            continue
        # Only consider production imports (not test-to-test)
        prod_imports = [imp for imp in info.imports if not imp.startswith("tests.")]
        if not prod_imports:
            continue
        # All production imports must point to dead modules
        all_dead = all(
            any(imp == dm or imp.startswith(dm + ".") for dm in dead_module_names)
            for imp in prod_imports
        )
        if all_dead:
            dead_tests.add(path)
    return dead_tests


def print_dry_run_report(
    dead_items: list[DeadCodeItem],
    graph: CrossReferenceGraph,
    config: DeadCodeConfig,
) -> None:
    """Print a line-count report for dead code removal."""
    print(f"\n{BOLD}Dry Run: Lines removable by deleting dead code{RESET}\n")

    by_kind: dict[str, list[DeadCodeEntry]] = {}
    prod_total = 0

    for item in dead_items:
        defn = item.definition
        if defn.kind == "module":
            lines = _count_file_lines(defn.file)
        else:
            lines = _count_node_lines(defn.file, defn.line, defn.kind)
        prod_total += lines
        if defn.kind not in by_kind:
            by_kind[defn.kind] = []
        entry = DeadCodeEntry(
            name=defn.name,
            kind=defn.kind,
            file=defn.file,
            line=defn.line,
            reason=item.reason,
            line_count=lines,
        )
        by_kind[defn.kind].append(entry)

    print(f"{BOLD}DEAD PRODUCTION CODE:{RESET}")
    for kind in KIND_ORDER:
        entries = by_kind.get(kind, [])
        if not entries:
            continue
        label = KIND_LABELS.get(kind, f"UNREFERENCED {kind.upper()}S")
        print(f"  {label} ({len(entries)}):")
        for entry in sorted(entries, key=lambda x: (x.file, x.line)):
            if kind == "module":
                loc = f"    {entry.file}"
            else:
                short = entry.name.split(".")[-1]
                loc = f"    {entry.file}:{entry.line}  {short}"
            print(f"{loc:<55} {YELLOW}{entry.line_count} lines{RESET}")
    print(f"  {BOLD}Production subtotal: {prod_total} lines{RESET}\n")

    # Dead test files
    dead_tests = find_dead_test_files(dead_items, graph, config)
    test_total = 0
    if dead_tests:
        print(f"{BOLD}DEAD TEST FILES:{RESET}")
        for path in sorted(dead_tests):
            lines = _count_file_lines(path)
            test_total += lines
            print(f"    {path:<55} {YELLOW}{lines} lines{RESET}")
        print(f"  {BOLD}Test subtotal: {test_total} lines{RESET}\n")
    else:
        print("  No fully-dead test files found.\n")

    grand = prod_total + test_total
    print(f"{BOLD}TOTAL: {grand} lines removable{RESET}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_graph(files: list[str], *, verbose: bool) -> CrossReferenceGraph:
    """Analyze all files and build a cross-reference graph."""
    graph = CrossReferenceGraph()
    parse_errors = 0
    for file_path in files:
        info = analyze_module(file_path)
        if info is not None:
            graph.add(info)
        else:
            parse_errors += 1
            if verbose:
                print(f"  Warning: could not parse {file_path}")

    if parse_errors:
        print(f"  Parse errors: {parse_errors}")
    return graph


def main() -> None:
    """Main entry point for dead code detection."""
    parser = argparse.ArgumentParser(
        description="AST-based dead code detection for Python projects",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all analyzed files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Count lines removable by deleting dead code",
    )
    args = parser.parse_args()

    loaded = load_config(args.config)
    raw_config = cast(RawConfig, loaded.raw)
    config = cast(DeadCodeConfig, loaded.config)
    scan_paths: list[str] = raw_config.get("scan_paths", ["ami"])
    ignore_paths: list[str] = raw_config.get("ignore_paths", [])

    print("Dead Code Analysis (AST-based)")
    print(f"  Config: {args.config}")

    files = discover_files(scan_paths, ignore_paths)
    print(f"  Files to analyze: {len(files)}")

    if args.verbose:
        for f in files:
            print(f"    {f}")

    graph = _build_graph(files, verbose=args.verbose)
    dead = find_dead_code(graph, config)

    if args.dry_run:
        if dead:
            print_dry_run_report(dead, graph, config)
        else:
            print(f"\n{GREEN}No dead code to remove.{RESET}")
        sys.exit(1 if dead else 0)

    if args.json_output:
        print(format_json_output(dead))
        sys.exit(1 if dead else 0)

    if dead:
        print_report(dead)
        sys.exit(1)

    print(f"\n{GREEN}SUCCESS: No dead code detected.{RESET}")
    sys.exit(0)


if __name__ == "__main__":
    main()
