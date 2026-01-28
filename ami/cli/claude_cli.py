"""Implementation of AgentCLI using Claude Code CLI.

ClaudeAgentCLI implements the AgentCLI interface and provides concrete
functionality for running Claude Code agents with proper error handling,
timeout management, and streaming support.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from ami.cli.base_provider import CLIProvider as BaseProvider
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.core.config import get_config
from ami.types.api import StreamMetadata
from ami.types.config import AgentConfig
from ami.utils.uuid_utils import uuid7


class ClaudeAgentCLI(BaseProvider, AgentCLI):
    """Implementation of AgentCLI using Claude Code CLI."""

    ALL_TOOLS: ClassVar[set[str]] = {
        "Bash",
        "Edit",
        "Read",
        "Write",
        "Ask",
        "WebSearch",
        "WebFetch",
        "TermTool",
        "VSCodeEditor",
        "CodeSearch",
        "GitClient",
        "FileSys",
        "DatabaseClient",
        "APIExplorer",
        "DebuggingTool",
    }

    def __init__(self) -> None:
        """Initialize ClaudeAgentCLI."""
        self.current_process: subprocess.Popen[str] | None = None

    def _get_default_config(self) -> AgentConfig:
        """Get default agent configuration."""
        return AgentConfig(
            model="claude-sonnet-4-5",
            session_id=uuid7(),
            provider=ProviderType.CLAUDE,
            allowed_tools=None,
            enable_hooks=True,
            timeout=180,
        )

    def _build_command(
        self,
        instruction: str,
        cwd: Path | None,
        config: AgentConfig,
    ) -> list[str]:
        """Build Claude Code CLI command with proper flags and options."""
        app_config = get_config()
        claude_cmd = app_config.get_provider_command(ProviderType.CLAUDE)

        cmd = [claude_cmd]
        cmd.extend(["--model", config.model])

        if config.session_id and str(config.session_id).strip():
            session_id_str: str = str(config.session_id)
            try:
                UUID(session_id_str)
            except ValueError:
                msg = f"WARNING: Invalid session_id '{session_id_str}'"
                sys.stderr.write(f"{msg}, starting fresh session\n")
            else:
                cmd.extend(["--session-id", session_id_str])

        if config.allowed_tools is not None:
            cmd.extend(["--allowed-tools", *config.allowed_tools])

        if config.enable_streaming:
            cmd.extend(["--verbose", "--output-format", "stream-json"])

        cmd.append("--print")
        cmd.append(instruction)

        if cwd:
            cmd.extend(["--add-dir", str(cwd)])

        return cmd

    def _parse_stream_message(
        self,
        line: str,
        _cmd: list[str],
        _line_count: int,
        _agent_config: AgentConfig | None,
    ) -> tuple[str, StreamMetadata | None]:
        """Parse a single line from Claude CLI's streaming output."""
        if not line.strip():
            return "", None

        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return self._handle_json_dict(data)
            return str(data), None
        except json.JSONDecodeError:
            return line, None

    def _handle_json_dict(
        self,
        data: dict[str, str | int | float | bool | list[object] | dict[str, object]],
    ) -> tuple[str, StreamMetadata | None]:
        """Handle parsing of JSON dictionary from Claude CLI output."""
        msg_type = data.get("type")
        if msg_type is None:
            return json.dumps(data), None

        metadata = StreamMetadata(
            session_id=str(data.get("session_id")) if data.get("session_id") else None,
            model=str(data.get("model")) if data.get("model") else None,
            provider="claude",
        )

        output_text: str
        if msg_type == "content_block_delta":
            delta = data.get("delta", {})
            if isinstance(delta, dict):
                text_val = delta.get("text", "")
                output_text = str(text_val) if text_val else ""
            else:
                output_text = ""
        elif msg_type == "assistant" and "message" in data:
            msg = data.get("message")
            output_text = (
                self._extract_assistant_message(msg) if isinstance(msg, dict) else ""
            )
        elif msg_type in {"system", "result"}:
            output_text = ""
        else:
            output_text = json.dumps(data)

        return output_text, metadata

    def _extract_assistant_message(self, message_data: object) -> str:
        """Extract text content from assistant message."""
        if not isinstance(message_data, dict):
            return ""
        content = message_data.get("content")
        if not isinstance(content, list):
            return ""
        text_parts: list[str] = []
        for content_item in content:
            if (
                isinstance(content_item, dict)
                and content_item.get("type") == "text"
                and "text" in content_item
            ):
                text = content_item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "".join(text_parts)
