"""Unit tests for SelectionDialog - config, init, items, keys, and selection."""

from ami.cli_components.selection_dialog import (
    DEFAULT_DIALOG_WIDTH,
    DEFAULT_MAX_HEIGHT,
    DOWN,
    ENTER,
    ESC,
    INDENT_CHILD,
    TRUNCATION_SUFFIX,
    UP,
    SelectionDialog,
    SelectionDialogConfig,
)

EXPECTED_DIALOG_WIDTH = 80
EXPECTED_MAX_HEIGHT = 10
EXPECTED_DEFAULT_CONFIG_WIDTH = 80
EXPECTED_DEFAULT_CONFIG_MAX_HEIGHT = 10
EXPECTED_CUSTOM_WIDTH = 100
EXPECTED_CUSTOM_MAX_HEIGHT = 15
EXPECTED_STRING_ITEM_COUNT = 3
EXPECTED_DICT_ITEM_COUNT = 2
EXPECTED_CONFIG_WIDTH = 60
EXPECTED_ITEM_C_INDEX = 2
EXPECTED_PROCESSED_STRING_ITEM_COUNT = 2
EXPECTED_PROCESSED_UNKNOWN_ITEM_COUNT = 2
EXPECTED_UNKNOWN_ITEM_VALUE = 42
EXPECTED_GROUP_RANGE_COUNT = 2
EXPECTED_GROUP_CHILD_INDEX = 2
EXPECTED_GROUP_DESELECT_INDEX = 2
EXPECTED_MULTI_SELECTION_COUNT = 2


class TestConstants:
    """Tests for module constants."""

    def test_key_constants(self):
        """Test key constants are defined correctly."""
        assert UP == "UP"
        assert DOWN == "DOWN"
        assert ENTER == "ENTER"
        assert ESC == "ESC"

    def test_default_values(self):
        """Test default value constants."""
        assert DEFAULT_DIALOG_WIDTH == EXPECTED_DIALOG_WIDTH
        assert DEFAULT_MAX_HEIGHT == EXPECTED_MAX_HEIGHT
        assert TRUNCATION_SUFFIX == "..."
        assert INDENT_CHILD == "   "


class TestSelectionDialogConfig:
    """Tests for SelectionDialogConfig class."""

    def test_default_init(self):
        """Test default initialization."""
        config = SelectionDialogConfig()
        assert config.title == "Select"
        assert config.width == EXPECTED_DEFAULT_CONFIG_WIDTH
        assert config.multi is False
        assert config.max_height == EXPECTED_DEFAULT_CONFIG_MAX_HEIGHT
        assert config.preselected == set()

    def test_custom_init(self):
        """Test custom initialization."""
        preselected = {"item1", "item2"}
        config = SelectionDialogConfig(
            title="Custom Title",
            width=100,
            multi=True,
            max_height=15,
            preselected=preselected,
        )
        assert config.title == "Custom Title"
        assert config.width == EXPECTED_CUSTOM_WIDTH
        assert config.multi is True
        assert config.max_height == EXPECTED_CUSTOM_MAX_HEIGHT
        assert config.preselected == preselected

    def test_omitted_preselected_becomes_empty_set(self):
        """Test omitted preselected becomes empty set."""
        config = SelectionDialogConfig()
        assert config.preselected == set()


class TestSelectionDialogInit:
    """Tests for SelectionDialog initialization."""

    def test_init_with_string_items(self):
        """Test initialization with string items."""
        items = ["Item 1", "Item 2", "Item 3"]
        dialog = SelectionDialog(items)

        assert len(dialog.items) == EXPECTED_STRING_ITEM_COUNT
        assert dialog.items[0]["label"] == "Item 1"
        assert dialog.items[0]["value"] == "Item 1"
        assert dialog.items[0]["is_header"] is False

    def test_init_with_dict_items(self):
        """Test initialization with dict items."""
        items = [
            {"label": "First", "value": "1", "is_header": False},
            {"label": "Second", "value": "2", "is_header": False},
        ]
        dialog = SelectionDialog(items)

        assert len(dialog.items) == EXPECTED_DICT_ITEM_COUNT
        assert dialog.items[0]["label"] == "First"
        assert dialog.items[1]["value"] == "2"

    def test_init_with_config(self):
        """Test initialization with config object."""
        config = SelectionDialogConfig(title="Test", width=60, multi=True)
        dialog = SelectionDialog(["Item"], config)

        assert dialog.title == "Test"
        assert dialog.width == EXPECTED_CONFIG_WIDTH
        assert dialog.multi is True

    def test_init_defaults(self):
        """Test initialization defaults."""
        dialog = SelectionDialog(["Item"])

        assert dialog.cursor == 0
        assert dialog.scroll_offset == 0
        assert dialog.selected == set()
        assert dialog._last_render_lines == 0

    def test_init_with_preselected(self):
        """Test initialization with preselected items."""
        items = [
            {"id": "a", "label": "A", "value": "a", "is_header": False},
            {"id": "b", "label": "B", "value": "b", "is_header": False},
            {"id": "c", "label": "C", "value": "c", "is_header": False},
        ]
        config = SelectionDialogConfig(preselected={"a", "c"})
        dialog = SelectionDialog(items, config)

        assert 0 in dialog.selected  # index of item "a"
        assert EXPECTED_ITEM_C_INDEX in dialog.selected  # index of item "c"
        assert 1 not in dialog.selected


