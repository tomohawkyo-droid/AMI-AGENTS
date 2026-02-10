"""Unit tests for npm support in ci/check_dependency_versions module."""

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.scripts.ci.check_dependency_versions import (
    _is_npm_file,
    check_npm_and_collect,
    get_latest_npm_version,
    main,
    parse_npm_dependency,
    upgrade_package_json,
)
from ami.types.results import LooseDependency, OutdatedDependency


class TestGetLatestNpmVersion:
    """Tests for get_latest_npm_version function."""

    @patch("ami.scripts.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_version_on_success(self, mock_urlopen) -> None:
        """Test returns version when npm registry API succeeds."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"version": "19.1.1"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        version = get_latest_npm_version("react")

        assert version == "19.1.1"

    @patch("ami.scripts.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_none_on_url_error(self, mock_urlopen) -> None:
        """Test returns None when URL request fails."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        version = get_latest_npm_version("nonexistent-package")

        assert version is None

    @patch("ami.scripts.ci.check_dependency_versions.urllib.request.urlopen")
    def test_returns_none_on_json_error(self, mock_urlopen) -> None:
        """Test returns None when JSON parsing fails."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        version = get_latest_npm_version("react")

        assert version is None

    @patch("ami.scripts.ci.check_dependency_versions.urllib.request.urlopen")
    def test_encodes_scoped_package(self, mock_urlopen) -> None:
        """Test properly encodes scoped npm packages in URL."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"version": "24.0.0"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        version = get_latest_npm_version("@types/node")

        assert version == "24.0.0"
        call_url = mock_urlopen.call_args[0][0]
        assert "@types%2Fnode" in call_url


class TestParseNpmDependency:
    """Tests for parse_npm_dependency function."""

    def test_strict_pin(self) -> None:
        """Test parsing exact semver version."""
        name, _extras, op, version = parse_npm_dependency("react", "19.1.1")

        assert name == "react"
        assert op == "=="
        assert version == "19.1.1"

    def test_caret_range(self) -> None:
        """Test parsing caret range."""
        name, _extras, op, version = parse_npm_dependency("next", "^15.5.4")

        assert name == "next"
        assert op == "^"
        assert version == "15.5.4"

    def test_tilde_range(self) -> None:
        """Test parsing tilde range."""
        name, _extras, op, version = parse_npm_dependency("eslint", "~9.0.0")

        assert name == "eslint"
        assert op == "~"
        assert version == "9.0.0"

    def test_gte_constraint(self) -> None:
        """Test parsing >= constraint."""
        name, _extras, op, version = parse_npm_dependency("zod", ">=3.0.0")

        assert name == "zod"
        assert op == ">="
        assert version == "3.0.0"

    def test_star_wildcard(self) -> None:
        """Test parsing star wildcard."""
        name, _extras, op, version = parse_npm_dependency("foo", "*")

        assert name == "foo"
        assert op is None
        assert version is None

    def test_latest_tag(self) -> None:
        """Test parsing 'latest' tag."""
        name, _extras, op, version = parse_npm_dependency("foo", "latest")

        assert name == "foo"
        assert op is None
        assert version is None

    def test_x_range_is_loose(self) -> None:
        """Test x-range treated as loose."""
        _name, _extras, op, version = parse_npm_dependency("foo", "1.x")

        assert op is None
        assert version == "1.x"

    def test_prerelease_is_strict(self) -> None:
        """Test prerelease version treated as strict."""
        _name, _extras, op, version = parse_npm_dependency("foo", "1.0.0-beta.1")

        assert op == "=="
        assert version == "1.0.0-beta.1"


class TestCheckNpmAndCollect:
    """Tests for check_npm_and_collect function."""

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_detects_loose_caret(self, mock_npm, tmp_path: Path) -> None:
        """Test detects caret range as loose."""
        mock_npm.return_value = "19.1.1"
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))

        loose, _outdated, _data = check_npm_and_collect(pkg, set())

        assert len(loose) == 1
        assert loose[0].name == "react"

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_detects_outdated(self, mock_npm, tmp_path: Path) -> None:
        """Test detects outdated strict pin."""
        mock_npm.return_value = "19.1.1"
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"react": "18.0.0"}}))

        loose, outdated, _data = check_npm_and_collect(pkg, set())

        assert loose == []
        assert len(outdated) == 1
        assert outdated[0].name == "react"
        assert outdated[0].old_version == "18.0.0"
        assert outdated[0].new_version == "19.1.1"

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_up_to_date_passes(self, mock_npm, tmp_path: Path) -> None:
        """Test up-to-date strict pin passes."""
        mock_npm.return_value = "19.1.1"
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"react": "19.1.1"}}))

        loose, outdated, _data = check_npm_and_collect(pkg, set())

        assert loose == []
        assert outdated == []

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_checks_dev_dependencies(self, mock_npm, tmp_path: Path) -> None:
        """Test checks devDependencies."""
        mock_npm.return_value = "10.0.0"
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"devDependencies": {"eslint": "^9.0.0"}}))

        loose, _outdated, _data = check_npm_and_collect(pkg, set())

        assert len(loose) == 1
        assert loose[0].name == "eslint"

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_skips_workspace_refs(self, mock_npm, tmp_path: Path) -> None:
        """Test skips workspace: references."""
        mock_npm.return_value = "1.0.0"
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"my-lib": "workspace:*"}}))

        loose, outdated, _data = check_npm_and_collect(pkg, set())

        assert loose == []
        assert outdated == []
        mock_npm.assert_not_called()

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_respects_excludes(self, mock_npm, tmp_path: Path) -> None:
        """Test respects exclusion set."""
        mock_npm.return_value = "2.0.0"
        pkg = tmp_path / "package.json"
        pkg.write_text(
            json.dumps({"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}})
        )

        loose, _outdated, _data = check_npm_and_collect(pkg, {"react"})

        assert len(loose) == 1
        assert loose[0].name == "next"

    @patch("ami.scripts.ci.check_dependency_versions.get_latest_npm_version")
    def test_skips_when_registry_returns_none(self, mock_npm, tmp_path: Path) -> None:
        """Test skips when npm registry lookup fails."""
        mock_npm.return_value = None
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"private-pkg": "1.0.0"}}))

        loose, outdated, _data = check_npm_and_collect(pkg, set())

        assert loose == []
        assert outdated == []


