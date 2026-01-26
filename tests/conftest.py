"""Pytest configuration for all tests.

Handles path setup so test files can import from project modules.
"""

import sys
from pathlib import Path

# Find AMI_ROOT (agents/ directory)
_TESTS_DIR = Path(__file__).resolve().parent
_AMI_ROOT = _TESTS_DIR.parent

# Add AMI_ROOT to path for project imports
if str(_AMI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AMI_ROOT))

# Export for use in tests
AMI_ROOT = _AMI_ROOT
