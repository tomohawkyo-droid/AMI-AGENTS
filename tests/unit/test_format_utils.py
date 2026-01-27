"""Unit tests for format_utils module."""

from ami.cli_components.format_utils import GB, KB, MB, format_file_size

EXPECTED_KB_VALUE = 1024


class TestFormatFileSize:
    """Tests for format_file_size function."""

    def test_format_gigabytes(self) -> None:
        """Test formatting sizes in gigabytes."""
        # 2GB
        assert format_file_size(2 * GB) == "2.0GB"
        # 1.5GB
        assert format_file_size(int(1.5 * GB)) == "1.5GB"

    def test_format_megabytes(self) -> None:
        """Test formatting sizes in megabytes."""
        # 500MB
        assert format_file_size(500 * MB) == "500.0MB"
        # Just over 1MB (function uses > not >=)
        assert format_file_size(MB + 1) == "1.0MB"

    def test_format_kilobytes(self) -> None:
        """Test formatting sizes in kilobytes."""
        # 100KB
        assert format_file_size(100 * KB) == "100.0KB"
        # Just over 1KB (function uses > not >=)
        assert format_file_size(KB + 1) == "1.0KB"

    def test_format_bytes(self) -> None:
        """Test formatting sizes in bytes."""
        assert format_file_size(500) == "500B"
        assert format_file_size(0) == "0B"
        assert format_file_size(1) == "1B"

    def test_format_string_input(self) -> None:
        """Test formatting with string input."""
        # 1024 bytes = exactly 1KB, but function uses > so it stays as bytes
        assert format_file_size("1025") == "1.0KB"
        assert format_file_size(str(2 * GB)) == "2.0GB"

    def test_format_unknown(self) -> None:
        """Test formatting 'Unknown' size."""
        assert format_file_size("Unknown") == "Unknown"

    def test_format_invalid_string(self) -> None:
        """Test formatting invalid string returns as-is."""
        assert format_file_size("not a number") == "not a number"
        assert format_file_size("abc123") == "abc123"

    def test_format_edge_cases(self) -> None:
        """Test edge cases at boundaries."""
        # Just under 1KB - stays as bytes
        assert format_file_size(1023) == "1023B"
        # Exactly 1KB - function uses > so stays as bytes
        assert format_file_size(1024) == "1024B"
        # Just over 1KB
        assert format_file_size(1025) == "1.0KB"
        # Just under 1MB
        assert format_file_size(MB - 1) == f"{(MB - 1) / KB:.1f}KB"
        # Just under 1GB
        assert format_file_size(GB - 1) == f"{(GB - 1) / MB:.1f}MB"


class TestConstants:
    """Tests for size constants."""

    def test_kb_constant(self) -> None:
        """Test KB constant value."""
        assert KB == EXPECTED_KB_VALUE

    def test_mb_constant(self) -> None:
        """Test MB constant value."""
        assert MB == 1024 * 1024

    def test_gb_constant(self) -> None:
        """Test GB constant value."""
        assert GB == 1024 * 1024 * 1024
