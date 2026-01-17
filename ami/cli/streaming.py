"""Unified Streaming Pipeline implementation using StreamProcessor."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Tuple

from ami.cli.stream_processor import StreamProcessor, StreamEvent, StreamObserver
from ami.cli_components.stream_renderer import StreamRenderer
from ami.core.logic import parse_completion_marker

if TYPE_CHECKING:
    from ami.core.models import AgentConfig


class RendererObserver(StreamObserver):
    """Observer that routes stream events to the StreamRenderer."""
    
    def __init__(self, renderer: StreamRenderer, processor: StreamProcessor):
        self.renderer = renderer
        self.processor = processor

    def on_event(self, event: StreamEvent) -> None:
        if event.type == 'chunk':
            self.renderer.process_chunk(event.data + "\n")
        elif event.type == 'metadata':
            if isinstance(event.data, dict) and "session_id" in event.data:
                self.renderer.session_id = event.data["session_id"]


def execute_streaming(
    cmd: List[str],
    stdin_data: Optional[str] = None,
    cwd: Optional[Path] = None,
    agent_config: Any = None,
    config: Any = None,
    provider: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """Execute command using the unified StreamProcessor."""
    
    timeout = agent_config.timeout if agent_config else None
    processor = StreamProcessor(cmd, cwd=cwd, timeout=timeout, provider=provider, agent_config=agent_config)
    
    # If streaming is enabled in config, attach the renderer
    if agent_config and getattr(agent_config, "enable_streaming", False):
        session_id = getattr(agent_config, "session_id", "unknown") or "unknown"
        capture_content = getattr(agent_config, "capture_content", False)
        
        renderer = StreamRenderer(session_id, capture_content)
        renderer.start()
        
        observer = RendererObserver(renderer, processor)
        processor.add_observer(observer)
        
        try:
            output, metadata = processor.run(stdin_data=stdin_data)
            # Finalize renderer and merge metadata
            renderer_metadata = renderer.finish()
            metadata.update(renderer_metadata)
            return output, metadata
        except Exception:
            renderer.finish()
            raise
    
    # Standard non-display execution
    return processor.run(stdin_data=stdin_data)