"""Implementation of AgentCLI using Gemini CLI."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from ami.cli.base_provider import CLIProvider as BaseProvider
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.core.config import get_config
from ami.core.interfaces import RunPrintParams
from ami.types.api import ProviderMetadata, StreamMetadata
from ami.types.config import AgentConfig
from ami.utils.uuid_utils import uuid7


class GeminiAgentCLI(BaseProvider, AgentCLI):
    """Implementation of AgentCLI using Gemini CLI."""

    ALL_TOOLS: ClassVar[set[str]] = {
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
        params: RunPrintParams | None = None,
    ) -> tuple[str, ProviderMetadata | None]:
        """Run agent in print mode."""
        return super().run_print(params=params)

    def _build_command(
        self,
        instruction: str,
        cwd: Path | None,
        config: AgentConfig,
    ) -> list[str]:
        """Build Gemini CLI command."""
        cli_config = get_config()
        gemini_cmd = cli_config.get_provider_command(ProviderType.GEMINI)

        cmd = [
            gemini_cmd,
            "--prompt",
            instruction,
            "--model",
            config.model,
            "--output-format",
            "json",
        ]

        if config.session_id:
            cmd.extend(["--resume", str(config.session_id)])

        cmd.append("--yolo")

        return cmd

    def _parse_stream_message(
        self,
        line: str,
        _cmd: list[str],
        _line_count: int,
        _agent_config: AgentConfig | None,
    ) -> tuple[str, StreamMetadata | None]:
        """Parse streaming output from Gemini CLI."""
        return line, None
