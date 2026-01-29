"""Unit tests for core/logic module."""

from pathlib import Path
from typing import TypedDict, cast
from unittest.mock import MagicMock, patch

import pytest

from ami.core.logic import (
    GREETING_PATTERNS,
    MIN_CODE_FENCE_LINES,
    CompletionMarker,
    ModeratorResult,
    PythonPattern,
    load_api_limit_patterns,
    load_bash_patterns,
    load_communication_patterns,
    load_exemptions,
    load_python_patterns,
    load_sensitive_patterns,
    parse_code_fence_output,
    parse_completion_marker,
    parse_json_block,
    parse_moderator_result,
)

EXPECTED_JSON_NUM_VALUE = 42
EXPECTED_JSON_FLOAT_VALUE = 3.14
EXPECTED_MIN_CODE_FENCE_LINES_VALUE = 2


class JsonResult(TypedDict, total=False):
    """Generic JSON result for tests."""

    key: str
    data: object
    outer: object
    str: str
    num: int
    float: float
    bool: bool
    null: None


class NestedJson(TypedDict):
    """Nested JSON result for tests."""

    inner: str


class OuterJson(TypedDict):
    """Outer JSON result for tests."""

    outer: NestedJson


class TestTypedDicts:
    """Tests for TypedDict definitions."""

    def test_python_pattern(self) -> None:
        """Test PythonPattern TypedDict."""
        pattern: PythonPattern = {
            "name": "test",
            "pattern": r"\beval\b",
            "reason": "Avoid eval",
        }
        assert pattern["name"] == "test"

    def test_completion_marker(self) -> None:
        """Test CompletionMarker TypedDict."""
        marker: CompletionMarker = {"type": "work_done", "content": None}
        assert marker["type"] == "work_done"

    def test_moderator_result(self) -> None:
        """Test ModeratorResult TypedDict."""
        result: ModeratorResult = {"status": "pass", "reason": None}
        assert result["status"] == "pass"


