"""Unit tests for automation.config module."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

import ami.core.config as config_module
from ami.core.config import Config, get_config


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
        assert config._data["version"] == "2.0.0"
        assert config._data["environment"] == "test"

    def test_environment_variable_substitution(self, temp_env_var_config: Path) -> None:
        """Config substitutes ${VAR:default} patterns."""
        # Set environment variable
        os.environ["AMI_ENV"] = "production"

        try:
            config = Config(config_file=temp_env_var_config)
            assert config._data["environment"] == "production"
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
        assert config._data["test_var"] == ""

    def test_nested_environment_substitution(self, temp_env_var_config: Path) -> None:
        """Config substitutes env vars in nested dicts."""
        os.environ["NESTED_VAR"] = "nested_value"

        try:
            config = Config(config_file=temp_env_var_config)
            assert config._data["nested"]["value"] == "nested_value"
        finally:
            if "NESTED_VAR" in os.environ:
                del os.environ["NESTED_VAR"]

    def test_dot_notation_access(self, temp_config_file: Path) -> None:
        """Config.get() supports dot notation."""
        config = Config(config_file=temp_config_file)

        assert config.get("logging.level") == "INFO"
        assert config.get("logging.format") == "json"

    def test_dot_notation_missing_key(self, temp_config_file: Path) -> None:
        """Config.get() returns default for missing keys."""
        config = Config(config_file=temp_config_file)

        assert config.get("missing.key", "default") == "default"
        assert config.get("missing.nested.key") is None

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
