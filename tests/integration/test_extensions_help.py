"""Integration tests for extensions defined in ami/config/extensions.yaml.

Tests that extensions have valid metadata, binaries exist, and commands
are properly installed in .boot-linux/bin/.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest
import yaml


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


PROJECT_ROOT = _find_project_root()
EXTENSIONS_YAML = PROJECT_ROOT / "ami" / "config" / "extensions.yaml"
BIN_DIR = PROJECT_ROOT / ".boot-linux" / "bin"
VALID_CATEGORIES = frozenset(["core", "enterprise", "dev", "agents"])
MIN_DESCRIPTION_LENGTH = 5


class ExtensionMetadata(NamedTuple):
    """Parsed extension metadata."""

    name: str
    description: str
    category: str
    binary: str
    features: str
    hidden: bool


def get_all_extensions() -> list[ExtensionMetadata]:
    """Get all extensions from extensions.yaml (single source of truth)."""
    if not EXTENSIONS_YAML.exists():
        return []
    config = yaml.safe_load(EXTENSIONS_YAML.read_text())
    return [
        ExtensionMetadata(
            name=ext.get("name", ""),
            description=ext.get("description", ""),
            category=ext.get("category", ""),
            binary=ext.get("binary", ""),
            features=ext.get("features", ""),
            hidden=ext.get("hidden", False),
        )
        for ext in config.get("extensions", [])
    ]


def check_binary_exists(binary_path: str) -> bool:
    """Check if the binary exists relative to project root."""
    if not binary_path:
        return False
    full_path = PROJECT_ROOT / binary_path
    return full_path.exists()


def get_binary_shebang(binary_path: str) -> str | None:
    """Get the shebang line from a binary file."""
    full_path = PROJECT_ROOT / binary_path
    if not full_path.exists():
        return None
    try:
        with open(full_path, "rb") as f:
            first_line = f.readline()
            if first_line.startswith(b"#!"):
                return first_line.decode("utf-8", errors="replace").strip()
    except (OSError, UnicodeDecodeError):
        pass
    return None


def validate_shebang_paths(shebang: str) -> list[str]:
    """Validate that paths in shebang actually exist. Returns list of issues."""
    issues: list[str] = []
    if not shebang:
        return issues

    shebang_content = shebang[2:].strip()
    path_pattern = re.compile(r'(/[^\s"\']+)')
    for match in path_pattern.finditer(shebang_content):
        path = match.group(1)
        if not Path(path).exists():
            issues.append(f"Shebang references non-existent path: {path}")

    return issues


ALL_EXTENSIONS = get_all_extensions()
EXTENSION_NAMES = [ext.name for ext in ALL_EXTENSIONS]


def make_test_env():
    """Create environment for running extension tests."""
    env = os.environ.copy()
    env["AMI_ROOT"] = str(PROJECT_ROOT)
    env["PATH"] = (
        f"{BIN_DIR}:"
        f"{PROJECT_ROOT}/.venv/bin:"
        f"{PROJECT_ROOT}/.venv/node_modules/.bin:"
        f"{env.get('PATH', '')}"
    )
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return env


def get_extension_by_name(name: str) -> ExtensionMetadata | None:
    """Get extension metadata by name."""
    for ext in ALL_EXTENSIONS:
        if ext.name == name:
            return ext
    return None


@pytest.mark.integration
class TestExtensionInstallation:
    """Test that extensions are installed as symlinks/wrappers in .boot-linux/bin/."""

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_command_exists_in_bin(self, ext_name: str):
        """Test that extension command exists in .boot-linux/bin/."""
        cmd_path = BIN_DIR / ext_name
        assert cmd_path.exists(), (
            f"Extension {ext_name} not installed in {BIN_DIR}\n"
            f"Run: make register-extensions"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_command_is_executable(self, ext_name: str):
        """Test that extension command is executable."""
        cmd_path = BIN_DIR / ext_name
        if not cmd_path.exists():
            pytest.xfail(f"Command not installed: {ext_name}")

        assert os.access(cmd_path, os.X_OK), (
            f"Extension {ext_name} is not executable: {cmd_path}"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_symlink_or_wrapper_type(self, ext_name: str):
        """Test that non-.py binaries are symlinks, .py binaries are wrappers."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None
        cmd_path = BIN_DIR / ext_name
        if not cmd_path.exists():
            pytest.xfail(f"Command not installed: {ext_name}")

        if ext.binary.endswith(".py"):
            # Python scripts get wrapper scripts (not symlinks)
            assert not cmd_path.is_symlink(), (
                f"{ext_name} (.py binary) should be a wrapper, not a symlink"
            )
            content = cmd_path.read_text()
            assert "ami-run" in content, f"{ext_name} wrapper should call ami-run"
        else:
            # Non-Python binaries get symlinks
            assert cmd_path.is_symlink(), (
                f"{ext_name} (non-.py binary) should be a symlink"
            )


