"""Core Agent implementation consolidating the ReAct loop."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import ClassVar

import yaml
from pydantic import BaseModel, ConfigDict

from ami.cli.provider_type import ProviderType
from ami.core.config import get_config
from ami.core.env import get_project_root, setup_agent_env
from ami.core.guards import check_command_safety
from ami.core.interfaces import AgentRuntimeProtocol, RunPrintParams
from ami.types.api import ProviderMetadata
from ami.types.config import AgentConfig
from ami.types.events import StreamEvent
from ami.utils.process import ProcessExecutor

# Type alias for stream callback
StreamCallbackType = Callable[[str | StreamEvent], None] | None


class RunContext(BaseModel):
    """Context for agent run execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    instruction: str
    session_id: str | None = None
    stream_callback: StreamCallbackType = None
    stop_event: Event | None = None
    input_func: Callable[[str], bool] | None = None
    allowed_tools: list[str] | None = None
    timeout: int = 300
    guard_rules_path: Path | None = None


class ExecutionResult(BaseModel):
    """Result from shell execution."""

    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class BootloaderAgent:
    """Core logic for the Agent with session support and ReAct loop."""

    DEFAULT_ALLOWED_TOOLS: ClassVar[list[str]] = ["save_memory"]
    MAX_LOOPS: ClassVar[int] = 10

    def __init__(self, runtime: AgentRuntimeProtocol | None = None) -> None:
        self.project_root = get_project_root()
        self.prompt_template = (
            self.project_root / "ami/config/prompts/bootloader_agent.txt"
        )
        self.extensions_config = (
            self.project_root / "ami/config/extensions.template.yaml"
        )
        self.runtime = runtime

        setup_agent_env()

    def _get_runtime(self, agent_config: AgentConfig) -> AgentRuntimeProtocol:
        """Get the runtime. Raises if not provided."""
        if self.runtime:
            return self.runtime
        raise RuntimeError("Agent runtime not provided to BootloaderAgent")

    def _get_banner(self) -> str:
        """Get environment context by sourcing .bashrc."""
        try:
            bashrc = Path("~/.bashrc").expanduser()
            if not bashrc.exists():
                return "System Context: .bashrc not found."

            result = subprocess.run(
                ["/bin/bash", "--rcfile", str(bashrc), "-i", "-c", "true"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            content = result.stdout + "\n" + result.stderr
            clean_content = content.replace(
                "bash: cannot set terminal process group (-1): Inappropriate ioctl for device",
                "",
            )
            clean_content = clean_content.replace(
                "bash: no job control in this shell", ""
            )

            return clean_content.replace("@", "(at)").strip()
        except Exception as e:
            return f"Error loading context: {e}"

    def _load_extensions(self) -> str:
        """Generate shell setup command from extensions registry."""
        if not self.extensions_config.exists():
            return ""

        try:
            with open(self.extensions_config) as f:
                data = yaml.safe_load(f)

            extensions = data.get("extensions", [])
            if not extensions:
                return ""

            cmds = [f'eval "$({ext})"' for ext in extensions]
            return " && ".join(cmds)
        except Exception as e:
            sys.stderr.write(f"Error loading extensions: {e}\n")
            return ""

    def _handle_user_confirmation(
        self,
        script: str,
        input_func: Callable[[str], bool],
        stream_callback: StreamCallbackType,
    ) -> str | None:
        """Handle user confirmation for script execution. Returns error message or None."""
        try:
            confirmed = input_func(script)
            if not confirmed:
                return "🛑 EXECUTION CANCELLED BY USER."

            success_msg = "\n✅ Confirmed. Executing...\n"
            if stream_callback:
                stream_callback(success_msg)
            else:
                print(success_msg)
        except Exception as e:
            return f"🛑 CONFIRMATION ERROR: {e}"
        return None

    def _format_shell_output(self, script: str, result: ExecutionResult) -> str:
        """Format shell execution output."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

        def strip_ansi(text: str) -> str:
            return ansi_escape.sub("", text)

        output = f"\n> {script}\n"
        stdout = result.stdout
        stderr = result.stderr

        if stdout.strip():
            clean_stdout = strip_ansi(stdout)
            clean_lines = [
                line
                for line in clean_stdout.splitlines()
                if "🚀 Setting up AMI Orchestrator shell environment..." not in line
            ]
            final_stdout = "\n".join(clean_lines).strip()
            if final_stdout:
                output += f"{final_stdout}\n"

        if stderr.strip():
            output += f"ERR: {strip_ansi(stderr).strip()}\n"

        if result.returncode != 0:
            output += f"(Exit Code: {result.returncode})\n"

        return output

    def execute_shell(
        self,
        script: str,
        input_func: Callable[[str], bool] | None = None,
        stream_callback: StreamCallbackType = None,
        guard_rules_path: Path | None = None,
    ) -> str:
        """Execute validated shell commands on the host."""
        is_safe, error = check_command_safety(script, guard_rules_path)
        if not is_safe:
            return f"🛑 BLOCKED: {error}"

        if input_func:
            confirm_error = self._handle_user_confirmation(
                script, input_func, stream_callback
            )
            if confirm_error:
                return confirm_error

        try:
            setup_cmd = self._load_extensions()
            full_command = f"{setup_cmd} && {script}" if setup_cmd else script

            executor = ProcessExecutor(work_dir=self.project_root)
            raw_result = executor.run(
                ["/bin/bash", "-c", full_command],
                timeout=300,
            )
            # Convert raw dict result to ExecutionResult
            result = ExecutionResult(
                stdout=raw_result.get("stdout", ""),
                stderr=raw_result.get("stderr", ""),
                returncode=raw_result.get("returncode", 0),
            )
        except Exception as e:
            return f"EXEC ERR: {e}"
        else:
            return self._format_shell_output(script, result)

    def _build_tools_message(self, allowed_tools: list[str]) -> str:
        """Build the tools availability message for the prompt."""
        if allowed_tools and allowed_tools != ["save_memory"]:
            return (
                "Use the explicitly allowed tools for non-shell operations:"
                + "\n".join([f"- {t}" for t in allowed_tools])
            )
        return "No internal tools are available by default. Rely on shell commands for all operations."

    def _build_initial_prompt(self, instruction: str, allowed_tools: list[str]) -> str:
        """Build the initial prompt with banner and tools message."""
        banner = self._get_banner()
        tools_msg = self._build_tools_message(allowed_tools)

        if not self.prompt_template.exists():
            raise FileNotFoundError(
                f"CRITICAL: Agent prompt template missing at {self.prompt_template}"
            )

        template = self.prompt_template.read_text()
        return template.format(
            tools_msg=tools_msg, banner=banner, instruction=instruction
        )

    def _build_agent_config(
        self, ctx: RunContext, session_id: str | None, allowed_tools: list[str]
    ) -> AgentConfig:
        """Build agent configuration from context."""
        global_config = get_config()
        provider_name = global_config.get_value("agent.provider", "claude")
        try:
            actual_provider = ProviderType(str(provider_name))
        except ValueError:
            actual_provider = ProviderType.CLAUDE

        default_model = global_config.get_provider_default_model(actual_provider)
        return AgentConfig(
            model=str(global_config.get_value("agent.worker.model") or default_model),
            session_id=session_id,
            provider=actual_provider,
            allowed_tools=allowed_tools,
            enable_hooks=True,
            enable_streaming=True,
            timeout=ctx.timeout,
            stream_callback=ctx.stream_callback,
            guard_rules_path=ctx.guard_rules_path,
        )

    def _handle_agent_error(
        self, e: Exception, ctx: RunContext, session_id: str | None
    ) -> tuple[str, str]:
        """Handle agent execution errors. Returns (error_msg, session_id) or raises."""
        if isinstance(e, KeyboardInterrupt | SystemExit):
            raise e

        error_msg = f"Agent Logic Error: {e}"
        if ctx.stream_callback:
            ctx.stream_callback(f"\n{error_msg}\n")
        else:
            sys.stderr.write(f"{error_msg}\n")

        if "isinstance() arg 2 must be a type" in str(e):
            raise e from None
        return error_msg, session_id or ""

    def _execute_shell_blocks(
        self,
        blocks: list[str],
        ctx: RunContext,
        response_parts: list[str],
    ) -> list[str]:
        """Execute shell blocks and return tool outputs."""
        tool_outputs = []
        for block in blocks:
            if ctx.stop_event and ctx.stop_event.is_set():
                break

            res = self.execute_shell(
                block, ctx.input_func, ctx.stream_callback, ctx.guard_rules_path
            )
            tool_outputs.append(res)

            formatted_res = f"\n\n{res}\n\n"
            if ctx.stream_callback:
                ctx.stream_callback(formatted_res)
            else:
                print(formatted_res)

            response_parts.append(res)
        return tool_outputs

    def _extract_session_id(
        self, metadata: ProviderMetadata | None, current: str | None
    ) -> str | None:
        """Extract session ID from metadata."""
        if metadata is None:
            return current
        return metadata.session_id or current

    def run(self, ctx: RunContext) -> tuple[str, str | None]:
        """Run the agent loop.

        Args:
            ctx: RunContext containing all execution parameters.

        Returns:
            Tuple of (response_text, actual_session_id)
        """
        session_id = ctx.session_id
        response_parts: list[str] = []
        allowed_tools = ctx.allowed_tools or self.DEFAULT_ALLOWED_TOOLS

        next_prompt = ctx.instruction
        if not session_id:
            next_prompt = self._build_initial_prompt(ctx.instruction, allowed_tools)

        for _iteration in range(self.MAX_LOOPS):
            if ctx.stop_event and ctx.stop_event.is_set():
                if ctx.stream_callback:
                    ctx.stream_callback("\n\n🛑 Agent execution stopped by user.\n")
                return "\n".join(
                    response_parts
                ) + "\n🛑 Agent stopped.", session_id or ""

            config = self._build_agent_config(ctx, session_id, allowed_tools)
            runtime = self._get_runtime(config)

            try:
                output, metadata = runtime.run_print(
                    params=RunPrintParams(
                        instruction=next_prompt,
                        agent_config=config,
                        cwd=self.project_root,
                    )
                )
                session_id = self._extract_session_id(metadata, session_id)
                session_id = session_id or ""
            except Exception as e:
                return self._handle_agent_error(e, ctx, session_id)

            response_parts.append(output)

            shell_blocks = re.findall(
                r"```(?:run|bash)\n?(.*?)\n?```", output, re.DOTALL
            )

            if not shell_blocks:
                has_tool_or_blocked = (
                    any(tool in output for tool in allowed_tools)
                    or "🛑 BLOCKED:" in output
                )
                if has_tool_or_blocked:
                    next_prompt = "Continue."
                    continue
                break

            tool_outputs = self._execute_shell_blocks(
                blocks=shell_blocks, ctx=ctx, response_parts=response_parts
            )
            next_prompt = "Tool Output:\n" + "\n".join(tool_outputs)

        return "\n".join(response_parts), session_id
