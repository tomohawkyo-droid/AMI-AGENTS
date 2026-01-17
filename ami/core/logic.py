"""Core logic and rule definitions for agent orchestration.

Consolidates regex patterns and parsing logic from legacy validation modules.
"""

import json
from pathlib import Path
from functools import lru_cache
import re
from typing import Any, Dict, List, Literal, Optional

import yaml

from ami.core.config import get_config


# Code fence parsing constants
MIN_CODE_FENCE_LINES = 2


@lru_cache(maxsize=1)
def load_python_patterns() -> List[Dict[str, Any]]:
    """Load Python fast pattern validation rules from YAML."""
    config = get_config()
    patterns_dir = config.root / "scripts/config/patterns"
    patterns_file = patterns_dir / "python_fast.yaml"

    if not patterns_file.exists():
        return []

    with patterns_file.open() as f:
        data = yaml.safe_load(f)

    return data.get("patterns", [])


@lru_cache(maxsize=16)
def load_bash_patterns(patterns_path: Path | None = None) -> List[Dict[str, str]]:
    """Load Bash command validation patterns from YAML.
    
    Args:
        patterns_path: Optional path to specific patterns file.
    """
    if patterns_path:
        patterns_file = patterns_path
    else:
        config = get_config()
        patterns_dir = config.root / "ami/config/policies"
        patterns_file = patterns_dir / "default.yaml"

    if not patterns_file.exists():
        return []

    with patterns_file.open() as f:
        data = yaml.safe_load(f)

    return data.get("deny_patterns", [])


@lru_cache(maxsize=1)
def load_sensitive_patterns() -> List[Dict[str, str]]:
    """Load sensitive file patterns from YAML."""
    config = get_config()
    patterns_dir = config.root / "scripts/config/patterns"
    patterns_file = patterns_dir / "sensitive_files.yaml"

    if not patterns_file.exists():
        return []

    with patterns_file.open() as f:
        data = yaml.safe_load(f)

    return data.get("sensitive_patterns", [])


@lru_cache(maxsize=1)
def load_exemptions() -> set[str]:
    """Load file exemptions from YAML."""
    config = get_config()
    patterns_dir = config.root / "scripts/config/patterns"
    exemptions_file = patterns_dir / "exemptions.yaml"

    if not exemptions_file.exists():
        return set()

    with exemptions_file.open() as f:
        data = yaml.safe_load(f)

    return set(data.get("pattern_check_exemptions", []))


def parse_code_fence_output(output: str) -> str:
    """Parse output, removing markdown code fences if present."""
    cleaned = output.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if len(lines) > MIN_CODE_FENCE_LINES and lines[-1] == "```":
            cleaned = "\n".join(lines[1:-1]).strip()
        elif len(lines) > 1:
            cleaned = "\n".join(lines[1:]).strip()
    return cleaned


def parse_completion_marker(output: str) -> Dict[str, Any]:
    """Parse completion marker from worker output."""
    if "WORK DONE" in output:
        return {"type": "work_done", "content": None}

    feedback_match = re.search(r"FEEDBACK:\s*(.+)", output, re.DOTALL)
    if feedback_match:
        return {"type": "feedback", "content": feedback_match.group(1).strip()}

    return {"type": "none", "content": None}


def parse_moderator_result(output: str) -> Dict[str, Any]:
    """Parse moderator validation result."""
    if "PASS" in output:
        return {"status": "pass", "reason": None}

    fail_match = re.search(r"FAIL:\s*(.+)", output, re.DOTALL)
    if fail_match:
        return {"status": "fail", "reason": fail_match.group(1).strip()}

    return {"status": "fail", "reason": "Moderator validation unclear - no explicit PASS or FAIL in output"}


# Prohibited communication patterns (regexes)
PROHIBITED_PATTERNS = [
    {
        "pattern": r"the issue is clear",
        "description": "Assuming clarity without verification"
    },
    {
        "pattern": r"you are right",
        "description": "Premature agreement"
    },
    {
        "pattern": r"i see the problem",
        "description": "Definitive claim without reading code"
    }
]

# API Limit / Throttling patterns
API_LIMIT_PATTERNS = [
    r"rate limit",
    r"throttled",
    r"too many requests",
    r"api limit"
]

# Greeting patterns to ignore
GREETING_PATTERNS = [
    r"^hello\b",
    r"^hi\b",
    r"^hey\b"
]

def parse_json_block(output: str) -> Dict[str, Any]:
    """Parse JSON block from LLM output, handling markdown fences."""
    cleaned = output.strip()
    
    # Try finding JSON block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if json_match:
        cleaned = json_match.group(1).strip()
    
    # If no block, assume the whole output might be JSON if it starts with {
    elif not cleaned.startswith("{") and "{" in cleaned:
        # Fallback: find the first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
            
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Last ditch: fix common LLM JSON errors (trailing commas)
        # Not implemented here to keep it safe, just re-raise
        raise ValueError(f"Invalid JSON in output: {str(e)}") from e

