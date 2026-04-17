"""Debug log writer for ami-banner / ami-extra tool-check runs.

Opens a JSON-lines log file under AMI_ROOT/logs/ each time the banner
runs its tool health checks. The log captures every tool's status,
the full command executed, stdout, stderr, returncode, elapsed time,
and exceptions. Use it to diagnose why a tool is showing as
UNAVAILABLE / DEGRADED / unhealthy without re-running anything.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Iterator
    from io import TextIOWrapper

# A log record is a dict whose values are JSON-friendly scalars or lists.
# object (not Any) keeps the type loose without tripping the "no Any" ban.
LogRecord: TypeAlias = dict[str, object]
LogFn: TypeAlias = Callable[[LogRecord], None]


class CheckRecord(NamedTuple):
    """Typed payload the run_check hook passes to make_check_hook."""

    command: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    elapsed_s: float
    healthy: bool
    version: str | None
    exception: str | None


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _write_record(fh: TextIOWrapper, record: LogRecord) -> None:
    record.setdefault("ts", datetime.now(tz=UTC).isoformat())
    try:
        fh.write(json.dumps(record, default=str) + "\n")
        fh.flush()
    except (OSError, ValueError) as exc:
        # Banner logging must not crash the banner itself. Surface the cause
        # on stderr (once per call) so the failure is visible in shell output.
        print(f"[banner-log] write failed: {exc}", file=sys.stderr)


def _close_fh(fh: TextIOWrapper) -> None:
    try:
        fh.close()
    except OSError as exc:
        print(f"[banner-log] close failed: {exc}", file=sys.stderr)


def _write_footer(path: Path) -> None:
    if not sys.stdout.isatty():
        return
    try:
        sys.stderr.write(f"\033[2m[banner log: {path}]\033[0m\n")
    except OSError:
        # stderr not writable; nothing to salvage.
        return


@contextmanager
def banner_log_session(root: Path, mode: str) -> Iterator[LogFn]:
    """Open a JSON-lines log file under {root}/logs/; yield a log function.

    The file is named banner-<mode>-<timestamp>.log. The context manager
    always closes the file on exit and never raises to the caller.
    """
    logs_dir = root / "logs"
    fh: TextIOWrapper | None = None
    path: Path | None = None
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        path = logs_dir / f"banner-{mode}-{_timestamp()}.log"
        fh = path.open("w", encoding="utf-8")
        _write_record(
            fh,
            {
                "event": "session_start",
                "mode": mode,
                "root": str(root),
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "python": sys.executable,
                "tty": sys.stdout.isatty(),
            },
        )
    except OSError as exc:
        # Could not create the log file. Announce it once and continue with a
        # noop logger; the banner itself must still render.
        print(f"[banner-log] setup failed: {exc}", file=sys.stderr)
        fh = None
        path = None

    start = time.monotonic()

    def log(record: LogRecord) -> None:
        if fh is not None:
            _write_record(fh, record)

    try:
        yield log
    finally:
        if fh is not None:
            _write_record(
                fh,
                {
                    "event": "session_end",
                    "elapsed_s": round(time.monotonic() - start, 3),
                },
            )
            _close_fh(fh)
        if path is not None:
            _write_footer(path)


def make_check_hook(log: LogFn, ext_name: str) -> Callable[[CheckRecord], None]:
    """Return a log_hook suitable to pass into run_check(..., log_hook=...).

    The returned callable takes a typed CheckRecord so run_check does not
    have to pass nine keyword arguments.
    """

    def hook(record: CheckRecord) -> None:
        log(
            {
                "event": "check",
                "name": ext_name,
                "command": record.command,
                "returncode": record.returncode,
                "stdout": record.stdout,
                "stderr": record.stderr,
                "elapsed_s": round(record.elapsed_s, 3),
                "healthy": record.healthy,
                "version": record.version,
                "exception": record.exception,
            },
        )

    return hook
