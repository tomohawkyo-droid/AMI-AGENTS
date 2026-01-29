"""Unit tests for bootstrap installer formatting, scanning, and menu building."""

from typing import cast
from unittest.mock import MagicMock, patch

from ami.cli_components.selection_dialog import SelectableItem
from ami.scripts.bootstrap_components import Component, ComponentStatus, ComponentType
from ami.scripts.bootstrap_installer import (
    DIM,
    GREEN,
    _extract_components,
    _show_selection_summary,
    build_menu_items,
    format_component_description,
    format_component_label,
    print_progress,
    print_section,
    print_status,
    scan_components,
)
from ami.types.results import NamedComponentStatus

EXPECTED_MENU_ITEM_COUNT = 2


class TestPrintSection:
    """Tests for print_section function."""

    def test_prints_section_header(self, capsys) -> None:
        """Test prints section header."""
        print_section("Test Section")

        captured = capsys.readouterr()
        assert "Test Section" in captured.out
        assert "\u250c" in captured.out
        assert "\u2514" in captured.out


class TestPrintStatus:
    """Tests for print_status function."""

    def test_prints_status_message(self, capsys) -> None:
        """Test prints status message with icon."""
        print_status("\u2713", "Success", GREEN)

        captured = capsys.readouterr()
        assert "\u2713" in captured.out
        assert "Success" in captured.out

    def test_prints_status_default_color(self, capsys) -> None:
        """Test prints status with default color."""
        print_status("\u2022", "Message")

        captured = capsys.readouterr()
        assert "\u2022" in captured.out
        assert "Message" in captured.out


class TestPrintProgress:
    """Tests for print_progress function."""

    def test_prints_progress_bar(self, capsys) -> None:
        """Test prints progress bar."""
        print_progress(5, 10, "Installing...")

        captured = capsys.readouterr()
        assert "5/10" in captured.out
        assert "Installing..." in captured.out
        assert "\u2588" in captured.out

    def test_prints_full_progress_bar(self, capsys) -> None:
        """Test prints full progress bar at 100%."""
        print_progress(10, 10, "Done")

        captured = capsys.readouterr()
        assert "10/10" in captured.out


class TestFormatComponentLabel:
    """Tests for format_component_label function."""

    def test_formats_installed_with_version(self) -> None:
        """Test formats installed component with version."""
        comp = Component(
            name="test",
            label="Test",
            description="Test desc",
            type=ComponentType.NPM,
            group="Test",
        )
        status = NamedComponentStatus(
            name="test", installed=True, version="1.0.0", path=None
        )

        result = format_component_label(comp, status)

        assert "Test" in result
        assert "v1.0.0" in result
        assert GREEN in result

    def test_formats_uninstalled(self) -> None:
        """Test formats uninstalled component."""
        comp = Component(
            name="test",
            label="Test",
            description="Test desc",
            type=ComponentType.NPM,
            group="Test",
        )
        status = NamedComponentStatus(
            name="test", installed=False, version=None, path=None
        )

        result = format_component_label(comp, status)

        assert result == "Test"


class TestFormatComponentDescription:
    """Tests for format_component_description function."""

    def test_formats_installed_description(self) -> None:
        """Test formats installed component description."""
        comp = Component(
            name="test",
            label="Test",
            description="Test desc",
            type=ComponentType.NPM,
            group="Test",
        )
        status = NamedComponentStatus(
            name="test", installed=True, version=None, path=None
        )

        result = format_component_description(comp, status)

        assert "Test desc" in result
        assert "\u2713" in result
        assert GREEN in result

    def test_formats_uninstalled_description(self) -> None:
        """Test formats uninstalled component description."""
        comp = Component(
            name="test",
            label="Test",
            description="Test desc",
            type=ComponentType.NPM,
            group="Test",
        )
        status = NamedComponentStatus(
            name="test", installed=False, version=None, path=None
        )

        result = format_component_description(comp, status)

        assert "Test desc" in result
        assert "(not installed)" in result
        assert DIM in result


