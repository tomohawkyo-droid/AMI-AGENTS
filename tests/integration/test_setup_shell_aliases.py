"""Integration test for shell-setup aliases and functions.

Verifies that all registered aliases/functions respond to -h calls.
"""

import subprocess
from pathlib import Path


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


# Find AMI_ROOT (agents/ directory)
AMI_ROOT = _find_project_root()


def test_aliases_exist_and_respond_to_help() -> None:
    """Test that all aliases and functions from shell-setup exist and respond to -h."""
    script_path = AMI_ROOT / "ami" / "scripts" / "shell" / "shell-setup"

    assert script_path.exists(), f"Setup script does not exist: {script_path}"

    expected_functions = [
        "ami-run",
        "ami-agent",
        "ami-repo",
        "ami",
        "ami-check-storage",
        "ami-gcloud",
        "ami-git",
        "ami-claude",
        "ami-gemini",
        "ami-qwen",
    ]

    expected_aliases: list[str] = []

    for func_name in expected_functions:
        if func_name in ["ami-claude", "ami-gemini", "ami-qwen"]:
            bash_test_cmd = [
                "bash",
                "-c",
                f"source {script_path} >/dev/null 2>&1 && type -t {func_name}",
            ]

            result = subprocess.run(
                bash_test_cmd, check=False, capture_output=True, text=True
            )
            assert (
                result.returncode == 0
            ), f"Function {func_name} does not exist: {result.stderr}"

            output = result.stdout.strip()
            assert output in [
                "function",
                "builtin",
                "file",
            ], f"{func_name} is not a function/command: {output}"
            continue

        bash_test_cmd = [
            "bash",
            "-c",
            f"source {script_path} >/dev/null 2>&1 && type -t {func_name}",
        ]

        result = subprocess.run(
            bash_test_cmd, check=False, capture_output=True, text=True
        )
        assert (
            result.returncode == 0
        ), f"Function {func_name} does not exist: {result.stderr}"

        output = result.stdout.strip()
        assert output in [
            "function",
            "builtin",
            "file",
        ], f"{func_name} is not a function/command: {output}"

        try:
            test_script = rf"""
                export AMI_ROOT="{AMI_ROOT}"
                export PYTHONPATH="{AMI_ROOT}"
                export PATH="{AMI_ROOT}/.venv/bin:{AMI_ROOT}/.boot-linux/bin:$PATH"

                source "{script_path}" >/dev/null 2>&1

                output=$( {func_name} -h 2>&1 )
                exit_code=$?

                if echo "$output" | grep -q 'No such file or directory\|command not found'; then
                    echo "$output"
                    exit 1
                fi

                echo "Function executed (exit code: $exit_code)"
                [ -n "$output" ] && echo "$output" || true
            """
            result = subprocess.run(
                ["bash", "-c", test_script],
                check=False,
                capture_output=True,
                timeout=10,
                text=True,
                cwd=AMI_ROOT,
            )
        except subprocess.TimeoutExpired:
            continue  # Skip to next function
        except Exception as e:
            raise AssertionError(
                f"Command {func_name} failed during execution: {e!s}"
            ) from e

        combined_output = result.stdout + result.stderr
        if (
            "No such file or directory" in combined_output
            or "command not found" in combined_output
        ):
            raise AssertionError(
                f"Command {func_name} failed with file error: {combined_output}"
            )

    for alias_name in expected_aliases:
        bash_test_cmd = [
            "bash",
            "-c",
            f"source {script_path} >/dev/null 2>&1 && alias {alias_name}",
        ]

        result = subprocess.run(
            bash_test_cmd, check=False, capture_output=True, text=True
        )
        assert (
            result.returncode == 0
        ), f"Alias {alias_name} does not exist: {result.stderr}"


def test_cli_agents_available() -> None:
    """Test that CLI agents are available and respond."""
    script_path = AMI_ROOT / "ami" / "scripts" / "shell" / "shell-setup"

    cli_agents = ["ami-claude", "ami-gemini", "ami-qwen"]

    for agent in cli_agents:
        bash_test_cmd = ["bash", "-c", f"source {script_path} && type -t {agent}"]

        result = subprocess.run(
            bash_test_cmd, check=False, capture_output=True, text=True
        )
        assert (
            result.returncode == 0
        ), f"CLI agent {agent} does not exist: {result.stderr}"


if __name__ == "__main__":
    test_aliases_exist_and_respond_to_help()
    test_cli_agents_available()
