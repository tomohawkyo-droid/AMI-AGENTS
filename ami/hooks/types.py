"""Hook system type definitions for AMI Agent validation pipeline."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import NamedTuple, Protocol

from ami.types.common import ScopeOverride


class HookEvent(StrEnum):
    """Types of hook events in the validation pipeline."""

    PRE_BASH = "pre_bash"
    POST_OUTPUT = "post_output"
    PRE_EDIT = "pre_edit"


class HookResult(NamedTuple):
    """Result from a hook validation check."""

    allowed: bool
    message: str
    needs_confirmation: bool = False


class HookContext(NamedTuple):
    """Context passed to hook validators.

    Contains all data a validator might need. Validators ignore fields
    they do not use.
    """

    event: HookEvent
    command: str = ""
    content: str = ""
    project_root: Path | None = None
    scope_overrides: tuple[ScopeOverride, ...] = ()


class ValidatorProtocol(Protocol):
    """Protocol that all hook validators must implement."""

    @property
    def name(self) -> str:
        """Unique validator name matching hooks.yaml key."""
        ...

    def check(self, context: HookContext) -> HookResult:
        """Run validation. Return HookResult(allowed=False, ...) to deny."""
        ...
