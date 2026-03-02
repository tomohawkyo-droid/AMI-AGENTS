"""Base provider class for CLI agent implementations."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from ami.core.interfaces import RunInteractiveParams, RunPrintParams
from ami.types.config import AgentConfig
from ami.types.results import ParseResult, ProviderResult
from ami.utils.uuid_utils import uuid7

from .streaming import execute_streaming
from .streaming_utils import load_instruction_with_replacements


class CLIProvider(ABC):
    """Base class for CLI agent providers with common functionality."""

    def __init__(self) -> None:
        """Initialize CLIProvider."""
        self.current_process: subprocess.Popen[str] | None = None

    def kill_current_process(self) -> bool:
        """Kill the current running agent process if one exists.

        Returns:
            True if a process was killed, False if no process was running
        """
        if self.current_process is None:
            return False

        try:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
                self.current_process.wait()
        except ProcessLookupError:
            pass
        finally:
            self.current_process = None

        return True

    @abstractmethod
    def _build_command(
        self,
        instruction: str,
        cwd: Path | None,
        config: AgentConfig,
    ) -> list[str]:
        """Build the CLI command with proper flags and options.

        Args:
            instruction: Natural language instruction for the agent
            cwd: Working directory for agent execution
            config: Agent configuration

        Returns:
            List of command arguments
        """

    @abstractmethod
    def _parse_stream_message(
        self,
        line: str,
        cmd: list[str],
        line_count: int,
        agent_config: AgentConfig | None,
    ) -> ParseResult:
        """Parse a single line from CLI's streaming output.

        Args:
            line: Raw line from CLI output
            cmd: Original command for error reporting
            line_count: Current line number for error reporting
            agent_config: Agent configuration

        Returns:
            ParseResult with (text, metadata or None)
        """

    @abstractmethod
    def _get_default_config(self) -> AgentConfig:
        """Get default agent configuration.

        Returns:
            Default AgentConfig instance
        """

    def _execute_with_timeout(
        self,
        instruction: str,
        cwd: Path | None,
        agent_config: AgentConfig,
        stdin_data: str | None = None,
    ) -> ProviderResult:
        """Execute CLI command with timeout handling.

        Logging is handled by ConversationTranscript in the bootloader.
        This method is pure execution — no side effects.

        Args:
            instruction: Natural language instruction
            cwd: Working directory for execution
            agent_config: Agent configuration
            stdin_data: Data to provide to stdin

        Returns:
            ProviderResult with (output, metadata)

        Raises:
            AgentError: If execution fails or times out
        """
        cmd = self._build_command(instruction, cwd, agent_config)
        return execute_streaming(
            cmd=cmd,
            stdin_data=stdin_data,
            cwd=cwd,
            agent_config=agent_config,
            provider=self,
        )

    def run_interactive(
        self,
        params: RunInteractiveParams | None = None,
    ) -> ProviderResult:
        """Run agent interactively with CLI.

        Args:
            params: RunInteractiveParams with instruction, cwd, session_id

        Returns:
            ProviderResult with (output, metadata) where metadata includes session info

        Raises:
            AgentError: If agent execution fails
        """
        if params is None:
            params = RunInteractiveParams()

        config = AgentConfig(
            model="default-model",
            provider=self,
            session_id=params.session_id or uuid7(),
            allowed_tools=None,
            enable_hooks=True,
            timeout=None,
            mcp_servers=params.mcp_servers or None,
        )
        return self._execute_with_timeout(params.instruction, params.cwd, config)

    def run_print(
        self,
        params: RunPrintParams | None = None,
    ) -> ProviderResult:
        """Run agent in print mode with CLI.

        Args:
            params: Parameters for execution (instruction, cwd, config, etc.)

        Returns:
            ProviderResult with (output, metadata) where metadata includes session info

        Raises:
            AgentError: If agent execution fails
        """
        if params is None:
            params = RunPrintParams()
        instruction = params.instruction
        cwd = params.cwd
        agent_config = params.agent_config
        instruction_file = params.instruction_file
        stdin_data = params.stdin

        if instruction_file is not None:
            if instruction is not None:
                msg = "Cannot provide both instruction and instruction_file"
                raise ValueError(msg)
            instruction_content = load_instruction_with_replacements(instruction_file)
            if cwd is None:
                cwd = instruction_file.parent
        elif isinstance(instruction, Path):
            msg = "Use instruction_file parameter for Path instructions"
            raise ValueError(msg)
        else:
            if instruction is None:
                msg = "Either instruction or instruction_file is required"
                raise ValueError(msg)
            instruction_content = instruction

        config = agent_config or self._get_default_config()
        return self._execute_with_timeout(
            instruction_content,
            cwd,
            config,
            stdin_data=stdin_data,
        )
