"""Unit tests for SelectionDialog - scrolling, rendering, prefixes, and run."""

from unittest.mock import patch

from ami.cli_components.selection_dialog import (
    ENTER,
    ESC,
    INDENT_CHILD,
    SelectionDialog,
    SelectionDialogConfig,
)

EXPECTED_TRUNCATED_LENGTH = 8
EXPECTED_RENDER_LINES = 5
EXPECTED_CONTENT_LENGTH = 2


class TestScrolling:
    """Tests for scrolling methods."""

    def test_scroll_up(self):
        """Test _scroll_up adjusts offset."""
        config = SelectionDialogConfig(max_height=3)
        dialog = SelectionDialog(["A", "B", "C", "D", "E"], config)
        dialog.scroll_offset = 2
        dialog.cursor = 1

        dialog._scroll_up()

        assert dialog.scroll_offset == 1

    def test_scroll_down(self):
        """Test _scroll_down adjusts offset."""
        config = SelectionDialogConfig(max_height=3)
        dialog = SelectionDialog(["A", "B", "C", "D", "E"], config)
        dialog.scroll_offset = 0
        dialog.cursor = 3

        dialog._scroll_down()

        assert dialog.scroll_offset == 1


class TestGroupSelectionState:
    """Tests for _get_group_selection_state method."""

    def test_all_selected(self):
        """Test returns 'all' when all group items selected."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.selected = {1, 2}

        result = dialog._get_group_selection_state(0)

        assert result == "all"

    def test_some_selected(self):
        """Test returns 'some' when some group items selected."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.selected = {1}

        result = dialog._get_group_selection_state(0)

        assert result == "some"

    def test_none_selected(self):
        """Test returns 'none' when no group items selected."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)

        result = dialog._get_group_selection_state(0)

        assert result == "none"

    def test_empty_group_returns_none(self):
        """Test returns 'none' for empty/nonexistent group."""
        dialog = SelectionDialog(["A"])

        result = dialog._get_group_selection_state(99)

        assert result == "none"


class TestItemAccessors:
    """Tests for _get_item_label and _get_item_description methods."""

    def test_get_label_from_dict(self):
        """Test getting label from dict item."""
        dialog = SelectionDialog(["dummy"])
        item = {"label": "Test Label", "value": "v"}

        result = dialog._get_item_label(item)

        assert result == "Test Label"

    def test_get_description_from_dict(self):
        """Test getting description from dict item."""
        dialog = SelectionDialog(["dummy"])
        item = {"label": "L", "description": "Test Description"}

        result = dialog._get_item_description(item)

        assert result == "Test Description"

    def test_get_description_missing(self):
        """Test getting description when missing."""
        dialog = SelectionDialog(["dummy"])
        item = {"label": "L", "value": "v"}

        result = dialog._get_item_description(item)

        assert result == ""


class TestPrefixBuilders:
    """Tests for prefix builder methods."""

    def test_cursor_prefix_selected(self):
        """Test cursor prefix when selected."""
        dialog = SelectionDialog(["dummy"])

        formatted, visible = dialog._build_cursor_prefix(True)

        assert "> " in visible
        assert "\033[" in formatted  # Contains ANSI codes

    def test_cursor_prefix_not_selected(self):
        """Test cursor prefix when not selected."""
        dialog = SelectionDialog(["dummy"])

        _formatted, visible = dialog._build_cursor_prefix(False)

        assert visible == "  "

    def test_checkbox_prefix_selected(self):
        """Test checkbox prefix when item selected."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A"], config)
        dialog.selected = {0}

        formatted, visible = dialog._build_checkbox_prefix(0)

        assert "[x]" in visible
        assert "\033[" in formatted  # Contains ANSI codes

    def test_checkbox_prefix_not_selected(self):
        """Test checkbox prefix when item not selected."""
        dialog = SelectionDialog(["A"])

        _formatted, visible = dialog._build_checkbox_prefix(0)

        assert visible == "[ ] "

    def test_group_checkbox_all_selected(self):
        """Test group checkbox when all selected."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.selected = {1}

        _formatted, visible = dialog._build_group_checkbox_prefix(0)

        assert "[■]" in visible

    def test_group_checkbox_some_selected(self):
        """Test group checkbox when some selected."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.selected = {1}

        _formatted, visible = dialog._build_group_checkbox_prefix(0)

        assert "[◧]" in visible

    def test_group_checkbox_none_selected(self):
        """Test group checkbox when none selected."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)

        _formatted, visible = dialog._build_group_checkbox_prefix(0)

        assert "[□]" in visible


class TestTruncateText:
    """Tests for _truncate_text method."""

    def test_no_truncation_needed(self):
        """Test text not truncated when fits."""
        dialog = SelectionDialog(["dummy"])

        result = dialog._truncate_text("Hello", 10)

        assert result == "Hello"

    def test_truncation_applied(self):
        """Test text truncated when too long."""
        dialog = SelectionDialog(["dummy"])

        result = dialog._truncate_text("Hello World", 8)

        assert result == "Hello..."
        assert len(result) == EXPECTED_TRUNCATED_LENGTH


class TestRenderItems:
    """Tests for render item methods."""

    def test_render_header_item(self):
        """Test rendering header item."""
        dialog = SelectionDialog(["dummy"])
        item = {"id": "_header_1", "label": "Group Header", "is_header": True}

        result = dialog._render_header_item(item, 0, False)

        assert "Group Header" in result
        assert "\033[" in result  # Contains ANSI codes

    def test_render_regular_item(self):
        """Test rendering regular item."""
        dialog = SelectionDialog(["dummy"])
        item = {"label": "Regular Item", "is_header": False}

        result = dialog._render_regular_item(item, 0, False)

        assert "Regular Item" in result
        assert INDENT_CHILD in result

    def test_render_regular_item_with_description(self):
        """Test rendering regular item with description."""
        dialog = SelectionDialog(["dummy"])
        item = {"label": "Item", "description": "Desc", "is_header": False}

        result = dialog._render_regular_item(item, 0, False)

        assert "Item" in result
        assert "Desc" in result
        assert " - " in result


class TestFormatItemLine:
    """Tests for _format_item_line method."""

    def test_format_without_description(self):
        """Test formatting line without description."""
        dialog = SelectionDialog(["dummy"])

        result = dialog._format_item_line(">> ", "Label", "", 50)

        assert result == ">> Label"

    def test_format_with_description(self):
        """Test formatting line with description."""
        dialog = SelectionDialog(["dummy"])

        result = dialog._format_item_line(">> ", "Label", "Desc", 50)

        assert "Label" in result
        assert "Desc" in result
        assert " - " in result


class TestBuildFooterText:
    """Tests for _build_footer_text method."""

    def test_single_mode_footer(self):
        """Test footer text in single mode."""
        dialog = SelectionDialog(["A"])

        result = dialog._build_footer_text()

        assert "navigate" in result
        assert "Enter" in result
        assert "Esc" in result
        assert "Space" not in result

    def test_multi_mode_footer(self):
        """Test footer text in multi mode."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A"], config)

        result = dialog._build_footer_text()

        assert "toggle" in result
        assert "all" in result
        assert "none" in result


