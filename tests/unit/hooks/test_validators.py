"""Unit tests for ami/hooks/validators.py."""

from pathlib import Path
from unittest.mock import patch

from ami.core.policies.tiers import CommandTier
from ami.hooks.types import HookContext, HookEvent
from ami.hooks.validators import (
    CommandTierValidator,
    ContentSafetyValidator,
    EditSafetyValidator,
    PathTraversalValidator,
)


class TestCommandTierValidator:
    """Tests for CommandTierValidator."""

    def test_name(self) -> None:
        assert CommandTierValidator().name == "command_tier"

    @patch("ami.hooks.validators.get_tier_classifier")
    def test_allows_observe(self, mock_get_classifier) -> None:
        """Observe-tier commands are allowed without confirmation."""
        mock_cls = mock_get_classifier.return_value
        mock_cls.check_hard_deny.return_value = (True, "")
        mock_cls.classify.return_value = CommandTier.OBSERVE
        mock_cls.resolve_action.return_value = "allow"

        ctx = HookContext(event=HookEvent.PRE_BASH, command="ls -la")
        result = CommandTierValidator().check(ctx)

        assert result.allowed is True
        assert result.needs_confirmation is False

    @patch("ami.hooks.validators.get_tier_classifier")
    def test_confirm_modify(self, mock_get_classifier) -> None:
        """Modify-tier commands need confirmation."""
        mock_cls = mock_get_classifier.return_value
        mock_cls.check_hard_deny.return_value = (True, "")
        mock_cls.classify.return_value = CommandTier.MODIFY
        mock_cls.resolve_action.return_value = "confirm"

        ctx = HookContext(event=HookEvent.PRE_BASH, command="echo hello > file.txt")
        result = CommandTierValidator().check(ctx)

        assert result.allowed is True
        assert result.needs_confirmation is True

    @patch("ami.hooks.validators.get_tier_classifier")
    def test_denies_admin(self, mock_get_classifier) -> None:
        """Admin-tier commands are denied."""
        mock_cls = mock_get_classifier.return_value
        mock_cls.check_hard_deny.return_value = (True, "")
        mock_cls.classify.return_value = CommandTier.ADMIN
        mock_cls.resolve_action.return_value = "deny"

        ctx = HookContext(event=HookEvent.PRE_BASH, command="rm -rf /")
        result = CommandTierValidator().check(ctx)

        assert result.allowed is False
        assert "admin-tier" in result.message

    @patch("ami.hooks.validators.get_tier_classifier")
    def test_hard_deny(self, mock_get_classifier) -> None:
        """Hard deny patterns block before classification."""
        mock_cls = mock_get_classifier.return_value
        mock_cls.check_hard_deny.return_value = (
            False,
            "SECURITY VIOLATION: forbidden",
        )

        ctx = HookContext(event=HookEvent.PRE_BASH, command="git commit --no-verify")
        result = CommandTierValidator().check(ctx)

        assert result.allowed is False
        assert "forbidden" in result.message
        mock_cls.classify.assert_not_called()


class TestEditSafetyValidator:
    def test_name(self) -> None:
        assert EditSafetyValidator().name == "edit_safety"

    @patch("ami.hooks.validators.check_edit_safety")
    def test_allows_safe_edit(self, mock_check) -> None:
        mock_check.return_value = (True, "")
        ctx = HookContext(event=HookEvent.PRE_BASH, command="ls -la")
        result = EditSafetyValidator().check(ctx)
        assert result.allowed is True

    @patch("ami.hooks.validators.check_edit_safety")
    def test_blocks_sensitive_edit(self, mock_check) -> None:
        mock_check.return_value = (False, "SECURITY VIOLATION: sensitive file")
        ctx = HookContext(event=HookEvent.PRE_BASH, command="sed -i 's/a/b/' .env")
        result = EditSafetyValidator().check(ctx)
        assert result.allowed is False
        assert "sensitive file" in result.message


class TestContentSafetyValidator:
    def test_name(self) -> None:
        assert ContentSafetyValidator().name == "content_safety"

    @patch("ami.hooks.validators.check_content_safety")
    def test_allows_clean_content(self, mock_check) -> None:
        mock_check.return_value = (True, "")
        ctx = HookContext(event=HookEvent.POST_OUTPUT, content="Here is the fix.")
        result = ContentSafetyValidator().check(ctx)
        assert result.allowed is True

    @patch("ami.hooks.validators.check_content_safety")
    def test_blocks_prohibited_content(self, mock_check) -> None:
        mock_check.return_value = (
            False,
            "COMMUNICATION VIOLATION: you're right variations",
        )
        ctx = HookContext(
            event=HookEvent.POST_OUTPUT,
            content="you're absolutely correct",
        )
        result = ContentSafetyValidator().check(ctx)
        assert result.allowed is False
        assert "COMMUNICATION VIOLATION" in result.message


class TestPathTraversalValidator:
    def test_name(self) -> None:
        assert PathTraversalValidator().name == "path_traversal"

    @patch("ami.hooks.validators.check_path_traversal")
    def test_allows_safe_command(self, mock_check) -> None:
        mock_check.return_value = (True, "")
        ctx = HookContext(
            event=HookEvent.PRE_EDIT,
            command="sed -i 's/a/b/' src/main.py",
        )
        result = PathTraversalValidator().check(ctx)
        assert result.allowed is True

    @patch("ami.hooks.validators.check_path_traversal")
    def test_blocks_traversal(self, mock_check) -> None:
        mock_check.return_value = (False, "Path traversal detected")
        project = Path("/tmp/test-project")
        ctx = HookContext(
            event=HookEvent.PRE_EDIT,
            command="cat ../../etc/passwd",
            project_root=project,
        )
        result = PathTraversalValidator().check(ctx)
        assert result.allowed is False
        assert "Path traversal" in result.message
        mock_check.assert_called_once_with("cat ../../etc/passwd", project)
