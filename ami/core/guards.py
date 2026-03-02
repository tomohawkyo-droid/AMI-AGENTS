"""Native security guards for agent orchestration.

Implements zero-tolerance checks for sensitive-file edits, content safety,
and path traversal detection.
"""

import re
from pathlib import Path

from ami.core.logic import (
    load_communication_patterns,
    load_sensitive_patterns,
)
from ami.types.results import SafetyCheckResult


def check_edit_safety(command: str) -> SafetyCheckResult:
    """
    Block edits to security-sensitive files via shell commands.
    This static check looks for sensitive files.
    """
    # 1. Check for sensitive files
    sensitive_patterns = load_sensitive_patterns()
    for config in sensitive_patterns:
        pattern = config.get("pattern", "")
        desc = config.get("description", "Sensitive file")
        if re.search(pattern, command):
            msg = (
                f"SECURITY VIOLATION: Direct modification of '{desc}' "
                f"({pattern}) via shell is forbidden. "
                "Use dedicated tools or edit manually."
            )
            return SafetyCheckResult(False, msg)

    return SafetyCheckResult(True, "")


def check_content_safety(content: str) -> SafetyCheckResult:
    """
    Check for prohibited communication patterns in agent output.
    """
    prohibited_patterns = load_communication_patterns()
    for pattern_config in prohibited_patterns:
        pattern = pattern_config.get("pattern", "")
        desc = pattern_config.get("description", "")

        if re.search(pattern, content, re.IGNORECASE):
            return SafetyCheckResult(False, f"COMMUNICATION VIOLATION: {desc}")

    return SafetyCheckResult(True, "")


# Path traversal detection patterns covering common evasion techniques.
_TRAVERSAL_PATTERNS = (
    r"\.\./",  # Direct traversal
    r"\.\.\x5c",  # Backslash traversal (Windows-style)
    r"%2e%2e",  # URL-encoded ..
    r"%252e%252e",  # Double URL-encoded
    r"\x00",  # Null byte injection
    r"\.%00\.",  # Null byte in path
    r"%c0%ae",  # Overlong UTF-8 encoded .
    r"%c1%9c",  # Overlong UTF-8 encoded /
    r"\\\\",  # UNC paths
)


def _validate_path_within_root(
    path_str: str, resolved_root: Path
) -> SafetyCheckResult | None:
    """Validate a single path is within project root. Returns failure or None if ok."""
    try:
        resolved = Path(path_str).resolve()
        if not str(resolved).startswith(str(resolved_root)):
            return SafetyCheckResult(
                False,
                f"SECURITY VIOLATION: Path '{path_str}' "
                f"escapes project root '{resolved_root}'",
            )
    except (ValueError, OSError):
        return SafetyCheckResult(
            False,
            f"SECURITY VIOLATION: Unresolvable path '{path_str}'",
        )
    return None


def check_path_traversal(
    command: str, project_root: Path | None = None
) -> SafetyCheckResult:
    """Detect path traversal attacks in a command string.

    Checks for encoded traversal sequences, null bytes, overlong UTF-8,
    and absolute paths escaping the project root.
    """
    for pattern in _TRAVERSAL_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return SafetyCheckResult(
                False,
                f"SECURITY VIOLATION: Path traversal detected (pattern: {pattern})",
            )

    if project_root:
        abs_path_matches = re.findall(r"(?:^|\s)(/[^\s]+)", command)
        resolved_root = project_root.resolve()
        for path_str in abs_path_matches:
            result = _validate_path_within_root(path_str, resolved_root)
            if result is not None:
                return result

    return SafetyCheckResult(True, "")
