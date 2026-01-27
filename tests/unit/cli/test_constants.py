"""Unit tests for ami/cli/constants.py."""

from ami.cli.constants import DEFAULT_MAX_WORKERS, DEFAULT_TIMEOUT

EXPECTED_MAX_WORKERS = 4
EXPECTED_TIMEOUT = 3600


class TestConstants:
    """Tests for CLI constants."""

    def test_default_max_workers_value(self):
        """Test DEFAULT_MAX_WORKERS has expected value."""
        assert DEFAULT_MAX_WORKERS == EXPECTED_MAX_WORKERS

    def test_default_timeout_value(self):
        """Test DEFAULT_TIMEOUT has expected value."""
        assert DEFAULT_TIMEOUT == EXPECTED_TIMEOUT

    def test_constants_are_integers(self):
        """Test constants are integer types."""
        assert isinstance(DEFAULT_MAX_WORKERS, int)
        assert isinstance(DEFAULT_TIMEOUT, int)
