"""Extension registry: discover, validate, resolve, check."""

from __future__ import annotations

import enum
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple, TypedDict

import yaml

# Re-export so callers can keep using extension_registry.{run_check,HealthCheckResult}.
from ami.scripts.shell.run_check import HealthCheckResult, run_check

__all__ = ["HealthCheckResult", "run_check"]

# Typed structures for manifest data


class CheckConfig(TypedDict, total=False):
    """Extension health/version check configuration."""

    command: list[str]
    healthExpect: str
    versionPattern: str
    timeout: int


class DepConfig(TypedDict, total=False):
    """Extension dependency configuration."""

    name: str
    type: str
    path: str
    container: str
    required: bool


class CategoryProps(TypedDict, total=False):
    """Category display properties."""

    title: str
    icon: str
    color: str


class ExtensionEntry(TypedDict, total=False):
    """Single extension entry from a manifest file."""

    name: str
    binary: str
    description: str
    category: str
    features: list[str]
    bannerPriority: int
    hidden: bool
    container: str
    installHint: str
    check: CheckConfig
    deps: list[DepConfig]


class DepCheckResult(NamedTuple):
    """Result of checking additional dependencies."""

    status: Status
    reason: str


class CategoryGroup(NamedTuple):
    """A category and its extensions, for display."""

    name: str
    extensions: list[ResolvedExtension]


# Constants

REQUIRED_FIELDS = {"name", "binary", "description", "category"}
KNOWN_FIELDS = REQUIRED_FIELDS | {
    "features",
    "bannerPriority",
    "hidden",
    "container",
    "installHint",
    "check",
    "deps",
}

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "target",
    ".venv",
    ".boot-linux",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}

_MIN_DESC_LEN = 5
_MAX_CHECK_TIMEOUT = 5
_DEFAULT_BANNER_PRIORITY = 500

DEFAULT_CATEGORY_ORDER = [
    "core",
    "enterprise",
    "dev",
    "infra",
    "docs",
    "agents",
]

DEFAULT_CATEGORY_PROPS = {
    "core": {
        "title": "Core Execution & Management",
        "icon": "\U0001f7e1",
        "color": "gold",
    },
    "enterprise": {
        "title": "Enterprise Services",
        "icon": "\U0001f310",
        "color": "cyan",
    },
    "dev": {
        "title": "Development Tools",
        "icon": "\U0001f338",
        "color": "pink",
    },
    "infra": {
        "title": "Infrastructure & Networking",
        "icon": "\U0001f527",
        "color": "purple",
    },
    "docs": {
        "title": "Document Production",
        "icon": "\U0001f4c4",
        "color": "blue",
    },
    "agents": {
        "title": "AI Coding Agents (REQUIRE HUMAN SUPERVISION)",
        "icon": "\U0001f916",
        "color": "red",
    },
}


# Status enum & ResolvedExtension dataclass


class Status(enum.Enum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    HIDDEN = "hidden"


class ResolvedExtension(NamedTuple):
    """Resolved extension with status and optional version."""

    entry: ExtensionEntry
    manifest_path: Path
    status: Status
    reason: str = ""
    version: str | None = None


# Root discovery


def find_ami_root() -> Path:
    """Return the AMI project root directory.

    Checks ``AMI_ROOT`` env var first, then walks up from this
    file looking for ``pyproject.toml``.
    """
    env_root = os.environ.get("AMI_ROOT")
    if env_root:
        return Path(env_root)
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    msg = "Cannot determine AMI_ROOT"
    raise RuntimeError(msg)


# Manifest discovery


def discover_manifests(root: Path) -> list[Path]:
    """Recursively discover ``extension.manifest.yaml`` files.

    Prunes directories in ``EXCLUDE_DIRS`` and dot-prefixed dirs.
    """
    manifests: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]
        if "extension.manifest.yaml" in filenames:
            manifests.append(Path(dirpath) / "extension.manifest.yaml")
    return sorted(manifests)


# Validation


