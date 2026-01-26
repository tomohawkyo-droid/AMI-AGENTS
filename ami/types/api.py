"""API type definitions for AMI Agents.

Provides Pydantic models for API responses, stream messages, and configurations.
"""

from pydantic import BaseModel, Field


class StreamMetadata(BaseModel):
    """Metadata extracted from a stream message."""

    session_id: str | None = None
    model: str | None = None
    provider: str | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    # Allow extra fields for provider-specific metadata
    extra: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ProviderMetadata(BaseModel):
    """Metadata returned from provider execution."""

    session_id: str | None = None
    duration: float | None = None
    exit_code: int | None = None
    model: str | None = None
    tokens: int | None = None
    # Allow provider-specific data
    extra: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    """Response from a CLI provider execution."""

    content: str
    metadata: ProviderMetadata | None = None


class MCPServerConfig(BaseModel):
    """MCP (Model Context Protocol) server configuration."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class StreamEventData(BaseModel):
    """Data payload for complete stream events."""

    output: str
    metadata: ProviderMetadata
