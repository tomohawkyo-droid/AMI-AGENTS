# Specification: Hook Validation Pipeline

**Date:** 2026-04-05
**Status:** ACTIVE
**Type:** Specification

## Overview

The hook validation pipeline replaces the original guard system with a configurable, YAML-driven validation architecture. Validators are registered in `hooks.yaml` and dispatched by `HookManager` at key pipeline points.

## Implementation Status

### Phase 1 (v4.0.0): COMPLETE

| Requirement | Status | Implementation |
|---|---|---|
| REQ-HOOK-001: Event interception at pipeline points | DONE | PRE_BASH, PRE_EDIT, POST_OUTPUT events |
| REQ-HOOK-002: YAML-configurable validation rules | DONE | `hooks.yaml` + `manifest.yaml` + policy YAML files |
| REQ-HOOK-004: Pattern-based regex validation | DONE | 4 validators using PolicyEngine patterns |
| REQ-HOOK-006 (partial): ALLOW/DENY/CONFIRM decisions | DONE | `HookResult(allowed, message, needs_confirmation)` |
| REQ-HOOK-007: Replace guards.py mechanisms | DONE | Validators wrap `guards.py` functions |
| REQ-HOOK-009: Maintain security properties | DONE | Fail-closed error handling, tiered command classification |
| REQ-HOOK-011: Reimplement guard functions | DONE | CommandTierValidator, EditSafetyValidator, ContentSafetyValidator, PathTraversalValidator |
| REQ-HOOK-012: Integrate policy loading | DONE | PolicyEngine loads tiers, sensitive files, communication patterns |
| REQ-HOOK-013: Update bootloader agent | DONE | `execute_shell()` dispatches PRE_BASH + PRE_EDIT hooks via `_validate_with_hooks()` |

### Phase 2: NOT IMPLEMENTED

| Requirement | Status | Notes |
|---|---|---|
| REQ-HOOK-003: Load prompts from TXT/MD files | NOT STARTED | For future LLM-based validators |
| REQ-HOOK-005: LLM-based content evaluation | NOT STARTED | Requires prompt loading infrastructure |
| REQ-HOOK-006 (full): MODIFY / REQUEST_FEEDBACK | NOT STARTED | Current system supports ALLOW/DENY/CONFIRM only |
| REQ-HOOK-008: Multi-provider compatibility | IMPLICIT | Hooks run before provider calls, provider-agnostic |
| REQ-HOOK-010: Feedback injection into agent loop | NOT STARTED | Would require HookResult extension |

## Architecture

### Core Components

```
hooks.yaml          HookManager           Validators           guards.py
+-----------+      +-------------+      +----------------+    +-------------+
| pre_bash: |----->| from_config |----->| CommandTier    |--->| (tier       |
|   - tier  |      | run()       |      |   classify     |    |  classifier)|
| pre_edit: |      | noop()      |      | EditSafety     |--->| edit check  |
|   - trav  |      | create()    |      | PathTraversal  |--->| traversal   |
|   - edit  |      +-------------+      | ContentSafety  |--->| comm check  |
| post_out: |                           +----------------+    +-------------+
|   - cont  |
+-----------+
```

### Validator Details

| Validator | Event | What it does |
|-----------|-------|-------------|
| **CommandTierValidator** | PRE_BASH | Classifies commands into 4 tiers (observe/modify/execute/admin). Checks hard deny patterns (22 rules, no override). Resolves action from scope chain. Returns DENY, CONFIRM, or ALLOW. |
| **PathTraversalValidator** | PRE_EDIT | Detects encoded traversal attacks: `../`, `%2e%2e`, `%252e`, null bytes, overlong UTF-8, absolute paths escaping project root. 9 pattern types. |
| **EditSafetyValidator** | PRE_EDIT | Blocks edits to security-sensitive files. Loads patterns from `sensitive_files.yaml`. |
| **ContentSafetyValidator** | POST_OUTPUT | Checks LLM response for prohibited communication patterns from `prohibited_communication_patterns.yaml`. |

### Command Tier System

Commands are classified into 4 security tiers in `command_tiers.yaml`:

| Tier | Default Action | Triggers Edit Hooks | Examples |
|------|---------------|-------------------|---------|
| **observe** | ALLOW | No | ls, cat, grep, git status/log/diff, find, head, tail, wc, stat |
| **modify** | CONFIRM | Yes | touch, mkdir, sed, awk, tee, cp, mv, ln, echo, >, >> |
| **execute** | CONFIRM | No | python, pytest, mypy, make, cargo, uv, curl, wget, ami-* |
| **admin** | DENY | No | rm, sudo, chmod, chown, kill, git push/reset/checkout/commit |

Additionally, 22 **hard deny** patterns block dangerous constructs unconditionally (command chaining, nested shells, dangerous invocations).

Scope overrides from `RunContext` can modify tier actions per-session.

### Event Flow

1. `execute_shell(script)` called in bootloader agent
2. **PRE_BASH**: `CommandTierValidator` classifies the command by tier, checks hard deny patterns, resolves action from scope chain. If DENY, blocks. If CONFIRM, prompts user.
3. If the tier has `triggers_edit_hooks=true` (modify tier), **PRE_EDIT** fires: `PathTraversalValidator` checks for encoded sequences, null bytes, overlong UTF-8, project root escape. Then `EditSafetyValidator` checks for sensitive file modifications.
4. Command executes via `/bin/bash -c` with 300s timeout.
5. **POST_OUTPUT**: `ContentSafetyValidator` checks LLM response for prohibited communication patterns.

### Dispatch Order

```yaml
# hooks.yaml v4.0.0
hooks:
  pre_bash:
    - validator: command_tier         # Tier classification + scope resolution
  pre_edit:
    - validator: path_traversal       # No traversal attacks
    - validator: edit_safety          # No sensitive file edits
  post_output:
    - validator: content_safety       # No prohibited communication
```

First deny short-circuits. If a validator raises an exception, the system denies (fail-closed).

### Data Types

```python
# ami/hooks/types.py
class HookEvent(StrEnum):
    PRE_BASH = "pre_bash"
    PRE_EDIT = "pre_edit"
    POST_OUTPUT = "post_output"

class HookResult(NamedTuple):
    allowed: bool
    message: str
    needs_confirmation: bool = False

class HookContext(NamedTuple):
    event: HookEvent
    command: str = ""
    content: str = ""
    project_root: Path | None = None
    scope_overrides: tuple[ScopeOverride, ...] = ()
```

### Configuration Override Chain

Hook config path resolution (in `HookManager.create()`):
1. `AMI_HOOKS_FILE` env var (absolute or relative to project root)
2. `hooks.file` key in `automation.yaml`
3. Default: `ami/config/hooks.yaml`

## File Map

| File | Purpose |
|---|---|
| `ami/hooks/types.py` | HookEvent, HookResult, HookContext, ValidatorProtocol |
| `ami/hooks/validators.py` | 4 validator classes: CommandTier, EditSafety, PathTraversal, ContentSafety |
| `ami/hooks/manager.py` | HookManager: registry (`_VALIDATOR_REGISTRY`), YAML loading, dispatch |
| `ami/core/guards.py` | Guard functions: check_edit_safety, check_content_safety, check_path_traversal |
| `ami/core/policies/tiers.py` | TierClassifier, CommandTier enum, TierAction enum, scope resolution |
| `ami/core/policies/engine.py` | PolicyEngine: loads patterns from YAML via manifest |
| `ami/config/hooks.yaml` | Validator-to-event mapping (v4.0.0) |
| `ami/config/policies/manifest.yaml` | Maps policy names to pattern file paths (v1.0.0) |
| `ami/config/policies/command_tiers.yaml` | 4 tiers + 22 hard deny rules (v1.0.0) |
| `ami/config/patterns/sensitive_files.yaml` | Sensitive file patterns for EditSafetyValidator |
| `ami/config/patterns/prohibited_communication_patterns.yaml` | Prohibited output patterns for ContentSafetyValidator |

## Adding a New Validator

1. Create a class in `ami/hooks/validators.py` implementing `ValidatorProtocol`:
   - `name` property returning the YAML key
   - `check(context: HookContext) -> HookResult` method
2. Add to `_VALIDATOR_REGISTRY` in `ami/hooks/manager.py`
3. Add to the appropriate event in `ami/config/hooks.yaml`
4. Add tests in `tests/unit/hooks/test_validators.py`