class TestClear:
    """Tests for clear method."""

    @patch("ami.cli_components.selection_dialog.TUI")
    def test_clear_calls_tui(self, mock_tui):
        """Test clear calls TUI.clear_lines."""
        dialog = SelectionDialog(["A"])
        dialog._last_render_lines = 5

        dialog.clear()

        mock_tui.clear_lines.assert_called_once_with(5)
        assert dialog._last_render_lines == 0


class TestRender:
    """Tests for _render method."""

    @patch("ami.cli_components.selection_dialog.TUI")
    def test_render_calls_tui_draw_box(self, mock_tui):
        """Test _render calls TUI.draw_box."""
        mock_tui.draw_box.return_value = 5
        dialog = SelectionDialog(["A", "B"])

        dialog._render()

        mock_tui.draw_box.assert_called_once()
        assert dialog._last_render_lines == EXPECTED_RENDER_LINES


class TestRenderScrollIndicators:
    """Tests for _render_scroll_indicators method."""

    def test_no_indicators_when_all_visible(self):
        """Test no indicators when all items visible."""
        config = SelectionDialogConfig(max_height=10)
        dialog = SelectionDialog(["A", "B"], config)
        content = ["line1", "line2"]

        dialog._render_scroll_indicators(content)

        assert len(content) == EXPECTED_CONTENT_LENGTH

    def test_above_indicator(self):
        """Test above indicator when scrolled down."""
        config = SelectionDialogConfig(max_height=2)
        dialog = SelectionDialog(["A", "B", "C", "D"], config)
        dialog.scroll_offset = 2
        content = ["line1", "line2"]

        dialog._render_scroll_indicators(content)

        assert any("above" in line for line in content)

    def test_below_indicator(self):
        """Test below indicator when more items below."""
        config = SelectionDialogConfig(max_height=2)
        dialog = SelectionDialog(["A", "B", "C", "D"], config)
        dialog.scroll_offset = 0
        content = ["line1", "line2"]

        dialog._render_scroll_indicators(content)

        assert any("below" in line for line in content)


class TestRun:
    """Tests for run method."""

    @patch("ami.cli_components.selection_dialog.read_key_sequence")
    @patch("ami.cli_components.selection_dialog.TUI")
    def test_run_returns_selection_on_enter(self, mock_tui, mock_read_key):
        """Test run returns selection when Enter pressed."""
        mock_tui.draw_box.return_value = 3
        mock_read_key.return_value = ENTER
        dialog = SelectionDialog(["A", "B"])

        result = dialog.run()

        assert result["label"] == "A"

    @patch("ami.cli_components.selection_dialog.read_key_sequence")
    @patch("ami.cli_components.selection_dialog.TUI")
    def test_run_returns_none_on_esc(self, mock_tui, mock_read_key):
        """Test run returns None when Esc pressed."""
        mock_tui.draw_box.return_value = 3
        mock_read_key.return_value = ESC
        dialog = SelectionDialog(["A", "B"])

        result = dialog.run()

        assert result is None

    @patch("ami.cli_components.selection_dialog.read_key_sequence")
    @patch("ami.cli_components.selection_dialog.TUI")
    def test_run_returns_none_on_keyboard_interrupt(self, mock_tui, mock_read_key):
        """Test run returns None on KeyboardInterrupt."""
        mock_tui.draw_box.return_value = 3
        mock_read_key.side_effect = KeyboardInterrupt()
        dialog = SelectionDialog(["A"])

        result = dialog.run()

        assert result is None

    @patch("ami.cli_components.selection_dialog.read_key_sequence")
    @patch("ami.cli_components.selection_dialog.TUI")
    def test_run_ignores_non_string_keys(self, mock_tui, mock_read_key):
        """Test run ignores non-string key values."""
        mock_tui.draw_box.return_value = 3
        mock_read_key.side_effect = [None, 123, ENTER]  # Non-strings then Enter
        dialog = SelectionDialog(["A"])

        result = dialog.run()

        assert result["label"] == "A"
