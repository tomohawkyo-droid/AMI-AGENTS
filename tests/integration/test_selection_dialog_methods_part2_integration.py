"""Integration tests for SelectionDialog rendering,
MenuItem, and backup selector (part 2).

Covers: ami/cli_components/selection_dialog.py,
ami/cli_components/menu_selector.py,
ami/cli_components/selector.py
"""

from __future__ import annotations

from typing import ClassVar, TypedDict
from unittest.mock import patch

import pytest

from ami.cli_components.menu_selector import MenuItem
from ami.cli_components.selection_dialog import (
    TRUNCATION_SUFFIX,
    SelectionDialog,
    SelectionDialogConfig,
)
from ami.cli_components.selector import (
    FILE_ID_DISPLAY_THRESHOLD,
    display_backup_list,
    select_backup_by_index,
)
from ami.core.config import _ConfigSingleton

# -- Constants for expected test values --------------------------------------

EXPECTED_TRUNCATED_LENGTH = 7
EXPECTED_FILE_ID_THRESHOLD = 12
EXPECTED_GENERIC_VALUE = 42


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _dlg(items, **kw):
    return SelectionDialog(items, SelectionDialogConfig(**kw))


def _mi(
    item_id,
    label,
    value=None,
    description="",
    is_header=False,
):
    return MenuItem(item_id, label, value, description, is_header)


# 10. Item access


class TestItemAccess:
    def test_label_dict(self):
        result = _dlg(["x"])._get_item_label({"label": "Hi"})
        assert result == "Hi"

    def test_label_proto(self):
        result = _dlg(["x"])._get_item_label(_mi("x", "Proto"))
        assert result == "Proto"

    def test_desc_dict(self):
        result = _dlg(["x"])._get_item_description({"label": "L", "description": "D"})
        assert result == "D"

    def test_desc_missing(self):
        result = _dlg(["x"])._get_item_description({"label": "L"})
        assert result == ""

    def test_desc_proto(self):
        result = _dlg(["x"])._get_item_description(_mi("x", "L", description="D"))
        assert result == "D"

    def test_desc_empty_proto(self):
        result = _dlg(["x"])._get_item_description(_mi("x", "L"))
        assert result == ""


# 11. Prefixes


class TestPrefixes:
    def test_cursor_active(self):
        _, vis = _dlg(["a"])._build_cursor_prefix(True)
        assert vis == "> "

    def test_cursor_inactive(self):
        fmt, vis = _dlg(["a"])._build_cursor_prefix(False)
        assert fmt == vis == "  "

    def test_checkbox_selected(self):
        d = _dlg(["a"], multi=True)
        d.selected.add(0)
        assert "[x]" in d._build_checkbox_prefix(0)[1]

    def test_checkbox_unselected(self):
        prefix = _dlg(["a"], multi=True)._build_checkbox_prefix(0)[1]
        assert prefix == "[ ] "

    def test_group_checkbox_all(self):
        d = _dlg(
            [
                _mi(
                    "_header_g",
                    "G",
                    is_header=True,
                ),
                _mi("c1", "C1"),
            ],
            multi=True,
        )
        d.selected = {1}
        result = d._build_group_checkbox_prefix(0)[1]
        assert "[" in result

    def test_group_checkbox_none(self):
        d = _dlg(
            [
                _mi(
                    "_header_g",
                    "G",
                    is_header=True,
                ),
                _mi("c1", "C1"),
            ],
            multi=True,
        )
        result = d._build_group_checkbox_prefix(0)[1]
        assert "[" in result


# 12. Truncation


class TestTruncation:
    def test_short(self):
        result = _dlg(["a"])._truncate_text("hello", 10)
        assert result == "hello"

    def test_exact(self):
        result = _dlg(["a"])._truncate_text("12345", 5)
        assert result == "12345"

    def test_long(self):
        r = _dlg(["a"])._truncate_text("abcdefghij", EXPECTED_TRUNCATED_LENGTH)
        assert r.endswith("...")
        assert len(r) == EXPECTED_TRUNCATED_LENGTH

    def test_suffix(self):
        result = _dlg(["a"])._truncate_text("a" * 20, 10)
        assert result.endswith(TRUNCATION_SUFFIX)


# 13. Rendering


