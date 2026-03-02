"""
Common ASCII dialog components for CLI interactions.
"""

from ami.cli_components.keys import ENTER, ESC, LEFT, RIGHT
from ami.cli_components.selection_dialog import (
    DialogItem,
    SelectableItem,
    SelectableItemDict,
    SelectionDialog,
    SelectionDialogConfig,
)
from ami.cli_components.terminal.ansi import AnsiTerminal
from ami.cli_components.text_input_utils import Colors, read_key_sequence
from ami.cli_components.tui import TUI, BoxStyle, strip_ansi, visible_len

# Type alias for selectable items union
SelectableUnion = SelectableItem | SelectableItemDict

# Constants for rendering
DEFAULT_DIALOG_WIDTH = 80


class BaseDialog:
    """Base class for dialogs."""

    def __init__(self, title: str = "Dialog", width: int = 80):
        self.title = title
        self.width = width
        self._last_render_lines = 0

    def clear(self) -> None:
        """Clear the dialog from screen."""
        TUI.clear_lines(self._last_render_lines)
        self._last_render_lines = 0

    def render(self) -> None:
        """Render the dialog. Must update self._last_render_lines."""
        raise NotImplementedError

    def _format_shortcut(self, label: str, shortcut: str, selected: bool) -> str:
        """Format label with shortcut underlined or appended."""
        lower_label = label.lower()
        lower_shortcut = shortcut.lower()

        # Find shortcut in label
        idx = lower_label.find(lower_shortcut)

        style = f"{Colors.REVERSE}" if selected else ""
        reset = f"{Colors.RESET}"
        underline = AnsiTerminal.UNDERLINE
        no_underline = "\033[24m"  # SGR 24 — no dedicated constant needed

        if idx != -1:
            # Underline the char in label
            prefix = label[:idx]
            char = label[idx]
            suffix = label[idx + 1 :]
            formatted = f"{style}{prefix}{underline}{char}{no_underline}{suffix}{reset}"
        else:
            # Append shortcut
            formatted = f"{style}{label} ({underline}{shortcut}{no_underline}){reset}"

        return formatted


class AlertDialog(BaseDialog):
    """Simple alert/message dialog."""

    def __init__(self, message: str, title: str = "Alert", width: int = 80):
        super().__init__(title, width)
        self.message = message

    def show(self) -> None:
        """Show the alert and wait for Enter."""
        try:
            self._render()
            while True:
                key = read_key_sequence()
                if key in (ENTER, ESC):
                    break
        finally:
            # We usually leave alerts on screen or clear?
            # Interactive apps usually clear dialogs.
            self.clear()

    def _render(self) -> None:
        self.clear()
        # Wrap text
        inner_width = self.width - 4
        lines = TUI.wrap_text(self.message, inner_width)

        # Center lines manually because TUI.draw_box is simple
        centered_lines = [line.center(inner_width) for line in lines]

        # Add button
        button = f"{Colors.REVERSE}  OK  {Colors.RESET}"
        # Pad lines with blank
        content = [
            *centered_lines,
            "",
            button.center(inner_width + len(Colors.REVERSE) + len(Colors.RESET)),
        ]

        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=f"{Colors.GREEN}Press Enter to continue{Colors.RESET}",
            style=BoxStyle(width=self.width, center_content=False),
        )


class ConfirmationDialog(BaseDialog):
    """Yes/No confirmation dialog."""

    def __init__(self, message: str, title: str = "Confirmation", width: int = 80):
        super().__init__(title, width)
        self.message = message
        self.selected_yes = True

    def run(self) -> bool:
        """Run loop. Returns True (Yes) or False (No)."""
        try:
            while True:
                self._render()
                key = read_key_sequence()

                if key in (LEFT, RIGHT):
                    self.selected_yes = not self.selected_yes
                elif key in ["y", "Y"]:
                    self.selected_yes = True
                    return True
                elif key in ["n", "N"]:
                    self.selected_yes = False
                    return False
                elif key == ENTER:
                    return self.selected_yes
                elif key == ESC:
                    return False
        except KeyboardInterrupt:
            return False
        finally:
            self.clear()

    def _render(self) -> None:
        self.clear()
        inner_width = self.width - 4
        lines = TUI.wrap_text(self.message, inner_width)
        centered_lines = [line.center(inner_width) for line in lines]

        # Buttons with shortcuts
        yes_disp = self._format_shortcut("  Yes  ", "Y", self.selected_yes)
        no_disp = self._format_shortcut("  No   ", "N", not self.selected_yes)

        # Calculate spacing
        # Just simple spacing:  [Yes]      [No]
        # We need raw length for centering logic
        raw_yes = "  Yes  "
        raw_no = "  No   "

        buttons_raw_len = len(raw_yes) + 6 + len(raw_no)
        pad_len = (inner_width - buttons_raw_len) // 2

        # Construct line with colors
        # Note: Padding calculation relies on ANSI codes NOT being counted in raw length
        # TUI.draw_box handles basic color codes but sophisticated cursor positioning
        # might drift if we aren't careful
        # But here we construct a single string line

        buttons_line = " " * pad_len + yes_disp + "      " + no_disp
        # Pad right side to fill line so box border aligns
        current_len = pad_len + buttons_raw_len
        buttons_line += " " * (inner_width - current_len)

        content = [*centered_lines, "", buttons_line]

        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=f"{Colors.GREEN}Use ←/→ to navigate, y/n shortcuts{Colors.RESET}",
            style=BoxStyle(width=self.width, center_content=False),
        )


# Facade functions
def confirm(message: str, title: str = "Confirmation") -> bool:
    return ConfirmationDialog(message, title).run()


def alert(message: str, title: str = "Alert") -> None:
    AlertDialog(message, title).show()


def select(
    items: list[DialogItem], title: str = "Select Option"
) -> SelectableItem | SelectableItemDict | None:
    """Select single item. Returns item or None."""
    config = SelectionDialogConfig(title=title, multi=False)
    result = SelectionDialog(items, config).run()
    # In single-select mode, result is either a single item or None
    if result is None:
        return None
    if isinstance(result, list):
        return result[0] if result else None
    return result


def multiselect(
    items: list[DialogItem],
    title: str = "Select Options",
    preselected: set[str] | None = None,
    skippable_ids: set[str] | None = None,
    max_height: int = 15,
) -> list[SelectableUnion]:
    """Select multiple items. Returns list of items or empty list if cancelled.

    Args:
        items: List of items to select from
        title: Dialog title
        preselected: Set of item IDs to pre-select
        skippable_ids: Set of item IDs that can be skipped (installed components)
        max_height: Maximum visible items before scrolling
    """
    config = SelectionDialogConfig(
        title=title,
        multi=True,
        preselected=preselected or set(),
        skippable_ids=skippable_ids or set(),
        max_height=max_height,
    )
    result = SelectionDialog(items, config).run()
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


# Public API exports
__all__ = [
    "AlertDialog",
    "BaseDialog",
    "ConfirmationDialog",
    "SelectionDialog",
    "SelectionDialogConfig",
    "alert",
    "confirm",
    "multiselect",
    "select",
    "strip_ansi",
    "visible_len",
]
