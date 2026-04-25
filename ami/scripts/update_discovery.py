"""Workspace discovery and post-pull workspace sync for ami-update."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ami.cli_components.text_input_utils import Colors
from ami.scripts.update_types import (
    EXCLUDED_REPOS,
    EXCLUDED_SUBMODULES,
    SYSTEM_NAMES,
    RepoInfo,
)

_CYAN, _RESET = Colors.CYAN, Colors.RESET
_PRUNE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def find_ami_root() -> Path:
    """Return AMI project root (AMI_ROOT env or walk-up to pyproject.toml)."""
    env_root = os.environ.get("AMI_ROOT")
    if env_root:
        return Path(env_root)
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    msg = "Cannot determine AMI_ROOT"
    raise RuntimeError(msg)


def discover_repos(root: Path) -> list[RepoInfo]:
    """Walk projects/ for .git dirs/files, excluding vendored repos."""
    repos = [RepoInfo(path=root, name="AMI-AGENTS")]
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return repos
    for dirpath, dirnames, _filenames in os.walk(projects_dir):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        path = Path(dirpath)
        if (path / ".git").exists():
            rel = str(path.relative_to(root))
            if rel in EXCLUDED_REPOS or any(
                rel.endswith(exc) for exc in EXCLUDED_SUBMODULES
            ):
                dirnames.clear()
                continue
            repos.append(RepoInfo(path=path, name=rel))
            dirnames.clear()
    return sorted(repos, key=lambda r: r.name)


def categorize(repos: list[RepoInfo], tier: str) -> list[RepoInfo]:
    """Split repos into SYSTEM (ordered) or APPS tier."""
    if tier == "system":
        by_name = {r.name: r for r in repos}
        return [by_name[s] for s in SYSTEM_NAMES if s in by_name]
    return [r for r in repos if r.name not in SYSTEM_NAMES]


def run_post_system_update(root: Path) -> None:
    """Sync deps and reinstall hooks in every SYSTEM repo after pull."""
    boot_uv = root / ".boot-linux" / "bin" / "uv"
    ci_hooks = root / "projects" / "AMI-CI" / "scripts" / "generate-hooks"
    print(f"\n  {_CYAN}Syncing Python dependencies...{_RESET}")
    subprocess.run([str(boot_uv), "sync", "--extra", "dev"], cwd=str(root), check=False)
    dataops = root / "projects" / "AMI-DATAOPS" / "pyproject.toml"
    if dataops.exists():
        subprocess.run(
            [str(boot_uv), "pip", "install", "-e", "projects/AMI-DATAOPS"],
            cwd=str(root),
            check=False,
        )
    if ci_hooks.exists():
        print(f"  {_CYAN}Reinstalling git hooks in SYSTEM repos...{_RESET}")
        for sys_name in SYSTEM_NAMES:
            repo_path = root if sys_name == "AMI-AGENTS" else root / sys_name
            if (repo_path / ".pre-commit-config.yaml").exists():
                subprocess.run(
                    ["bash", str(ci_hooks)],
                    cwd=str(repo_path),
                    check=False,
                )
