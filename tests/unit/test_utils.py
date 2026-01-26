"""Unit tests for automation.common.utils module."""

from pathlib import Path

from ami.core.utils import detect_language


class TestDetectLanguage:
    """Unit tests for detect_language function."""

    def test_detect_language_python(self) -> None:
        """detect_language() detects Python files."""
        lang = detect_language(Path("/test/file.py"))

        assert lang == "python"

    def test_detect_language_javascript(self) -> None:
        """detect_language() detects JavaScript files."""
        lang = detect_language(Path("/test/file.js"))

        assert lang == "javascript"

    def test_detect_language_typescript(self) -> None:
        """detect_language() detects TypeScript files."""
        lang = detect_language(Path("/test/file.ts"))

        assert lang == "typescript"

    def test_detect_language_unknown(self) -> None:
        """detect_language() returns None for unknown files."""
        lang = detect_language(Path("/test/file.txt"))

        assert lang is None
