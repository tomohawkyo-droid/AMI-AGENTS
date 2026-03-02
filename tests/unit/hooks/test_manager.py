"""Unit tests for ami/hooks/manager.py."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from ami.hooks.manager import HookManager
from ami.hooks.types import HookContext, HookEvent, HookResult

EXPECTED_DUAL_VALIDATORS = 2


class TestHookManagerRun:
    def test_noop_allows_everything(self) -> None:
        manager = HookManager.noop()
        ctx = HookContext(event=HookEvent.PRE_BASH, command="rm -rf /")
        result = manager.run(HookEvent.PRE_BASH, ctx)
        assert result.allowed is True

    def test_first_deny_wins(self) -> None:
        v1 = MagicMock()
        v1.check.return_value = HookResult(allowed=True, message="")
        v2 = MagicMock()
        v2.check.return_value = HookResult(allowed=False, message="denied by v2")
        v3 = MagicMock()

        manager = HookManager(validators_by_event={HookEvent.PRE_BASH: [v1, v2, v3]})
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="test"),
        )

        assert not result.allowed
        assert "denied by v2" in result.message
        v3.check.assert_not_called()

    def test_all_pass(self) -> None:
        v1 = MagicMock()
        v1.check.return_value = HookResult(allowed=True, message="")
        v2 = MagicMock()
        v2.check.return_value = HookResult(allowed=True, message="")

        manager = HookManager(validators_by_event={HookEvent.PRE_BASH: [v1, v2]})
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH),
        )
        assert result.allowed is True

    def test_unknown_event_allows(self) -> None:
        manager = HookManager(validators_by_event={})
        result = manager.run(
            HookEvent.POST_OUTPUT,
            HookContext(event=HookEvent.POST_OUTPUT),
        )
        assert result.allowed is True

    def test_validator_exception_denies(self) -> None:
        """If a validator raises, run() returns deny (fail-closed)."""
        v = MagicMock()
        v.name = "broken"
        v.check.side_effect = RuntimeError("boom")

        manager = HookManager(validators_by_event={HookEvent.PRE_BASH: [v]})
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="test"),
        )
        assert not result.allowed
        assert "boom" in result.message


class TestHookManagerFromConfig:
    def test_loads_valid_config(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text(
            "version: '4.0.0'\n"
            "hooks:\n"
            "  pre_bash:\n"
            "    - validator: command_tier\n"
            "  post_output:\n"
            "    - validator: content_safety\n"
        )
        manager = HookManager.from_config(config)
        assert HookEvent.PRE_BASH in manager._validators
        assert HookEvent.POST_OUTPUT in manager._validators
        assert len(manager._validators[HookEvent.PRE_BASH]) == 1
        assert len(manager._validators[HookEvent.POST_OUTPUT]) == 1

    def test_loads_multiple_validators_per_event(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text(
            "version: '4.0.0'\n"
            "hooks:\n"
            "  pre_bash:\n"
            "    - validator: command_tier\n"
            "    - validator: edit_safety\n"
        )
        manager = HookManager.from_config(config)
        assert len(manager._validators[HookEvent.PRE_BASH]) == EXPECTED_DUAL_VALIDATORS

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            HookManager.from_config(tmp_path / "nonexistent.yaml")

    def test_raises_on_unknown_validator(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text(
            "version: '4.0.0'\n"
            "hooks:\n"
            "  pre_bash:\n"
            "    - validator: unknown_validator\n"
        )
        with pytest.raises(ValueError, match="Unknown validator"):
            HookManager.from_config(config)

    def test_raises_on_unknown_event(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text(
            "version: '4.0.0'\nhooks:\n  pre_unknown:\n    - validator: command_tier\n"
        )
        with pytest.raises(ValueError, match="Unknown hook event"):
            HookManager.from_config(config)

    def test_raises_on_missing_validator_key(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text(
            "version: '4.0.0'\nhooks:\n  pre_bash:\n    - name: not_a_validator\n"
        )
        with pytest.raises(TypeError, match="missing 'validator' key"):
            HookManager.from_config(config)

    def test_empty_hooks_section(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text("version: '4.0.0'\nhooks: {}\n")
        manager = HookManager.from_config(config)
        assert len(manager._validators) == 0

    def test_raises_on_malformed_yaml(self, tmp_path: Path) -> None:
        config = tmp_path / "hooks.yaml"
        config.write_text(": bad:\nyaml: [unterminated")
        with pytest.raises(yaml.YAMLError):
            HookManager.from_config(config)


class TestHookManagerCreate:
    def test_creates_noop_when_disabled(self, tmp_path: Path) -> None:
        config = MagicMock()
        config.enable_hooks = False

        manager = HookManager.create(config, tmp_path)

        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="rm -rf /"),
        )
        assert result.allowed is True

    def test_creates_from_config_when_enabled(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "ami" / "config"
        hooks_dir.mkdir(parents=True)
        hooks_file = hooks_dir / "hooks.yaml"
        hooks_file.write_text(
            "version: '4.0.0'\nhooks:\n  pre_bash:\n    - validator: command_tier\n"
        )

        config = MagicMock()
        config.enable_hooks = True

        manager = HookManager.create(config, tmp_path)
        assert HookEvent.PRE_BASH in manager._validators

    def test_config_hooks_file_overrides_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """hooks.file from automation.yaml overrides default hooks path."""
        monkeypatch.delenv("AMI_HOOKS_FILE", raising=False)

        # Custom hooks.yaml with ONLY post_output (no pre_bash)
        custom_dir = tmp_path / "my-custom"
        custom_dir.mkdir()
        custom_file = custom_dir / "my-hooks.yaml"
        custom_file.write_text(
            "version: '3.0.0'\n"
            "hooks:\n"
            "  post_output:\n"
            "    - validator: content_safety\n"
        )

        # Mock get_config to return custom hooks.file path
        mock_cfg = MagicMock()
        mock_cfg.get_value.return_value = "my-custom/my-hooks.yaml"
        monkeypatch.setattr("ami.hooks.manager.get_config", lambda: mock_cfg)

        agent_config = MagicMock()
        agent_config.enable_hooks = True

        manager = HookManager.create(agent_config, tmp_path)

        # Proves it loaded the custom file (only post_output, no pre_bash)
        assert HookEvent.POST_OUTPUT in manager._validators
        assert HookEvent.PRE_BASH not in manager._validators
        mock_cfg.get_value.assert_called_once_with(
            "hooks.file", "ami/config/hooks.yaml"
        )

    def test_env_var_overrides_hooks_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AMI_HOOKS_FILE env var overrides automation.yaml hooks.file."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        custom_file = custom_dir / "hooks.yaml"
        custom_file.write_text(
            "version: '4.0.0'\nhooks:\n  pre_bash:\n    - validator: command_tier\n"
        )
        monkeypatch.setenv("AMI_HOOKS_FILE", str(custom_file))

        config = MagicMock()
        config.enable_hooks = True

        manager = HookManager.create(config, tmp_path)
        assert HookEvent.PRE_BASH in manager._validators

    def test_env_var_relative_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Relative AMI_HOOKS_FILE is resolved against project_root."""
        hooks_dir = tmp_path / "custom"
        hooks_dir.mkdir()
        hooks_file = hooks_dir / "hooks.yaml"
        hooks_file.write_text(
            "version: '4.0.0'\n"
            "hooks:\n"
            "  post_output:\n"
            "    - validator: content_safety\n"
        )
        monkeypatch.setenv("AMI_HOOKS_FILE", "custom/hooks.yaml")

        config = MagicMock()
        config.enable_hooks = True

        manager = HookManager.create(config, tmp_path)
        assert HookEvent.POST_OUTPUT in manager._validators
