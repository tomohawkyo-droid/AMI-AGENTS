#!/usr/bin/env python3
"""
Bootstrap Installer TUI for AMI Orchestrator.

Provides an interactive multi-select interface for installing optional
bootstrap components with status detection.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

# Ruff E402 exempts sys.path.insert between imports
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
sys.path.insert(0, str(Path(__file__).parent))

import ami.scripts.bootstrap_components as _bootstrap_components
import ami.scripts.bootstrap_install as _bootstrap_install
from ami.cli_components import dialogs as _dialogs
from ami.cli_components import menu_selector as _menu
from ami.cli_components.selection_dialog import DialogItem
from ami.cli_components.text_input_utils import Colors
from ami.types.results import NamedComponentStatus

if TYPE_CHECKING:
    from ami.cli_components.menu_selector import MenuItem
    from ami.scripts.bootstrap_components import Component

# =============================================================================
# ANSI Colors & Styles
# =============================================================================
CYAN = Colors.CYAN
GREEN = Colors.GREEN
YELLOW = Colors.YELLOW
RED = Colors.RED
BOLD = Colors.BOLD
DIM = "\033[2m"
RESET = Colors.RESET


class MenuBuildResult(NamedTuple):
    """Result from building menu items."""

    menu_items: object  # list of MenuItem with Component or None values
    preselected_ids: set[str]


class InstallationResult(NamedTuple):
    """Result from running installation."""

    success_count: int
    failed_labels: list[str]


# =============================================================================
# ASCII Art & Banners
# =============================================================================

_BANNER_LINES = [
    f"{CYAN}╔══════════════════════════════════════════════════════════════╗",
    f"║{' ' * 64}║",
    f"║  {BOLD}█████╗ ███╗   ███╗██╗   ██████╗  ██████╗ ████████╗{RESET}{CYAN}   ║",
    f"║ {BOLD}██╔══██╗████╗ ████║██║   ██╔══██╗██╔═══██╗╚══██╔══╝{RESET}{CYAN}   ║",
    f"║ {BOLD}███████║██╔████╔██║██║   ██████╔╝██║   ██║   ██║{RESET}{CYAN}      ║",
    f"║ {BOLD}██╔══██║██║╚██╔╝██║██║   ██╔══██╗██║   ██║   ██║{RESET}{CYAN}      ║",
    f"║ {BOLD}██║  ██║██║ ╚═╝ ██║██║   ██████╔╝╚██████╔╝   ██║{RESET}{CYAN}      ║",
    f"║ {BOLD}╚═╝  ╚═╝╚═╝     ╚═╝╚═╝   ╚═════╝  ╚═════╝    ╚═╝{RESET}{CYAN}      ║",
    f"║{' ' * 64}║",
    f"║ {YELLOW}Bootstrap Component Installer{RESET}{CYAN}" + " " * 33 + "║",
    f"║ {DIM}Select components to install{RESET}{CYAN}" + " " * 34 + "║",
    f"║{' ' * 64}║",
    f"╚══════════════════════════════════════════════════════════════╝{RESET}",
]
BANNER = "\n".join(_BANNER_LINES)


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{CYAN}┌{'─' * 58}┐{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}{title}{RESET}{' ' * (57 - len(title))}{CYAN}│{RESET}")
    print(f"{CYAN}└{'─' * 58}┘{RESET}")


def print_status(icon: str, message: str, color: str = RESET) -> None:
    """Print a status message with icon."""
    print(f"  {color}{icon}{RESET} {message}")


def print_progress(current: int, total: int, label: str) -> None:
    """Print progress indicator."""
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = f"{'█' * filled}{'░' * (bar_width - filled)}"
    print(f"\n{CYAN}[{bar}]{RESET} {current}/{total}")
    print(f"{BOLD}  ► {label}{RESET}")


def _find_status_by_name(
    statuses: list[NamedComponentStatus], name: str
) -> NamedComponentStatus | None:
    """Find a status entry by component name."""
    for s in statuses:
        if s.name == name:
            return s
    return None


def format_component_label(comp: Component, status: NamedComponentStatus | None) -> str:
    """Format component label with version if installed."""
    if status and status.installed and status.version:
        return f"{comp.label} {GREEN}v{status.version}{RESET}"
    return comp.label


def format_component_description(
    comp: Component, status: NamedComponentStatus | None
) -> str:
    """Format component description with status."""
    if status and status.installed:
        return f"{comp.description} {GREEN}✓{RESET}"
    return f"{comp.description} {DIM}(not installed){RESET}"


def scan_components() -> list[NamedComponentStatus]:
    """Scan all components and return their status as a list.

    Each status has a name field for lookups.
    """
    print(f"\n{CYAN}Scanning installed components...{RESET}")

    components_by_group = _bootstrap_components.get_components_by_group()
    statuses: list[NamedComponentStatus] = []

    total = sum(len(comps) for comps in components_by_group.values())

    for group_name in _bootstrap_components.GROUPS:
        components = components_by_group.get(group_name, [])
        for comp in components:
            # Show scanning progress
            sys.stdout.write(f"\r  Checking {comp.label}...{' ' * 20}")
            sys.stdout.flush()

            raw_status = comp.get_status()
            statuses.append(
                NamedComponentStatus(
                    name=comp.name,
                    installed=raw_status.installed,
                    version=raw_status.version,
                    path=raw_status.path,
                )
            )

    sys.stdout.write(f"\r{' ' * 60}\r")  # Clear line
    sys.stdout.flush()

    # Print summary
    installed = sum(1 for s in statuses if s.installed)
    print(f"  {GREEN}✓{RESET} Found {installed}/{total} components installed\n")

    return statuses


def build_menu_items(
    statuses: list[NamedComponentStatus],
) -> MenuBuildResult:
    """Build menu items with status information.

    Returns:
        MenuBuildResult with menu_items and preselected_ids
    """
    components_by_group = _bootstrap_components.get_components_by_group()
    menu_items: list[DialogItem] = []
    preselected: set[str] = set()
    MenuItemClass = _menu.MenuItem

    for group_name in _bootstrap_components.GROUPS:
        components = components_by_group.get(group_name, [])
        if not components:
            continue

        # Count installed in group
        installed_count = sum(
            1
            for c in components
            if (
                _find_status_by_name(statuses, c.name)
                or NamedComponentStatus(c.name, False, None, None)
            ).installed
        )

        # Add group header
        menu_items.append(
            MenuItemClass(
                id=f"_header_{group_name}",
                label=group_name,
                value=None,
                description=f"{installed_count}/{len(components)} installed",
            )
        )

        # Add components in this group
        for comp in components:
            status = _find_status_by_name(statuses, comp.name)

            # Pre-select installed components
            if status and status.installed:
                preselected.add(comp.name)

            menu_items.append(
                MenuItemClass(
                    id=comp.name,
                    label=format_component_label(comp, status),
                    value=comp,
                    description=format_component_description(comp, status),
                )
            )

    return MenuBuildResult(menu_items=menu_items, preselected_ids=preselected)


def _extract_components(selected: list[MenuItem]) -> list[Component]:
    """Extract component values from selected menu items."""
    # MenuItem.value is T | str (uses id if value was None)
    # We know our values are Component instances, so filter and cast
    return [
        cast("Component", item.value)
        for item in selected
        if not isinstance(item.value, str)
    ]


def _show_selection_summary(
    components: list[Component], statuses: list[NamedComponentStatus]
) -> None:
    """Display selected components with install/reinstall status."""
    print_section(f"Selected {len(components)} Component(s)")
    for comp in components:
        status = _find_status_by_name(statuses, comp.name)
        if status and status.installed:
            print_status("•", f"{comp.label} {DIM}(reinstall){RESET}", CYAN)
        else:
            print_status("•", comp.label, CYAN)


def _run_installation(components: list[Component]) -> InstallationResult:
    """Run installation and return InstallationResult."""
    _bootstrap_install.ensure_directories()
    print_status("✓", "Ensured directories exist", GREEN)

    success_count = 0
    failed: list[str] = []

    def on_progress(current: int, total: int, label: str) -> None:
        print_progress(current, total, label)

    def on_result(comp: Component, success: bool) -> None:
        nonlocal success_count
        if success:
            success_count += 1
            print_status("✓", f"{comp.label} installed", GREEN)
        else:
            failed.append(comp.label)
            print_status("✗", f"{comp.label} failed", RED)

    _bootstrap_install.install_components(
        list(components), on_progress=on_progress, on_result=on_result
    )
    return InstallationResult(success_count=success_count, failed_labels=failed)


def _print_summary(success_count: int, failed: list[str]) -> int:
    """Print installation summary and return exit code."""
    print_section("Installation Summary")

    if failed:
        print_status("✓", f"Successful: {success_count}", GREEN)
        print_status("✗", f"Failed: {len(failed)}", RED)
        print()
        for name in failed:
            print_status("  •", name, RED)
        return 1

    print_status(
        "✓", f"All {success_count} component(s) installed successfully!", GREEN
    )
    print(f"\n{CYAN}{'─' * 60}{RESET}")
    print(f"{GREEN}  Installation complete!{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")
    return 0


def main() -> int:
    """Main entry point for the bootstrap installer TUI."""
    if not sys.stdin.isatty():
        print(f"{RED}Error:{RESET} This script requires an interactive terminal.")
        print("Run it directly, not through a pipe.")
        return 1

    print(BANNER)
    statuses = scan_components()
    menu_build_result = build_menu_items(statuses)
    menu_items = menu_build_result.menu_items
    preselected = menu_build_result.preselected_ids

    # MenuItem implements SelectableItem protocol structurally
    dialog_items = cast(list[DialogItem], menu_items)
    raw_selected = _dialogs.multiselect(
        dialog_items,
        title="Select Components",
        preselected=preselected,
        max_height=20,
    )

    # Cast back to MenuItem since we know what we passed in
    selected = cast(list["MenuItem"], raw_selected)
    selected = [s for s in selected if s.value is not None]

    if not selected:
        print(f"\n{YELLOW}No components selected. Exiting.{RESET}")
        return 0

    components = _extract_components(selected)
    _show_selection_summary(components, statuses)

    print()
    if not _dialogs.confirm(f"Install {len(components)} component(s)?", "Confirm"):
        print(f"\n{YELLOW}Installation cancelled.{RESET}")
        return 0

    print_section("Installing Components")
    install_result = _run_installation(components)
    return _print_summary(install_result.success_count, install_result.failed_labels)


if __name__ == "__main__":
    sys.exit(main())
