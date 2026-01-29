"""API type definitions for AMI Agents.

Provides Pydantic models for API responses, stream messages, and configurations.
"""

from typing import cast

from pydantic import BaseModel, Field

from ami.types.common import ProcessEnvironment


def _empty_env() -> ProcessEnvironment:
    """Return empty ProcessEnvironment for default factory."""
    return cast(ProcessEnvironment, {})


class ProviderExtraMetadata(BaseModel):
    """Extra metadata from provider-specific fields."""

    tool_calls: int | None = None
    thinking_tokens: int | None = None
    cache_hits: int | None = None
    api_calls: int | None = None
    rate_limit_remaining: int | None = None


class StreamMetadata(BaseModel):
    """Metadata extracted from a stream message."""

    session_id: str | None = None
    model: str | None = None
    provider: str | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    extra: ProviderExtraMetadata = Field(default_factory=ProviderExtraMetadata)


class ProviderMetadata(BaseModel):
    """Metadata returned from provider execution."""

    session_id: str | None = None
    duration: float | None = None
    exit_code: int | None = None
    model: str | None = None
    tokens: int | None = None
    extra: ProviderExtraMetadata = Field(default_factory=ProviderExtraMetadata)


class ProviderResponse(BaseModel):
    """Response from a CLI provider execution."""

    content: str
    metadata: ProviderMetadata | None = None


class MCPServerConfig(BaseModel):
    """MCP (Model Context Protocol) server configuration."""

    name: str = ""
    command: str
    args: list[str] = Field(default_factory=list)
    env: ProcessEnvironment = Field(default_factory=_empty_env)


class StreamEventData(BaseModel):
    """Data payload for complete stream events."""

    output: str
    metadata: ProviderMetadata
