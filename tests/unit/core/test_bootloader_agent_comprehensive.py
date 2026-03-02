"""Comprehensive unit tests for ami/core/bootloader_agent.py."""

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from ami.core.bootloader_agent import (
    BootloaderAgent,
    ExecutionResult,
    RunContext,
)

EXPECTED_DEFAULT_TIMEOUT = 300
EXPECTED_CUSTOM_TIMEOUT = 600


class TestRunContext:
    """Tests for RunContext model."""

    def test_minimal_init(self):
        """Test RunContext with minimal required fields."""
        ctx = RunContext(instruction="test")
        assert ctx.instruction == "test"
        assert ctx.session_id is None
        assert ctx.stream_callback is None
        assert ctx.stop_event is None
        assert ctx.input_func is None
        assert ctx.allowed_tools is None
        assert ctx.timeout == EXPECTED_DEFAULT_TIMEOUT
        assert ctx.scope_overrides == {}

    def test_full_init(self):
        """Test RunContext with all fields."""
        stop_event = Event()

        def input_func(x):
            return True

        def callback(x):
            return None

        ctx = RunContext(
            instruction="test",
            session_id="sess-123",
            stream_callback=callback,
            stop_event=stop_event,
            input_func=input_func,
            allowed_tools=["tool1", "tool2"],
            timeout=600,
            scope_overrides={"observe": "allow", "modify": "confirm"},
        )

        assert ctx.instruction == "test"
        assert ctx.session_id == "sess-123"
        assert ctx.timeout == EXPECTED_CUSTOM_TIMEOUT
        assert ctx.allowed_tools == ["tool1", "tool2"]
        assert ctx.scope_overrides == {"observe": "allow", "modify": "confirm"}


class TestExecutionResult:
    """Tests for ExecutionResult model."""

    def test_default_values(self):
        """Test ExecutionResult default values."""
        result = ExecutionResult()
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.returncode == 0

    def test_custom_values(self):
        """Test ExecutionResult with custom values."""
        result = ExecutionResult(
            stdout="output",
            stderr="error",
            returncode=1,
        )
        assert result.stdout == "output"
        assert result.stderr == "error"
        assert result.returncode == 1


class TestBootloaderAgentInit:
    """Tests for BootloaderAgent initialization."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_init_sets_paths(self, mock_get_root, mock_setup_env):
        """Test initialization sets correct paths."""
        mock_get_root.return_value = Path("/project")

        agent = BootloaderAgent()

        assert agent.project_root == Path("/project")
        assert agent.prompt_template == Path(
            "/project/ami/config/prompts/bootloader_agent.txt"
        )
        assert agent.extensions_config == Path(
            "/project/ami/config/extensions.template.yaml"
        )
        assert agent.runtime is None
        mock_setup_env.assert_called_once()

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_init_with_runtime(self, mock_get_root, mock_setup_env):
        """Test initialization with provided runtime."""
        mock_get_root.return_value = Path("/project")
        mock_runtime = MagicMock()

        agent = BootloaderAgent(runtime=mock_runtime)

        assert agent.runtime == mock_runtime


class TestGetRuntime:
    """Tests for _get_runtime method."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_provided_runtime(self, mock_get_root, mock_setup_env):
        """Test returns provided runtime."""
        mock_get_root.return_value = Path("/project")
        mock_runtime = MagicMock()

        agent = BootloaderAgent(runtime=mock_runtime)
        config = MagicMock()

        result = agent._get_runtime(config)

        assert result == mock_runtime

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_raises_without_runtime(self, mock_get_root, mock_setup_env):
        """Test raises RuntimeError when no runtime provided."""
        mock_get_root.return_value = Path("/project")

        agent = BootloaderAgent()
        config = MagicMock()

        with pytest.raises(RuntimeError, match="Agent runtime not provided"):
            agent._get_runtime(config)


class TestGetBanner:
    """Tests for _get_banner method."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_context_from_banner_script(
        self, mock_get_root, mock_setup_env, tmp_path
    ):
        """Test returns cleaned content from banner script."""
        mock_get_root.return_value = tmp_path

        # Create a fake banner script
        banner_dir = tmp_path / "ami" / "scripts" / "shell"
        banner_dir.mkdir(parents=True)
        banner_script = banner_dir / "ami-banner.sh"
        banner_script.write_text(
            "#!/bin/bash\necho 'AMI Orchestrator shell environment'"
        )
        banner_script.chmod(0o755)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="AMI Orchestrator shell environment\nTools available",
                stderr="",
            )
            agent = BootloaderAgent()
            result = agent._get_banner()

        assert "AMI Orchestrator" in result or "Tools available" in result

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_error_on_exception(self, mock_get_root, mock_setup_env, tmp_path):
        """Test returns error message on exception."""
        mock_get_root.return_value = tmp_path

        # Create a fake banner script so the path check passes
        banner_dir = tmp_path / "ami" / "scripts" / "shell"
        banner_dir.mkdir(parents=True)
        banner_script = banner_dir / "ami-banner.sh"
        banner_script.write_text("#!/bin/bash\nexit 1")
        banner_script.chmod(0o755)

        with patch("subprocess.run", side_effect=Exception("Test error")):
            agent = BootloaderAgent()
            result = agent._get_banner()

        assert "Error loading context" in result

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_fallback_when_script_missing(
        self, mock_get_root, mock_setup_env, tmp_path
    ):
        """Test returns fallback message when banner script doesn't exist."""
        mock_get_root.return_value = tmp_path

        agent = BootloaderAgent()
        result = agent._get_banner()

        assert "Banner script not found" in result

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_strips_ansi_codes(self, mock_get_root, mock_setup_env, tmp_path):
        """Test strips ANSI escape codes from banner output."""
        mock_get_root.return_value = tmp_path

        # Create a fake banner script
        banner_dir = tmp_path / "ami" / "scripts" / "shell"
        banner_dir.mkdir(parents=True)
        banner_script = banner_dir / "ami-banner.sh"
        banner_script.write_text("#!/bin/bash\necho test")
        banner_script.chmod(0o755)

        with patch("subprocess.run") as mock_run:
            # Include ANSI codes in the output
            mock_run.return_value = MagicMock(
                stdout="\x1b[32mGreen\x1b[0m Normal \x1b[1;34mBold Blue\x1b[0m",
                stderr="",
            )
            agent = BootloaderAgent()
            result = agent._get_banner()

        # Verify ANSI codes are stripped
        assert "\x1b[" not in result
        assert "Green" in result
        assert "Normal" in result
        assert "Bold Blue" in result


