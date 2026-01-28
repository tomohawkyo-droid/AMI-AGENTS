"""Integration tests for extension help options.

Tests that every extension in ami/scripts/extensions/ responds to --help or -h
without errors, verifying that the underlying tools are properly configured.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


PROJECT_ROOT = _find_project_root()
EXTENSIONS_DIR = PROJECT_ROOT / "ami" / "scripts" / "extensions"
VALID_CATEGORIES = frozenset(["core", "enterprise", "dev", "agents"])
REQUIRED_METADATA_FIELDS = frozenset(
    ["@name", "@description", "@category", "@binary", "@features"]
)
MIN_DESCRIPTION_LENGTH = 5


class ExtensionMetadata(NamedTuple):
    """Parsed extension metadata."""

    name: str
    description: str
    category: str
    binary: str
    features: str
    hidden: bool
    file_path: Path


def parse_extension_metadata(ext_file: Path) -> ExtensionMetadata | None:
    """Parse metadata from an extension file."""
    content = ext_file.read_text()
    metadata: dict[str, str] = {}

    for line in content.splitlines():
        if line.startswith("# @"):
            match = re.match(r"# @(\w+):\s*(.+)", line)
            if match:
                metadata[match.group(1)] = match.group(2).strip()

    if "name" not in metadata:
        return None

    return ExtensionMetadata(
        name=metadata.get("name", ""),
        description=metadata.get("description", ""),
        category=metadata.get("category", ""),
        binary=metadata.get("binary", ""),
        features=metadata.get("features", ""),
        hidden=metadata.get("hidden", "").lower() == "true",
        file_path=ext_file,
    )


def get_all_extensions() -> list[ExtensionMetadata]:
    """Get all extensions with their metadata."""
    extensions = []
    for ext_file in sorted(EXTENSIONS_DIR.glob("*.sh")):
        meta = parse_extension_metadata(ext_file)
        if meta:
            extensions.append(meta)
    return extensions


def check_binary_exists(binary_path: str) -> bool:
    """Check if the binary exists relative to project root."""
    if not binary_path:
        return False
    full_path = PROJECT_ROOT / binary_path
    return full_path.exists()


def check_binary_executable(binary_path: str) -> bool:
    """Check if the binary is executable."""
    if not binary_path:
        return False
    full_path = PROJECT_ROOT / binary_path
    return full_path.exists() and os.access(full_path, os.X_OK)


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


def validate_shebang_paths(shebang: str, binary_path: str) -> list[str]:
    """Validate that paths in shebang actually exist. Returns list of issues."""
    issues = []
    if not shebang:
        return issues

    # Extract paths from shebang
    shebang_content = shebang[2:].strip()  # Remove #!

    # Check for hardcoded absolute paths that might be wrong
    path_pattern = re.compile(r'(/[^\s"\']+)')
    for match in path_pattern.finditer(shebang_content):
        path = match.group(1)
        if not Path(path).exists():
            issues.append(f"Shebang references non-existent path: {path}")

    return issues


ALL_EXTENSIONS = get_all_extensions()
EXTENSION_NAMES = [ext.name for ext in ALL_EXTENSIONS]


def make_test_env() -> dict[str, str]:
    """Create environment for running extension tests."""
    env = os.environ.copy()
    env["AMI_ROOT"] = str(PROJECT_ROOT)
    env["PATH"] = (
        f"{PROJECT_ROOT}/.boot-linux/bin:"
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
class TestExtensionFunctionGeneration:
    """Test that extensions generate valid shell functions."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Setup environment for extension tests."""
        self.env = make_test_env()

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_generates_function(self, ext_name: str):
        """Test that extension script outputs a valid function definition."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None, f"Extension {ext_name} not found"

        result = subprocess.run(
            ["bash", str(ext.file_path)],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=10,
            check=False,
        )

        assert result.returncode == 0, (
            f"Extension {ext_name} script failed with code {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

        func_def = result.stdout.strip()
        assert func_def, f"Extension {ext_name} produced no output"

        # Verify it looks like a function definition
        assert f"{ext_name}()" in func_def, (
            f"Extension {ext_name} output doesn't contain function definition\n"
            f"Output: {func_def}"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_function_is_valid_bash(self, ext_name: str):
        """Test that the generated function is valid bash syntax."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        result = subprocess.run(
            ["bash", str(ext.file_path)],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=10,
            check=False,
        )
        func_def = result.stdout.strip()

        # Use bash -n to syntax check
        syntax_check = subprocess.run(
            ["bash", "-n", "-c", func_def],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        assert syntax_check.returncode == 0, (
            f"Extension {ext_name} generates invalid bash syntax\n"
            f"Function: {func_def}\n"
            f"Error: {syntax_check.stderr}"
        )


@pytest.mark.integration
class TestExtensionHelp:
    """Test that all extensions respond to help flags."""

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

        # Check for broken shebangs in the binary
        shebang = get_binary_shebang(ext.binary)
        if shebang:
            issues = validate_shebang_paths(shebang, ext.binary)
            if issues:
                pytest.fail(
                    f"Extension {ext_name} binary has broken shebang:\n"
                    f"Binary: {ext.binary}\n"
                    f"Shebang: {shebang}\n"
                    f"Issues: {'; '.join(issues)}"
                )

        # Get the function definition
        result = subprocess.run(
            ["bash", str(ext.file_path)],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=10,
            check=False,
        )
        func_def = result.stdout.strip()

        if not func_def:
            pytest.fail(f"Extension {ext_name} produced no function definition")

        # Try --help first
        help_cmd = f"{func_def}; {ext_name} --help"
        result = subprocess.run(
            ["bash", "-c", help_cmd],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
            check=False,
        )

        # Fall back to -h if --help fails
        if result.returncode != 0:
            help_cmd = f"{func_def}; {ext_name} -h"
            result = subprocess.run(
                ["bash", "-c", help_cmd],
                capture_output=True,
                text=True,
                env=self.env,
                timeout=30,
                check=False,
            )

        assert result.returncode == 0, (
            f"Extension {ext_name} help failed with code {result.returncode}\n"
            f"Binary: {ext.binary}\n"
            f"stdout: {result.stdout[:500] if result.stdout else '(empty)'}\n"
            f"stderr: {result.stderr[:500] if result.stderr else '(empty)'}"
        )

        output = result.stdout + result.stderr
        assert len(output) > 0, f"Extension {ext_name} --help produced no output"


@pytest.mark.integration
class TestExtensionMetadata:
    """Test that all extensions have valid metadata."""

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_has_required_metadata(self, ext_name: str):
        """Test that extension has all required metadata fields."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        content = ext.file_path.read_text()
        missing_fields = [
            field for field in REQUIRED_METADATA_FIELDS if f"# {field}:" not in content
        ]

        assert (
            not missing_fields
        ), f"Extension {ext_name} missing metadata fields: {', '.join(missing_fields)}"

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
    def test_extension_is_executable(self, ext_name: str):
        """Test that extension file is executable."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        assert os.access(ext.file_path, os.X_OK), (
            f"Extension {ext_name} is not executable: {ext.file_path}\n"
            f"Run: chmod +x {ext.file_path}"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_name_matches_filename(self, ext_name: str):
        """Test that @name matches the filename."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        expected_filename = f"{ext_name}.sh"
        actual_filename = ext.file_path.name

        assert actual_filename == expected_filename, (
            f"Extension @name '{ext_name}' doesn't match filename '{actual_filename}'\n"
            f"Expected filename: {expected_filename}"
        )

    @pytest.mark.parametrize("ext_name", EXTENSION_NAMES)
    def test_extension_has_description(self, ext_name: str):
        """Test that extension has a non-empty description."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None

        assert ext.description, f"Extension {ext_name} has empty description"
        assert (
            len(ext.description) >= MIN_DESCRIPTION_LENGTH
        ), f"Extension {ext_name} description too short: '{ext.description}'"


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

        # Should be relative path
        assert not ext.binary.startswith("/"), (
            f"Extension {ext_name} binary should be"
            f" relative path, not absolute: {ext.binary}"
        )

        # Should not contain ..
        assert (
            ".." not in ext.binary
        ), f"Extension {ext_name} binary path should not contain '..': {ext.binary}"

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

        # Python files should use venv python or env python
        if ext.binary.endswith(".py"):
            # Python scripts can be run via ami-run, no shebang needed
            pass
        elif shebang:
            issues = validate_shebang_paths(shebang, ext.binary)
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

        # At least ami-pwd should be hidden
        hidden_names = [ext.name for ext in hidden]
        assert "ami-pwd" in hidden_names, "ami-pwd should be marked as hidden"

        # Should have more visible than hidden
        msg = f"Too many hidden: {len(hidden)} vs {len(visible)} visible"
        assert len(visible) > len(hidden), msg

    @pytest.mark.parametrize(
        "ext_name",
        [ext.name for ext in ALL_EXTENSIONS if ext.hidden],
        ids=lambda x: f"hidden-{x}",
    )
    def test_hidden_extension_still_works(self, ext_name: str):
        """Test that hidden extensions still generate valid functions."""
        ext = get_extension_by_name(ext_name)
        assert ext is not None
        assert ext.hidden, f"Extension {ext_name} should be hidden"

        env = make_test_env()
        result = subprocess.run(
            ["bash", str(ext.file_path)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )

        assert (
            result.returncode == 0
        ), f"Hidden extension {ext_name} failed to generate function"
        assert (
            f"{ext_name}()" in result.stdout
        ), f"Hidden extension {ext_name} missing function def"
