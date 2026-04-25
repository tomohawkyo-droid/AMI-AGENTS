"""Console output helpers for ami-update (errors, tier status, summaries)."""

from __future__ import annotations

from ami.cli_components.text_input_utils import Colors
from ami.scripts.update_types import PullResult, RemoteUpdate, RepoInfo

_CYAN, _GREEN, _RED = Colors.CYAN, Colors.GREEN, Colors.RED
_BOLD, _RESET, _DIM = Colors.BOLD, Colors.RESET, "\033[2m"


def print_dirty_error(dirty: list[RepoInfo]) -> None:
    print(
        f"\n{_RED}ERROR:{_RESET} Cannot update, the following repos have "
        "uncommitted changes:\n"
    )
    for repo in dirty:
        print(f"  {repo.name}")
    print("\nCommit or stash your changes, then retry.")


def print_diverge_error(non_ff: list[RemoteUpdate]) -> None:
    print(f"\n{_RED}ERROR:{_RESET} The following repos have diverged history:\n")
    for u in non_ff:
        print(f"  {u.repo.name}  {u.remote}/{u.branch}")
    print("\nRebase or reset manually, then retry.")


def print_tier_status(
    label: str, updates: list[RemoteUpdate], repos: list[RepoInfo]
) -> None:
    print(f"\n{_BOLD}{label}: Update Status{_RESET}")
    print(f"{_CYAN}{'─' * 56}{_RESET}")
    seen: set[str] = set()
    for u in updates:
        seen.add(u.repo.name)
        ff = f"{_GREEN}clean ff{_RESET}" if u.can_ff else f"{_RED}diverged{_RESET}"
        print(
            f"  {u.repo.name:<20s} {u.remote}/{u.branch:<16s} "
            f"↓{u.commits_behind:<4d} {ff}"
        )
    for r in repos:
        if r.name not in seen:
            print(f"  {r.name:<20s} {_DIM}already up to date{_RESET}")


def print_summary(results: list[PullResult], label: str) -> None:
    if not results:
        return
    print(f"\n{_BOLD}{label}:{_RESET}")
    for r in results:
        mark = f"{_GREEN}✓{_RESET}" if r.success else f"{_RED}✗{_RESET}"
        status = "pulled" if r.success else "FAILED"
        print(f"  {mark} {r.repo.name:<20s} {r.remote}  {status}")
