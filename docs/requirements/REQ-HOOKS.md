# Requirements: Hook Validation Pipeline

**Date:** 2026-03-01
**Updated:** 2026-04-13
**Status:** ACTIVE
**Type:** Requirements
**Spec:** [SPEC-HOOKS](../specifications/SPEC-HOOKS.md)

## Overview

Configurable validation pipeline intercepting agent actions at key points. YAML-driven validators classify commands by security tier, block dangerous operations, and enforce content safety. Phase 1 (pattern-based) is complete. Phase 2 adds LLM-in-the-loop evaluation, action modification, feedback injection, and security loadout profiles.

## 1. Event Interception

- **REQ-HOOK-001**: System shall intercept agent actions at three pipeline points:
  - PRE_BASH: Before executing any shell command
  - PRE_EDIT: Before file-modifying operations (triggered by modify-tier commands)
  - POST_OUTPUT: After receiving LLM response, before presenting to user

## 2. Configuration

- **REQ-HOOK-002**: All validation rules shall be configurable via YAML files without code changes
- **REQ-HOOK-003**: Hook configuration shall support an override chain (env var, config file, default)
- **REQ-HOOK-004**: Policy patterns shall be loaded from a manifest pointing to individual pattern files
- **REQ-HOOK-005**: Validators shall run in declaration order per event; first DENY short-circuits

## 3. Command Tier System

- **REQ-HOOK-010**: Commands shall be classified into four security tiers:
  - **observe** (default: ALLOW, no edit hooks): read-only commands (ls, cat, grep, git status/log/diff, find, stat, wc)
  - **modify** (default: CONFIRM, triggers edit hooks): file-modifying commands (touch, mkdir, sed, awk, tee, cp, mv, echo, >, >>)
  - **execute** (default: CONFIRM, no edit hooks): runtime commands (python, pytest, make, cargo, uv, curl, ami-*)
  - **admin** (default: DENY, no edit hooks): destructive commands (rm, sudo, chmod, kill, git push/reset/checkout/commit)
- **REQ-HOOK-011**: Unclassified commands shall be DENIED (fail-closed)
- **REQ-HOOK-012**: Hard deny patterns shall block unconditionally with no scope override:
  - Command chaining: `&&`, `;`, `||`, background `&`
  - Nested shells: bash, sh, zsh, ksh, csh, dash, node
  - Dangerous invocations: `--no-verify`, inline python (`python -c`, pipe to python), pip (use uv), cd (use absolute paths), `git rm --cached`, dd, shred, wipe
- **REQ-HOOK-013**: Tier definitions and hard deny patterns shall be in a YAML config file, editable without code changes

## 4. Scope Overrides

- **REQ-HOOK-020**: Tier default actions shall be overridable via scope chain (directory -> session -> default)
- **REQ-HOOK-021**: System shall support per-tier action overrides (e.g., allow execute tier for specific agent sessions)
- **REQ-HOOK-022**: Hard deny patterns shall NOT be overridable by any scope

## 5. Decision Types

- **REQ-HOOK-030**: System shall support five decision types:
  - **ALLOW**: Permit the action without prompting
  - **DENY**: Block the action with explanation
  - **CONFIRM**: Prompt user for approval before proceeding
  - **MODIFY**: Alter the command or content before proceeding (Phase 2)
  - **REQUEST_FEEDBACK**: Inject feedback into the agent's next LLM interaction (Phase 2)

## 6. Pattern-Based Validation

- **REQ-HOOK-040**: System shall provide a validator that classifies commands by tier and resolves actions from scope chain
- **REQ-HOOK-041**: System shall provide a validator that detects encoded path traversal attacks (directory traversal, null bytes, overlong UTF-8, UNC paths, project root escape)
- **REQ-HOOK-042**: System shall provide a validator that blocks edits to security-sensitive files (configurable pattern list)
- **REQ-HOOK-043**: System shall provide a validator that checks LLM output against prohibited communication patterns (configurable pattern list)

## 7. LLM-in-the-Loop Validation

- **REQ-HOOK-050**: System shall support LLM-based validation as a validator type, available on any hook event (PRE_BASH, PRE_EDIT, POST_OUTPUT)
- **REQ-HOOK-051**: LLM validators shall load evaluation prompts from external files (TXT/MD) referenced in hook config
- **REQ-HOOK-052**: LLM evaluation shall use the agent's existing CLI backend (claude, qwen, gemini, or OpenCode) — no direct API calls, no SDK imports
- **REQ-HOOK-053**: LLM validator shall receive full context (command, content, event type, project root) as input to the evaluation prompt
- **REQ-HOOK-054**: LLM validator shall return a structured decision (ALLOW/DENY/MODIFY/REQUEST_FEEDBACK) with reasoning
- **REQ-HOOK-055**: LLM evaluation shall have a configurable timeout (default: 30s) with DENY on timeout (fail-closed)
- **REQ-HOOK-056**: LLM validators shall be optional per-hook — pattern validators remain the fast path; LLM is an additional layer
- **REQ-HOOK-057**: LLM validation results shall be logged for audit

