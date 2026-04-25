"""Integration tests for ami/scripts/update.py against real git repos."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ami.scripts.update_ci import run_from_defaults
from ami.scripts.update_git import analyze_repo, check_dirty, pull_updates
from ami.scripts.update_types import RepoInfo

pytestmark = pytest.mark.integration


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _commit(cwd: Path, filename: str, content: str, message: str) -> None:
    (cwd / filename).write_text(content)
    _git(cwd, "add", filename)
    _git(cwd, "commit", "-m", message)


@pytest.fixture
def git_workspace(tmp_path: Path) -> dict[str, Path]:
    """Create an upstream bare repo + a clone with a fast-forwardable state."""
    upstream = tmp_path / "upstream.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(upstream))

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _commit(seed, "README.md", "init\n", "initial")
    _git(seed, "remote", "add", "origin", str(upstream))
    _git(seed, "push", "origin", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(upstream), str(clone))

    # Add a new commit on upstream via seed → push, so clone is one behind.
    _commit(seed, "new.txt", "new\n", "feature")
    _git(seed, "push", "origin", "main")

    return {"upstream": upstream, "seed": seed, "clone": clone}


class TestAnalyzeRepoReal:
    def test_fast_forward_detected(self, git_workspace: dict[str, Path]) -> None:
        repo = RepoInfo(path=git_workspace["clone"], name="clone")
        updates = analyze_repo(repo)
        assert len(updates) == 1
        update = updates[0]
        assert update.commits_behind == 1
        assert update.can_ff is True
        assert update.remote == "origin"
        assert update.branch == "main"

    def test_diverged_detected(self, git_workspace: dict[str, Path]) -> None:
        clone = git_workspace["clone"]
        _commit(clone, "local.txt", "local\n", "local-only")
        repo = RepoInfo(path=clone, name="clone")
        updates = analyze_repo(repo)
        assert len(updates) == 1
        assert updates[0].can_ff is False

    def test_dirty_repo_reported(self, git_workspace: dict[str, Path]) -> None:
        clone = git_workspace["clone"]
        (clone / "dirty.txt").write_text("uncommitted\n")
        _git(clone, "add", "dirty.txt")
        repo = RepoInfo(path=clone, name="clone")
        dirty = check_dirty([repo])
        assert dirty == [repo]


class TestPullUpdatesReal:
    def test_fast_forward_pull_advances_head(
        self,
        git_workspace: dict[str, Path],
    ) -> None:
        repo = RepoInfo(path=git_workspace["clone"], name="clone")
        updates = analyze_repo(repo)
        before = _git(repo.path, "rev-parse", "HEAD").stdout.strip()
        results = pull_updates(updates)
        after = _git(repo.path, "rev-parse", "HEAD").stdout.strip()
        assert len(results) == 1
        assert results[0].success is True
        assert before != after
        assert (repo.path / "new.txt").exists()


class TestRunFromDefaultsReal:
    def test_ci_mode_happy_path(
        self,
        git_workspace: dict[str, Path],
        tmp_path: Path,
    ) -> None:
        clone = git_workspace["clone"]
        repo = RepoInfo(path=clone, name="AMI-AGENTS")
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text(
            "remote: origin\n"
            "tiers: [apps]\n"
            "fail_on_diverge: true\n"
            "fail_on_dirty: true\n",
        )
        rc = run_from_defaults(defaults, [], [repo], tmp_path)
        assert rc == 0

    def test_ci_mode_fails_on_diverge(
        self,
        git_workspace: dict[str, Path],
        tmp_path: Path,
    ) -> None:
        clone = git_workspace["clone"]
        _commit(clone, "local.txt", "local\n", "local-only")
        repo = RepoInfo(path=clone, name="AMI-AGENTS")
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text(
            "remote: origin\n"
            "tiers: [apps]\n"
            "fail_on_diverge: true\n"
            "fail_on_dirty: true\n",
        )
        rc = run_from_defaults(defaults, [], [repo], tmp_path)
        assert rc == 1


class TestCliCiFlag:
    def test_ci_flag_without_defaults_uses_default_yaml(
        self,
        tmp_path: Path,
        project_root: Path,
    ) -> None:
        fake_root = tmp_path / "fake-root"
        (fake_root / "ami" / "config").mkdir(parents=True)
        (fake_root / "pyproject.toml").touch()
        (fake_root / "projects").mkdir()
        (fake_root / "ami" / "config" / "update-defaults.yaml").write_text(
            "remote: origin\ntiers: []\nfail_on_diverge: true\nfail_on_dirty: true\n",
        )

        env = os.environ.copy()
        env["AMI_ROOT"] = str(fake_root)
        env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-m", "ami.scripts.update", "--ci"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(project_root),
            timeout=30,
        )
        # Empty tiers => nothing to pull => exit 0.
        assert result.returncode == 0, (
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
