"""Integration tests for CLI provider implementations.

Exercises: cli/claude_cli.py, cli/qwen_cli.py, cli/gemini_cli.py,
cli/base_provider.py, cli/factory.py, cli/interface.py
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ami.cli.claude_cli import ClaudeAgentCLI
from ami.cli.factory import get_agent_cli
from ami.cli.gemini_cli import GeminiAgentCLI
from ami.cli.interface import AgentCLI
from ami.cli.provider_type import ProviderType
from ami.cli.qwen_cli import QwenAgentCLI
from ami.core.config import _ConfigSingleton
from ami.types.config import AgentConfig

# Named constant for magic number used in assertions
EXPECTED_DEFAULT_TIMEOUT = 180


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    """Ensure Config is available for provider tests."""
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# Claude provider
# ---------------------------------------------------------------------------


class TestClaudeAgentCLI:
    """Test ClaudeAgentCLI build and parse."""

    def test_init(self):
        cli = ClaudeAgentCLI()
        assert cli.current_process is None

    def test_default_config(self):
        cli = ClaudeAgentCLI()
        cfg = cli._get_default_config()
        assert cfg.model == "claude-sonnet-4-5"
        assert cfg.enable_hooks is True
        assert cfg.timeout == EXPECTED_DEFAULT_TIMEOUT

    def test_all_tools_not_empty(self):
        assert len(ClaudeAgentCLI.ALL_TOOLS) > 0
        assert "Bash" in ClaudeAgentCLI.ALL_TOOLS
        assert "Read" in ClaudeAgentCLI.ALL_TOOLS

    def test_build_command_basic(self):
        cli = ClaudeAgentCLI()
        cfg = AgentConfig(model="claude-sonnet-4-5", provider=ProviderType.CLAUDE)
        cmd = cli._build_command("Do something", None, cfg)
        assert isinstance(cmd, list)
        assert "--model" in cmd
        assert "claude-sonnet-4-5" in cmd
        assert "--print" in cmd
        assert "Do something" in cmd

    def test_build_command_with_session(self):
        cli = ClaudeAgentCLI()
        cfg = AgentConfig(
            model="claude-sonnet-4-5",
            provider=ProviderType.CLAUDE,
            session_id="01926b78-24d4-7d25-8123-456789abcdef",
        )
        cmd = cli._build_command("test", None, cfg)
        assert "--session-id" in cmd

    def test_build_command_with_streaming(self):
        cli = ClaudeAgentCLI()
        cfg = AgentConfig(
            model="claude-sonnet-4-5",
            provider=ProviderType.CLAUDE,
            enable_streaming=True,
        )
        cmd = cli._build_command("test", None, cfg)
        assert "--verbose" in cmd
        assert "stream-json" in cmd

    def test_build_command_with_tools(self):
        cli = ClaudeAgentCLI()
        cfg = AgentConfig(
            model="claude-sonnet-4-5",
            provider=ProviderType.CLAUDE,
            allowed_tools=["Bash", "Read"],
        )
        cmd = cli._build_command("test", None, cfg)
        assert "--allowed-tools" in cmd
        assert "Bash" in cmd
        assert "Read" in cmd

    def test_build_command_with_cwd(self, tmp_path: Path):
        cli = ClaudeAgentCLI()
        cfg = AgentConfig(model="claude-sonnet-4-5", provider=ProviderType.CLAUDE)
        cmd = cli._build_command("test", tmp_path, cfg)
        assert "--add-dir" in cmd
        assert str(tmp_path) in cmd

    def test_parse_stream_empty_line(self):
        cli = ClaudeAgentCLI()
        text, meta = cli._parse_stream_message("", [], 0, None)
        assert text == ""
        assert meta is None

    def test_parse_stream_content_block_delta(self):
        cli = ClaudeAgentCLI()
        msg = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"text": "hello world"},
            }
        )
        text, meta = cli._parse_stream_message(msg, [], 1, None)
        assert text == "hello world"
        assert meta is not None
        assert meta.provider == "claude"

    def test_parse_stream_assistant_message(self):
        cli = ClaudeAgentCLI()
        msg = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "response text"}],
                },
            }
        )
        text, _meta = cli._parse_stream_message(msg, [], 1, None)
        assert "response text" in text

    def test_parse_stream_system_type(self):
        cli = ClaudeAgentCLI()
        msg = json.dumps({"type": "system"})
        text, _meta = cli._parse_stream_message(msg, [], 1, None)
        assert text == ""

    def test_parse_stream_result_type(self):
        cli = ClaudeAgentCLI()
        msg = json.dumps({"type": "result", "session_id": "s123"})
        text, meta = cli._parse_stream_message(msg, [], 1, None)
        assert text == ""
        assert meta.session_id == "s123"

    def test_parse_stream_non_json(self):
        cli = ClaudeAgentCLI()
        text, meta = cli._parse_stream_message("plain text output", [], 1, None)
        assert text == "plain text output"
        assert meta is None

    def test_extract_assistant_message_empty_content(self):
        cli = ClaudeAgentCLI()
        result = cli._extract_assistant_message({"content": []})
        assert result == ""

    def test_extract_assistant_message_non_dict(self):
        cli = ClaudeAgentCLI()
        result = cli._extract_assistant_message("not a dict")
        assert result == ""


# ---------------------------------------------------------------------------
# Qwen provider
# ---------------------------------------------------------------------------


class TestQwenAgentCLI:
    """Test QwenAgentCLI build and parse."""

    def test_default_config(self):
        cli = QwenAgentCLI()
        cfg = cli._get_default_config()
        assert cfg.model == "qwen-coder"

    def test_all_tools(self):
        assert "run_shell_command" in QwenAgentCLI.ALL_TOOLS
        assert "read_file" in QwenAgentCLI.ALL_TOOLS

    def test_build_command_basic(self):
        cli = QwenAgentCLI()
        cfg = AgentConfig(model="qwen-coder", provider=ProviderType.QWEN)
        cmd = cli._build_command("Do task", None, cfg)
        assert "--model" in cmd
        assert "qwen-coder" in cmd
        assert "--yolo" in cmd
        assert "Do task" in cmd

    def test_build_command_with_session(self):
        cli = QwenAgentCLI()
        cfg = AgentConfig(
            model="qwen-coder",
            provider=ProviderType.QWEN,
            session_id="session-abc",
        )
        cmd = cli._build_command("test", None, cfg)
        assert "--resume" in cmd
        assert "session-abc" in cmd

    def test_build_command_with_streaming(self):
        cli = QwenAgentCLI()
        cfg = AgentConfig(
            model="qwen-coder",
            provider=ProviderType.QWEN,
            enable_streaming=True,
        )
        cmd = cli._build_command("test", None, cfg)
        assert "stream-json" in cmd
        assert "--include-partial-messages" in cmd

    def test_build_command_with_tools(self):
        cli = QwenAgentCLI()
        cfg = AgentConfig(
            model="qwen-coder",
            provider=ProviderType.QWEN,
            allowed_tools=["read_file", "edit"],
        )
        cmd = cli._build_command("test", None, cfg)
        assert "--allowed-tools" in cmd

    def test_parse_stream_empty(self):
        cli = QwenAgentCLI()
        text, meta = cli._parse_stream_message("  ", [], 0, None)
        assert text == ""
        assert meta is None

    def test_parse_stream_event(self):
        cli = QwenAgentCLI()
        msg = json.dumps(
            {
                "type": "stream_event",
                "session_id": "qsess",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"text": "qwen output"},
                },
            }
        )
        text, meta = cli._parse_stream_message(msg, [], 1, None)
        assert text == "qwen output"
        assert meta is not None
        assert meta.session_id == "qsess"

    def test_parse_system_init(self):
        cli = QwenAgentCLI()
        msg = json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "session_id": "init-sess",
            }
        )
        text, meta = cli._parse_stream_message(msg, [], 1, None)
        assert text == ""
        assert meta.session_id == "init-sess"

    def test_parse_result_type(self):
        cli = QwenAgentCLI()
        msg = json.dumps(
            {
                "type": "result",
                "session_id": "result-sess",
            }
        )
        text, meta = cli._parse_stream_message(msg, [], 1, None)
        assert text == ""
        assert meta.session_id == "result-sess"

    def test_parse_non_json(self):
        cli = QwenAgentCLI()
        text, meta = cli._parse_stream_message("raw text", [], 1, None)
        assert text == "raw text"
        assert meta is None


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


class TestGeminiAgentCLI:
    """Test GeminiAgentCLI build and parse."""

    def test_default_config(self):
        cli = GeminiAgentCLI()
        cfg = cli._get_default_config()
        assert cfg.model == "gemini-3-pro"

    def test_all_tools(self):
        assert "read_file" in GeminiAgentCLI.ALL_TOOLS
        assert "run_shell_command" in GeminiAgentCLI.ALL_TOOLS
        assert "google_web_search" in GeminiAgentCLI.ALL_TOOLS

    def test_build_command_basic(self):
        cli = GeminiAgentCLI()
        cfg = AgentConfig(model="gemini-3-pro", provider=ProviderType.GEMINI)
        cmd = cli._build_command("Do task", None, cfg)
        assert "--prompt" in cmd
        assert "Do task" in cmd
        assert "--model" in cmd
        assert "gemini-3-pro" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--yolo" in cmd

    def test_build_command_with_session(self):
        cli = GeminiAgentCLI()
        cfg = AgentConfig(
            model="gemini-3-pro",
            provider=ProviderType.GEMINI,
            session_id="gem-sess",
        )
        cmd = cli._build_command("test", None, cfg)
        assert "--resume" in cmd
        assert "gem-sess" in cmd

    def test_parse_stream_passthrough(self):
        cli = GeminiAgentCLI()
        text, meta = cli._parse_stream_message("raw output", [], 1, None)
        assert text == "raw output"
        assert meta is None


# ---------------------------------------------------------------------------
# CLI factory
# ---------------------------------------------------------------------------


class TestCLIFactory:
    """Test get_agent_cli factory dispatch."""

    def test_default_returns_valid_cli(self):
        cli = get_agent_cli()
        assert isinstance(cli, AgentCLI)

    def test_claude_dispatch(self):
        cfg = AgentConfig(
            model="claude-sonnet-4-5",
            provider=ProviderType.CLAUDE,
        )
        cli = get_agent_cli(cfg)
        assert isinstance(cli, ClaudeAgentCLI)

    def test_qwen_dispatch(self):
        cfg = AgentConfig(
            model="qwen-coder",
            provider=ProviderType.QWEN,
        )
        cli = get_agent_cli(cfg)
        assert isinstance(cli, QwenAgentCLI)

    def test_gemini_dispatch(self):
        cfg = AgentConfig(
            model="gemini-3-pro",
            provider=ProviderType.GEMINI,
        )
        cli = get_agent_cli(cfg)
        assert isinstance(cli, GeminiAgentCLI)


# ---------------------------------------------------------------------------
# Base provider (kill_current_process)
# ---------------------------------------------------------------------------


class TestBaseProvider:
    """Test base provider behavior."""

    def test_kill_current_process_no_process(self):
        cli = ClaudeAgentCLI()
        assert cli.current_process is None
        result = cli.kill_current_process()
        assert result is False

    def test_kill_current_process_with_mock_process(self):
        cli = ClaudeAgentCLI()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        cli.current_process = mock_proc
        result = cli.kill_current_process()
        assert result is True
        mock_proc.terminate.assert_called_once()
