"""Streaming-related utility functions extracted from base_provider.py."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import subprocess
import time
from typing import TYPE_CHECKING, Any, Protocol
import sys
import termios
import textwrap
import tty

from loguru import logger

from agents.ami.cli.env_utils import get_unprivileged_env
from agents.ami.cli.exceptions import (
    AgentCommandNotFoundError,
    AgentExecutionError,
    AgentTimeoutError,
)
from agents.ami.core.config import get_config
from agents.ami.cli.process_utils import handle_process_completion, start_streaming_process, read_streaming_line
from agents.ami.cli.streaming_utils import calculate_timeout
from agents.ami.cli.timer_utils import TimerDisplay
from agents.ami.core.logic import parse_completion_marker


if TYPE_CHECKING:
    pass


# Constants for display formatting
CONTENT_WIDTH = 76  # Content width for wrapped text (80 total - 4 for borders/indentation)
TOTAL_WIDTH = 80  # Total width for display boxes


class AgentConfigProtocol(Protocol):
    """Protocol for agent configuration to avoid circular imports."""

    session_id: str
    timeout: int | None
    enable_streaming: bool | None


# Define a protocol for the provider interface to avoid circular imports
class StreamMessageParser(Protocol):
    """Protocol defining the interface for stream message parsing."""

    def _parse_stream_message(
        self,
        line: str,
        cmd: list[str],
        line_count: int,
        agent_config: Any,
    ) -> tuple[str, dict[str, Any] | None]:
        """Parse a single line from CLI's streaming output."""
        ...


def run_streaming_loop(
    process: subprocess.Popen[str],
    cmd: list[str],
    agent_config: AgentConfigProtocol | None,
) -> tuple[str, dict[str, Any]]:
    """Run the main streaming loop to collect CLI output.

    Args:
        process: The subprocess to read from
        cmd: Original command for error reporting
        agent_config: Agent configuration

    Returns:
        Tuple of (output, metadata)
    """
    output_lines = []
    metadata: dict[str, Any] = {}
    line_count = 0
    started_at = time.time()

    session_id = agent_config.session_id if agent_config else "unknown"
    logger.info("streaming_loop_started", command=" ".join(cmd), session_id=session_id)

    while True:
        # Calculate timeout for this read

        timeout_val = calculate_timeout(agent_config.timeout if agent_config else None, line_count)

        line, is_timeout = read_streaming_line(process, timeout_val, cmd)

        if is_timeout:
            # Check if overall timeout was exceeded
            if agent_config and agent_config.timeout is not None:
                elapsed = time.time() - started_at
                if elapsed >= agent_config.timeout:
                    timeout_val = agent_config.timeout if agent_config else 0
                    timeout = agent_config.timeout or 0
                    raise AgentTimeoutError(timeout, cmd, elapsed) from None

            # Otherwise, just continue waiting
            continue

        if line is None:
            # Check if process has exited
            if process.poll() is not None:
                # Process has exited, handle completion
                break
            # No data but process still running, continue
            continue

        # Parse the line - this needs to be handled by the caller since it's specific to each provider
        # For now, we'll just collect the raw line
        output_lines.append(line + "\n")

        # Update counters and time
        line_count += 1
        time.time()

    # Combine all output
    final_output = "".join(output_lines)
    
    # Parse completion marker
    metadata["completion"] = parse_completion_marker(final_output)
    
    return final_output, metadata


