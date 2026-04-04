#!/usr/bin/env python3
"""AMI Repository Management CLI.

Git repository and server management tool for AMI Orchestrator.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="ami-repo",
        description="Git repository and server management for AMI Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ami-repo status          Show repository status
  ami-repo status-all      Show status across all repos
  ami-repo pull            Pull latest changes
  ami-repo push            Push local changes
  ami-repo sync            Pull and push (sync with remote)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    subparsers.add_parser("status", help="Show repository status")

    # Status-all command
    subparsers.add_parser("status-all", help="Recursive git status across all repos")

    # Pull command
    subparsers.add_parser("pull", help="Pull latest changes from remote")

    # Push command
    subparsers.add_parser("push", help="Push local changes to remote")

    # Sync command
    subparsers.add_parser("sync", help="Sync with remote (pull then push)")

    return parser


def run_git(*args: str) -> int:
    """Run a git command."""
    cmd = ["git", *args]
    result = subprocess.run(cmd, capture_output=False, check=False)
    return result.returncode


def cmd_status() -> int:
    """Show repository status."""
    return run_git("status")


def cmd_status_all() -> int:
    """Recursive git status across all repos — delegates to git-status-all."""
    ami_root = os.environ.get("AMI_ROOT")
    if not ami_root:
        print("Error: AMI_ROOT not set", file=sys.stderr)
        return 1

    status_script = Path(ami_root) / "ami" / "scripts" / "utils" / "git-status-all"
    if not status_script.exists():
        print(f"Error: {status_script} not found", file=sys.stderr)
        return 1

    result = subprocess.run([str(status_script)], check=False)
    return result.returncode


def cmd_pull() -> int:
    """Pull latest changes."""
    return run_git("pull", "--rebase")


def cmd_push() -> int:
    """Push local changes."""
    return run_git("push")


def cmd_sync() -> int:
    """Sync with remote."""
    ret = cmd_pull()
    if ret != 0:
        return ret
    return cmd_push()


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "status": cmd_status,
        "status-all": cmd_status_all,
        "pull": cmd_pull,
        "push": cmd_push,
        "sync": cmd_sync,
    }

    handler = commands.get(args.command)
    if handler:
        return handler()

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
