"""Process-related utility functions for streaming."""

import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from ami.cli.env_utils import get_unprivileged_env
from ami.cli.exceptions import (
    AgentCommandNotFoundError,
    AgentExecutionError,
    AgentTimeoutError,
)
from ami.core.config import Config, get_config
from ami.types.api import ProviderMetadata

if TYPE_CHECKING:
    from ami.types.config import AgentConfig

# ASCII code for ESC key
ESC_KEY_CODE = 27


def start_streaming_process(
    cmd: list[str],
    stdin_data: str | None,
    cwd: Path | None,
    config: Config | None = None,
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
    resolved_config: Config = config if config is not None else get_config()
    env = get_unprivileged_env(resolved_config)
    if env is None:
        env = os.environ.copy()

    stdin_pipe = subprocess.PIPE if stdin_data is not None else None

    try:
        if not isinstance(cmd, list) or not all(isinstance(arg, str) for arg in cmd):
            raise ValueError(f"Invalid command format: {cmd}")
        for arg in cmd:
            if arg.startswith(("..", "/", "~")) and not Path(arg).is_absolute():
                raise ValueError(f"Unsafe command path: {arg}")

        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin_pipe,
            text=True,
            bufsize=1,
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
    try:
        rlist = [process.stdout]
        if check_stdin and not sys.stdin.closed and sys.stdin.isatty():
            rlist.append(sys.stdin)

        ready, _, _ = select.select(rlist, [], [], timeout_val)

        if sys.stdin in ready:
            key = sys.stdin.read(1)
            if ord(key) == ESC_KEY_CODE:
                raise KeyboardInterrupt("User interrupted with Esc")

        if not ready or process.stdout not in ready:
            return None, True

        if process.stdout is not None:
            line = process.stdout.readline()
            if not line:
                return None, False

            return line.rstrip(), False
    except OSError:
        stdout, stderr = process.communicate()
        raise AgentExecutionError(process.returncode, stdout, stderr, cmd) from None
    else:
        return None, False


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
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise AgentExecutionError(
            process.returncode,
            stdout,
            stderr,
            ["cli"],
        ) from None

    return stdout


def handle_first_output_logging(
    agent_config: "AgentConfig | None",
) -> None:
    """Handle logging for first output from agent.

    Args:
        agent_config: Agent configuration
    """
    if agent_config is not None:
        session_id = agent_config.session_id or "unknown"
        timeout_val = agent_config.timeout
        logger.info(
            "agent_first_output_waiting",
            extra={
                "session_id": session_id,
                "timeout": timeout_val,
            },
        )


def handle_process_completion(
    process: subprocess.Popen[str],
    cmd: list[str],
    started_at: float,
    session_id: str,
) -> tuple[str, ProviderMetadata | None]:
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

    if process.poll() is not None:
        stdout, stderr = process.communicate()
    else:
        stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise AgentExecutionError(process.returncode, stdout, stderr, cmd) from None

    logger.info(
        "agent_completed",
        session_id=session_id,
        duration=duration,
        exit_code=process.returncode,
    )

    metadata = ProviderMetadata(
        session_id=session_id,
        duration=duration,
        exit_code=process.returncode,
    )
    return stdout, metadata
