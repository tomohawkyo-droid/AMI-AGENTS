"""Unit tests for scripts/bootstrap_install module."""

from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

from ami.scripts.bootstrap_components import Component, ComponentType
from ami.scripts.bootstrap_install import (
    ensure_directories,
    get_bootstrap_dir,
    install_component,
    install_components,
    run_bootstrap_script,
)


class ProgressCall(NamedTuple):
    """Progress callback invocation data."""

    current: int
    total: int
    label: str


class ResultCall(NamedTuple):
    """Result callback invocation data."""

    component: Component
    success: bool


EXPECTED_DIRECTORY_COUNT = 2
EXPECTED_SCRIPT_INSTALL_CALL_COUNT = 2
EXPECTED_COMPONENT_RESULT_COUNT = 2


class TestEnsureDirectories:
    """Tests for ensure_directories function."""

    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/test/root"))
    def test_creates_directories(self) -> None:
        """Test creates required directories."""
        with patch.object(Path, "mkdir") as mock_mkdir:
            ensure_directories()

            # Should be called twice (for .boot-linux/bin and .venv/bin)
            assert mock_mkdir.call_count == EXPECTED_DIRECTORY_COUNT


class TestGetPaths:
    """Tests for path getter functions."""

    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/test/root"))
    def test_get_bootstrap_dir(self) -> None:
        """Test get_bootstrap_dir returns correct path."""
        result = get_bootstrap_dir()
        assert result == Path("/test/root/ami/scripts/bootstrap")


class TestRunBootstrapScript:
    """Tests for run_bootstrap_script function."""

    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    def test_returns_false_if_script_not_found(self, mock_dir) -> None:
        """Test returns False if script doesn't exist."""
        mock_dir.return_value = Path("/scripts")

        with patch.object(Path, "exists", return_value=False):
            result = run_bootstrap_script("test.sh")

        assert result is False

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/root"))
    def test_runs_script(self, mock_dir, mock_run) -> None:
        """Test runs bootstrap script."""
        mock_dir.return_value = Path("/scripts")
        mock_run.return_value = MagicMock(returncode=0)

        with patch.object(Path, "exists", return_value=True):
            result = run_bootstrap_script("test.sh")

        assert result is True
        mock_run.assert_called_once()

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/root"))
    def test_returns_false_on_script_failure(self, mock_dir, mock_run) -> None:
        """Test returns False if script fails."""
        mock_dir.return_value = Path("/scripts")
        mock_run.return_value = MagicMock(returncode=1)

        with patch.object(Path, "exists", return_value=True):
            result = run_bootstrap_script("test.sh")

        assert result is False


class TestInstallComponent:
    """Tests for install_component function."""

    @patch("ami.scripts.bootstrap_install.run_bootstrap_script", return_value=True)
    def test_installs_script_component(self, mock_run) -> None:
        """Test installs script component."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            script="test.sh",
        )

        result = install_component(comp)

        assert result is True
        mock_run.assert_called_once_with("test.sh")

    def test_returns_false_for_script_without_script(self) -> None:
        """Test returns False for script component without script."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        result = install_component(comp)

        assert result is False

    def test_returns_true_for_uv_component(self) -> None:
        """Test returns True for UV component (no action needed)."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.UV,
            group="Test",
        )

        result = install_component(comp)

        assert result is True


class TestInstallComponents:
    """Tests for install_components function."""

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_component", return_value=True)
    def test_installs_script_components_separately(
        self, mock_install, mock_dirs
    ) -> None:
        """Test installs script components one at a time."""
        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.SCRIPT,
                group="Test",
                script="a.sh",
            ),
            Component(
                name="b",
                label="B",
                description="B",
                type=ComponentType.SCRIPT,
                group="Test",
                script="b.sh",
            ),
        ]

        results = install_components(comps)

        # Results is now a list of InstallationResult
        assert len(results) == EXPECTED_COMPONENT_RESULT_COUNT
        names = [r["component_name"] for r in results]
        assert "a" in names
        assert "b" in names
        assert all(r["success"] for r in results)
        assert mock_install.call_count == EXPECTED_SCRIPT_INSTALL_CALL_COUNT

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_component", return_value=True)
    def test_calls_progress_callback(self, mock_install, mock_dirs) -> None:
        """Test calls progress callback."""
        progress_calls: list[ProgressCall] = []

        def on_progress(current: int, total: int, label: str) -> None:
            progress_calls.append(ProgressCall(current, total, label))

        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.SCRIPT,
                group="Test",
                script="a.sh",
            ),
        ]

        install_components(comps, on_progress=on_progress)

        assert len(progress_calls) == 1

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_component", return_value=True)
    def test_calls_result_callback(self, mock_install, mock_dirs) -> None:
        """Test calls result callback."""
        result_calls: list[ResultCall] = []

        def on_result(comp: Component, success: bool) -> None:
            result_calls.append(ResultCall(comp, success))

        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.SCRIPT,
                group="Test",
                script="a.sh",
            ),
        ]

        install_components(comps, on_result=on_result)

        assert len(result_calls) == 1
        assert result_calls[0].success is True
