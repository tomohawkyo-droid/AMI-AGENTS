"""Unit tests for scripts/bootstrap_components module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.scripts.bootstrap_components import (
    AI_AGENTS,
    ALL_COMPONENTS,
    CONTAINERS,
    CORE_DEPS,
    DEV_TOOLS,
    DOCUMENTS,
    GROUPS,
    MATRIX,
    MISC,
    SECURITY,
    Component,
    ComponentStatus,
    ComponentType,
    get_component_by_name,
    get_components_by_group,
)

EXPECTED_GROUP_COUNT = 8


class TestComponentType:
    """Tests for ComponentType enum."""

    def test_script_value(self) -> None:
        """Test SCRIPT enum value."""
        assert ComponentType.SCRIPT.value == "script"

    def test_uv_value(self) -> None:
        """Test UV enum value."""
        assert ComponentType.UV.value == "uv"


class TestComponentStatus:
    """Tests for ComponentStatus model."""

    def test_creates_installed_status(self) -> None:
        """Test creates installed status."""
        status = ComponentStatus(installed=True, version="1.0.0", path="/path/to/bin")

        assert status.installed is True
        assert status.version == "1.0.0"
        assert status.path == "/path/to/bin"

    def test_creates_not_installed_status(self) -> None:
        """Test creates not-installed status."""
        status = ComponentStatus(installed=False)

        assert status.installed is False
        assert status.version is None
        assert status.path is None


class TestComponent:
    """Tests for Component model."""

    def test_creates_component(self) -> None:
        """Test creates component with required fields."""
        comp = Component(
            name="test",
            label="Test",
            description="Test component",
            type=ComponentType.SCRIPT,
            group="Test Group",
        )

        assert comp.name == "test"
        assert comp.label == "Test"
        assert comp.type == ComponentType.SCRIPT

    @patch("ami.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    def test_get_status_with_detect_path(self) -> None:
        """Test get_status with path detection."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="existing/path",
        )

        with patch.object(Path, "exists", return_value=True):
            status = comp.get_status()

        assert status.installed is True

    @patch("ami.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    def test_get_status_path_not_found(self) -> None:
        """Test get_status when path not found."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="nonexistent/path",
        )

        with patch.object(Path, "exists", return_value=False):
            status = comp.get_status()

        assert status.installed is False

    @patch("ami.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("ami.scripts.bootstrap_components.subprocess.run")
    def test_get_status_with_detect_cmd(self, mock_run) -> None:
        """Test get_status with command detection."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version 1.0.0", stderr=""
        )

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["test", "--version"],
        )

        status = comp.get_status()

        assert status.installed is True
        assert status.version == "1.0.0"

    @patch("ami.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("ami.scripts.bootstrap_components.subprocess.run")
    def test_get_status_cmd_fails(self, mock_run) -> None:
        """Test get_status when command fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["nonexistent"],
        )

        status = comp.get_status()

        assert status.installed is False

    @patch("ami.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("ami.scripts.bootstrap_components.subprocess.run")
    def test_get_status_cmd_timeout(self, mock_run) -> None:
        """Test get_status when command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["slow_cmd"],
        )

        status = comp.get_status()

        assert status.installed is False

    @patch("ami.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("ami.scripts.bootstrap_components.subprocess.run")
    def test_get_status_file_not_found(self, mock_run) -> None:
        """Test get_status when command not found."""
        mock_run.side_effect = FileNotFoundError()

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["nonexistent_binary"],
        )

        status = comp.get_status()

        assert status.installed is False


class TestExtractVersion:
    """Tests for Component._extract_version method."""

    def test_extracts_with_custom_pattern(self) -> None:
        """Test extracts version with custom pattern."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            version_pattern=r"Version: (\d+\.\d+)",
        )

        version = comp._extract_version("Version: 2.5 (stable)")

        assert version == "2.5"

    def test_extracts_semver(self) -> None:
        """Test extracts semver pattern."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("tool version 1.2.3")

        assert version == "1.2.3"

    def test_extracts_v_prefixed_version(self) -> None:
        """Test extracts v-prefixed version."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("v4.5.6")

        assert version == "4.5.6"

    def test_extracts_major_minor(self) -> None:
        """Test extracts major.minor pattern."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("release 7.8")

        assert version == "7.8"

    def test_returns_none_for_empty_output(self) -> None:
        """Test returns None for empty output."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("")

        assert version is None

    def test_returns_none_for_no_match(self) -> None:
        """Test returns None when no version found."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("no version here")

        assert version is None


