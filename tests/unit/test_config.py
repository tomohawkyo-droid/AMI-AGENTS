"""Unit tests for automation.config module."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml

import ami.core.config as config_module
from ami.cli.provider_type import ProviderType
from ami.core.config import Config, get_config


class TestConfigData(TypedDict, total=False):
    """TypedDict for config data used in tests."""

    version: str
    environment: str
    logging: object
    paths: object
    nested: object
    test_var: str
    list_values: object
    tasks: object
    non_string_path: object
    agent: object


class TasksConfig(TypedDict, total=False):
    """TypedDict for tasks config used in tests."""

    file_locking: bool
    other: str


class NestedConfigData(TypedDict, total=False):
    """TypedDict for nested config data in tests."""

    value: str


def _get_data(config: Config) -> TestConfigData:
    """Get config._data for test assertions."""
    return cast(TestConfigData, config._data)


@pytest.fixture
def temp_config_file() -> Generator[Path, None, None]:
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {
            "version": "2.0.0",
            "environment": "test",
            "logging": {"level": "INFO", "format": "json"},
            "paths": {"logs": "logs", "config": "config"},
        }
        yaml.dump(config_data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_env_var_config() -> Generator[Path, None, None]:
    """Create config with environment variables."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_data = {
            "environment": "${AMI_ENV:development}",
            "test_var": "${TEST_VAR}",
            "nested": {"value": "${NESTED_VAR:default_value}"},
        }
        yaml.dump(config_data, f)
        temp_path = Path(f.name)

    yield temp_path

    if temp_path.exists():
        temp_path.unlink()


