"""Integration tests for the git-guard safety wrapper.

Tests that the git-guard script blocks destructive commands and passes
safe commands through to real git.
"""

import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


PROJECT_ROOT = _find_project_root()
GIT_GUARD = PROJECT_ROOT / "ami/scripts/utils/git-guard"


class MockEnv(NamedTuple):
    """Test environment with paths and env vars."""

    env: dict
    bin_dir: Path
    git_guard: Path


@pytest.fixture
def mock_env(tmp_path: Path) -> MockEnv:
    """Sets up a temp bin dir with git-guard and a mock real-git."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # Copy git-guard into temp bin dir
    guard_dest = bin_dir / "git"
    guard_dest.write_text(GIT_GUARD.read_text())
    guard_dest.chmod(0o755)

    # Create a mock real-git that just prints args
    git_real = bin_dir / "real-git"
    git_real.write_text('#!/usr/bin/env bash\necho "PASSTHROUGH: $*"\n')
    git_real.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    # Point guard to our mock real-git via env var
    env["GIT_GUARD_REAL_GIT"] = str(git_real)

    return MockEnv(env=env, bin_dir=bin_dir, git_guard=guard_dest)


def run_git_cmd(cmd: str, env: dict) -> subprocess.CompletedProcess[str]:
    """Runs a git command via the wrapper."""
    return subprocess.run(
        ["bash", "-c", cmd], env=env, capture_output=True, text=True, check=False
    )


def test_guard_exists() -> None:
    """Verify the git-guard script exists and is executable."""
    assert GIT_GUARD.exists(), "git-guard not found"
    assert os.access(GIT_GUARD, os.X_OK), "git-guard not executable"
    content = GIT_GUARD.read_text()
    assert "BLOCKED" in content
    assert "GIT_REAL" in content


def test_guard_blocks_destructive_commands(mock_env: MockEnv) -> None:
    """Verify destructive commands are blocked."""
    destructive_cmds = [
        "git reset --hard HEAD",
        "git checkout main",
        "git clean -fd",
        "git restore .",
        "git rm file.txt",
        "git rebase main",
        "git gc",
        "git prune",
    ]

    for cmd in destructive_cmds:
        res = run_git_cmd(cmd, mock_env.env)
        assert res.returncode == 1, f"'{cmd}' should have been blocked"
        combined = res.stdout + res.stderr
        assert "BLOCKED" in combined, f"'{cmd}' output: {combined}"


def test_guard_blocks_destructive_flags(mock_env: MockEnv) -> None:
    """Verify destructive flags are blocked."""
    blocked_flag_cmds = [
        "git commit -m 'msg' --no-verify",
        "git push origin main --force",
        "git push origin main -f",
        "git anycommand --hard",
    ]

    for cmd in blocked_flag_cmds:
        res = run_git_cmd(cmd, mock_env.env)
        assert res.returncode == 1, f"'{cmd}' should have been blocked"
        combined = res.stdout + res.stderr
        assert "BLOCKED" in combined, f"'{cmd}' output: {combined}"


def test_guard_blocks_destructive_subcommands(mock_env: MockEnv) -> None:
    """Verify blocked sub-commands/args."""
    cmds = ["git stash drop", "git stash clear", "git branch -D feature"]

    for cmd in cmds:
        res = run_git_cmd(cmd, mock_env.env)
        assert res.returncode == 1
        combined = res.stdout + res.stderr
        assert "BLOCKED" in combined, f"'{cmd}' output: {combined}"


def test_guard_allows_safe_commands(mock_env: MockEnv) -> None:
    """Verify safe commands pass through to real-git.

    Runs in `mock_env.bin_dir` — no `.git` dir present — so the P0/P1/P2
    history-safety checks skip (their `_is_on_remote` / `_current_branch`
    helpers return non-zero when there is no repo to query).
    """
    safe_cmds = [
        "git status",
        "git log --oneline -1",
        "git diff",
        "git add .",
        "git commit -m 'msg'",
        "git push origin main",
        "git pull --ff-only",
        "git pull --rebase",
        "git fetch",
        "git branch -d feature",
        "git stash",
        "git stash list",
        "git stash pop",
    ]

    for cmd in safe_cmds:
        res = run_git_cmd(cmd, mock_env.env)
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, f"'{cmd}' should be allowed"
        assert "PASSTHROUGH" in res.stdout, f"'{cmd}' didn't reach real-git"


def test_guard_no_args_passes_through(mock_env: MockEnv) -> None:
    """Verify bare 'git' with no args passes through."""
    res = run_git_cmd("git", mock_env.env)
    combined = res.stdout + res.stderr
    assert "BLOCKED" not in combined


@pytest.mark.skipif(
    os.path.isfile("/usr/bin/git"),
    reason="Guard auto-discovers /usr/bin/git — cannot test missing-git path",
)
def test_guard_fails_without_git_real(mock_env: MockEnv) -> None:
    """Verify guard errors if real-git is missing."""
    (mock_env.bin_dir / "real-git").unlink()
    mock_env.env["GIT_GUARD_REAL_GIT"] = "/nonexistent/git"
    res = run_git_cmd("git status", mock_env.env)
    assert res.returncode == 1
    combined = res.stdout + res.stderr
    assert "not found" in combined.lower()


# ---------------------------------------------------------------------------
# P0/P1/P2/P3 history-safety fixtures + tests
# ---------------------------------------------------------------------------


def _resolve_system_git() -> Path:
    """Pick the real git binary to use as the wrapper's underlying executable."""
    for candidate in (
        "/usr/bin/git.original",
        "/usr/local/bin/git.original",
        "/usr/bin/git",
        "/usr/local/bin/git",
        "/snap/bin/git",
    ):
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return Path(candidate)
    msg = "no system git binary found for history-safety tests"
    raise RuntimeError(msg)


