"""Implementation of AgentCLI using Qwen Code CLI.

QwenAgentCLI implements the AgentCLI interface and provides concrete
functionality for running Qwen Code agents with proper error handling,
timeout management, and streaming support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ami.utils.uuid_utils import uuid7
from ami.cli.base_provider import CLIProvider as BaseProvider
from ami.cli.config import AgentConfig
from ami.core.config import get_config
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.cli.streaming_utils import load_instruction_with_replacements


class QwenAgentCLI(BaseProvider, AgentCLI):
    """Implementation of AgentCLI using Qwen Code CLI."""

    # All Qwen Code tools (in snake_case format as found in source)
    ALL_TOOLS = {
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
        # Legacy/Compatibility mappings if needed (removed for strictness)
    }

    def __init__(self) -> None:
        """Initialize QwenAgentCLI."""
        super().__init__()  # Initialize parent class

    def _get_default_config(self) -> AgentConfig:
        """Get default agent configuration.

        Returns:
            Default AgentConfig instance
        """
        return AgentConfig(
            model="qwen-coder",  # Default Qwen model
            session_id=None,
            provider=ProviderType.QWEN,
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
        """Run agent in print mode with Qwen-specific settings."""
        # Handle instruction vs instruction_file
        if instruction_file is not None:
            if instruction is not None:
                raise ValueError("Cannot specify both instruction and instruction_file")
            instruction_content = load_instruction_with_replacements(instruction_file)
            if cwd is None:
                cwd = instruction_file.parent
        elif isinstance(instruction, Path):
            raise ValueError("Path objects should be passed as instruction_file parameter")
        else:
            instruction_content = instruction if instruction is not None else ""

        config = agent_config or self._get_default_config()
        
        # Qwen Optimization: Pass large instructions via stdin to avoid argv limits/parsing issues
        # We combine instruction and existing stdin
        combined_stdin = ""
        if instruction_content:
            combined_stdin += instruction_content
        if stdin:
            if combined_stdin:
                combined_stdin += "\n"
            combined_stdin += stdin
            
        # Pass empty instruction to _execute_with_timeout so _build_command sees empty string
        # and doesn't add it to args. We pass the real content via stdin_data.
        return self._execute_with_timeout(
            "", 
            cwd, 
            config, 
            stdin_data=combined_stdin if combined_stdin else None, 
            audit_log_path=audit_log_path
        )

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

        # Add model flag
        cmd.extend(["--model", config.model])

        # Add session ID / Resume logic
        if config.session_id and str(config.session_id).strip():
            cmd.extend(["--resume", str(config.session_id)])

        # Use allowlist approach for security (Fail Closed)
        if config.allowed_tools is not None:
            cmd.extend(["--allowed-tools"] + config.allowed_tools)

        # Add streaming flag if enabled
        if config.enable_streaming:
            cmd.extend(["--output-format", "stream-json", "--include-partial-messages"])

        # Add print mode settings
        # Qwen uses -y/--yolo for non-interactive tools
        cmd.append("--yolo")
        
        # Positional prompt is the default and preferred way, BUT if we passed it via stdin
        # (indicated by empty instruction here due to run_print override), skip it.
        if instruction:
            cmd.append(instruction)

        return cmd

    def _parse_stream_message(
        self,
        line: str,
        _cmd: list[str],
        _line_count: int,
        _agent_config: AgentConfig,
    ) -> tuple[str, dict[str, Any] | None]:
        """Parse a single line from Qwen CLI's streaming output.

        Args:
            line: Raw line from Qwen CLI output
            _cmd: Original command for error reporting (unused in Qwen implementation)
            _line_count: Current line number for error reporting (unused in Qwen implementation)
            _agent_config: Agent configuration (unused in Qwen implementation)

        Returns:
            Tuple of (output text, metadata dict or None)
        """
        output_text = ""
        metadata = None

        if not line.strip():
            return output_text, metadata

        # Qwen CLI can output JSON lines mixed with regular output
        try:
            # Try to parse as JSON first
            data = json.loads(line)
            if isinstance(data, dict):
                # This is a structured response
                msg_type = data.get("type")

                # Handle stream_event wrapper (Qwen wraps events)
                if msg_type == "stream_event":
                    # Unwrap the inner event
                    inner_event = data.get("event", {})
                    inner_type = inner_event.get("type")
                    
                    if inner_type == "content_block_delta":
                        output_text = inner_event.get("delta", {}).get("text", "")
                    elif inner_type == "message_start":
                        # Capture message ID or other metadata if needed
                        metadata = data
                    
                    # Capture session_id from stream event if present
                    if "session_id" in data:
                        if metadata is None:
                            metadata = {}
                        metadata["session_id"] = data["session_id"]

                # Handle direct messages (legacy or system messages)
                elif msg_type == "content_block_delta":
                    output_text = data.get("delta", {}).get("text", "")
                
                elif msg_type == "assistant":
                    # Full message at end (sometimes sent as type=assistant)
                    # Extract text from content list
                    pass
                
                elif msg_type == "system" and data.get("subtype") == "init":
                    metadata = data
                    # Capture session_id from init event
                    if "session_id" in data:
                        metadata["session_id"] = data["session_id"]
                
                elif msg_type == "result":
                    # Final result block
                    metadata = data

                else:
                    # Not a recognized message type, return as text if strictly needed,
                    # but usually better to ignore unknown JSON to avoid clutter
                    # output_text = json.dumps(data)
                    metadata = None
            else:
                # Not a dict, return as string
                output_text = str(data)
                metadata = None
        except json.JSONDecodeError:
            # Not JSON, return as regular text
            output_text = line
            metadata = None

        return output_text, metadata
