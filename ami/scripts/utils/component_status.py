#!/usr/bin/env python3
"""
Component status detection for AMI shell banner.

Outputs component availability for shell script consumption.
"""

import re
import subprocess
from pathlib import Path


# Find project root by looking for pyproject.toml or .git
def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    msg = "Could not find project root"
    raise RuntimeError(msg)


PROJECT_ROOT = _find_project_root()


def check_binary(path: str) -> tuple[bool, str | None]:
    """Check if binary exists and get version."""
    full_path = PROJECT_ROOT / path
    if not full_path.exists():
        return False, None

    # Try common version flags
    for flag in ["--version", "-V", "version"]:
        try:
            result = subprocess.run(
                [str(full_path), flag],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                output = result.stdout.strip() or result.stderr.strip()
                # Extract version number
                match = re.search(r"(\d+\.\d+\.\d+)", output)
                if match:
                    return True, match.group(1)
                return True, None
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass
    return True, None


def check_command(cmd: list[str]) -> tuple[bool, str | None]:
    """Check if command works and get version."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if result.returncode == 0:
            output = result.stdout.strip() or result.stderr.strip()
            match = re.search(r"(\d+\.\d+\.\d+)", output)
            return True, match.group(1) if match else None
    except (subprocess.SubprocessError, FileNotFoundError, OSError, TimeoutError):
        pass
    return False, None


# Type for component tuple: (name, check_type, check_arg, description)
ComponentTuple = tuple[str, str, str | None, str]

# Component definitions: (name, check_type, check_arg, description)
COMPONENTS: dict[str, list[ComponentTuple]] = {
    # Core (always available)
    "core": [
        ("ami", "always", None, "Unified CLI for services and system management"),
        ("ami-run", "always", None, "Universal project execution wrapper"),
        (
            "ami-repo",
            "binary",
            "ami/scripts/bin/ami-repo",
            "Git repository and server management",
        ),
    ],
    # Enterprise services
    "enterprise": [
        (
            "ami-mail",
            "binary",
            "ami/scripts/bin/ami_mail.py",
            "Enterprise mail operations CLI",
        ),
        (
            "ami-chat",
            "binary",
            ".boot-linux/bin/matrix-commander",
            "Matrix CLI chat and automation",
        ),
        ("ami-admin", "binary", ".boot-linux/bin/synadm", "Matrix Server Admin CLI"),
        (
            "ami-browser",
            "binary",
            ".venv/bin/playwright",
            "Browser automation (Playwright)",
        ),
    ],
    # Dev tools
    "dev": [
        (
            "ami-backup",
            "binary",
            "ami/scripts/backup/create/cli.py",
            "Backup to Google Drive",
        ),
        (
            "ami-restore",
            "binary",
            "ami/scripts/backup/restore/cli.py",
            "Restore from Google Drive",
        ),
    ],
    # AI Agents
    "agents": [
        (
            "ami-claude",
            "binary",
            ".venv/node_modules/.bin/claude",
            "Claude Code AI assistant",
        ),
        (
            "ami-gemini",
            "binary",
            ".venv/node_modules/.bin/gemini",
            "Gemini CLI AI assistant",
        ),
        (
            "ami-qwen",
            "binary",
            ".venv/node_modules/.bin/qwen",
            "Qwen Code AI assistant",
        ),
    ],
}


def get_component_status() -> dict[str, list[tuple[str, bool, str | None, str]]]:
    """Get status of all components."""
    status: dict[str, list[tuple[str, bool, str | None, str]]] = {}

    for category, components in COMPONENTS.items():
        status[category] = []
        for name, check_type, check_arg, description in components:
            if check_type == "always":
                status[category].append((name, True, None, description))
            elif check_type == "binary" and check_arg is not None:
                installed, version = check_binary(check_arg)
                status[category].append((name, installed, version, description))
            elif check_type == "command" and check_arg is not None:
                installed, version = check_command(check_arg.split())
                status[category].append((name, installed, version, description))

    return status


def print_shell_format() -> None:
    """Print component status in shell-parseable format."""
    status = get_component_status()

    for category, components in status.items():
        for name, installed, version, description in components:
            v = version or ""
            print(f"{category}|{name}|{1 if installed else 0}|{v}|{description}")


if __name__ == "__main__":
    print_shell_format()
