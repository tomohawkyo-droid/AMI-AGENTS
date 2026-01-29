"""
Selection dialog for CLI menu selection with hierarchical group support.
"""

from typing import Protocol, TypedDict, cast, runtime_checkable

from ami.cli_components.text_input_utils import Colors, read_key_sequence
from ami.cli_components.tui import TUI, BoxStyle
from ami.types.results import FormattedPrefix, GroupRange, KeyHandleResult


@runtime_checkable
class SelectableItem(Protocol):
    """Protocol for objects that can be used as selection dialog items."""

    id: str
    label: str
    description: str
    is_header: bool
    value: str | object


class SelectableItemDict(TypedDict, total=False):
    """TypedDict for dict-based selection items."""

    id: str
    label: str
    description: str
    is_header: bool
    value: str | object


# Type alias for selectable items union (without str for internal use)
SelectableUnion = SelectableItem | SelectableItemDict

# Union type for all valid item formats
DialogItem = SelectableItem | SelectableItemDict | str

# Constants for rendering
DEFAULT_DIALOG_WIDTH = 80
DEFAULT_MAX_HEIGHT = 10
TRUNCATION_SUFFIX = "..."
INDENT_CHILD = "   "

# Key constants
UP = "UP"
DOWN = "DOWN"
ENTER = "ENTER"
ESC = "ESC"


class SelectionDialogConfig:
    """Configuration for SelectionDialog to reduce argument count."""

    def __init__(
        self,
        title: str = "Select",
        width: int = DEFAULT_DIALOG_WIDTH,
        multi: bool = False,
        max_height: int = DEFAULT_MAX_HEIGHT,
        preselected: set[str] | None = None,
    ):
        self.title = title
        self.width = width
        self.multi = multi
        self.max_height = max_height
        self.preselected: set[str] = preselected or set()


