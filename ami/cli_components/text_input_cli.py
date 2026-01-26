#!/usr/bin/env python3

import sys
from typing import Any

from ami.cli_components.text_editor import TextEditor

"""
Simple in-line text input with borders that preserves terminal scrollability.
Arrow keys for navigation, Ctrl+D to save and exit.
"""


def create_text_editor(initial_text: str = "") -> Any:
    """Create a text input that supports arrow key navigation."""
    editor = TextEditor(initial_text)
    # Clear on submit to behave like a transient input tool
    return editor.run(clear_on_submit=True)


def main() -> None:
    """Main function to run the text editor."""
    # Accept command line arguments as initial text
    initial_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    result = create_text_editor(initial_text)

    if result is not None:
        print(result)


if __name__ == "__main__":
    main()
