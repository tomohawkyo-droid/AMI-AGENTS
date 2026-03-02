"""Unit tests for ami/core/policies/tiers.py."""

from pathlib import Path

import pytest

from ami.core.policies.tiers import (
    CommandTier,
    TierAction,
    TierClassifier,
)

EXPECTED_TIER_COUNT = 4


@pytest.fixture
def classifier(tmp_path: Path) -> TierClassifier:
    """Create a TierClassifier from a minimal command_tiers.yaml."""
    config = tmp_path / "command_tiers.yaml"
    config.write_text(
        "version: '1.0.0'\n"
        "\n"
        "hard_deny:\n"
        "  - pattern: '--no-verify'\n"
        "    message: 'Git hook bypass forbidden'\n"
        "  - pattern: '\\bpython3?\\s+-c\\b'\n"
        "    message: 'Inline python execution forbidden'\n"
        "  - pattern: ';'\n"
        "    message: 'Command chaining with ; forbidden'\n"
        "\n"
        "tiers:\n"
        "  admin:\n"
        "    default_action: deny\n"
        "    triggers_edit_hooks: false\n"
        "    patterns:\n"
        "      - '\\brm\\b'\n"
        "      - '\\bsudo\\b'\n"
        "      - '\\bgit\\s+(push|reset)\\b'\n"
        "\n"
        "  execute:\n"
        "    default_action: confirm\n"
        "    triggers_edit_hooks: false\n"
        "    patterns:\n"
        "      - '\\bpython3?\\b'\n"
        "      - '\\bpytest\\b'\n"
        "      - '\\bmake\\b'\n"
        "\n"
        "  modify:\n"
        "    default_action: confirm\n"
        "    triggers_edit_hooks: true\n"
        "    patterns:\n"
        "      - '\\becho\\b'\n"
        "      - '\\bsed\\b'\n"
        "      - '\\btouch\\b'\n"
        "      - '>>'\n"
        "      - '(?<![>])[>](?![>])'\n"
        "\n"
        "  observe:\n"
        "    default_action: allow\n"
        "    triggers_edit_hooks: false\n"
        "    patterns:\n"
        "      - '\\bls\\b'\n"
        "      - '\\bcat\\b'\n"
        "      - '\\bgrep\\b'\n"
        "      - '\\bgit\\s+(status|log|diff)\\b'\n"
    )
    return TierClassifier(config)


class TestClassify:
    """Tests for TierClassifier.classify method."""

    def test_ls_is_observe(self, classifier: TierClassifier) -> None:
        assert classifier.classify("ls -la") == CommandTier.OBSERVE

    def test_echo_is_modify(self, classifier: TierClassifier) -> None:
        assert classifier.classify("echo hello > file.txt") == CommandTier.MODIFY

    def test_python_is_execute(self, classifier: TierClassifier) -> None:
        assert classifier.classify("python3 script.py") == CommandTier.EXECUTE

    def test_rm_is_admin(self, classifier: TierClassifier) -> None:
        assert classifier.classify("rm -rf /tmp/test") == CommandTier.ADMIN

    def test_unknown_is_unclassified(self, classifier: TierClassifier) -> None:
        assert classifier.classify("foobar_unknown_cmd") == CommandTier.UNCLASSIFIED

    def test_pipe_takes_highest(self, classifier: TierClassifier) -> None:
        """cat file | python3 should classify as execute (highest)."""
        assert classifier.classify("cat file | python3") == CommandTier.EXECUTE

    def test_git_status_is_observe(self, classifier: TierClassifier) -> None:
        assert classifier.classify("git status") == CommandTier.OBSERVE

    def test_git_push_is_admin(self, classifier: TierClassifier) -> None:
        assert classifier.classify("git push origin main") == CommandTier.ADMIN


class TestHardDeny:
    """Tests for TierClassifier.check_hard_deny method."""

    def test_blocks_no_verify(self, classifier: TierClassifier) -> None:
        safe, msg = classifier.check_hard_deny("git commit --no-verify")
        assert not safe
        assert "Git hook bypass forbidden" in msg

    def test_blocks_python_c(self, classifier: TierClassifier) -> None:
        safe, msg = classifier.check_hard_deny("python -c 'import os'")
        assert not safe
        assert "Inline python" in msg

    def test_blocks_semicolon(self, classifier: TierClassifier) -> None:
        safe, msg = classifier.check_hard_deny("ls; rm -rf /")
        assert not safe
        assert "Command chaining" in msg

    def test_allows_safe_command(self, classifier: TierClassifier) -> None:
        safe, msg = classifier.check_hard_deny("ls -la")
        assert safe
        assert msg == ""


class TestResolveAction:
    """Tests for TierClassifier.resolve_action method."""

    def test_default_action_no_scopes(self, classifier: TierClassifier) -> None:
        """No scopes = fall back to default_action."""
        action = classifier.resolve_action(CommandTier.OBSERVE, [])
        assert action == TierAction.ALLOW

        action = classifier.resolve_action(CommandTier.ADMIN, [])
        assert action == TierAction.DENY

    def test_session_override(self, classifier: TierClassifier) -> None:
        """Session scope overrides default."""
        scopes = [{"admin": "confirm"}]
        action = classifier.resolve_action(CommandTier.ADMIN, scopes)
        assert action == TierAction.CONFIRM

    def test_directory_wins_over_session(self, classifier: TierClassifier) -> None:
        """Directory scope (first) beats session scope (second)."""
        dir_scope = {"admin": "allow"}
        session_scope = {"admin": "deny"}
        action = classifier.resolve_action(
            CommandTier.ADMIN, [dir_scope, session_scope]
        )
        assert action == TierAction.ALLOW

    def test_unclassified_denied_by_default(self, classifier: TierClassifier) -> None:
        """Unclassified commands are denied by default."""
        action = classifier.resolve_action(CommandTier.UNCLASSIFIED, [])
        assert action == TierAction.DENY


class TestTriggersEditHooks:
    """Tests for triggers_edit_hooks flag on tier config."""

    def test_modify_triggers_edit_hooks(self, classifier: TierClassifier) -> None:
        config = classifier.get_tier_config(CommandTier.MODIFY)
        assert config.triggers_edit_hooks is True

    def test_observe_no_edit_hooks(self, classifier: TierClassifier) -> None:
        config = classifier.get_tier_config(CommandTier.OBSERVE)
        assert config.triggers_edit_hooks is False

    def test_execute_no_edit_hooks(self, classifier: TierClassifier) -> None:
        config = classifier.get_tier_config(CommandTier.EXECUTE)
        assert config.triggers_edit_hooks is False

    def test_admin_no_edit_hooks(self, classifier: TierClassifier) -> None:
        config = classifier.get_tier_config(CommandTier.ADMIN)
        assert config.triggers_edit_hooks is False
