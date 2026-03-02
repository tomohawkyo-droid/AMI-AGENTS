"""Unit tests for ci/check_dependency_versions module."""

import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.ci.check_dependency_versions import (
    BUILTIN_EXCLUDES,
    check_and_collect,
    get_latest_pypi_version,
    main,
    parse_dependency,
    upgrade_pyproject,
)
from ami.ci.types import LooseDependency, OutdatedDependency


class TestConstants:
    """Tests for module constants."""

    def test_builtin_excludes_contains_torch(self) -> None:
        """Test BUILTIN_EXCLUDES contains torch-related packages."""
        assert "torch" in BUILTIN_EXCLUDES
        assert "torchvision" in BUILTIN_EXCLUDES
        assert "torchaudio" in BUILTIN_EXCLUDES


class TestGetLatestPypiVersion:
    """Tests for get_latest_pypi_version function."""

    @patch("ami.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_version_on_success(self, mock_urlopen) -> None:
        """Test returns version when PyPI API succeeds."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "8.0.0"}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        version = get_latest_pypi_version("pytest")

        assert version == "8.0.0"

    @patch("ami.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_none_on_url_error(self, mock_urlopen) -> None:
        """Test returns None when URL request fails."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        version = get_latest_pypi_version("nonexistent-package")

        assert version is None

    @patch("ami.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_none_on_json_error(self, mock_urlopen) -> None:
        """Test returns None when JSON parsing fails."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        version = get_latest_pypi_version("pytest")

        assert version is None

    @patch("ami.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_none_when_version_missing(self, mock_urlopen) -> None:
        """Test returns None when version key missing in response."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        version = get_latest_pypi_version("pytest")

        assert version is None


class TestParseDependency:
    """Tests for parse_dependency function."""

    def test_parses_strict_pin(self) -> None:
        """Test parsing dependency with strict pin."""
        name, extras, op, version = parse_dependency("pytest==8.0.0")

        assert name == "pytest"
        assert extras is None
        assert op == "=="
        assert version == "8.0.0"

    def test_parses_loose_constraint_gte(self) -> None:
        """Test parsing dependency with >= constraint."""
        name, _extras, op, version = parse_dependency("requests>=2.25.0")

        assert name == "requests"
        assert op == ">="
        assert version == "2.25.0"

    def test_parses_loose_constraint_tilde(self) -> None:
        """Test parsing dependency with ~= constraint."""
        name, _extras, op, version = parse_dependency("flask~=2.0")

        assert name == "flask"
        assert op == "~="
        assert version == "2.0"

    def test_parses_unpinned(self) -> None:
        """Test parsing unpinned dependency."""
        name, extras, op, version = parse_dependency("numpy")

        assert name == "numpy"
        assert extras is None
        assert op is None
        assert version is None

    def test_parses_with_extras(self) -> None:
        """Test parsing dependency with extras."""
        name, extras, op, version = parse_dependency("uvicorn[standard]==0.29.0")

        assert name == "uvicorn"
        assert extras == "[standard]"
        assert op == "=="
        assert version == "0.29.0"

    def test_parses_with_environment_marker(self) -> None:
        """Test parsing dependency with environment marker."""
        name, _extras, op, version = parse_dependency(
            'colorama==0.4.6; sys_platform=="win32"'
        )

        assert name == "colorama"
        assert op == "=="
        assert version == "0.4.6"

    def test_handles_whitespace(self) -> None:
        """Test handles whitespace in dependency string."""
        name, _extras, op, version = parse_dependency("  pytest==8.0.0  ")

        assert name == "pytest"
        assert op == "=="
        assert version == "8.0.0"


class TestCheckAndCollect:
    """Tests for check_and_collect function."""

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_detects_loose_constraint(self, mock_pypi, tmp_path: Path) -> None:
        """Test detects loose constraint."""
        mock_pypi.return_value = "2.0.0"
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["numpy>=1.20.0"]
""")

        loose, _outdated, _data = check_and_collect(pyproject, set())

        assert len(loose) == 1
        assert loose[0][0] == "numpy"

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_detects_outdated_dependency(self, mock_pypi, tmp_path: Path) -> None:
        """Test detects outdated dependency."""
        mock_pypi.return_value = "2.0.0"
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["numpy==1.20.0"]
""")

        loose, outdated, _data = check_and_collect(pyproject, set())

        assert loose == []
        assert len(outdated) == 1
        assert outdated[0][0] == "numpy"
        assert outdated[0][2] == "1.20.0"
        assert outdated[0][3] == "2.0.0"

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_skips_builtin_excludes(self, mock_pypi, tmp_path: Path) -> None:
        """Test skips builtin excluded packages."""
        mock_pypi.return_value = "2.0.0"
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["torch>=1.0.0", "torchvision"]
""")

        loose, outdated, _data = check_and_collect(pyproject, set())

        assert loose == []
        assert outdated == []
        mock_pypi.assert_not_called()

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_checks_optional_dependencies(self, mock_pypi, tmp_path: Path) -> None:
        """Test checks optional dependencies."""
        mock_pypi.return_value = "8.0.0"
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0.0"]
""")

        loose, _outdated, _data = check_and_collect(pyproject, set())

        assert len(loose) == 1
        assert "pytest" in loose[0][0]

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_skips_duplicate_packages(self, mock_pypi, tmp_path: Path) -> None:
        """Test skips duplicate packages."""
        mock_pypi.return_value = "2.0.0"
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["numpy==1.20.0"]

