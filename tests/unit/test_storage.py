"""Unit tests for ami/cli_components/storage.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ami.cli_components import storage


@pytest.fixture
def mock_disk_usage():
    """psutil.disk_usage returns 50% used of 1TB."""
    usage = MagicMock(percent=50.0, used=500_000_000_000, total=1_000_000_000_000)
    with patch("ami.cli_components.storage.psutil.disk_usage", return_value=usage):
        yield usage


class TestPrintRootDisk:
    def test_renders_label_and_size(self, mock_disk_usage, capsys) -> None:
        storage._print_root_disk()
        out = capsys.readouterr().out
        assert "Root Disk" in out
        # Sizes get rendered via get_size_str -> "465.7GB" style output
        assert "GB" in out


class TestPrintContainerSizes:
    def test_empty(self, capsys) -> None:
        with patch("ami.cli_components.storage.get_container_sizes", return_value=[]):
            storage._print_container_sizes()
        out = capsys.readouterr().out
        assert "Container Sizes" in out
        assert "No containers" in out

    def test_renders_each_container(self, capsys) -> None:
        sizes = [
            {"name": "ami-keycloak", "writable": "22kB", "virtual": "198MB"},
            {"name": "ami-openbao", "writable": "5MB", "virtual": "150MB"},
        ]
        with patch(
            "ami.cli_components.storage.get_container_sizes", return_value=sizes
        ):
            storage._print_container_sizes()
        out = capsys.readouterr().out
        assert "ami-keycloak" in out
        assert "writable=22kB" in out
        assert "virtual=198MB" in out
        assert "ami-openbao" in out


class TestMain:
    def test_default_runs_all_three_sections(self, mock_disk_usage, capsys) -> None:
        with (
            patch("ami.cli_components.storage.analyze") as mock_analyze,
            patch("ami.cli_components.storage.get_container_sizes", return_value=[]),
            patch("sys.argv", ["ami-storage"]),
        ):
            rc = storage.main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "Root Disk" in out
        assert "Container Sizes" in out
        mock_analyze.assert_called_once_with(".")

    def test_no_breakdown_skips_analyze(self, mock_disk_usage, capsys) -> None:
        with (
            patch("ami.cli_components.storage.analyze") as mock_analyze,
            patch("ami.cli_components.storage.get_container_sizes", return_value=[]),
            patch("sys.argv", ["ami-storage", "--no-breakdown"]),
        ):
            rc = storage.main()
        assert rc == 0
        mock_analyze.assert_not_called()

    def test_no_containers_skips_podman(self, mock_disk_usage, capsys) -> None:
        with (
            patch("ami.cli_components.storage.analyze"),
            patch("ami.cli_components.storage.get_container_sizes") as mock_sizes,
            patch("sys.argv", ["ami-storage", "--no-containers"]),
        ):
            rc = storage.main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "Container Sizes" not in out
        mock_sizes.assert_not_called()

    def test_custom_path(self, mock_disk_usage, capsys) -> None:
        with (
            patch("ami.cli_components.storage.analyze") as mock_analyze,
            patch("ami.cli_components.storage.get_container_sizes", return_value=[]),
            patch("sys.argv", ["ami-storage", "/tmp/xyz"]),
        ):
            storage.main()
        mock_analyze.assert_called_once_with("/tmp/xyz")
