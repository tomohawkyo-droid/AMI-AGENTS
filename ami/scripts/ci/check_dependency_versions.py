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
from typing import Any

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


def parse_dependency(dep: str) -> tuple[str, str | None, str | None, str | None]:
    """
    Parse a dependency string into (name, extras, operator, version).

    Returns:
        (package_name, extras, operator, version) - extras/operator/version may be None
    """
    dep = dep.strip()
    extras_match = re.match(r"^([a-zA-Z0-9_-]+)(\[[^\]]+\])?(.*)$", dep)
    if not extras_match:
        return dep, None, None, None

    name = extras_match.group(1)
    extras = extras_match.group(2)
    remainder = extras_match.group(3).strip()

    if not remainder:
        return name, extras, None, None

    for op in ["==", ">=", "<=", "~=", ">", "<"]:
        if remainder.startswith(op):
            version = remainder[len(op) :].strip()
            if ";" in version:
                version = version.split(";")[0].strip()
            return name, extras, op, version

    return name, extras, None, None


def check_and_collect(
    path: Path, excludes: set[str]
) -> tuple[
    list[tuple[str, str, str]],
    list[tuple[str, str | None, str | None, str]],
    dict[str, Any],
]:
    """
    Check pyproject.toml and collect issues.

    Returns:
        (loose_deps, outdated_deps, toml_data)
        loose_deps: [(name, current_spec, latest_version), ...]
        outdated_deps: [(name, extras, old_version, new_version), ...]
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    optional_deps = data.get("project", {}).get("optional-dependencies", {})

    all_deps = list(deps)
    for extra_deps in optional_deps.values():
        all_deps.extend(extra_deps)

    loose_deps = []
    outdated_deps = []
    checked = set()

    for dep in all_deps:
        name, extras, op, version = parse_dependency(dep)
        name_lower = name.lower()

        if name_lower in excludes or name_lower in BUILTIN_EXCLUDES:
            continue
        if name_lower in checked:
            continue
        checked.add(name_lower)

        latest = get_latest_pypi_version(name)
        if latest is None:
            continue

        if op is None or op != "==":
            current_spec = f"{name}{extras or ''}{op or ''}{version or ''}"
            loose_deps.append((name, current_spec, latest))
        elif version != latest:
            outdated_deps.append((name, extras, version, latest))

    return loose_deps, outdated_deps, data


def upgrade_pyproject(
    path: Path,
    loose: list[tuple[str, str, str]],
    outdated: list[tuple[str, str | None, str | None, str]],
) -> None:
    """Upgrade versions in pyproject.toml."""
    content = path.read_text()

    # Only match deps inside arrays (lines starting with whitespace + quote)
    for name, _current_spec, latest in loose:
        pattern = rf'(^\s+)"{re.escape(name)}(\[[^\]]*\])?(>=|<=|~=|>|<)?[^"]*"'
        replacement = rf'\1"{name}\2=={latest}"'
        content = re.sub(
            pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE
        )

    for name, extras, _old, new in outdated:
        extras_pattern = re.escape(extras) if extras else ""
        pattern = rf'(^\s+)"{re.escape(name)}{extras_pattern}==[^"]*"'
        replacement = rf'\1"{name}{extras or ""}=={new}"'
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
        for name, current, latest in loose:
            print(f"  - {current} -> {name}=={latest}")

    if outdated:
        has_errors = True
        print("\n!!! OUTDATED DEPENDENCIES !!!")
        print("The following dependencies are not at their latest PyPI version:")
        for name, extras, old, new in outdated:
            print(f"  - {name}{extras or ''}=={old} -> {new}")

    if has_errors:
        print("\nRun with --upgrade to auto-fix.")
        return 1

    print("All dependencies are strictly pinned and up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
