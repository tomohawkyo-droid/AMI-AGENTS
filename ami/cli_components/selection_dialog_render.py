"""Pure rendering helpers for SelectionDialog.

The dialog's state management + key handling lives in
`selection_dialog.py`; the ANSI/label construction used once per paint
lives here so the main module stays under the 512-line cap. Functions
here take the dialog instance and read its state (selected, cursor,
width, multi, items) without mutating it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ami.cli_components.text_input_utils import Colors
from ami.types.results import FormattedPrefix

if TYPE_CHECKING:
    from ami.cli_components.selection_dialog import (
        SelectableItem,
        SelectableItemDict,
        SelectionDialog,
    )

INDENT_CHILD = "   "
TRUNCATION_SUFFIX = "..."


def build_cursor_prefix(is_cursor: bool) -> FormattedPrefix:
    if is_cursor:
        return FormattedPrefix(f"{Colors.BOLD}{Colors.REVERSE}>{Colors.RESET} ", "> ")
    return FormattedPrefix("  ", "  ")


def build_checkbox_prefix(
    dialog: SelectionDialog, real_idx: int, *, is_disabled: bool = False
) -> FormattedPrefix:
    if is_disabled:
        return FormattedPrefix("\033[2m[✓]\033[0m ", "[✓] ")
    if real_idx in dialog.selected:
        return FormattedPrefix(f"{Colors.GREEN}[x]{Colors.RESET} ", "[x] ")
    return FormattedPrefix("[ ] ", "[ ] ")


def build_group_checkbox_prefix(
    dialog: SelectionDialog, real_idx: int
) -> FormattedPrefix:
    state = dialog._get_group_selection_state(real_idx)
    if state == "all":
        return FormattedPrefix(f"{Colors.GREEN}[■]{Colors.RESET} ", "[■] ")
    if state == "some":
        return FormattedPrefix(f"{Colors.YELLOW}[◧]{Colors.RESET} ", "[◧] ")
    return FormattedPrefix(f"{Colors.CYAN}[□]{Colors.RESET} ", "[□] ")


def build_skip_checkbox_prefix() -> FormattedPrefix:
    return FormattedPrefix(f"{Colors.CYAN}[■]{Colors.RESET} ", "[■] ")


def truncate_text(text: str, max_width: int) -> str:
    if len(text) <= max_width:
        return text
    return text[: max_width - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX


def item_label(item: SelectableItem | SelectableItemDict) -> str:
    if isinstance(item, dict):
        return item["label"]
    return item.label


def item_description(item: SelectableItem | SelectableItemDict) -> str:
    if isinstance(item, dict):
        raw = item.get("description") or ""
        return raw if isinstance(raw, str) else ""
    return item.description or ""


def render_header_item(
    dialog: SelectionDialog,
    item: SelectableItem | SelectableItemDict,
    real_idx: int,
    *,
    is_cursor: bool,
) -> str:
    cursor_result = build_cursor_prefix(is_cursor)
    prefix, prefix_visible = cursor_result.formatted, cursor_result.visible
    if dialog.multi:
        chk_result = build_group_checkbox_prefix(dialog, real_idx)
        prefix += chk_result.formatted
        prefix_visible += chk_result.visible
    label = item_label(item)
    available_width = dialog.width - 4 - len(prefix_visible)
    label = truncate_text(label, available_width)
    return f"{prefix}{Colors.CYAN}{Colors.BOLD}{label}{Colors.RESET}"


def render_regular_item(
    dialog: SelectionDialog,
    item: SelectableItem | SelectableItemDict,
    real_idx: int,
    *,
    is_cursor: bool,
) -> str:
    prefix = INDENT_CHILD
    prefix_visible = INDENT_CHILD
    is_disabled = dialog._is_disabled(item)

    cursor_result = build_cursor_prefix(is_cursor)
    prefix += cursor_result.formatted
    prefix_visible += cursor_result.visible

    if dialog.multi:
        if dialog._has_descendants(real_idx) and not is_disabled:
            chk_result = build_group_checkbox_prefix(dialog, real_idx)
            prefix += chk_result.formatted
            prefix_visible += chk_result.visible
            label = item_label(item)
            available_width = dialog.width - 4 - len(prefix_visible)
            label = truncate_text(label, available_width)
            description = item_description(item)
            if description:
                return f"{prefix}{label}  \033[2m{description}\033[22m"
            return f"{prefix}{label}"
        if real_idx in dialog.skipped:
            chk_result = build_skip_checkbox_prefix()
        else:
            chk_result = build_checkbox_prefix(
                dialog, real_idx, is_disabled=is_disabled
            )
        prefix += chk_result.formatted
        prefix_visible += chk_result.visible

    label = item_label(item)
    desc_text = item_description(item)

    if real_idx in dialog.skippable and real_idx in dialog.selected:
        desc_text = f"{desc_text} (Reinstall)" if desc_text else "(Reinstall)"

    available_width = dialog.width - 4 - len(prefix_visible)
    line = _format_item_line(prefix, label, desc_text, available_width)

    if is_disabled:
        return f"\033[2m{line}\033[0m"
    return line


def _format_item_line(
    prefix: str, label: str, desc_text: str, available_width: int
) -> str:
    if not desc_text:
        return f"{prefix}{truncate_text(label, available_width)}"
    full_text = f"{label} - {desc_text}"
    full_text = truncate_text(full_text, available_width)
    if " - " in full_text:
        label_part, desc_part = full_text.split(" - ", 1)
        return f"{prefix}{label_part} - {Colors.YELLOW}{desc_part}{Colors.RESET}"
    return f"{prefix}{full_text}"


def render_scroll_indicators(dialog: SelectionDialog, content: list[str]) -> None:
    has_items_above = dialog.scroll_offset > 0
    has_items_below = dialog.scroll_offset + dialog.max_height < len(dialog.items)
    if has_items_above:
        content.insert(
            0, f"  {Colors.CYAN}▲ {dialog.scroll_offset} more above{Colors.RESET}"
        )
    if has_items_below:
        remaining = len(dialog.items) - dialog.scroll_offset - dialog.max_height
        content.append(f"  {Colors.CYAN}▼ {remaining} more below{Colors.RESET}")


def build_footer_text(*, multi: bool) -> str:
    instr = "↑/↓: navigate"
    if multi:
        instr += ", Space: toggle, a: all, n: none"
    instr += ", Enter: ok, Esc: cancel"
    return f"{Colors.GREEN}{instr}{Colors.RESET}"
