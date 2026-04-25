"""Unit tests for ami/scripts/update_interactive.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.scripts.update_interactive import (
    _run_tier_interactive,
    _select_updates_interactive,
    run_interactive,
)
from ami.scripts.update_types import PullResult, RemoteUpdate, RepoInfo


def _repo(name: str = "test-repo") -> RepoInfo:
    return RepoInfo(path=Path("/fake"), name=name)


def _update(name: str = "r", can_ff: bool = True) -> RemoteUpdate:
    return RemoteUpdate(
        repo=_repo(name=name),
        remote="origin",
        branch="main",
        commits_behind=1,
        can_ff=can_ff,
    )


def _result(name: str = "r", success: bool = True) -> PullResult:
    return PullResult(
        repo=_repo(name=name),
        remote="origin",
        success=success,
        output="ok",
    )


class TestSelectUpdatesInteractive:
    def test_empty_updates_returns_empty(self, capsys) -> None:
        result = _select_updates_interactive([], "title")
        assert result == []
        assert "Nothing to update" in capsys.readouterr().out

    def test_dialog_cancelled_returns_none(self) -> None:
        with patch(
            "ami.scripts.update_interactive._dialogs.multiselect", return_value=None
        ):
            result = _select_updates_interactive([_update()], "title")
        assert result is None

    def test_dialog_returns_unwrapped_updates(self) -> None:
        u = _update()
        item = MagicMock(value=u)
        with patch(
            "ami.scripts.update_interactive._dialogs.multiselect", return_value=[item]
        ):
            result = _select_updates_interactive([u], "title")
        assert result == [u]


class TestRunTierInteractive:
    def test_empty_repos_short_circuits(self) -> None:
        results, updates = _run_tier_interactive("SYSTEM", [])
        assert results == []
        assert updates == []

    def test_dirty_aborts_tier(self) -> None:
        repo = _repo()
        with (
            patch("ami.scripts.update_interactive.check_dirty", return_value=[repo]),
            patch("ami.scripts.update_interactive.print_dirty_error") as mock_err,
        ):
            results, updates = _run_tier_interactive("SYSTEM", [repo])
        assert results == []
        assert updates == []
        mock_err.assert_called_once_with([repo])

    def test_no_updates_returns_empty(self, capsys) -> None:
        repo = _repo()
        with (
            patch("ami.scripts.update_interactive.check_dirty", return_value=[]),
            patch("ami.scripts.update_interactive.analyze_repo", return_value=[]),
            patch("ami.scripts.update_interactive.print_tier_status"),
        ):
            results, updates = _run_tier_interactive("SYSTEM", [repo])
        assert results == []
        assert updates == []
        assert "Everything up to date" in capsys.readouterr().out

    def test_user_cancels_returns_empty(self, capsys) -> None:
        repo = _repo()
        u = _update()
        with (
            patch("ami.scripts.update_interactive.check_dirty", return_value=[]),
            patch("ami.scripts.update_interactive.analyze_repo", return_value=[u]),
            patch("ami.scripts.update_interactive.print_tier_status"),
            patch(
                "ami.scripts.update_interactive._select_updates_interactive",
                return_value=None,
            ),
        ):
            results, _updates = _run_tier_interactive("SYSTEM", [repo])
        assert results == []
        assert "Cancelled" in capsys.readouterr().out

    def test_pulls_chosen_updates(self) -> None:
        repo = _repo()
        u = _update()
        r = _result()
        with (
            patch("ami.scripts.update_interactive.check_dirty", return_value=[]),
            patch("ami.scripts.update_interactive.analyze_repo", return_value=[u]),
            patch("ami.scripts.update_interactive.print_tier_status"),
            patch(
                "ami.scripts.update_interactive._select_updates_interactive",
                return_value=[u],
            ),
            patch(
                "ami.scripts.update_interactive.pull_updates", return_value=[r]
            ) as mock_pull,
        ):
            results, _ = _run_tier_interactive("SYSTEM", [repo])
        assert results == [r]
        mock_pull.assert_called_once_with([u])


class TestRunInteractive:
    def test_system_only_skips_apps(self, tmp_path) -> None:
        sys_repos = [_repo("AMI-AGENTS")]
        app_repos = [_repo("projects/app")]
        sys_result = _result("AMI-AGENTS")
        with (
            patch("ami.scripts.update_interactive._run_tier_interactive") as mock_tier,
            patch("ami.scripts.update_interactive.run_post_system_update") as mock_post,
            patch("ami.scripts.update_interactive.print_summary"),
        ):
            mock_tier.return_value = ([sys_result], [])
            rc = run_interactive(sys_repos, app_repos, tmp_path, ["system"])
        assert rc == 0
        # Only one tier call (SYSTEM), not APPS
        assert mock_tier.call_count == 1
        assert mock_tier.call_args.args[0] == "SYSTEM"
        mock_post.assert_called_once_with(tmp_path)

    def test_apps_only_skips_system(self, tmp_path) -> None:
        sys_repos = [_repo("AMI-AGENTS")]
        app_repos = [_repo("projects/app")]
        app_result = _result("projects/app")
        with (
            patch("ami.scripts.update_interactive._run_tier_interactive") as mock_tier,
            patch("ami.scripts.update_interactive.run_post_system_update") as mock_post,
            patch("ami.scripts.update_interactive.print_summary"),
        ):
            mock_tier.return_value = ([app_result], [])
            rc = run_interactive(sys_repos, app_repos, tmp_path, ["apps"])
        assert rc == 0
        assert mock_tier.call_count == 1
        assert mock_tier.call_args.args[0] == "APPS"
        mock_post.assert_not_called()

    def test_all_tiers(self, tmp_path) -> None:
        sys_repos = [_repo("AMI-AGENTS")]
        app_repos = [_repo("projects/app")]
        expected_tier_calls = 2
        with (
            patch("ami.scripts.update_interactive._run_tier_interactive") as mock_tier,
            patch("ami.scripts.update_interactive.run_post_system_update"),
            patch("ami.scripts.update_interactive.print_summary"),
        ):
            mock_tier.return_value = ([_result()], [])
            rc = run_interactive(sys_repos, app_repos, tmp_path, ["system", "apps"])
        assert rc == 0
        assert mock_tier.call_count == expected_tier_calls

    def test_all_clean_short_circuits(self, tmp_path, capsys) -> None:
        with patch(
            "ami.scripts.update_interactive._run_tier_interactive",
            return_value=([], []),
        ):
            rc = run_interactive([], [], tmp_path, ["system", "apps"])
        assert rc == 0
        assert "Everything up to date" in capsys.readouterr().out

    def test_failed_pull_returns_nonzero(self, tmp_path) -> None:
        with (
            patch("ami.scripts.update_interactive._run_tier_interactive") as mock_tier,
            patch("ami.scripts.update_interactive.run_post_system_update"),
            patch("ami.scripts.update_interactive.print_summary"),
        ):
            mock_tier.return_value = ([_result(success=False)], [])
            rc = run_interactive([_repo()], [], tmp_path, ["system"])
        assert rc == 1
