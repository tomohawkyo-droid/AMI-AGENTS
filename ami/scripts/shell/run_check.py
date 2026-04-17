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


class HealthCheckResult(NamedTuple):
    """Result of a health + version check."""

    healthy: bool
    version: str | None


def run_check(
    entry: ExtensionEntry,
    root: Path,
    *,
    log_hook: Callable[[CheckRecord], None] | None = None,
) -> HealthCheckResult:
    """Run health + version check. ``{python}`` -> hermetic interpreter. Max 5 s."""
    check = entry.get("check")
    if not check:
        return HealthCheckResult(healthy=True, version=None)

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

    if log_hook is not None:
        log_hook(
            CheckRecord(cmd, rc, stdout, stderr, elapsed, health_ok, version, exc),
        )
    return HealthCheckResult(healthy=health_ok, version=version)
