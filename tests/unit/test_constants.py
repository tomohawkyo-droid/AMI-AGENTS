"""Unit tests for core/constants module."""

from ami.core.constants import COMMON_EXCLUDE_PATTERNS


class TestCommonExcludePatterns:
    """Tests for COMMON_EXCLUDE_PATTERNS constant."""

    def test_patterns_is_list(self) -> None:
        """Test that patterns is a list."""
        assert isinstance(COMMON_EXCLUDE_PATTERNS, list)

    def test_patterns_not_empty(self) -> None:
        """Test that patterns list is not empty."""
        assert len(COMMON_EXCLUDE_PATTERNS) > 0

    def test_node_modules_excluded(self) -> None:
        """Test that node_modules is in exclusion patterns."""
        assert "**/node_modules/**" in COMMON_EXCLUDE_PATTERNS

    def test_git_excluded(self) -> None:
        """Test that .git is in exclusion patterns."""
        assert "**/.git/**" in COMMON_EXCLUDE_PATTERNS

    def test_venv_excluded(self) -> None:
        """Test that virtual environments are excluded."""
        assert "**/.venv/**" in COMMON_EXCLUDE_PATTERNS
        assert "**/venv/**" in COMMON_EXCLUDE_PATTERNS

    def test_pycache_excluded(self) -> None:
        """Test that __pycache__ is excluded."""
        assert "**/__pycache__/**" in COMMON_EXCLUDE_PATTERNS

    def test_cache_directories_excluded(self) -> None:
        """Test that cache directories are excluded."""
        assert "**/.cache/**" in COMMON_EXCLUDE_PATTERNS
        assert "**/.pytest_cache/**" in COMMON_EXCLUDE_PATTERNS
        assert "**/.mypy_cache/**" in COMMON_EXCLUDE_PATTERNS
        assert "**/.ruff_cache/**" in COMMON_EXCLUDE_PATTERNS

    def test_build_directories_excluded(self) -> None:
        """Test that build directories are excluded."""
        assert "**/dist/**" in COMMON_EXCLUDE_PATTERNS
        assert "**/build/**" in COMMON_EXCLUDE_PATTERNS

    def test_egg_info_excluded(self) -> None:
        """Test that egg-info directories are excluded."""
        assert "**/*.egg-info/**" in COMMON_EXCLUDE_PATTERNS

    def test_all_patterns_are_strings(self) -> None:
        """Test that all patterns are strings."""
        for pattern in COMMON_EXCLUDE_PATTERNS:
            assert isinstance(pattern, str)

    def test_all_patterns_use_glob_syntax(self) -> None:
        """Test that all patterns use glob syntax with **."""
        for pattern in COMMON_EXCLUDE_PATTERNS:
            assert "**" in pattern, f"Pattern {pattern} doesn't use ** glob syntax"
