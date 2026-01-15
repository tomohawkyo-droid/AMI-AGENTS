"""
Confirmation dialog proxy.
DEPRECATED: Use agents.ami.cli_components.dialogs instead.
"""

from agents.ami.cli_components.dialogs import confirm as _confirm, ConfirmationDialog as _CD

# Re-export for compatibility
ConfirmationDialog = _CD
confirm = _confirm

if __name__ == "__main__":
    if confirm("Do you really want to delete all files?", "Dangerous Operation"):
        print("\nDeleting files...")
    else:
        print("\nOperation cancelled.")