class TestConfig:
    """Unit tests for Config class."""

    def test_load_valid_yaml(self, temp_config_file: Path) -> None:
        """Config loads valid YAML file."""
        config = Config(config_file=temp_config_file)

        assert config._data is not None
        assert _get_data(config)["version"] == "2.0.0"
        assert _get_data(config)["environment"] == "test"

    def test_environment_variable_substitution(self, temp_env_var_config: Path) -> None:
        """Config substitutes ${VAR:default} patterns."""
        # Set environment variable
        os.environ["AMI_ENV"] = "production"

        try:
            config = Config(config_file=temp_env_var_config)
            assert _get_data(config)["environment"] == "production"
        finally:
            # Cleanup
            if "AMI_ENV" in os.environ:
                del os.environ["AMI_ENV"]

    def test_environment_variable_no_default(self, temp_env_var_config: Path) -> None:
        """Config handles ${VAR} without default."""
        # Ensure TEST_VAR is not set
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        config = Config(config_file=temp_env_var_config)
        # Should return empty string when var not set and no default
        assert _get_data(config)["test_var"] == ""

    def test_nested_environment_substitution(self, temp_env_var_config: Path) -> None:
        """Config substitutes env vars in nested dicts."""
        os.environ["NESTED_VAR"] = "nested_value"

        try:
            config = Config(config_file=temp_env_var_config)
            nested = cast(NestedConfigData, _get_data(config)["nested"])
            assert nested["value"] == "nested_value"
        finally:
            if "NESTED_VAR" in os.environ:
                del os.environ["NESTED_VAR"]

    def test_dot_notation_access(self, temp_config_file: Path) -> None:
        """Config.get_value() supports dot notation."""
        config = Config(config_file=temp_config_file)

        assert config.get_value("logging.level") == "INFO"
        assert config.get_value("logging.format") == "json"

    def test_dot_notation_missing_key(self, temp_config_file: Path) -> None:
        """Config.get_value() returns default for missing keys."""
        config = Config(config_file=temp_config_file)

        assert config.get_value("missing.key", "default") == "default"
        assert config.get_value("missing.nested.key") is None

    def test_resolve_path_with_template(self, temp_config_file: Path) -> None:
        """Config.resolve_path() handles template substitution."""
        config = Config(config_file=temp_config_file)

        path = config.resolve_path("paths.logs", date="2025-10-18")
        # Should return absolute path with template substituted
        assert "logs" in str(path)
        # Path should be absolute
        assert path.is_absolute()

    def test_resolve_path_absolute(self, temp_config_file: Path) -> None:
        """Config.resolve_path() returns absolute paths."""
        config = Config(config_file=temp_config_file)

        path = config.resolve_path("paths.logs")
        assert path.is_absolute()
        assert config.root in path.parents or path == config.root / "logs"

    def test_config_file_not_found(self) -> None:
        """Config raises error if file missing."""
        with pytest.raises(FileNotFoundError) as exc_info:
            Config(config_file=Path("/nonexistent/path.yaml"))

        assert "not found" in str(exc_info.value).lower()

    def test_invalid_yaml_syntax(self) -> None:
        """Config raises error on invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Write malformed YAML
            f.write("version: 2.0.0\n")
            f.write("  invalid indentation: true\n")
            f.write("missing_quote: '\n")
            temp_path = Path(f.name)

        try:
            with pytest.raises((ValueError, yaml.YAMLError)):
                Config(config_file=temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_singleton_pattern(
        self, temp_config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_config() returns same instance."""
        # Create temp config as default
        monkeypatch.setenv("TEST_CONFIG", str(temp_config_file))

        # Reset singleton
        config_module._ConfigSingleton.instance = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_orchestrator_root_detection(self, temp_config_file: Path) -> None:
        """Config detects orchestrator root correctly."""
        config = Config(config_file=temp_config_file)

        # root should be set to ORCHESTRATOR_ROOT
        assert config.root is not None
        assert isinstance(config.root, Path)
        assert config.root.is_absolute()

    def test_empty_config_raises_error(self) -> None:
        """Config raises error if YAML is empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match=r"(?i)empty"):
                Config(config_file=temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_value_returns_default_for_non_dict_path(
        self, temp_config_file: Path
    ) -> None:
        """Config.get_value returns default when path goes through non-dict."""
        config = Config(config_file=temp_config_file)

        # logging.level is "INFO" (a string), so logging.level.subkey should fail
        result = config.get_value("logging.level.subkey", "default_val")

        assert result == "default_val"

    def test_resolve_path_type_error(self, temp_config_file: Path) -> None:
        """Config.resolve_path raises TypeError for non-string template."""
        config = Config(config_file=temp_config_file)

        # Manually set a non-string value
        _get_data(config)["non_string_path"] = 12345

        with pytest.raises(TypeError) as exc_info:
            config.resolve_path("non_string_path")

        assert "must be string" in str(exc_info.value)

    def test_list_env_substitution(self) -> None:
        """Config substitutes env vars in list values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {
                "list_values": ["${LIST_VAR:item1}", "static", "${OTHER_VAR:item2}"]
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)
            list_values = cast(list[str], _get_data(config)["list_values"])
            assert list_values[0] == "item1"
            assert list_values[1] == "static"
            assert list_values[2] == "item2"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_ami_test_mode_creates_tasks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config creates tasks dict when AMI_TEST_MODE=1."""
        monkeypatch.setenv("AMI_TEST_MODE", "1")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Config without tasks key
            config_data = {"version": "2.0.0"}
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)
            data = _get_data(config)
            assert "tasks" in data
            tasks = cast(TasksConfig, data["tasks"])
            assert tasks["file_locking"] is False
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_ami_test_mode_updates_existing_tasks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config updates existing tasks when AMI_TEST_MODE=1."""
        monkeypatch.setenv("AMI_TEST_MODE", "1")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"version": "2.0.0", "tasks": {"other": "value"}}
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)
            tasks = cast(TasksConfig, _get_data(config)["tasks"])
            assert tasks["file_locking"] is False
            assert tasks["other"] == "value"
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestConfigProviderMethods:
    """Tests for provider-related methods in Config."""

    @pytest.fixture
    def config_with_providers(self) -> Generator[Config, None, None]:
        """Create config with provider settings."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {
                "version": "2.0.0",
                "agent": {
                    "claude": {"command": "custom-claude"},
                    "qwen": {"command": "/usr/local/bin/qwen"},
                },
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        config = Config(config_file=temp_path)
        yield config

        if temp_path.exists():
            temp_path.unlink()

    def test_get_provider_command_custom(self, config_with_providers: Config) -> None:
        """Test getting custom provider command."""
        cmd = config_with_providers.get_provider_command(ProviderType.CLAUDE)
        # Should be absolute path resolved from relative "custom-claude"
        assert "custom-claude" in cmd

    def test_get_provider_command_absolute(self, config_with_providers: Config) -> None:
        """Test getting absolute provider command."""
        cmd = config_with_providers.get_provider_command(ProviderType.QWEN)
        # Already absolute, should stay as is
        assert cmd == "/usr/local/bin/qwen"

    def test_get_provider_command_default(self) -> None:
        """Test getting default provider command when not configured."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"version": "2.0.0"}
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)
            cmd = config.get_provider_command(ProviderType.GEMINI)
            # Should use default "gemini" resolved to absolute path
            assert "gemini" in cmd
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_provider_command_non_string_config(self) -> None:
        """Test provider command when config value is not a string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"version": "2.0.0", "agent": {"claude": {"command": 12345}}}
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)
            cmd = config.get_provider_command(ProviderType.CLAUDE)
            # Should fall back to default "claude"
            assert "claude" in cmd
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_provider_default_model(self) -> None:
        """Test getting default models for providers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"version": "2.0.0"}
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)

            assert (
                config.get_provider_default_model(ProviderType.CLAUDE)
                == "claude-sonnet-4-5"
            )
            assert config.get_provider_default_model(ProviderType.QWEN) == "qwen-coder"
            assert (
                config.get_provider_default_model(ProviderType.GEMINI) == "gemini-3-pro"
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_provider_audit_model(self) -> None:
        """Test getting audit models for providers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_data = {"version": "2.0.0"}
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(config_file=temp_path)

            assert (
                config.get_provider_audit_model(ProviderType.CLAUDE)
                == "claude-sonnet-4-5"
            )
            assert config.get_provider_audit_model(ProviderType.QWEN) == "qwen-coder"
            assert (
                config.get_provider_audit_model(ProviderType.GEMINI) == "gemini-3-flash"
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()
