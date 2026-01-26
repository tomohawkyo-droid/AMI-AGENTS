"""Unified Streaming Pipeline implementation using StreamProcessor."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ami.cli.stream_processor import StreamObserver, StreamProcessor
from ami.cli_components.stream_renderer import StreamRenderer
from ami.types.api import ProviderMetadata, StreamEventData
from ami.types.events import StreamEvent, StreamEventType

if TYPE_CHECKING:
    from ami.cli.stream_processor import StreamParserProtocol
    from ami.types.config import AgentConfig


class RendererObserver(StreamObserver):
    """Observer that routes stream events to the StreamRenderer."""

    def __init__(self, renderer: StreamRenderer, processor: StreamProcessor) -> None:
        self.renderer = renderer
        self.processor = processor

    def on_event(self, event: StreamEvent) -> None:
        if event.type == StreamEventType.CHUNK and isinstance(event.data, str):
            self.renderer.process_chunk(event.data)
        elif (
            event.type == StreamEventType.METADATA
            and isinstance(event.data, StreamEventData)
            and event.data.metadata.session_id
        ):
            self.renderer.session_id = event.data.metadata.session_id


def execute_streaming(
    cmd: list[str],
    stdin_data: str | None = None,
    cwd: Path | None = None,
    agent_config: AgentConfig | None = None,
    provider: StreamParserProtocol | None = None,
) -> tuple[str, ProviderMetadata | None]:
    """Execute command using the unified StreamProcessor."""
    timeout = agent_config.timeout if agent_config else None
    processor = StreamProcessor(
        cmd, cwd=cwd, timeout=timeout, provider=provider, agent_config=agent_config
    )

    # If streaming is enabled in config, attach the renderer
    enable_streaming = agent_config.enable_streaming if agent_config else False
    if enable_streaming:
        session_id = (agent_config.session_id if agent_config else None) or "unknown"
        capture_content = agent_config.capture_content if agent_config else False

        renderer = StreamRenderer(session_id, capture_content)
        renderer.start()

        observer = RendererObserver(renderer, processor)
        processor.add_observer(observer)

        try:
            output = ""
            metadata: ProviderMetadata | None = None
            for event in processor.run(stdin_data=stdin_data):
                if event.type == StreamEventType.COMPLETE and isinstance(
                    event.data, StreamEventData
                ):
                    output = event.data.output
                    metadata = event.data.metadata
        except Exception:
            renderer.finish()
            raise
        else:
            # Finalize renderer and merge metadata
            renderer_meta = renderer.finish()
            if metadata is None:
                metadata = ProviderMetadata()
            # Merge renderer metadata into provider metadata
            if renderer_meta.get("session_id"):
                metadata = ProviderMetadata(
                    session_id=renderer_meta.get("session_id") or metadata.session_id,
                    duration=metadata.duration,
                    exit_code=metadata.exit_code,
                )
            return output, metadata

    # Standard non-display execution
    output = ""
    metadata = None
    for event in processor.run(stdin_data=stdin_data):
        if event.type == StreamEventType.COMPLETE and isinstance(
            event.data, StreamEventData
        ):
            output = event.data.output
            metadata = event.data.metadata
    return output, metadata
