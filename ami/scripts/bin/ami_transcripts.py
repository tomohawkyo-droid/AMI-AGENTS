#!/usr/bin/env python3
"""AMI Transcript Management CLI.

Browse, search, replay, and resume transcript sessions.
"""

import argparse
import sys

from ami.cli.transcript_search import TranscriptSearcher
from ami.cli.transcript_store import TranscriptStore
from ami.core.conversation import ConversationEntry

# Display formatting constants
_TIMESTAMP_DISPLAY_LEN = 19
_TEXT_TRUNCATE_LEN = 200
_MAX_HITS_SHOWN = 5


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="ami-transcripts",
        description="Manage AMI agent transcript sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ami-transcripts list
  ami-transcripts list --status paused --limit 5
  ami-transcripts show <session_id>
  ami-transcripts show <session_id> --last 5
  ami-transcripts search "keyword1" "keyword2"
  ami-transcripts search "error" --session <session_id>
  ami-transcripts replay <session_id>
  ami-transcripts resume
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    list_parser = subparsers.add_parser("list", help="List transcript sessions")
    list_parser.add_argument(
        "--status", choices=["active", "paused", "completed"], default=None
    )
    list_parser.add_argument("--limit", type=int, default=20)

    # show
    show_parser = subparsers.add_parser("show", help="Show entries for a session")
    show_parser.add_argument("session_id")
    show_parser.add_argument("--last", type=int, default=None)

    # search
    search_parser = subparsers.add_parser("search", help="Search transcripts")
    search_parser.add_argument("keywords", nargs="+")
    search_parser.add_argument("--session", default=None, dest="session_id")

    # replay
    replay_parser = subparsers.add_parser("replay", help="Full replay of a session")
    replay_parser.add_argument("session_id")

    # resume
    subparsers.add_parser("resume", help="Show most recent paused session")

    return parser


def _format_entry_line(entry: object) -> str:
    """Format a transcript entry for display."""
    if not isinstance(entry, ConversationEntry):
        return str(entry)

    ts = (
        entry.timestamp[:_TIMESTAMP_DISPLAY_LEN]
        if len(entry.timestamp) > _TIMESTAMP_DISPLAY_LEN
        else entry.timestamp
    )

    text = entry.content
    if len(text) > _TEXT_TRUNCATE_LEN:
        text = text[:_TEXT_TRUNCATE_LEN] + "..."

    label = entry.role.value.upper()
    return f"  [{ts}] {label}: {text}"


def cmd_list(args: argparse.Namespace) -> int:
    """List sessions."""
    store = TranscriptStore()
    sessions = store.list_sessions(status=args.status)
    sessions = sessions[: args.limit]

    if not sessions:
        print("No sessions found.")
        return 0

    for s in sessions:
        status_icon = {"active": "🟢", "paused": "⏸️ ", "completed": "✅"}.get(
            s.status, "❓"
        )
        summary = s.summary[:60] if s.summary else "(no summary)"
        print(
            f"{status_icon} {s.session_id[:12]}...  "
            f"[{s.status}]  {s.entry_count} entries  {summary}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show entries for a session."""
    store = TranscriptStore()
    session_id = _resolve_session_id(store, args.session_id)
    if not session_id:
        return 1

    meta = store.get_session(session_id)
    if not meta:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1

    print(f"Session: {meta.session_id}")
    print(f"Status:  {meta.status}")
    print(f"Created: {meta.created}")
    print(f"Entries: {meta.entry_count}")
    print(f"Summary: {meta.summary or '(none)'}")
    print()

    if args.last:
        entries = store.read_recent(session_id, n=args.last)
    else:
        entries = store.read_entries(session_id)

    for entry in entries:
        print(_format_entry_line(entry))

    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search transcripts."""
    store = TranscriptStore()
    searcher = TranscriptSearcher(store)

    if args.session_id:
        session_id = _resolve_session_id(store, args.session_id)
        if not session_id:
            return 1
        hits = searcher.search(args.keywords, session_id=session_id)
        for hit in hits:
            print(f"  [{hit.entry_id[:12]}] {hit.keyword}: {hit.context_snippet}")
    else:
        results = searcher.search_sessions(args.keywords)
        if not results:
            print("No matches found.")
            return 0
        for result in results:
            print(
                f"Session {result.session_id[:12]}... "
                f"({result.summary or 'no summary'}) -- {len(result.hits)} hits"
            )
            for hit in result.hits[:_MAX_HITS_SHOWN]:
                print(f"    {hit.keyword}: {hit.context_snippet}")
            if len(result.hits) > _MAX_HITS_SHOWN:
                extra = len(result.hits) - _MAX_HITS_SHOWN
                print(f"    ... and {extra} more")

    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """Replay a full session."""
    store = TranscriptStore()
    session_id = _resolve_session_id(store, args.session_id)
    if not session_id:
        return 1

    entries = store.read_entries(session_id)
    if not entries:
        print("No entries to replay.")
        return 0

    print("## Full Session Replay")
    for entry in entries:
        print(_format_entry_line(entry))
    return 0


def cmd_resume(_args: argparse.Namespace) -> int:
    """Show most recent paused session."""
    store = TranscriptStore()
    resumable = store.get_resumable_session()
    if not resumable:
        print("No paused sessions found.")
        return 0
    print(f"Most recent paused session: {resumable.session_id}")
    print(f"Summary: {resumable.summary or '(none)'}")
    print(f"Entries: {resumable.entry_count}")
    print(f"Last active: {resumable.last_active}")
    print("\nUse 'ami-agent' to resume this session automatically.")
    return 0


def _resolve_session_id(store: TranscriptStore, partial: str) -> str | None:
    """Resolve a partial session ID to a full one."""
    # Exact match first
    if store.get_session(partial):
        return partial

    # Prefix match
    sessions = store.list_sessions()
    matches = [s for s in sessions if s.session_id.startswith(partial)]
    if len(matches) == 1:
        return matches[0].session_id
    if len(matches) > 1:
        print(f"Ambiguous session ID '{partial}'. Matches:", file=sys.stderr)
        for m in matches[:10]:
            print(f"  {m.session_id}", file=sys.stderr)
        return None

    print(f"Session not found: {partial}", file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "search": cmd_search,
        "replay": cmd_replay,
        "resume": cmd_resume,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
