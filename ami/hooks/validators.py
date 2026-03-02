"""Built-in hook validators for the AMI Agent validation pipeline."""

from __future__ import annotations

from ami.core.guards import (
    check_content_safety,
    check_edit_safety,
    check_path_traversal,
)
from ami.core.policies.tiers import TierAction, get_tier_classifier
from ami.hooks.types import HookContext, HookResult


class CommandTierValidator:
    """Classifies commands by tier and resolves action from scope chain.

    Uses TierClassifier to:
    1. Check hard deny patterns (no override)
    2. Classify command into a tier (observe/modify/execute/admin)
    3. Resolve the action (allow/confirm/deny) from the scope chain
    """

    @property
    def name(self) -> str:
        return "command_tier"

    def check(self, context: HookContext) -> HookResult:
        classifier = get_tier_classifier()

        # 1. Hard deny (no override)
        safe, msg = classifier.check_hard_deny(context.command)
        if not safe:
            return HookResult(allowed=False, message=msg)

        # 2. Classify
        tier = classifier.classify(context.command)

        # 3. Resolve action from scope chain
        action = classifier.resolve_action(tier, list(context.scope_overrides))

        # 4. Return result based on action
        if action == TierAction.DENY:
            return HookResult(
                allowed=False,
                message=f"SECURITY VIOLATION: {tier.value}-tier command denied.",
            )
        if action == TierAction.CONFIRM:
            return HookResult(allowed=True, message="", needs_confirmation=True)
        return HookResult(allowed=True, message="")


class EditSafetyValidator:
    """Validates commands for edits to sensitive files.

    Wraps guards.check_edit_safety which loads sensitive file patterns.
    """

    @property
    def name(self) -> str:
        return "edit_safety"

    def check(self, context: HookContext) -> HookResult:
        is_safe, message = check_edit_safety(context.command)
        return HookResult(allowed=is_safe, message=message)


class ContentSafetyValidator:
    """Validates agent output for prohibited communication patterns.

    Wraps guards.check_content_safety which loads communication patterns.
    """

    @property
    def name(self) -> str:
        return "content_safety"

    def check(self, context: HookContext) -> HookResult:
        is_safe, message = check_content_safety(context.content)
        return HookResult(allowed=is_safe, message=message)


class PathTraversalValidator:
    """Detects path traversal attacks in commands.

    Wraps guards.check_path_traversal with multi-layer defense:
    encoded sequences, null bytes, overlong UTF-8, absolute paths
    escaping the project root.
    """

    @property
    def name(self) -> str:
        return "path_traversal"

    def check(self, context: HookContext) -> HookResult:
        is_safe, message = check_path_traversal(context.command, context.project_root)
        return HookResult(allowed=is_safe, message=message)
