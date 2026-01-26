"""Unified Streaming Pipeline for AMI Agent output.

Implements the Observer pattern to handle real-time output processing and rendering.
"""

import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from ami.cli.exceptions import AgentTimeoutError
from ami.cli.process_utils import read_streaming_line, start_streaming_process
from ami.cli.streaming_utils import calculate_timeout
from ami.types.api import ProviderMetadata, StreamMetadata
from ami.types.events import StreamEvent

if TYPE_CHECKING:
    from ami.types.config import AgentConfig


def _raise_timeout_error(timeout: int, cmd: list[str], elapsed: float) -> None:
    """Raise a timeout error with the given parameters."""
    raise AgentTimeoutError(timeout, cmd, elapsed)


class StreamObserver(Protocol):
    """Interface for stream observers."""

    def on_event(self, event: StreamEvent) -> None:
        """Handle a stream event."""
        ...


class StreamParserProtocol(Protocol):
    """Protocol for providers that can parse stream messages."""

    def _parse_stream_message(
        self,
        line: str,
        cmd: list[str],
        line_count: int,
        agent_config: "AgentConfig | None",
    ) -> tuple[str, StreamMetadata | None]:
        """Parse a single line from CLI's streaming output."""
        ...


class StreamProcessor:
    """Orchestrates the lifecycle of a streaming command execution."""

    def __init__(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        timeout: int | None = None,
        provider: StreamParserProtocol | None = None,
        agent_config: "AgentConfig | None" = None,
    ) -> None:
        self.cmd = cmd
        self.cwd = cwd
        self.timeout = timeout
        self.provider = provider
        self.agent_config = agent_config
        self.observers: list[StreamObserver] = []
        self.full_output: list[str] = []
        self._duration: float = 0.0
        self._exit_code: int = 0

    def add_observer(self, observer: StreamObserver) -> None:
        """Register an observer for stream events."""
        self.observers.append(observer)

    def _notify(self, event: StreamEvent) -> None:
        """Notify all observers of an event."""
        for observer in self.observers:
            try:
                observer.on_event(event)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def _write_stdin(self, process: subprocess.Popen[str], stdin_data: str) -> None:
        """Write stdin data to process and close stdin."""
        if process.stdin:
            process.stdin.write(stdin_data)
            process.stdin.flush()
            process.stdin.close()
            process.stdin = None

    def _process_line(
        self, line: str, line_count: int
    ) -> tuple[str, StreamMetadata | None]:
        """Process a line through provider if available."""
        if self.provider is not None:
            return self.provider._parse_stream_message(
                line, self.cmd, line_count, self.agent_config
            )
        return line, None

    def _check_timeout(self, is_timeout: bool, started_at: float) -> bool:
        """Check if timeout occurred. Returns True if loop should continue."""
        if not is_timeout:
            return False
        if self.timeout and (time.time() - started_at) >= self.timeout:
            _raise_timeout_error(self.timeout, self.cmd, time.time() - started_at)
        return True

    def run(self, stdin_data: str | None = None) -> Generator[StreamEvent, None, None]:
        """Execute the command and process the stream, yielding events."""
        process = start_streaming_process(self.cmd, stdin_data, self.cwd)
        if stdin_data is not None:
            self._write_stdin(process, stdin_data)

        started_at = time.time()
        line_count = 0

        try:
            while True:
                timeout_val = calculate_timeout(self.timeout, line_count)
                line, is_timeout = read_streaming_line(process, timeout_val, self.cmd)

                if self._check_timeout(is_timeout, started_at):
                    continue

                if line is None:
                    if process.poll() is not None:
                        break
                    continue

                chunk_text, parsed_metadata = self._process_line(line, line_count)
                if parsed_metadata:
                    event = StreamEvent.metadata(parsed_metadata)
                    self._notify(event)
                    yield event

                if chunk_text:
                    chunk_with_nl = (
                        chunk_text if chunk_text.endswith("\n") else chunk_text + "\n"
                    )
                    self.full_output.append(chunk_with_nl)
                    event = StreamEvent.chunk(chunk_text)
                    self._notify(event)
                    yield event

                line_count += 1

            self._exit_code = process.wait()
            self._duration = time.time() - started_at

            metadata = ProviderMetadata(
                duration=self._duration,
                exit_code=self._exit_code,
            )
            comp_event = StreamEvent.complete("".join(self.full_output), metadata)
            self._notify(comp_event)
            yield comp_event

        except Exception as e:
            err_event = StreamEvent.error(str(e))
            self._notify(err_event)
            yield err_event
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
