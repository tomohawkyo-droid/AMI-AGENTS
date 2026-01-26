#!/usr/bin/env python3
import os
import re
import sys
from typing import TypedDict

import yaml


class BannedConfig(TypedDict, total=False):
    """Configuration for banned words."""

    banned: list[dict[str, str]]
    dir_rules: list[dict[str, str | list[dict[str, str]]]]
    filename_rules: list[dict[str, str | list[dict[str, str]]]]


class ViolationRecord(TypedDict):
    """Record of a banned pattern violation."""

    file: str
    line: int
    pattern: str
    reason: str
    text: str


def load_banned_config(
    config_path: str = "res/config/banned_words.yaml",
) -> BannedConfig:
    if not os.path.exists(config_path):
        print(f"Error: Configuration file {config_path} not found.")
        sys.exit(1)
    with open(config_path) as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print("Error: Invalid configuration format.")
            sys.exit(1)
        return BannedConfig(
            banned=data.get("banned", []),
            dir_rules=data.get("dir_rules", []),
            filename_rules=data.get("filename_rules", []),
        )


def is_text_file(filepath: str) -> bool:
    """Simple heuristic to check if a file is text."""
    try:
        with open(filepath) as check_file:
            check_file.read(1024)
            return True
    except Exception:
        return False


def check_file(
    filepath: str, banned_patterns: list[dict[str, str]]
) -> list[ViolationRecord]:
    errors: list[ViolationRecord] = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                for rule in banned_patterns:
                    pattern = rule["pattern"]
                    # Use regex search
                    if re.search(pattern, line):
                        # Check for exception regex (allow-list) matches LINE or FILEPATH
                        if "exception_regex" in rule and (
                            re.search(rule["exception_regex"], line)
                            or re.search(rule["exception_regex"], filepath)
                        ):
                            continue

                        errors.append(
                            ViolationRecord(
                                file=filepath,
                                line=i + 1,
                                pattern=pattern,
                                reason=rule["reason"],
                                text=line.strip(),
                            )
                        )
    except Exception:
        # If we can't read it as text, skip it
        pass
    return errors


def main() -> None:
    config = load_banned_config()
    banned_rules = config.get("banned", [])

    # Directories to always ignore
    IGNORE_DIRS = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "checkpoints",
        "logs",
        "results",
        "mlruns",
        ".gemini",
        "rocm_artifacts",
        "tmp",
    }

    # Files to ignore
    IGNORE_FILES = {
        "uv.lock",
        "package-lock.json",
        "yarn.lock",
        "check_banned_words.py",
        "block_coauthored.py",
        "banned_words.yaml",
    }

    # Format inclusion list
    INCLUDE_EXTENSIONS = {".py", ".js", ".ts"}

    found_errors = []
    root_dir = os.getcwd()

    print("Scanning repository for banned words in .py, .js, .ts files...")

    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file in IGNORE_FILES:
                continue

            # Only check specific formats
            if not any(file.endswith(ext) for ext in INCLUDE_EXTENSIONS):
                continue

            filepath = os.path.join(root, file)
            # Make path relative for cleaner output
            rel_path = os.path.relpath(filepath, root_dir)

            found_errors.extend(check_file(rel_path, banned_rules))

    if found_errors:
        print("\n\033[91mFAILED: Banned words found in codebase:\033[0m")
        for err in found_errors:
            print(
                f"  \033[1m{err['file']}:{err['line']}\033[0m - Found '{err['pattern']}'"
            )
            print(f"    Reason: {err['reason']}")
        sys.exit(1)

    print("\033[92mSUCCESS: No banned words found.\033[0m")
    sys.exit(0)


if __name__ == "__main__":
    main()
