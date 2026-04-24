"""Unit tests for ami/scripts/shell/banner_log.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ami.scripts.shell.banner_log import (
    CheckRecord,
    _write_record,
    banner_log_session,
    make_check_hook,
)

_EXPECTED_ELAPSED = 0.123


class TestBannerLogSession:
    def test_creates_log_file(self, tmp_path: Path) -> None:
        with banner_log_session(tmp_path, "banner") as log:
            log({"event": "resolved", "name": "x"})
        files = list((tmp_path / "logs").glob("banner-banner-*.log"))
        assert len(files) == 1
        contents = files[0].read_text().splitlines()
        events = [json.loads(line)["event"] for line in contents]
        assert "session_start" in events
        assert "resolved" in events
        assert "session_end" in events

    def test_logs_session_metadata(self, tmp_path: Path) -> None:
        with banner_log_session(tmp_path, "doctor") as _:
            pass
        files = list((tmp_path / "logs").glob("banner-doctor-*.log"))
        first = json.loads(files[0].read_text().splitlines()[0])
        assert first["event"] == "session_start"
        assert first["mode"] == "doctor"
        assert first["root"] == str(tmp_path)
        assert "python" in first
        assert "pid" in first

    def test_survives_oserror_on_open(self, tmp_path: Path) -> None:
        # Make logs/ creation fail
        with (
            patch(
                "ami.scripts.shell.banner_log.Path.mkdir",
                side_effect=OSError("denied"),
            ),
            banner_log_session(tmp_path, "banner") as log,
        ):
            log({"event": "resolved"})  # must not raise
        # No log file created
        assert not (tmp_path / "logs").exists() or not list(
            (tmp_path / "logs").glob("*")
        )

    def test_write_record_swallows_ioerror_on_closed_file(self, tmp_path: Path) -> None:
        # _write_record is the internal helper; hit its OSError branch by
        # handing it a closed file handle.
        path = tmp_path / "sink.log"
        fh = path.open("w", encoding="utf-8")
        fh.close()
        _write_record(fh, {"event": "dead"})  # must not raise

    def test_unserializable_record_is_swallowed(self, tmp_path: Path) -> None:
        # default=str in _write_record handles objects that aren't JSON
        # serializable; circular references still raise ValueError which
        # the helper swallows.
        with banner_log_session(tmp_path, "banner") as log:
            circular: dict = {"event": "x"}
            circular["self"] = circular
            log(circular)  # must not raise
        # Session file still exists and session_start/end were recorded
        files = list((tmp_path / "logs").glob("banner-banner-*.log"))
        assert files


class TestMakeCheckHook:
    def test_hook_writes_record_with_all_fields(self) -> None:
        captured: list[dict] = []

        def log(record: dict) -> None:
            captured.append(record)

        hook = make_check_hook(log, "ami-test")
        hook(
            CheckRecord(
                command=["/bin/echo", "x"],
                returncode=0,
                stdout="out",
                stderr="",
                elapsed_s=_EXPECTED_ELAPSED,
                healthy=True,
                version="1.2.3",
                exception=None,
            ),
        )
        assert len(captured) == 1
        record = captured[0]
        assert record["event"] == "check"
        assert record["name"] == "ami-test"
        assert record["command"] == ["/bin/echo", "x"]
        assert record["returncode"] == 0
        assert record["stdout"] == "out"
        assert record["healthy"] is True
        assert record["version"] == "1.2.3"
        assert record["exception"] is None
        # Elapsed rounded to 3 decimals
        assert record["elapsed_s"] == _EXPECTED_ELAPSED

    def test_hook_handles_failure_record(self) -> None:
        captured: list[dict] = []
        hook = make_check_hook(captured.append, "ami-broken")
        hook(
            CheckRecord(
                command=["/bin/false"],
                returncode=None,
                stdout="",
                stderr="boom",
                elapsed_s=5.0,
                healthy=False,
                version=None,
                exception="TimeoutExpired",
            ),
        )
        record = captured[0]
        assert record["healthy"] is False
        assert record["exception"] == "TimeoutExpired"
        assert record["name"] == "ami-broken"
