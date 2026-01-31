"""Integration tests for the git safety patcher script.

Tests that the patcher installs a git wrapper that blocks destructive commands.
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
PATCHER_SCRIPT = PROJECT_ROOT / "ami/scripts/utils/disable_no_verify_patcher.sh"


class MockEnv(NamedTuple):
    """Test environment with paths and env vars."""

    env: dict
    boot_linux_dir: Path
    git_wrapper: Path


@pytest.fixture
def mock_env(tmp_path: Path) -> MockEnv:
    """Sets up a temporary environment for testing the patcher."""
    boot_linux_dir = tmp_path / ".boot-linux"
    boot_linux_dir.mkdir()
    bin_dir = boot_linux_dir / "bin"
    bin_dir.mkdir()

    # Set up env to use temp boot-linux dir
    env = os.environ.copy()
    env["BOOT_LINUX_DIR"] = str(boot_linux_dir)
    # Prepend our bin dir to PATH so wrapper is found first
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"

    return MockEnv(
        env=env,
        boot_linux_dir=boot_linux_dir,
        git_wrapper=bin_dir / "git",
    )


def run_git_cmd(cmd: str, env: dict) -> subprocess.CompletedProcess[str]:
    """Runs a git command via the wrapper."""
    return subprocess.run(
        ["bash", "-c", cmd], env=env, capture_output=True, text=True, check=False
    )


def test_patcher_installation(mock_env: MockEnv) -> None:
    """Verify the patcher installs the wrapper correctly."""
    # Run patcher
    subprocess.run(["bash", str(PATCHER_SCRIPT)], env=mock_env.env, check=True)

    # Check wrapper was created
    assert mock_env.git_wrapper.exists(), "Git wrapper not created"
    assert os.access(mock_env.git_wrapper, os.X_OK), "Git wrapper not executable"

    # Check wrapper content
    content = mock_env.git_wrapper.read_text()
    assert "BLOCKED" in content
    assert "reset)" in content
    assert "checkout)" in content
    assert "clean)" in content


def test_blocked_commands(mock_env: MockEnv) -> None:
    """Verify destructive commands are blocked."""
    subprocess.run(
        ["bash", str(PATCHER_SCRIPT)], env=mock_env.env, check=True
    )  # Install first

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
        assert res.returncode == 1, f"Command '{cmd}' should have failed"
        assert "BLOCKED" in res.stdout, f"Command '{cmd}' output: {res.stdout}"


def test_blocked_flags(mock_env: MockEnv) -> None:
    """Verify destructive flags are blocked."""
    subprocess.run(["bash", str(PATCHER_SCRIPT)], env=mock_env.env, check=True)

    blocked_flag_cmds = [
        "git commit -m 'msg' --no-verify",
        "git push origin main --force",
        "git push origin main -f",
        "git anycommand --hard",
    ]

    for cmd in blocked_flag_cmds:
        res = run_git_cmd(cmd, mock_env.env)
        assert res.returncode == 1, f"Command '{cmd}' should have failed"
        assert "BLOCKED" in res.stdout


def test_blocked_subcommands(mock_env: MockEnv) -> None:
    """Verify blocked sub-commands/args."""
    subprocess.run(["bash", str(PATCHER_SCRIPT)], env=mock_env.env, check=True)

    cmds = ["git stash drop", "git stash clear", "git branch -D feature"]

    for cmd in cmds:
        res = run_git_cmd(cmd, mock_env.env)
        assert res.returncode == 1
        assert "BLOCKED" in res.stdout


def test_allowed_commands(mock_env: MockEnv) -> None:
    """Verify safe commands are allowed."""
    subprocess.run(["bash", str(PATCHER_SCRIPT)], env=mock_env.env, check=True)

    # These should NOT be blocked (they pass through to real git)
    res = run_git_cmd("git status", mock_env.env)
    assert "BLOCKED" not in res.stdout

    res = run_git_cmd("git log --oneline -1", mock_env.env)
    assert "BLOCKED" not in res.stdout