class TestProcessItems:
    """Tests for _process_items method."""

    def test_process_string_items(self):
        """Test processing string items."""
        dialog = SelectionDialog([])
        dialog.items = []
        dialog._process_items(["One", "Two"])

        assert len(dialog.items) == EXPECTED_PROCESSED_STRING_ITEM_COUNT
        assert dialog.items[0] == {"label": "One", "value": "One", "is_header": False}
        assert dialog.items[1] == {"label": "Two", "value": "Two", "is_header": False}

    def test_process_dict_items(self):
        """Test processing dict items."""
        dialog = SelectionDialog([])
        dialog.items = []
        dict_item = {"label": "Test", "value": 123, "is_header": True}
        dialog._process_items([dict_item])

        assert len(dialog.items) == 1
        assert dialog.items[0] == dict_item

    def test_process_unknown_type(self):
        """Test processing unknown type items."""
        dialog = SelectionDialog([])
        dialog.items = []
        dialog._process_items([42, 3.14])

        assert len(dialog.items) == EXPECTED_PROCESSED_UNKNOWN_ITEM_COUNT
        assert dialog.items[0]["label"] == "42"
        assert dialog.items[0]["value"] == EXPECTED_UNKNOWN_ITEM_VALUE
        assert dialog.items[1]["label"] == "3.14"


class TestBuildGroupRanges:
    """Tests for _build_group_ranges method."""

    def test_no_headers(self):
        """Test building ranges with no headers."""
        items = [
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items)

        assert dialog.group_ranges == []

    def test_single_group(self):
        """Test building ranges with single group."""
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items)

        assert len(dialog.group_ranges) == 1
        assert dialog.group_ranges[0] == (0, 1, 3)  # header_idx, start, end

    def test_multiple_groups(self):
        """Test building ranges with multiple groups."""
        items = [
            {"id": "_header_1", "label": "Group 1", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"id": "_header_2", "label": "Group 2", "value": "", "is_header": True},
            {"label": "B", "value": "b", "is_header": False},
            {"label": "C", "value": "c", "is_header": False},
        ]
        dialog = SelectionDialog(items)

        assert len(dialog.group_ranges) == EXPECTED_GROUP_RANGE_COUNT
        assert dialog.group_ranges[0] == (0, 1, 2)
        assert dialog.group_ranges[1] == (2, 3, 5)


class TestIsHeader:
    """Tests for _is_header method."""

    def test_header_by_id_prefix(self):
        """Test header detection by ID prefix."""
        dialog = SelectionDialog(["dummy"])
        item = {"id": "_header_test", "label": "Test", "value": "", "is_header": False}

        assert dialog._is_header(item) is True

    def test_header_by_flag(self):
        """Test header detection by is_header flag."""
        dialog = SelectionDialog(["dummy"])
        item = {"id": "normal", "label": "Test", "value": "", "is_header": True}

        assert dialog._is_header(item) is True

    def test_not_header(self):
        """Test non-header item."""
        dialog = SelectionDialog(["dummy"])
        item = {"id": "normal", "label": "Test", "value": "", "is_header": False}

        assert dialog._is_header(item) is False

    def test_header_without_id(self):
        """Test header detection without id field."""
        dialog = SelectionDialog(["dummy"])
        item = {"label": "Test", "value": "", "is_header": True}

        assert dialog._is_header(item) is True


class TestGetGroupItems:
    """Tests for _get_group_items method."""

    def test_get_existing_group(self):
        """Test getting items for existing group."""
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items)

        result = dialog._get_group_items(0)  # header at index 0

        assert result == [1, 2]

    def test_get_nonexistent_group(self):
        """Test getting items for nonexistent group."""
        dialog = SelectionDialog(["Item"])

        result = dialog._get_group_items(99)

        assert result == []