class SelectionDialog:
    """Menu selection dialog with hierarchical group support."""

    def __init__(
        self,
        items: list[DialogItem],
        config: SelectionDialogConfig | None = None,
    ):
        config = config or SelectionDialogConfig()
        self.title = config.title
        self.width = config.width
        self._last_render_lines = 0

        self.items: list[SelectableUnion] = []
        self.group_ranges: list[GroupRange] = []
        self._preselected_ids = config.preselected

        self._process_items(items)
        self._build_group_ranges()

        self.multi = config.multi
        self.cursor = 0
        self.scroll_offset = 0
        self.max_height = config.max_height

        self.selected: set[int] = set()
        self._initialize_preselected()

    def clear(self) -> None:
        """Clear the dialog from screen."""
        TUI.clear_lines(self._last_render_lines)
        self._last_render_lines = 0

    def _process_items(self, items: list[DialogItem]) -> None:
        """Normalize items to consistent dict format."""
        for item in items:
            if isinstance(item, str):
                self.items.append({"label": item, "value": item, "is_header": False})
            elif isinstance(item, SelectableItem) or (
                isinstance(item, dict) and "label" in item
            ):
                self.items.append(item)
            else:
                self.items.append(
                    {"label": str(item), "value": item, "is_header": False}
                )

    def _build_group_ranges(self) -> None:
        """Build group ranges from processed items."""
        current_group_start = -1
        current_header_idx = -1

        for i, item in enumerate(self.items):
            is_header = self._is_header(item)
            if is_header:
                self._close_group(current_header_idx, current_group_start, i)
                current_header_idx = i
                current_group_start = i + 1
            elif current_header_idx >= 0 and current_group_start < 0:
                current_group_start = i

        # Close last group
        self._close_group(current_header_idx, current_group_start, len(self.items))

    def _close_group(self, header_idx: int, group_start: int, end_idx: int) -> None:
        """Close a group range if valid."""
        if header_idx >= 0 and group_start >= 0:
            self.group_ranges.append(GroupRange(header_idx, group_start, end_idx))

    def _initialize_preselected(self) -> None:
        """Initialize selected set with preselected item IDs."""
        if not self._preselected_ids:
            return
        for idx, item in enumerate(self.items):
            item_id: str | None = None
            if isinstance(item, SelectableItem):
                item_id = item.id
            elif isinstance(item, dict):
                item_id = item.get("id")
            if item_id and item_id in self._preselected_ids:
                self.selected.add(idx)

    def _is_header(self, item: SelectableItem | SelectableItemDict) -> bool:
        """Check if an item is a group header."""
        if isinstance(item, SelectableItem):
            if item.id and item.id.startswith("_header_"):
                return True
            if item.is_header:
                return True
        elif isinstance(item, dict):
            if item.get("id", "").startswith("_header_"):
                return True
            if item.get("is_header", False):
                return True
        return False

    def _get_group_items(self, header_idx: int) -> list[int]:
        """Get indices of items in a group (excluding header)."""
        for group_range in self.group_ranges:
            if group_range.header_idx == header_idx:
                return list(range(group_range.start, group_range.end))
        return []

    def _handle_key(self, key: str) -> KeyHandleResult:
        """Handle key press. Returns (should_continue, result)."""
        if key == UP and self.cursor > 0:
            self.cursor -= 1
            self._scroll_up()
        elif key == DOWN and self.cursor < len(self.items) - 1:
            self.cursor += 1
            self._scroll_down()
        elif key == " " and self.multi:
            self._toggle_selection()
        elif key == "a" and self.multi:
            # Select all
            for i, item in enumerate(self.items):
                if not self._is_header(item):
                    self.selected.add(i)
        elif key == "n" and self.multi:
            # Select none
            self.selected.clear()
        elif key == ENTER:
            return KeyHandleResult(False, self._get_selection())
        elif key == ESC:
            return KeyHandleResult(False, None)
        return KeyHandleResult(True, None)

    def _toggle_selection(self) -> None:
        """Toggle selection of current item or group."""
        current_item = self.items[self.cursor]

        if self._is_header(current_item):
            # Toggle all items in this group
            group_items = self._get_group_items(self.cursor)
            if group_items:
                # Check if all are selected
                all_selected = all(i in self.selected for i in group_items)
                if all_selected:
                    # Deselect all
                    for i in group_items:
                        self.selected.discard(i)
                else:
                    # Select all
                    for i in group_items:
                        self.selected.add(i)
        # Toggle single item
        elif self.cursor in self.selected:
            self.selected.remove(self.cursor)
        else:
            self.selected.add(self.cursor)

    def _get_selection(
        self,
    ) -> SelectableUnion | list[SelectableUnion]:
        """Get current selection result (excluding headers)."""
        if self.multi:
            return [
                self.items[i]
                for i in sorted(self.selected)
                if not self._is_header(self.items[i])
            ]
        return self.items[self.cursor]

    def run(
        self,
    ) -> SelectableUnion | list[SelectableUnion] | None:
        """Run loop. Returns selected value(s) or None."""
        try:
            while True:
                self._render()
                key = read_key_sequence()
                # Only process string keys, ignore int/None
                if not isinstance(key, str):
                    continue
                key_result = self._handle_key(key)
                if not key_result.should_continue:
                    return cast(
                        SelectableUnion | list[SelectableUnion] | None,
                        key_result.result,
                    )
        except KeyboardInterrupt:
            return None
        finally:
            self.clear()

    def _scroll_up(self) -> None:
        self.scroll_offset = min(self.cursor, self.scroll_offset)

    def _scroll_down(self) -> None:
        if self.cursor >= self.scroll_offset + self.max_height:
            self.scroll_offset = self.cursor - self.max_height + 1

    def _get_group_selection_state(self, header_idx: int) -> str:
        """Get selection state for a group: 'all', 'some', 'none'."""
        group_items = self._get_group_items(header_idx)
        if not group_items:
            return "none"
        selected_count = sum(1 for i in group_items if i in self.selected)
        if selected_count == 0:
            return "none"
        elif selected_count == len(group_items):
            return "all"
        else:
            return "some"

    def _get_item_label(self, item: SelectableItem | SelectableItemDict) -> str:
        """Get label from item regardless of format."""
        if isinstance(item, SelectableItem):
            return item.label
        return item["label"]

    def _get_item_description(self, item: SelectableItem | SelectableItemDict) -> str:
        """Get description from item if available."""
        if isinstance(item, SelectableItem):
            return item.description if item.description else ""
        if isinstance(item, dict) and item.get("description"):
            return item["description"]
        return ""

    def _build_cursor_prefix(self, is_cursor: bool) -> FormattedPrefix:
        """Build cursor indicator prefix. Returns (formatted, visible)."""
        if is_cursor:
            return FormattedPrefix(
                f"{Colors.BOLD}{Colors.REVERSE}>{Colors.RESET} ", "> "
            )
        return FormattedPrefix("  ", "  ")

    def _build_checkbox_prefix(self, real_idx: int) -> FormattedPrefix:
        """Build checkbox prefix for multi-select. Returns (formatted, visible)."""
        if real_idx in self.selected:
            return FormattedPrefix(f"{Colors.GREEN}[x]{Colors.RESET} ", "[x] ")
        return FormattedPrefix("[ ] ", "[ ] ")

    def _build_group_checkbox_prefix(self, real_idx: int) -> FormattedPrefix:
        """Build group checkbox prefix showing selection state."""
        state = self._get_group_selection_state(real_idx)
        if state == "all":
            return FormattedPrefix(f"{Colors.GREEN}[■]{Colors.RESET} ", "[■] ")
        if state == "some":
            return FormattedPrefix(f"{Colors.YELLOW}[◧]{Colors.RESET} ", "[◧] ")
        return FormattedPrefix(f"{Colors.CYAN}[□]{Colors.RESET} ", "[□] ")

    def _truncate_text(self, text: str, max_width: int) -> str:
        """Truncate text to fit within max_width."""
        if len(text) <= max_width:
            return text
        return text[: max_width - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX

    def _render_header_item(
        self, item: SelectableItem | SelectableItemDict, real_idx: int, is_cursor: bool
    ) -> str:
        """Render a group header item."""
        cursor_result = self._build_cursor_prefix(is_cursor)
        prefix, prefix_visible = cursor_result.formatted, cursor_result.visible

        if self.multi:
            chk_result = self._build_group_checkbox_prefix(real_idx)
            prefix += chk_result.formatted
            prefix_visible += chk_result.visible

        label = self._get_item_label(item)
        available_width = self.width - 4 - len(prefix_visible)
        label = self._truncate_text(label, available_width)

        return f"{prefix}{Colors.CYAN}{Colors.BOLD}{label}{Colors.RESET}"

    def _render_regular_item(
        self, item: SelectableItem | SelectableItemDict, real_idx: int, is_cursor: bool
    ) -> str:
        """Render a regular (non-header) item."""
        prefix = INDENT_CHILD
        prefix_visible = INDENT_CHILD

        cursor_result = self._build_cursor_prefix(is_cursor)
        prefix += cursor_result.formatted
        prefix_visible += cursor_result.visible

        if self.multi:
            chk_result = self._build_checkbox_prefix(real_idx)
            prefix += chk_result.formatted
            prefix_visible += chk_result.visible

        label = self._get_item_label(item)
        desc_text = self._get_item_description(item)
        available_width = self.width - 4 - len(prefix_visible)

        return self._format_item_line(prefix, label, desc_text, available_width)

    def _format_item_line(
        self, prefix: str, label: str, desc_text: str, available_width: int
    ) -> str:
        """Format an item line with optional description."""
        if not desc_text:
            return f"{prefix}{self._truncate_text(label, available_width)}"

        full_text = f"{label} - {desc_text}"
        full_text = self._truncate_text(full_text, available_width)

        if " - " in full_text:
            label_part, desc_part = full_text.split(" - ", 1)
            return f"{prefix}{label_part} - {Colors.YELLOW}{desc_part}{Colors.RESET}"
        return f"{prefix}{full_text}"

    def _render_scroll_indicators(self, content: list[str]) -> None:
        """Add scroll indicators to content if needed."""
        has_items_above = self.scroll_offset > 0
        has_items_below = self.scroll_offset + self.max_height < len(self.items)

        if has_items_above:
            content.insert(
                0, f"  {Colors.CYAN}▲ {self.scroll_offset} more above{Colors.RESET}"
            )
        if has_items_below:
            remaining = len(self.items) - self.scroll_offset - self.max_height
            content.append(f"  {Colors.CYAN}▼ {remaining} more below{Colors.RESET}")

    def _build_footer_text(self) -> str:
        """Build the footer instructions text."""
        instr = "↑/↓: navigate"
        if self.multi:
            instr += ", Space: toggle, a: all, n: none"
        instr += ", Enter: ok, Esc: cancel"
        return f"{Colors.GREEN}{instr}{Colors.RESET}"

    def _render(self) -> None:
        self.clear()
        content: list[str] = []

        visible_items = self.items[
            self.scroll_offset : self.scroll_offset + self.max_height
        ]

        for idx, item in enumerate(visible_items):
            real_idx = self.scroll_offset + idx
            is_cursor = real_idx == self.cursor
            is_header = self._is_header(item)

            if is_header:
                line_str = self._render_header_item(item, real_idx, is_cursor)
            else:
                line_str = self._render_regular_item(item, real_idx, is_cursor)
            content.append(line_str)

        self._render_scroll_indicators(content)

        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=self._build_footer_text(),
            style=BoxStyle(width=self.width, center_content=False),
        )
