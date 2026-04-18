"""Tests for version constraint checking and version_enforcer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ami.scripts.shell.extension_registry import ResolvedExtension, Status
from ami.scripts.shell.run_check import (
    HealthCheckResult,
    _check_version_constraint,
    _compare_semver,
    _parse_semver,
)
from ami.scripts.shell.version_enforcer import enforce_versions


class TestParseSemver:
    def test_three_part(self) -> None:
        assert _parse_semver("1.2.3") == (1, 2, 3)

    def test_with_pre_release(self) -> None:
        assert _parse_semver("1.2.3-rc1") == (1, 2, 3)

    def test_with_build(self) -> None:
        assert _parse_semver("1.2.3+build.42") == (1, 2, 3)

    def test_one_part(self) -> None:
        assert _parse_semver("5") == (5, 0, 0)

    def test_two_parts_fallback_takes_leading_int(self) -> None:
        # Fallback splits on non-digits, keeps leading integer only.
        assert _parse_semver("5.1") == (5, 0, 0)

    def test_empty(self) -> None:
        assert _parse_semver("") is None

    def test_non_numeric(self) -> None:
        assert _parse_semver("abc") is None


class TestCompareSemver:
    def test_less(self) -> None:
        assert _compare_semver("1.0.0", "2.0.0") == -1

    def test_greater(self) -> None:
        assert _compare_semver("2.0.0", "1.0.0") == 1

    def test_equal(self) -> None:
        assert _compare_semver("1.2.3", "1.2.3") == 0

    def test_unparseable(self) -> None:
        assert _compare_semver("abc", "1.2.3") == 0


class TestCheckVersionConstraint:
    def test_no_constraint(self) -> None:
        ok, reason = _check_version_constraint({"name": "x", "binary": "b"}, "1.2.3")
        assert ok is None
        assert reason is None

    def test_min_satisfied(self) -> None:
        entry = {"name": "x", "binary": "b", "minVersion": "1.0.0"}
        ok, reason = _check_version_constraint(entry, "1.2.3")
        assert ok is True
        assert reason is None

    def test_min_violated(self) -> None:
        entry = {"name": "x", "binary": "b", "minVersion": "2.0.0"}
        ok, reason = _check_version_constraint(entry, "1.2.3")
        assert ok is False
        assert "< required minVersion" in (reason or "")

    def test_max_violated(self) -> None:
        entry = {"name": "x", "binary": "b", "maxVersion": "1.0.0"}
        ok, reason = _check_version_constraint(entry, "1.2.3")
        assert ok is False
        assert "> allowed maxVersion" in (reason or "")

    def test_no_version_extracted_with_constraint(self) -> None:
        entry = {"name": "x", "binary": "b", "minVersion": "1.0.0"}
        ok, reason = _check_version_constraint(entry, None)
        assert ok is False
        assert "no version extracted" in (reason or "")


_VERSION_ENFORCER_RUN = "ami.scripts.shell.version_enforcer.run_check"


class TestEnforceVersions:
    def _make_ext(self, **entry_overrides: object) -> ResolvedExtension:
        entry = {
            "name": "foo",
            "binary": "bin/foo",
            "check": {"command": ["{binary}", "--version"]},
            **entry_overrides,
        }
        return ResolvedExtension(
            entry=entry,
            manifest_path=Path("/m"),
            status=Status.READY,
            reason="",
            version=None,
        )

    def test_no_constraint_passthrough(self, tmp_path: Path) -> None:
        ext = self._make_ext()
        out = enforce_versions([ext], tmp_path)
        assert out[0].status == Status.READY
        assert out[0].version is None

    def test_unavailable_passthrough(self, tmp_path: Path) -> None:
        ext = self._make_ext(minVersion="1.0.0")
        ext = ext._replace(status=Status.UNAVAILABLE, reason="missing")
        out = enforce_versions([ext], tmp_path)
        assert out[0].status == Status.UNAVAILABLE

    def test_mismatch_downgrades(self, tmp_path: Path) -> None:
        ext = self._make_ext(minVersion="2.0.0")
        with patch(
            _VERSION_ENFORCER_RUN,
            return_value=HealthCheckResult(
                healthy=True,
                version="1.2.3",
                version_ok=False,
                version_reason="1.2.3 < required minVersion 2.0.0",
            ),
        ):
            out = enforce_versions([ext], tmp_path)
        assert out[0].status == Status.VERSION_MISMATCH
        assert "minVersion" in out[0].reason
        assert out[0].version == "1.2.3"

    def test_ok_keeps_status(self, tmp_path: Path) -> None:
        ext = self._make_ext(minVersion="1.0.0")
        with patch(
            _VERSION_ENFORCER_RUN,
            return_value=HealthCheckResult(
                healthy=True,
                version="1.5.0",
                version_ok=True,
                version_reason=None,
            ),
        ):
            out = enforce_versions([ext], tmp_path)
        assert out[0].status == Status.READY
        assert out[0].version == "1.5.0"
