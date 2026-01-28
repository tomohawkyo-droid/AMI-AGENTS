"""Integration tests for SelectionDialog internals (part 1).

Covers: ami/cli_components/selection_dialog.py
"""

from unittest.mock import patch

import pytest

from ami.cli_components.menu_selector import MenuItem
from ami.cli_components.selection_dialog import (
    SelectionDialog,
    SelectionDialogConfig,
)
from ami.core.config import _ConfigSingleton

# Named constants for magic numbers used in assertions
EXPECTED_MIXED_ITEMS_COUNT = 3
EXPECTED_SCROLL_OFFSET = 3


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _dlg(items, **kw):
    return SelectionDialog(items, SelectionDialogConfig(**kw))


def _mi(item_id, label, value=None, description="", is_header=False):
    return MenuItem(item_id, label, value, description, is_header)


# 1. SelectionDialogConfig ────────────────────────────────────────────────


class TestSelectionDialogConfig:
    def test_defaults(self):
        c = SelectionDialogConfig()
        assert (c.title, c.width, c.multi, c.max_height) == ("Select", 80, False, 10)
        assert c.preselected == set()

    def test_custom(self):
        c = SelectionDialogConfig(
            title="P", width=60, multi=True, max_height=5, preselected={"a"}
        )
        assert (c.title, c.width, c.multi, c.max_height) == ("P", 60, True, 5)
        assert c.preselected == {"a"}

    def test_preselected_none(self):
        assert SelectionDialogConfig(preselected=None).preselected == set()


# 2. _process_items ───────────────────────────────────────────────────────


class TestProcessItems:
    def test_strings(self):
        d = _dlg(["A", "B"])
        assert d.items[0] == {"label": "A", "value": "A", "is_header": False}

    def test_dicts(self):
        d = _dlg([{"label": "X", "value": "x", "is_header": False}])
        assert d.items[0]["label"] == "X"

    def test_protocol_objects(self):
        mi = _mi("m1", "M1", "v1")
        assert _dlg([mi]).items[0] is mi

    def test_mixed(self):
        d = _dlg(["plain", {"label": "Dict"}, _mi("m", "Menu")])
        assert len(d.items) == EXPECTED_MIXED_ITEMS_COUNT
        assert d.items[0]["label"] == "plain"
        assert d.items[2].label == "Menu"


# 3. _build_group_ranges ──────────────────────────────────────────────────


class TestGroupRanges:
    def test_no_headers(self):
        assert _dlg(["a", "b"]).group_ranges == []

    def test_single_group(self):
        d = _dlg(
            [_mi("_header_g", "G", is_header=True), _mi("c1", "C1"), _mi("c2", "C2")]
        )
        assert d.group_ranges == [(0, 1, 3)]

    def test_two_groups(self):
        d = _dlg(
            [
                _mi("_header_a", "GA", is_header=True),
                _mi("a1", "A1"),
                _mi("_header_b", "GB", is_header=True),
                _mi("b1", "B1"),
                _mi("b2", "B2"),
            ]
        )
        assert d.group_ranges == [(0, 1, 2), (2, 3, 5)]

    def test_header_only(self):
        d = _dlg([_mi("_header_x", "H", is_header=True)])
        assert d.group_ranges == [(0, 1, 1)]


# 4. _is_header ───────────────────────────────────────────────────────────


class TestIsHeader:
    def test_id_prefix(self):
        assert _dlg(["x"])._is_header(_mi("_header_g", "G")) is True

    def test_flag(self):
        assert _dlg(["x"])._is_header(_mi("nrm", "G", is_header=True)) is True

    def test_regular(self):
        assert _dlg(["x"])._is_header(_mi("r", "R")) is False

    def test_dict_header_id(self):
        assert _dlg(["x"])._is_header({"id": "_header_x", "label": "H"}) is True

    def test_dict_flag(self):
        assert _dlg(["x"])._is_header({"label": "H", "is_header": True}) is True

    def test_dict_regular(self):
        assert _dlg(["x"])._is_header({"label": "R", "is_header": False}) is False


# 5. _handle_key ──────────────────────────────────────────────────────────


