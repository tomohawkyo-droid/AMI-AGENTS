#!/usr/bin/env python3

import sys

from ami.cli_components.cursor_manager import CursorManager
from ami.cli_components.editor_display import EditorDisplay
from ami.cli_components.text_input_utils import (
    BRACKETED_PASTE_DISABLE,
    BRACKETED_PASTE_ENABLE,
    Colors,
    read_key_sequence,
)


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

    def handle_key_navigation(self, key: str) -> None:
        """Handle all cursor navigation keys."""
        if key == "UP":
            self.cursor_manager.move_cursor_up()
        elif key == "DOWN":
            self.cursor_manager.move_cursor_down()
        elif key == "LEFT":
            self.cursor_manager.move_cursor_left()
        elif key == "RIGHT":
            self.cursor_manager.move_cursor_right()
        elif key == "CTRL_LEFT":  # Ctrl+Left - move to previous word
            self.cursor_manager.move_to_previous_word()
        elif key == "CTRL_RIGHT":  # Ctrl+Right - move to next word
            self.cursor_manager.move_to_next_word()
        elif key == "CTRL_UP":  # Ctrl+Up - move to previous paragraph (empty line)
            self.cursor_manager.move_to_previous_paragraph()
        elif key == "CTRL_DOWN":  # Ctrl+Down - move to next paragraph (empty line)
            self.cursor_manager.move_to_next_paragraph()

    def process_enter_key(self) -> None:
        """Process the Enter key by splitting the current line."""
        # Split the current line at the cursor position
        current_line_content = self.lines[self.cursor_manager.current_line]
        before_cursor = current_line_content[: self.cursor_manager.current_col]
        after_cursor = current_line_content[self.cursor_manager.current_col :]

        # Update current line and insert new line
        self.lines[self.cursor_manager.current_line] = before_cursor
        self.lines.insert(self.cursor_manager.current_line + 1, after_cursor)

        # Move to the new line
        self.cursor_manager.current_line += 1
        self.cursor_manager.current_col = 0

    def process_backspace_key(self) -> None:
        """Process the Backspace key by deleting character or joining lines."""
        if self.cursor_manager.current_col > 0:
            # Delete character before cursor
            current_line_content = self.lines[self.cursor_manager.current_line]
            before_cursor = current_line_content[: self.cursor_manager.current_col - 1]
            after_cursor = current_line_content[self.cursor_manager.current_col :]
            self.lines[self.cursor_manager.current_line] = before_cursor + after_cursor
            self.cursor_manager.current_col -= 1
        elif self.cursor_manager.current_line > 0:
            # Join with previous line
            prev_line = self.lines[self.cursor_manager.current_line - 1]
            current_line_content = self.lines[self.cursor_manager.current_line]

            # Remember where the cursor should go (end of prev_line before joining)
            new_col = len(prev_line)

            # Combine lines
            self.lines[self.cursor_manager.current_line - 1] = (
                prev_line + current_line_content
            )

            # Remove current line
            del self.lines[self.cursor_manager.current_line]

            # Move to previous line and set column to the join point
            self.cursor_manager.current_line -= 1
            self.cursor_manager.current_col = new_col

    def process_home_key(self) -> None:
        """Process the Home key (Ctrl+A) to move cursor to beginning of line."""
        # Ctrl+A pressed - go to beginning of current line
        self.cursor_manager.current_col = 0

    def process_delete_word(self) -> None:
        """Process Ctrl+W or Ctrl+Backspace to delete the word before the cursor."""
        current_line_content = self.lines[self.cursor_manager.current_line]

        # Find the start of the word to delete
        start_pos = self.cursor_manager.current_col
        pos = start_pos

        # Skip any whitespace before the cursor
        while pos > 0 and current_line_content[pos - 1].isspace():
            pos -= 1

        # Delete backward until we hit a word boundary (whitespace or beginning of line)
        word_start = pos
        while word_start > 0 and not current_line_content[word_start - 1].isspace():
            word_start -= 1

        # If we're deleting something
        if word_start < start_pos:
            # Remove the characters from word_start to start_pos
            before_word = current_line_content[:word_start]
            after_word = current_line_content[start_pos:]
            self.lines[self.cursor_manager.current_line] = before_word + after_word

            # Move cursor to the start of the deleted word
            self.cursor_manager.current_col = word_start

    def _insert_pasted_content(self, content: str) -> None:
        """Insert pasted content into the editor, handling newlines properly."""
        if not content:
            return  # Nothing to insert

        # Split the pasted content by newlines
        lines = content.split("\n")

        if len(lines) == 1:
            # Single-line paste - insert at cursor position
            current_line_content = self.lines[self.cursor_manager.current_line]
            before_cursor = current_line_content[: self.cursor_manager.current_col]
            after_cursor = current_line_content[self.cursor_manager.current_col :]

            self.lines[self.cursor_manager.current_line] = (
                before_cursor + content + after_cursor
            )
            self.cursor_manager.current_col += len(content)
        else:
            # Multi-line paste - split the current line and insert multiple lines
            current_line_content = self.lines[self.cursor_manager.current_line]
            before_cursor = current_line_content[: self.cursor_manager.current_col]
            after_cursor = current_line_content[self.cursor_manager.current_col :]

            # First line goes at current position (combine with text before cursor)
            first_line = before_cursor + lines[0]
            self.lines[self.cursor_manager.current_line] = first_line

            # Middle lines (if any) are inserted as new lines
            min_lines_for_middle = 2
            middle_lines = lines[1:-1] if len(lines) > min_lines_for_middle else []
            for i, line in enumerate(middle_lines):
                insert_pos = self.cursor_manager.current_line + i + 1
                self.lines.insert(insert_pos, line)

            # Last line is combined with text after cursor
            last_line = lines[-1] + after_cursor
            insert_pos = self.cursor_manager.current_line + len(middle_lines) + 1
            self.lines.insert(insert_pos, last_line)

            # Update cursor position: move to end of the last inserted line
            self.cursor_manager.current_line = insert_pos
            self.cursor_manager.current_col = len(lines[-1])

    def handle_text_modification(self, key: str) -> None:
        """Handle text modification keys (enter, backspace, etc)."""
        if key == "ENTER":
            self.process_enter_key()
        elif key == "BACKSPACE":
            self.process_backspace_key()
        elif key == "HOME":
            self.process_home_key()
        elif key in ["DELETE_WORD", "BACKSPACE_WORD"]:
            self.process_delete_word()

    def run(self, clear_on_submit: bool = True) -> str | None:
        """Run the main editor loop."""
        display = EditorDisplay()

        # Enable bracketed paste mode
        sys.stdout.write(BRACKETED_PASTE_ENABLE)
        sys.stdout.flush()

        # Initial display
        display.display_editor(
            self.lines,
            self.cursor_manager.current_line,
            self.cursor_manager.current_col,
        )

        try:
            while True:
                try:
                    # Get the next key sequence
                    key = read_key_sequence()

                    if key is None:
                        continue

                    # Any key press resets the Ctrl+C counter
                    # (another Ctrl+C raises exception)
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
                        self.ctrl_c_pressed_count = (
                            0  # Reset count so next Ctrl+C triggers the warning
                        )
                        # Re-render with cleared content
                        display.display_editor(self.lines, 0, 0)
                        continue

                    if self.ctrl_c_pressed_count == 0:
                        self.ctrl_c_pressed_count = 1
                        # Re-render with warning status
                        warn = f"{Colors.RED}Ctrl+C again to quit{Colors.RESET}"
                        display.display_editor(self.lines, 0, 0, status_override=warn)
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

    def _process_key(self, key: str, display: EditorDisplay) -> bool:
        """Process a key from the input and return whether to exit."""
        # Handle paste mode
        if self.in_paste_mode:
            return self._process_paste_mode_key(key, display)
        return self._process_normal_mode_key(key, display)

    def _process_paste_mode_key(self, key: str, display: EditorDisplay) -> bool:
        """Process a key while in paste mode."""
        # If we get paste end sequence, exit paste mode and process the content
        if key in ["PASTE_END", "PASTE_END_ALT"]:
            # Insert the accumulated paste buffer content
            self._insert_pasted_content(self.paste_buffer)
            # Reset paste mode
            self.paste_buffer = ""
            self.in_paste_mode = False
            # Redraw the editor after inserting pasted content
            display.display_editor(
                self.lines,
                self.cursor_manager.current_line,
                self.cursor_manager.current_col,
            )
        # In paste mode, accumulate characters in paste buffer
        # Convert "ENTER" back to newline character during paste mode
        elif key == "ENTER":
            self.paste_buffer += "\n"
        elif isinstance(key, str):
            self.paste_buffer += key
            # Don't redraw during paste accumulation to avoid flickering

        return False  # Don't exit

    def _process_normal_mode_key(self, key: str, display: EditorDisplay) -> bool:
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
            "BACKSPACE",
            "SUBMIT",
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

    def _handle_navigation_command_keys(self, key: str, display: EditorDisplay) -> bool:
        """Handle navigation and command key inputs."""
        if key == "ENTER":
            # Enter now sends the message
            return True

        if key == "SUBMIT":
            # Ctrl+S also sends the message
            return True

        if key == "ALT_ENTER":
            # Alt+Enter adds a newline
            self.process_enter_key()
        elif key == "F1":
            # Toggle help display
            display.show_help = not display.show_help
        elif key in [
            "UP",
            "DOWN",
            "LEFT",
            "RIGHT",
            "CTRL_UP",
            "CTRL_DOWN",
            "CTRL_LEFT",
            "CTRL_RIGHT",
        ]:
            self.handle_key_navigation(key)
        else:  # Other text modification keys
            self.handle_text_modification(key)

        # Redraw the editor by reprinting the entire interface
        display.display_editor(
            self.lines,
            self.cursor_manager.current_line,
            self.cursor_manager.current_col,
        )
        return False  # Don't exit

    def _handle_character_input(self, key: str, display: EditorDisplay) -> bool:
        """Handle single character input."""
        # Single character input (or other string)
        if len(key) == 1:
            current_line_content = self.lines[self.cursor_manager.current_line]

            # Insert character at cursor position
            before_cursor = current_line_content[: self.cursor_manager.current_col]
            after_cursor = current_line_content[self.cursor_manager.current_col :]

            self.lines[self.cursor_manager.current_line] = (
                before_cursor + key + after_cursor
            )
            self.cursor_manager.current_col += 1

            # Redraw the editor by reprinting the entire interface
            display.display_editor(
                self.lines,
                self.cursor_manager.current_line,
                self.cursor_manager.current_col,
            )
        else:
            # Some other string - treat as special key (shouldn't happen)
            # For safety, treat as regular input if not handled elsewhere
            pass

        return False  # Don't exit
