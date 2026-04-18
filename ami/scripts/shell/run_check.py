"""Tool health + version check executed by the extension registry.

Owns ``HealthCheckResult`` (the output type) and ``run_check`` (the call).
Extracted from ``extension_registry`` to keep that module under the
512-line cap. ``extension_registry`` re-exports both names for
back-compat; new code can import from either.
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import TYPE_CHECKING, NamedTuple

from ami.scripts.shell.banner_log import CheckRecord

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ami.scripts.shell.extension_registry import ExtensionEntry


MAX_CHECK_TIMEOUT = 5

# Semver core: MAJOR.MINOR.PATCH with optional -pre / +build suffix we discard.
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
_SEMVER_PARTS = 3


class HealthCheckResult(NamedTuple):
    """Result of a health + version check."""

    healthy: bool
    version: str | None
    version_ok: bool | None = None
    version_reason: str | None = None


def _parse_semver(v: str) -> tuple[int, int, int] | None:
    """Parse a semver-ish string into a (major, minor, patch) tuple.

    Accepts ``1``, ``1.2``, ``1.2.3``, ``1.2.3-rc1``, ``1.2.3+build``.
    Missing components default to 0. Returns None if no leading integer
    is present.
    """
    if not v:
        return None
    m = _SEMVER_RE.match(v)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    # Fall back to best-effort: take leading int(s) separated by dots.
    parts = re.split(r"[^0-9]", v, maxsplit=1)[0].split(".")
    try:
        nums = [int(p) for p in parts if p]
    except ValueError:
        return None
    if not nums:
        return None
    while len(nums) < _SEMVER_PARTS:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _compare_semver(a: str, b: str) -> int:
    """Return -1/0/1 comparing two semver-ish strings. Unparseable -> 0."""
    pa = _parse_semver(a)
    pb = _parse_semver(b)
    if pa is None or pb is None:
        return 0
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def _check_version_constraint(
    entry: ExtensionEntry,
    version: str | None,
) -> tuple[bool | None, str | None]:
    """Compare *version* against the entry's minVersion / maxVersion.

    Returns ``(version_ok, reason)``:
    - ``(None, None)`` if the entry declares no constraint.
    - ``(True, None)`` if the observed version satisfies the constraint.
    - ``(False, reason)`` if the observed version violates the constraint
      (or if no version was extracted but a constraint is declared).
    """
    min_v = entry.get("minVersion")
    max_v = entry.get("maxVersion")
    if not min_v and not max_v:
        return None, None

    if version is None:
        bound = f">={min_v}" if min_v else f"<={max_v}"
        return False, f"no version extracted (required {bound})"

    if min_v and _compare_semver(version, min_v) < 0:
        return False, f"{version} < required minVersion {min_v}"
    if max_v and _compare_semver(version, max_v) > 0:
        return False, f"{version} > allowed maxVersion {max_v}"
    return True, None


def run_check(
    entry: ExtensionEntry,
    root: Path,
    *,
    log_hook: Callable[[CheckRecord], None] | None = None,
) -> HealthCheckResult:
    """Run health + version check. ``{python}`` -> hermetic interpreter. Max 5 s."""
    check = entry.get("check")
    if not check:
        # No check block — but minVersion/maxVersion can still be declared,
        # in which case we can't validate and must flag as such.
        v_ok, v_reason = _check_version_constraint(entry, None)
        healthy = v_ok is not False
        return HealthCheckResult(
            healthy=healthy,
            version=None,
            version_ok=v_ok,
            version_reason=v_reason,
        )

    binary = str(root / entry["binary"])
    venv_py = root / ".venv" / "bin" / "python"
    boot_py = root / ".boot-linux" / "python-env" / "bin" / "python"
    python_path = str(venv_py if venv_py.exists() else boot_py)
    cmd = [
        a.replace("{binary}", binary).replace("{python}", python_path)
        for a in check["command"]
    ]
    timeout = min(check.get("timeout", MAX_CHECK_TIMEOUT), MAX_CHECK_TIMEOUT)

    start = time.monotonic()
    rc: int | None = None
    stdout = stderr = ""
    exc: str | None = None
    output = ""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        rc, stdout, stderr = r.returncode, r.stdout, r.stderr
        output = stdout + stderr
    except subprocess.TimeoutExpired as e:
        exc = f"TimeoutExpired({timeout}s): {e}"
    except OSError as e:
        exc = f"OSError: {e}"

    elapsed = time.monotonic() - start
    health_ok = exc is None
    version: str | None = None
    if exc is None:
        if "healthExpect" in check:
            health_ok = check["healthExpect"] in output
        if "versionPattern" in check:
            m = re.search(check["versionPattern"], output)
            version = m.group(1) if m else None

    v_ok, v_reason = _check_version_constraint(entry, version)

    if log_hook is not None:
        log_hook(
            CheckRecord(cmd, rc, stdout, stderr, elapsed, health_ok, version, exc),
        )
    return HealthCheckResult(
        healthy=health_ok,
        version=version,
        version_ok=v_ok,
        version_reason=v_reason,
    )
