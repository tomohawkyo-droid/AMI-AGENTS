"""
Confirmation dialog proxy.
DEPRECATED: Use ami.cli_components.dialogs instead.
"""

from ami.cli_components.dialogs import ConfirmationDialog as _CD
from ami.cli_components.dialogs import confirm as _confirm

# Re-export from dialogs module
ConfirmationDialog = _CD
confirm = _confirm

if __name__ == "__main__":
    if confirm("Do you really want to delete all files?", "Dangerous Operation"):
        print("\nDeleting files...")
    else:
        print("\nOperation cancelled.")