@pytest.mark.integration
class TestExtensionHelp:
    """Test that extensions respond to help flags."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Setup environment for extension tests."""
        self.env = make_test_env()

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_help(self, ext_name: str):
        """Test that extension responds to --help or -h without error."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        if not ext.binary:
            pytest.xfail(f"No binary defined for {ext_name}")

        if not check_binary_exists(ext.binary):
            pytest.xfail(f"Binary not installed: {ext.binary}")

        cmd_path = BIN_DIR / ext_name
        if not cmd_path.exists():
            pytest.xfail(f"Command not installed in bin: {ext_name}")

        # Check for broken shebangs in the binary
        shebang = get_binary_shebang(ext.binary)
        if shebang:
            issues = validate_shebang_paths(shebang)
            if issues:
                pytest.fail(
                    f"Extension {ext_name} binary has broken shebang:\n"
                    f"Binary: {ext.binary}\n"
                    f"Shebang: {shebang}\n"
                    f"Issues: {'; '.join(issues)}"
                )

        # Try --help first, fall back to -h
        for flag in ("--help", "-h"):
            result = subprocess.run(
                [str(cmd_path), flag],
                capture_output=True,
                text=True,
                env=self.env,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                break
        else:
            assert result.returncode == 0, (
                f"Extension {ext_name} help failed with code {result.returncode}\n"
                f"Binary: {ext.binary}\n"
                f"stdout: {result.stdout[:500] if result.stdout else '(empty)'}\n"
                f"stderr: {result.stderr[:500] if result.stderr else '(empty)'}"
            )


@pytest.mark.integration
class TestExtensionMetadata:
    """Test that all extensions have valid metadata in extensions.yaml."""

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_category_valid(self, ext_name: str):
        """Test that extension category is valid."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        assert ext.category in VALID_CATEGORIES, (
            f"Extension {ext_name} has invalid category: '{ext.category}'\n"
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_has_description(self, ext_name: str):
        """Test that extension has a non-empty description."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        assert ext.description, f"Extension {ext_name} has empty description"
        assert len(ext.description) >= MIN_DESCRIPTION_LENGTH, (
            f"Extension {ext_name} description too short: '{ext.description}'"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_has_binary(self, ext_name: str):
        """Test that extension has a binary path defined."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None
        assert ext.binary, f"Extension {ext_name} has no binary defined"


@pytest.mark.integration
class TestExtensionBinaries:
    """Test extension binary configuration."""

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_binary_path_format(self, ext_name: str):
        """Test that binary path is relative and properly formatted."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        if not ext.binary:
            pytest.xfail(f"No binary defined for {ext_name}")

        assert not ext.binary.startswith("/"), (
            f"Extension {ext_name} binary should be"
            f" relative path, not absolute: {ext.binary}"
        )

        assert ".." not in ext.binary, (
            f"Extension {ext_name} binary path should not contain '..': {ext.binary}"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_binary_shebang_valid(self, ext_name: str):
        """Test that binary has valid shebang if it's a script."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        if not ext.binary:
            pytest.xfail(f"No binary defined for {ext_name}")

        if not check_binary_exists(ext.binary):
            pytest.xfail(f"Binary not installed: {ext.binary}")

        shebang = get_binary_shebang(ext.binary)

        if ext.binary.endswith(".py"):
            pass  # Python scripts run via ami-run, no shebang needed
        elif shebang:
            issues = validate_shebang_paths(shebang)
            assert not issues, (
                f"Extension {ext_name} binary has invalid shebang:\n"
                f"Binary: {ext.binary}\n"
                f"Shebang: {shebang}\n"
                f"Issues:\n" + "\n".join(f"  - {issue}" for issue in issues)
            )


@pytest.mark.integration
class TestHiddenExtensions:
    """Test hidden extension behavior."""

    def test_hidden_extensions_exist(self):
        """Test that hidden extensions are properly marked."""
        hidden = [ext for ext in ALL_EXTENSIONS if ext.hidden]
        visible = [ext for ext in ALL_EXTENSIONS if not ext.hidden]

        hidden_names = [ext.name for ext in hidden]
        assert "ami-pwd" in hidden_names, "ami-pwd should be marked as hidden"

        msg = f"Too many hidden: {len(hidden)} vs {len(visible)} visible"
        assert len(visible) > len(hidden), msg

    @pytest.mark.parametrize(
        "ext_name",
        [ext.name for ext in ALL_EXTENSIONS if ext.hidden],
        ids=lambda x: f"hidden-{x}",
    )
    def test_hidden_extension_command_exists(self, ext_name: str):
        """Test that hidden extensions still have commands installed."""
        cmd_path = BIN_DIR / ext_name
        assert cmd_path.exists(), (
            f"Hidden extension {ext_name} not installed in {BIN_DIR}"
        )
