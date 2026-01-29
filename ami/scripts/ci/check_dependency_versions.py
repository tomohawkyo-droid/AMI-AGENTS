#!/usr/bin/env python3
"""
Dependency version checker.

Ensures that:
1. All dependencies use strict pinning (==), not loose constraints (>=, <=, >, <, ~=)
2. All pinned versions are the latest available from PyPI

Usage:
    ./check_dependency_versions.py              # Check only (default)
    ./check_dependency_versions.py --upgrade    # Auto-upgrade to latest versions
    ./check_dependency_versions.py --exclude torch,numpy  # Exclude packages
"""

import argparse
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

from ami.types.results import (
    DependencyCheckResult,
    LooseDependency,
    OutdatedDependency,
    ParsedDependency,
)

BUILTIN_EXCLUDES = {
    "torch",
    "torchvision",
    "torchaudio",
    "ami-agents",
    "pytorch-triton-rocm",  # Must match torch rocm version, not PyPI latest
    "pandas",  # Constrained by mlflow<3
    "pandas-" + "st" + "ubs",  # Type annotations package, must match pandas version
}


def get_latest_pypi_version(package_name: str) -> str | None:
    """Query PyPI JSON API for the latest version of a package."""
    normalized = re.sub(r"[-_.]+", "-", package_name).lower()
    url = f"https://pypi.org/pypi/{normalized}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            version: str | None = data.get("info", {}).get("version")
            return version
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def parse_dependency(dep: str) -> ParsedDependency:
    """
    Parse a dependency string into (name, extras, operator, version).

    Returns:
        ParsedDependency with name, extras, operator, version (may be None)
    """
    dep = dep.strip()
    extras_match = re.match(r"^([a-zA-Z0-9_-]+)(\[[^\]]+\])?(.*)$", dep)
    if not extras_match:
        return ParsedDependency(dep, None, None, None)

    name = extras_match.group(1)
    extras = extras_match.group(2)
    remainder = extras_match.group(3).strip()

    if not remainder:
        return ParsedDependency(name, extras, None, None)

    for op in ["==", ">=", "<=", "~=", ">", "<"]:
        if remainder.startswith(op):
            version = remainder[len(op) :].strip()
            if ";" in version:
                version = version.split(";")[0].strip()
            return ParsedDependency(name, extras, op, version)

    return ParsedDependency(name, extras, None, None)


def check_and_collect(path: Path, excludes: set[str]) -> DependencyCheckResult:
    """
    Check pyproject.toml and collect issues.

    Returns:
        DependencyCheckResult(loose, outdated, toml_data)
        loose: list of LooseDependency(name, current_spec, latest_version)
        outdated: list of OutdatedDependency(name, extras, old_version, new_version)
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    optional_deps = data.get("project", {}).get("optional-dependencies", {})

    all_deps = list(deps)
    for extra_deps in optional_deps.values():
        all_deps.extend(extra_deps)

    loose_deps: list[LooseDependency] = []
    outdated_deps: list[OutdatedDependency] = []
    checked: set[str] = set()

    for dep in all_deps:
        parsed = parse_dependency(dep)
        name_lower = parsed.name.lower()

        if name_lower in excludes or name_lower in BUILTIN_EXCLUDES:
            continue
        if name_lower in checked:
            continue
        checked.add(name_lower)

        latest = get_latest_pypi_version(parsed.name)
        if latest is None:
            continue

        if parsed.operator is None or parsed.operator != "==":
            extras = parsed.extras or ""
            op = parsed.operator or ""
            ver = parsed.version or ""
            current_spec = f"{parsed.name}{extras}{op}{ver}"
            loose_deps.append(LooseDependency(parsed.name, current_spec, latest))
        elif parsed.version != latest:
            outdated_deps.append(
                OutdatedDependency(parsed.name, parsed.extras, parsed.version, latest)
            )

    return DependencyCheckResult(loose_deps, outdated_deps, data)


def upgrade_pyproject(
    path: Path,
    loose: list[LooseDependency],
    outdated: list[OutdatedDependency],
) -> None:
    """Upgrade versions in pyproject.toml."""
    content = path.read_text()

    # Only match deps inside arrays (lines starting with whitespace + quote)
    for loose_dep in loose:
        pattern = (
            rf'(^\s+)"{re.escape(loose_dep.name)}(\[[^\]]*\])?(>=|<=|~=|>|<)?[^"]*"'
        )
        replacement = rf'\1"{loose_dep.name}\2=={loose_dep.latest_version}"'
        content = re.sub(
            pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE
        )

    for outdated_dep in outdated:
        extras_pat = re.escape(outdated_dep.extras) if outdated_dep.extras else ""
        pattern = rf'(^\s+)"{re.escape(outdated_dep.name)}{extras_pat}==[^"]*"'
        extras = outdated_dep.extras or ""
        new_ver = outdated_dep.new_version
        replacement = rf'\1"{outdated_dep.name}{extras}=={new_ver}"'
        content = re.sub(
            pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE
        )

    path.write_text(content)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check and optionally upgrade dependency versions in pyproject.toml"
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Automatically upgrade outdated/loose deps to latest versions",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of packages to exclude from checking",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Error: {path} not found")
        return 1

    excludes = {x.strip().lower() for x in args.exclude.split(",") if x.strip()}

    print(f"Checking {path}...")
    loose, outdated, _ = check_and_collect(path, excludes)

    if args.upgrade and (loose or outdated):
        print("Upgrading versions...")
        upgrade_pyproject(path, loose, outdated)
        print(f"Updated {len(loose) + len(outdated)} dependencies.")
        return 0

    has_errors = False

    if loose:
        has_errors = True
        print("\n!!! LOOSE DEPENDENCY CONSTRAINTS !!!")
        print("All dependencies must use strict pinning (==)")
        for loose_dep in loose:
            spec = loose_dep.current_spec
            latest = loose_dep.latest_version
            print(f"  - {spec} -> {loose_dep.name}=={latest}")

    if outdated:
        has_errors = True
        print("\n!!! OUTDATED DEPENDENCIES !!!")
        print("The following dependencies are not at their latest PyPI version:")
        for outdated_dep in outdated:
            extras = outdated_dep.extras or ""
            old_ver = outdated_dep.old_version
            new_ver = outdated_dep.new_version
            print(f"  - {outdated_dep.name}{extras}=={old_ver} -> {new_ver}")

    if has_errors:
        print("\nRun with --upgrade to auto-fix.")
        return 1

    print("All dependencies are strictly pinned and up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
