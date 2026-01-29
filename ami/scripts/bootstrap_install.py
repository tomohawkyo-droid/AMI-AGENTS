"""
Bootstrap installation logic.

Handles the actual installation of components, separate from TUI.
"""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from ami.scripts.bootstrap_components import PROJECT_ROOT, Component, ComponentType
from ami.types.common import InstallationResult


def ensure_directories() -> None:
    """Ensure required directories exist."""
    dirs = [
        PROJECT_ROOT / ".boot-linux" / "bin",
        PROJECT_ROOT / ".venv" / "bin",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def get_bootstrap_dir() -> Path:
    """Get the bootstrap scripts directory."""
    return PROJECT_ROOT / "ami" / "scripts" / "bootstrap"


def get_npm_path() -> Path:
    """Get npm binary path."""
    return PROJECT_ROOT / ".boot-linux" / "node-env" / "bin" / "npm"


def get_node_modules_dir() -> Path:
    """Get node_modules installation directory."""
    return PROJECT_ROOT / ".venv" / "node_modules"


def ensure_node_env() -> bool:
    """Ensure Node.js environment is set up."""
    npm_path = get_npm_path()
    if npm_path.exists():
        return True

    try:
        result = subprocess.run(
            ["bash", "-c", "source ami/scripts/setup/node.sh && setup_node_env"],
            cwd=str(PROJECT_ROOT),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    else:
        return result.returncode == 0


def install_npm_packages(packages: list[str]) -> bool:
    """Install npm packages (all at once to avoid conflicts).

    Args:
        packages: List of package names with versions

    Returns:
        True if successful, False otherwise
    """
    if not packages:
        return True

    if not ensure_node_env():
        return False

    npm_path = get_npm_path()
    node_modules = get_node_modules_dir()

    try:
        cmd = [
            str(npm_path),
            "install",
            "--prefix",
            str(node_modules.parent),
            "--no-save",
            "--force",
            "--loglevel",
            "error",
            *packages,
        ]
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    else:
        return result.returncode == 0


def run_bootstrap_script(script_name: str) -> bool:
    """Run a single bootstrap script."""
    script_path = get_bootstrap_dir() / script_name
    if not script_path.exists():
        return False

    try:
        # Set environment variables to fix path issues in scripts
        env = dict(os.environ)
        env["BOOT_LINUX_DIR"] = str(PROJECT_ROOT / ".boot-linux")
        env["VENV_DIR"] = str(PROJECT_ROOT / ".venv")

        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=str(PROJECT_ROOT),
            env=env,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    else:
        return result.returncode == 0


def install_component(component: Component) -> bool:
    """Install a single component based on its type."""
    if component.type == ComponentType.NPM:
        if not component.package:
            return False
        return install_npm_packages([component.package])
    elif component.type == ComponentType.SCRIPT:
        if not component.script:
            return False
        return run_bootstrap_script(component.script)
    elif component.type == ComponentType.UV:
        # UV packages are handled by uv sync
        return True
    return False


def install_components(
    components: list[Component],
    on_progress: Callable[[int, int, str], None] | None = None,
    on_result: Callable[[Component, bool], None] | None = None,
) -> list[InstallationResult]:
    """Install multiple components.

    Args:
        components: List of components to install
        on_progress: Callback(current, total, label) for progress updates
        on_result: Callback(component, success) for each result

    Returns:
        list of InstallationResult with name and success status
    """
    ensure_directories()

    results: list[InstallationResult] = []

    # Separate npm packages from scripts for batching
    npm_components = [c for c in components if c.type == ComponentType.NPM]
    other_components = [c for c in components if c.type != ComponentType.NPM]

    total = len(components)
    current = 0

    # Install all npm packages at once (to avoid conflicts)
    if npm_components:
        current += 1
        if on_progress:
            labels = [c.label for c in npm_components]
            on_progress(current, total, f"NPM: {', '.join(labels)}")

        packages = [c.package for c in npm_components if c.package]
        success = install_npm_packages(packages)

        for comp in npm_components:
            results.append(
                InstallationResult(
                    component_name=comp.name, success=success, error=None
                )
            )
            if on_result:
                on_result(comp, success)

    # Install other components one at a time
    for comp in other_components:
        current += 1
        if on_progress:
            on_progress(current, total, comp.label)

        success = install_component(comp)
        results.append(
            InstallationResult(component_name=comp.name, success=success, error=None)
        )

        if on_result:
            on_result(comp, success)

    return results
