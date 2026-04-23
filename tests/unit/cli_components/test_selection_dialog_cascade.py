"""Unit tests for parent_id / descendants cascade in SelectionDialog.

Ensures that a parent row with `parent_id`-linked descendants:
- builds the descendants map,
- lets the cursor land on it,
- toggling cascades to every descendant and back,
- renders a tri-state checkbox reflecting partial selection.
"""

from __future__ import annotations

from ami.cli_components.selection_dialog import (
    SelectionDialog,
    SelectionDialogConfig,
)
from ami.cli_components.selection_dialog_render import (
    item_description,
    item_label,
    render_regular_item,
    render_scroll_indicators,
)

_CHILDREN = 3


def _item(
    item_id: str,
    *,
    label: str | None = None,
    parent_id: str | None = None,
    is_header: bool = False,
    disabled: bool = False,
) -> dict:
    return {
        "id": item_id,
        "label": label or item_id,
        "value": item_id,
        "is_header": is_header,
        "disabled": disabled,
        "parent_id": parent_id,
    }


def _flat_tree() -> list[dict]:
    """Parent row `root` with three non-header children."""
    return [
        _item("root"),
        _item("a", parent_id="root"),
        _item("b", parent_id="root"),
        _item("c", parent_id="root"),
    ]


def _make(items: list[dict]) -> SelectionDialog:
    return SelectionDialog(items, SelectionDialogConfig(multi=True))


class TestDescendantsMap:
    def test_flat_tree_populates_descendants(self) -> None:
        dialog = _make(_flat_tree())
        # root idx 0, children at 1, 2, 3.
        assert dialog._descendants[0] == [1, 2, 3]

    def test_transitive_descendants_expand(self) -> None:
        items = [
            _item("root"),
            _item("mid", parent_id="root"),
            _item("leaf", parent_id="mid"),
        ]
        dialog = _make(items)
        assert dialog._descendants[0] == [1, 2]
        assert dialog._descendants[1] == [2]

    def test_no_parent_id_means_empty_map(self) -> None:
        items = [_item("a"), _item("b"), _item("c")]
        dialog = _make(items)
        assert dialog._descendants == {}


class TestCascadeToggle:
    def test_toggle_on_parent_selects_all_descendants_plus_self(self) -> None:
        dialog = _make(_flat_tree())
        dialog.cursor = 0
        dialog._toggle_selection()
        assert dialog.selected == {0, 1, 2, 3}

    def test_second_toggle_clears_the_group(self) -> None:
        dialog = _make(_flat_tree())
        dialog.cursor = 0
        dialog._toggle_selection()
        dialog._toggle_selection()
        assert dialog.selected == set()

    def test_partial_selection_becomes_all_on_toggle(self) -> None:
        """If the group is partially ticked, toggling the parent fills it."""
        dialog = _make(_flat_tree())
        dialog.selected.add(1)  # one child pre-selected
        dialog.cursor = 0
        dialog._toggle_selection()
        assert dialog.selected == {0, 1, 2, 3}

    def test_disabled_descendants_are_skipped(self) -> None:
        items = [
            _item("root"),
            _item("a", parent_id="root"),
            _item("locked", parent_id="root", disabled=True),
            _item("c", parent_id="root"),
        ]
        dialog = _make(items)
        locked_idx = 2
        assert locked_idx in dialog.selected  # disabled items auto-select
        dialog.cursor = 0
        dialog._toggle_selection()
        # locked stays, others flip on.
        assert dialog.selected.issuperset({0, 1, 3})
        assert locked_idx in dialog.selected


class TestCursorOnParents:
    def test_cursor_lands_on_header_with_descendants(self) -> None:
        items = [
            _item("_header_x", label="Group", is_header=True),
            _item("a", parent_id="_header_x"),
            _item("b", parent_id="_header_x"),
        ]
        dialog = _make(items)
        # First selectable = the header (has descendants).
        assert dialog.cursor == 0

    def test_cursor_skips_pure_decorative_header(self) -> None:
        items = [
            _item("_header_x", label="Group", is_header=True),
            _item("a"),
            _item("b"),
        ]
        dialog = _make(items)
        # No parent_id wiring → header stays decorative → cursor skips it.
        assert dialog.cursor == 1


class TestTriStateRendering:
    def test_group_state_all_when_all_descendants_selected(self) -> None:
        dialog = _make(_flat_tree())
        for i in (0, 1, 2, 3):
            dialog.selected.add(i)
        assert dialog._get_group_selection_state(0) == "all"

    def test_group_state_some_when_mixed(self) -> None:
        dialog = _make(_flat_tree())
        dialog.selected.add(1)
        assert dialog._get_group_selection_state(0) == "some"

    def test_group_state_none_when_empty(self) -> None:
        dialog = _make(_flat_tree())
        assert dialog._get_group_selection_state(0) == "none"


class TestRenderRegularWithDescendants:
    """Coverage for the render_regular_item parent-row branch."""

    def test_parent_row_uses_group_checkbox(self) -> None:
        dialog = _make(_flat_tree())
        line = render_regular_item(dialog, dialog.items[0], 0, is_cursor=False)
        # Group-checkbox is one of [□] [◧] [■].
        assert any(ch in line for ch in ("[□]", "[◧]", "[■]"))

    def test_parent_row_with_description_renders_dim_tail(self) -> None:
        items = [
            {
                "id": "root",
                "label": "root",
                "description": "7 files",
                "is_header": False,
            },
            {"id": "a", "label": "a", "parent_id": "root", "is_header": False},
        ]
        dialog = _make(items)
        line = render_regular_item(dialog, dialog.items[0], 0, is_cursor=False)
        assert "7 files" in line
        assert "\033[2m" in line  # dim styling wraps the description

    def test_skipped_row_uses_skip_checkbox(self) -> None:
        items = [
            {"id": "a", "label": "a", "is_header": False},
        ]
        dialog = SelectionDialog(
            items,
            SelectionDialogConfig(multi=True, skippable_ids={"a"}),
        )
        line = render_regular_item(dialog, dialog.items[0], 0, is_cursor=False)
        # Skip-prefix has a filled-block glyph.
        assert "[■]" in line


class TestRenderHelpers:
    def test_item_label_from_object(self) -> None:
        class _Obj:
            id = "x"
            label = "Object"
            description = ""
            is_header = False
            value = "x"
            disabled = False
            parent_id = None

        assert item_label(_Obj()) == "Object"

    def test_item_description_object_empty(self) -> None:
        class _Obj:
            id = "x"
            label = "Object"
            description = None
            is_header = False
            value = "x"
            disabled = False
            parent_id = None

        assert item_description(_Obj()) == ""

    def test_scroll_indicators_both(self) -> None:
        dialog = SelectionDialog(
            [str(i) for i in range(10)],
            SelectionDialogConfig(max_height=3),
        )
        dialog.scroll_offset = 4
        content: list[str] = ["a", "b", "c"]
        render_scroll_indicators(dialog, content)
        joined = "\n".join(content)
        assert "above" in joined
        assert "below" in joined