def run_streaming_loop_with_display(
    process: subprocess.Popen[str],
    cmd: list[str],
    agent_config: AgentConfigProtocol | None,
    provider_instance: StreamMessageParser | None = None,
    capture_content: bool = False,  # When True, content is captured but not printed directly
) -> tuple[str, dict[str, Any]]:
    """Run the main streaming loop with clean output display.

    Args:
        process: The subprocess to read from
        cmd: Original command for error reporting
        agent_config: Agent configuration
        provider_instance: The CLI provider instance with _parse_stream_message method
        capture_content: When True, content is captured for return but not printed to stdout

    Returns:
        Tuple of (output, metadata)
    """
    display_context: dict[str, Any] = {
        "full_output": "",
        "started_at": time.time(),
        "session_id": agent_config.session_id if agent_config else "unknown",
        "timer": TimerDisplay(),
        "content_started": False,
        "box_displayed": False,
        "last_print_ended_with_newline": False,
        "capture_content": capture_content,  # Add flag to control output behavior
        "response_box_started": False,  # Track if response box top border has been displayed
        "response_box_ended": False,  # Track if response box bottom border has been displayed
        "line_buffer": "", # Buffer for incomplete lines to handle wrapping correctly
        "in_run_block": False, # Track if we are inside a ```run block for display sanitization
    }

    # Start the timer display
    timer_display = display_context["timer"]
    if isinstance(timer_display, TimerDisplay):
        timer_display.start()

    # Setup terminal for raw input if possible to detect ESC
    old_settings = None
    try:
        if sys.stdin.isatty():
            old_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
    except Exception:
        # If setting cbreak fails (e.g. not a real TTY in tests), ignore
        pass

    try:
        # Main streaming loop
        while True:
            should_continue = _handle_read_iteration(process, cmd, agent_config, display_context, provider_instance)
            if not should_continue:
                break
    finally:
        # Restore terminal settings
        if old_settings:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)

        timer_display = display_context["timer"]
        if isinstance(timer_display, TimerDisplay):
            _handle_display_cleanup(timer_display)

        # Flush any remaining buffer content
        if not display_context.get("capture_content", False) and display_context.get("line_buffer"):
             # Print whatever is left in the buffer, wrapped
             remaining = display_context["line_buffer"]
             wrapped = textwrap.fill(remaining, width=CONTENT_WIDTH).split("\n")
             for line in wrapped:
                 sys.stdout.write(f"  {line}\n")
             sys.stdout.flush()

        # Close response box if it was opened but not yet closed
        if (
            not display_context.get("capture_content", False)
            and display_context.get("response_box_started", False)
            and not display_context.get("response_box_ended", False)
        ):
            sys.stdout.write("└" + "─" * 78 + "┘\n")  # Bottom border
            sys.stdout.flush()
            display_context["response_box_ended"] = True

    # Add completion message after processing is done
    if not display_context.get("capture_content", False):
            # Display timestamp message after processing completes
            sys.stdout.write(f"🤖 {time.strftime('%H:%M:%S')}\n\n")
            sys.stdout.flush()
            metadata = {
        "session_id": display_context["session_id"],
        "duration": time.time() - display_context["started_at"],
        "output_length": len(display_context["full_output"]),
        "completion": parse_completion_marker(display_context["full_output"]),
    }
    return display_context["full_output"], metadata


def _handle_read_iteration(
    process: subprocess.Popen[str],
    cmd: list[str],
    agent_config: AgentConfigProtocol | None,
    display_context: dict[str, Any],
    provider_instance: StreamMessageParser | None,
) -> bool:
    """Handle a single iteration of the streaming read loop."""
    # Calculate timeout for this read
    timeout_val = calculate_timeout(agent_config.timeout if agent_config else None, len(display_context["full_output"]))

    # Read a line with timeout
    line, is_timeout = read_streaming_line(process, timeout_val, cmd, check_stdin=True)

    if is_timeout:
        # Check if overall timeout was exceeded
        return not _handle_timeout(cmd, agent_config, display_context["started_at"])

    if line is None:
        # Check if process has exited
        return process.poll() is None  # Continue if process is still running

    # Process the line based on whether we have a provider instance
    if provider_instance:
        _process_line_with_provider(line, cmd, display_context, provider_instance, len(display_context["full_output"]), agent_config)
    else:
        _process_raw_line(line, display_context)

    return True


def _handle_timeout(cmd: list[str], agent_config: AgentConfigProtocol | None, started_at: float) -> bool:
    """Handle timeout case. Returns True if we should stop the loop (timeout error), False to continue waiting."""
    if agent_config and agent_config.timeout is not None:
        elapsed = time.time() - started_at
        if elapsed >= agent_config.timeout:
            timeout = agent_config.timeout or 0
            raise AgentTimeoutError(timeout, cmd, elapsed) from None
    return False  # Continue waiting


