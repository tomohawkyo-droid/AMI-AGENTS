"""Unified Streaming Pipeline for AMI Agent output.

Implements the Observer pattern to handle real-time output processing and rendering.
"""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from loguru import logger

from ami.cli.exceptions import AgentTimeoutError
from ami.cli.process_utils import read_streaming_line, start_streaming_process
from ami.cli.streaming_utils import calculate_timeout


@dataclass
class StreamEvent:
    """Represents a single event in the output stream."""
    type: str  # 'chunk', 'metadata', 'error', 'complete'
    data: Any
    timestamp: float = field(default_factory=time.time)


class StreamObserver(Protocol):
    """Interface for stream observers."""
    def on_event(self, event: StreamEvent) -> None:
        """Handle a stream event."""
        ...


class StreamProcessor:
    """Orchestrates the lifecycle of a streaming command execution."""

    def __init__(self, cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None, provider: Optional[Any] = None, agent_config: Optional[Any] = None):
        self.cmd = cmd
        self.cwd = cwd
        self.timeout = timeout
        self.provider = provider
        self.agent_config = agent_config
        self.observers: List[StreamObserver] = []
        self.full_output: List[str] = []
        self.metadata: Dict[str, Any] = {}

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

    def run(self, stdin_data: Optional[str] = None) -> Any:
        """Execute the command and process the stream, yielding events."""
        process = start_streaming_process(self.cmd, stdin_data, self.cwd)
        
        if stdin_data is not None and process.stdin:
            process.stdin.write(stdin_data)
            process.stdin.flush()
            process.stdin.close()
            process.stdin = None

        started_at = time.time()
        line_count = 0

        try:
            while True:
                timeout_val = calculate_timeout(self.timeout, line_count)
                line, is_timeout = read_streaming_line(process, timeout_val, self.cmd)

                if is_timeout:
                    if self.timeout and (time.time() - started_at) >= self.timeout:
                        raise AgentTimeoutError(self.timeout, self.cmd, time.time() - started_at)
                    continue

                if line is None:
                    if process.poll() is not None:
                        break
                    continue

                # Process the line through provider if available
                chunk_text = line
                if self.provider and hasattr(self.provider, "_parse_stream_message"):
                    parsed_text, parsed_metadata = self.provider._parse_stream_message(
                        line, self.cmd, line_count, self.agent_config
                    )
                    chunk_text = parsed_text
                    if parsed_metadata:
                        event = StreamEvent(type='metadata', data=parsed_metadata)
                        self._notify(event)
                        yield event

                # Notify observers of new chunk
                if chunk_text:
                    self.full_output.append(chunk_text if chunk_text.endswith("\n") else chunk_text + "\n")
                    event = StreamEvent(type='chunk', data=chunk_text)
                    self._notify(event)
                    yield event
                
                line_count += 1

            # Finalize
            exit_code = process.wait()
            self.metadata.update({
                "duration": time.time() - started_at,
                "exit_code": exit_code
            })
            
            final_text = "".join(self.full_output)
            comp_event = StreamEvent(type='complete', data={"output": final_text, "metadata": self.metadata})
            self._notify(comp_event)
            yield comp_event

        except Exception as e:
            err_event = StreamEvent(type='error', data=str(e))
            self._notify(err_event)
            yield err_event
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
