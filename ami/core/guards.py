"""Native security guards for agent orchestration.

Implements zero-tolerance checks for malicious behavior and forbidden commands
without relying on external CLI sidecars.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from ami.core.logic import load_bash_patterns, load_sensitive_patterns, load_communication_patterns, load_api_limit_patterns


def check_command_safety(command: str, guard_rules_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Check if a bash command violates security patterns.
    """
    deny_patterns = load_bash_patterns(guard_rules_path)
    
    for pattern_config in deny_patterns:
        pattern = pattern_config.get("pattern", "")
        message = pattern_config.get("message", "Pattern violation detected")
        
        if re.search(pattern, command):
            return False, f"SECURITY VIOLATION: {message} (Pattern: {pattern})"
    
    # Additional check for edit safety on risky commands
    risky_edit_cmds = [r"\bsed\b", r"\becho\b", r"\bcat\b", r"\bawk\b", r">", r">>", r"\|"]
    if any(re.search(p, command) for p in risky_edit_cmds):
        return check_edit_safety(command)
            
    return True, ""


def check_edit_safety(command: str) -> Tuple[bool, str]:
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
            return False, f"SECURITY VIOLATION: Direct modification of '{desc}' ({pattern}) via shell is forbidden. Use dedicated tools or edit manually."

    return True, ""



def check_content_safety(content: str) -> Tuple[bool, str]:
    """
    Check for prohibited communication patterns in agent output.
    """
    prohibited_patterns = load_communication_patterns()
    for pattern_config in prohibited_patterns:
        pattern = pattern_config.get("pattern", "")
        desc = pattern_config.get("description", "")
        
        if re.search(pattern, content, re.IGNORECASE):
            return False, f"COMMUNICATION VIOLATION: {desc}"
            
    return True, ""