def _process_line_with_provider(
    line: str,
    cmd: list[str],
    display_context: dict[str, Any],
    provider_instance: StreamMessageParser,
    line_count: int,
    agent_config: AgentConfigProtocol | None,
) -> None:
    """Process a line using the provider-specific parser."""
    chunk_text, chunk_metadata = provider_instance._parse_stream_message(line, cmd, line_count, agent_config)

    # Process the chunk
    if chunk_text:
        # Invoke stream callback if provided
        if agent_config and hasattr(agent_config, 'stream_callback') and agent_config.stream_callback:
            try:
                agent_config.stream_callback(chunk_text)
            except Exception as e:
                # Log but don't crash
                print(f"Stream callback error: {e}")

        if not display_context["content_started"]:
            if not display_context.get("capture_content", False):
                display_context["timer"].stop()
            display_context["content_started"] = True
            display_context["box_displayed"] = True
            if not display_context.get("capture_content", False):
                sys.stdout.write("┌" + "─" * 78 + "┐\n")
                sys.stdout.flush()
            display_context["response_box_started"] = True

        if not display_context.get("capture_content", False):
            current_buffer = display_context.get("line_buffer", "")
            current_buffer += chunk_text
            
            if "\n" in current_buffer:
                lines = current_buffer.split("\n")
                complete_lines = lines[:-1]
                display_context["line_buffer"] = lines[-1]
                
                # Process and print complete lines
                for line in complete_lines:
                    display_line = line
                    # Display-only replacements to make output clearer
                    if "```run" in display_line:
                        display_line = display_line.replace("```run", "</>")
                        display_context["in_run_block"] = True
                    
                    if "```" in display_line and display_context.get("in_run_block"):
                        # Replace the closing fence with empty string
                        display_line = display_line.replace("```", "")
                        display_context["in_run_block"] = False
                        # If the line is empty after removing the fence, skip printing it
                        if not display_line.strip():
                            continue
                    
                    # Print the line with indentation to match the text bubble style
                    print(f"  {display_line}")
            else:
                display_context["line_buffer"] = current_buffer

        display_context["last_print_ended_with_newline"] = chunk_text.endswith("\n")
        display_context["full_output"] += chunk_text

    if chunk_metadata:
        if "session_id" in chunk_metadata:
            display_context["session_id"] = chunk_metadata["session_id"]


def _process_raw_line(line: str, display_context: dict[str, Any]) -> None:
    """Process a raw line when no provider instance is available."""
    if not display_context["content_started"]:
        if not display_context.get("capture_content", False):
            display_context["timer"].stop()
        display_context["content_started"] = True
        display_context["box_displayed"] = True

    if len(line) <= CONTENT_WIDTH:
        if not display_context.get("capture_content", False):
            sys.stdout.write("  " + line + "\n")
            sys.stdout.flush()
        display_context["last_print_ended_with_newline"] = True
    else:
        wrapped = textwrap.fill(line, width=CONTENT_WIDTH).split("\n")
        for idx, wrap_line in enumerate(wrapped):
            if not display_context.get("capture_content", False):
                sys.stdout.write("  " + wrap_line + "\n")
                sys.stdout.flush()
            if idx < len(wrapped) - 1 and not display_context.get("capture_content", False):
                sys.stdout.write("\n")
                sys.stdout.flush()
        display_context["last_print_ended_with_newline"] = True
    display_context["full_output"] += line + "\n"


def _handle_display_cleanup(timer: TimerDisplay | None) -> None:
    """Handle cleanup of display elements."""
    if timer is not None and timer.is_running:
        timer.stop()


def execute_streaming(
    cmd: list[str],
    stdin_data: str | None = None,
    cwd: Path | None = None,
    agent_config: AgentConfigProtocol | None = None,
    config: Any = None,
    parse_stream_callback: Callable[..., Any] | None = None,  # Optional callback for parsing stream messages
) -> tuple[str, dict[str, Any] | None]:
    """Execute CLI command in streaming mode.

    Args:
        cmd: Command to execute
        stdin_data: Data to provide to stdin
        cwd: Working directory
        agent_config: Agent configuration
        config: Configuration object
        parse_stream_callback: Optional callback function for parsing stream messages with real-time display

    Returns:
        Tuple of (output, metadata)
    """
    if stdin_data is not None:
        return _execute_with_stdin(cmd, stdin_data, cwd, agent_config, config)
    return _execute_with_streaming(cmd, stdin_data, cwd, agent_config, config, parse_stream_callback)


