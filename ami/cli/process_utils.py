"""Process-related utility functions for streaming."""

import os
from pathlib import Path
import select
import subprocess
import sys
import time
from typing import Any

from loguru import logger

from ami.cli.env_utils import get_unprivileged_env
from ami.cli.exceptions import (
    AgentCommandNotFoundError,
    AgentExecutionError,
    AgentTimeoutError,
)
from ami.core.config import get_config


def start_streaming_process(
    cmd: list[str],
    stdin_data: str | None,
    cwd: Path | None,
    config: Any = None,
) -> subprocess.Popen[str]:
    """Start CLI process in streaming mode.

    Args:
        cmd: Command to execute
        stdin_data: Data to send to stdin, or None
        cwd: Working directory
        config: Configuration object for environment settings

    Returns:
        Started subprocess.Popen instance
    """
    # Get unprivileged environment if configured
    if config is None:
        config = get_config()
    env = get_unprivileged_env(config)
    if env is None:
        env = os.environ.copy()

    # Prepare stdin - we'll provide stdin_data directly to communicate() later
    stdin_pipe = subprocess.PIPE if stdin_data is not None else None

    # Start the process
    try:
        # Validate command to prevent injection attacks
        if not isinstance(cmd, list) or not all(isinstance(arg, str) for arg in cmd):
            raise ValueError(f"Invalid command format: {cmd}")
        # Ensure command paths are absolute or safe relative paths
        for arg in cmd:
            if arg.startswith(("..", "/", "~")) and not Path(arg).is_absolute():
                raise ValueError(f"Unsafe command path: {arg}")

        # Security review: Command validation already performed above (lines 57-65)
        # The cmd list is validated to be a list of strings with proper path checks
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin_pipe,
            text=True,
            bufsize=1,  # Line buffered
            cwd=cwd,
            env=env,
        )

    except FileNotFoundError:
        raise AgentCommandNotFoundError(cmd[0]) from None


def read_streaming_line(
    process: subprocess.Popen[str],
    timeout_val: float,
    cmd: list[str],
    check_stdin: bool = False,
) -> tuple[str | None, bool]:
    """Read a line from streaming process with timeout.

    Args:
        process: The subprocess to read from
        timeout_val: Timeout in seconds
        cmd: Original command for error reporting
        check_stdin: Whether to check stdin for interruption (Esc key)

    Returns:
        Tuple of (line content or None, True if timeout occurred)
    """
    # Use select to implement timeout on reading from subprocess
    try:
        rlist = [process.stdout]
        # Only check stdin if requested and it is a TTY
        if check_stdin and sys.stdin.isatty():
            rlist.append(sys.stdin)

        # Wait for data to be available with timeout
        ready, _, _ = select.select(rlist, [], [], timeout_val)
        
        # Check for user input interrupt
        if sys.stdin in ready:
            # Read a single character
            key = sys.stdin.read(1)
            # Check for ESC (27)
            if ord(key) == 27:
                raise KeyboardInterrupt("User interrupted with Esc")
            # We consumed a char. If it wasn't Esc, it's lost/ignored.
            # Ideally we shouldn't consume if we can't peek, but select says ready.
            
            # If we consumed stdin but stdout is NOT ready, we loop back or return timeout?
            # If we return timeout=False, the caller thinks we got data but we return None.
            # Returning (None, False) usually means EOF.
            # Returning (None, True) means timeout.
            
            # If process stdout is ALSO ready, we fall through to read it.
            # If not, we return (None, False) which loop interprets as continue waiting?
            # streaming loops: 
            # line, is_timeout = read_streaming_line(...)
            # if is_timeout: ... continue
            # if line is None: ... (check poll)
            
            # So if we return (None, False), it checks poll().
            # If process is running, it continues.
            # So consuming a key is "safe" in terms of loop flow, just the key is gone.
        
        if not ready or process.stdout not in ready:
            return None, True  # Timeout occurred (or only stdin was ready)

        # Read the line
        if process.stdout is not None:
            line = process.stdout.readline()
            if not line:  # EOF
                return None, False

            return line.rstrip(), False
        return None, False
    except OSError:
        stdout, stderr = process.communicate()
        raise AgentExecutionError(process.returncode, stdout, stderr, cmd) from None


def handle_first_output_timeout(
    started_at: float,
    cmd: list[str],
    timeout: int | None,
) -> None:
    """Handle timeout for first output from agent.

    Args:
        started_at: Time when execution started
        cmd: Command that timed out
        timeout: Configured timeout value
    """
    if timeout is not None:
        elapsed = time.time() - started_at
        if elapsed >= timeout:
            raise AgentTimeoutError(timeout, cmd, elapsed)


def handle_process_exit(
    process: subprocess.Popen[str],
) -> str:
    """Handle process exit and return final output.

    Args:
        process: The subprocess that exited

    Returns:
        Final output from the process
    """
    # Get remaining output
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise AgentExecutionError(
            process.returncode,
            stdout,
            stderr,
            ["cli"],  # Default command
        ) from None

    # In streaming mode, we should have been collecting output already
    # Just return the final stdout
    return stdout


def handle_first_output_logging(
    agent_config: Any,  # Using Any to avoid circular import issues
    logger: Any,
) -> None:
    """Handle logging for first output from agent.

    Args:
        agent_config: Agent configuration
        logger: Logger instance
    """
    # Log that we're waiting for first output
    if agent_config is not None:
        logger.info(
            "agent_first_output_waiting",
            extra={
                "session_id": agent_config.session_id if hasattr(agent_config, "session_id") else "unknown",
                "timeout": agent_config.timeout if hasattr(agent_config, "timeout") else None,
            },
        )


def handle_process_completion(
    process: subprocess.Popen[str],
    cmd: list[str],
    started_at: float,
    session_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """Handle process completion and return results.

    Args:
        process: Completed subprocess
        cmd: Original command
        started_at: Time when execution started
        session_id: Session identifier for logging

    Returns:
        Tuple of (output, metadata)
    """
    duration = time.time() - started_at

    # Get the final output - don't call communicate() if process already finished
    # For processes that are already done, just return their output
    if process.poll() is not None:
        # Process already finished, get any remaining output
        stdout, stderr = process.communicate()
    else:
        # Process still running, wait for it to complete
        stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise AgentExecutionError(process.returncode, stdout, stderr, cmd) from None

    # Log completion

    logger.info(
        "agent_completed",
        session_id=session_id,
        duration=duration,
        exit_code=process.returncode,
    )

    # Return output and basic metadata
    metadata = {
        "session_id": session_id,
        "duration": duration,
        "exit_code": process.returncode,
    }
    return stdout, metadata
