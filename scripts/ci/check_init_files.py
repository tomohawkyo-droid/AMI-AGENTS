#!/usr/bin/env python3
"""Check that all __init__.py files are completely empty.

This enforces a strict policy: ALL __init__.py files MUST be empty.
No imports, no docstrings, no logic, no variables - NOTHING.

This is a CRITICAL security and code quality requirement.
"""

import sys


def check_file(filepath: str) -> list[str]:
    """Check if __init__.py file is completely empty.

    Args:
        filepath: Path to __init__.py file to check

    Returns:
        List of error messages (empty if file is empty)
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    errors = []

    # File MUST be completely empty
    if content.strip():
        errors.append(
            f"__init__.py files MUST be completely EMPTY.\n"
            f"    Found {len(content)} characters in {filepath}\n"
            f"    ALL __init__.py files must be 0 bytes with NO content.\n"
            f"    This is a CRITICAL security and code quality requirement.\n"
            f"    Remove ALL content from this file: imports, docstrings, variables, EVERYTHING."
        )

    return errors


def main() -> None:
    """Main entry point - check all __init__.py files passed as arguments."""
    has_errors = False
    for filepath in sys.argv[1:]:
        errors = check_file(filepath)
        if errors:
            print(f"\n❌ CRITICAL ERROR: {filepath}")
            for err in errors:
                print(f"{err}")
            has_errors = True

    if has_errors:
        print("\n" + "=" * 80)
        print("POLICY: ALL __init__.py FILES MUST BE COMPLETELY EMPTY")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
