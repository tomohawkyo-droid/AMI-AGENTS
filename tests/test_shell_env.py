"""Shell-environment integration tests.

Sources `shell-setup` from the actual project root (resolved relative to this
test file) and verifies that registered extensions and `ami` subcommands
behave correctly. No `agents/` parent-monorepo prefix; no swallowed exit
codes.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _find_project_root() -> Path:
    """Walk up from this file until we find pyproject.toml or .git."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


REPO_ROOT = _find_project_root()
SHELL_SETUP_SCRIPT = REPO_ROOT / "ami" / "scripts" / "shell" / "shell-setup"
BOOT_LINUX_BIN = REPO_ROOT / ".boot-linux" / "bin"


def get_clean_env() -> dict[str, str]:
    """Strip BOOT_LINUX_BIN from PATH so shell-setup has to put it back."""
    env = os.environ.copy()
    paths = env.get("PATH", "").split(os.pathsep)
    clean = [p for p in paths if Path(p).resolve() != BOOT_LINUX_BIN.resolve()]
    env["PATH"] = os.pathsep.join(clean)
    env["AMI_QUIET_MODE"] = "1"
    return env


def run_in_shell_env(command: str) -> subprocess.CompletedProcess[str]:
    """Source shell-setup, then run `command` in bash. Returns CompletedProcess."""
    full = f"source {SHELL_SETUP_SCRIPT} && {command}"
    return subprocess.run(
        full,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=get_clean_env(),
        check=False,
    )


class TestShellAliases:
    def test_source_script_configures_path(self) -> None:
        """Sourcing shell-setup must add .boot-linux/bin to PATH."""
        result = run_in_shell_env("type node")
        assert result.returncode == 0, (
            f"node not found after sourcing shell-setup. stderr={result.stderr!r}"
        )

    def test_ami_run_python(self) -> None:
        """`ami-run python --version` reports a Python version."""
        result = run_in_shell_env("ami-run python --version")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "Python" in result.stdout or "Python" in result.stderr

    def test_ami_run_node(self) -> None:
        """`ami-run node --version` reports a Node version."""
        result = run_in_shell_env("ami-run node --version")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "v" in result.stdout

    # --- AI Agents (Critical Wrappers) ---

    def test_ami_gemini_executable(self) -> None:
        """`ami-gemini --help` exits 0 with usable help text."""
        result = run_in_shell_env("ami-gemini --help")
        if "env: node: No such file or directory" in result.stderr:
            pytest.fail("ami-gemini failed: node interpreter not found in PATH")
        assert result.returncode == 0, (
            f"ami-gemini --help failed: rc={result.returncode}, "
            f"stderr={result.stderr!r}"
        )
        assert "Usage" in result.stdout or "Commands" in result.stdout, (
            f"ami-gemini --help produced no help text: stdout={result.stdout!r}"
        )

    def test_ami_claude_executable(self) -> None:
        """`ami-claude --help` exits 0 with usable help text."""
        result = run_in_shell_env("ami-claude --help")
        if "env: node: No such file or directory" in result.stderr:
            pytest.fail("ami-claude failed: node interpreter not found in PATH")
        assert result.returncode == 0, (
            f"ami-claude --help failed: rc={result.returncode}, "
            f"stderr={result.stderr!r}"
        )
        assert "Usage" in result.stdout or "Commands" in result.stdout, (
            f"ami-claude --help produced no help text: stdout={result.stdout!r}"
        )

    def test_ami_qwen_executable(self) -> None:
        """`ami-qwen --help` exits 0 with usable help text."""
        result = run_in_shell_env("ami-qwen --help")
        if "env: node: No such file or directory" in result.stderr:
            pytest.fail("ami-qwen failed: node interpreter not found in PATH")
        assert result.returncode == 0, (
            f"ami-qwen --help failed: rc={result.returncode}, stderr={result.stderr!r}"
        )
        assert "Usage" in result.stdout or "Commands" in result.stdout, (
            f"ami-qwen --help produced no help text: stdout={result.stdout!r}"
        )

    # --- Orchestration & Python Script Imports ---

    def test_ami_status_execution(self) -> None:
        """`ami status` executes without ModuleNotFoundError."""
        result = run_in_shell_env("ami status")
        if "ModuleNotFoundError" in result.stderr:
            pytest.fail(f"ami status failed with import error: {result.stderr}")
        assert result.returncode == 0, f"stderr={result.stderr!r}"

    def test_ami_extras_execution(self) -> None:
        """`ami extras` lists hidden extensions or prints empty-state message."""
        result = run_in_shell_env("ami extras")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert (
            "Hidden Extensions" in result.stdout
            or "No hidden extensions" in result.stdout
        ), f"unexpected extras output: {result.stdout!r}"

    def test_ami_doctor_execution(self) -> None:
        """`ami doctor` reports problems or prints all-clean message."""
        result = run_in_shell_env("ami doctor")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        expected = [
            "No problems detected",
            "Degraded",
            "Unavailable",
            "Version-Mismatched",
        ]
        assert any(s in result.stdout for s in expected), (
            f"unexpected doctor output: {result.stdout!r}"
        )

    def test_ami_storage_execution(self) -> None:
        """`ami storage --no-breakdown --no-containers` reports root disk usage."""
        result = run_in_shell_env("ami storage --no-breakdown --no-containers")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        # Root-disk line always renders (label "Root Disk" + size string).
        assert "Root Disk" in result.stdout, (
            f"unexpected storage output: {result.stdout!r}"
        )

    # --- Git / Repo Tools ---

    def test_ami_repo_execution(self) -> None:
        """`ami-repo --help` runs without import errors."""
        result = run_in_shell_env("ami-repo --help")
        if "ModuleNotFoundError" in result.stderr:
            pytest.fail(f"ami-repo failed with import error: {result.stderr}")
        assert result.returncode == 0, f"stderr={result.stderr!r}"
