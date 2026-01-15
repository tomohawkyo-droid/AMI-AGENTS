"""Common utilities for LLM orchestration executors.

Now leverages consolidated logic from logic.py.
"""

from pathlib import Path
from typing import Any

from agents.ami.core.logic import (
    parse_json_block
)


def detect_language(file_path: Path) -> str | None:
    """Detect language from file extension."""
    ext = file_path.suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".html": "html",
        ".css": "css",
        ".md": "markdown",
    }
    return mapping.get(ext)