"""Interactive backup selector for restore operations."""

from ami.scripts.backup.restore.drive_client import DriveFileMetadata


def select_backup_interactive(backup_files: list[DriveFileMetadata]) -> str | None:
    """Interactively select a backup file from the list.

    Args:
        backup_files: List of backup file metadata dicts with 'id', 'name', 'modifiedTime', 'size'

    Returns:
        The file ID of the selected backup, or None if cancelled
    """
    if not backup_files:
        return None

    print("\nAvailable backups:")
    print("-" * 80)

    for i, file_info in enumerate(backup_files):
        name = file_info.get("name", "Unknown")
        modified = file_info.get("modifiedTime", "Unknown")[:19]
        size = file_info.get("size", "?")
        print(f"  [{i}] {name}")
        print(f"      Modified: {modified}  Size: {size}")

    print("-" * 80)
    print("Enter number to select, or 'q' to cancel:")

    while True:
        try:
            choice = input("> ").strip()
            if choice.lower() == "q":
                return None
            idx = int(choice)
            if 0 <= idx < len(backup_files):
                return backup_files[idx].get("id")
            print(f"Invalid selection. Enter 0-{len(backup_files) - 1} or 'q'")
        except ValueError:
            print("Invalid input. Enter a number or 'q'")
        except (KeyboardInterrupt, EOFError):
            return None
