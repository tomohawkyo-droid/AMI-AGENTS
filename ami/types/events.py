"""Stream event types for AMI Agents.

Defines the event types used in the streaming pipeline.
"""

import time
from enum import Enum

from pydantic import BaseModel, Field

from ami.types.api import ProviderMetadata, StreamEventData, StreamMetadata


class StreamEventType(str, Enum):
    """Types of events in the output stream."""

    CHUNK = "chunk"
    METADATA = "metadata"
    ERROR = "error"
    COMPLETE = "complete"


# Type alias for stream event data based on event type
StreamEventPayload = str | StreamMetadata | StreamEventData


class StreamEvent(BaseModel):
    """Represents a single event in the output stream.

    Replaces the dataclass version with a Pydantic model.
    """

    type: StreamEventType
    data: StreamEventPayload
    timestamp: float = Field(default_factory=time.time)

    @classmethod
    def chunk(cls, content: str) -> "StreamEvent":
        """Create a chunk event."""
        return cls(type=StreamEventType.CHUNK, data=content)

    @classmethod
    def metadata(cls, meta: StreamMetadata) -> "StreamEvent":
        """Create a metadata event."""
        return cls(type=StreamEventType.METADATA, data=meta)

    @classmethod
    def error(cls, message: str) -> "StreamEvent":
        """Create an error event."""
        return cls(type=StreamEventType.ERROR, data=message)

    @classmethod
    def complete(cls, output: str, meta: ProviderMetadata) -> "StreamEvent":
        """Create a completion event."""
        return cls(
            type=StreamEventType.COMPLETE,
            data=StreamEventData(output=output, metadata=meta),
        )
