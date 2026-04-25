"""Interactive (TUI multiselect) runner for ami-update."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from ami.cli_components import dialogs as _dialogs
from ami.cli_components.menu_selector import MenuItem
from ami.cli_components.selection_dialog import DialogItem
from ami.cli_components.text_input_utils import Colors
from ami.scripts.update_discovery import run_post_system_update
from ami.scripts.update_display import (
    print_dirty_error,
    print_summary,
    print_tier_status,
)
from ami.scripts.update_git import analyze_repo, check_dirty, pull_updates
from ami.scripts.update_types import PullResult, RemoteUpdate, RepoInfo

_CYAN, _GREEN, _YELLOW, _RED = Colors.CYAN, Colors.GREEN, Colors.YELLOW, Colors.RED
_BOLD, _RESET, _DIM = Colors.BOLD, Colors.RESET, "\033[2m"


def _select_updates_interactive(
    updates: list[RemoteUpdate], title: str
) -> list[RemoteUpdate] | None:
    items: list[DialogItem] = []
    preselected: set[str] = set()
    for u in updates:
        item_id = f"{u.repo.name}:{u.remote}"
        suffix = "" if u.can_ff else f"  {_RED}diverged{_RESET}"
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
        print(f"\n  {_DIM}Nothing to update.{_RESET}")
        return []
    selected = _dialogs.multiselect(
        items=items,
        title=title,
        preselected=preselected,
        max_height=20,
    )
    if not selected:
        return None
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
        print_dirty_error(dirty)
        return [], []
    print(f"\n{_CYAN}Fetching {label} repos...{_RESET}")
    all_updates: list[RemoteUpdate] = []
    for repo in repos:
        all_updates.extend(analyze_repo(repo))
    print_tier_status(label, all_updates, repos)
    if not all_updates:
        print(f"\n  {_GREEN}Everything up to date.{_RESET}")
        return [], all_updates
    chosen = _select_updates_interactive(all_updates, f"Update {label} repos")
    if chosen is None:
        print(f"\n  {_YELLOW}Cancelled.{_RESET}")
        return [], all_updates
    return pull_updates(chosen), all_updates


def run_interactive(
    system_repos: list[RepoInfo],
    app_repos: list[RepoInfo],
    root: Path,
    scope_tiers: list[str],
) -> int:
    all_results: list[PullResult] = []
    sys_results: list[PullResult] = []
    app_results: list[PullResult] = []
    if "system" in scope_tiers:
        sys_results, _ = _run_tier_interactive("SYSTEM", system_repos)
        all_results.extend(sys_results)
        if sys_results and any(r.success for r in sys_results):
            run_post_system_update(root)
            print(f"\n  {_GREEN}→ Hooks reinstalled, deps synced{_RESET}")
    if "apps" in scope_tiers:
        app_results, _ = _run_tier_interactive("APPS", app_repos)
        all_results.extend(app_results)
    if not all_results:
        print(f"\n{_GREEN}Everything up to date.{_RESET}")
        return 0
    print(f"\n{_BOLD}Update Summary{_RESET}")
    print(f"{_CYAN}{'─' * 56}{_RESET}")
    if "system" in scope_tiers:
        print_summary(sys_results, "SYSTEM")
    if "apps" in scope_tiers:
        print_summary(app_results, "APPS")
    return 0 if all(r.success for r in all_results) else 1