class TestLoadExtensions:
    """Tests for _load_extensions method."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_empty_when_no_config(
        self, mock_get_root, mock_setup_env, tmp_path
    ):
        """Test returns empty when config doesn't exist."""
        mock_get_root.return_value = tmp_path

        agent = BootloaderAgent()
        result = agent._load_extensions()

        assert result == ""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_loads_extensions(self, mock_get_root, mock_setup_env, tmp_path):
        """Test loads and formats extensions."""
        mock_get_root.return_value = tmp_path

        # Create config file
        config_dir = tmp_path / "ami" / "config"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "extensions.template.yaml"
        config_file.write_text("""
extensions:
  - ext1 --setup
  - ext2 --init
""")

        agent = BootloaderAgent()
        agent.extensions_config = config_file

        result = agent._load_extensions()

        assert 'eval "$(ext1 --setup)"' in result
        assert 'eval "$(ext2 --init)"' in result
        assert " && " in result

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_skips_dict_extensions(self, mock_get_root, mock_setup_env, tmp_path):
        """Dict entries in extensions list are skipped (not eval'd)."""
        mock_get_root.return_value = tmp_path

        config_dir = tmp_path / "ami" / "config"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "extensions.template.yaml"
        config_file.write_text(
            "extensions:\n"
            "  - name: ami-agent\n"
            "    binary: ami-agent\n"
            "    description: Main entry point\n"
            "    category: core\n"
        )

        agent = BootloaderAgent()
        agent.extensions_config = config_file

        result = agent._load_extensions()

        assert result == ""


class TestHandleUserConfirmation:
    """Tests for _handle_user_confirmation method."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_none_on_confirm(self, mock_get_root, mock_setup_env):
        """Test returns None when user confirms."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        def input_func(x):
            return True

        callback = MagicMock()

        result = agent._handle_user_confirmation("ls -la", input_func, callback)

        assert result is None
        callback.assert_called_once()

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_cancelled_on_reject(self, mock_get_root, mock_setup_env):
        """Test returns cancelled message when user rejects."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        def input_func(x):
            return False

        result = agent._handle_user_confirmation("rm -rf /", input_func, None)

        assert "CANCELLED BY USER" in result

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_returns_error_on_exception(self, mock_get_root, mock_setup_env):
        """Test returns error on input_func exception."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        def bad_input(x):
            msg = "Input error"
            raise ValueError(msg)

        result = agent._handle_user_confirmation("cmd", bad_input, None)

        assert "CONFIRMATION ERROR" in result


class TestFormatShellOutput:
    """Tests for _format_shell_output method."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_formats_success(self, mock_get_root, mock_setup_env):
        """Test formats successful output."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        result = ExecutionResult(stdout="output\n", stderr="", returncode=0)
        output = agent._format_shell_output("echo test", result)

        assert "> echo test" in output
        assert "output" in output
        assert "Exit Code" not in output

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_formats_error(self, mock_get_root, mock_setup_env):
        """Test formats error output."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        result = ExecutionResult(stdout="", stderr="error msg", returncode=1)
        output = agent._format_shell_output("bad_cmd", result)

        assert "ERR: error msg" in output
        assert "Exit Code: 1" in output


class TestBuildToolsMessage:
    """Tests for _build_tools_message method."""

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_with_custom_tools(self, mock_get_root, mock_setup_env):
        """Test builds message with custom tools."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        result = agent._build_tools_message(["tool1", "tool2"])

        assert "explicitly allowed tools" in result
        assert "tool1" in result
        assert "tool2" in result

    @patch("ami.core.bootloader_agent.setup_agent_env")
    @patch("ami.core.bootloader_agent.get_project_root")
    def test_default_tools(self, mock_get_root, mock_setup_env):
        """Test builds message for default tools."""
        mock_get_root.return_value = Path("/project")
        agent = BootloaderAgent()

        result = agent._build_tools_message(["save_memory"])

        assert "No internal tools are available" in result
