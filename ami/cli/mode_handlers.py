"""Mode handler functions for main CLI entry point."""

import sys
from datetime import datetime
from pathlib import Path

from ami.cli.factory import get_agent_cli
from ami.cli.timer_utils import wrap_text_in_box
from ami.cli.transcript_store import TranscriptStore
from ami.cli.validation_utils import validate_path_and_return_code
from ami.cli_components.dialogs import confirm
from ami.cli_components.text_editor import TextEditor
from ami.cli_components.text_input_utils import display_final_output
from ami.core.bootloader_agent import BootloaderAgent, RunContext
from ami.core.factory import AgentFactory

__all__ = [
    "display_final_output",
    "get_agent_cli",
    "get_latest_session_id",
    "mode_interactive_editor",
    "mode_print",
    "mode_query",
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


def _get_active_session(store: TranscriptStore, interactive: bool = False) -> str:
    """Resolve the transcript session ID, optionally prompting to resume."""
    resumable = store.get_resumable_session()
    if interactive and resumable:
        sys.stdout.write(
            f"📋 Resumable session found: {resumable.session_id[:8]}..."
            f" ({resumable.summary or 'no summary'})\n"
        )
        if confirm("Resume previous session?", title="Resume Session"):
            store.update_session(resumable.session_id, status="active")
            return resumable.session_id

    return store.create_session(provider="bootloader", model="default")


def _run_session_loop(
    agent: BootloaderAgent,
    transcript_id: str,
    initial_query: str | None = None,
    interactive: bool = True,
) -> int:
    """Universal agent execution loop for both query and interactive modes."""
    store = TranscriptStore()
    current_query = initial_query

    while True:
        # 1. Get query if not provided (interactive mode)
        if current_query is None:
            if not interactive:
                break
            editor = TextEditor()
            current_query = editor.run(clear_on_submit=True)

        # 2. Exit on empty/cancelled input
        if current_query is None or not current_query.strip():
            if interactive:
                sys.stdout.write("❌ Session ended.\n")
                store.update_session(transcript_id, status="paused")
            break

        # 3. Format and display input
        sys.stdout.write(wrap_text_in_box(current_query) + "\n")
        sys.stdout.write(f"💬 {datetime.now().strftime('%H:%M:%S')}\n\n")
        sys.stdout.flush()

        # 4. Execute Agent turn
        try:
            ctx = RunContext(
                instruction=current_query,
                transcript_id=transcript_id,
                input_func=get_user_confirmation,
            )
            agent.run(ctx)
        except KeyboardInterrupt:
            sys.stdout.write(
                f"\n❌ Cancelled. {datetime.now().strftime('%H:%M:%S')}\n\n"
            )
        except Exception as e:
            sys.stderr.write(f"\nError: {e}\n")
            return 1

        # 5. Clean up turn
        current_query = None
        if not interactive:
            break

    return 0


def mode_query(query: str) -> int:
    """Run a single-turn agent query."""
    agent = AgentFactory.create_bootloader()
    store = TranscriptStore()
    # For queries, we just use the latest session without prompting
    resumable = store.get_resumable_session()
    transcript_id = resumable.session_id if resumable else _get_active_session(store)

    return _run_session_loop(
        agent, transcript_id, initial_query=query, interactive=False
    )


def mode_interactive_editor() -> int:
    """Run a multi-turn interactive agent session."""
    agent = AgentFactory.create_bootloader()
    store = TranscriptStore()
    transcript_id = _get_active_session(store, interactive=True)

    return _run_session_loop(agent, transcript_id, interactive=True)


def mode_print(instruction_path: str) -> int:
    """Non-interactive mode - Run agent with --print."""
    if validate_path_and_return_code(instruction_path) != 0:
        return 1

    instruction_content = Path(instruction_path).read_text()
    stdin = sys.stdin.read()
    if stdin:
        instruction_content += f"\n\nContext from stdin:\n{stdin}"

    return mode_query(instruction_content)
