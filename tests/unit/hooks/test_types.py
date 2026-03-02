"""Unit tests for ami/hooks/types.py."""

from pathlib import Path

from ami.hooks.types import HookContext, HookEvent, HookResult


class TestHookEvent:
    def test_values(self) -> None:
        assert HookEvent.PRE_BASH == "pre_bash"
        assert HookEvent.POST_OUTPUT == "post_output"
        assert HookEvent.PRE_EDIT == "pre_edit"

    def test_construction_from_string(self) -> None:
        assert HookEvent("pre_bash") == HookEvent.PRE_BASH
        assert HookEvent("post_output") == HookEvent.POST_OUTPUT


class TestHookResult:
    def test_tuple_unpacking(self) -> None:
        allowed, message, needs_confirmation = HookResult(allowed=True, message="")
        assert allowed is True
        assert message == ""
        assert needs_confirmation is False

    def test_deny_result(self) -> None:
        result = HookResult(allowed=False, message="blocked")
        assert not result.allowed
        assert result.message == "blocked"

    def test_needs_confirmation_default(self) -> None:
        result = HookResult(allowed=True, message="")
        assert result.needs_confirmation is False

    def test_needs_confirmation_set(self) -> None:
        result = HookResult(allowed=True, message="", needs_confirmation=True)
        assert result.needs_confirmation is True


class TestHookContext:
    def test_defaults(self) -> None:
        ctx = HookContext(event=HookEvent.PRE_BASH)
        assert ctx.command == ""
        assert ctx.content == ""
        assert ctx.project_root is None
        assert ctx.scope_overrides == ()

    def test_with_all_fields(self) -> None:
        scope = ({"observe": "allow", "modify": "confirm"},)
        ctx = HookContext(
            event=HookEvent.PRE_BASH,
            command="ls -la",
            content="some output",
            project_root=Path("/tmp/project"),
            scope_overrides=scope,
        )
        assert ctx.event == HookEvent.PRE_BASH
        assert ctx.command == "ls -la"
        assert ctx.content == "some output"
        assert ctx.project_root == Path("/tmp/project")
        assert ctx.scope_overrides == scope