[project.optional-dependencies]
dev = ["numpy==1.20.0"]
""")

        _loose, _outdated, _data = check_and_collect(pyproject, set())

        # Should only check numpy once
        assert mock_pypi.call_count == 1

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_respects_custom_excludes(self, mock_pypi, tmp_path: Path) -> None:
        """Test respects custom exclusion list."""
        mock_pypi.return_value = "2.0.0"
        pyproject = tmp_path / "pyproject.toml"
        # Use requests instead of pandas - pandas is in BUILTIN_EXCLUDES
        pyproject.write_text("""
[project]
dependencies = ["numpy>=1.0.0", "requests>=1.0.0"]
""")

        loose, _outdated, _data = check_and_collect(pyproject, {"numpy"})

        # Only requests should be checked (pandas is in BUILTIN_EXCLUDES)
        assert len(loose) == 1
        assert loose[0][0] == "requests"

    @patch("ami.ci.check_dependency_versions.get_latest_pypi_version")
    def test_skips_when_pypi_returns_none(self, mock_pypi, tmp_path: Path) -> None:
        """Test skips when PyPI lookup fails."""
        mock_pypi.return_value = None
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["custom-pkg==1.0.0"]
""")

        loose, outdated, _data = check_and_collect(pyproject, set())

        assert loose == []
        assert outdated == []


class TestUpgradePyproject:
    """Tests for upgrade_pyproject function."""

    def test_upgrades_loose_constraints(self, tmp_path: Path) -> None:
        """Test upgrades loose constraints to strict pins."""
        pyproject = tmp_path / "pyproject.toml"
        # Use multi-line array format (regex requires lines starting with whitespace)
        pyproject.write_text("""[project]
dependencies = [
    "numpy>=1.0.0",
]
""")

        loose = [LooseDependency("numpy", "numpy>=1.0.0", "2.0.0")]
        upgrade_pyproject(pyproject, loose, [])

        content = pyproject.read_text()
        assert "numpy==2.0.0" in content

    def test_upgrades_outdated_versions(self, tmp_path: Path) -> None:
        """Test upgrades outdated versions."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
dependencies = [
    "numpy==1.0.0",
]
""")

        outdated = [OutdatedDependency("numpy", None, "1.0.0", "2.0.0")]
        upgrade_pyproject(pyproject, [], outdated)

        content = pyproject.read_text()
        assert "numpy==2.0.0" in content

    def test_upgrades_with_extras(self, tmp_path: Path) -> None:
        """Test upgrades packages with extras."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
dependencies = [
    "uvicorn[standard]==0.29.0",
]
""")

        outdated = [OutdatedDependency("uvicorn", "[standard]", "0.29.0", "0.30.0")]
        upgrade_pyproject(pyproject, [], outdated)

        content = pyproject.read_text()
        assert "uvicorn[standard]==0.30.0" in content


class TestMain:
    """Tests for main function."""

    @patch("ami.ci.check_dependency_versions.check_and_collect")
    @patch("ami.ci.check_dependency_versions.Path")
    def test_returns_zero_when_all_pass(self, mock_path_class, mock_check) -> None:
        """Test returns 0 when all dependencies pass."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        mock_check.return_value = ([], [], {})

        with patch("sys.argv", ["check_dependency_versions.py"]):
            result = main()

        assert result == 0

    @patch("ami.ci.check_dependency_versions.check_and_collect")
    @patch("ami.ci.check_dependency_versions.Path")
    def test_returns_one_for_loose_constraints(
        self, mock_path_class, mock_check
    ) -> None:
        """Test returns 1 when loose constraints found."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        mock_check.return_value = (
            [LooseDependency("numpy", "numpy>=1.0", "2.0")],
            [],
            {},
        )

        with patch("sys.argv", ["check_dependency_versions.py"]):
            result = main()

        assert result == 1

    @patch("ami.ci.check_dependency_versions.check_and_collect")
    @patch("ami.ci.check_dependency_versions.Path")
    def test_returns_one_for_outdated(self, mock_path_class, mock_check) -> None:
        """Test returns 1 when outdated dependencies found."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        mock_check.return_value = (
            [],
            [OutdatedDependency("numpy", None, "1.0", "2.0")],
            {},
        )

        with patch("sys.argv", ["check_dependency_versions.py"]):
            result = main()

        assert result == 1

    @patch("ami.ci.check_dependency_versions.Path")
    def test_returns_one_for_missing_pyproject(self, mock_path_class) -> None:
        """Test returns 1 when pyproject.toml missing."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        with patch("sys.argv", ["check_dependency_versions.py"]):
            result = main()

        assert result == 1

    @patch("ami.ci.check_dependency_versions.upgrade_pyproject")
    @patch("ami.ci.check_dependency_versions.check_and_collect")
    @patch("ami.ci.check_dependency_versions.Path")
    def test_upgrade_mode(self, mock_path_class, mock_check, mock_upgrade) -> None:
        """Test upgrade mode calls upgrade_pyproject."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        mock_check.return_value = (
            [LooseDependency("numpy", "numpy>=1.0", "2.0")],
            [],
            {},
        )

        with patch("sys.argv", ["check_dependency_versions.py", "--upgrade"]):
            result = main()

        mock_upgrade.assert_called_once()
        assert result == 0
