"""UUID utilities for AMI Agents.

Provides a pure Python implementation of UUIDv7 (RFC 9562) to avoid external dependencies
or waiting for Python 3.14.
"""

import time
import random
import uuid

def uuid7() -> str:
    """
    Generates a UUIDv7 string according to RFC 9562.

    This implementation uses a 48-bit Unix timestamp in milliseconds,
    a 12-bit pseudo-random 'rand_a' field, a 4-bit version (7),
    a 2-bit RFC 4122 variant (10), and a 62-bit pseudo-random 'rand_b' field.
    
    Returns:
        str: A UUIDv7 string.
    """
    # 1. Get current Unix timestamp in milliseconds (48 bits)
    # time.time() returns seconds since epoch as a float.
    # Multiply by 1000 for milliseconds and convert to integer.
    # Mask to 48 bits to ensure it fits the field size.
    unixts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF

    # 2. Generate rand_a (12 bits)
    # This field can be a counter or random. For a pure, stateless implementation,
    # a random number is used as per RFC 9562 allowance.
    rand_a = random.getrandbits(12)

    # 3. Version (4 bits) - fixed to 0x7 for UUIDv7
    version = 0x7

    # 4. Variant (2 bits) - fixed to 0x2 (binary 10) for RFC 4122
    variant = 0x2

    # 5. Generate rand_b (62 bits)
    # This field provides additional randomness.
    rand_b = random.getrandbits(62)

    # Combine all parts into a single 128-bit integer.
    # The fields are concatenated directly in order of significance:
    # unixts_ms (48 bits) | version (4 bits) | rand_a (12 bits) | variant (2 bits) | rand_b (62 bits)
    #
    # Bit positions (from MSB 127 down to LSB 0):
    # unixts_ms:   [127-80] (48 bits)
    # version:     [79-76]  (4 bits, value 0x7)
    # rand_a:      [75-64]  (12 bits)
    # variant:     [63-62]  (2 bits, value 0x2 / binary 10)
    # rand_b:      [61-0]   (62 bits)
    #
    # Total bits: 48 + 4 + 12 + 2 + 62 = 128 bits

    uuid_int = (unixts_ms << 80) | \
               (version << 76) | \
               (rand_a << 64) | \
               (variant << 62) | \
               rand_b

    # Create a UUID object from the 128-bit integer and return its string representation.
    return str(uuid.UUID(int=uuid_int))