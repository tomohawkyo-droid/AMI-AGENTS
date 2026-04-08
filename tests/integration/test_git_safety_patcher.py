"""Integration tests for the git-guard safety wrapper.

Tests that the git-guard script blocks destructive commands and passes
safe commands through to real-git.
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
    assert "real-git" in content


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
    """Verify safe commands pass through to real-git."""
    safe_cmds = [
        "git status",
        "git log --oneline -1",
        "git diff",
        "git add .",
        "git commit -m 'msg'",
        "git push origin main",
        "git pull",
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
    assert "BLOCKED" not in res.stdout
    assert "PASSTHROUGH" in res.stdout


def test_guard_fails_without_git_real(mock_env: MockEnv) -> None:
    """Verify guard errors if real-git is missing."""
    (mock_env.bin_dir / "real-git").unlink()
    res = run_git_cmd("git status", mock_env.env)
    assert res.returncode == 1
    assert "real-git not found" in res.stdout
