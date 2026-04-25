"""Shared types and constants for the ami-update CLI."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, TypedDict


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


SYSTEM_NAMES = ["projects/AMI-CI", "projects/AMI-DATAOPS", "AMI-AGENTS"]
DEFAULT_CI_CONFIG = Path("ami/config/update-defaults.yaml")

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
