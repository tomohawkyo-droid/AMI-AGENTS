"""Native security guards for agent orchestration.

Implements zero-tolerance checks for malicious behavior and forbidden commands
without relying on external CLI sidecars.
"""

import re
from pathlib import Path

from ami.core.logic import (
    load_bash_patterns,
    load_communication_patterns,
    load_sensitive_patterns,
)
from ami.types.results import SafetyCheckResult


def check_command_safety(
    command: str, guard_rules_path: Path | None = None
) -> SafetyCheckResult:
    """
    Check if a bash command violates security patterns.
    """
    deny_patterns = load_bash_patterns(guard_rules_path)

    for pattern_config in deny_patterns:
        pattern = pattern_config.get("pattern", "")
        message = pattern_config.get("message", "Pattern violation detected")

        if re.search(pattern, command):
            return SafetyCheckResult(
                False, f"SECURITY VIOLATION: {message} (Pattern: {pattern})"
            )

    # Additional check for edit safety on risky commands
    risky_edit_cmds = [
        r"\bsed\b",
        r"\becho\b",
        r"\bcat\b",
        r"\bawk\b",
        r">",
        r">>",
        r"\|",
    ]
    if any(re.search(p, command) for p in risky_edit_cmds):
        return check_edit_safety(command)

    return SafetyCheckResult(True, "")


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