## 8. Action Modification

- **REQ-HOOK-060**: When a validator returns MODIFY, the modified command/content shall replace the original before execution
- **REQ-HOOK-061**: Modified commands shall be re-validated through the remaining validators in the chain
- **REQ-HOOK-062**: The user shall be shown the original and modified versions for approval before execution
- **REQ-HOOK-063**: Modification shall be logged with before/after for audit

## 9. Feedback Injection

- **REQ-HOOK-070**: When a validator returns REQUEST_FEEDBACK, the feedback message shall be prepended to the agent's next LLM interaction as system context
- **REQ-HOOK-071**: Feedback shall not block the current action — the action proceeds, but the agent receives guidance for subsequent actions
- **REQ-HOOK-072**: Feedback injection shall support both corrective ("avoid doing X") and instructive ("prefer doing Y") messages
- **REQ-HOOK-073**: Accumulated feedback shall be visible in the agent's context and clearable by the user
- **REQ-HOOK-074**: Feedback shall expire after a configurable number of interactions (default: 5) to prevent context pollution

## 10. Security Loadouts / Profiles

- **REQ-HOOK-080**: System shall support named security profiles (loadouts) that bundle scope overrides, validator sets, and tier action mappings
- **REQ-HOOK-081**: Loadouts shall be defined in YAML (e.g., `ami/config/loadouts/research.yaml`, `development.yaml`, `deployment.yaml`)
- **REQ-HOOK-082**: A loadout shall specify:
  - Which validators are active per event
  - Tier action overrides (e.g., research loadout: execute=ALLOW, admin=DENY)
  - Additional pattern files to load or suppress
  - LLM validator prompt files (if any)
  - Allowed tool list for containerized agents
- **REQ-HOOK-083**: Loadout shall be selectable at agent startup via `--loadout <name>` flag or `AMI_LOADOUT` env var
- **REQ-HOOK-084**: Default loadout (`standard`) shall match current v4.0.0 behavior
- **REQ-HOOK-085**: Loadouts shall be composable — a loadout can extend another (e.g., `deployment` extends `standard` with stricter admin rules)
- **REQ-HOOK-086**: Containerized agents (REQ-AGENT-CONTAINERS) shall have their loadout set at container creation, not changeable at runtime
- **REQ-HOOK-087**: Loadout changes at runtime shall require CONFIRM from user

## 11. Validator Protocol

- **REQ-HOOK-090**: All validators shall implement a common protocol (name + check method returning a result)
- **REQ-HOOK-091**: System shall be fail-closed — if any validator raises an exception, the action is DENIED
- **REQ-HOOK-092**: New validators shall be addable without modifying existing validator code (registry + config)

## 12. Integration

- **REQ-HOOK-100**: Hook validation shall run on every agent shell execution and file edit
- **REQ-HOOK-101**: Hook validation shall be compatible with all agent providers (Claude, Qwen, Gemini)
- **REQ-HOOK-102**: Hooks shall be disablable per-agent via configuration
- **REQ-HOOK-103**: Hook system shall not import or depend on any LLM provider SDK — CLI invocation only

## Constraints

### Technical
- Python 3.11+
- YAML-based configuration
- No LLM SDK dependencies — agents invoked via CLI or OpenCode
- Synchronous validation (no async)

### Security
- Fail-closed on all error paths
- Hard deny patterns not overridable
- Sensitive file patterns not editable by agents
- All hook decisions logged for audit
- No credentials in hook config files

## Dependencies

### Internal
- Agent execution pipeline (shell execution, file editing)
- Guard / policy subsystem
- Agent configuration system

### External
- PyYAML
- CLI agents: claude, qwen, gemini (for LLM-in-the-loop, Phase 2)
- OpenCode (unified CLI for API key-based LLM access, Phase 2)

## Success Criteria

### Phase 1
- Pattern-based validators operational across all hook events
- Command tier classification with 4 tiers + hard deny patterns
- Scope overrides functional
- Fail-closed error handling
- All tests passing

### Phase 2
- LLM validator operational on any hook event via CLI backend
- MODIFY action rewrites commands with user approval
- REQUEST_FEEDBACK injects guidance into next agent interaction
- At least 3 loadout profiles defined (standard, research, deployment)
- Loadout selection at startup and per-container
- All decisions audit-logged
