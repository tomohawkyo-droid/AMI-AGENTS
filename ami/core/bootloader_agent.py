"""Core Agent implementation consolidating the ReAct loop."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from threading import Event
from typing import ClassVar, NamedTuple

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ami.cli.provider_type import ProviderType
from ami.cli.transcript_store import TranscriptStore
from ami.core.config import get_config
from ami.core.conversation import ConversationTranscript, EntryMetadata
from ami.core.env import get_project_root, setup_agent_env
from ami.core.interfaces import AgentRuntimeProtocol, RunPrintParams
from ami.core.policies.tiers import get_tier_classifier
from ami.hooks.manager import HookManager
from ami.hooks.types import HookContext, HookEvent
from ami.types.common import ScopeOverride
from ami.types.config import AgentConfig
from ami.types.events import StreamEvent
from ami.utils.process import ProcessExecutor

# Compiled ANSI escape sequence pattern for stripping terminal codes
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Type alias for stream callback
StreamCallbackType = Callable[[str | StreamEvent], None] | None


class AgentRunResult(NamedTuple):
    """Result from agent run execution."""

    response_text: str
    session_id: str | None


class RunContext(BaseModel):
    """Context for agent run execution.

    Note on naming: ``transcript_id`` is the TranscriptStore session UUID
    (the directory name under ``logs/transcripts/``).  ``session_id`` is the
    provider's native session concept (e.g. Claude's ``--resume`` session).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    instruction: str
    session_id: str | None = None
    transcript_id: str | None = None
    stream_callback: StreamCallbackType = None
    stop_event: Event | None = None
    input_func: Callable[[str], bool] | None = None
    allowed_tools: list[str] | None = None
    timeout: int = 300
    scope_overrides: ScopeOverride = Field(default_factory=ScopeOverride)


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
        self._hook_manager: HookManager | None = None

        setup_agent_env()

    def _get_hook_manager(self, agent_config: AgentConfig) -> HookManager:
        """Get or create the hook manager based on agent config."""
        if self._hook_manager is None:
            self._hook_manager = HookManager.create(agent_config, self.project_root)
        return self._hook_manager

    def _get_runtime(self, agent_config: AgentConfig) -> AgentRuntimeProtocol:
        """Get the runtime. Raises if not provided."""
        if self.runtime:
            return self.runtime
        msg = "Agent runtime not provided to BootloaderAgent"
        raise RuntimeError(msg)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI escape sequences from text."""
        return _ANSI_ESCAPE.sub("", text)

    def _get_banner(self) -> str:
        """Get environment context by running the banner script directly."""
        banner_script = self.project_root / "ami/scripts/shell/ami-banner.sh"
        if not banner_script.exists():
            return "System Context: Banner script not found."
        try:
            result = subprocess.run(
                ["/bin/bash", str(banner_script), "--exclude-categories", "agents"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                env={**os.environ, "AMI_ROOT": str(self.project_root)},
            )
            content = result.stdout or result.stderr or "Banner generation failed."
            return self._strip_ansi(content).strip()
        except subprocess.TimeoutExpired:
            return "System Context: Banner generation timed out."
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

            cmds = [f'eval "$({ext})"' for ext in extensions if isinstance(ext, str)]
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
        """Handle user confirmation for script execution. Returns error or None."""
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
        output = f"\n> {script}\n"
        stdout = result.stdout
        stderr = result.stderr

        if stdout.strip():
            clean_stdout = self._strip_ansi(stdout)
            clean_lines = [
                line
                for line in clean_stdout.splitlines()
                if "🚀 Setting up AMI Orchestrator shell environment..." not in line
            ]
            final_stdout = "\n".join(clean_lines).strip()
            if final_stdout:
                output += f"{final_stdout}\n"

        if stderr.strip():
            output += f"ERR: {self._strip_ansi(stderr).strip()}\n"

        if result.returncode != 0:
            output += f"(Exit Code: {result.returncode})\n"

        return output

    def _validate_command(
        self,
        script: str,
        input_func: Callable[[str], bool] | None,
        stream_callback: StreamCallbackType,
        hook_manager: HookManager | None,
        scope_overrides: ScopeOverride | None,
    ) -> str | None:
        """Run pre-execution hooks and confirmation. Returns error or None."""
        if hook_manager is not None:
            return self._validate_with_hooks(
                script, input_func, stream_callback, hook_manager, scope_overrides
            )

        if input_func:
            return self._handle_user_confirmation(script, input_func, stream_callback)
        return None

    def _validate_with_hooks(
        self,
        script: str,
        input_func: Callable[[str], bool] | None,
        stream_callback: StreamCallbackType,
        hook_manager: HookManager,
        scope_overrides: ScopeOverride | None,
    ) -> str | None:
        """Run hook validation pipeline. Returns error message or None."""
        hook_result = hook_manager.run(
            HookEvent.PRE_BASH,
            HookContext(
                event=HookEvent.PRE_BASH,
                command=script,
                project_root=self.project_root,
                scope_overrides=(scope_overrides,) if scope_overrides else (),
            ),
        )
        if not hook_result.allowed:
            return f"🛑 BLOCKED: {hook_result.message}"

        # Handle needs_confirmation (tier-driven)
        if hook_result.needs_confirmation:
            if input_func:
                confirm_error = self._handle_user_confirmation(
                    script, input_func, stream_callback
                )
                if confirm_error:
                    return confirm_error
            else:
                return (
                    "🛑 BLOCKED: Command requires user confirmation"
                    " but no confirmation handler."
                )

        # Tier-based PRE_EDIT dispatch (replaces is_risky_edit_command)
        classifier = get_tier_classifier()
        tier = classifier.classify(script)
        tier_config = classifier.get_tier_config(tier)
        if tier_config.triggers_edit_hooks:
            edit_result = hook_manager.run(
                HookEvent.PRE_EDIT,
                HookContext(
                    event=HookEvent.PRE_EDIT,
                    command=script,
                    project_root=self.project_root,
                ),
            )
            if not edit_result.allowed:
                return f"🛑 BLOCKED: {edit_result.message}"

        return None

    def execute_shell(
        self,
        script: str,
        input_func: Callable[[str], bool] | None = None,
        stream_callback: StreamCallbackType = None,
        hook_manager: HookManager | None = None,
        scope_overrides: ScopeOverride | None = None,
    ) -> str:
        """Execute validated shell commands on the host."""
        validation_error = self._validate_command(
            script, input_func, stream_callback, hook_manager, scope_overrides
        )
        if validation_error:
            return validation_error

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
        return (
            "No internal tools are available by default. "
            "Rely on shell commands for all operations."
        )

    def _build_initial_prompt(self, instruction: str, allowed_tools: list[str]) -> str:
        """Build the initial prompt with banner and tools message."""
        banner = self._get_banner()
        tools_msg = self._build_tools_message(allowed_tools)

        if not self.prompt_template.exists():
            msg = f"Agent prompt template missing at {self.prompt_template}"
            raise FileNotFoundError(msg)

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
        )

    def _handle_agent_error(self, e: Exception, ctx: RunContext) -> AgentRunResult:
        """Handle agent execution errors. Returns AgentRunResult or raises."""
        if isinstance(e, KeyboardInterrupt | SystemExit):
            raise e

        error_msg = f"Agent Logic Error: {e}"
        if ctx.stream_callback:
            ctx.stream_callback(f"\n{error_msg}\n")
        else:
            sys.stderr.write(f"{error_msg}\n")

        if "isinstance() arg 2 must be a type" in str(e):
            raise e from None
        return AgentRunResult(response_text=error_msg, session_id=None)

    def _execute_shell_blocks(
        self,
        blocks: list[str],
        ctx: RunContext,
        response_parts: list[str],
        hook_manager: HookManager,
        transcript: ConversationTranscript,
    ) -> None:
        """Execute shell blocks, stream output, and record in transcript."""
        parent_id = transcript.last_entry_id
        for block in blocks:
            if ctx.stop_event and ctx.stop_event.is_set():
                break

            call_entry = transcript.add_tool_call(block, parent_id=parent_id)

            res = self.execute_shell(
                block,
                ctx.input_func,
                ctx.stream_callback,
                hook_manager,
                ctx.scope_overrides or None,
            )

            transcript.add_tool_result(res, parent_id=call_entry.entry_id)

            formatted_res = f"\n\n{res}\n\n"
            if ctx.stream_callback:
                ctx.stream_callback(formatted_res)
            else:
                print(formatted_res)

            response_parts.append(res)

    @staticmethod
    def _build_entry_metadata(provider_meta: object) -> EntryMetadata:
        """Convert provider metadata to EntryMetadata."""
        if not provider_meta:
            return EntryMetadata()
        return EntryMetadata(
            model=getattr(provider_meta, "model", None),
            tokens=getattr(provider_meta, "tokens", None),
            duration=getattr(provider_meta, "duration", None),
            exit_code=getattr(provider_meta, "exit_code", None),
        )

    def _is_stopped(self, ctx: RunContext, response_parts: list[str]) -> bool:
        """Check if stop event is set. Notifies callback if so."""
        if not (ctx.stop_event and ctx.stop_event.is_set()):
            return False
        if ctx.stream_callback:
            ctx.stream_callback("\n\n🛑 Agent execution stopped by user.\n")
        response_parts.append("🛑 Agent stopped.")
        return True

    def run(self, ctx: RunContext) -> AgentRunResult:
        """Run the agent loop."""
        transcript_id = ctx.transcript_id
        response_parts: list[str] = []
        allowed_tools = ctx.allowed_tools or self.DEFAULT_ALLOWED_TOOLS

        store = TranscriptStore()
        transcript = ConversationTranscript(store, transcript_id or "")
        if transcript_id:
            transcript.load_from_store()

        system_prompt = self._build_initial_prompt(ctx.instruction, allowed_tools)
        transcript.add_system(system_prompt)
        transcript.add_user(ctx.instruction)

        if transcript.has_history():
            next_prompt = f"{transcript.build_context_summary()}\n\n{system_prompt}"
        else:
            next_prompt = system_prompt

        initial_config = self._build_agent_config(ctx, None, allowed_tools)
        hook_manager = self._get_hook_manager(initial_config)

        for _iteration in range(self.MAX_LOOPS):
            if self._is_stopped(ctx, response_parts):
                break

            config = self._build_agent_config(ctx, None, allowed_tools)
            try:
                output, _metadata = self._get_runtime(config).run_print(
                    params=RunPrintParams(
                        instruction=next_prompt,
                        agent_config=config,
                        cwd=self.project_root,
                    )
                )
            except Exception as e:
                transcript.add_error(str(e))
                return self._handle_agent_error(e, ctx)

            post_result = hook_manager.run(
                HookEvent.POST_OUTPUT,
                HookContext(event=HookEvent.POST_OUTPUT, content=output),
            )
            if not post_result.allowed:
                violation_msg = f"🛑 OUTPUT VIOLATION: {post_result.message}"
                if ctx.stream_callback:
                    ctx.stream_callback(f"\n{violation_msg}\n")
                response_parts.append(violation_msg)
                break

            transcript.add_assistant(
                output, metadata=self._build_entry_metadata(_metadata)
            )
            response_parts.append(output)

            shell_blocks = re.findall(
                r"```\s*(?:run|bash)\b\s*(.*?)\s*```", output, re.DOTALL
            )
            if not shell_blocks:
                has_tool_or_blocked = (
                    any(tool in output for tool in allowed_tools)
                    or "🛑 BLOCKED:" in output
                )
                if has_tool_or_blocked:
                    transcript.add_internal("Continue.")
                    next_prompt = transcript.build_prompt()
                    continue
                break

            self._execute_shell_blocks(
                shell_blocks,
                ctx,
                response_parts,
                hook_manager,
                transcript,
            )
            next_prompt = transcript.build_prompt()

        return AgentRunResult(response_text="\n".join(response_parts), session_id=None)
