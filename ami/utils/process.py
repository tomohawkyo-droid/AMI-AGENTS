"""Process execution utilities for AMI Agents.

Provides robust subprocess management using memory-based pipes and selectors
to avoid deadlocks and minimize disk I/O.
"""

import os
import selectors
import subprocess
import time
from io import TextIOWrapper
from pathlib import Path
from typing import TypedDict, cast

from ami.types.common import ProcessEnvironment
from ami.types.results import SelectorEvent

# Return code for timeout
TIMEOUT_RETURN_CODE = 124

# Selector poll interval in seconds
SELECTOR_POLL_INTERVAL = 0.1


class ProcessResult(TypedDict):
    """Result from process execution."""

    stdout: str
    stderr: str
    returncode: int


def _create_result(stdout: str, stderr: str, returncode: int) -> ProcessResult:
    """Create a standardized result dictionary."""
    return {
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
    }


def _drain_pipes(
    sel: selectors.DefaultSelector,
    stdout_data: list[str],
    stderr_data: list[str],
) -> None:
    """Drain remaining data from all registered pipes."""
    for key in list(sel.get_map().values()):
        fileobj = cast(TextIOWrapper, key.fileobj)
        remaining = fileobj.read()
        if remaining:
            key.data.append(remaining)
        sel.unregister(key.fileobj)


def _process_pipe_events(
    sel: selectors.DefaultSelector,
    events: list[SelectorEvent],
) -> None:
    """Process read events from pipes."""
    for event in events:
        fileobj = event.key.fileobj
        if not isinstance(fileobj, TextIOWrapper):
            continue
        line = fileobj.readline()
        if line:
            event.key.data.append(line)
        else:
            sel.unregister(event.key.fileobj)


class ProcessExecutor:
    """Synchronous process executor using memory-based pipes and selectors."""

    def __init__(self, work_dir: Path | None = None):
        self.work_dir = work_dir or Path.cwd()

    def run(
        self,
        command: str | list[str],
        cwd: Path | None = None,
        env: ProcessEnvironment | None = None,
        timeout: int | None = None,
    ) -> ProcessResult:
        """
        Run a command and capture output via pipes.

        Args:
            command: Command string or list of arguments.
            cwd: Working directory (defaults to self.work_dir).
            env: Environment variables (defaults to os.environ).
            timeout: Execution timeout in seconds.

        Returns:
            ProcessResult containing stdout, stderr, returncode.
        """
        cwd = cwd or self.work_dir
        if not cwd.exists():
            return _create_result("", f"Working directory does not exist: {cwd}", 1)

        run_env = os.environ.copy()
        if env:
            # ProcessEnvironment is a TypedDict subset of env vars
            run_env.update(cast(dict, env))

        try:
            return self._execute_command(
                command, cwd, cast(ProcessEnvironment, run_env), timeout
            )
        except Exception as e:
            return _create_result("", f"Execution failed: {e!s}", 1)

    def _execute_command(
        self,
        command: str | list[str],
        cwd: Path,
        run_env: ProcessEnvironment,
        timeout: int | None,
    ) -> ProcessResult:
        """Execute command and collect output."""
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=cast(dict, run_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=isinstance(command, str),
            text=True,
            bufsize=1,
        )

        stdout_data: list[str] = []
        stderr_data: list[str] = []

        sel = selectors.DefaultSelector()
        if process.stdout:
            sel.register(process.stdout, selectors.EVENT_READ, stdout_data)
        if process.stderr:
            sel.register(process.stderr, selectors.EVENT_READ, stderr_data)

        result = self._collect_output(process, sel, stdout_data, stderr_data, timeout)
        sel.close()
        return result

    def _collect_output(
        self,
        process: subprocess.Popen[str],
        sel: selectors.DefaultSelector,
        stdout_data: list[str],
        stderr_data: list[str],
        timeout: int | None,
    ) -> ProcessResult:
        """Collect output from process pipes."""
        start_time = time.time()

        while sel.get_map():
            if timeout is not None and (time.time() - start_time) > timeout:
                return self._handle_timeout(process, stdout_data, stderr_data, timeout)

            raw_events = sel.select(timeout=SELECTOR_POLL_INTERVAL)
            events = [SelectorEvent(key, mask) for key, mask in raw_events]
            _process_pipe_events(sel, events)

            if not raw_events and process.poll() is not None:
                _drain_pipes(sel, stdout_data, stderr_data)

        process.wait()
        return _create_result(
            "".join(stdout_data).strip(),
            "".join(stderr_data).strip(),
            process.returncode or 0,
        )

    def _handle_timeout(
        self,
        process: subprocess.Popen[str],
        stdout_data: list[str],
        stderr_data: list[str],
        timeout: int,
    ) -> ProcessResult:
        """Handle process timeout."""
        process.kill()
        process.wait()
        stderr_msg = (
            f"Process timed out after {timeout} seconds.\n"
            + "".join(stderr_data).strip()
        )
        return _create_result(
            "".join(stdout_data).strip(), stderr_msg, TIMEOUT_RETURN_CODE
        )
