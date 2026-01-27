"""Unit tests for ami/cli/streaming_utils.py."""

import re
from unittest.mock import MagicMock, patch

from ami.cli.streaming_utils import (
    calculate_timeout,
    load_instruction_with_replacements,
)

EXPECTED_SHORT_TIMEOUT = 10.0
EXPECTED_SMALL_BASE_TIMEOUT = 4.0
EXPECTED_BASE_TIMEOUT = 60.0
EXPECTED_DEFAULT_TIMEOUT = 30.0
EXPECTED_MIN_DATE_DASHES = 4


class TestCalculateTimeout:
    """Tests for calculate_timeout function."""

    def test_initial_lines_short_timeout(self):
        """Test initial lines use shorter timeout."""
        # First few lines should use half of base or 10s, whichever is smaller
        for line_count in range(5):
            result = calculate_timeout(60, line_count)
            assert result == EXPECTED_SHORT_TIMEOUT  # min(10.0, 60/2)

    def test_initial_lines_with_small_base(self):
        """Test initial lines with small base timeout."""
        # With base of 8, half is 4, which is less than 10
        for line_count in range(5):
            result = calculate_timeout(8, line_count)
            assert result == EXPECTED_SMALL_BASE_TIMEOUT  # min(10.0, 8/2)

    def test_after_initial_lines_uses_base(self):
        """Test lines after threshold use base timeout."""
        result = calculate_timeout(60, 5)
        assert result == EXPECTED_BASE_TIMEOUT

        result = calculate_timeout(60, 10)
        assert result == EXPECTED_BASE_TIMEOUT

    def test_none_timeout_uses_default(self):
        """Test None base timeout uses default of 30."""
        # Initial lines: min(10.0, 30/2) = 10
        result = calculate_timeout(None, 0)
        assert result == EXPECTED_SHORT_TIMEOUT

        # After threshold: uses 30
        result = calculate_timeout(None, 10)
        assert result == EXPECTED_DEFAULT_TIMEOUT

    def test_zero_timeout_uses_default(self):
        """Test zero base timeout uses default."""
        result = calculate_timeout(0, 10)
        assert result == EXPECTED_DEFAULT_TIMEOUT  # 0 is falsy, so defaults to 30

    def test_returns_float(self):
        """Test always returns float."""
        result = calculate_timeout(60, 10)
        assert isinstance(result, float)


class TestLoadInstructionWithReplacements:
    """Tests for load_instruction_with_replacements function."""

    def test_loads_simple_file(self, tmp_path):
        """Test loading simple instruction file."""
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Hello world")

        result = load_instruction_with_replacements(instruction_file)

        assert "Hello world" in result

    def test_replaces_date_pattern(self, tmp_path):
        """Test replaces {date} pattern."""
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Today is {date}")

        result = load_instruction_with_replacements(instruction_file)

        assert "{date}" not in result
        # Should contain a date-like string (YYYY-MM-DD)
        assert re.search(r"\d{4}-\d{2}-\d{2}", result)

    @patch("ami.cli.streaming_utils.get_config")
    def test_replaces_patterns_template(self, mock_get_config, tmp_path):
        """Test replaces {PATTERNS} with patterns file content."""
        # Create instruction file with {PATTERNS}
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Rules: {PATTERNS}")

        # Create patterns file
        patterns_dir = tmp_path / "ami" / "config" / "prompts"
        patterns_dir.mkdir(parents=True)
        patterns_file = patterns_dir / "patterns_core.txt"
        patterns_file.write_text("PATTERN 1: Do X\nPATTERN 2: Do Y")

        # Mock config
        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        result = load_instruction_with_replacements(instruction_file)

        assert "{PATTERNS}" not in result
        assert "PATTERN 1: Do X" in result
        assert "PATTERN 2: Do Y" in result

    @patch("ami.cli.streaming_utils.get_config")
    def test_patterns_file_missing(self, mock_get_config, tmp_path):
        """Test handles missing patterns file gracefully."""
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Rules: {PATTERNS}")

        mock_config = MagicMock()
        mock_config.root = tmp_path
        mock_get_config.return_value = mock_config

        result = load_instruction_with_replacements(instruction_file)

        # Should still contain {PATTERNS} since file doesn't exist
        assert "{PATTERNS}" in result

    def test_preserves_code_braces(self, tmp_path):
        """Test preserves braces in code examples."""
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text('def foo(): return {"key": "value"}')

        result = load_instruction_with_replacements(instruction_file)

        # Code braces should be preserved
        assert '{"key": "value"}' in result

    def test_multiple_date_replacements(self, tmp_path):
        """Test replaces multiple {date} occurrences."""
        instruction_file = tmp_path / "instruction.txt"
        instruction_file.write_text("Start: {date}\nEnd: {date}")

        result = load_instruction_with_replacements(instruction_file)

        assert "{date}" not in result
        # Both should be replaced
        # At least two dates with dashes
        assert result.count("-") >= EXPECTED_MIN_DATE_DASHES
