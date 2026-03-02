import os
import subprocess

import pytest

# Path to the shell setup script
SHELL_SETUP_SCRIPT = "agents/ami/scripts/shell/shell-setup"
PROJECT_ROOT = os.getcwd()


def get_clean_env():
    """
    Returns a copy of os.environ with AMI-specific paths removed from PATH.
    This ensures we rely solely on shell-setup to configure the environment.
    """
    env = os.environ.copy()
    current_path = env.get("PATH", "")

    # Identify the boot-linux bin path to remove
    boot_linux_bin = os.path.join(PROJECT_ROOT, "agents", ".boot-linux", "bin")

    # Split PATH, filter out the boot-linux path, and rejoin
    paths = current_path.split(os.pathsep)
    clean_paths = [
        p for p in paths if os.path.abspath(p) != os.path.abspath(boot_linux_bin)
    ]

    env["PATH"] = os.pathsep.join(clean_paths)
    env["AMI_QUIET_MODE"] = "1"  # Suppress banner

    return env


def run_in_shell_env(command):
    """
    Runs a command in a bash shell after sourcing the setup script.
    Uses a clean environment to ensure shell-setup does the work.
    Returns the CompletedProcess object.
    """
    full_command = f"source {SHELL_SETUP_SCRIPT} && {command}"

    result = subprocess.run(
        full_command,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=get_clean_env(),
        check=False,
    )
    return result


class TestShellAliases:
    def test_source_script_configures_path(self):
        """
        Critical Test: Verify that sourcing the script ADDS .boot-linux/bin to PATH.
        This catches the regression where functions were defined but not called.
        """
        # We check if 'node' (which is in .boot-linux/bin) becomes available
        # 'type node' will fail in clean env, should pass after source
        result = run_in_shell_env("type node")
        assert result.returncode == 0, (
            "node not found after sourcing shell-setup. PATH configuration failed."
        )

    def test_ami_run_python(self):
        """Test 'ami-run python' alias."""
        result = run_in_shell_env("ami-run python --version")
        assert result.returncode == 0
        assert "Python" in result.stdout or "Python" in result.stderr

    def test_ami_run_node(self):
        """Test 'ami-run node' alias."""
        result = run_in_shell_env("ami-run node --version")
        assert result.returncode == 0
        assert "v" in result.stdout

    # --- AI Agents (Critical Wrappers) ---

    def test_ami_gemini_executable(self):
        """
        Test 'ami-gemini'.
        If this passes, it implies 'node' is in PATH because
        the agent scripts use '#!/usr/bin/env node'.
        """
        result = run_in_shell_env("ami-gemini --help")
        # Exit code might be 0 or 1 depending on auth,
        # but it shouldn't be 127 (not found)
        # or a 'env: node: No such file or directory' error.

        if "env: node: No such file or directory" in result.stderr:
            pytest.fail("ami-gemini failed: node interpreter not found in PATH")

        # We accept 0 (success) or 1 (likely auth/config error),
        # but NOT 127 (command not found) or 126 (permission denied)
        assert result.returncode in [0, 1]

    def test_ami_claude_executable(self):
        result = run_in_shell_env("ami-claude --help")
        if "env: node: No such file or directory" in result.stderr:
            pytest.fail("ami-claude failed: node interpreter not found in PATH")
        assert result.returncode in [0, 1]

    def test_ami_qwen_executable(self):
        result = run_in_shell_env("ami-qwen --help")
        if "env: node: No such file or directory" in result.stderr:
            pytest.fail("ami-qwen failed: node interpreter not found in PATH")
        assert result.returncode in [0, 1]

    # --- Orchestration & Python Script Imports ---

    def test_ami_status_execution(self):
        """
        Test 'ami status'.
        This triggers `launcher/scripts/launch_services.py`.
        Catches 'ModuleNotFoundError: No module named base'.
        """
        # We run with --help (passed to python script) to avoid
        # actually checking docker/services
        # but still trigger imports.
        # Note: 'ami status --help' passes '--help' to the status subcommand.
        # Wait, the ami wrapper logic:
        # status) ami-run python "$launcher_script" status "$@"
        # so 'ami status --help' -> python script status --help
        result = run_in_shell_env("ami status --help")

        if "ModuleNotFoundError" in result.stderr:
            pytest.fail(f"ami status failed with import error: {result.stderr}")

        assert result.returncode == 0

    def test_ami_monitor_execution(self):
        """
        Test 'ami monitor'.
        Triggers `launcher/scripts/monitoring_server.py`.
        """
        result = run_in_shell_env("ami monitor --help")
        if "ModuleNotFoundError" in result.stderr:
            pytest.fail(f"ami monitor failed with import error: {result.stderr}")
        assert result.returncode == 0

    # --- Git / Repo Tools ---

    def test_ami_repo_execution(self):
        """Test 'ami-repo' execution (triggers scripts/ami_repo.py)."""
        result = run_in_shell_env("ami-repo --help")
        if "ModuleNotFoundError" in result.stderr:
            pytest.fail(f"ami-repo failed with import error: {result.stderr}")
        assert result.returncode == 0

    def test_ami_check_storage(self):
        """Test 'ami-check-storage' (triggers base/scripts/check_storage.py)."""
        result = run_in_shell_env("ami-check-storage --help")
        if "ModuleNotFoundError" in result.stderr:
            pytest.fail(f"ami-check-storage failed with import error: {result.stderr}")
        assert result.returncode == 0
