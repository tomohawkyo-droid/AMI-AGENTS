"""Unit tests for bootstrap installer installation execution and main function."""

from unittest.mock import MagicMock, patch

from ami.scripts.bootstrap_components import Component, ComponentType
from ami.scripts.bootstrap_installer import (
    _print_summary,
    _run_installation,
    main,
)


class TestRunInstallation:
    """Tests for _run_installation function."""

    @patch("ami.scripts.bootstrap_installer._bootstrap_install.install_components")
    @patch("ami.scripts.bootstrap_installer._bootstrap_install.ensure_directories")
    def test_runs_installation(self, mock_dirs, mock_install, capsys) -> None:
        """Test runs installation."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
            package="test-pkg",
        )

        def simulate_install(comps, on_progress=None, on_result=None):
            if on_progress:
                on_progress(1, 1, "Test")
            if on_result:
                on_result(comp, True)
            return {"test": True}

        mock_install.side_effect = simulate_install

        success_count, failed = _run_installation([comp])

        assert success_count == 1
        assert failed == []
        mock_dirs.assert_called_once()

    @patch("ami.scripts.bootstrap_installer._bootstrap_install.install_components")
    @patch("ami.scripts.bootstrap_installer._bootstrap_install.ensure_directories")
    def test_tracks_failures(self, mock_dirs, mock_install, capsys) -> None:
        """Test tracks installation failures."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
            package="test-pkg",
        )

        def simulate_install(comps, on_progress=None, on_result=None):
            if on_result:
                on_result(comp, False)
            return {"test": False}

        mock_install.side_effect = simulate_install

        success_count, failed = _run_installation([comp])

        assert success_count == 0
        assert failed == ["Test"]


class TestPrintSummary:
    """Tests for _print_summary function."""

    def test_prints_success_summary(self, capsys) -> None:
        """Test prints success summary."""
        exit_code = _print_summary(5, [])

        captured = capsys.readouterr()
        assert "5 component(s) installed successfully" in captured.out
        assert "Installation complete" in captured.out
        assert exit_code == 0

    def test_prints_failure_summary(self, capsys) -> None:
        """Test prints failure summary."""
        exit_code = _print_summary(3, ["Failed1", "Failed2"])

        captured = capsys.readouterr()
        assert "Successful: 3" in captured.out
        assert "Failed: 2" in captured.out
        assert "Failed1" in captured.out
        assert "Failed2" in captured.out
        assert exit_code == 1


class TestMain:
    """Tests for main function."""

    @patch("sys.stdin")
    def test_returns_error_when_not_tty(self, mock_stdin, capsys) -> None:
        """Test returns 1 when not running in TTY."""
        mock_stdin.isatty.return_value = False

        result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "interactive terminal" in captured.out

    @patch("ami.scripts.bootstrap_installer._dialogs.multiselect")
    @patch("ami.scripts.bootstrap_installer.build_menu_items")
    @patch("ami.scripts.bootstrap_installer.scan_components")
    @patch("sys.stdin")
    def test_exits_on_cancel(
        self, mock_stdin, mock_scan, mock_build, mock_multi, capsys
    ) -> None:
        """Test exits when user cancels confirmation."""
        mock_stdin.isatty.return_value = True
        mock_scan.return_value = {}
        mock_build.return_value = ([], set())

        # Create mock selected items with actual component values
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
            package="test-pkg",
        )
        mock_item = MagicMock()
        mock_item.value = comp
        mock_multi.return_value = [mock_item]

        with patch(
            "ami.scripts.bootstrap_installer._dialogs.confirm",
            return_value=False,
        ):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "cancelled" in captured.out

    @patch("ami.scripts.bootstrap_installer._dialogs.multiselect")
    @patch("ami.scripts.bootstrap_installer.build_menu_items")
    @patch("ami.scripts.bootstrap_installer.scan_components")
    @patch("sys.stdin")
    def test_exits_when_no_selection(
        self, mock_stdin, mock_scan, mock_build, mock_multi, capsys
    ) -> None:
        """Test exits when user selects nothing."""
        mock_stdin.isatty.return_value = True
        mock_scan.return_value = {}
        mock_build.return_value = ([], set())
        mock_multi.return_value = []

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "No components selected" in captured.out

    @patch("ami.scripts.bootstrap_installer._dialogs.multiselect")
    @patch("ami.scripts.bootstrap_installer.build_menu_items")
    @patch("ami.scripts.bootstrap_installer.scan_components")
    @patch("sys.stdin")
    def test_runs_installation_on_confirm(
        self,
        mock_stdin,
        mock_scan,
        mock_build,
        mock_multi,
    ) -> None:
        """Test runs installation when user confirms."""
        mock_stdin.isatty.return_value = True
        mock_scan.return_value = {}
        mock_build.return_value = ([], set())

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.NPM,
            group="Test",
            package="test-pkg",
        )
        mock_item = MagicMock()
        mock_item.value = comp
        mock_multi.return_value = [mock_item]

        with (
            patch(
                "ami.scripts.bootstrap_installer._dialogs.confirm",
                return_value=True,
            ),
            patch(
                "ami.scripts.bootstrap_installer._run_installation",
                return_value=(1, []),
            ) as mock_install,
            patch(
                "ami.scripts.bootstrap_installer._print_summary",
                return_value=0,
            ),
        ):
            result = main()

        assert result == 0
        mock_install.assert_called_once()
