"""Mode handler functions for main CLI entry point."""

import sys
from datetime import datetime
from pathlib import Path

from ami.cli.config import AgentConfigPresets
from ami.cli.exceptions import AgentError, AgentExecutionError
from ami.cli.factory import get_agent_cli
from ami.cli.timer_utils import wrap_text_in_box
from ami.cli.transcript_store import TranscriptStore
from ami.cli.validation_utils import (
    validate_path_and_return_code,
)
from ami.cli_components.dialogs import confirm
from ami.cli_components.text_editor import TextEditor
from ami.cli_components.text_input_utils import display_final_output
from ami.core.bootloader_agent import BootloaderAgent, RunContext
from ami.core.factory import AgentFactory
from ami.core.interfaces import RunPrintParams


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


def mode_query(query: str) -> int:
    """Non-interactive query mode - run agent with provided query string.

    Args:
        query: The query string to send to the agent

    Returns:
        Exit code (0=success, 1=failure)
    """
    # Format and display the user's input with borders and "Sent" message
    sys.stdout.write(wrap_text_in_box(query) + "\n")
    # Send message to agent
    sys.stdout.write(f"💬 {datetime.now().strftime('%H:%M:%S')}\n")
    sys.stdout.flush()

    try:
        # Get CLI instance
        cli = get_agent_cli()

        # Enable streaming mode with content capture in config,
        # but disable hooks for query mode.
        # Pass session_id=None to let provider manage session creation
        # (avoids Qwen --resume failure)
        config = AgentConfigPresets.worker(session_id=None)
        config.enable_hooks = (
            False  # Disable hooks for query mode to avoid quality violations
        )
        config.enable_streaming = (
            True  # Enable streaming to show timer during processing
        )
        config.capture_content = (
            False  # Disable content capture to allow streaming display
        )

        # Run with streaming to capture content while showing timer
        _output, _metadata = cli.run_print(
            params=RunPrintParams(
                instruction=query,
                agent_config=config,
            )
        )

        # The response will be handled by the streaming loop which formats it in a box
        # and displays the timestamp message

    except KeyboardInterrupt:
        # User cancelled with Ctrl+C
        sys.stdout.write(f"🤖 {datetime.now().strftime('%H:%M:%S')}\n\n")
        sys.stdout.flush()
        return 0
    except Exception:
        # Even if there's an error, try to display a completion message
        sys.stdout.write(f"🤖 {datetime.now().strftime('%H:%M:%S')}\n\n")
        sys.stdout.flush()
        return 1
    else:
        return 0


def mode_print(instruction_path: str) -> int:
    """Non-interactive mode - Run agent with --print.

    Uses worker agent preset (hooks enabled, all tools).

    Args:
        instruction_path: Path to instruction file

    Returns:
        Exit code (0=success, 1=failure)
    """
    if validate_path_and_return_code(instruction_path) != 0:
        return 1

    instruction_file = Path(instruction_path)

    # Read stdin
    stdin = sys.stdin.read()

    # Run with worker agent preset (hooks enabled, all tools)
    cli = get_agent_cli()
    try:
        # Pass session_id=None to let provider manage session creation
        cli.run_print(
            params=RunPrintParams(
                instruction_file=instruction_file,
                stdin=stdin,
                agent_config=AgentConfigPresets.worker(session_id=None),
            )
        )
        # Print output
    except AgentExecutionError as e:
        # Print output even on failure
        sys.stderr.write(f"Agent execution error: {e}\n")
        return e.exit_code
    except AgentError as e:
        sys.stderr.write(f"Agent error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 1
    else:
        return 0


def _resolve_transcript_session(store: TranscriptStore) -> str:
    """Resolve transcript session: resume existing or create new."""
    resumable = store.get_resumable_session()
    if resumable:
        sys.stdout.write(
            f"📋 Resumable session found: {resumable.session_id[:8]}..."
            f" ({resumable.summary or 'no summary'})\n"
        )
        if confirm("Resume previous session?", title="Resume Session"):
            store.update_session(resumable.session_id, status="active")
            return resumable.session_id
    return store.create_session(provider="bootloader", model="default")


def _run_editor_loop(
    agent: BootloaderAgent,
    store: TranscriptStore,
    transcript_id: str,
    first_instruction: str,
) -> None:
    """Run the interactive editor-agent loop until user exits."""
    current_instruction = first_instruction

    while True:
        next_initial_text = ""

        try:
            ctx = RunContext(
                instruction=current_instruction,
                session_id=None,
                transcript_id=transcript_id,
                input_func=get_user_confirmation,
            )
            agent.run(ctx)
        except KeyboardInterrupt:
            sys.stdout.write("\n❌ Cancelled by user.\n\n")
            sys.stdout.flush()
            next_initial_text = current_instruction

        editor = TextEditor(initial_text=next_initial_text)
        next_content = editor.run(clear_on_submit=True)

        if next_content is None or not next_content.strip():
            sys.stdout.write("❌ Empty input or cancelled. Exiting session.\n")
            store.update_session(transcript_id, status="paused")
            break

        current_instruction = next_content
        display_final_output(current_instruction.splitlines(), "✅ Sent to agent")


def mode_interactive_editor() -> int:
    """Interactive editor mode - opens text editor first, Ctrl+S sends to agent.

    Returns:
        Exit code (0=success, 1=failure)
    """

    try:
        try:
            editor = TextEditor()
            content = editor.run(clear_on_submit=True)

            if content is None:
                display_final_output(editor.lines, "❌ Message discarded")
                return 0

            if not content.strip():
                return 0

            display_final_output(content.splitlines(), "✅ Sent to agent")

        except KeyboardInterrupt:
            return 0

        agent = AgentFactory.create_bootloader()
        store = TranscriptStore()
        transcript_id = _resolve_transcript_session(store)

        _run_editor_loop(agent, store, transcript_id, content)

    except Exception as e:
        sys.stderr.write(f"Error calling agent: {e!s}\n")
        sys.stderr.flush()
        return 1
    else:
        return 0
