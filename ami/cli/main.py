#!/usr/bin/env python3

from __future__ import annotations


"""AMI Agent - Unified automation entry point.

Usage:
    ami-agent --print <instruction>     # Non-interactive mode
    ami-agent --query <query>           # Non-interactive query mode
    ami-agent --interactive-editor      # Interactive editor mode (default)

Examples:
    # Non-interactive print
    ami-agent --print config/prompts/agent.txt

    # Interactive session
    ami-agent
"""

import argparse
from collections.abc import Callable
from pathlib import Path
import sys


# Standard /base imports pattern to find orchestrator root
_root = next(p for p in Path(__file__).resolve().parents if (p / "base").exists())
sys.path.insert(0, str(_root))
from base.scripts.env.paths import setup_imports


ORCHESTRATOR_ROOT, MODULE_ROOT = setup_imports()

# Additional imports after path setup

# Load .env file before importing automation modules (ensures env vars available for Config)
from dotenv import load_dotenv


load_dotenv(ORCHESTRATOR_ROOT / ".env")

# Ensure scripts.automation is importable
sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from agents.ami.cli.mode_handlers import (
    mode_interactive_editor,
    mode_print,
    mode_query,
)


def main() -> int:
    """Main entry point - Route to appropriate mode."""
    parser = argparse.ArgumentParser(
        description="AMI Agent - Unified automation entry point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--print",
        metavar="INSTRUCTION_FILE",
        help="Non-interactive mode - run agent with --print",
    )

    # New argument for editor mode
    parser.add_argument(
        "--interactive-editor",
        action="store_true",
        help="Interactive editor mode - opens text editor first, Ctrl+S sends to agent",
    )

    parser.add_argument(
        "--query",
        metavar="QUERY",
        help="Non-interactive mode - run agent with provided query string",
    )

    args = parser.parse_args()

    # Route to appropriate mode using dispatch
    mode_handlers_list: list[tuple[str | bool | None, Callable[[], int]]] = [
        (args.interactive_editor, lambda: mode_interactive_editor() if args.interactive_editor else 1),
        (args.query, lambda: mode_query(args.query) if args.query else 1),
        (args.print, lambda: mode_print(args.print) if args.print else 1),
    ]

    for condition, handler in mode_handlers_list:
        if condition:
            return handler()

    # NEW: If no arguments provided, default to interactive editor mode
    if not any([args.print, args.interactive_editor, args.query]):
        return mode_interactive_editor()

    # Show help if no mode specified
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
