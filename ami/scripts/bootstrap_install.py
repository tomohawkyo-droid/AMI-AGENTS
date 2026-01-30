"""
Bootstrap installation logic.

Handles the actual installation of components, separate from TUI.
"""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from ami.scripts.bootstrap_components import PROJECT_ROOT, Component, ComponentType
from ami.types.common import InstallationResult


class CategorizedComponents(NamedTuple):
    """Components separated by installation order."""

    core: list[Component]
    npm: list[Component]
    other: list[Component]


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


def _categorize_components(components: list[Component]) -> CategorizedComponents:
    """Separate components into core, npm, and other categories."""
    core = [c for c in components if c.group == "Core Dependencies"]
    npm = [c for c in components if c.type == ComponentType.NPM]
    other = [c for c in components if c.type != ComponentType.NPM and c not in core]
    return CategorizedComponents(core=core, npm=npm, other=other)


def _make_result(name: str, success: bool) -> InstallationResult:
    """Create an InstallationResult with keyword arguments."""
    return InstallationResult(component_name=name, success=success, error=None)


def _install_core_deps(cat: CategorizedComponents, ctx: "_InstallContext") -> int:
    """Install core dependencies. Returns next index."""
    for comp in cat.core:
        ctx.idx += 1
        if ctx.on_progress:
            ctx.on_progress(ctx.idx, ctx.total, f"Core: {comp.label}")
        success = install_component(comp)
        ctx.results.append(_make_result(comp.name, success))
        if ctx.on_result:
            ctx.on_result(comp, success)
    return ctx.idx


def _install_npm_batch(cat: CategorizedComponents, ctx: "_InstallContext") -> None:
    """Install npm packages as a batch."""
    if not cat.npm:
        return
    ctx.idx += 1
    if ctx.on_progress:
        ctx.on_progress(
            ctx.idx, ctx.total, f"NPM: {', '.join(c.label for c in cat.npm)}"
        )
    packages = [c.package for c in cat.npm if c.package]
    success = install_npm_packages(packages)
    for comp in cat.npm:
        ctx.results.append(_make_result(comp.name, success))
        if ctx.on_result:
            ctx.on_result(comp, success)


def _install_other_components(
    cat: CategorizedComponents, ctx: "_InstallContext"
) -> None:
    """Install remaining components."""
    for comp in cat.other:
        ctx.idx += 1
        if ctx.on_progress:
            ctx.on_progress(ctx.idx, ctx.total, comp.label)
        success = install_component(comp)
        ctx.results.append(_make_result(comp.name, success))
        if ctx.on_result:
            ctx.on_result(comp, success)


class _InstallContext:
    """Mutable context for installation process."""

    def __init__(
        self,
        total: int,
        on_progress: Callable[[int, int, str], None] | None,
        on_result: Callable[[Component, bool], None] | None,
    ) -> None:
        self.total = total
        self.on_progress = on_progress
        self.on_result = on_result
        self.results: list[InstallationResult] = []
        self.idx = 0


def install_components(
    components: list[Component],
    on_progress: Callable[[int, int, str], None] | None = None,
    on_result: Callable[[Component, bool], None] | None = None,
) -> list[InstallationResult]:
    """Install components in order: core deps, npm batch, others."""
    ensure_directories()
    cat = _categorize_components(components)
    ctx = _InstallContext(len(components), on_progress, on_result)

    _install_core_deps(cat, ctx)
    _install_npm_batch(cat, ctx)
    _install_other_components(cat, ctx)

    return ctx.results
