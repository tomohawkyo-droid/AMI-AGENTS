"""Unit tests for ami.scripts.shell.banner_helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ami.scripts.shell.banner_helper import (
    _BannerCtx,
    _color_for,
    _format_features,
    _format_partial_line,
    _has_failed_container_dep,
    _icon_for,
    _print_extension,
    _title_for,
    main,
    output_banner,
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

    def test_mismatched_listed(self, capsys) -> None:
        exts = [
            _make_ext(
                "old-cmd",
                Status.VERSION_MISMATCH,
                reason="1.0.0 < required minVersion 2.0.0",
            ),
        ]
        output_extra(exts)
        captured = capsys.readouterr()
        assert "old-cmd" in captured.out
        assert "VERSION_MISMATCH" in captured.out
        assert "minVersion" in captured.out

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


class TestFormatFeatures:
    def test_with_features(self) -> None:
        ext = _make_ext("cmd", Status.READY)
        ext.entry["features"] = ["a", "b", "c"]
        result = _format_features(ext)
        assert result is not None
        assert "a, b, c" in result

    def test_no_features(self) -> None:
        ext = _make_ext("cmd", Status.READY)
        assert _format_features(ext) is None


class TestFormatPartialLine:
    def test_contains_name_and_desc(self) -> None:
        ext = _make_ext("my-cmd", Status.READY)
        line = _format_partial_line(ext, "\033[0m", "v1.0")
        assert "my-cmd" in line
        assert "Test my-cmd" in line
        assert "v1.0" in line


class TestHasFailedContainerDep:
    def test_no_deps(self) -> None:
        ext = _make_ext("cmd", Status.READY)
        assert not _has_failed_container_dep(ext, Path("/tmp"))

    def test_with_container_dep(self) -> None:
        ext = _make_ext("cmd", Status.READY)
        ext.entry["deps"] = [
            {"name": "ctr", "type": "container", "container": "x"},
        ]
        with patch(
            "ami.scripts.shell.banner_helper.check_dep",
            return_value=False,
        ):
            assert _has_failed_container_dep(ext, Path("/tmp"))


class TestPrintExtension:
    def test_no_check_quiet(self, capsys) -> None:
        ext = _make_ext("cmd", Status.READY)
        _print_extension(
            ext,
            Path("/tmp"),
            "\033[0m",
            _BannerCtx(quiet=True, is_tty=False, log=None),
        )
        out = capsys.readouterr().out
        assert "cmd" in out


class TestOutputBanner:
    def test_skips_hidden_and_unavailable(self, capsys) -> None:
        exts = [
            _make_ext("visible", Status.READY),
            _make_ext("hidden", Status.HIDDEN),
            _make_ext("gone", Status.UNAVAILABLE),
        ]
        output_banner(exts, Path("/tmp"), quiet=True)
        out = capsys.readouterr().out
        assert "visible" in out
        assert "hidden" not in out
        assert "gone" not in out

    def test_empty_category_skipped(self, capsys) -> None:
        exts = [
            _make_ext("h", Status.HIDDEN),
        ]
        output_banner(exts, Path("/tmp"), quiet=True)
        out = capsys.readouterr().out
        assert out == ""

    def test_degraded_shown_with_warning(self, capsys) -> None:
        ext = _make_ext("deg", Status.DEGRADED, reason="dep missing")
        output_banner([ext], Path("/tmp"), quiet=True)
        out = capsys.readouterr().out
        assert "deg" in out

    def test_with_check_non_tty(self, capsys) -> None:
        ext = _make_ext("cmd", Status.READY)
        ext.entry["check"] = {
            "command": ["echo", "v1.2.3"],
            "versionPattern": r"(\d+\.\d+\.\d+)",
            "healthExpect": "1.2.3",
        }
        _print_extension(
            ext,
            Path("/tmp"),
            "\033[0m",
            _BannerCtx(quiet=False, is_tty=False, log=None),
        )
        out = capsys.readouterr().out
        assert "cmd" in out

    def test_with_failed_health(self, capsys) -> None:
        ext = _make_ext("bad", Status.READY)
        ext.entry["check"] = {
            "command": ["false"],
            "healthExpect": "never",
        }
        _print_extension(
            ext,
            Path("/tmp"),
            "\033[0m",
            _BannerCtx(quiet=False, is_tty=False, log=None),
        )
        out = capsys.readouterr().out
        assert "bad" in out


class TestMain:
    def test_banner_mode(self) -> None:
        with (
            patch(
                "ami.scripts.shell.banner_helper.find_ami_root",
                return_value=Path("/tmp"),
            ),
            patch(
                "ami.scripts.shell.banner_helper.discover_manifests", return_value=[]
            ),
            patch(
                "ami.scripts.shell.banner_helper.resolve_extensions", return_value=[]
            ),
            patch("ami.scripts.shell.banner_helper.output_banner") as mock_banner,
            patch("sys.argv", ["banner_helper.py", "--mode", "banner", "--quiet"]),
        ):
            main()
            mock_banner.assert_called_once()

    def test_extra_mode(self) -> None:
        with (
            patch(
                "ami.scripts.shell.banner_helper.find_ami_root",
                return_value=Path("/tmp"),
            ),
            patch(
                "ami.scripts.shell.banner_helper.discover_manifests", return_value=[]
            ),
            patch(
                "ami.scripts.shell.banner_helper.resolve_extensions", return_value=[]
            ),
            patch("ami.scripts.shell.banner_helper.output_extra") as mock_extra,
            patch("sys.argv", ["banner_helper.py", "--mode", "extra"]),
        ):
            main()
            mock_extra.assert_called_once()

    def test_quiet_from_env(self) -> None:
        with (
            patch(
                "ami.scripts.shell.banner_helper.find_ami_root",
                return_value=Path("/tmp"),
            ),
            patch(
                "ami.scripts.shell.banner_helper.discover_manifests", return_value=[]
            ),
            patch(
                "ami.scripts.shell.banner_helper.resolve_extensions", return_value=[]
            ),
            patch("ami.scripts.shell.banner_helper.output_banner") as mock_banner,
            patch("sys.argv", ["banner_helper.py"]),
            patch.dict("os.environ", {"AMI_QUIET_MODE": "1"}),
        ):
            main()
            _, kwargs = mock_banner.call_args
            assert kwargs.get("quiet") is True
