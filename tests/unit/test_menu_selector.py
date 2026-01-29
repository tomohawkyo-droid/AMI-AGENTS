"""Unit tests for menu_selector module."""

from unittest.mock import MagicMock, patch

from ami.cli_components.menu_selector import (
    MenuItem,
    MenuSelector,
    multi_menu_select,
    simple_menu_select,
)

EXPECTED_INT_MENU_VALUE = 42


class TestMenuItem:
    """Tests for MenuItem class."""

    def test_basic_initialization(self) -> None:
        """Test basic MenuItem initialization."""
        item: MenuItem = MenuItem("id1", "Label 1")
        assert item.id == "id1"
        assert item.label == "Label 1"
        assert item.value == "id1"  # Default value is id
        assert item.description == ""
        assert item.is_header is False

    def test_with_value(self) -> None:
        """Test MenuItem with explicit value."""
        item: MenuItem[str] = MenuItem("id1", "Label 1", value="custom_value")
        assert item.value == "custom_value"

    def test_with_description(self) -> None:
        """Test MenuItem with description."""
        item: MenuItem[str] = MenuItem("id1", "Label 1", description="A description")
        assert item.description == "A description"

    def test_header_item(self) -> None:
        """Test MenuItem as header."""
        item: MenuItem[str] = MenuItem("header", "Section Header", is_header=True)
        assert item.is_header is True

    def test_generic_value_type(self) -> None:
        """Test MenuItem with different value types."""
        # String value
        item_str = MenuItem[str]("id", "Label", "string_value")
        assert item_str.value == "string_value"

        # Int value
        item_int = MenuItem[int]("id", "Label", 42)
        assert item_int.value == EXPECTED_INT_MENU_VALUE

        # Dict value
        item_dict = MenuItem[dict]("id", "Label", {"key": "value"})
        assert item_dict.value == {"key": "value"}


class TestMenuSelector:
    """Tests for MenuSelector class."""

    @patch("ami.cli_components.menu_selector.SelectionDialog")
    def test_initialization(self, mock_dialog_class) -> None:
        """Test MenuSelector initialization."""
        items: list[MenuItem] = [MenuItem("1", "Option 1"), MenuItem("2", "Option 2")]
        selector: MenuSelector = MenuSelector(items, title="Test Menu")

        mock_dialog_class.assert_called_once()
        assert selector._items == items

    @patch("ami.cli_components.menu_selector.SelectionDialog")
    def test_run_returns_none_on_cancel(self, mock_dialog_class) -> None:
        """Test MenuSelector returns None when cancelled."""
        mock_dialog = MagicMock()
        mock_dialog.run.return_value = None
        mock_dialog_class.return_value = mock_dialog

        items: list[MenuItem] = [MenuItem("1", "Option 1")]
        selector: MenuSelector = MenuSelector(items)
        result = selector.run()

        assert result is None

    @patch("ami.cli_components.menu_selector.SelectionDialog")
    def test_run_returns_selected_items(self, mock_dialog_class) -> None:
        """Test MenuSelector returns selected items."""
        item1 = MenuItem("1", "Option 1", "value1")
        item2 = MenuItem("2", "Option 2", "value2")

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = [item1]
        mock_dialog_class.return_value = mock_dialog

        selector: MenuSelector = MenuSelector([item1, item2])
        result = selector.run()

        assert result is not None
        assert len(result) == 1
        assert result[0].value == "value1"

    @patch("ami.cli_components.menu_selector.SelectionDialog")
    def test_run_with_single_result(self, mock_dialog_class) -> None:
        """Test MenuSelector wraps single result in list."""
        item1: MenuItem = MenuItem("1", "Option 1")

        mock_dialog = MagicMock()
        mock_dialog.run.return_value = item1  # Single item, not list
        mock_dialog_class.return_value = mock_dialog

        selector: MenuSelector = MenuSelector([item1])
        result = selector.run()

        assert result is not None
        assert len(result) == 1

    @patch("ami.cli_components.menu_selector.SelectionDialog")
    def test_multi_select_mode(self, mock_dialog_class) -> None:
        """Test MenuSelector in multi-select mode."""
        items: list[MenuItem] = [MenuItem("1", "A"), MenuItem("2", "B")]
        MenuSelector(items, allow_multiple=True)

        # Verify config was passed with multi=True
        call_args = mock_dialog_class.call_args
        config = call_args[0][1]  # Second positional arg is config
        assert config.multi is True


class TestSimpleMenuSelect:
    """Tests for simple_menu_select function."""

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_returns_selected_value(self, mock_selector_class) -> None:
        """Test simple_menu_select returns the selected value."""
        mock_item = MagicMock()
        mock_item.value = "Option B"

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item]
        mock_selector_class.return_value = mock_selector

        result = simple_menu_select(["Option A", "Option B", "Option C"])

        assert result == "Option B"

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_returns_none_on_cancel(self, mock_selector_class) -> None:
        """Test simple_menu_select returns None when cancelled."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        result = simple_menu_select(["A", "B"])

        assert result is None

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_returns_none_on_empty_result(self, mock_selector_class) -> None:
        """Test simple_menu_select returns None on empty result."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = []
        mock_selector_class.return_value = mock_selector

        result = simple_menu_select(["A", "B"])

        assert result is None

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_with_custom_title(self, mock_selector_class) -> None:
        """Test simple_menu_select with custom title."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        simple_menu_select(["A", "B"], title="Custom Title")

        # Verify MenuSelector was created with custom title (positional arg)
        mock_selector_class.assert_called_once()
        call_args = mock_selector_class.call_args
        # Title is second positional argument
        assert call_args[0][1] == "Custom Title"


class TestMultiMenuSelect:
    """Tests for multi_menu_select function."""

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_returns_selected_values(self, mock_selector_class) -> None:
        """Test multi_menu_select returns list of selected values."""
        mock_item1 = MagicMock()
        mock_item1.value = "A"
        mock_item2 = MagicMock()
        mock_item2.value = "C"

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item1, mock_item2]
        mock_selector_class.return_value = mock_selector

        result = multi_menu_select(["A", "B", "C"])

        assert result == ["A", "C"]

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_returns_none_on_cancel(self, mock_selector_class) -> None:
        """Test multi_menu_select returns None when cancelled."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        result = multi_menu_select(["A", "B"])

        assert result is None

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_allows_multiple_selection(self, mock_selector_class) -> None:
        """Test multi_menu_select enables multiple selection."""
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        multi_menu_select(["A", "B"])

        call_args = mock_selector_class.call_args
        assert call_args[1]["allow_multiple"] is True

    @patch("ami.cli_components.menu_selector.MenuSelector")
    def test_filters_none_values(self, mock_selector_class) -> None:
        """Test multi_menu_select filters out None values."""
        mock_item1 = MagicMock()
        mock_item1.value = "A"
        mock_item2 = MagicMock()
        mock_item2.value = None

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item1, mock_item2]
        mock_selector_class.return_value = mock_selector

        result = multi_menu_select(["A", "B"])

        assert result == ["A"]
