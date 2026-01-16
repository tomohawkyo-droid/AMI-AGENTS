#!/usr/bin/env python3

import sys
from typing import Any

from ami.cli_components.cursor_manager import CursorManager
from ami.cli_components.editor_display import EditorDisplay
from ami.cli_components.text_input_utils import BRACKETED_PASTE_DISABLE, BRACKETED_PASTE_ENABLE, read_key_sequence


class TextEditor:
    """A class to manage the text editor functionality."""

    def __init__(self, initial_text: str = "") -> None:
        self.lines: list[str] = initial_text.split("\n") if initial_text else [""]
        self.cursor_manager = CursorManager(self.lines)
        # Paste mode state management
        self.in_paste_mode = False
        self.paste_buffer = ""
        # Ctrl+C state management
        self.ctrl_c_pressed_count = 0

    # ... (handlers remain same) ...

    def run(self, clear_on_submit: bool = True) -> str | None:
        """Run the main editor loop."""
        display = EditorDisplay()

        # Enable bracketed paste mode
        sys.stdout.write(BRACKETED_PASTE_ENABLE)
        sys.stdout.flush()

        # Initial display
        display.display_editor(self.lines, self.cursor_manager.current_line, self.cursor_manager.current_col)

        try:
            while True:
                status_override = None
                if self.ctrl_c_pressed_count > 0:
                    status_override = f"{Colors.RED}Press Ctrl+C again to quit{Colors.RESET}"

                try:
                    # Get the next key sequence
                    key = read_key_sequence()

                    if key is None:
                        continue

                    # Any key press resets the Ctrl+C counter (unless it's another Ctrl+C which raises exception)
                    self.ctrl_c_pressed_count = 0
                    
                    # Process the key
                    if isinstance(key, str):
                        should_exit = self._process_key(key, display)
                        if should_exit:
                            break
                
                except KeyboardInterrupt:
                    # Handle Ctrl+C logic
                    has_content = any(line for line in self.lines)
                    
                    if has_content:
                        # Clear content
                        self.lines = [""]
                        self.cursor_manager = CursorManager(self.lines)
                        self.ctrl_c_pressed_count = 0 # Reset count so next Ctrl+C triggers the warning
                        # Re-render with cleared content
                        display.display_editor(self.lines, 0, 0)
                        continue
                    
                    if self.ctrl_c_pressed_count == 0:
                        self.ctrl_c_pressed_count = 1
                        # Re-render with warning status
                        display.display_editor(self.lines, 0, 0, status_override=f"{Colors.RED}Press Ctrl+C again to quit{Colors.RESET}")
                        continue
                    
                    # Second Ctrl+C with empty content -> Exit
                    display.clear()
                    return None

        finally:
            # Disable bracketed paste mode before exiting
            sys.stdout.write(BRACKETED_PASTE_DISABLE)
            sys.stdout.flush()

        if clear_on_submit:
            display.clear()

        return "\n".join(self.lines)

    def _process_key(self, key: str, display: Any) -> bool:
        """Process a key from the input and return whether to exit."""
        # Handle paste mode
        if self.in_paste_mode:
            return self._process_paste_mode_key(key, display)
        return self._process_normal_mode_key(key, display)

    def _process_paste_mode_key(self, key: str, display: Any) -> bool:
        """Process a key while in paste mode."""
        # If we get paste end sequence, exit paste mode and process the content
        if key in ["PASTE_END", "PASTE_END_ALT"]:
            # Insert the accumulated paste buffer content
            self._insert_pasted_content(self.paste_buffer)
            # Reset paste mode
            self.paste_buffer = ""
            self.in_paste_mode = False
            # Redraw the editor after inserting pasted content
            display.display_editor(self.lines, self.cursor_manager.current_line, self.cursor_manager.current_col)
        # In paste mode, accumulate characters in paste buffer
        # Convert "ENTER" back to newline character during paste mode
        elif key == "ENTER":
            self.paste_buffer += "\n"
        elif isinstance(key, str):
            self.paste_buffer += key
            # Don't redraw during paste accumulation to avoid flickering

        return False  # Don't exit

    def _process_normal_mode_key(self, key: str, display: Any) -> bool:
        """Process a key while in normal mode."""
        # Check for paste start sequences
        if key in ["PASTE_START", "PASTE_START_ALT"]:
            self.in_paste_mode = True
            self.paste_buffer = ""
            # Don't process as regular input
            return False

        # Handle navigation and command keys
        if key in [
            "UP",
            "DOWN",
            "LEFT",
            "RIGHT",
            "ENTER",
            "ALT_ENTER",
            "CTRL_ENTER",
            "BACKSPACE",
            "EOF",
            "HOME",
            "DELETE_WORD",
            "BACKSPACE_WORD",
            "CTRL_UP",
            "CTRL_DOWN",
            "CTRL_LEFT",
            "CTRL_RIGHT",
            "F1",
        ]:
            return self._handle_navigation_command_keys(key, display)
        # Handle single character input
        return self._handle_character_input(key, display)

    def _handle_navigation_command_keys(self, key: str, display: Any) -> bool:
        """Handle navigation and command key inputs."""
        if key == "ENTER":
             # Enter now sends the message
             return True
        
        if key == "EOF":
            # Ctrl+S still works as send for compatibility
            return True

        if key in ["ALT_ENTER", "CTRL_ENTER"]:
            # Alt+Enter or Ctrl+Enter adds a newline
            self.process_enter_key()
        elif key == "F1":
            # Toggle help display
            display.show_help = not getattr(display, "show_help", False)
        elif key in ["UP", "DOWN", "LEFT", "RIGHT", "CTRL_UP", "CTRL_DOWN", "CTRL_LEFT", "CTRL_RIGHT"]:
            self.handle_key_navigation(key)
        else:  # Other text modification keys
            self.handle_text_modification(key)

        # Redraw the editor by reprinting the entire interface
        display.display_editor(self.lines, self.cursor_manager.current_line, self.cursor_manager.current_col)
        return False  # Don't exit

    def _handle_character_input(self, key: str, display: Any) -> bool:
        """Handle single character input."""
        # Single character input (or other string)
        if len(key) == 1:
            current_line_content = self.lines[self.cursor_manager.current_line]

            # Insert character at cursor position
            before_cursor = current_line_content[: self.cursor_manager.current_col]
            after_cursor = current_line_content[self.cursor_manager.current_col :]

            self.lines[self.cursor_manager.current_line] = before_cursor + key + after_cursor
            self.cursor_manager.current_col += 1

            # Redraw the editor by reprinting the entire interface
            display.display_editor(self.lines, self.cursor_manager.current_line, self.cursor_manager.current_col)
        else:
            # Some other string - treat as special key (shouldn't happen with our new handling)
            # For safety, we'll treat as regular input if not handled elsewhere
            pass

        return False  # Don't exit
