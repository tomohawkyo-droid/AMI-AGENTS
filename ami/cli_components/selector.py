"""
Backup selector UI module.

Provides interactive selection of backup files from a list.
"""

from typing import TypedDict

from loguru import logger

from ami.cli_components.format_utils import format_file_size
from ami.cli_components.menu_selector import MenuItem, MenuSelector
from ami.cli_components.text_input_utils import Colors

# Threshold for truncating file IDs in display
FILE_ID_DISPLAY_THRESHOLD = 12


class BackupFileInfo(TypedDict, total=False):
    """Metadata for a backup file."""

    id: str
    name: str
    modifiedTime: str
    size: str | int


def select_backup_interactive(backup_files: list[BackupFileInfo]) -> str | None:
    """
    Present an interactive menu to select a backup file.

    Args:
        backup_files: List of backup file metadata dicts

    Returns:
        Selected file ID or None if no selection made
    """
    if not backup_files:
        logger.error("No backup files available to select")
        return None

    # Convert backup files to menu items
    menu_items = []
    for i, file_info in enumerate(backup_files):
        name = file_info.get("name", "Unknown")
        modified_time = file_info.get("modifiedTime", "Unknown")
        size = file_info.get("size", "Unknown")
        file_id = file_info.get("id", "")

        size_str = format_file_size(size)

        description = f"Modified: {modified_time} | Size: {size_str}"

        # We use file_id as the value
        menu_items.append(MenuItem(str(i), name, file_id, description))

    selector = MenuSelector(
        menu_items, "Select a backup to restore", max_visible_items=10
    )
    selected = selector.run()

    if selected:
        selected_item = selected[0]
        logger.info(
            f"Selected backup: {selected_item.label} (ID: {selected_item.value})"
        )
        return selected_item.value

    return None


def display_backup_list(
    backup_files: list[BackupFileInfo], title: str = "Available Backup Files"
) -> None:
    """
    Display a list of backup files without interactive selection.

    Args:
        backup_files: List of backup file metadata
        title: Title for the display
    """
    if not backup_files:
        print(f"{Colors.YELLOW}No backup files found.{Colors.RESET}")
        return

    print(f"\n{Colors.CYAN}┌{'─' * 78}┐{Colors.RESET}")
    print(f"  {title:^76}")
    print(f"{Colors.CYAN}├{'─' * 78}┤{Colors.RESET}")

    for i, file_info in enumerate(backup_files, 1):
        name = file_info.get("name", "Unknown")
        modified_time = file_info.get("modifiedTime", "Unknown")
        size = file_info.get("size", "Unknown")
        file_id = file_info.get("id", "")

        # Format the size in a readable way
        size_str = format_file_size(size)

        print(f"{Colors.GREEN}{i:2d}.{Colors.RESET} {name}")
        print(
            f"    {Colors.YELLOW}Modified:{Colors.RESET} {modified_time} {Colors.CYAN}|{Colors.RESET} {Colors.YELLOW}Size:{Colors.RESET} {size_str}"
        )
        print(
            f"    {Colors.YELLOW}File ID:{Colors.RESET} {file_id[:8]}...{file_id[-4:] if len(file_id) > FILE_ID_DISPLAY_THRESHOLD else file_id}"
        )

    print(f"{Colors.CYAN}└{'─' * 78}┘{Colors.RESET}")


def select_backup_by_index(
    backup_files: list[BackupFileInfo], index: int
) -> str | None:
    """
    Select a backup by index without interactive prompts.

    Args:
        backup_files: List of backup file metadata
        index: Zero-based index of backup to select

    Returns:
        Selected file ID or None if index is invalid
    """
    if 0 <= index < len(backup_files):
        selected = backup_files[index]
        file_id = selected.get("id")
        name = selected.get("name", "Unknown")
        logger.info(f"Selected backup by index: {name} (ID: {file_id})")
        return file_id
    else:
        logger.error(
            f"Invalid backup index: {index}. Available backups: {len(backup_files)}"
        )
        return None
