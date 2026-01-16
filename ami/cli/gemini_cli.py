"""Implementation of AgentCLI using Gemini CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from base.backend.utils.uuid_utils import uuid7
from agents.ami.cli.base_provider import CLIProvider as BaseProvider
from agents.ami.cli.config import AgentConfig
from agents.ami.core.config import get_config
from agents.ami.cli.interface import AgentCLI
from agents.ami.cli.provider_type import ProviderType
from agents.ami.cli.streaming_utils import load_instruction_with_replacements


class GeminiAgentCLI(BaseProvider, AgentCLI):
    """Implementation of AgentCLI using Gemini CLI."""

    # All Gemini tools (in snake_case format)
    ALL_TOOLS = {
        "read_file",
        "write_file",
        "edit",
        "run_shell_command",
        "search_file_content",
        "glob",
        "google_web_search",
        "web_fetch",
        "write_todos",
    }

    def __init__(self) -> None:
        """Initialize GeminiAgentCLI."""
        super().__init__()

    @staticmethod
    def compute_disallowed_tools(allowed_tools: list[str] | None) -> list[str]:
        """Compute disallowed tools."""
        if allowed_tools is None:
            return []
        allowed_set = set(allowed_tools)
        all_tools_set = GeminiAgentCLI.ALL_TOOLS
        disallowed = [tool for tool in all_tools_set if tool not in allowed_set]
        return sorted(disallowed)

    def _get_default_config(self) -> AgentConfig:
        """Get default agent configuration."""
        return AgentConfig(
            model="gemini-3-pro",
            session_id=uuid7(),
            provider=ProviderType.GEMINI,
            allowed_tools=None,
            enable_hooks=True,
            timeout=180,
        )

    def run_print(
        self,
        instruction: str | Path | None = None,
        cwd: Path | None = None,
        agent_config: AgentConfig | None = None,
        instruction_file: Path | None = None,
        stdin: str | None = None,
        audit_log_path: Path | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Run agent in print mode."""
        if instruction_file is not None:
            instruction_content = load_instruction_with_replacements(instruction_file)
        else:
            instruction_content = str(instruction)

        config = agent_config or self._get_default_config()
        return self._execute_with_timeout(instruction_content, cwd, config, stdin_data=stdin, audit_log_path=audit_log_path)

    def _build_command(
        self,
        instruction: str,
        cwd: Path | None,
        config: AgentConfig,
    ) -> list[str]:
        """Build Gemini CLI command."""
        cli_config = get_config()
        gemini_cmd = cli_config.get_provider_command(ProviderType.GEMINI)

        cmd = [gemini_cmd, "--prompt", instruction, "--model", config.model, "--output-format", "json"]
        
        # Add session ID / Resume logic
        if config.session_id:
            cmd.extend(["--resume", str(config.session_id)])
        
        # Note: --yolo is usually required for Gemini CLI to not prompt
        cmd.append("--yolo")
        
        return cmd

    def _parse_stream_message(self, line: str, _cmd, _line_count, _agent_config) -> tuple[str, dict[str, Any] | None]:
        """Parse streaming output (placeholder as Gemini CLI support is being added)."""
        return line, None
