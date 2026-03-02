"""Mode handler functions for main CLI entry point."""

import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from ami.cli.factory import get_agent_cli
from ami.cli.timer_utils import wrap_text_in_box
from ami.cli.transcript_store import TranscriptStore
from ami.cli.validation_utils import validate_path_and_return_code
from ami.cli_components.dialogs import confirm
from ami.cli_components.session_browser import browse_sessions_with_filter
from ami.cli_components.session_detail import (
    ACTION_DELETE,
    ACTION_RESUME,
    run_session_detail,
)
from ami.cli_components.text_editor import TextEditor
from ami.cli_components.text_input_utils import display_final_output
from ami.core.bootloader_agent import BootloaderAgent, RunContext
from ami.core.conversation import EntryRole
from ami.core.factory import AgentFactory


class _SessionResult(NamedTuple):
    """Result from session resolution."""

    session_id: str
    resumed: bool


__all__ = [
    "display_final_output",
    "get_agent_cli",
    "get_latest_session_id",
    "mode_interactive_editor",
    "mode_print",
    "mode_query",
    "mode_sessions",
]


def get_user_confirmation(command: str) -> bool:
    """Get Y/N confirmation from user via TUI dialog."""
    return confirm(command, title="Execute Command?")


def get_latest_session_id() -> str | None:
    """Find the most recent session ID from transcript logs."""
    try:
        store = TranscriptStore()
        sessions = store.list_sessions()
        if not sessions:
            return None
        return sessions[0].session_id
    except Exception:
        return None


def _get_active_session(
    store: TranscriptStore, interactive: bool = False
) -> _SessionResult:
    """Resolve the transcript session ID, optionally prompting to resume."""
    current_cwd = str(Path.cwd())
    resumable = store.get_resumable_session(cwd=current_cwd)
    if interactive and resumable:
        sys.stdout.write(
            f"📋 Resumable session found: {resumable.session_id[:8]}..."
            f" ({resumable.summary or 'no summary'})\n"
        )
        if confirm("Resume previous session?", title="Resume Session"):
            store.update_session(resumable.session_id, status="active")
            return _SessionResult(resumable.session_id, resumed=True)

    new_id = store.create_session(
        provider="bootloader", model="default", cwd=current_cwd
    )
    return _SessionResult(new_id, resumed=False)


def _replay_session(store: TranscriptStore, transcript_id: str) -> None:
    """Display previous conversation entries for a resumed session."""
    entries = store.read_entries(transcript_id)
    if not entries:
        return

    _TS_DISPLAY_LEN = 19

    for entry in entries:
        if entry.role == EntryRole.USER:
            sys.stdout.write(wrap_text_in_box(entry.content) + "\n")
            ts = entry.timestamp[:_TS_DISPLAY_LEN]
            sys.stdout.write(f"💬 {ts}\n\n")
        elif entry.role == EntryRole.ASSISTANT:
            sys.stdout.write(wrap_text_in_box(entry.content) + "\n")
            ts = entry.timestamp[:_TS_DISPLAY_LEN]
            sys.stdout.write(f"🤖 {ts}\n\n")

    sys.stdout.flush()


def _execute_turn(
    agent: BootloaderAgent,
    store: TranscriptStore,
    transcript_id: str,
    query: str,
) -> int | None:
    """Execute a single agent turn. Returns 1 on fatal error, None on success."""
    sys.stdout.write(wrap_text_in_box(query) + "\n")
    sys.stdout.write(f"💬 {datetime.now().strftime('%H:%M:%S')}\n\n")
    sys.stdout.flush()

    try:
        ctx = RunContext(
            instruction=query,
            transcript_id=transcript_id,
            input_func=get_user_confirmation,
            scope_overrides={
                "observe": "allow",
                "modify": "confirm",
                "execute": "confirm",
            },
        )
        agent.run(ctx)
    except KeyboardInterrupt:
        sys.stdout.write(f"\n❌ Cancelled. {datetime.now().strftime('%H:%M:%S')}\n\n")
    except Exception as e:
        sys.stderr.write(f"\nError: {e}\n")
        store.update_session(transcript_id, status="paused")
        return 1

    return None


def _run_session_loop(
    agent: BootloaderAgent,
    transcript_id: str,
    initial_query: str | None = None,
    interactive: bool = True,
    resumed: bool = False,
) -> int:
    """Universal agent execution loop for both query and interactive modes."""
    store = TranscriptStore()
    current_query = initial_query

    if resumed:
        _replay_session(store, transcript_id)

    while True:
        if current_query is None:
            if not interactive:
                break
            editor = TextEditor()
            current_query = editor.run(clear_on_submit=True)

        if current_query is None or not current_query.strip():
            if interactive:
                sys.stdout.write("❌ Session ended.\n")
                store.update_session(transcript_id, status="paused")
            break

        error = _execute_turn(agent, store, transcript_id, current_query)
        if error is not None:
            return error

        current_query = None
        if not interactive:
            break

    if not interactive:
        store.update_session(transcript_id, status="completed")

    return 0


def mode_query(query: str) -> int:
    """Run a single-turn agent query (always creates a fresh session)."""
    agent = AgentFactory.create_bootloader()
    store = TranscriptStore()
    transcript_id = store.create_session(
        provider="bootloader", model="default", cwd=str(Path.cwd())
    )

    return _run_session_loop(
        agent, transcript_id, initial_query=query, interactive=False
    )


def mode_interactive_editor() -> int:
    """Run a multi-turn interactive agent session."""
    agent = AgentFactory.create_bootloader()
    store = TranscriptStore()
    transcript_id, resumed = _get_active_session(store, interactive=True)

    return _run_session_loop(agent, transcript_id, interactive=True, resumed=resumed)


def mode_sessions() -> int:
    """Interactive session browser mode."""
    store = TranscriptStore()

    while True:
        session_id = browse_sessions_with_filter(store)
        if session_id is None:
            return 0

        result = run_session_detail(store, session_id)
        if result == ACTION_RESUME:
            store.update_session(session_id, status="active")
            agent = AgentFactory.create_bootloader()
            return _run_session_loop(agent, session_id, interactive=True, resumed=True)
        if result == ACTION_DELETE and confirm(
            f"Delete session {session_id[:12]}?",
            title="Confirm Delete",
        ):
            store.delete_session(session_id)
        # ACTION_BACK or post-delete: loop back to browser


def mode_print(instruction_path: str) -> int:
    """Non-interactive mode - Run agent with --print."""
    if validate_path_and_return_code(instruction_path) != 0:
        return 1

    instruction_content = Path(instruction_path).read_text()
    stdin = sys.stdin.read()
    if stdin:
        instruction_content += f"\n\nContext from stdin:\n{stdin}"

    return mode_query(instruction_content)