class TestGetComponentsByGroup:
    """Tests for get_components_by_group function."""

    def test_returns_list_with_all_groups(self) -> None:
        """Test returns list with all groups."""
        result = get_components_by_group()
        group_names = {gc.group for gc in result}

        for group in GROUPS:
            assert group in group_names

    def test_components_in_correct_groups(self) -> None:
        """Test components are in their correct groups."""
        result = get_components_by_group()
        by_group = {gc.group: gc.components for gc in result}

        assert any(c.name == "claude" for c in by_group["AI Coding Assistants"])
        assert any(c.name == "podman" for c in by_group["Containers & Orchestration"])


class TestGetComponentByName:
    """Tests for get_component_by_name function."""

    def test_finds_existing_component(self) -> None:
        """Test finds existing component by name."""
        comp = get_component_by_name("claude")

        assert comp is not None
        assert comp.name == "claude"

    def test_returns_none_for_nonexistent(self) -> None:
        """Test returns None for nonexistent component."""
        comp = get_component_by_name("nonexistent_component")

        assert comp is None


class TestComponentLists:
    """Tests for component list constants."""

    def test_core_deps_not_empty(self) -> None:
        """Test CORE_DEPS is not empty."""
        assert len(CORE_DEPS) > 0
        assert all(c.group == "Core Dependencies" for c in CORE_DEPS)

    def test_ai_agents_not_empty(self) -> None:
        """Test AI_AGENTS is not empty."""
        assert len(AI_AGENTS) > 0
        assert all(c.group == "AI Coding Assistants" for c in AI_AGENTS)

    def test_containers_not_empty(self) -> None:
        """Test CONTAINERS is not empty."""
        assert len(CONTAINERS) > 0
        assert all(c.group == "Containers & Orchestration" for c in CONTAINERS)

    def test_dev_tools_not_empty(self) -> None:
        """Test DEV_TOOLS is not empty."""
        assert len(DEV_TOOLS) > 0
        assert all(c.group == "Development Tools" for c in DEV_TOOLS)

    def test_security_not_empty(self) -> None:
        """Test SECURITY is not empty."""
        assert len(SECURITY) > 0
        assert all(c.group == "Security & Networking" for c in SECURITY)

    def test_documents_not_empty(self) -> None:
        """Test DOCUMENTS is not empty."""
        assert len(DOCUMENTS) > 0
        assert all(c.group == "Document Processing" for c in DOCUMENTS)

    def test_matrix_not_empty(self) -> None:
        """Test MATRIX is not empty."""
        assert len(MATRIX) > 0
        assert all(c.group == "Matrix & Communication" for c in MATRIX)

    def test_misc_not_empty(self) -> None:
        """Test MISC is not empty."""
        assert len(MISC) > 0
        assert all(c.group == "Miscellaneous" for c in MISC)

    def test_all_components_has_all(self) -> None:
        """Test ALL_COMPONENTS contains all components."""
        total = (
            len(CORE_DEPS)
            + len(AI_AGENTS)
            + len(CONTAINERS)
            + len(DEV_TOOLS)
            + len(SECURITY)
            + len(DOCUMENTS)
            + len(MATRIX)
            + len(MISC)
        )
        assert len(ALL_COMPONENTS) == total


class TestGroups:
    """Tests for GROUPS constant."""

    def test_groups_not_empty(self) -> None:
        """Test GROUPS is not empty."""
        assert len(GROUPS) == EXPECTED_GROUP_COUNT

    def test_groups_contains_expected(self) -> None:
        """Test GROUPS contains expected groups."""
        expected = [
            "Core Dependencies",
            "AI Coding Assistants",
            "Containers & Orchestration",
            "Development Tools",
            "Security & Networking",
            "Document Processing",
            "Matrix & Communication",
            "Miscellaneous",
        ]
        assert expected == GROUPS