class HistoryEnv(NamedTuple):
    """Working repo + env wired to run git-guard against real system git."""

    env: dict
    work_dir: Path
    origin_dir: Path
    pushed_sha: str


@pytest.fixture
def history_env(tmp_path: Path) -> HistoryEnv:
    """Set up bare `origin` + working repo with one pushed commit on main."""
    real_git = _resolve_system_git()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    guard_dest = bin_dir / "git"
    guard_dest.write_text(GIT_GUARD.read_text())
    guard_dest.chmod(0o755)

    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"

    base_env = {
        **os.environ,
        "GIT_GUARD_REAL_GIT": str(real_git),
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
    }

    def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(real_git), *args],
            cwd=cwd,
            env=base_env,
            capture_output=True,
            text=True,
            check=True,
        )

    subprocess.run(
        [str(real_git), "init", "--bare", "-b", "main", str(origin_dir)],
        env=base_env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(real_git), "clone", str(origin_dir), str(work_dir)],
        env=base_env,
        check=True,
        capture_output=True,
    )
    (work_dir / "README.md").write_text("seed\n")
    run(["add", "README.md"], work_dir)
    run(["-c", "commit.gpgsign=false", "commit", "-m", "seed"], work_dir)
    run(["push", "-u", "origin", "main"], work_dir)
    pushed_sha = run(["rev-parse", "HEAD"], work_dir).stdout.strip()

    # Ensure the wrapper (guard_dest) is what gets picked by PATH.
    env = {**base_env, "PWD": str(work_dir)}
    return HistoryEnv(
        env=env, work_dir=work_dir, origin_dir=origin_dir, pushed_sha=pushed_sha
    )


def _run_in(env: HistoryEnv, cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", cmd],
        cwd=env.work_dir,
        env=env.env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestCommitAmendOnPushedHead:
    def test_amend_on_pushed_head_blocked(self, history_env: HistoryEnv) -> None:
        res = _run_in(history_env, "git commit --amend --no-edit --allow-empty")
        combined = res.stdout + res.stderr
        assert res.returncode == 1, f"amend should block; got: {combined}"
        assert "BLOCKED" in combined
        assert "already on origin" in combined

    def test_amend_on_local_only_commit_allowed(self, history_env: HistoryEnv) -> None:
        (history_env.work_dir / "note.txt").write_text("local-only\n")
        _run_in(history_env, "git add note.txt && git commit -m 'local'")
        res = _run_in(history_env, "git commit --amend --no-edit")
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, combined
        assert res.returncode == 0


class TestRevertSafety:
    def test_revert_unpushed_commit_blocked(self, history_env: HistoryEnv) -> None:
        (history_env.work_dir / "local.txt").write_text("x\n")
        _run_in(history_env, "git add local.txt && git commit -m 'local only'")
        res = _run_in(history_env, "git revert --no-edit HEAD")
        combined = res.stdout + res.stderr
        assert res.returncode == 1, f"revert should block; got: {combined}"
        assert "BLOCKED" in combined
        assert "not on origin" in combined

    def test_revert_pushed_commit_allowed(self, history_env: HistoryEnv) -> None:
        res = _run_in(history_env, f"git revert --no-edit {history_env.pushed_sha}")
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, combined
        assert res.returncode == 0


class TestPullOnProtectedBranch:
    def test_pull_without_flag_blocked_on_main(self, history_env: HistoryEnv) -> None:
        res = _run_in(history_env, "git pull")
        combined = res.stdout + res.stderr
        assert res.returncode == 1, combined
        assert "BLOCKED" in combined
        assert "--ff-only or --rebase" in combined

    def test_pull_ff_only_allowed(self, history_env: HistoryEnv) -> None:
        res = _run_in(history_env, "git pull --ff-only")
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, combined

    def test_pull_rebase_allowed(self, history_env: HistoryEnv) -> None:
        res = _run_in(history_env, "git pull --rebase")
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, combined

    def test_pull_on_feature_branch_allowed_without_flag(
        self, history_env: HistoryEnv
    ) -> None:
        _run_in(history_env, "git switch -c feature")
        res = _run_in(history_env, "git pull")
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, combined


class TestMergeOnProtectedBranch:
    def test_merge_without_ff_only_blocked_on_main(
        self, history_env: HistoryEnv
    ) -> None:
        res = _run_in(history_env, "git merge origin/main")
        combined = res.stdout + res.stderr
        assert res.returncode == 1, combined
        assert "BLOCKED" in combined
        assert "--ff-only" in combined

    def test_merge_ff_only_allowed(self, history_env: HistoryEnv) -> None:
        res = _run_in(history_env, "git merge --ff-only origin/main")
        combined = res.stdout + res.stderr
        assert "BLOCKED" not in combined, combined
