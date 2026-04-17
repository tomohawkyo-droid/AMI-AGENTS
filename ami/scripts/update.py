#!/usr/bin/env python3
"""Auto-update all AMI repos (SYSTEM then APPS).

Provides interactive multiselect and non-interactive (--defaults) modes.
See docs/specifications/SPEC-UPDATE.md for full design.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, TypedDict, cast

import yaml

sys.path.insert(
    0,
    os.environ.get(
        "AMI_PROJECT_ROOT",
        str(
            next(
                p
                for p in Path(__file__).resolve().parents
                if (p / "pyproject.toml").exists()
            )
        ),
    ),
)

from ami.cli_components import dialogs as _dialogs
from ami.cli_components.menu_selector import MenuItem
from ami.cli_components.selection_dialog import DialogItem
from ami.cli_components.text_input_utils import Colors

CYAN, GREEN, YELLOW, RED = Colors.CYAN, Colors.GREEN, Colors.YELLOW, Colors.RED
BOLD, RESET, DIM = Colors.BOLD, Colors.RESET, "\033[2m"


class RepoInfo(NamedTuple):
    path: Path
    name: str


class RemoteUpdate(NamedTuple):
    repo: RepoInfo
    remote: str
    branch: str
    commits_behind: int
    can_ff: bool


class PullResult(NamedTuple):
    repo: RepoInfo
    remote: str
    success: bool
    output: str


class UpdateConfig(TypedDict, total=False):
    remote: str
    tiers: list[str]
    fail_on_diverge: bool
    fail_on_dirty: bool


EXCLUDED_REPOS = {
    "projects/RUST-TRADING/python-ta-reference",
    "projects/RUST-TRADING/config",
    "projects/RUST-TRADING/docs",
    "projects/RUST-TRADING/scripts",
    "projects/RUST-TRADING/SUCK",
    "projects/polymarket-insider-tracker",
    "projects/AMI-SRP",
    "projects/AMI-FOLD",
    "projects/CV",
    "projects/docs",
    "projects/res",
}
EXCLUDED_SUBMODULES = {
    "ansible/matrix-docker-ansible-deploy",
    "himalaya",
}
SYSTEM_NAMES = ["projects/AMI-CI", "projects/AMI-DATAOPS", "AMI-AGENTS"]
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


def _git(path: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def check_dirty(repos: list[RepoInfo]) -> list[RepoInfo]:
    """Return repos with uncommitted changes."""
    dirty: list[RepoInfo] = []
    for repo in repos:
        result = _git(repo.path, "status", "--porcelain", timeout=10)
        if result.stdout.strip():
            dirty.append(repo)
    return dirty


def get_current_branch(repo: RepoInfo) -> str | None:
    result = _git(repo.path, "branch", "--show-current", timeout=10)
    return result.stdout.strip() or None


def get_remotes(repo: RepoInfo) -> list[str]:
    result = _git(repo.path, "remote", timeout=10)
    return [r for r in result.stdout.strip().splitlines() if r]


def ref_exists(repo: RepoInfo, ref: str) -> bool:
    return _git(repo.path, "rev-parse", "--verify", ref, timeout=10).returncode == 0


def count_behind(repo: RepoInfo, revrange: str) -> int:
    result = _git(repo.path, "rev-list", "--count", revrange, timeout=10)
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def is_ancestor(repo: RepoInfo, ancestor: str, descendant: str) -> bool:
    return (
        _git(
            repo.path, "merge-base", "--is-ancestor", ancestor, descendant, timeout=10
        ).returncode
        == 0
    )


def analyze_repo(repo: RepoInfo) -> list[RemoteUpdate]:
    """Fetch all remotes and return updates with behind count and ff status."""
    if _git(repo.path, "fetch", "--all", "--quiet", timeout=60).returncode != 0:
        print(f"  {YELLOW}!{RESET} {repo.name}: fetch failed, skipping")
        return []
    branch = get_current_branch(repo)
    if not branch:
        print(f"  {YELLOW}!{RESET} {repo.name}: detached HEAD, skipping")
        return []
    remotes = get_remotes(repo)
    if not remotes:
        print(f"  {YELLOW}!{RESET} {repo.name}: no remotes, skipping")
        return []
    updates: list[RemoteUpdate] = []
    for remote in remotes:
        remote_ref = f"{remote}/{branch}"
        if not ref_exists(repo, remote_ref):
            continue
        behind = count_behind(repo, f"HEAD..{remote_ref}")
        if behind == 0:
            continue
        updates.append(
            RemoteUpdate(
                repo=repo,
                remote=remote,
                branch=branch,
                commits_behind=behind,
                can_ff=is_ancestor(repo, "HEAD", remote_ref),
            )
        )
    return updates


def pull_updates(updates: list[RemoteUpdate]) -> list[PullResult]:
    """Execute git pull --ff-only for each update."""
    results: list[PullResult] = []
    for u in updates:
        r = _git(u.repo.path, "pull", "--ff-only", u.remote, u.branch, timeout=60)
        results.append(
            PullResult(
                repo=u.repo,
                remote=u.remote,
                success=r.returncode == 0,
                output=(r.stdout + r.stderr).strip(),
            )
        )
    return results


def run_post_system_update(root: Path) -> None:
    """Sync deps and reinstall hooks in every SYSTEM repo after pull."""
    boot_uv = root / ".boot-linux" / "bin" / "uv"
    ci_hooks = root / "projects" / "AMI-CI" / "scripts" / "generate-hooks"
    print(f"\n  {CYAN}Syncing Python dependencies...{RESET}")
    subprocess.run([str(boot_uv), "sync", "--extra", "dev"], cwd=str(root), check=False)
    dataops = root / "projects" / "AMI-DATAOPS" / "pyproject.toml"
    if dataops.exists():
        subprocess.run(
            [str(boot_uv), "pip", "install", "-e", "projects/AMI-DATAOPS"],
            cwd=str(root),
            check=False,
        )
    if ci_hooks.exists():
        print(f"  {CYAN}Reinstalling git hooks in SYSTEM repos...{RESET}")
        for sys_name in SYSTEM_NAMES:
            repo_path = root if sys_name == "AMI-AGENTS" else root / sys_name
            if (repo_path / ".pre-commit-config.yaml").exists():
                subprocess.run(
                    ["bash", str(ci_hooks)],
                    cwd=str(repo_path),
                    check=False,
                )


# -- Display helpers --------------------------------------------------------


def _print_dirty_error(dirty: list[RepoInfo]) -> None:
    print(
        f"\n{RED}ERROR:{RESET} Cannot update -- the following repos have "
        "uncommitted changes:\n"
    )
    for repo in dirty:
        print(f"  {repo.name}")
    print("\nCommit or stash your changes, then retry.")


def _print_diverge_error(non_ff: list[RemoteUpdate]) -> None:
    print(f"\n{RED}ERROR:{RESET} The following repos have diverged history:\n")
    for u in non_ff:
        print(f"  {u.repo.name}  {u.remote}/{u.branch}")
    print("\nRebase or reset manually, then retry.")


def _print_tier_status(
    label: str, updates: list[RemoteUpdate], repos: list[RepoInfo]
) -> None:
    print(f"\n{BOLD}{label} -- Update Status{RESET}")
    print(f"{CYAN}{'─' * 56}{RESET}")
    seen: set[str] = set()
    for u in updates:
        seen.add(u.repo.name)
        ff = f"{GREEN}clean ff{RESET}" if u.can_ff else f"{RED}diverged{RESET}"
        print(
            f"  {u.repo.name:<20s} {u.remote}/{u.branch:<16s} "
            f"↓{u.commits_behind:<4d} {ff}"
        )
    for r in repos:
        if r.name not in seen:
            print(f"  {r.name:<20s} {DIM}already up to date{RESET}")


def _print_summary(results: list[PullResult], label: str) -> None:
    if not results:
        return
    print(f"\n{BOLD}{label}:{RESET}")
    for r in results:
        mark = f"{GREEN}✓{RESET}" if r.success else f"{RED}✗{RESET}"
        status = "pulled" if r.success else "FAILED"
        print(f"  {mark} {r.repo.name:<20s} {r.remote}  {status}")


# -- Interactive mode -------------------------------------------------------


def _select_updates_interactive(
    updates: list[RemoteUpdate], title: str
) -> list[RemoteUpdate] | None:
    items: list[DialogItem] = []
    preselected: set[str] = set()
    for u in updates:
        item_id = f"{u.repo.name}:{u.remote}"
        suffix = "" if u.can_ff else f"  {RED}diverged{RESET}"
        items.append(
            cast(
                DialogItem,
                MenuItem(
                    id=item_id,
                    label=u.repo.name,
                    value=u,
                    description=f"{u.remote}/{u.branch}  ↓{u.commits_behind}{suffix}",
                    disabled=not u.can_ff,
                ),
            )
        )
        if u.can_ff:
            preselected.add(item_id)
    if not items:
        print(f"\n  {DIM}Nothing to update.{RESET}")
        return []
    selected = _dialogs.multiselect(
        items=items,
        title=title,
        preselected=preselected,
        max_height=20,
    )
    if not selected:
        return None
    # MenuItem objects have .value; filter and cast
    result: list[RemoteUpdate] = []
    for item in selected:
        menu_item = cast("MenuItem[RemoteUpdate]", item)
        result.append(cast(RemoteUpdate, menu_item.value))
    return result


def _run_tier_interactive(
    label: str, repos: list[RepoInfo]
) -> tuple[list[PullResult], list[RemoteUpdate]]:
    if not repos:
        return [], []
    dirty = check_dirty(repos)
    if dirty:
        _print_dirty_error(dirty)
        return [], []
    print(f"\n{CYAN}Fetching {label} repos...{RESET}")
    all_updates: list[RemoteUpdate] = []
    for repo in repos:
        all_updates.extend(analyze_repo(repo))
    _print_tier_status(label, all_updates, repos)
    if not all_updates:
        print(f"\n  {GREEN}Everything up to date.{RESET}")
        return [], all_updates
    chosen = _select_updates_interactive(all_updates, f"Update {label} repos")
    if chosen is None:
        print(f"\n  {YELLOW}Cancelled.{RESET}")
        return [], all_updates
    return pull_updates(chosen), all_updates


def _run_interactive(
    system_repos: list[RepoInfo], app_repos: list[RepoInfo], root: Path
) -> int:
    all_results: list[PullResult] = []
    sys_results, _ = _run_tier_interactive("SYSTEM", system_repos)
    all_results.extend(sys_results)
    if sys_results and any(r.success for r in sys_results):
        run_post_system_update(root)
        print(f"\n  {GREEN}→ Hooks reinstalled, deps synced{RESET}")
    app_results, _ = _run_tier_interactive("APPS", app_repos)
    all_results.extend(app_results)
    if not all_results:
        print(f"\n{GREEN}Everything up to date.{RESET}")
        return 0
    print(f"\n{BOLD}Update Summary{RESET}")
    print(f"{CYAN}{'─' * 56}{RESET}")
    _print_summary(sys_results, "SYSTEM")
    _print_summary(app_results, "APPS")
    return 0 if all(r.success for r in all_results) else 1


# -- Non-interactive mode ---------------------------------------------------


def _run_from_defaults(
    defaults_file: Path,
    system_repos: list[RepoInfo],
    app_repos: list[RepoInfo],
    root: Path,
) -> int:
    if not defaults_file.exists():
        print(f"{RED}Error:{RESET} Defaults file not found: {defaults_file}")
        return 1
    raw = yaml.safe_load(defaults_file.read_text())
    config = cast(UpdateConfig, raw or {})
    remote = config.get("remote", "origin")
    fail_on_diverge = config.get("fail_on_diverge", True)
    fail_on_dirty = config.get("fail_on_dirty", True)
    tiers = config.get("tiers", ["system", "apps"])
    print(f"{CYAN}Running in CI mode with defaults from:{RESET} {defaults_file}\n")
    all_repos: list[RepoInfo] = []
    if "system" in tiers:
        all_repos.extend(system_repos)
    if "apps" in tiers:
        all_repos.extend(app_repos)
    dirty = check_dirty(all_repos)
    if dirty:
        _print_dirty_error(dirty)
        return 1 if fail_on_dirty else 0
    print(f"{CYAN}Fetching all repos...{RESET}")
    updates: list[RemoteUpdate] = []
    for repo in all_repos:
        updates.extend(u for u in analyze_repo(repo) if u.remote == remote)
    non_ff = [u for u in updates if not u.can_ff]
    if non_ff and fail_on_diverge:
        _print_diverge_error(non_ff)
        return 1
    mergeable = [u for u in updates if u.can_ff]
    if not mergeable:
        print(f"\n{GREEN}Everything up to date.{RESET}")
        return 0
    results = pull_updates(mergeable)
    if "system" in tiers and any(r.success for r in results):
        run_post_system_update(root)
    system_set = set(SYSTEM_NAMES)
    sys_results = [r for r in results if r.repo.name in system_set]
    app_results = [r for r in results if r.repo.name not in system_set]
    print(f"\n{BOLD}Update Summary{RESET}")
    print(f"{CYAN}{'─' * 56}{RESET}")
    _print_summary(sys_results, "SYSTEM")
    _print_summary(app_results, "APPS")
    return 0 if all(r.success for r in results) else 1


# -- Terminal restore & entry points ----------------------------------------


DEFAULT_CI_CONFIG = Path("ami/config/update-defaults.yaml")


def _restore_terminal() -> None:
    if not sys.stdout.isatty():
        return
    try:
        sys.stdout.write(f"{RESET}")
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[r")
        sys.stdout.write("\033[999E")
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


def main() -> int:
    """Entry point with terminal restore on any exit path."""
    try:
        return _main_impl()
    finally:
        _restore_terminal()


def _main_impl() -> int:
    parser = argparse.ArgumentParser(
        prog="ami-update",
        description="Auto-update AMI repos (SYSTEM then APPS)",
    )
    parser.add_argument(
        "--defaults",
        type=Path,
        metavar="FILE",
        help="Non-interactive mode using YAML config file",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help=f"Non-interactive CI; uses {DEFAULT_CI_CONFIG} unless --defaults given",
    )
    args = parser.parse_args()
    root = find_ami_root()
    repos = discover_repos(root)
    system_repos = categorize(repos, tier="system")
    app_repos = categorize(repos, tier="apps")
    defaults_path: Path | None = args.defaults
    if args.ci and defaults_path is None:
        defaults_path = root / DEFAULT_CI_CONFIG
    if defaults_path is not None:
        return _run_from_defaults(defaults_path, system_repos, app_repos, root)
    if not sys.stdin.isatty():
        print(f"{RED}Error:{RESET} This script requires an interactive terminal.")
        print("Run it directly, not through a pipe.")
        print(f"\n{CYAN}Tip:{RESET} Use --defaults FILE for non-interactive CI mode.")
        return 1
    return _run_interactive(system_repos, app_repos, root)


if __name__ == "__main__":
    sys.exit(main())
