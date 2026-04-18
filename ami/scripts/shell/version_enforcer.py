"""Post-resolution version-constraint enforcement for extensions."""

from __future__ import annotations

from pathlib import Path

from ami.scripts.shell.extension_registry import ResolvedExtension, Status
from ami.scripts.shell.run_check import run_check


def enforce_versions(
    resolved: list[ResolvedExtension],
    root: Path,
) -> list[ResolvedExtension]:
    """Run health checks for entries with minVersion/maxVersion, downgrade on mismatch.

    Only touches entries whose resolved status is READY or DEGRADED and that
    declare at least one version constraint. UNAVAILABLE / HIDDEN stay put.
    Returns a new list with updated ``status`` / ``reason`` / ``version``.
    """
    out: list[ResolvedExtension] = []
    for ext in resolved:
        entry = ext.entry
        has_constraint = bool(entry.get("minVersion") or entry.get("maxVersion"))
        if not has_constraint or ext.status in (Status.UNAVAILABLE, Status.HIDDEN):
            out.append(ext)
            continue
        result = run_check(entry, root)
        if result.version_ok is False:
            reason = result.version_reason or "version constraint violated"
            out.append(
                ResolvedExtension(
                    entry=entry,
                    manifest_path=ext.manifest_path,
                    status=Status.VERSION_MISMATCH,
                    reason=reason,
                    version=result.version,
                ),
            )
        else:
            out.append(
                ResolvedExtension(
                    entry=entry,
                    manifest_path=ext.manifest_path,
                    status=ext.status,
                    reason=ext.reason,
                    version=result.version,
                ),
            )
    return out
