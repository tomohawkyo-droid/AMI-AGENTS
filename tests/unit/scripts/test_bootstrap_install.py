"""Unit tests for scripts/bootstrap_install module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.scripts.bootstrap_components import Component, ComponentType
from ami.scripts.bootstrap_install import (
    ensure_directories,
    ensure_node_env,
    get_bootstrap_dir,
    get_node_modules_dir,
    get_npm_path,
    install_component,
    install_components,
    install_npm_packages,
    run_bootstrap_script,
)

EXPECTED_DIRECTORY_COUNT = 2
EXPECTED_SCRIPT_INSTALL_CALL_COUNT = 2


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

    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/test/root"))
    def test_get_npm_path(self) -> None:
        """Test get_npm_path returns correct path."""
        result = get_npm_path()
        assert result == Path("/test/root/.boot-linux/node-env/bin/npm")

    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/test/root"))
    def test_get_node_modules_dir(self) -> None:
        """Test get_node_modules_dir returns correct path."""
        result = get_node_modules_dir()
        assert result == Path("/test/root/.venv/node_modules")


class TestEnsureNodeEnv:
    """Tests for ensure_node_env function."""

    @patch("ami.scripts.bootstrap_install.get_npm_path")
    def test_returns_true_if_npm_exists(self, mock_npm_path) -> None:
        """Test returns True if npm already exists."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_npm_path.return_value = mock_path

        result = ensure_node_env()

        assert result is True

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_npm_path")
    def test_runs_setup_script_if_npm_missing(self, mock_npm_path, mock_run) -> None:
        """Test runs setup script if npm doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_npm_path.return_value = mock_path
        mock_run.return_value = MagicMock(returncode=0)

        result = ensure_node_env()

        assert result is True
        mock_run.assert_called_once()

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_npm_path")
    def test_returns_false_on_setup_failure(self, mock_npm_path, mock_run) -> None:
        """Test returns False if setup script fails."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_npm_path.return_value = mock_path
        mock_run.return_value = MagicMock(returncode=1)

        result = ensure_node_env()

        assert result is False

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_npm_path")
    def test_returns_false_on_exception(self, mock_npm_path, mock_run) -> None:
        """Test returns False on subprocess exception."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_npm_path.return_value = mock_path
        mock_run.side_effect = OSError("Command not found")

        result = ensure_node_env()

        assert result is False


class TestInstallNpmPackages:
    """Tests for install_npm_packages function."""

    def test_returns_true_for_empty_packages(self) -> None:
        """Test returns True for empty package list."""
        result = install_npm_packages([])

        assert result is True

    @patch("ami.scripts.bootstrap_install.ensure_node_env", return_value=False)
    def test_returns_false_if_node_env_fails(self, mock_ensure) -> None:
        """Test returns False if node env setup fails."""
        result = install_npm_packages(["package"])

        assert result is False

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_node_modules_dir")
    @patch("ami.scripts.bootstrap_install.get_npm_path")
    @patch("ami.scripts.bootstrap_install.ensure_node_env", return_value=True)
    def test_installs_packages(
        self, mock_ensure, mock_npm_path, mock_modules, mock_run
    ) -> None:
        """Test installs npm packages."""
        mock_npm_path.return_value = Path("/npm")
        mock_modules.return_value = Path("/modules")
        mock_run.return_value = MagicMock(returncode=0)

        result = install_npm_packages(["package1", "package2"])

        assert result is True
        mock_run.assert_called_once()

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_node_modules_dir")
    @patch("ami.scripts.bootstrap_install.get_npm_path")
    @patch("ami.scripts.bootstrap_install.ensure_node_env", return_value=True)
    def test_returns_false_on_install_failure(
        self, mock_ensure, mock_npm_path, mock_modules, mock_run
    ) -> None:
        """Test returns False if npm install fails."""
        mock_npm_path.return_value = Path("/npm")
        mock_modules.return_value = Path("/modules")
        mock_run.return_value = MagicMock(returncode=1)

        result = install_npm_packages(["package"])

        assert result is False


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

    @patch("ami.scripts.bootstrap_install.install_npm_packages", return_value=True)
    def test_installs_npm_component(self, mock_install) -> None:
        """Test installs NPM component."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
            package="test-package",
        )

        result = install_component(comp)

        assert result is True
        mock_install.assert_called_once_with(["test-package"])

    def test_returns_false_for_npm_without_package(self) -> None:
        """Test returns False for NPM component without package."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
        )

        result = install_component(comp)

        assert result is False

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
    @patch("ami.scripts.bootstrap_install.install_npm_packages", return_value=True)
    def test_installs_npm_components_together(self, mock_npm, mock_dirs) -> None:
        """Test installs NPM components in batch."""
        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.NPM,
                group="Test",
                package="pkg-a",
            ),
            Component(
                name="b",
                label="B",
                description="B",
                type=ComponentType.NPM,
                group="Test",
                package="pkg-b",
            ),
        ]

        results = install_components(comps)

        assert results == {"a": True, "b": True}
        mock_npm.assert_called_once_with(["pkg-a", "pkg-b"])

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

        assert results == {"a": True, "b": True}
        assert mock_install.call_count == EXPECTED_SCRIPT_INSTALL_CALL_COUNT

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_npm_packages", return_value=True)
    def test_calls_progress_callback(self, mock_npm, mock_dirs) -> None:
        """Test calls progress callback."""
        progress_calls: list[tuple[int, int, str]] = []

        def on_progress(current: int, total: int, label: str) -> None:
            progress_calls.append((current, total, label))

        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.NPM,
                group="Test",
                package="pkg-a",
            ),
        ]

        install_components(comps, on_progress=on_progress)

        assert len(progress_calls) == 1

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_npm_packages", return_value=True)
    def test_calls_result_callback(self, mock_npm, mock_dirs) -> None:
        """Test calls result callback."""
        result_calls: list[tuple[Component, bool]] = []

        def on_result(comp: Component, success: bool) -> None:
            result_calls.append((comp, success))

        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.NPM,
                group="Test",
                package="pkg-a",
            ),
        ]

        install_components(comps, on_result=on_result)

        assert len(result_calls) == 1
        assert result_calls[0][1] is True