class TestHandleKey:
    """Tests for _handle_key method."""

    def test_up_key_moves_cursor(self):
        """Test UP key moves cursor up."""
        dialog = SelectionDialog(["A", "B", "C"])
        dialog.cursor = 2

        should_continue, result = dialog._handle_key(UP)

        assert should_continue is True
        assert result is None
        assert dialog.cursor == 1

    def test_up_key_at_top_does_nothing(self):
        """Test UP key at top doesn't move cursor."""
        dialog = SelectionDialog(["A", "B"])
        dialog.cursor = 0

        _should_continue, _result = dialog._handle_key(UP)

        assert dialog.cursor == 0

    def test_down_key_moves_cursor(self):
        """Test DOWN key moves cursor down."""
        dialog = SelectionDialog(["A", "B", "C"])
        dialog.cursor = 0

        should_continue, _result = dialog._handle_key(DOWN)

        assert should_continue is True
        assert dialog.cursor == 1

    def test_down_key_at_bottom_does_nothing(self):
        """Test DOWN key at bottom doesn't move cursor."""
        dialog = SelectionDialog(["A", "B"])
        dialog.cursor = 1

        _should_continue, _result = dialog._handle_key(DOWN)

        assert dialog.cursor == 1

    def test_space_toggles_selection_in_multi(self):
        """Test space key toggles selection in multi mode."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A", "B"], config)
        dialog.cursor = 0

        dialog._handle_key(" ")

        assert 0 in dialog.selected

        dialog._handle_key(" ")

        assert 0 not in dialog.selected

    def test_space_ignored_in_single_mode(self):
        """Test space key ignored in single mode."""
        dialog = SelectionDialog(["A", "B"])
        dialog.cursor = 0

        dialog._handle_key(" ")

        assert dialog.selected == set()

    def test_a_key_selects_all(self):
        """Test 'a' key selects all in multi mode."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A", "B", "C"], config)

        dialog._handle_key("a")

        assert dialog.selected == {0, 1, 2}

    def test_n_key_deselects_all(self):
        """Test 'n' key deselects all in multi mode."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A", "B", "C"], config)
        dialog.selected = {0, 1, 2}

        dialog._handle_key("n")

        assert dialog.selected == set()

    def test_enter_returns_selection(self):
        """Test ENTER key returns selection."""
        dialog = SelectionDialog(["A", "B"])
        dialog.cursor = 1

        should_continue, result = dialog._handle_key(ENTER)

        assert should_continue is False
        assert result["label"] == "B"

    def test_esc_returns_none(self):
        """Test ESC key returns None."""
        dialog = SelectionDialog(["A", "B"])

        should_continue, result = dialog._handle_key(ESC)

        assert should_continue is False
        assert result is None


class TestToggleSelection:
    """Tests for _toggle_selection method."""

    def test_toggle_single_item(self):
        """Test toggling single item."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A", "B"], config)
        dialog.cursor = 0

        dialog._toggle_selection()
        assert 0 in dialog.selected

        dialog._toggle_selection()
        assert 0 not in dialog.selected

    def test_toggle_group_header_selects_all(self):
        """Test toggling group header selects all group items."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.cursor = 0  # On header

        dialog._toggle_selection()

        assert 1 in dialog.selected
        assert EXPECTED_GROUP_CHILD_INDEX in dialog.selected

    def test_toggle_group_header_deselects_all(self):
        """Test toggling fully selected group deselects all."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Group", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
            {"label": "B", "value": "b", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.cursor = 0
        dialog.selected = {1, 2}  # All group items selected

        dialog._toggle_selection()

        assert 1 not in dialog.selected
        assert EXPECTED_GROUP_DESELECT_INDEX not in dialog.selected


class TestGetSelection:
    """Tests for _get_selection method."""

    def test_single_mode_returns_item(self):
        """Test single mode returns current item."""
        dialog = SelectionDialog(["A", "B", "C"])
        dialog.cursor = 1

        result = dialog._get_selection()

        assert result["label"] == "B"

    def test_multi_mode_returns_selected_list(self):
        """Test multi mode returns list of selected items."""
        config = SelectionDialogConfig(multi=True)
        dialog = SelectionDialog(["A", "B", "C"], config)
        dialog.selected = {0, 2}

        result = dialog._get_selection()

        assert len(result) == EXPECTED_MULTI_SELECTION_COUNT
        assert result[0]["label"] == "A"
        assert result[1]["label"] == "C"

    def test_multi_mode_excludes_headers(self):
        """Test multi mode excludes headers from result."""
        config = SelectionDialogConfig(multi=True)
        items = [
            {"id": "_header_1", "label": "Header", "value": "", "is_header": True},
            {"label": "A", "value": "a", "is_header": False},
        ]
        dialog = SelectionDialog(items, config)
        dialog.selected = {0, 1}  # Both header and item selected

        result = dialog._get_selection()

        assert len(result) == 1
        assert result[0]["label"] == "A"