def validate_entry(entry: ExtensionEntry, manifest_path: Path) -> list[str]:
    """Validate a single extension entry against the schema.

    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        errors.append(f"{manifest_path}: missing required fields: {missing}")
    unknown = set(entry.keys()) - KNOWN_FIELDS
    if unknown:
        errors.append(f"{manifest_path}: unknown fields: {unknown}")
    desc = entry.get("description", "")
    if desc and len(desc) < _MIN_DESC_LEN:
        errors.append(f"{manifest_path}: description too short: {desc!r}")
    check = entry.get("check")
    if isinstance(check, dict):
        timeout = check.get("timeout", _MAX_CHECK_TIMEOUT)
        if timeout > _MAX_CHECK_TIMEOUT:
            errors.append(
                f"{manifest_path}: check timeout "
                f"{timeout}s exceeds max of "
                f"{_MAX_CHECK_TIMEOUT}s"
            )
    return errors


# Container runtime detection (cached)

_container_runtime_cache: list[str] = []


def get_container_runtime() -> str | None:
    """Return ``'podman'``, ``'docker'``, or ``None``. Cached after first call."""
    if not _container_runtime_cache:
        if shutil.which("podman"):
            _container_runtime_cache.append("podman")
        elif shutil.which("docker"):
            _container_runtime_cache.append("docker")
        else:
            _container_runtime_cache.append("")
    return _container_runtime_cache[0] or None


def check_container(name: str) -> bool:
    """Return True if a container named *name* exists."""
    runtime = get_container_runtime()
    if not runtime:
        return False
    try:
        result = subprocess.run(
            [
                runtime,
                "ps",
                "-a",
                "--filter",
                f"name={name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=_MAX_CHECK_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return name in result.stdout


# Dependency checking


def check_dep(dep: DepConfig, root: Path) -> bool:
    """Check a single dependency. Returns True if satisfied."""
    dep_type = dep.get("type", "")

    if dep_type == "binary":
        path = root / dep["path"]
        return path.exists() and os.access(path, os.X_OK)

    if dep_type == "submodule":
        path = root / dep["path"]
        return path.is_dir() and any(path.iterdir())

    if dep_type == "container":
        return check_container(dep.get("container", dep["name"]))

    if dep_type == "system-package":
        return shutil.which(dep["name"]) is not None

    if dep_type == "file":
        return (root / dep["path"]).exists()

    return False


def check_additional_deps(deps: list[DepConfig], root: Path) -> DepCheckResult:
    """Check additional deps. Returns ``(status, reason)``."""
    if not deps:
        return DepCheckResult(status=Status.READY, reason="")

    degraded_reasons: list[str] = []
    for dep in deps:
        present = check_dep(dep, root)
        required = dep.get("required", True)
        if not present and required:
            return DepCheckResult(
                status=Status.UNAVAILABLE,
                reason=f"missing required dep: {dep['name']}",
            )
        if not present and not required:
            degraded_reasons.append(f"optional dep missing: {dep['name']}")

    if degraded_reasons:
        return DepCheckResult(
            status=Status.DEGRADED,
            reason="; ".join(degraded_reasons),
        )
    return DepCheckResult(status=Status.READY, reason="")


# Resolution pipeline


def _resolve_entry(
    entry: ExtensionEntry,
    manifest_path: Path,
    root: Path,
) -> ResolvedExtension:
    """Resolve a single validated entry to a ResolvedExtension."""
    binary_path = root / entry["binary"]
    if entry["binary"].endswith(".py"):
        binary_exists = binary_path.is_file()
    else:
        binary_exists = binary_path.exists() and os.access(binary_path, os.X_OK)

    if not binary_exists:
        hint = entry.get("installHint", "")
        reason = f"binary not found: {entry['binary']}"
        if hint:
            reason += f" (install: {hint})"
        return ResolvedExtension(
            entry, manifest_path, Status.UNAVAILABLE, reason=reason
        )

    status, reason = check_additional_deps(entry.get("deps", []), root)

    if entry.get("hidden", False) and status == Status.READY:
        status = Status.HIDDEN

    return ResolvedExtension(entry, manifest_path, status, reason=reason)


def resolve_extensions(manifests: list[Path], root: Path) -> list[ResolvedExtension]:
    """Resolve manifests into a flat list of ResolvedExtension."""
    seen_names: dict[str, Path] = {}
    resolved: list[ResolvedExtension] = []

    for manifest_path in manifests:
        entries = _parse_manifest(manifest_path)
        if entries is None:
            continue

        for entry in entries:
            errors = validate_entry(entry, manifest_path)
            if errors:
                for err in errors:
                    print(f"ERROR: {err}", file=sys.stderr)
                continue

            name = entry["name"]

            if name in seen_names:
                print(
                    f"ERROR: duplicate extension '{name}' "
                    f"in {manifest_path} "
                    f"(first seen in {seen_names[name]}), "
                    f"skipping",
                    file=sys.stderr,
                )
                continue
            seen_names[name] = manifest_path

            resolved.append(_resolve_entry(entry, manifest_path, root))

    return resolved


def _parse_manifest(
    manifest_path: Path,
) -> list[ExtensionEntry] | None:
    """Parse a manifest file. Returns entries or None on error."""
    try:
        data = yaml.safe_load(manifest_path.read_text())
    except yaml.YAMLError as exc:
        print(
            f"ERROR: malformed YAML in {manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if not data or "extensions" not in data:
        return None

    entries: list[ExtensionEntry] = data.get("extensions", [])
    return entries


# Category helpers


def group_by_category(
    resolved: list[ResolvedExtension],
) -> list[CategoryGroup]:
    """Group extensions by category with ordering.

    Known categories appear in ``DEFAULT_CATEGORY_ORDER``; unknown
    ones are appended alphabetically.  Within each category,
    extensions sort by ``bannerPriority`` (default 500, lower first).
    """
    buckets: dict[str, list[ResolvedExtension]] = defaultdict(list)
    for ext in resolved:
        cat = ext.entry.get("category", "unknown")
        buckets.setdefault(cat, []).append(ext)

    for exts in buckets.values():
        exts.sort(key=lambda e: e.entry.get("bannerPriority", _DEFAULT_BANNER_PRIORITY))

    ordered: list[CategoryGroup] = [
        CategoryGroup(name=cat, extensions=buckets.pop(cat))
        for cat in DEFAULT_CATEGORY_ORDER
        if cat in buckets
    ]
    ordered.extend(
        CategoryGroup(name=cat, extensions=buckets[cat]) for cat in sorted(buckets)
    )

    return ordered