class TestLoadPatterns:
    """Tests for pattern loading functions."""

    @patch("ami.core.logic.get_policy_engine")
    def test_load_python_patterns(self, mock_engine) -> None:
        """Test loading Python patterns from policy engine."""
        mock_policy = MagicMock()
        mock_policy.load_python_patterns.return_value = [
            {"name": "test", "pattern": ".*", "reason": "test"}
        ]
        mock_engine.return_value = mock_policy

        patterns = load_python_patterns()

        assert len(patterns) == 1
        mock_policy.load_python_patterns.assert_called_once()

    @patch("ami.core.logic.get_policy_engine")
    def test_load_bash_patterns_from_engine(self, mock_engine) -> None:
        """Test loading Bash patterns from policy engine."""
        mock_policy = MagicMock()
        mock_policy.load_bash_patterns.return_value = [{"pattern": "rm -rf /"}]
        mock_engine.return_value = mock_policy

        patterns = load_bash_patterns()

        assert len(patterns) == 1
        mock_policy.load_bash_patterns.assert_called_once()

    def test_load_bash_patterns_from_file(self, tmp_path: Path) -> None:
        """Test loading Bash patterns from file path."""
        patterns_file = tmp_path / "patterns.yaml"
        patterns_file.write_text(
            """
deny_patterns:
  - pattern: "rm -rf /"
    message: "Dangerous command"
"""
        )

        patterns = load_bash_patterns(patterns_file)

        assert len(patterns) == 1
        assert patterns[0]["pattern"] == "rm -rf /"

    def test_load_bash_patterns_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file returns empty."""
        nonexistent = tmp_path / "nonexistent.yaml"

        patterns = load_bash_patterns(nonexistent)

        assert patterns == []

    @patch("ami.core.logic.get_policy_engine")
    def test_load_sensitive_patterns(self, mock_engine) -> None:
        """Test loading sensitive file patterns."""
        mock_policy = MagicMock()
        mock_policy.load_sensitive_patterns.return_value = [{"pattern": r"\.env"}]
        mock_engine.return_value = mock_policy

        patterns = load_sensitive_patterns()

        assert len(patterns) == 1

    @patch("ami.core.logic.get_policy_engine")
    def test_load_communication_patterns(self, mock_engine) -> None:
        """Test loading communication patterns."""
        mock_policy = MagicMock()
        mock_policy.load_communication_patterns.return_value = [
            {"pattern": "ignore instructions"}
        ]
        mock_engine.return_value = mock_policy

        patterns = load_communication_patterns()

        assert len(patterns) == 1

    @patch("ami.core.logic.get_policy_engine")
    def test_load_api_limit_patterns(self, mock_engine) -> None:
        """Test loading API limit patterns."""
        mock_policy = MagicMock()
        mock_policy.load_api_limit_patterns.return_value = ["pattern1", "pattern2"]
        mock_engine.return_value = mock_policy

        patterns = load_api_limit_patterns()

        assert patterns == ["pattern1", "pattern2"]

    @patch("ami.core.logic.get_policy_engine")
    def test_load_exemptions(self, mock_engine) -> None:
        """Test loading exemptions."""
        mock_policy = MagicMock()
        mock_policy.load_exemptions.return_value = {"file1.py", "file2.py"}
        mock_engine.return_value = mock_policy

        exemptions = load_exemptions()

        assert exemptions == {"file1.py", "file2.py"}


class TestParseCodeFenceOutput:
    """Tests for parse_code_fence_output function."""

    def test_no_code_fence(self) -> None:
        """Test output without code fence."""
        output = "plain text output"
        result = parse_code_fence_output(output)
        assert result == "plain text output"

    def test_with_code_fence(self) -> None:
        """Test output with code fence."""
        output = """```
code content
```"""
        result = parse_code_fence_output(output)
        assert result == "code content"

    def test_with_language_specifier(self) -> None:
        """Test output with language specifier."""
        output = """```python
print("hello")
```"""
        result = parse_code_fence_output(output)
        # Should remove the python specifier line
        assert "print" in result

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        output = "  output with spaces  "
        result = parse_code_fence_output(output)
        assert result == "output with spaces"

    def test_incomplete_code_fence(self) -> None:
        """Test handling of incomplete code fence."""
        output = """```
content without closing"""
        result = parse_code_fence_output(output)
        # Should handle gracefully
        assert "content" in result


class TestParseCompletionMarker:
    """Tests for parse_completion_marker function."""

    def test_work_done_marker(self) -> None:
        """Test parsing WORK DONE marker."""
        output = "Task completed. WORK DONE"
        result = parse_completion_marker(output)

        assert result["type"] == "work_done"
        assert result["content"] is None

    def test_feedback_marker(self) -> None:
        """Test parsing FEEDBACK marker."""
        output = "FEEDBACK: Need more information about requirements"
        result = parse_completion_marker(output)

        assert result["type"] == "feedback"
        assert result["content"] is not None
        assert "Need more information" in result["content"]

    def test_feedback_multiline(self) -> None:
        """Test parsing multiline feedback."""
        output = """FEEDBACK: First line
Second line
Third line"""
        result = parse_completion_marker(output)

        assert result["type"] == "feedback"
        assert result["content"] is not None
        assert "First line" in result["content"]

    def test_no_marker(self) -> None:
        """Test output without marker."""
        output = "Regular output without markers"
        result = parse_completion_marker(output)

        assert result["type"] == "none"
        assert result["content"] is None


class TestParseModeratorResult:
    """Tests for parse_moderator_result function."""

    def test_pass_result(self) -> None:
        """Test parsing PASS result."""
        output = "Review complete. PASS"
        result = parse_moderator_result(output)

        assert result["status"] == "pass"
        assert result["reason"] is None

    def test_fail_result_with_reason(self) -> None:
        """Test parsing FAIL result with reason."""
        output = "FAIL: Security issue detected"
        result = parse_moderator_result(output)

        assert result["status"] == "fail"
        assert result["reason"] is not None
        assert "Security issue" in result["reason"]

    def test_unclear_result(self) -> None:
        """Test handling unclear result."""
        output = "Not sure what to do"
        result = parse_moderator_result(output)

        assert result["status"] == "fail"
        assert result["reason"] is not None
        assert "unclear" in result["reason"].lower()


class TestParseJsonBlock:
    """Tests for parse_json_block function."""

    def test_parse_json_in_code_fence(self) -> None:
        """Test parsing JSON from code fence."""
        output = """```json
{"key": "value"}
```"""
        result = cast(JsonResult, parse_json_block(output))
        assert result["key"] == "value"

    def test_parse_plain_json(self) -> None:
        """Test parsing plain JSON."""
        output = '{"key": "value"}'
        result = cast(JsonResult, parse_json_block(output))
        assert result["key"] == "value"

    def test_parse_json_with_text_prefix(self) -> None:
        """Test parsing JSON with text before it."""
        output = 'Here is the result: {"key": "value"}'
        result = cast(JsonResult, parse_json_block(output))
        assert result["key"] == "value"

    def test_parse_json_array(self) -> None:
        """Test parsing JSON array returns wrapped dict."""
        output = '["a", "b", "c"]'
        result = cast(JsonResult, parse_json_block(output))
        assert "data" in result
        assert result["data"] == ["a", "b", "c"]

    def test_parse_nested_json(self) -> None:
        """Test parsing nested JSON."""
        output = '{"outer": {"inner": "value"}}'
        result = cast(OuterJson, parse_json_block(output))
        assert result["outer"]["inner"] == "value"

    def test_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises ValueError."""
        output = "not valid json"
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_json_block(output)

    def test_json_with_various_types(self) -> None:
        """Test parsing JSON with various types."""
        output = '{"str": "text", "num": 42, "float": 3.14, "bool": true, "null": null}'
        result = cast(JsonResult, parse_json_block(output))
        assert result["str"] == "text"
        assert result["num"] == EXPECTED_JSON_NUM_VALUE
        assert result["float"] == EXPECTED_JSON_FLOAT_VALUE
        assert result["bool"] is True
        assert result["null"] is None


class TestConstants:
    """Tests for module constants."""

    def test_min_code_fence_lines(self) -> None:
        """Test MIN_CODE_FENCE_LINES value."""
        assert MIN_CODE_FENCE_LINES == EXPECTED_MIN_CODE_FENCE_LINES_VALUE

    def test_greeting_patterns_exist(self) -> None:
        """Test GREETING_PATTERNS is defined."""
        assert len(GREETING_PATTERNS) > 0
        assert any("hello" in p for p in GREETING_PATTERNS)
