"""Unit tests for ami.scripts.shell.banner_helper."""

from __future__ import annotations

from pathlib import Path

from ami.scripts.shell.banner_helper import (
    _color_for,
    _icon_for,
    _title_for,
    output_extra,
)
from ami.scripts.shell.extension_registry import (
    ResolvedExtension,
    Status,
)


class TestColorFor:
    def test_known_category(self) -> None:
        result = _color_for("core")
        assert "\033[38;5;214m" in result

    def test_unknown_category(self) -> None:
        result = _color_for("mystery")
        assert "\033[" in result


class TestIconFor:
    def test_known_category(self) -> None:
        assert _icon_for("agents") == "\U0001f916"

    def test_unknown_category(self) -> None:
        assert _icon_for("mystery") == "\U0001f539"


class TestTitleFor:
    def test_known_category(self) -> None:
        assert "Core" in _title_for("core")

    def test_unknown_category(self) -> None:
        assert _title_for("mystery") == "Mystery"


def _make_ext(
    name: str,
    status: Status,
    reason: str = "",
    hint: str = "",
) -> ResolvedExtension:
    entry = {
        "name": name,
        "binary": f"bin/{name}",
        "description": f"Test {name}",
        "category": "core",
    }
    if hint:
        entry["installHint"] = hint
    return ResolvedExtension(
        entry=entry,
        manifest_path=Path("test.yaml"),
        status=status,
        reason=reason,
    )


class TestOutputExtra:
    def test_hidden_listed(self, capsys) -> None:
        exts = [_make_ext("hidden-cmd", Status.HIDDEN)]
        output_extra(exts)
        captured = capsys.readouterr()
        assert "hidden-cmd" in captured.out
        assert "Hidden" in captured.out

    def test_degraded_listed(self, capsys) -> None:
        exts = [_make_ext("bad-cmd", Status.DEGRADED, reason="dep missing")]
        output_extra(exts)
        captured = capsys.readouterr()
        assert "bad-cmd" in captured.out
        assert "DEGRADED" in captured.out
        assert "dep missing" in captured.out

    def test_unavailable_with_hint(self, capsys) -> None:
        exts = [
            _make_ext(
                "miss-cmd",
                Status.UNAVAILABLE,
                reason="not found",
                hint="make install",
            ),
        ]
        output_extra(exts)
        captured = capsys.readouterr()
        assert "miss-cmd" in captured.out
        assert "UNAVAILABLE" in captured.out
        assert "make install" in captured.out

    def test_no_issues(self, capsys) -> None:
        exts = [_make_ext("ok-cmd", Status.READY)]
        output_extra(exts)
        captured = capsys.readouterr()
        assert "No hidden" in captured.out

    def test_all_categories(self, capsys) -> None:
        exts = [
            _make_ext("h", Status.HIDDEN),
            _make_ext("d", Status.DEGRADED, reason="r"),
            _make_ext("u", Status.UNAVAILABLE, reason="r"),
        ]
        output_extra(exts)
        captured = capsys.readouterr()
        assert "Hidden" in captured.out
        assert "Degraded" in captured.out
        assert "Unavailable" in captured.out
