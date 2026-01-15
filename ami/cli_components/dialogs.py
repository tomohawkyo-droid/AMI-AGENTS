"""
Common ASCII dialog components for CLI interactions.
"""

import sys
from typing import List, Optional, Any, Union

from agents.ami.cli_components.text_input_utils import read_key_sequence, Colors
from agents.ami.cli_components.tui import TUI

# Key constants
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
ENTER = "ENTER"
ESC = "ESC"


class BaseDialog:
    """Base class for dialogs."""
    
    def __init__(self, title: str = "Dialog", width: int = 60):
        self.title = title
        self.width = width
        self._last_render_lines = 0

    def clear(self):
        """Clear the dialog from screen."""
        TUI.clear_lines(self._last_render_lines)
        self._last_render_lines = 0

    def render(self):
        """Render the dialog. Must update self._last_render_lines."""
        raise NotImplementedError


class AlertDialog(BaseDialog):
    """Simple alert/message dialog."""
    
    def __init__(self, message: str, title: str = "Alert", width: int = 60):
        super().__init__(title, width)
        self.message = message
        
    def show(self):
        """Show the alert and wait for Enter."""
        try:
            self._render()
            while True:
                key = read_key_sequence()
                if key == ENTER or key == ESC:
                    break
        finally:
            # We usually leave alerts on screen or clear? 
            # Interactive apps usually clear dialogs.
            self.clear()

    def _render(self):
        # Wrap text
        inner_width = self.width - 4
        lines = TUI.wrap_text(self.message, inner_width)
        
        # Center lines manually because TUI.draw_box is simple
        centered_lines = [line.center(inner_width) for line in lines]
        
        # Add button
        button = f"{Colors.REVERSE}  OK  {Colors.RESET}"
        # Pad lines with blank
        content = centered_lines + ["", button.center(inner_width + len(Colors.REVERSE) + len(Colors.RESET))]
        
        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=f"{Colors.GREEN}Press Enter to continue{Colors.RESET}",
            width=self.width,
            center_content=False # We centered manually
        )


class ConfirmationDialog(BaseDialog):
    """Yes/No confirmation dialog."""
    
    def __init__(self, message: str, title: str = "Confirmation", width: int = 60):
        super().__init__(title, width)
        self.message = message
        self.selected_yes = True
        
    def run(self) -> bool:
        """Run loop. Returns True (Yes) or False (No)."""
        try:
            while True:
                self._render()
                key = read_key_sequence()
                
                if key == LEFT or key == RIGHT:
                    self.selected_yes = not self.selected_yes
                elif key in ["y", "Y"]:
                    self.selected_yes = True
                    self._render()
                    return True
                elif key in ["n", "N"]:
                    self.selected_yes = False
                    self._render()
                    return False
                elif key == ENTER:
                    return self.selected_yes
                elif key == ESC:
                    return False
        except KeyboardInterrupt:
            return False
        finally:
            self.clear()

    def _render(self):
        inner_width = self.width - 4
        lines = TUI.wrap_text(self.message, inner_width)
        centered_lines = [line.center(inner_width) for line in lines]
        
        # Buttons
        yes_btn = "  Yes  "
        no_btn = "  No   "
        
        if self.selected_yes:
            y_disp = f"{Colors.REVERSE}{yes_btn}{Colors.RESET}"
            n_disp = no_btn
        else:
            y_disp = yes_btn
            n_disp = f"{Colors.REVERSE}{no_btn}{Colors.RESET}"
            
        # Calculate spacing
        # Just simple spacing:  [Yes]      [No]
        # Total raw width = len(yes_btn) + 6 + len(no_btn)
        # Center this block
        
        buttons_raw = f"{yes_btn}      {no_btn}"
        pad_len = (inner_width - len(buttons_raw)) // 2
        
        # Construct line with colors
        buttons_line = " " * pad_len + y_disp + "      " + n_disp
        # Pad right side to fill line so box border aligns
        # Use existing length of buttons_raw for calc
        current_len = pad_len + len(buttons_raw)
        buttons_line += " " * (inner_width - current_len)
        
        content = centered_lines + ["", buttons_line]
        
        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=f"{Colors.GREEN}Use ←/→ to navigate, Enter to confirm{Colors.RESET}",
            width=self.width,
            center_content=False
        )


