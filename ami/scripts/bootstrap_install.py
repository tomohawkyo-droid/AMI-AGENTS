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
    if component.type == ComponentType.SCRIPT:
        if not component.script:
            return False
        script_ok = run_bootstrap_script(component.script)
        # If script exited non-zero but the component is actually installed
        # (detect_path exists), treat as success. Some bootstrap scripts
        # have non-critical failures in post-install steps.
        if not script_ok and component.detect_path:
            path = PROJECT_ROOT / component.detect_path
            if path.exists():
                return True
        return script_ok
    elif component.type == ComponentType.UV:
        # UV packages are handled by uv sync
        return True
    return False


def _categorize_components(components: list[Component]) -> CategorizedComponents:
    """Separate components into core and other categories."""
    core = [c for c in components if c.group == "Core Dependencies"]
    other = [c for c in components if c not in core]
    return CategorizedComponents(core=core, other=other)


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
    """Install components in order: core deps, others."""
    ensure_directories()
    cat = _categorize_components(components)
    ctx = _InstallContext(len(components), on_progress, on_result)

    _install_core_deps(cat, ctx)
    _install_other_components(cat, ctx)

    return ctx.results
