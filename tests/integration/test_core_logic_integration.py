"""Integration tests for core logic, config, env, and factory modules.

Exercises: core/logic.py, core/config.py, core/env.py, core/factory.py,
config_utils.py
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ami.cli.provider_type import ProviderType
from ami.config_utils import get_config_path
from ami.core.bootloader_agent import BootloaderAgent
from ami.core.config import Config, _ConfigSingleton, get_config
from ami.core.env import _ProjectRootCache, get_project_root
from ami.core.factory import AgentFactory
from ami.core.logic import (
    parse_code_fence_output,
    parse_completion_marker,
    parse_json_block,
    parse_moderator_result,
)

# Named constant for magic number used in assertions
EXPECTED_JSON_VALUE = 42

# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------


class TestConfigLoading:
    """Test Config loads and parses real automation.yaml."""

    def test_config_loads_from_real_yaml(self, real_config: Config):
        assert real_config._data is not None
        assert isinstance(real_config._data, dict)

    def test_config_root_is_valid_path(self, real_config: Config):
        assert real_config.root.exists()
        assert (real_config.root / "pyproject.toml").exists()

    def test_config_file_path(self, real_config: Config):
        assert real_config.config_file.exists()
        assert real_config.config_file.name == "automation.yaml"

    def test_config_get_value_returns_data(self, real_config: Config):
        # The config should have at least some top-level key
        assert real_config._data  # not empty

    def test_config_get_value_missing_key_returns_default(self, real_config: Config):
        result = real_config.get_value("nonexistent.deep.key", "fallback")
        assert result == "fallback"

    def test_config_get_value_none_default(self, real_config: Config):
        result = real_config.get_value("nonexistent_key")
        assert result is None

    def test_config_env_var_substitution(self, monkeypatch: pytest.MonkeyPatch):
        """Verify ${VAR:default} substitution works."""
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        monkeypatch.setenv("AMI_TEST_SENTINEL", "hello_world")
        _ConfigSingleton.instance = None
        try:
            cfg = Config()
            # _substitute_env should handle ${AMI_TEST_SENTINEL:fallback}
            result = cfg._substitute_env("value=${AMI_TEST_SENTINEL:fallback}")
            assert result == "value=hello_world"
        finally:
            _ConfigSingleton.instance = None

    def test_config_env_var_default_when_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        monkeypatch.delenv("AMI_NONEXISTENT_VAR_XYZ", raising=False)
        _ConfigSingleton.instance = None
        try:
            cfg = Config()
            result = cfg._substitute_env("${AMI_NONEXISTENT_VAR_XYZ:default_val}")
            assert result == "default_val"
        finally:
            _ConfigSingleton.instance = None

    def test_config_root_substitution(self, real_config: Config):
        result = real_config._substitute_env("{root}/some/path")
        assert str(real_config.root) in result
        assert result.endswith("/some/path")

    def test_config_recursive_substitution(self, real_config: Config):
        data = {"key": "{root}/path", "nested": ["{root}/other"]}
        result = real_config._substitute_env(data)
        assert isinstance(result, dict)
        assert str(real_config.root) in result["key"]
        assert str(real_config.root) in result["nested"][0]

    def test_config_test_mode_disables_file_locking(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        try:
            cfg = Config()
            tasks = cfg.get_value("tasks")
            if isinstance(tasks, dict):
                assert tasks.get("file_locking") is False
        finally:
            _ConfigSingleton.instance = None


class TestConfigSingleton:
    """Test the get_config singleton behavior."""

    def test_singleton_returns_same_instance(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        try:
            c1 = get_config()
            c2 = get_config()
            assert c1 is c2
        finally:
            _ConfigSingleton.instance = None

    def test_singleton_reset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        try:
            c1 = get_config()
            _ConfigSingleton.instance = None
            c2 = get_config()
            assert c1 is not c2
        finally:
            _ConfigSingleton.instance = None


class TestConfigProviders:
    """Test provider configuration methods."""

    def test_get_provider_default_model(self, real_config: Config):
        assert (
            real_config.get_provider_default_model(ProviderType.CLAUDE)
            == "claude-sonnet-4-5"
        )
        assert real_config.get_provider_default_model(ProviderType.QWEN) == "qwen-coder"
        assert (
            real_config.get_provider_default_model(ProviderType.GEMINI)
            == "gemini-3-pro"
        )

    def test_get_provider_audit_model(self, real_config: Config):
        assert (
            real_config.get_provider_audit_model(ProviderType.CLAUDE)
            == "claude-sonnet-4-5"
        )
        assert (
            real_config.get_provider_audit_model(ProviderType.GEMINI)
            == "gemini-3-flash"
        )

    def test_get_provider_command_returns_string(self, real_config: Config):
        cmd = real_config.get_provider_command(ProviderType.CLAUDE)
        assert isinstance(cmd, str)
        assert len(cmd) > 0


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------


class TestProjectRoot:
    """Test get_project_root resolution."""

    def test_returns_path_with_pyproject(self, project_root: Path):
        assert (project_root / "pyproject.toml").exists()

    def test_returns_path_with_ami_dir(self, project_root: Path):
        assert (project_root / "ami").is_dir()

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """AMI_PROJECT_ROOT env var overrides detection."""
        marker = tmp_path / "pyproject.toml"
        marker.write_text("[project]\nname='test'\n")
        monkeypatch.setenv("AMI_PROJECT_ROOT", str(tmp_path))

        # Clear cache to force re-evaluation
        _ProjectRootCache._value = None
        try:
            root = get_project_root()
            assert root == tmp_path
        finally:
            _ProjectRootCache._value = None
            monkeypatch.delenv("AMI_PROJECT_ROOT", raising=False)


# ---------------------------------------------------------------------------
# Code fence parsing
# ---------------------------------------------------------------------------


class TestParseCodeFenceOutput:
    """Test parse_code_fence_output with real fenced blocks."""

    def test_no_fences_returns_stripped(self):
        assert parse_code_fence_output("  hello world  ") == "hello world"

    def test_removes_code_fence(self):
        text = "```python\nprint('hi')\n```"
        result = parse_code_fence_output(text)
        assert result == "print('hi')"

    def test_removes_plain_fence(self):
        text = "```\nsome code\n```"
        assert parse_code_fence_output(text) == "some code"

    def test_multi_line_fenced(self):
        text = "```bash\nline1\nline2\nline3\n```"
        result = parse_code_fence_output(text)
        assert "line1" in result
        assert "line3" in result

    def test_no_closing_fence(self):
        text = "```python\ncode here"
        result = parse_code_fence_output(text)
        assert result == "code here"

    def test_empty_string(self):
        assert parse_code_fence_output("") == ""


# ---------------------------------------------------------------------------
# Completion markers
# ---------------------------------------------------------------------------


class TestParseCompletionMarker:
    """Test parse_completion_marker with various variants."""

    def test_work_done(self):
        result = parse_completion_marker("Task completed. WORK DONE")
        assert result["type"] == "work_done"
        assert result["content"] is None

    def test_feedback(self):
        result = parse_completion_marker("FEEDBACK: need more info about X")
        assert result["type"] == "feedback"
        assert "need more info" in result["content"]

    def test_none_marker(self):
        result = parse_completion_marker("just normal output")
        assert result["type"] == "none"
        assert result["content"] is None

    def test_empty_string(self):
        result = parse_completion_marker("")
        assert result["type"] == "none"


# ---------------------------------------------------------------------------
# Moderator result parsing
# ---------------------------------------------------------------------------


class TestParseModeratorResult:
    """Test parse_moderator_result with pass/fail/unclear variants."""

    def test_pass(self):
        result = parse_moderator_result("Code quality: PASS")
        assert result["status"] == "pass"
        assert result["reason"] is None

    def test_fail_with_reason(self):
        result = parse_moderator_result("FAIL: code uses eval()")
        assert result["status"] == "fail"
        assert "eval()" in result["reason"]

    def test_unclear_defaults_to_fail(self):
        result = parse_moderator_result("something ambiguous")
        assert result["status"] == "fail"
        assert "unclear" in result["reason"].lower()


# ---------------------------------------------------------------------------
# JSON block parsing
# ---------------------------------------------------------------------------


class TestParseJsonBlock:
    """Test parse_json_block with fenced, bare, nested, and invalid JSON."""

    def test_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = parse_json_block(text)
        assert result["key"] == "value"

    def test_bare_json(self):
        text = '{"key": 42}'
        result = parse_json_block(text)
        assert result["key"] == EXPECTED_JSON_VALUE

    def test_nested_json(self):
        text = '```\n{"outer": {"inner": true}}\n```'
        result = parse_json_block(text)
        assert result["outer"]["inner"] is True

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"status": "ok"} done.'
        result = parse_json_block(text)
        assert result["status"] == "ok"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_json_block("not json at all {broken")

    def test_array_wrapped_in_dict(self):
        text = "```json\n[1, 2, 3]\n```"
        result = parse_json_block(text)
        assert "data" in result
        assert result["data"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Config utils
# ---------------------------------------------------------------------------


class TestConfigUtils:
    """Test config_utils path resolution."""

    def test_get_config_path(self, project_root: Path):
        path = get_config_path("automation.yaml")
        assert path.name == "automation.yaml"
        assert "res/config" in str(path)

    def test_get_vendor_config_path(self, project_root: Path):
        path = get_config_path("automation.yaml")
        assert isinstance(path, Path)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


class TestAgentFactory:
    """Test AgentFactory.create_bootloader."""

    def test_create_bootloader_returns_agent(self, real_config: Config):
        # Pass a mock runtime to avoid needing a real CLI
        mock_runtime = MagicMock()
        agent = AgentFactory.create_bootloader(runtime=mock_runtime)
        assert isinstance(agent, BootloaderAgent)