class TestHandleKey:
    def test_up(self):
        d = _dlg(["a", "b", "c"])
        d.cursor = 2
        assert d._handle_key("UP") == (True, None)
        assert d.cursor == 1

    def test_up_at_zero(self):
        d = _dlg(["a"])
        d._handle_key("UP")
        assert d.cursor == 0

    def test_down(self):
        d = _dlg(["a", "b"])
        d._handle_key("DOWN")
        assert d.cursor == 1

    def test_down_at_end(self):
        d = _dlg(["a", "b"])
        d.cursor = 1
        d._handle_key("DOWN")
        assert d.cursor == 1

    @patch("ami.cli_components.tui.TUI.clear_lines")
    def test_enter(self, mock_clear):
        assert mock_clear is not None
        d = _dlg(["a", "b"])
        d.cursor = 1
        ok, res = d._handle_key("ENTER")
        assert ok is False
        assert res["label"] == "b"

    def test_esc(self):
        ok, res = _dlg(["a"])._handle_key("ESC")
        assert ok is False
        assert res is None

    def test_space_multi(self):
        d = _dlg(["a"], multi=True)
        d._handle_key(" ")
        assert 0 in d.selected

    def test_space_single_ignored(self):
        d = _dlg(["a"])
        d._handle_key(" ")
        assert 0 not in d.selected

    def test_a_all(self):
        d = _dlg(["a", "b"], multi=True)
        d._handle_key("a")
        assert d.selected == {0, 1}

    def test_n_none(self):
        d = _dlg(["a"], multi=True)
        d.selected = {0}
        d._handle_key("n")
        assert d.selected == set()


# 6. _toggle_selection ────────────────────────────────────────────────────


class TestToggle:
    def test_on(self):
        d = _dlg(["a"], multi=True)
        d._toggle_selection()
        assert 0 in d.selected

    def test_off(self):
        d = _dlg(["a"], multi=True)
        d.selected.add(0)
        d._toggle_selection()
        assert 0 not in d.selected

    def test_group_select(self):
        d = _dlg(
            [_mi("_header_g", "G", is_header=True), _mi("c1", "C1"), _mi("c2", "C2")],
            multi=True,
        )
        d._toggle_selection()  # cursor=0 (header)
        assert d.selected == {1, 2}

    def test_group_deselect(self):
        d = _dlg(
            [_mi("_header_g", "G", is_header=True), _mi("c1", "C1"), _mi("c2", "C2")],
            multi=True,
        )
        d.selected = {1, 2}
        d._toggle_selection()
        assert d.selected == set()


# 7. _get_selection ───────────────────────────────────────────────────────


class TestGetSelection:
    def test_single(self):
        d = _dlg(["a", "b"])
        d.cursor = 1
        assert d._get_selection()["label"] == "b"

    def test_multi(self):
        d = _dlg(["a", "b", "c"], multi=True)
        d.selected = {0, 2}
        r = d._get_selection()
        assert [x["label"] for x in r] == ["a", "c"]

    def test_multi_excludes_headers(self):
        d = _dlg([_mi("_header_g", "G", is_header=True), _mi("c1", "C1")], multi=True)
        d.selected = {0, 1}
        assert len(d._get_selection()) == 1


# 8. Scroll ───────────────────────────────────────────────────────────────


class TestScroll:
    def test_scroll_up_adjusts(self):
        d = _dlg([str(i) for i in range(20)], max_height=5)
        d.scroll_offset = 5
        d.cursor = 3
        d._scroll_up()
        assert d.scroll_offset == EXPECTED_SCROLL_OFFSET

    def test_scroll_up_noop(self):
        d = _dlg([str(i) for i in range(20)], max_height=5)
        d.cursor = 2
        d._scroll_up()
        assert d.scroll_offset == 0

    def test_scroll_down_adjusts(self):
        d = _dlg([str(i) for i in range(20)], max_height=5)
        d.cursor = 5
        d._scroll_down()
        assert d.scroll_offset == 1

    def test_scroll_down_noop(self):
        d = _dlg([str(i) for i in range(20)], max_height=5)
        d.cursor = 3
        d._scroll_down()
        assert d.scroll_offset == 0


# 9. _get_group_selection_state ───────────────────────────────────────────


class TestGroupState:
    def _gd(self):
        return _dlg(
            [_mi("_header_g", "G", is_header=True), _mi("c1", "C1"), _mi("c2", "C2")],
            multi=True,
        )

    def test_none(self):
        assert self._gd()._get_group_selection_state(0) == "none"

    def test_all(self):
        d = self._gd()
        d.selected = {1, 2}
        assert d._get_group_selection_state(0) == "all"

    def test_some(self):
        d = self._gd()
        d.selected = {1}
        assert d._get_group_selection_state(0) == "some"

    def test_empty_group(self):
        assert (
            _dlg(
                [_mi("_header_g", "G", is_header=True)], multi=True
            )._get_group_selection_state(0)
            == "none"
        )