class TestScanComponents:
    """Tests for scan_components function."""

    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.get_components_by_group"
    )
    @patch("ami.scripts.bootstrap_installer._bootstrap_components.GROUPS", ["Test"])
    def test_scans_all_components(self, mock_get_groups, capsys) -> None:
        """Test scans all components and returns status list."""
        comp = MagicMock()
        comp.name = "test"
        comp.label = "Test"
        comp.get_status.return_value = ComponentStatus(installed=True, version="1.0")
        mock_get_groups.return_value = {"Test": [comp]}

        statuses = scan_components()

        test_status = next((s for s in statuses if s.name == "test"), None)
        assert test_status is not None
        assert test_status.installed is True

    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.get_components_by_group"
    )
    @patch("ami.scripts.bootstrap_installer._bootstrap_components.GROUPS", [])
    def test_handles_empty_groups(self, mock_get_groups, capsys) -> None:
        """Test handles empty groups."""
        mock_get_groups.return_value = {}

        statuses = scan_components()

        assert statuses == []


class TestBuildMenuItems:
    """Tests for build_menu_items function."""

    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.get_components_by_group"
    )
    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.GROUPS", ["TestGroup"]
    )
    def test_builds_menu_with_headers(self, mock_get_groups) -> None:
        """Test builds menu items with group headers."""
        comp = Component(
            name="test",
            label="Test",
            description="Test desc",
            type=ComponentType.NPM,
            group="TestGroup",
        )
        mock_get_groups.return_value = {"TestGroup": [comp]}
        statuses = [
            NamedComponentStatus(name="test", installed=False, version=None, path=None)
        ]

        result = build_menu_items(statuses)
        items = cast(list[SelectableItem], result.menu_items)
        preselected = result.preselected_ids

        # Should have header + component
        assert len(items) == EXPECTED_MENU_ITEM_COUNT
        assert items[0].id == "_header_TestGroup"
        assert items[1].id == "test"
        assert preselected == set()

    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.get_components_by_group"
    )
    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.GROUPS", ["TestGroup"]
    )
    def test_preselects_installed_components(self, mock_get_groups) -> None:
        """Test preselects installed components."""
        comp = Component(
            name="test",
            label="Test",
            description="Test desc",
            type=ComponentType.NPM,
            group="TestGroup",
        )
        mock_get_groups.return_value = {"TestGroup": [comp]}
        statuses = [
            NamedComponentStatus(name="test", installed=True, version="1.0", path=None)
        ]

        result = build_menu_items(statuses)

        assert "test" in result.preselected_ids

    @patch(
        "ami.scripts.bootstrap_installer._bootstrap_components.get_components_by_group"
    )
    @patch("ami.scripts.bootstrap_installer._bootstrap_components.GROUPS", ["Empty"])
    def test_skips_empty_groups(self, mock_get_groups) -> None:
        """Test skips empty groups."""
        mock_get_groups.return_value = {"Empty": []}

        result = build_menu_items([])
        items = cast(list[SelectableItem], result.menu_items)

        assert items == []


class TestExtractComponents:
    """Tests for _extract_components function."""

    def test_extracts_component_values(self) -> None:
        """Test extracts component values from menu items."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
        )
        # Mock MenuItem
        item = MagicMock()
        item.value = comp

        result = _extract_components([item])

        assert result == [comp]

    def test_filters_string_values(self) -> None:
        """Test filters out string values (headers)."""
        item1 = MagicMock()
        item1.value = "header_string"

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
        )
        item2 = MagicMock()
        item2.value = comp

        result = _extract_components([item1, item2])

        assert len(result) == 1
        assert result[0] == comp


class TestShowSelectionSummary:
    """Tests for _show_selection_summary function."""

    def test_shows_components_to_install(self, capsys) -> None:
        """Test shows components to install."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
        )
        statuses = [
            NamedComponentStatus(name="test", installed=False, version=None, path=None)
        ]

        _show_selection_summary([comp], statuses)

        captured = capsys.readouterr()
        assert "Test" in captured.out
        assert "Selected 1 Component(s)" in captured.out

    def test_shows_reinstall_for_installed(self, capsys) -> None:
        """Test shows reinstall for installed components."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
        )
        statuses = [
            NamedComponentStatus(name="test", installed=True, version="1.0", path=None)
        ]

        _show_selection_summary([comp], statuses)

        captured = capsys.readouterr()
        assert "(reinstall)" in captured.out
