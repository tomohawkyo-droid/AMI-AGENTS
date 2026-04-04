#!/usr/bin/env python3
"""AMI Cron Management CLI.

AMI-aware crontab wrapper that auto-injects AMI environment into cron entries.
Jobs are tagged with '# AMI:' for identification and management.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

AMI_TAG = "# AMI:"


class CronJob(NamedTuple):
    """A cron job entry with its line number."""

    line_num: int
    line: str


def _ami_root() -> str:
    """Get AMI_ROOT."""
    root = os.environ.get("AMI_ROOT")
    if not root:
        print("Error: AMI_ROOT not set", file=sys.stderr)
        sys.exit(1)
    return root


def _boot_bin() -> str:
    """Get .boot-linux/bin path."""
    return str(Path(_ami_root()) / ".boot-linux" / "bin")


def _get_crontab() -> str:
    """Get current crontab contents."""
    result = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _set_crontab(content: str) -> int:
    """Write crontab contents."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cron", delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        result = subprocess.run(["crontab", tmp], check=False)
        return result.returncode
    finally:
        os.unlink(tmp)


def _get_ami_jobs(crontab: str) -> list[CronJob]:
    """Extract AMI-tagged jobs with line numbers."""
    return [
        CronJob(i + 1, line)
        for i, line in enumerate(crontab.splitlines())
        if AMI_TAG in line
    ]


def cmd_list(_args: argparse.Namespace) -> int:
    """List AMI cron jobs."""
    crontab = _get_crontab()
    jobs = _get_ami_jobs(crontab)

    if not jobs:
        print("No AMI cron jobs found.")
        return 0

    print(f"{'#':>3}  {'Schedule':<20}  Command")
    print(f"{'─' * 3}  {'─' * 20}  {'─' * 50}")

    for line_num, line in jobs:
        # Strip the AMI tag and parse
        clean = line.split(AMI_TAG)[0].strip()
        cron_field_count = 5
        parts = clean.split(None, cron_field_count)
        if len(parts) > cron_field_count:
            schedule = " ".join(parts[:cron_field_count])
            command = parts[cron_field_count]
        else:
            schedule = "???"
            command = clean
        print(f"{line_num:>3}  {schedule:<20}  {command}")

    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Add an AMI cron job."""
    root = _ami_root()
    boot = _boot_bin()
    env_file = Path(root) / ".env"

    # Build the wrapped command with AMI environment
    env_prefix = f"AMI_ROOT={root} PATH={boot}:$PATH"
    if env_file.exists():
        env_prefix = f"set -a && . {env_file} && set +a && {env_prefix}"

    label = args.label or args.command.split()[0]
    entry = f"{args.schedule} {env_prefix} {args.command}  {AMI_TAG} {label}"

    crontab = _get_crontab()
    if crontab and not crontab.endswith("\n"):
        crontab += "\n"
    crontab += entry + "\n"

    ret = _set_crontab(crontab)
    if ret == 0:
        print(f"Added AMI cron job: {label}")
    return ret


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove an AMI cron job by pattern."""
    crontab = _get_crontab()
    if not crontab:
        print("Crontab is empty.")
        return 0

    pattern = args.pattern
    lines = crontab.splitlines()
    new_lines = []
    removed = 0

    for line in lines:
        if AMI_TAG in line and re.search(pattern, line):
            removed += 1
            print(f"Removed: {line.strip()}")
        else:
            new_lines.append(line)

    if removed == 0:
        print(f"No AMI jobs matching '{pattern}' found.")
        return 0

    ret = _set_crontab("\n".join(new_lines) + "\n")
    if ret == 0:
        print(f"Removed {removed} job(s).")
    return ret


def cmd_edit(_args: argparse.Namespace) -> int:
    """Open crontab in editor."""
    return subprocess.run(["crontab", "-e"], check=False).returncode


def cmd_status(_args: argparse.Namespace) -> int:
    """Show AMI cron job status."""
    crontab = _get_crontab()
    jobs = _get_ami_jobs(crontab)

    print(f"AMI cron jobs: {len(jobs)}")
    if not jobs:
        return 0

    # Try to get recent execution info from syslog
    try:
        result = subprocess.run(
            ["journalctl", "--user-unit=cron", "-n", "50", "--no-pager", "-q"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            # Fallback to system cron log
            result = subprocess.run(
                ["grep", "-i", "cron", "/var/log/syslog"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        log_lines = result.stdout.splitlines()[-20:] if result.stdout else []
    except Exception:
        log_lines = []

    print()
    cmd_list(_args)

    if log_lines:
        print(f"\nRecent cron activity ({len(log_lines)} entries):")
        for line in log_lines[-5:]:
            print(f"  {line.strip()}")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="ami-cron",
        description="AMI-aware cron job management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ami-cron list
  ami-cron add "0 2 * * *" "ami-backup --mode full" --label nightly-backup
  ami-cron add "*/5 * * * *" "ami-repo status-all" --label repo-check
  ami-cron remove nightly-backup
  ami-cron edit
  ami-cron status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    subparsers.add_parser("list", help="List AMI cron jobs")

    # add
    p_add = subparsers.add_parser("add", help="Add an AMI cron job")
    p_add.add_argument("schedule", help='Cron schedule (e.g., "0 2 * * *")')
    p_add.add_argument("command", help="Command to run")
    p_add.add_argument("--label", help="Job label (default: command name)")

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove AMI cron job(s)")
    p_remove.add_argument("pattern", help="Pattern to match (regex)")

    # edit
    subparsers.add_parser("edit", help="Open crontab in editor")

    # status
    subparsers.add_parser("status", help="Show job status with recent activity")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "list": cmd_list,
        "add": cmd_add,
        "remove": cmd_remove,
        "edit": cmd_edit,
        "status": cmd_status,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
