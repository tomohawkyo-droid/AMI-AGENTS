"""Integration tests for the dependency version checker.

Exercises: scripts/ci/check_dependency_versions.py
"""

from pathlib import Path
from unittest.mock import patch

from ami.scripts.ci.check_dependency_versions import (
    BUILTIN_EXCLUDES,
    check_and_collect,
    parse_dependency,
    upgrade_pyproject,
)
from ami.types.results import LooseDependency, OutdatedDependency

# ---------------------------------------------------------------------------
# parse_dependency
# ---------------------------------------------------------------------------


class TestParseDependency:
    """Test parse_dependency with various dependency strings."""

    def test_pinned(self):
        name, extras, op, version = parse_dependency("requests==2.31.0")
        assert name == "requests"
        assert extras is None
        assert op == "=="
        assert version == "2.31.0"

    def test_pinned_with_extras(self):
        name, extras, op, version = parse_dependency("uvicorn[standard]==0.29.0")
        assert name == "uvicorn"
        assert extras == "[standard]"
        assert op == "=="
        assert version == "0.29.0"

    def test_loose_greater_equal(self):
        name, _extras, op, version = parse_dependency("flask>=2.0")
        assert name == "flask"
        assert op == ">="
        assert version == "2.0"

    def test_loose_tilde(self):
        name, _extras, op, version = parse_dependency("django~=4.2")
        assert name == "django"
        assert op == "~="
        assert version == "4.2"

    def test_no_version(self):
        name, extras, op, version = parse_dependency("pytest")
        assert name == "pytest"
        assert extras is None
        assert op is None
        assert version is None

    def test_with_environment_marker(self):
        name, _extras, op, version = parse_dependency(
            'pywin32==306; sys_platform == "win32"'
        )
        assert name == "pywin32"
        assert op == "=="
        assert version == "306"

    def test_whitespace_stripped(self):
        name, _extras, _op, version = parse_dependency("  requests==2.31.0  ")
        assert name == "requests"
        assert version == "2.31.0"

    def test_less_than(self):
        name, _extras, op, version = parse_dependency("numpy<2.0")
        assert name == "numpy"
        assert op == "<"
        assert version == "2.0"

    def test_greater_than(self):
        name, _extras, op, version = parse_dependency("scipy>1.10")
        assert name == "scipy"
        assert op == ">"
        assert version == "1.10"


# ---------------------------------------------------------------------------
# BUILTIN_EXCLUDES
# ---------------------------------------------------------------------------


class TestBuiltinExcludes:
    """Test builtin exclusion list."""

    def test_has_expected_entries(self):
        assert "torch" in BUILTIN_EXCLUDES
        assert "torchvision" in BUILTIN_EXCLUDES
        assert isinstance(BUILTIN_EXCLUDES, set)


# ---------------------------------------------------------------------------
# check_and_collect (with mocked PyPI)
# ---------------------------------------------------------------------------


class TestCheckAndCollect:
    """Test check_and_collect with mocked PyPI calls."""

    def _write_pyproject(self, path: Path, deps: list[str]) -> Path:
        toml_path = path / "pyproject.toml"
        lines = ['[project]\nname = "test"\ndependencies = [\n']
        lines.extend(f'    "{dep}",\n' for dep in deps)
        lines.append("]\n")
        toml_path.write_text("".join(lines))
        return toml_path

    def test_pinned_up_to_date(self, tmp_path: Path):
        toml = self._write_pyproject(tmp_path, ["requests==2.31.0"])
        with patch(
            "ami.scripts.ci.check_dependency_versions.get_latest_pypi_version",
            return_value="2.31.0",
        ):
            loose, outdated, _data = check_and_collect(toml, set())
        assert loose == []
        assert outdated == []

    def test_pinned_outdated(self, tmp_path: Path):
        toml = self._write_pyproject(tmp_path, ["requests==2.30.0"])
        with patch(
            "ami.scripts.ci.check_dependency_versions.get_latest_pypi_version",
            return_value="2.31.0",
        ):
            _loose, outdated, _data = check_and_collect(toml, set())
        assert len(outdated) == 1
        assert outdated[0][0] == "requests"
        assert outdated[0][3] == "2.31.0"

    def test_loose_constraint(self, tmp_path: Path):
        toml = self._write_pyproject(tmp_path, ["flask>=2.0"])
        with patch(
            "ami.scripts.ci.check_dependency_versions.get_latest_pypi_version",
            return_value="3.0.0",
        ):
            loose, _outdated, _data = check_and_collect(toml, set())
        assert len(loose) == 1
        assert loose[0][0] == "flask"

    def test_excluded_package(self, tmp_path: Path):
        toml = self._write_pyproject(tmp_path, ["torch>=2.0"])
        with patch(
            "ami.scripts.ci.check_dependency_versions.get_latest_pypi_version",
        ) as mock:
            _loose, _outdated, _data = check_and_collect(toml, set())
        mock.assert_not_called()

    def test_pypi_unreachable(self, tmp_path: Path):
        toml = self._write_pyproject(tmp_path, ["requests==2.31.0"])
        with patch(
            "ami.scripts.ci.check_dependency_versions.get_latest_pypi_version",
            return_value=None,
        ):
            loose, outdated, _data = check_and_collect(toml, set())
        assert loose == []
        assert outdated == []

    def test_custom_excludes(self, tmp_path: Path):
        toml = self._write_pyproject(tmp_path, ["mypackage>=1.0"])
        with patch(
            "ami.scripts.ci.check_dependency_versions.get_latest_pypi_version",
        ) as mock:
            _loose, _outdated, _data = check_and_collect(toml, {"mypackage"})
        mock.assert_not_called()


# ---------------------------------------------------------------------------
# upgrade_pyproject
# ---------------------------------------------------------------------------


class TestUpgradePyproject:
    """Test upgrade_pyproject rewrites versions."""

    def test_upgrade_loose(self, tmp_path: Path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[project]\nname = "test"\ndependencies = [\n    "flask>=2.0",\n]\n'
        )
        upgrade_pyproject(toml, [LooseDependency("flask", "flask>=2.0", "3.0.0")], [])
        content = toml.read_text()
        assert "flask==3.0.0" in content

    def test_upgrade_outdated(self, tmp_path: Path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[project]\nname = "test"\ndependencies = [\n    "requests==2.30.0",\n]\n'
        )
        upgrade_pyproject(
            toml, [], [OutdatedDependency("requests", None, "2.30.0", "2.31.0")]
        )
        content = toml.read_text()
        assert "requests==2.31.0" in content

    def test_upgrade_with_extras(self, tmp_path: Path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[project]\nname = "test"\ndependencies = [\n'
            '    "uvicorn[standard]==0.28.0",\n'
            "]\n"
        )
        upgrade_pyproject(
            toml, [], [OutdatedDependency("uvicorn", "[standard]", "0.28.0", "0.29.0")]
        )
        content = toml.read_text()
        assert "uvicorn[standard]==0.29.0" in content
