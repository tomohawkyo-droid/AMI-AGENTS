#!/usr/bin/env python3
"""
Component status detection for AMI shell banner.

Outputs component availability for shell script consumption.
"""

import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from ami.core.env import PROJECT_ROOT
from ami.types.results import BinaryCheckResult, ComponentStatusEntry


class ComponentDef(NamedTuple):
    """Definition for a component to check."""

    name: str
    check_type: str
    check_arg: str | None
    description: str


def _try_version_flag(full_path: Path, flag: str) -> BinaryCheckResult | None:
    """Try a single version flag on a binary. Returns result if successful."""
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
            match = re.search(r"(\d+\.\d+\.\d+)", output)
            if match:
                return BinaryCheckResult(True, match.group(1))
            return BinaryCheckResult(True, None)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return None


def check_binary(path: str) -> BinaryCheckResult:
    """Check if binary exists and get version."""
    full_path = PROJECT_ROOT / path
    if not full_path.exists():
        return BinaryCheckResult(False, None)

    for flag in ["--version", "-V", "version"]:
        result = _try_version_flag(full_path, flag)
        if result is not None:
            return result
    return BinaryCheckResult(True, None)


def check_container(container_name: str) -> BinaryCheckResult:
    """Check if a Docker container is running and get its image version."""
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Running}}|{{.Config.Image}}",
                container_name,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            running = parts[0] == "true"
            image = parts[1] if len(parts) > 1 else ""
            version = None
            if ":" in image:
                tag = image.split(":")[-1]
                match = re.search(r"(\d[\d.]*)", tag)
                if match:
                    version = match.group(1)
            return BinaryCheckResult(running, version)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return BinaryCheckResult(False, None)


def check_command(cmd: list[str]) -> BinaryCheckResult:
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
            return BinaryCheckResult(True, match.group(1) if match else None)
    except (subprocess.SubprocessError, FileNotFoundError, OSError, TimeoutError):
        pass
    return BinaryCheckResult(False, None)


# Component definitions: category -> list of ComponentDef
COMPONENTS = {  # Mapping from category to list of ComponentDef
    # Core (always available)
    "core": [
        ComponentDef(
            "ami", "always", None, "Unified CLI for services and system management"
        ),
        ComponentDef("ami-run", "always", None, "Universal project execution wrapper"),
        ComponentDef(
            "ami-repo",
            "binary",
            "ami/scripts/bin/ami-repo",
            "Git repository and server management",
        ),
    ],
    # Enterprise services
    "enterprise": [
        ComponentDef(
            "ami-mail",
            "binary",
            "ami/scripts/bin/ami_mail.py",
            "Enterprise mail operations CLI",
        ),
        ComponentDef(
            "ami-chat",
            "binary",
            ".boot-linux/bin/matrix-commander",
            "Matrix CLI chat and automation",
        ),
        ComponentDef(
            "ami-synadm", "binary", ".boot-linux/bin/synadm", "Matrix Server Admin CLI"
        ),
        ComponentDef("ami-kcadm", "container", "ami-keycloak", "Keycloak Admin CLI"),
        ComponentDef(
            "ami-browser",
            "binary",
            ".venv/bin/playwright",
            "Browser automation (Playwright)",
        ),
    ],
    # Dev tools
    "dev": [
        ComponentDef(
            "ami-backup",
            "binary",
            "ami/scripts/backup/create/cli.py",
            "Backup to Google Drive",
        ),
        ComponentDef(
            "ami-restore",
            "binary",
            "ami/scripts/backup/restore/cli.py",
            "Restore from Google Drive",
        ),
    ],
    # AI Agents
    "agents": [
        ComponentDef(
            "ami-claude",
            "binary",
            ".venv/node_modules/.bin/claude",
            "Claude Code AI assistant",
        ),
        ComponentDef(
            "ami-gemini",
            "binary",
            ".venv/node_modules/.bin/gemini",
            "Gemini CLI AI assistant",
        ),
        ComponentDef(
            "ami-qwen",
            "binary",
            ".venv/node_modules/.bin/qwen",
            "Qwen Code AI assistant",
        ),
    ],
}


def get_component_status() -> list[ComponentStatusEntry]:
    """Get status of all components as a flat list.

    Each entry includes the component name and category for identification.
    """
    status: list[ComponentStatusEntry] = []

    for category, components in COMPONENTS.items():
        for comp in components:
            if comp.check_type == "always":
                status.append(
                    ComponentStatusEntry(
                        comp.name, True, None, comp.description, category
                    )
                )
            elif comp.check_type == "binary" and comp.check_arg is not None:
                check_result = check_binary(comp.check_arg)
                status.append(
                    ComponentStatusEntry(
                        comp.name,
                        check_result.exists,
                        check_result.version,
                        comp.description,
                        category,
                    )
                )
            elif comp.check_type == "container" and comp.check_arg is not None:
                check_result = check_container(comp.check_arg)
                status.append(
                    ComponentStatusEntry(
                        comp.name,
                        check_result.exists,
                        check_result.version,
                        comp.description,
                        category,
                    )
                )
            elif comp.check_type == "command" and comp.check_arg is not None:
                check_result = check_command(comp.check_arg.split())
                status.append(
                    ComponentStatusEntry(
                        comp.name,
                        check_result.exists,
                        check_result.version,
                        comp.description,
                        category,
                    )
                )

    return status


def print_shell_format() -> None:
    """Print component status in shell-parseable format."""
    status = get_component_status()

    for entry in status:
        v = entry.version or ""
        installed = 1 if entry.installed else 0
        print(f"{entry.category}|{entry.name}|{installed}|{v}|{entry.description}")


if __name__ == "__main__":
    print_shell_format()
