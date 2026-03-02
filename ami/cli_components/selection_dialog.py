"""
Selection dialog for CLI menu selection with hierarchical group support.
"""

from typing import Protocol, TypedDict, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ami.cli_components.keys import BACKSPACE, DOWN, ENTER, ESC, UP
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
    disabled: bool  # If True, item is greyed out and permanently selected


class SelectableItemDict(TypedDict, total=False):
    """TypedDict for dict-based selection items."""

    id: str
    label: str
    description: str
    is_header: bool
    value: str | object
    disabled: bool  # If True, item is greyed out and permanently selected


# Type alias for selectable items union (without str for internal use)
SelectableUnion = SelectableItem | SelectableItemDict

# Union type for all valid item formats
DialogItem = SelectableItem | SelectableItemDict | str

# Constants for rendering
DEFAULT_DIALOG_WIDTH = 80
DEFAULT_MAX_HEIGHT = 10
TRUNCATION_SUFFIX = "..."
INDENT_CHILD = "   "


class SelectionDialogConfig(BaseModel):
    """Configuration for SelectionDialog to reduce argument count."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str = "Select"
    width: int = DEFAULT_DIALOG_WIDTH
    multi: bool = False
    max_height: int = DEFAULT_MAX_HEIGHT
    preselected: set[str] = Field(default_factory=set)
    skippable_ids: set[str] = Field(default_factory=set)

    @field_validator("preselected", "skippable_ids", mode="before")
    @classmethod
    def _none_to_set(cls, v: set[str] | None) -> set[str]:
        return set() if v is None else v


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
        self.cursor = self._first_selectable_index()
        self.scroll_offset = 0
        self.max_height = config.max_height
        self._skippable_ids = config.skippable_ids

        self.selected: set[int] = set()
        self.skipped: set[int] = set()
        self.skippable: set[int] = set()
        self._initialize_preselected()
        self._initialize_skippable()

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
        if header_idx >= 0 and group_start >= 0:
            self.group_ranges.append(GroupRange(header_idx, group_start, end_idx))

    def _initialize_preselected(self) -> None:
        """Initialize selected set with preselected and disabled items."""
        for idx, item in enumerate(self.items):
            # Disabled items are always selected
            if self._is_disabled(item):
                self.selected.add(idx)
                continue

            # Check preselected IDs
            if not self._preselected_ids:
                continue
            item_id: str | None = None
            if isinstance(item, SelectableItem):
                item_id = item.id
            elif isinstance(item, dict):
                item_id = item.get("id")
            if item_id and item_id in self._preselected_ids:
                self.selected.add(idx)

    def _initialize_skippable(self) -> None:
        """Initialize skippable set from config and set skipped state."""
        if not self._skippable_ids:
            return
        for idx, item in enumerate(self.items):
            item_id: str | None = None
            if isinstance(item, SelectableItem):
                item_id = item.id
            elif isinstance(item, dict):
                item_id = item.get("id")
            if item_id and item_id in self._skippable_ids:
                self.skippable.add(idx)
                # Skippable items start in skipped state (not selected)
                self.skipped.add(idx)
                # Remove from selected if it was preselected
                self.selected.discard(idx)

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

    def _is_disabled(self, item: SelectableItem | SelectableItemDict) -> bool:
        """Check if an item is disabled (locked/permanently selected)."""
        if isinstance(item, dict):
            return item.get("disabled", False)
        # SelectableItem protocol - access attribute directly
        try:
            return bool(item.disabled)
        except AttributeError:
            return False

    def _first_selectable_index(self) -> int:
        for i, item in enumerate(self.items):
            if not self._is_header(item):
                return i
        return 0

    def _get_group_items(self, header_idx: int) -> list[int]:
        """Get indices of items in a group (excluding header)."""
        for group_range in self.group_ranges:
            if group_range.header_idx == header_idx:
                return list(range(group_range.start, group_range.end))
        return []

    def _handle_key(self, key: str) -> KeyHandleResult:
        """Handle key press. Returns (should_continue, result)."""
        if key == UP:
            self._move_cursor_up()
        elif key == DOWN:
            self._move_cursor_down()
        elif key == " " and self.multi:
            self._toggle_selection()
        elif key == "a" and self.multi:
            for i, item in enumerate(self.items):
                if not self._is_header(item):
                    self.selected.add(i)
        elif key == "n" and self.multi:
            self.selected.clear()
        elif key == ENTER:
            return KeyHandleResult(False, self._get_selection())
        elif key in (ESC, BACKSPACE):
            return KeyHandleResult(False, None)
        return KeyHandleResult(True, None)

    def _move_cursor_up(self) -> None:
        """Move cursor up, skipping header items."""
        if self.cursor > 0:
            self.cursor -= 1
            while self.cursor > 0 and self._is_header(self.items[self.cursor]):
                self.cursor -= 1
            self._scroll_up()

    def _move_cursor_down(self) -> None:
        """Move cursor down, skipping header items."""
        if self.cursor < len(self.items) - 1:
            self.cursor += 1
            while self.cursor < len(self.items) - 1 and self._is_header(
                self.items[self.cursor]
            ):
                self.cursor += 1
            self._scroll_down()

    def _toggle_selection(self) -> None:
        """Toggle selection of current item or group."""
        current_item = self.items[self.cursor]

        # Disabled items cannot be toggled
        if self._is_disabled(current_item):
            return

        if self._is_header(current_item):
            self._toggle_group_selection()
        elif self.cursor in self.skippable:
            self._toggle_skippable_item()
        else:
            self._toggle_normal_item()

    def _toggle_group_selection(self) -> None:
        """Toggle all non-disabled items in the current group."""
        group_items = self._get_group_items(self.cursor)
        toggleable = [i for i in group_items if not self._is_disabled(self.items[i])]
        if not toggleable:
            return
        all_selected = all(i in self.selected for i in toggleable)
        if all_selected:
            # Deselect all (skippable go to skipped state)
            for i in toggleable:
                self.selected.discard(i)
                if i in self.skippable:
                    self.skipped.add(i)
        else:
            # Select all
            for i in toggleable:
                self.selected.add(i)
                self.skipped.discard(i)

    def _toggle_skippable_item(self) -> None:
        """Toggle skippable item between skipped and selected (no unselect)."""
        if self.cursor in self.skipped:
            self.skipped.remove(self.cursor)
            self.selected.add(self.cursor)
        else:
            self.selected.discard(self.cursor)
            self.skipped.add(self.cursor)

    def _toggle_normal_item(self) -> None:
        """Toggle normal two-state item."""
        if self.cursor in self.selected:
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
        group_items = self._get_group_items(header_idx)
        if not group_items:
            return "none"
        selected_count = sum(1 for i in group_items if i in self.selected)
        if selected_count == 0:
            return "none"
        if selected_count == len(group_items):
            return "all"
        return "some"

    def _get_item_label(self, item: SelectableItem | SelectableItemDict) -> str:
        if isinstance(item, SelectableItem):
            return item.label
        return item["label"]

    def _get_item_description(self, item: SelectableItem | SelectableItemDict) -> str:
        if isinstance(item, SelectableItem):
            return item.description or ""
        if isinstance(item, dict) and item.get("description"):
            return item["description"]
        return ""

    def _build_cursor_prefix(self, is_cursor: bool) -> FormattedPrefix:
        if is_cursor:
            return FormattedPrefix(
                f"{Colors.BOLD}{Colors.REVERSE}>{Colors.RESET} ", "> "
            )
        return FormattedPrefix("  ", "  ")

    def _build_checkbox_prefix(
        self, real_idx: int, is_disabled: bool = False
    ) -> FormattedPrefix:
        if is_disabled:
            return FormattedPrefix("\033[2m[✓]\033[0m ", "[✓] ")
        if real_idx in self.selected:
            return FormattedPrefix(f"{Colors.GREEN}[x]{Colors.RESET} ", "[x] ")
        return FormattedPrefix("[ ] ", "[ ] ")

    def _build_group_checkbox_prefix(self, real_idx: int) -> FormattedPrefix:
        state = self._get_group_selection_state(real_idx)
        if state == "all":
            return FormattedPrefix(f"{Colors.GREEN}[■]{Colors.RESET} ", "[■] ")
        if state == "some":
            return FormattedPrefix(f"{Colors.YELLOW}[◧]{Colors.RESET} ", "[◧] ")
        return FormattedPrefix(f"{Colors.CYAN}[□]{Colors.RESET} ", "[□] ")

    def _build_skip_checkbox_prefix(self) -> FormattedPrefix:
        return FormattedPrefix(f"{Colors.CYAN}[■]{Colors.RESET} ", "[■] ")

    def _truncate_text(self, text: str, max_width: int) -> str:
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
        is_disabled = self._is_disabled(item)

        cursor_result = self._build_cursor_prefix(is_cursor)
        prefix += cursor_result.formatted
        prefix_visible += cursor_result.visible

        if self.multi:
            # Tri-state: skipped shows [■], selected shows [x], unselected shows [ ]
            if real_idx in self.skipped:
                chk_result = self._build_skip_checkbox_prefix()
            else:
                chk_result = self._build_checkbox_prefix(real_idx, is_disabled)
            prefix += chk_result.formatted
            prefix_visible += chk_result.visible

        label = self._get_item_label(item)
        desc_text = self._get_item_description(item)

        # Add "(Reinstall)" suffix for skippable items that are selected
        if real_idx in self.skippable and real_idx in self.selected:
            desc_text = f"{desc_text} (Reinstall)" if desc_text else "(Reinstall)"

        available_width = self.width - 4 - len(prefix_visible)

        line = self._format_item_line(prefix, label, desc_text, available_width)

        # Wrap entire line in dim styling if disabled
        if is_disabled:
            return f"\033[2m{line}\033[0m"
        return line

    def _format_item_line(
        self, prefix: str, label: str, desc_text: str, available_width: int
    ) -> str:
        if not desc_text:
            return f"{prefix}{self._truncate_text(label, available_width)}"

        full_text = f"{label} - {desc_text}"
        full_text = self._truncate_text(full_text, available_width)

        if " - " in full_text:
            label_part, desc_part = full_text.split(" - ", 1)
            return f"{prefix}{label_part} - {Colors.YELLOW}{desc_part}{Colors.RESET}"
        return f"{prefix}{full_text}"

    def _render_scroll_indicators(self, content: list[str]) -> None:
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