class TestRendering:
    def test_header_label(self):
        d = _dlg([_mi("_header_g", "GL", is_header=True)])
        rendered = d._render_header_item(d.items[0], 0, False)
        assert "GL" in rendered

    def test_header_cursor(self):
        d = _dlg([_mi("_header_g", "GL", is_header=True)])
        rendered = d._render_header_item(d.items[0], 0, True)
        assert ">" in rendered

    def test_regular_label(self):
        d = _dlg(["ItemL"])
        rendered = d._render_regular_item(d.items[0], 0, False)
        assert "ItemL" in rendered

    def test_regular_with_desc(self):
        d = _dlg([_mi("x", "Lbl", description="Desc")])
        line = d._render_regular_item(d.items[0], 0, False)
        assert "Lbl" in line
        assert "Desc" in line

    def test_format_no_desc(self):
        result = _dlg(["a"])._format_item_line(">> ", "Label", "", 50)
        assert result == ">> Label"

    def test_format_with_desc(self):
        r = _dlg(["a"])._format_item_line(">> ", "Label", "Info", 50)
        assert "Label" in r
        assert " - " in r
        assert "Info" in r

    def test_footer_single(self):
        f = _dlg(["a"])._build_footer_text()
        assert "navigate" in f
        assert "Space" not in f

    def test_footer_multi(self):
        f = _dlg(["a"], multi=True)._build_footer_text()
        assert "Space" in f
        assert "all" in f

    def test_scroll_above(self):
        d = _dlg(
            [str(i) for i in range(20)],
            max_height=5,
        )
        d.scroll_offset = 3
        c = ["line"]
        d._render_scroll_indicators(c)
        assert any("more above" in x for x in c)

    def test_scroll_below(self):
        d = _dlg(
            [str(i) for i in range(20)],
            max_height=5,
        )
        c = ["line"]
        d._render_scroll_indicators(c)
        assert any("more below" in x for x in c)

    def test_no_scroll_indicators(self):
        d = _dlg(["a", "b"], max_height=10)
        c = ["line"]
        d._render_scroll_indicators(c)
        assert len(c) == 1

    @patch("ami.cli_components.tui.TUI.clear_lines")
    def test_clear(self, mock_cl):
        d = _dlg(["a"])
        d._last_render_lines = 5
        d.clear()
        mock_cl.assert_called_once_with(5)
        assert d._last_render_lines == 0


# 14. MenuItem


class TestMenuItem:
    def test_basic(self):
        m = MenuItem("id1", "L", "v", "d")
        assert (
            m.id,
            m.label,
            m.value,
            m.description,
            m.is_header,
        ) == (
            "id1",
            "L",
            "v",
            "d",
            False,
        )

    def test_value_defaults(self):
        assert MenuItem("id1", "L").value == "id1"

    def test_none_value_defaults(self):
        assert MenuItem("id1", "L", None).value == "id1"

    def test_header(self):
        result = MenuItem("h", "H", is_header=True).is_header
        assert result is True

    def test_empty_desc(self):
        assert MenuItem("i", "L").description == ""

    def test_generic(self):
        item = MenuItem[int]("i", "L", EXPECTED_GENERIC_VALUE)
        assert item.value == EXPECTED_GENERIC_VALUE


# 15. Backup selector


class BackupFileEntry(TypedDict):
    """Backup file data for tests."""

    id: str
    name: str
    modifiedTime: str
    size: int


class TestBackupSelector:
    _FILES: ClassVar[list[BackupFileEntry]] = [
        {
            "id": "abc123",
            "name": "backup1.tar",
            "modifiedTime": "2024-01-01",
            "size": 1024,
        },
        {
            "id": "def456xyz789long",
            "name": "backup2.tar",
            "modifiedTime": "2024-02-01",
            "size": 2048,
        },
    ]

    def test_display_names(self, capsys):
        display_backup_list(self._FILES)
        out = capsys.readouterr().out
        assert "backup1.tar" in out
        assert "backup2.tar" in out

    def test_display_title(self, capsys):
        display_backup_list(self._FILES, title="My Backups")
        assert "My Backups" in capsys.readouterr().out

    def test_display_empty(self, capsys):
        display_backup_list([])
        out = capsys.readouterr().out
        assert "No backup files found" in out

    def test_display_truncates_long_id(self, capsys):
        display_backup_list(
            [
                {
                    "id": "a" * 20,
                    "name": "f",
                    "modifiedTime": "n",
                    "size": 1,
                }
            ]
        )
        assert "..." in capsys.readouterr().out

    def test_display_short_id_intact(self, capsys):
        display_backup_list(
            [
                {
                    "id": "short",
                    "name": "f",
                    "modifiedTime": "n",
                    "size": 1,
                }
            ]
        )
        raw = capsys.readouterr().out
        lines = [line for line in raw.split("\n") if "File ID" in line]
        assert all("..." not in line for line in lines)

    def test_select_valid(self):
        assert select_backup_by_index(self._FILES, 0) == "abc123"
        assert select_backup_by_index(self._FILES, 1) == "def456xyz789long"

    def test_select_negative(self):
        result = select_backup_by_index(self._FILES, -1)
        assert result is None

    def test_select_oob(self):
        result = select_backup_by_index(self._FILES, 99)
        assert result is None

    def test_select_empty(self):
        assert select_backup_by_index([], 0) is None

    def test_threshold(self):
        assert FILE_ID_DISPLAY_THRESHOLD == EXPECTED_FILE_ID_THRESHOLD


# 16. Preselected


class TestPreselected:
    def test_ids_selected(self):
        d = _dlg(
            [
                _mi("a", "A"),
                _mi("b", "B"),
                _mi("c", "C"),
            ],
            multi=True,
            preselected={"a", "c"},
        )
        assert d.selected == {0, 2}

    def test_unknown_ignored(self):
        d = _dlg(
            [_mi("a", "A")],
            multi=True,
            preselected={"zzz"},
        )
        assert d.selected == set()
