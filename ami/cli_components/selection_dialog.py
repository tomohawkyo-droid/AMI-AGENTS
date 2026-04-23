"""
Selection dialog for CLI menu selection with hierarchical group support.
"""

from typing import Protocol, TypedDict, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ami.cli_components.keys import BACKSPACE, DOWN, ENTER, ESC, UP
from ami.cli_components.selection_dialog_render import (
    build_footer_text,
    render_header_item,
    render_regular_item,
    render_scroll_indicators,
)
from ami.cli_components.text_input_utils import read_key_sequence
from ami.cli_components.tui import TUI, BoxStyle
from ami.types.results import GroupRange, KeyHandleResult


@runtime_checkable
class SelectableItem(Protocol):
    """Protocol for objects that can be used as selection dialog items."""

    id: str
    label: str
    description: str
    is_header: bool
    value: str | object
    disabled: bool  # If True, item is greyed out and permanently selected
    parent_id: str | None  # If set, toggling the parent cascades to this item


class SelectableItemDict(TypedDict, total=False):
    """TypedDict for dict-based selection items."""

    id: str
    label: str
    description: str
    is_header: bool
    value: str | object
    disabled: bool  # If True, item is greyed out and permanently selected
    parent_id: str | None  # If set, toggling the parent cascades to this item


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
        # parent_id-based descendants (nested trees). Populated after items
        # are processed; empty when callers don't set parent_id anywhere.
        self._descendants: dict[int, list[int]] = {}

        self._process_items(items)
        self._build_group_ranges()
        self._build_descendants()

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

    def _item_id(self, item: SelectableItem | SelectableItemDict) -> str | None:
        if isinstance(item, dict):
            value = item.get("id")
            return value if isinstance(value, str) else None
        return getattr(item, "id", None)

    def _item_parent_id(self, item: SelectableItem | SelectableItemDict) -> str | None:
        if isinstance(item, dict):
            value = item.get("parent_id")
            return value if isinstance(value, str) else None
        return getattr(item, "parent_id", None)

    def _build_descendants(self) -> None:
        """Resolve `parent_id` links into `idx -> [descendant_idx, ...]`."""
        idx_by_id: dict[str, int] = {}
        for idx, item in enumerate(self.items):
            item_id = self._item_id(item)
            if item_id is not None:
                idx_by_id[item_id] = idx
        children: dict[int, list[int]] = {}
        for idx, item in enumerate(self.items):
            parent_id = self._item_parent_id(item)
            if parent_id is None:
                continue
            parent_idx = idx_by_id.get(parent_id)
            if parent_idx is None or parent_idx == idx:
                continue
            children.setdefault(parent_idx, []).append(idx)
        if not children:
            return
        # Expand to transitive descendants so a toggle cascades through the tree.
        for root_idx in children:
            stack = list(children.get(root_idx, []))
            seen: set[int] = set()
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(children.get(node, []))
            self._descendants[root_idx] = sorted(seen)

    def _has_descendants(self, idx: int) -> bool:
        return bool(self._descendants.get(idx))

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
        for i in range(len(self.items)):
            if not self._should_skip_cursor(i):
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

    def _should_skip_cursor(self, idx: int) -> bool:
        """Pure decorative headers are skipped; parents with descendants stay."""
        if not self._is_header(self.items[idx]):
            return False
        return not self._has_descendants(idx)

    def _move_cursor_up(self) -> None:
        """Move cursor up, skipping pure-decoration headers."""
        if self.cursor > 0:
            self.cursor -= 1
            while self.cursor > 0 and self._should_skip_cursor(self.cursor):
                self.cursor -= 1
            self._scroll_up()

    def _move_cursor_down(self) -> None:
        """Move cursor down, skipping pure-decoration headers."""
        if self.cursor < len(self.items) - 1:
            self.cursor += 1
            while self.cursor < len(self.items) - 1 and self._should_skip_cursor(
                self.cursor
            ):
                self.cursor += 1
            self._scroll_down()

    def _toggle_selection(self) -> None:
        """Toggle selection of current item or group."""
        current_item = self.items[self.cursor]

        # Disabled items cannot be toggled
        if self._is_disabled(current_item):
            return

        if self._has_descendants(self.cursor):
            self._toggle_descendants(self.cursor)
        elif self._is_header(current_item):
            self._toggle_group_selection()
        elif self.cursor in self.skippable:
            self._toggle_skippable_item()
        else:
            self._toggle_normal_item()

    def _toggle_descendants(self, parent_idx: int) -> None:
        """Cascade-toggle `parent_idx` + every descendant via parent_id."""
        affected = [parent_idx, *self._descendants[parent_idx]]
        toggleable = [i for i in affected if not self._is_disabled(self.items[i])]
        if not toggleable:
            return
        all_selected = all(i in self.selected for i in toggleable)
        if all_selected:
            for i in toggleable:
                self.selected.discard(i)
                if i in self.skippable:
                    self.skipped.add(i)
        else:
            for i in toggleable:
                self.selected.add(i)
                self.skipped.discard(i)

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
        if header_idx in self._descendants:
            member_ids = self._descendants[header_idx]
        else:
            member_ids = self._get_group_items(header_idx)
        if not member_ids:
            return "none"
        selected_count = sum(1 for i in member_ids if i in self.selected)
        if selected_count == 0:
            return "none"
        if selected_count == len(member_ids):
            return "all"
        return "some"

    def _render(self) -> None:
        self.clear()
        content: list[str] = []

        visible_items = self.items[
            self.scroll_offset : self.scroll_offset + self.max_height
        ]

        for idx, item in enumerate(visible_items):
            real_idx = self.scroll_offset + idx
            is_cursor = real_idx == self.cursor
            if self._is_header(item):
                line_str = render_header_item(self, item, real_idx, is_cursor=is_cursor)
            else:
                line_str = render_regular_item(
                    self, item, real_idx, is_cursor=is_cursor
                )
            content.append(line_str)

        render_scroll_indicators(self, content)

        self._last_render_lines = TUI.draw_box(
            content=content,
            title=self.title,
            footer=build_footer_text(multi=self.multi),
            style=BoxStyle(width=self.width, center_content=False),
        )
