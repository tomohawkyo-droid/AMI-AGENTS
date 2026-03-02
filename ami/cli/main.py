#!/usr/bin/env python3
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

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

from ami.cli.mode_handlers import (
    mode_interactive_editor,
    mode_print,
    mode_query,
    mode_sessions,
)
from ami.cli.transcript_store import TranscriptStore
from ami.core.config import get_config
from ami.types.results import ModeHandler

# Load .env file after imports
load_dotenv(Path.cwd() / ".env")


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

    parser.add_argument(
        "--sessions",
        action="store_true",
        help="Browse and manage transcript sessions interactively",
    )

    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune transcript sessions older than retention_days config",
    )

    parser.add_argument(
        "query_args",
        nargs="*",
        help="Positional query arguments (runs in query mode if provided)",
    )

    args = parser.parse_args()

    # Route to appropriate mode using dispatch
    # Positional args take precedence as a query if no other mode specified
    query_text = args.query
    if not query_text and args.query_args:
        query_text = " ".join(args.query_args)

    # Handle --prune before mode dispatch (it's a maintenance command, not a mode)
    if args.prune:
        store = TranscriptStore()
        raw = get_config().get_value("logging.retention_days", 90)
        retention = int(str(raw)) if raw is not None else 90
        deleted = store.prune_sessions(retention_days=retention)
        sys.stdout.write(f"Pruned {deleted} sessions older than {retention} days.\n")
        return 0

    mode_handlers_list: list[ModeHandler] = [
        ModeHandler(args.sessions, lambda: mode_sessions() if args.sessions else 1),
        ModeHandler(
            args.interactive_editor,
            lambda: mode_interactive_editor() if args.interactive_editor else 1,
        ),
        ModeHandler(query_text, lambda: mode_query(query_text) if query_text else 1),
        ModeHandler(args.print, lambda: mode_print(args.print) if args.print else 1),
    ]

    for mode_handler in mode_handlers_list:
        if mode_handler.condition:
            handler = mode_handler.handler
            if callable(handler):
                return cast(int, handler())

    # NEW: If no arguments provided, default to interactive editor mode
    has_mode = any(
        [args.print, args.interactive_editor, args.sessions, args.prune, query_text]
    )
    if not has_mode:
        return mode_interactive_editor()

    # Show help if no mode specified
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
