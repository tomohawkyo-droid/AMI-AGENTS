"""Non-interactive (YAML-driven CI) runner for ami-update."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from ami.cli_components.text_input_utils import Colors
from ami.scripts.update_discovery import run_post_system_update
from ami.scripts.update_display import (
    print_dirty_error,
    print_diverge_error,
    print_summary,
)
from ami.scripts.update_git import analyze_repo, check_dirty, pull_updates
from ami.scripts.update_types import (
    SYSTEM_NAMES,
    RemoteUpdate,
    RepoInfo,
    UpdateConfig,
)

_CYAN, _GREEN, _RED = Colors.CYAN, Colors.GREEN, Colors.RED
_BOLD, _RESET = Colors.BOLD, Colors.RESET


def run_from_defaults(
    defaults_file: Path,
    system_repos: list[RepoInfo],
    app_repos: list[RepoInfo],
    root: Path,
    cli_scope_tiers: list[str] | None = None,
) -> int:
    if not defaults_file.exists():
        print(f"{_RED}Error:{_RESET} Defaults file not found: {defaults_file}")
        return 1
    raw = yaml.safe_load(defaults_file.read_text())
    config = cast(UpdateConfig, raw or {})
    remote = config.get("remote", "origin")
    fail_on_diverge = config.get("fail_on_diverge", True)
    fail_on_dirty = config.get("fail_on_dirty", True)
    # CLI scope flags override the YAML's `tiers` list when provided.
    tiers = (
        cli_scope_tiers
        if cli_scope_tiers is not None
        else config.get("tiers", ["system"])
    )
    print(f"{_CYAN}Running in CI mode with defaults from:{_RESET} {defaults_file}\n")
    all_repos: list[RepoInfo] = []
    if "system" in tiers:
        all_repos.extend(system_repos)
    if "apps" in tiers:
        all_repos.extend(app_repos)
    dirty = check_dirty(all_repos)
    if dirty:
        print_dirty_error(dirty)
        return 1 if fail_on_dirty else 0
    print(f"{_CYAN}Fetching all repos...{_RESET}")
    updates: list[RemoteUpdate] = []
    for repo in all_repos:
        updates.extend(u for u in analyze_repo(repo) if u.remote == remote)
    non_ff = [u for u in updates if not u.can_ff]
    if non_ff and fail_on_diverge:
        print_diverge_error(non_ff)
        return 1
    mergeable = [u for u in updates if u.can_ff]
    if not mergeable:
        print(f"\n{_GREEN}Everything up to date.{_RESET}")
        return 0
    results = pull_updates(mergeable)
    if "system" in tiers and any(r.success for r in results):
        run_post_system_update(root)
    system_set = set(SYSTEM_NAMES)
    sys_results = [r for r in results if r.repo.name in system_set]
    app_results = [r for r in results if r.repo.name not in system_set]
    print(f"\n{_BOLD}Update Summary{_RESET}")
    print(f"{_CYAN}{'─' * 56}{_RESET}")
    print_summary(sys_results, "SYSTEM")
    print_summary(app_results, "APPS")
    return 0 if all(r.success for r in results) else 1