class SelectionDialog(BaseDialog):
    """Menu selection dialog."""
    
    def __init__(self, items: List[Any], title: str = "Select", width: int = 60, multi: bool = False):
        super().__init__(title, width)
        # Handle string items or objects with labels
        self.items = []
        for item in items:
            if isinstance(item, str):
                self.items.append({"label": item, "value": item})
            else:
                # Assume object has label/value or dict
                if hasattr(item, "label"):
                    self.items.append(item)
                elif isinstance(item, dict) and "label" in item:
                    self.items.append(item)
                else:
                    self.items.append({"label": str(item), "value": item})
                    
        self.multi = multi
        self.cursor = 0
        self.selected = set()
        self.scroll_offset = 0
        self.max_height = 10

    def run(self) -> Union[Any, List[Any], None]:
        """Run loop. Returns selected value(s) or None."""
        try:
            while True:
                self._render()
                key = read_key_sequence()
                
                if key == UP:
                    if self.cursor > 0:
                        self.cursor -= 1
                        self._scroll_up()
                elif key == DOWN:
                    if self.cursor < len(self.items) - 1:
                        self.cursor += 1
                        self._scroll_down()
                elif key == " " and self.multi:
                    if self.cursor in self.selected:
                        self.selected.remove(self.cursor)
                    else:
                        self.selected.add(self.cursor)
                elif key == ENTER:
                    if self.multi:
                        return [self.items[i] for i in sorted(self.selected)]
                    else:
                        return self.items[self.cursor]
                elif key == ESC:
                    return None
        except KeyboardInterrupt:
            return None
        finally:
            self.clear()

    def _scroll_up(self):
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor

    def _scroll_down(self):
        if self.cursor >= self.scroll_offset + self.max_height:
            self.scroll_offset = self.cursor - self.max_height + 1

    def _render(self):
        content = []
        
        visible_items = self.items[self.scroll_offset : self.scroll_offset + self.max_height]
        
        for idx, item in enumerate(visible_items):
            real_idx = self.scroll_offset + idx
            is_cursor = (real_idx == self.cursor)
            
            label = item.label if hasattr(item, "label") else item["label"]
            desc = ""
            if hasattr(item, "description") and item.description:
                desc = f" - {Colors.YELLOW}{item.description}{Colors.RESET}"
            elif isinstance(item, dict) and "description" in item and item["description"]:
                desc = f" - {Colors.YELLOW}{item['description']}{Colors.RESET}"
            
            # Format: "> [x] Label - Description"
            prefix = ""
            if is_cursor:
                prefix += f"{Colors.BOLD}{Colors.REVERSE}>{Colors.RESET} "
            else:
                prefix += "  "
                
            if self.multi:
                if real_idx in self.selected:
                    prefix += f"{Colors.GREEN}[x]{Colors.RESET} "
                else:
                    prefix += "[ ] "
            else:
                # Single select, just show label, maybe highlight if selected? 
                # Just highlight cursor line
                pass
                
            # Truncate label to fit
            # Width - 4 (box padding) - len(prefix_stripped)
            # Prefix len is roughly 4 chars visible
            # Note: We aren't calculating exact visible width of prefix/desc with colors stripped here
            # Ideally we would but for now we approximate.
            
            line_str = f"{prefix}{label}{desc}"
            content.append(line_str)
            
        # Footer
        instr = "↑/↓: navigate"
        if self.multi:
            instr += ", Space: select"
        instr += ", Enter: confirm, Esc: cancel"
        
        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=f"{Colors.GREEN}{instr}{Colors.RESET}",
            width=self.width,
            center_content=False
        )


# Facade functions
def confirm(message: str, title: str = "Confirmation") -> bool:
    return ConfirmationDialog(message, title).run()

def alert(message: str, title: str = "Alert") -> None:
    AlertDialog(message, title).show()

def select(items: List[Any], title: str = "Select Option") -> Any:
    """Select single item. Returns item or None."""
    return SelectionDialog(items, title, multi=False).run()

def multiselect(items: List[Any], title: str = "Select Options") -> List[Any]:
    """Select multiple items. Returns list of items or None."""
    return SelectionDialog(items, title, multi=True).run()
