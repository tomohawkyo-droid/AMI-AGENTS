"""Command tier classification and scope-based action resolution.

Classifies shell commands into security tiers (observe/modify/execute/admin)
and resolves the appropriate action (allow/confirm/deny) from a scope chain.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

import yaml

from ami.core.env import get_project_root
from ami.types.results import SafetyCheckResult

if TYPE_CHECKING:
    from ami.types.common import ScopeOverride


class CommandTier(StrEnum):
    """Security tiers for shell commands, ordered least to most powerful."""

    OBSERVE = "observe"
    MODIFY = "modify"
    EXECUTE = "execute"
    ADMIN = "admin"
    UNCLASSIFIED = "unclassified"


class TierAction(StrEnum):
    """Action to take for a command in a given tier."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


# Ordering for "highest tier wins" classification.
_TIER_RANK = {
    CommandTier.OBSERVE: 0,
    CommandTier.MODIFY: 1,
    CommandTier.EXECUTE: 2,
    CommandTier.ADMIN: 3,
    CommandTier.UNCLASSIFIED: -1,
}

# Tier names in rank order (highest first) for classification loop.
_TIER_RANK_ORDER = (
    CommandTier.ADMIN,
    CommandTier.EXECUTE,
    CommandTier.MODIFY,
    CommandTier.OBSERVE,
)


class TierConfig(NamedTuple):
    """Configuration for a single tier."""

    tier: CommandTier
    default_action: TierAction
    triggers_edit_hooks: bool
    compiled_patterns: list[re.Pattern[str]]


class HardDenyEntry(NamedTuple):
    """A compiled hard deny pattern with its message."""

    compiled: re.Pattern[str]
    message: str


class TierClassifier:
    """Classifies commands into tiers and resolves actions from scope chain.

    Loads configuration from command_tiers.yaml, compiles all regex patterns
    once, and provides fast classification and action resolution.
    """

    def __init__(self, config_path: Path) -> None:
        self._hard_deny: list[HardDenyEntry] = []
        self._tier_configs: dict[CommandTier, TierConfig] = {}
        self._load(config_path)

    def _load(self, config_path: Path) -> None:
        """Load and compile patterns from YAML config."""
        with config_path.open() as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return

        # Compile hard deny patterns
        for entry in data.get("hard_deny", []):
            if isinstance(entry, dict):
                pattern_str = entry.get("pattern", "")
                message = entry.get("message", "Hard deny pattern matched")
                self._hard_deny.append(
                    HardDenyEntry(
                        compiled=re.compile(pattern_str),
                        message=message,
                    )
                )

        # Compile tier patterns
        tiers_section = data.get("tiers", {})
        if not isinstance(tiers_section, dict):
            return

        for tier_name in _TIER_RANK_ORDER:
            tier_data = tiers_section.get(tier_name.value, {})
            if not isinstance(tier_data, dict):
                continue

            action_str = tier_data.get("default_action", "deny")
            try:
                default_action = TierAction(action_str)
            except ValueError:
                default_action = TierAction.DENY

            triggers = bool(tier_data.get("triggers_edit_hooks", False))

            compiled = [
                re.compile(p)
                for p in tier_data.get("patterns", [])
                if isinstance(p, str)
            ]

            self._tier_configs[CommandTier(tier_name)] = TierConfig(
                tier=CommandTier(tier_name),
                default_action=default_action,
                triggers_edit_hooks=triggers,
                compiled_patterns=compiled,
            )

    def check_hard_deny(self, command: str) -> SafetyCheckResult:
        """Check hard deny patterns. Returns (False, msg) if blocked."""
        for entry in self._hard_deny:
            if entry.compiled.search(command):
                return SafetyCheckResult(
                    False,
                    f"SECURITY VIOLATION: {entry.message}"
                    f" (pattern: {entry.compiled.pattern})",
                )
        return SafetyCheckResult(True, "")

    def _classify_single(self, command: str) -> CommandTier:
        """Classify a single command (no pipes) into its highest matching tier."""
        highest = CommandTier.UNCLASSIFIED
        highest_rank = -1

        for tier_name in _TIER_RANK_ORDER:
            config = self._tier_configs.get(tier_name)
            if config is None:
                continue
            rank = _TIER_RANK[tier_name]
            if rank <= highest_rank:
                continue
            for pattern in config.compiled_patterns:
                if pattern.search(command):
                    highest = tier_name
                    highest_rank = rank
                    break

        return highest

    def classify(self, command: str) -> CommandTier:
        """Classify command by highest matching tier.

        Splits by | (pipe), classifies each segment, returns highest.
        """
        segments = command.split("|")
        highest = CommandTier.UNCLASSIFIED
        highest_rank = -1

        for segment in segments:
            tier = self._classify_single(segment.strip())
            rank = _TIER_RANK.get(tier, -1)
            if rank > highest_rank:
                highest = tier
                highest_rank = rank

        return highest

    def get_tier_config(self, tier: CommandTier) -> TierConfig:
        """Get config for a tier. Returns a deny config for unknown tiers."""
        return self._tier_configs.get(
            tier,
            TierConfig(
                tier=tier,
                default_action=TierAction.DENY,
                triggers_edit_hooks=False,
                compiled_patterns=[],
            ),
        )

    def resolve_action(
        self,
        tier: CommandTier,
        scopes: Sequence[ScopeOverride],
    ) -> TierAction:
        """Resolve action from scope chain (most specific first).

        Checks each scope dict for an override of the tier's action.
        Falls back to the tier's default_action.
        """
        tier_key = tier.value
        for scope in scopes:
            # ScopeOverride is a TypedDict; cast to Mapping for dynamic key access
            mapping = cast(Mapping[str, str], scope)
            action_str = mapping.get(tier_key)
            if action_str is not None:
                try:
                    return TierAction(action_str)
                except ValueError:
                    continue
        return self.get_tier_config(tier).default_action


# Singleton container
_classifier_singleton: dict[str, TierClassifier] = {}


def get_tier_classifier() -> TierClassifier:
    """Get the global TierClassifier instance."""
    if "instance" not in _classifier_singleton:
        root = get_project_root()
        config_path = root / "ami/config/policies/command_tiers.yaml"
        _classifier_singleton["instance"] = TierClassifier(config_path)
    return _classifier_singleton["instance"]
