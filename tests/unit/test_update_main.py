"""Unit tests for terminal restore, main() wrapper, and --ci flag."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.update import (
    DEFAULT_CI_CONFIG,
    _main_impl,
    _restore_terminal,
    main,
)


class TestRestoreTerminal:
    def test_noop_when_not_tty(self) -> None:
        with (
            patch("ami.scripts.update.sys.stdout.isatty", return_value=False),
            patch("ami.scripts.update.sys.stdout.write") as mock_write,
        ):
            _restore_terminal()
        mock_write.assert_not_called()

    def test_writes_ansi_when_tty(self) -> None:
        with (
            patch("ami.scripts.update.sys.stdout.isatty", return_value=True),
            patch("ami.scripts.update.sys.stdout.write") as mock_write,
            patch("ami.scripts.update.sys.stdout.flush"),
        ):
            _restore_terminal()
        writes = [call.args[0] for call in mock_write.call_args_list]
        assert "\033[?25h" in writes
        assert "\033[r" in writes
        assert "\033[999E" in writes

    def test_swallows_oserror(self) -> None:
        with (
            patch("ami.scripts.update.sys.stdout.isatty", return_value=True),
            patch(
                "ami.scripts.update.sys.stdout.write",
                side_effect=OSError("closed"),
            ),
        ):
            _restore_terminal()  # must not raise


class TestMainEntry:
    def test_keyboard_interrupt_restores_and_reraises(self) -> None:
        with (
            patch(
                "ami.scripts.update._main_impl",
                side_effect=KeyboardInterrupt,
            ),
            patch("ami.scripts.update._restore_terminal") as mock_restore,
            pytest.raises(KeyboardInterrupt),
        ):
            main()
        assert mock_restore.called

    def test_exception_restores_and_reraises(self) -> None:
        with (
            patch(
                "ami.scripts.update._main_impl",
                side_effect=RuntimeError("boom"),
            ),
            patch("ami.scripts.update._restore_terminal") as mock_restore,
            pytest.raises(RuntimeError, match="boom"),
        ):
            main()
        assert mock_restore.called

    def test_clean_exit_still_restores(self) -> None:
        with (
            patch("ami.scripts.update._main_impl", return_value=0),
            patch("ami.scripts.update._restore_terminal") as mock_restore,
        ):
            rc = main()
        assert rc == 0
        assert mock_restore.called


class TestCiFlag:
    def test_ci_without_defaults_uses_repo_default(self, tmp_path: Path) -> None:
        default_yaml = tmp_path / DEFAULT_CI_CONFIG
        default_yaml.parent.mkdir(parents=True, exist_ok=True)
        default_yaml.write_text("remote: origin\ntiers: []\n")
        with (
            patch(
                "ami.scripts.update.argparse.ArgumentParser.parse_args",
                return_value=argparse.Namespace(defaults=None, ci=True),
            ),
            patch("ami.scripts.update.find_ami_root", return_value=tmp_path),
            patch("ami.scripts.update.discover_repos", return_value=[]),
            patch("ami.scripts.update._run_from_defaults", return_value=0) as mock_run,
        ):
            rc = _main_impl()
        assert rc == 0
        assert mock_run.call_args.args[0] == default_yaml

    def test_explicit_defaults_wins_over_ci(self, tmp_path: Path) -> None:
        explicit = tmp_path / "custom.yaml"
        with (
            patch(
                "ami.scripts.update.argparse.ArgumentParser.parse_args",
                return_value=argparse.Namespace(defaults=explicit, ci=True),
            ),
            patch("ami.scripts.update.find_ami_root", return_value=tmp_path),
            patch("ami.scripts.update.discover_repos", return_value=[]),
            patch("ami.scripts.update._run_from_defaults", return_value=0) as mock_run,
        ):
            _main_impl()
        assert mock_run.call_args.args[0] == explicit
