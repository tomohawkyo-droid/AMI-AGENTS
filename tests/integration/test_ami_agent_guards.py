"""Integration tests for AMI Agent Security Guards (v4.0.0 tier system).

Tests the tiered command permission system:
1. Admin-tier commands are blocked.
2. Observe-tier commands are allowed.
3. Hard deny patterns block regardless of tier.
"""

from pathlib import Path
from unittest.mock import patch

from ami.core.bootloader_agent import BootloaderAgent
from ami.hooks.manager import HookManager


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


_ROOT = _find_project_root()


def _agent():
    return BootloaderAgent()


def _hook_manager():
    return HookManager.from_config(_ROOT / "ami/config/hooks.yaml")


def test_admin_tier_blocks_rm():
    """Admin-tier commands like rm are blocked."""
    agent = _agent()
    hook_manager = _hook_manager()
    result = agent.execute_shell("rm -rf /", hook_manager=hook_manager)
    assert "BLOCKED" in result
    assert "SECURITY VIOLATION" in result


def test_observe_tier_allows_ls():
    """Observe-tier commands like ls are auto-allowed."""
    agent = _agent()
    hook_manager = _hook_manager()
    result = agent.execute_shell("ls -la", hook_manager=hook_manager)
    assert "BLOCKED" not in result


def test_modify_tier_needs_confirmation():
    """Modify-tier commands need confirmation. Without input_func, they are blocked."""
    agent = _agent()
    hook_manager = _hook_manager()
    result = agent.execute_shell(
        "echo hello > test.txt",
        hook_manager=hook_manager,
    )
    assert "BLOCKED" in result
    assert "confirmation" in result.lower()


def test_modify_tier_with_confirmation():
    """Modify-tier commands pass when user confirms."""
    agent = _agent()
    hook_manager = _hook_manager()

    with patch("ami.utils.process.ProcessExecutor.run") as mock_run:
        mock_run.return_value = {"stdout": "", "stderr": "", "returncode": 0}

        result = agent.execute_shell(
            "echo hello > test.txt",
            input_func=lambda cmd: True,
            hook_manager=hook_manager,
        )

    assert "BLOCKED" not in result
