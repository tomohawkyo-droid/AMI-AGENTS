"Core Agent implementation consolidating the ReAct loop."

import re
import json
import time
import sys
import subprocess
import os
from pathlib import Path
from typing import List, Optional, Tuple, Any, Callable
import yaml

from ami.utils.process import ProcessExecutor
from ami.utils.uuid_utils import uuid7
from ami.core.models import AgentConfig
from ami.core.interfaces import AgentRuntimeProtocol
from ami.core.config import get_config
from ami.cli.provider_type import ProviderType
from ami.core.guards import check_command_safety
from ami.core.env import setup_agent_env

# Setup import path for project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

class BootloaderAgent:
    """Core logic for the Agent with session support and ReAct loop."""

    # Default to NO tools allowed for security (rely on run blocks)
    # BUT we must allow at least one tool to satisfy Qwen API requirements
    DEFAULT_ALLOWED_TOOLS = ["save_memory"]
    
    MAX_LOOPS = 10
    
    def __init__(self, runtime: Optional[AgentRuntimeProtocol] = None):
        self.project_root = PROJECT_ROOT
        self.prompt_template = self.project_root / "ami/config/prompts/bootloader_agent.txt"
        self.extensions_config = self.project_root / "ami/config/extensions.template.yaml"
        self.runtime = runtime
        
        # Consolidated environment setup
        setup_agent_env()
    
    def _get_runtime(self, agent_config: Any) -> AgentRuntimeProtocol:
        """Get the runtime, either injected or via factory if absolutely necessary.
        
        NOTE: Relying on factory here is a fallback to maintain backward compatibility
        during refactoring. Injected runtime is preferred.
        """
        if self.runtime:
            return self.runtime
            
        # Fallback to factory (this still causes circularity if we import it here)
        # So we should ideally NOT have a fallback that imports factory.
        # For now, we will raise an error if no runtime is provided.
        raise RuntimeError("Agent runtime not provided to BootloaderAgent")
    
    def _get_banner(self) -> str:
        """Get environment context by sourcing .bashrc."""
        try:
            bashrc = Path("~/.bashrc").expanduser()
            if not bashrc.exists():
                return "System Context: .bashrc not found."

            # Run bash interactively to capture welcome messages/context
            # We use --rcfile to force sourcing .bashrc even if not login
            result = subprocess.run(
                ["/bin/bash", "--rcfile", str(bashrc), "-i", "-c", "true"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            content = result.stdout + "\n" + result.stderr
            
            # Clean up noise and sanitize
            clean_content = content.replace("bash: cannot set terminal process group (-1): Inappropriate ioctl for device", "")
            clean_content = clean_content.replace("bash: no job control in this shell", "")
            
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
                
            # Build eval chain: eval "$(<cmd1>)" && eval "$(<cmd2>)"
            # We run this from project root
            cmds = [f'eval "$({ext})"' for ext in extensions]
            return " && ".join(cmds)
        except Exception as e:
            # Fallback safe: log error to stderr but don't crash
            sys.stderr.write(f"Error loading extensions: {e}\n")
            return ""

    def execute_shell(self, script: str, input_func: Optional[Callable[[str], bool]] = None, stream_callback: Optional[Any] = None, guard_rules_path: Optional[Path] = None) -> str:
        """Execute validated shell commands on the host."""
        # Static Check
        is_safe, error = check_command_safety(script, guard_rules_path)
        if not is_safe:
            return f"🛑 BLOCKED: {error}"

        # Confirmation Step (Delegated to UI)
        if input_func:
            try:
                # Pass the script to the input function for rendering the dialog
                confirmed = input_func(script)
                if not confirmed:
                    return "🛑 EXECUTION CANCELLED BY USER."
                
                # Feedback after confirmation
                success_msg = "\n✅ Confirmed. Executing...\n"
                if stream_callback:
                    stream_callback(success_msg)
                else:
                    print(success_msg)
            except Exception as e:
                return f"🛑 CONFIRMATION ERROR: {e}"

        try:
            # Build setup command from extensions
            setup_cmd = self._load_extensions()
            
            # Combine: setup && script
            if setup_cmd:
                full_command = f"{setup_cmd} && {script}"
            else:
                full_command = script
            
            # Use ProcessExecutor for reliable I/O
            executor = ProcessExecutor(work_dir=self.project_root)
            
            # Run with bash
            result = executor.run(
                ["/bin/bash", "-c", full_command],
                timeout=300 # 5 min timeout
            )
            
            # Helper to strip ANSI codes
            def strip_ansi(text):
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                return ansi_escape.sub('', text)

            # Minimal formatting with newline before block
            output = f"\n> {script}\n"
            
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            
            if stdout.strip():
                clean_stdout = strip_ansi(stdout)
                # Filter out the setup message
                clean_lines = [
                    line for line in clean_stdout.splitlines() 
                    if "🚀 Setting up AMI Orchestrator shell environment..." not in line
                ]
                final_stdout = "\n".join(clean_lines).strip()
                if final_stdout:
                    output += f"{final_stdout}\n"

            if stderr.strip():
                output += f"ERR: {strip_ansi(stderr).strip()}\n"
            
            if result.get("returncode", 0) != 0:
                output += f"(Exit Code: {result.get('returncode')})\n"
                
            return output
            
        except Exception as e:
            return f"EXEC ERR: {e}"


    def run(self, instruction: str, session_id: Optional[str] = None, stream_callback: Optional[Any] = None, stop_event: Optional[Any] = None, input_func: Optional[Callable[[str], bool]] = None, allowed_tools: Optional[List[str]] = None, timeout: int = 300, guard_rules_path: Optional[Path] = None) -> Tuple[str, str]:
        """
        Run the agent loop.
        
        Args:
            instruction: The user message.
            session_id: Optional Qwen session ID to resume.
            stream_callback: Optional callback(token) for streaming.
            stop_event: Optional threading.Event to signal cancellation.
            input_func: Optional function to wait for user input.
            allowed_tools: List of allowed tools. Defaults to None (all forbidden).
            timeout: Execution timeout in seconds. Defaults to 300.
            guard_rules_path: Optional path to custom guard rules YAML.
            
        Returns:
            Tuple of (response_text, actual_session_id)
        """
        current_session_id = session_id
        final_response_parts = []
        
        # Use provided tools or default (empty list for security)
        current_allowed_tools = allowed_tools if allowed_tools is not None else self.DEFAULT_ALLOWED_TOOLS
        
        # Determine initial prompt
        next_prompt = instruction
        if not current_session_id:
            banner = self._get_banner()
            
            # Construct tools message
            if current_allowed_tools and current_allowed_tools != ["save_memory"]:
                tools_msg = "Use the explicitly allowed tools for non-shell operations:" + "\n".join([f"- {t}" for t in current_allowed_tools])
            else:
                tools_msg = "No internal tools are available by default. Rely on shell commands for all operations."

            # Load template (Mandatory)
            if not self.prompt_template.exists():
                raise FileNotFoundError(f"CRITICAL: Agent prompt template missing at {self.prompt_template}")
                
            template = self.prompt_template.read_text()
            next_prompt = template.format(
                tools_msg=tools_msg,
                banner=banner,
                instruction=instruction
            )

        for i in range(self.MAX_LOOPS):
            # Check stop event
            if stop_event and stop_event.is_set():
                if stream_callback:
                    stream_callback("\n\n🛑 Agent execution stopped by user.\n")
                return "\n".join(final_response_parts) + "\n🛑 Agent stopped.", current_session_id or ""

            # 1. Configure Agent
            # Note: We rely on global config default or override here.
            global_config = get_config()
            provider_name = global_config.get("agent.provider", "claude")
            try:
                actual_provider = ProviderType(provider_name)
            except ValueError:
                actual_provider = ProviderType.CLAUDE

            default_model = global_config.get_provider_default_model(actual_provider)
            
            config = AgentConfig(
                model=global_config.get("agent.worker.model") or default_model,
                session_id=current_session_id,
                provider=actual_provider,
                allowed_tools=current_allowed_tools,
                enable_hooks=True,
                enable_streaming=True,
                timeout=timeout,
                stream_callback=stream_callback,
                guard_rules_path=guard_rules_path
            )
            
            # 2. Get Runtime and Execute
            runtime = self._get_runtime(config)
            
            try:
                # 3. Execute Agent
                output, metadata = runtime.run_print(
                    instruction=next_prompt,
                    agent_config=config,
                    cwd=self.project_root
                )
                
                # Capture/Update Session ID
                if metadata and "session_id" in metadata:
                    current_session_id = metadata["session_id"]
                
                if not current_session_id:
                    current_session_id = ""

            except Exception as e:
                # Propagate critical errors that should exit the CLI
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                
                error_msg = f"Agent Logic Error: {e}"
                if stream_callback:
                    stream_callback(f"\n{error_msg}\n")
                else:
                    sys.stderr.write(f"{error_msg}\n")
                
                # Check for specific errors that should exit
                if "isinstance() arg 2 must be a type" in str(e):
                     raise # Propagate type errors seen in tests
                
                return error_msg, current_session_id or ""
            
            # Add agent output to response
            final_response_parts.append(output)
            
            # 4. Parse 'run' or 'bash' Blocks (Robust/Loose parsing)
            # Matches ```run or ```bash, handles content with or without leading/trailing newlines
            shell_blocks = re.findall(r"```(?:run|bash)\n?(.*?)\n?```", output, re.DOTALL)
            
            if not shell_blocks:
                # Check for internal tool usage to auto-continue
                has_internal_tool = any(tool in output for tool in current_allowed_tools)
                has_blocked_msg = "🛑 BLOCKED:" in output
                
                if has_internal_tool or has_blocked_msg:
                     next_prompt = "Continue."
                     continue

                # No tool calls, we are done
                break
            
            # 5. Execute Tools and Prepare Next Prompt
            tool_outputs = []
            for block in shell_blocks:
                # Check stop event before execution
                if stop_event and stop_event.is_set():
                    break

                res = self.execute_shell(block, input_func, stream_callback, guard_rules_path)
                tool_outputs.append(res)
                # Stream result
                formatted_res = f"\n\n{res}\n\n"
                if stream_callback:
                    stream_callback(formatted_res)
                else:
                    print(formatted_res)
                
                final_response_parts.append(res)
            
            # The prompt for the next iteration is the tool output
            next_prompt = "Tool Output:\n" + "\n".join(tool_outputs)
            
        return "\n".join(final_response_parts), current_session_id
