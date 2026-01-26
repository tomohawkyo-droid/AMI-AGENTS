"""Implementation of AgentCLI using Qwen Code CLI.

QwenAgentCLI implements the AgentCLI interface and provides concrete
functionality for running Qwen Code agents with proper error handling,
timeout management, and streaming support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from ami.cli.base_provider import CLIProvider as BaseProvider
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.core.config import get_config
from ami.core.interfaces import RunPrintParams
from ami.types.api import ProviderMetadata, StreamMetadata
from ami.types.config import AgentConfig


class QwenAgentCLI(BaseProvider, AgentCLI):
    """Implementation of AgentCLI using Qwen Code CLI."""

    ALL_TOOLS: ClassVar[set[str]] = {
        "run_shell_command",
        "read_file",
        "read_many_files",
        "write_file",
        "edit",
        "grep_search",
        "glob",
        "list_directory",
        "todo_write",
        "save_memory",
        "task",
        "skill",
        "exit_plan_mode",
        "web_fetch",
        "web_search",
    }

    def __init__(self) -> None:
        """Initialize QwenAgentCLI."""
        super().__init__()

    def _get_default_config(self) -> AgentConfig:
        """Get default agent configuration."""
        return AgentConfig(
            model="qwen-coder",
            session_id=None,
            provider=ProviderType.QWEN,
            allowed_tools=None,
            enable_hooks=True,
            timeout=180,
        )

    def run_print(
        self,
        params: RunPrintParams | None = None,
    ) -> tuple[str, ProviderMetadata | None]:
        """Run agent in print mode with Qwen-specific settings."""
        return super().run_print(params=params)

    def _build_command(
        self,
        instruction: str,
        cwd: Path | None,
        config: AgentConfig,
    ) -> list[str]:
        """Build Qwen Code CLI command with proper flags and options."""
        config_service = get_config()
        qwen_cmd = config_service.get_provider_command(ProviderType.QWEN)

        cmd = [qwen_cmd]
        cmd.extend(["--model", config.model])

        if config.session_id and str(config.session_id).strip():
            cmd.extend(["--resume", str(config.session_id)])

        if config.allowed_tools is not None:
            cmd.extend(["--allowed-tools", *config.allowed_tools])

        if config.enable_streaming:
            cmd.extend(["--output-format", "stream-json", "--include-partial-messages"])

        cmd.append("--yolo")

        if instruction:
            cmd.append(instruction)

        return cmd

    def _handle_stream_event(
        self,
        data: dict[str, str | int | float | bool | list[object] | dict[str, object]],
    ) -> tuple[str, StreamMetadata | None]:
        """Handle stream_event message type."""
        output_text = ""
        metadata: StreamMetadata | None = None
        inner_event = data.get("event", {})

        if isinstance(inner_event, dict):
            inner_type = inner_event.get("type")
            if inner_type == "content_block_delta":
                delta = inner_event.get("delta", {})
                if isinstance(delta, dict):
                    text = delta.get("text", "")
                    output_text = str(text) if text else ""
            elif inner_type == "message_start":
                session_id = data.get("session_id")
                metadata = StreamMetadata(
                    session_id=str(session_id) if session_id else None,
                    provider="qwen",
                )

        if "session_id" in data and metadata is None:
            session_id = data.get("session_id")
            metadata = StreamMetadata(
                session_id=str(session_id) if session_id else None,
                provider="qwen",
            )

        return output_text, metadata

    def _handle_system_init(
        self,
        data: dict[str, str | int | float | bool | list[object] | dict[str, object]],
    ) -> tuple[str, StreamMetadata | None]:
        """Handle system init message type."""
        session_id = data.get("session_id")
        metadata = StreamMetadata(
            session_id=str(session_id) if session_id else None,
            provider="qwen",
        )
        return "", metadata

    def _parse_json_message(
        self,
        data: dict[str, str | int | float | bool | list[object] | dict[str, object]],
    ) -> tuple[str, StreamMetadata | None]:
        """Parse a JSON message dict and extract output/metadata."""
        msg_type = data.get("type")

        if msg_type == "stream_event":
            return self._handle_stream_event(data)
        if msg_type == "content_block_delta":
            delta = data.get("delta", {})
            if isinstance(delta, dict):
                text = delta.get("text", "")
                return str(text) if text else "", None
            return "", None
        if msg_type == "system" and data.get("subtype") == "init":
            return self._handle_system_init(data)
        if msg_type == "result":
            session_id = data.get("session_id")
            return "", StreamMetadata(
                session_id=str(session_id) if session_id else None,
                provider="qwen",
            )
        return "", None

    def _parse_stream_message(
        self,
        line: str,
        _cmd: list[str],
        _line_count: int,
        _agent_config: AgentConfig | None,
    ) -> tuple[str, StreamMetadata | None]:
        """Parse a single line from Qwen CLI's streaming output."""
        if not line.strip():
            return "", None

        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return self._parse_json_message(data)
            return str(data), None
        except json.JSONDecodeError:
            return line, None
