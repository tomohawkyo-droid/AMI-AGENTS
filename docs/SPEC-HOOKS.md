# Specification: Hook Validation Pipeline

## Overview

The hook validation pipeline replaces the original guard system with a configurable, YAML-driven validation architecture. Validators are registered in `hooks.yaml` and dispatched by `HookManager` at key pipeline points.

## Implementation Status

### Phase 1 (v3.0.0): COMPLETE

| Requirement | Status | Implementation |
|---|---|---|
| REQ-HOOK-001: Event interception at pipeline points | DONE | PRE_BASH, PRE_EDIT, POST_OUTPUT events |
| REQ-HOOK-002: YAML-configurable validation rules | DONE | `hooks.yaml` + `manifest.yaml` + policy YAML files |
| REQ-HOOK-004: Pattern-based regex validation | DONE | 5 validators using PolicyEngine patterns |
| REQ-HOOK-006 (partial): ALLOW/DENY decisions | DONE | `HookResult(allowed, message)` |
| REQ-HOOK-007: Replace guards.py mechanisms | DONE | Validators wrap `guards.py` functions |
| REQ-HOOK-009: Maintain security properties | DONE | Fail-closed error handling, hybrid allowlist+deny |
| REQ-HOOK-011: Reimplement guard functions | DONE | CommandSafety, EditSafety, ContentSafety validators |
| REQ-HOOK-012: Integrate policy loading | DONE | PolicyEngine loads deny, allow, sensitive, communication patterns |
| REQ-HOOK-013: Update bootloader agent | DONE | `execute_shell()` dispatches PRE_BASH + PRE_EDIT hooks |

### Phase 2: NOT IMPLEMENTED

| Requirement | Status | Notes |
|---|---|---|
| REQ-HOOK-003: Load prompts from TXT/MD files | NOT STARTED | For future LLM-based validators |
| REQ-HOOK-005: LLM-based content evaluation | NOT STARTED | Requires prompt loading infrastructure |
| REQ-HOOK-006 (full): MODIFY / REQUEST_FEEDBACK | NOT STARTED | Current system only supports ALLOW/DENY |
| REQ-HOOK-008: Multi-provider compatibility | IMPLICIT | Hooks run before provider calls, provider-agnostic |
| REQ-HOOK-010: Feedback injection into agent loop | NOT STARTED | Would require HookResult extension |

## Architecture

### Core Components

```
hooks.yaml          HookManager           Validators           guards.py
+-----------+      +-------------+      +----------------+    +------------+
| pre_bash: |----->| from_config |----->| Allowlist      |--->| allowlist  |
|   - allow |      | run()       |      | CommandSafety  |--->| deny check |
|   - deny  |      | noop()      |      | EditSafety     |--->| sensitive  |
| pre_edit: |      | create()    |      | PathTraversal  |--->| traversal  |
|   - trav  |      +-------------+      | ContentSafety  |--->| comm check |
|   - edit  |                           +----------------+    +------------+
| post_out: |
|   - cont  |
+-----------+
```

### Event Flow

1. `execute_shell(script)` called in bootloader agent
2. **PRE_BASH**: `command_allowlist` checks script against allow patterns (default or interactive). If no match, DENY. Then `command_safety` checks against deny patterns. If match, DENY.
3. If script matches risky edit patterns (sed, echo, cat, awk, >, >>), **PRE_EDIT** fires: `path_traversal` checks for encoded sequences, null bytes, overlong UTF-8, project root escape. Then `edit_safety` checks for sensitive file modifications.
4. Command executes via `/bin/bash -c`.
5. **POST_OUTPUT**: `content_safety` checks LLM response for prohibited communication patterns.

### Dispatch Order

```yaml
# hooks.yaml v3.0.0
hooks:
  pre_bash:
    - validator: command_allowlist    # Must match allow pattern
    - validator: command_safety       # Must not match deny pattern
  pre_edit:
    - validator: path_traversal       # No traversal attacks
    - validator: edit_safety          # No sensitive file edits
  post_output:
    - validator: content_safety       # No prohibited communication
```

First deny short-circuits. If a validator raises an exception, the system denies (fail-closed).

### Configuration Override Chain

Hook config path resolution (in `HookManager.create()`):
1. `AMI_HOOKS_FILE` env var (absolute or relative to project root)
2. `hooks.file` key in `automation.yaml`
3. Default: `ami/config/hooks.yaml`

Allowlist policy selection (in `CommandAllowlistValidator`):
- Inferred from `guard_rules_path`: if filename contains "interactive", uses `interactive_allow.yaml`; otherwise `default_allow.yaml`

## File Map

| File | Purpose |
|---|---|
| `ami/hooks/types.py` | HookEvent, HookResult, HookContext, ValidatorProtocol |
| `ami/hooks/validators.py` | 5 validator classes wrapping guards.py |
| `ami/hooks/manager.py` | HookManager: registry, YAML loading, dispatch |
| `ami/core/guards.py` | Guard functions: allowlist, deny, edit, traversal, content |
| `ami/config/hooks.yaml` | Validator-to-event mapping (v3.0.0) |
| `ami/config/policies/manifest.yaml` | Maps policy names to YAML file paths |
| `ami/config/policies/default.yaml` | 53 deny patterns (default mode) |
| `ami/config/policies/interactive.yaml` | 39 deny patterns (interactive mode) |
| `ami/config/policies/default_allow.yaml` | 40 allow patterns (default mode) |
| `ami/config/policies/interactive_allow.yaml` | 44 allow patterns (interactive mode) |

## Adding a New Validator

1. Create a class in `ami/hooks/validators.py` implementing `ValidatorProtocol`:
   - `name` property returning the YAML key
   - `check(context: HookContext) -> HookResult` method
2. Add to `_VALIDATOR_REGISTRY` in `ami/hooks/manager.py`
3. Add to the appropriate event in `ami/config/hooks.yaml`
4. Add tests in `tests/unit/hooks/test_validators.py`
