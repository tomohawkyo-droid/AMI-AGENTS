"""Banner helper: renders extension banner and extra-info output.

Replaces bash YAML parsing for the AMI banner display.
Imports shared logic from extension_registry in the same directory.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from typing import TYPE_CHECKING

from ami.scripts.shell.extension_registry import (
    DEFAULT_CATEGORY_PROPS,
    HealthCheckResult,
    Status,
    check_dep,
    discover_manifests,
    find_ami_root,
    group_by_category,
    resolve_extensions,
    run_check,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ami.scripts.shell.extension_registry import ResolvedExtension

# ANSI color codes matching ami-banner.sh
_COLORS = {
    "gold": "\033[38;5;214m",
    "cyan": "\033[0;36m",
    "pink": "\033[38;5;205m",
    "purple": "\033[38;5;99m",
    "blue": "\033[0;34m",
    "red": "\033[38;5;203m",
    "green": "\033[0;32m",
}
_DIM = "\033[2m"
_NC = "\033[0m"
_BOLD = "\033[1m"

# Fallback props for unknown categories
_UNKNOWN_ICON = "\U0001f539"  # blue diamond
_UNKNOWN_COLOR = "green"

_NAME_PAD = 20  # column width for extension name alignment


# ---------------------------------------------------------------------------
# Banner mode
# ---------------------------------------------------------------------------


def _color_for(category: str) -> str:
    """Return ANSI color escape for a category."""
    props = DEFAULT_CATEGORY_PROPS.get(category, {})
    color_name = props.get("color", _UNKNOWN_COLOR)
    return _COLORS.get(color_name, _COLORS["green"])


def _icon_for(category: str) -> str:
    props = DEFAULT_CATEGORY_PROPS.get(category, {})
    icon: str = props.get("icon", _UNKNOWN_ICON)
    return icon


def _title_for(category: str) -> str:
    props = DEFAULT_CATEGORY_PROPS.get(category, {})
    title: str = props.get("title", category.title())
    return title


def _has_failed_container_dep(ext: ResolvedExtension, root: Path) -> bool:
    """Return True if any container dep is missing."""
    for dep in ext.entry.get("deps", []):
        if dep.get("type") == "container" and not check_dep(dep, root):
            return True
    return False


def _format_partial_line(
    ext: ResolvedExtension,
    color: str,
    suffix: str,
) -> str:
    """Format an extension line with a trailing suffix (countdown or result)."""
    name = ext.entry["name"]
    desc = ext.entry.get("description", "")
    pad = max(1, _NAME_PAD - len(name))
    return f"  {color}> {name}{_NC}{' ' * pad}\u2192 {desc} {suffix}"


def _format_features(ext: ResolvedExtension) -> str | None:
    features = ext.entry.get("features")
    if not features:
        return None
    joined = ", ".join(features)
    return f"{' ' * _NAME_PAD}    {_DIM}{joined}{_NC}"


def _run_check_with_countdown(
    ext: ResolvedExtension,
    root: Path,
    color: str,
) -> tuple[bool, str | None]:
    """Run check in a background thread with animated countdown."""
    result_holder: list[HealthCheckResult | None] = [None]
    check_cfg = ext.entry.get("check", {})
    timeout = min(check_cfg.get("timeout", 5), 5)

    def _do_check() -> None:
        result_holder[0] = run_check(ext.entry, root)

    thread = threading.Thread(target=_do_check, daemon=True)
    thread.start()

    start = time.monotonic()
    while thread.is_alive() and (time.monotonic() - start) < timeout:
        remaining = max(0.0, timeout - (time.monotonic() - start))
        secs = int(remaining)
        centis = int((remaining - secs) * 100)
        countdown = f"[{secs:02d}:{centis:02d}]"
        line = _format_partial_line(ext, color, countdown)
        sys.stdout.write(f"\r{line}")
        sys.stdout.flush()
        time.sleep(0.1)

    thread.join(timeout=0.5)

    if result_holder[0] is None:
        return False, None
    return result_holder[0].healthy, result_holder[0].version


def _print_extension(
    ext: ResolvedExtension,
    root: Path,
    color: str,
    *,
    quiet: bool,
    is_tty: bool,
) -> None:
    """Print a single extension line with optional health check."""
    has_check = bool(ext.entry.get("check")) and not quiet
    skip_check = _has_failed_container_dep(ext, root)

    version: str | None = None
    health_ok = True

    if has_check and not skip_check:
        if is_tty:
            health_ok, version = _run_check_with_countdown(ext, root, color)
            # Clear the countdown line before printing final result
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
        else:
            result = run_check(ext.entry, root)
            health_ok, version = result.healthy, result.version

    # Build status suffix
    green = _COLORS["green"]
    if version:
        suffix = f"{green}v{version}{_NC}"
    elif health_ok:
        suffix = f"{green}\u2713{_NC}"
    else:
        red = _COLORS["red"]
        suffix = f"{red}\u2717{_NC}"

    line = _format_partial_line(ext, color, suffix)
    print(line)

    feat_line = _format_features(ext)
    if feat_line:
        print(feat_line)


def output_banner(
    resolved: list[ResolvedExtension],
    root: Path,
    *,
    quiet: bool = False,
) -> None:
    """Render the full extension banner to stdout."""
    is_tty = sys.stdout.isatty()
    by_category = group_by_category(resolved)

    for cat_name, extensions in by_category:
        # Check if any visible extensions exist in this category
        visible = [
            e for e in extensions if e.status not in (Status.UNAVAILABLE, Status.HIDDEN)
        ]
        if not visible:
            continue

        color = _color_for(cat_name)
        icon = _icon_for(cat_name)
        title = _title_for(cat_name)
        print(f"{color}{icon} {title}:{_NC}")
        print()

        for ext in visible:
            _print_extension(ext, root, color, quiet=quiet, is_tty=is_tty)
            print()

        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Extra mode
# ---------------------------------------------------------------------------

_STATUS_PAD = 18  # column width for name in extra output


def output_extra(resolved: list[ResolvedExtension]) -> None:
    """List hidden, degraded, and unavailable extensions."""
    hidden = [e for e in resolved if e.status == Status.HIDDEN]
    degraded = [e for e in resolved if e.status == Status.DEGRADED]
    unavailable = [e for e in resolved if e.status == Status.UNAVAILABLE]

    if hidden:
        print(f"{_BOLD}Hidden Extensions:{_NC}")
        for ext in hidden:
            name = ext.entry["name"]
            desc = ext.entry.get("description", "")
            pad = max(1, _STATUS_PAD - len(name))
            print(f"  {name}{' ' * pad}{desc}")
        print()

    if degraded:
        print(f"{_BOLD}Degraded Extensions:{_NC}")
        for ext in degraded:
            name = ext.entry["name"]
            desc = ext.entry.get("description", "")
            reason = ext.reason
            pad = max(1, _STATUS_PAD - len(name))
            yellow = _COLORS["gold"]
            print(f"  {name}{' ' * pad}{desc}  {yellow}DEGRADED{_NC} ({reason})")
        print()

    if unavailable:
        print(f"{_BOLD}Unavailable Extensions:{_NC}")
        for ext in unavailable:
            name = ext.entry["name"]
            desc = ext.entry.get("description", "")
            reason = ext.reason
            hint = ext.entry.get("installHint", "")
            pad = max(1, _STATUS_PAD - len(name))
            red = _COLORS["red"]
            line = f"  {name}{' ' * pad}{desc}  {red}UNAVAILABLE{_NC} ({reason})"
            if hint:
                line += f" (install: {hint})"
            print(line)
        print()

    if not hidden and not degraded and not unavailable:
        print("No hidden, degraded, or unavailable extensions.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for banner_helper."""
    parser = argparse.ArgumentParser(
        description="AMI banner helper -- extension display",
    )
    parser.add_argument(
        "--mode",
        choices=["banner", "extra"],
        default="banner",
        help="Output mode: banner (default) or extra",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Skip health/version checks for faster output",
    )
    args = parser.parse_args()

    quiet = args.quiet or os.environ.get("AMI_QUIET_MODE") == "1"

    root = find_ami_root()
    manifests = discover_manifests(root)
    resolved = resolve_extensions(manifests, root)

    if args.mode == "banner":
        output_banner(resolved, root, quiet=quiet)
    elif args.mode == "extra":
        output_extra(resolved)


if __name__ == "__main__":
    main()
