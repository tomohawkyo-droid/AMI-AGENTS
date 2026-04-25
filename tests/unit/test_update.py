"""Unit tests for ami/scripts/update.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ami.scripts.update_ci import run_from_defaults
from ami.scripts.update_discovery import (
    categorize,
    discover_repos,
    find_ami_root,
    run_post_system_update,
)
from ami.scripts.update_display import (
    print_dirty_error,
    print_summary,
    print_tier_status,
)
from ami.scripts.update_git import (
    analyze_repo,
    check_dirty,
    count_behind,
    get_current_branch,
    get_remotes,
    is_ancestor,
    pull_updates,
    ref_exists,
)
from ami.scripts.update_types import PullResult, RemoteUpdate, RepoInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_THREE_COMMITS = 3
_FIVE_COMMITS = 5


def _completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _repo(path: Path | None = None, name: str = "test-repo") -> RepoInfo:
    return RepoInfo(path=path or Path("/fake"), name=name)


# ---------------------------------------------------------------------------
# find_ami_root
# ---------------------------------------------------------------------------


class TestFindAmiRoot:
    def test_returns_env_var_when_set(self, tmp_path: Path) -> None:
        with patch.dict("os.environ", {"AMI_ROOT": str(tmp_path)}):
            assert find_ami_root() == tmp_path

    def test_walks_up_to_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").touch()
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        fake_script = nested / "update.py"
        fake_script.touch()

        # Patch __file__ at module level so Path(__file__) resolves to our fake
        with (
            patch.dict("os.environ", {}, clear=False),
            patch("ami.scripts.update_discovery.os.environ.get", return_value=None),
            patch("ami.scripts.update_discovery.__file__", str(fake_script)),
        ):
            assert find_ami_root() == tmp_path

    def test_raises_when_no_root(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        fake_script = nested / "update.py"
        fake_script.touch()

        with (
            patch.dict("os.environ", {}, clear=False),
            patch("ami.scripts.update_discovery.os.environ.get", return_value=None),
            patch("ami.scripts.update_discovery.__file__", str(fake_script)),
            pytest.raises(RuntimeError, match="Cannot determine AMI_ROOT"),
        ):
            find_ami_root()


# ---------------------------------------------------------------------------
# discover_repos
# ---------------------------------------------------------------------------


class TestDiscoverRepos:
    def test_finds_repos_in_projects(self, tmp_path: Path) -> None:
        (tmp_path / "projects" / "my-app" / ".git").mkdir(parents=True)
        (tmp_path / "projects" / "other" / ".git").mkdir(parents=True)

        repos = discover_repos(tmp_path)
        names = [r.name for r in repos]
        assert "AMI-AGENTS" in names
        assert "projects/my-app" in names
        assert "projects/other" in names

    def test_excludes_configured_repos(self, tmp_path: Path) -> None:
        (tmp_path / "projects" / "AMI-SRP" / ".git").mkdir(parents=True)
        repos = discover_repos(tmp_path)
        names = [r.name for r in repos]
        assert "projects/AMI-SRP" not in names

    def test_excludes_submodules(self, tmp_path: Path) -> None:
        sub = tmp_path / "projects" / "foo" / "himalaya" / ".git"
        sub.mkdir(parents=True)
        # parent must also be a repo so the walk reaches it
        (tmp_path / "projects" / "foo" / ".git").mkdir(parents=True)
        repos = discover_repos(tmp_path)
        names = [r.name for r in repos]
        assert not any("himalaya" in n for n in names)

    def test_no_projects_dir(self, tmp_path: Path) -> None:
        repos = discover_repos(tmp_path)
        assert len(repos) == 1
        assert repos[0].name == "AMI-AGENTS"

    def test_sorted_output(self, tmp_path: Path) -> None:
        for n in ("z-repo", "a-repo", "m-repo"):
            (tmp_path / "projects" / n / ".git").mkdir(parents=True)
        repos = discover_repos(tmp_path)
        names = [r.name for r in repos]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# categorize
# ---------------------------------------------------------------------------


class TestCategorize:
    def test_system_tier_ordering(self) -> None:
        repos = [
            _repo(name="projects/AMI-DATAOPS"),
            _repo(name="projects/AMI-CI"),
            _repo(name="AMI-AGENTS"),
            _repo(name="projects/my-app"),
        ]
        system = categorize(repos, "system")
        names = [r.name for r in system]
        assert names == ["projects/AMI-CI", "projects/AMI-DATAOPS", "AMI-AGENTS"]

    def test_apps_tier_excludes_system(self) -> None:
        repos = [
            _repo(name="projects/AMI-CI"),
            _repo(name="AMI-AGENTS"),
            _repo(name="projects/my-app"),
        ]
        apps = categorize(repos, "apps")
        assert len(apps) == 1
        assert apps[0].name == "projects/my-app"


# ---------------------------------------------------------------------------
# check_dirty
# ---------------------------------------------------------------------------


class TestCheckDirty:
    @patch("ami.scripts.update_git._git")
    def test_clean_repos(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="")
        result = check_dirty([_repo()])
        assert result == []

    @patch("ami.scripts.update_git._git")
    def test_dirty_repos(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout=" M file.py\n")
        repo = _repo()
        result = check_dirty([repo])
        assert result == [repo]


# ---------------------------------------------------------------------------
# get_current_branch
# ---------------------------------------------------------------------------


class TestGetCurrentBranch:
    @patch("ami.scripts.update_git._git")
    def test_normal_branch(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="main\n")
        assert get_current_branch(_repo()) == "main"

    @patch("ami.scripts.update_git._git")
    def test_detached_head(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="")
        assert get_current_branch(_repo()) is None


# ---------------------------------------------------------------------------
# get_remotes
# ---------------------------------------------------------------------------


class TestGetRemotes:
    @patch("ami.scripts.update_git._git")
    def test_multiple_remotes(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="origin\nupstream\n")
        assert get_remotes(_repo()) == ["origin", "upstream"]

    @patch("ami.scripts.update_git._git")
    def test_no_remotes(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="")
        assert get_remotes(_repo()) == []


# ---------------------------------------------------------------------------
# ref_exists
# ---------------------------------------------------------------------------


class TestRefExists:
    @patch("ami.scripts.update_git._git")
    def test_exists(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(returncode=0)
        assert ref_exists(_repo(), "origin/main") is True

    @patch("ami.scripts.update_git._git")
    def test_not_exists(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(returncode=1)
        assert ref_exists(_repo(), "origin/gone") is False


# ---------------------------------------------------------------------------
# count_behind
# ---------------------------------------------------------------------------


class TestCountBehind:
    @patch("ami.scripts.update_git._git")
    def test_normal_count(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="3\n")
        assert count_behind(_repo(), "HEAD..origin/main") == _THREE_COMMITS

    @patch("ami.scripts.update_git._git")
    def test_parse_error(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="not-a-number\n")
        assert count_behind(_repo(), "HEAD..origin/main") == 0


# ---------------------------------------------------------------------------
# is_ancestor
# ---------------------------------------------------------------------------


class TestIsAncestor:
    @patch("ami.scripts.update_git._git")
    def test_true(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(returncode=0)
        assert is_ancestor(_repo(), "abc", "def") is True

    @patch("ami.scripts.update_git._git")
    def test_false(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(returncode=1)
        assert is_ancestor(_repo(), "abc", "def") is False


# ---------------------------------------------------------------------------
# analyze_repo
# ---------------------------------------------------------------------------


class TestAnalyzeRepo:
    @patch("ami.scripts.update_git._git")
    def test_fetch_fails(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(returncode=1)
        assert analyze_repo(_repo()) == []

    @patch("ami.scripts.update_git.is_ancestor", return_value=True)
    @patch("ami.scripts.update_git.count_behind", return_value=0)
    @patch("ami.scripts.update_git.ref_exists", return_value=True)
    @patch("ami.scripts.update_git.get_remotes", return_value=["origin"])
    @patch("ami.scripts.update_git.get_current_branch", return_value=None)
    @patch("ami.scripts.update_git._git")
    def test_detached_head(
        self,
        mock_git: MagicMock,
        *_: Any,
    ) -> None:
        mock_git.return_value = _completed(returncode=0)
        assert analyze_repo(_repo()) == []

    @patch("ami.scripts.update_git.get_remotes", return_value=[])
    @patch("ami.scripts.update_git.get_current_branch", return_value="main")
    @patch("ami.scripts.update_git._git")
    def test_no_remotes(
        self,
        mock_git: MagicMock,
        *_: Any,
    ) -> None:
        mock_git.return_value = _completed(returncode=0)
        assert analyze_repo(_repo()) == []

    @patch("ami.scripts.update_git.is_ancestor", return_value=True)
    @patch("ami.scripts.update_git.count_behind", return_value=_FIVE_COMMITS)
    @patch("ami.scripts.update_git.ref_exists", return_value=True)
    @patch("ami.scripts.update_git.get_remotes", return_value=["origin"])
    @patch("ami.scripts.update_git.get_current_branch", return_value="main")
    @patch("ami.scripts.update_git._git")
    def test_updates_found(
        self,
        mock_git: MagicMock,
        *_: Any,
    ) -> None:
        mock_git.return_value = _completed(returncode=0)
        updates = analyze_repo(_repo())
        assert len(updates) == 1
        assert updates[0].commits_behind == _FIVE_COMMITS
        assert updates[0].can_ff is True

    @patch("ami.scripts.update_git.count_behind", return_value=0)
    @patch("ami.scripts.update_git.ref_exists", return_value=True)
    @patch("ami.scripts.update_git.get_remotes", return_value=["origin"])
    @patch("ami.scripts.update_git.get_current_branch", return_value="main")
    @patch("ami.scripts.update_git._git")
    def test_no_updates(
        self,
        mock_git: MagicMock,
        *_: Any,
    ) -> None:
        mock_git.return_value = _completed(returncode=0)
        assert analyze_repo(_repo()) == []


# ---------------------------------------------------------------------------
# pull_updates
# ---------------------------------------------------------------------------


class TestPullUpdates:
    @patch("ami.scripts.update_git._git")
    def test_success(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout="Already up to date.\n")
        repo = _repo()
        update = RemoteUpdate(
            repo=repo,
            remote="origin",
            branch="main",
            commits_behind=2,
            can_ff=True,
        )
        results = pull_updates([update])
        assert len(results) == 1
        assert results[0].success is True

    @patch("ami.scripts.update_git._git")
    def test_failure(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(returncode=1, stderr="error")
        repo = _repo()
        update = RemoteUpdate(
            repo=repo,
            remote="origin",
            branch="main",
            commits_behind=2,
            can_ff=True,
        )
        results = pull_updates([update])
        assert len(results) == 1
        assert results[0].success is False


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


class TestPrintDirtyError:
    def test_output_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_dirty_error([_repo(name="foo"), _repo(name="bar")])
        out = capsys.readouterr().out
        assert "foo" in out
        assert "bar" in out
        assert "uncommitted" in out


class TestPrintTierStatus:
    def test_output_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        repo = _repo(name="my-proj")
        update = RemoteUpdate(
            repo=repo,
            remote="origin",
            branch="main",
            commits_behind=_THREE_COMMITS,
            can_ff=True,
        )
        up_to_date = _repo(name="other-proj")
        print_tier_status("SYSTEM", [update], [repo, up_to_date])
        out = capsys.readouterr().out
        assert "SYSTEM" in out
        assert "my-proj" in out
        assert "already up to date" in out


class TestPrintSummary:
    def test_with_results(self, capsys: pytest.CaptureFixture[str]) -> None:
        repo = _repo(name="my-repo")
        result = PullResult(repo=repo, remote="origin", success=True, output="ok")
        print_summary([result], "APPS")
        out = capsys.readouterr().out
        assert "APPS" in out
        assert "my-repo" in out
        assert "pulled" in out

    def test_empty_results(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_summary([], "SYSTEM")
        out = capsys.readouterr().out
        assert out == ""


class TestRunPostSystemUpdate:
    def test_runs_uv_sync_and_hooks(self, tmp_path: Path) -> None:
        boot_uv = tmp_path / ".boot-linux" / "bin" / "uv"
        boot_uv.parent.mkdir(parents=True)
        boot_uv.write_text("")
        ci_hooks = tmp_path / "projects" / "AMI-CI" / "scripts" / "generate-hooks"
        ci_hooks.parent.mkdir(parents=True)
        ci_hooks.write_text("")
        dataops = tmp_path / "projects" / "AMI-DATAOPS" / "pyproject.toml"
        dataops.parent.mkdir(parents=True)
        dataops.write_text("")

        with patch("ami.scripts.update_discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_post_system_update(tmp_path)

        _min_calls = 2
        assert mock_run.call_count >= _min_calls

    def test_regenerates_hooks_in_every_system_repo(self, tmp_path: Path) -> None:
        boot_uv = tmp_path / ".boot-linux" / "bin" / "uv"
        boot_uv.parent.mkdir(parents=True)
        boot_uv.write_text("")
        ci_hooks = tmp_path / "projects" / "AMI-CI" / "scripts" / "generate-hooks"
        ci_hooks.parent.mkdir(parents=True)
        ci_hooks.write_text("")
        (tmp_path / ".pre-commit-config.yaml").write_text("")
        (tmp_path / "projects" / "AMI-CI" / ".pre-commit-config.yaml").write_text("")
        dataops_dir = tmp_path / "projects" / "AMI-DATAOPS"
        dataops_dir.mkdir(parents=True, exist_ok=True)
        (dataops_dir / "pyproject.toml").write_text("")
        (dataops_dir / ".pre-commit-config.yaml").write_text("")

        with patch("ami.scripts.update_discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_post_system_update(tmp_path)

        hook_cwds = {
            call.kwargs.get("cwd")
            for call in mock_run.call_args_list
            if call.args and call.args[0][0] == "bash"
        }
        assert str(tmp_path) in hook_cwds
        assert str(tmp_path / "projects" / "AMI-CI") in hook_cwds
        assert str(tmp_path / "projects" / "AMI-DATAOPS") in hook_cwds


class TestRunFromDefaults:
    def test_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.yaml"
        repos: list[RepoInfo] = []
        result = run_from_defaults(missing, repos, repos, tmp_path)
        assert result == 1

    def test_all_clean(self, tmp_path: Path) -> None:
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text("remote: origin\ntiers: [system]\n")
        repo = _repo(name="projects/AMI-CI", path=tmp_path)
        run_path = "ami.scripts.update_git._git"
        with patch(run_path) as mock_git:
            mock_git.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = run_from_defaults(defaults, [repo], [], tmp_path)
        assert result == 0
