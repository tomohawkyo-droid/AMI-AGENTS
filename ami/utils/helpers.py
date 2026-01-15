"""Helper functions for task execution and CLI providers."""

from pathlib import Path
import re
from typing import Any


def parse_completion_marker(output: str) -> dict[str, Any]:
    """Parse completion marker from worker output.

    Args:
        output: Worker output text

    Returns:
        Dict with type and content
    """
    # Check for "WORK DONE"
    if "WORK DONE" in output:
        return {"type": "work_done", "content": None}

    # Check for "FEEDBACK: xxx"
    feedback_match = re.search(r"FEEDBACK:\s*(.+)", output, re.DOTALL)
    if feedback_match:
        return {"type": "feedback", "content": feedback_match.group(1).strip()}

    # No marker found
    return {"type": "none", "content": None}


def parse_moderator_result(output: str) -> dict[str, Any]:
    """Parse moderator validation result.

    Args:
        output: Moderator output text

    Returns:
        Dict with status ('pass' or 'fail') and optional reason
    """
    # Check for "PASS"
    if "PASS" in output:
        return {"status": "pass", "reason": None}

    # Check for "FAIL: xxx"
    fail_match = re.search(r"FAIL:\s*(.+)", output, re.DOTALL)
    if fail_match:
        return {"status": "fail", "reason": fail_match.group(1).strip()}

    # Moderator didn't output PASS or FAIL - treat as validation failure
    return {"status": "fail", "reason": "Moderator validation unclear - no explicit PASS or FAIL in output"}


def calculate_timeout(timeout: int | None, elapsed_time: float) -> float:
    """Calculate timeout for next read operation.

    Args:
        timeout: Overall timeout in seconds, or None for no limit
        elapsed_time: Time elapsed so far in seconds

    Returns:
        Timeout value in seconds for next operation
    """
    if timeout is None:
        return 1.0  # Default timeout to prevent infinite blocking

    remaining = timeout - elapsed_time
    if remaining <= 0:
        # Timeout occurred
        return 0.0

    # Use smaller of remaining time or default read timeout
    return min(remaining, 1.0)


def validate_path_and_return_code(path: str) -> int:
    """Validate path exists and return appropriate exit code.

    Args:
        path: Path string to validate

    Returns:
        Exit code (0=success, 1=failure)
    """
    path_obj = Path(path)
    if not path_obj.exists():
        return 1
    return 0
