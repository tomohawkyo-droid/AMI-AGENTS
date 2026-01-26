"""Unit tests for UUIDv7 utility."""

import time
import uuid

from ami.utils.uuid_utils import uuid7

# Test constants
UUID_VERSION_7 = 7


def test_uuid7_format() -> None:
    """Verify that generated ID is a valid UUID string."""
    val = uuid7()
    assert isinstance(val, str)
    # Should be parseable by standard uuid module
    parsed = uuid.UUID(val)
    assert str(parsed) == val


def test_uuid7_version() -> None:
    """Verify that generated ID is version 7."""
    val = uuid7()
    parsed = uuid.UUID(val)
    assert parsed.version == UUID_VERSION_7


def test_uuid7_monotonicity() -> None:
    """Verify that UUIDs are roughly monotonic (time-ordered)."""
    u1 = uuid7()
    time.sleep(0.002)  # Sleep 2ms to ensure timestamp change
    u2 = uuid7()

    assert u1 < u2


def test_uuid7_uniqueness() -> None:
    """Generate many UUIDs and check for collisions."""
    count = 1000
    uuids = {uuid7() for _ in range(count)}
    assert len(uuids) == count