class TestUpgradePackageJson:
    """Tests for upgrade_package_json function."""

    def test_upgrades_loose_to_strict(self, tmp_path: Path) -> None:
        """Test upgrades loose constraints to strict pins."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}, indent=2))

        loose = [LooseDependency("react", "react@^18.0.0", "19.1.1")]
        upgrade_package_json(pkg, loose, [])

        data = json.loads(pkg.read_text())
        assert data["dependencies"]["react"] == "19.1.1"

    def test_upgrades_outdated(self, tmp_path: Path) -> None:
        """Test upgrades outdated strict pins."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"react": "18.0.0"}}, indent=2))

        outdated = [OutdatedDependency("react", None, "18.0.0", "19.1.1")]
        upgrade_package_json(pkg, [], outdated)

        data = json.loads(pkg.read_text())
        assert data["dependencies"]["react"] == "19.1.1"

    def test_upgrades_dev_dependencies(self, tmp_path: Path) -> None:
        """Test upgrades devDependencies."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"devDependencies": {"eslint": "^8.0.0"}}, indent=2))

        loose = [LooseDependency("eslint", "eslint@^8.0.0", "9.36.0")]
        upgrade_package_json(pkg, loose, [])

        data = json.loads(pkg.read_text())
        assert data["devDependencies"]["eslint"] == "9.36.0"


class TestIsNpmFile:
    """Tests for _is_npm_file helper."""

    def test_package_json(self) -> None:
        """Test identifies package.json."""
        assert _is_npm_file(Path("package.json")) is True
        assert _is_npm_file(Path("projects/foo/package.json")) is True

    def test_pyproject_toml(self) -> None:
        """Test rejects pyproject.toml."""
        assert _is_npm_file(Path("pyproject.toml")) is False


class TestMainNpm:
    """Tests for main function with npm paths."""

    @patch("ami.scripts.ci.check_dependency_versions.check_npm_and_collect")
    @patch("ami.scripts.ci.check_dependency_versions.Path")
    def test_npm_all_pass(self, mock_path_class, mock_check) -> None:
        """Test returns 0 when all npm dependencies pass."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "package.json"
        mock_path_class.return_value = mock_path
        mock_check.return_value = ([], [], {})

        with patch("sys.argv", ["check_dependency_versions.py", "package.json"]):
            result = main()

        assert result == 0

    @patch("ami.scripts.ci.check_dependency_versions.check_npm_and_collect")
    @patch("ami.scripts.ci.check_dependency_versions.Path")
    def test_npm_loose_fails(self, mock_path_class, mock_check) -> None:
        """Test returns 1 when loose npm constraints found."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "package.json"
        mock_path_class.return_value = mock_path
        mock_check.return_value = (
            [LooseDependency("react", "react@^18.0.0", "19.1.1")],
            [],
            {},
        )

        with patch("sys.argv", ["check_dependency_versions.py", "package.json"]):
            result = main()

        assert result == 1

    @patch("ami.scripts.ci.check_dependency_versions.upgrade_package_json")
    @patch("ami.scripts.ci.check_dependency_versions.check_npm_and_collect")
    @patch("ami.scripts.ci.check_dependency_versions.Path")
    def test_npm_upgrade_mode(self, mock_path_class, mock_check, mock_upgrade) -> None:
        """Test upgrade mode calls upgrade_package_json for npm."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "package.json"
        mock_path_class.return_value = mock_path
        mock_check.return_value = (
            [LooseDependency("react", "react@^18.0.0", "19.1.1")],
            [],
            {},
        )

        with patch(
            "sys.argv",
            ["check_dependency_versions.py", "--upgrade", "package.json"],
        ):
            result = main()

        mock_upgrade.assert_called_once()
        assert result == 0

    @patch("ami.scripts.ci.check_dependency_versions.Path")
    def test_missing_file_returns_one(self, mock_path_class) -> None:
        """Test returns 1 when package.json not found."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        with patch("sys.argv", ["check_dependency_versions.py", "package.json"]):
            result = main()

        assert result == 1
