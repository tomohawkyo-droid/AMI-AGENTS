"""Integration tests for the hook validation pipeline (v4.0.0).

Verifies that HookManager loads real hooks.yaml and dispatches
to validators that use real command_tiers.yaml patterns.
"""

import ami.core.policies.engine
import ami.core.policies.tiers
from ami.core.policies.engine import get_policy_engine
from ami.hooks.manager import HookManager
from ami.hooks.types import HookContext, HookEvent


class TestHookIntegration:
    def setup_method(self) -> None:
        ami.core.policies.engine._singleton.clear()
        ami.core.policies.tiers._classifier_singleton.clear()
        self.engine = get_policy_engine()
        self.hooks_path = self.engine.root / "ami/config/hooks.yaml"

    def test_loads_real_hooks_config(self) -> None:
        manager = HookManager.from_config(self.hooks_path)
        assert HookEvent.PRE_BASH in manager._validators
        assert HookEvent.POST_OUTPUT in manager._validators

    def test_tier_observe_auto_allows(self) -> None:
        """Observe-tier command (ls) is allowed."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="ls -la"),
        )
        assert result.allowed
        assert not result.needs_confirmation

    def test_tier_modify_needs_confirmation(self) -> None:
        """Modify-tier command (echo) needs confirmation."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="echo hello > file.txt"),
        )
        assert result.allowed
        assert result.needs_confirmation

    def test_tier_admin_denied(self) -> None:
        """Admin-tier command (rm) is denied."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="rm -rf /"),
        )
        assert not result.allowed
        assert "SECURITY VIOLATION" in result.message

    def test_pre_bash_blocks_git_push(self) -> None:
        """git push is admin-tier and denied."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="git push origin main"),
        )
        assert not result.allowed

    def test_tier_scope_override_elevates(self) -> None:
        """Scope override can elevate admin from deny to confirm."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(
                event=HookEvent.PRE_BASH,
                command="rm test.txt",
                scope_overrides=({"admin": "confirm"},),
            ),
        )
        assert result.allowed
        assert result.needs_confirmation

    def test_post_output_blocks_prohibited(self) -> None:
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.POST_OUTPUT,
            HookContext(
                event=HookEvent.POST_OUTPUT,
                content="I see the problem here, let me fix it",
            ),
        )
        assert not result.allowed
        assert "COMMUNICATION VIOLATION" in result.message

    def test_post_output_allows_clean(self) -> None:
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.POST_OUTPUT,
            HookContext(
                event=HookEvent.POST_OUTPUT,
                content="Applying the fix to the authentication module.",
            ),
        )
        assert result.allowed

    def test_noop_allows_dangerous_commands(self) -> None:
        manager = HookManager.noop()
        result = manager.run(
            HookEvent.PRE_BASH,
            HookContext(event=HookEvent.PRE_BASH, command="rm -rf /"),
        )
        assert result.allowed

    def test_pre_edit_blocks_traversal(self) -> None:
        """Path traversal blocked at PRE_EDIT."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_EDIT,
            HookContext(
                event=HookEvent.PRE_EDIT,
                command="sed -i 's/a/b/' ../../etc/passwd",
                project_root=self.engine.root,
            ),
        )
        assert not result.allowed
        assert "Path traversal" in result.message

    def test_pre_edit_allows_safe_edit(self) -> None:
        """Safe edit passes PRE_EDIT."""
        manager = HookManager.from_config(self.hooks_path)
        result = manager.run(
            HookEvent.PRE_EDIT,
            HookContext(
                event=HookEvent.PRE_EDIT,
                command="sed -i 's/a/b/' src/main.py",
                project_root=self.engine.root,
            ),
        )
        assert result.allowed
