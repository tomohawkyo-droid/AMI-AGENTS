"""Core logic and rule definitions for agent orchestration.

Consolidates regex patterns and parsing logic from earlier validation modules.
"""

import json
import re
from typing import Literal, TypedDict

from ami.core.policies.engine import (
    BashPattern,
    PythonPattern,
    get_policy_engine,
)


class CompletionMarker(TypedDict):
    """Parsed completion marker from worker output."""

    type: Literal["work_done", "feedback", "none"]
    content: str | None


class ModeratorResult(TypedDict):
    """Parsed moderator validation result."""

    status: Literal["pass", "fail"]
    reason: str | None


class JsonBlockResult(TypedDict, total=False):
    """Parsed JSON block result."""

    data: object


# Code fence parsing constants
MIN_CODE_FENCE_LINES = 2


def load_python_patterns() -> list[PythonPattern]:
    """Load Python fast pattern validation rules."""
    return get_policy_engine().load_python_patterns()


def load_sensitive_patterns() -> list[BashPattern]:
    """Load sensitive file patterns."""
    return get_policy_engine().load_sensitive_patterns()


def load_communication_patterns() -> list[BashPattern]:
    """Load prohibited communication patterns."""
    return get_policy_engine().load_communication_patterns()


def load_api_limit_patterns() -> list[str]:
    """Load API limit patterns."""
    return get_policy_engine().load_api_limit_patterns()


def load_exemptions() -> set[str]:
    """Load file exemptions."""
    return get_policy_engine().load_exemptions()


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


def parse_completion_marker(output: str) -> CompletionMarker:
    """Parse completion marker from worker output."""
    if "WORK DONE" in output:
        return CompletionMarker(type="work_done", content=None)

    feedback_match = re.search(r"FEEDBACK:\s*(.+)", output, re.DOTALL)
    if feedback_match:
        return CompletionMarker(
            type="feedback", content=feedback_match.group(1).strip()
        )

    return CompletionMarker(type="none", content=None)


def parse_moderator_result(output: str) -> ModeratorResult:
    """Parse moderator validation result."""
    if "PASS" in output:
        return ModeratorResult(status="pass", reason=None)

    fail_match = re.search(r"FAIL:\s*(.+)", output, re.DOTALL)
    if fail_match:
        return ModeratorResult(status="fail", reason=fail_match.group(1).strip())

    return ModeratorResult(
        status="fail",
        reason="Moderator validation unclear - no explicit PASS or FAIL in output",
    )


# Greeting patterns to ignore
GREETING_PATTERNS = [r"^hello\b", r"^hi\b", r"^hey\b"]


def parse_json_block(output: str) -> object:
    """Parse JSON block from LLM output, handling markdown fences.

    Returns parsed JSON as an object. Caller should validate structure.
    """
    cleaned = output.strip()

    # Try finding JSON block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if json_match:
        cleaned = json_match.group(1).strip()

    # If no block, assume the whole output might be JSON if it starts with {
    elif not cleaned.startswith("{") and "{" in cleaned:
        # Find the first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]

    try:
        result = json.loads(cleaned)
        return result if isinstance(result, dict) else {"data": result}
    except json.JSONDecodeError as e:
        msg = "invalid JSON in output"
        raise ValueError(msg) from e
