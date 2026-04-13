"""Hook manager that dispatches validation events to configured validators."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import yaml

from ami.core.config import get_config
from ami.hooks.types import HookContext, HookEvent, HookResult
from ami.hooks.validators import (
    CommandTierValidator,
    ContentSafetyValidator,
    EditSafetyValidator,
    PathTraversalValidator,
)

if TYPE_CHECKING:
    from ami.hooks.types import ValidatorProtocol
    from ami.types.config import AgentConfig

# Registry mapping validator name strings (from hooks.yaml) to classes.
_VALIDATOR_REGISTRY: dict[str, type] = {
    "command_tier": CommandTierValidator,
    "edit_safety": EditSafetyValidator,
    "path_traversal": PathTraversalValidator,
    "content_safety": ContentSafetyValidator,
}

_ALLOW = HookResult(allowed=True, message="")


def _parse_event(event_key: str, config_path: Path) -> HookEvent:
    """Parse and validate a hook event key from config."""
    try:
        return HookEvent(event_key)
    except ValueError:
        msg = f"Unknown hook event '{event_key}' in {config_path}"
        raise ValueError(msg) from None


class _ValidatorConfig(TypedDict, total=False):
    """Validator configuration entry."""

    type: str
    config: dict[str, str]


def _parse_validators(
    event_key: str,
    validator_configs: list[_ValidatorConfig],
    config_path: Path,
) -> list[ValidatorProtocol]:
    """Parse and instantiate validators for one event from config."""
    if not isinstance(validator_configs, list):
        msg = f"Validators for '{event_key}' must be a list in {config_path}"
        raise TypeError(msg)

    validators: list[ValidatorProtocol] = []
    for entry in validator_configs:
        if not isinstance(entry, dict):
            msg = f"Validator entry must be a mapping: {entry}"
            raise TypeError(msg)

        validator_name = entry.get("validator")
        if not isinstance(validator_name, str):
            msg = f"Validator entry missing 'validator' key: {entry}"
            raise TypeError(msg)

        validator_cls = _VALIDATOR_REGISTRY.get(validator_name)
        if validator_cls is None:
            msg = (
                f"Unknown validator '{validator_name}' in {config_path}."
                f" Available: {sorted(_VALIDATOR_REGISTRY)}"
            )
            raise ValueError(msg)

        validators.append(validator_cls())

    return validators


class HookManager:
    """Loads hooks.yaml and dispatches HookEvents to registered validators.

    Each event type maps to an ordered list of validators. On dispatch,
    validators run in order; the first denial short-circuits.
    """

    def __init__(
        self,
        validators_by_event: dict[HookEvent, list[ValidatorProtocol]],
    ) -> None:
        self._validators = validators_by_event

    def run(self, event: HookEvent, context: HookContext) -> HookResult:
        """Dispatch event to all registered validators.

        Returns the first deny result, or an allow result if all pass.
        If a validator raises, logs the error and denies (fail-closed).
        """
        validators = self._validators.get(event, [])
        for validator in validators:
            try:
                result = validator.check(context)
            except Exception as exc:
                msg = f"Validator '{validator.name}' raised {type(exc).__name__}: {exc}"
                sys.stderr.write(f"Hook error: {msg}\n")
                return HookResult(allowed=False, message=msg)
            if not result.allowed:
                return result
            if result.needs_confirmation:
                return result
        return _ALLOW

    @classmethod
    def from_config(cls, hooks_config_path: Path) -> HookManager:
        """Create a HookManager from a hooks.yaml file."""
        if not hooks_config_path.exists():
            msg = f"Hooks config not found: {hooks_config_path}"
            raise FileNotFoundError(msg)

        with hooks_config_path.open() as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            msg = f"Hooks config must be a YAML mapping: {hooks_config_path}"
            raise TypeError(msg)

        hooks_section = data.get("hooks", {})
        if not isinstance(hooks_section, dict):
            msg = f"hooks section must be a mapping: {hooks_config_path}"
            raise TypeError(msg)

        validators_by_event: dict[HookEvent, list[ValidatorProtocol]] = {}
        for event_key, validator_configs in hooks_section.items():
            event = _parse_event(event_key, hooks_config_path)
            validators = _parse_validators(
                event_key, validator_configs, hooks_config_path
            )
            validators_by_event[event] = validators

        return cls(validators_by_event=validators_by_event)

    @classmethod
    def noop(cls) -> HookManager:
        """Create a no-op manager that allows everything.

        Used when enable_hooks=False on AgentConfig.
        """
        return cls(validators_by_event={})

    @classmethod
    def create(cls, agent_config: AgentConfig, project_root: Path) -> HookManager:
        """Factory that creates the appropriate HookManager from AgentConfig.

        If enable_hooks is False, returns a noop manager.
        Otherwise, resolves the hooks config path from (in priority order):
          1. ``AMI_HOOKS_FILE`` env var (absolute or relative to project_root)
          2. ``hooks.file`` key in automation.yaml
          3. Default ``ami/config/hooks.yaml``
        """
        if not agent_config.enable_hooks:
            return cls.noop()

        env_override = os.environ.get("AMI_HOOKS_FILE")
        if env_override:
            hooks_path = Path(env_override)
            if not hooks_path.is_absolute():
                hooks_path = project_root / hooks_path
        else:
            config = get_config()
            hooks_file = config.get_value("hooks.file", "ami/config/hooks.yaml")
            hooks_path = project_root / str(hooks_file)

        return cls.from_config(hooks_path)
