"""Mode handler functions for main CLI entry point."""

from datetime import datetime
from pathlib import Path
import sys

from ami.utils.uuid_utils import uuid7
from ami.cli.config import AgentConfigPresets
from ami.cli.exceptions import AgentError, AgentExecutionError
from ami.cli.factory import get_agent_cli
from ami.cli.timer_utils import wrap_text_in_box
from ami.cli.validation_utils import (
    validate_path_and_return_code,
)
from ami.core.bootloader_agent import BootloaderAgent
from ami.cli_components.text_input_utils import display_final_output
from ami.cli_components.text_editor import TextEditor
from ami.cli_components.dialogs import confirm
from ami.core.config import get_config


def get_user_confirmation(command: str) -> bool:
    """Get Y/N confirmation from user via TUI dialog."""
    return confirm(command, title="Execute Command?")


def get_latest_session_id() -> str | None:
    """Find the most recent session ID from transcript logs."""
    try:
        config = get_config()
        transcripts_dir = config.root / "logs" / "transcripts"
        if not transcripts_dir.exists():
            return None
            
        # Find all jsonl files recursively
        files = list(transcripts_dir.rglob("*.jsonl"))
        if not files:
            return None
            
        # Sort by modification time, newest first
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Return the stem (filename without extension) of the newest file
        return files[0].stem
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

        # Enable streaming mode with content capture in configuration, but disable hooks for query mode
        # Pass session_id=None to let provider manage session creation (avoids Qwen --resume failure)
        config = AgentConfigPresets.worker(session_id=None)
        config.enable_hooks = False  # Disable hooks for query mode to avoid quality violations
        config.enable_streaming = True  # Enable streaming to show timer during processing
        config.capture_content = False  # Disable content capture to allow streaming display

        # Run with streaming to capture content while showing timer
        output, metadata = cli.run_print(
            instruction=query,
            agent_config=config,
        )

        # The response will be handled by the streaming loop which formats it in a box
        # and displays the timestamp message

        return 0
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
            instruction_file=instruction_file,
            stdin=stdin,
            agent_config=AgentConfigPresets.worker(session_id=None),
        )
        # Print output
        return 0
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


def mode_interactive_editor() -> int:
    """Interactive editor mode - opens text editor first, Ctrl+S sends to agent.

    Args:
        None

    Returns:
        Exit code (0=success, 1=failure)
    """

    try:
        try:
            # Launch text editor and get content
            editor = TextEditor()
            content = editor.run(clear_on_submit=True)

            if content is None:  # User cancelled with Ctrl+C
                # Show discarded message
                display_final_output(editor.lines, "❌ Message discarded")
                return 0  # Exit quietly

            # If content is empty, exit gracefully
            if not content.strip():
                return 0  # Exit quietly

            # Display "Sent" confirmation
            display_final_output(content.splitlines(), "✅ Sent to agent")

        except KeyboardInterrupt:
            # User cancelled with Ctrl+C
            return 0  # Exit quietly

        # Instantiate BootloaderAgent once for the session with injected runtime
        cli = get_agent_cli()
        agent = BootloaderAgent(runtime=cli)
        
        # Initial input (from first editor run)
        current_instruction = content
        # Resume last session if available
        current_session_id = get_latest_session_id()
        if current_session_id:
            sys.stdout.write(f"🔄 Resuming session: {current_session_id}\n")
        
        while True:
            # Prepare initial text for next editor run (defaults to empty unless cancelled)
            next_initial_text = ""
            
            try:
                # Run agent loop (ReAct: Think -> Act -> Loop)
                # The agent maintains state via session_id passed to the provider
                _, current_session_id = agent.run(
                    instruction=current_instruction,
                    session_id=current_session_id,
                    input_func=get_user_confirmation
                )
            except KeyboardInterrupt:
                # User cancelled with Ctrl+C or Esc
                sys.stdout.write("\n❌ Cancelled by user.\n\n")
                sys.stdout.flush()
                # Pre-fill editor with the message we just sent/cancelled
                next_initial_text = current_instruction
            
            # --- SESSION LOOP ---
            # Immediately relaunch editor for next turn
            # Launch editor for next turn
            editor = TextEditor(initial_text=next_initial_text)
            next_content = editor.run(clear_on_submit=True)
            
            if next_content is None or not next_content.strip():
                sys.stdout.write("❌ Empty input or cancelled. Exiting session.\n")
                break
                
            current_instruction = next_content
            display_final_output(current_instruction.splitlines(), "✅ Sent to agent")

        return 0
    except Exception as e:
        # Print error for debugging
        sys.stderr.write(f"Error calling agent: {str(e)}\n")
        sys.stderr.flush()
        return 1