def _execute_with_stdin(
    cmd: list[str], stdin_data: str, cwd: Path | None, agent_config: AgentConfigProtocol | None, config: Any
) -> tuple[str, dict[str, Any] | None]:
    """Execute command with stdin data provided upfront."""
    # Get unprivileged environment
    if config is None:
        config = get_config()
    env = get_unprivileged_env(config)
    if env is None:
        env = os.environ.copy()

    # Run the process with communicate to provide stdin data
    start_time = time.time()
    try:
        _validate_command(cmd)

        # Security review: Command validation already performed above (lines 329-337)
        # The cmd list is validated to be a list of strings with proper path checks
        result = subprocess.run(
            cmd,
            check=False,
            input=stdin_data,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=agent_config.timeout if agent_config and agent_config.timeout else None,
        )

        duration = time.time() - start_time

        if result.returncode != 0:
            raise AgentExecutionError(result.returncode, result.stdout, result.stderr, cmd)

        # Log completion
        logger.info(
            "agent_completed",
            session_id=agent_config.session_id if agent_config else "unknown",
            duration=duration,
            exit_code=result.returncode,
        )

        # Return output and basic metadata
        metadata: dict[str, Any] = {
            "session_id": agent_config.session_id if agent_config else "unknown",
            "duration": duration,
            "exit_code": result.returncode,
        }
        return result.stdout, metadata

    except subprocess.TimeoutExpired as e:
        timeout = agent_config.timeout if agent_config and agent_config.timeout else 0
        raise AgentTimeoutError(timeout, cmd, e.timeout) from e
    except FileNotFoundError:
        raise AgentCommandNotFoundError(cmd[0]) from None


def _execute_with_streaming(
    cmd: list[str],
    stdin_data: str | None,
    cwd: Path | None,
    agent_config: AgentConfigProtocol | None,
    config: Any,
    parse_stream_callback: Callable[..., Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Execute command in streaming mode."""
    # For no stdin, use the original streaming approach
    process = start_streaming_process(cmd, stdin_data, cwd, config)
    start_time = time.time()

    try:
        if parse_stream_callback:
            return _handle_callback_execution(process, cmd, agent_config, start_time, parse_stream_callback)
        return _handle_standard_execution(process, cmd, agent_config)
    finally:
        # Clean up process reference if needed
        pass


def _validate_command(cmd: list[str]) -> None:
    """Validate command to prevent injection attacks."""
    if not isinstance(cmd, list) or not all(isinstance(arg, str) for arg in cmd):
        raise ValueError(f"Invalid command format: {cmd}")
    # Ensure command paths are absolute or safe relative paths
    for arg in cmd:
        if arg.startswith(("..", "/", "~")) and not Path(arg).is_absolute():
            raise ValueError(f"Unsafe command path: {arg}")


def _handle_callback_execution(
    process: subprocess.Popen[str],
    cmd: list[str],
    agent_config: AgentConfigProtocol | None,
    start_time: float,
    parse_stream_callback: Callable[..., Any],
) -> tuple[str, dict[str, Any] | None]:
    """Handle execution with a callback function."""
    output, metadata = parse_stream_callback(process, cmd, agent_config)

    # For streaming callbacks, we handle completion within the callback,
    # so return the output directly
    duration = time.time() - start_time
    session_id = agent_config.session_id if agent_config else "unknown"

    # Check if process completed successfully
    returncode = process.poll() or 0
    
    # Capture stderr to diagnose failures
    _, stderr_output = process.communicate()

    if returncode != 0:
        # If we failed and didn't produce any streaming output, we MUST raise to let the user know why
        if not output:
            raise AgentExecutionError(returncode, output, stderr_output, cmd)
        
        # If we did produce output, we might still want to log the stderr
        if stderr_output:
             print(f"\n[Process Error Output]:\n{stderr_output}")

    # Update metadata with duration if not already present
    if metadata is None:
        metadata = {}
        
    # Only set session_id from config if NOT already present in metadata (captured from stream)
    if "session_id" not in metadata or not metadata["session_id"]:
        metadata["session_id"] = session_id
        
    metadata.update({"duration": duration, "exit_code": returncode})
    return output, metadata


def _handle_standard_execution(
    process: subprocess.Popen[str],
    cmd: list[str],
    agent_config: AgentConfigProtocol | None,
) -> tuple[str, dict[str, Any] | None]:
    """Handle standard execution without a callback."""
    output, metadata = run_streaming_loop(process, cmd, agent_config)
    return handle_process_completion(process, cmd, time.time(), agent_config.session_id if agent_config else "unknown")
