"""Git subprocess primitives + repo analysis + pull execution for ami-update."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ami.cli_components.text_input_utils import Colors
from ami.scripts.update_types import PullResult, RemoteUpdate, RepoInfo

_YELLOW, _RESET = Colors.YELLOW, Colors.RESET


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
        print(f"  {_YELLOW}!{_RESET} {repo.name}: fetch failed, skipping")
        return []
    branch = get_current_branch(repo)
    if not branch:
        print(f"  {_YELLOW}!{_RESET} {repo.name}: detached HEAD, skipping")
        return []
    remotes = get_remotes(repo)
    if not remotes:
        print(f"  {_YELLOW}!{_RESET} {repo.name}: no remotes, skipping")
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
