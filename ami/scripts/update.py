#!/usr/bin/env python3
"""ami-update CLI entry point.

Argument parsing, terminal restoration, and dispatch to the runners
in update_ci / update_interactive. All domain logic lives in the
sibling update_* modules:

  update_types       types and constants
  update_git         git subprocess primitives and analyze/pull
  update_discovery   workspace discovery + post-pull sync
  update_display     console output helpers
  update_interactive interactive (TUI multiselect) runner
  update_ci          non-interactive (YAML-driven) runner

See docs/specifications/SPEC-UPDATE.md for the full design.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ami.cli_components.text_input_utils import Colors
from ami.scripts.update_ci import run_from_defaults
from ami.scripts.update_discovery import (
    categorize,
    discover_repos,
    find_ami_root,
)
from ami.scripts.update_interactive import run_interactive
from ami.scripts.update_types import DEFAULT_CI_CONFIG

_CYAN, _RED, _RESET = Colors.CYAN, Colors.RED, Colors.RESET


def _restore_terminal() -> None:
    if not sys.stdout.isatty():
        return
    try:
        sys.stdout.write(f"{_RESET}")
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
        description=(
            "Auto-update AMI repos. Default scope: SYSTEM only "
            "(AMI-CI, AMI-DATAOPS, AMI-AGENTS)."
        ),
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
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--projects",
        action="store_true",
        help="Update only projects/* (APPS tier); skip SYSTEM",
    )
    scope.add_argument(
        "--all",
        action="store_true",
        dest="all_tiers",
        help="Update SYSTEM and APPS tiers",
    )
    args = parser.parse_args()
    if args.projects:
        scope_tiers = ["apps"]
    elif args.all_tiers:
        scope_tiers = ["system", "apps"]
    else:
        scope_tiers = ["system"]
    cli_scope: list[str] | None = (
        scope_tiers if (args.projects or args.all_tiers) else None
    )
    root = find_ami_root()
    repos = discover_repos(root)
    system_repos = categorize(repos, tier="system")
    app_repos = categorize(repos, tier="apps")
    defaults_path: Path | None = args.defaults
    if args.ci and defaults_path is None:
        defaults_path = root / DEFAULT_CI_CONFIG
    if defaults_path is not None:
        return run_from_defaults(
            defaults_path, system_repos, app_repos, root, cli_scope_tiers=cli_scope
        )
    if not sys.stdin.isatty():
        print(f"{_RED}Error:{_RESET} This script requires an interactive terminal.")
        print("Run it directly, not through a pipe.")
        print(f"\n{_CYAN}Tip:{_RESET} Use --defaults FILE for non-interactive CI mode.")
        return 1
    return run_interactive(system_repos, app_repos, root, scope_tiers)


if __name__ == "__main__":
    sys.exit(main())
