# Architectural Audit and Remediation — Q1 2026

**Date:** 2026-02-01
**Status:** DEPRECATED
**Type:** Audit

This document consolidates the Q1 2026 architectural debt audit cycle: problem identification, remediation planning, execution tracking, and final report. Retained as historical reference.

---

## 1. Technical Debt Audit

Eight architectural issues were identified:

### 1.1 Circular Dependency (Core/CLI)
`ami.core.bootloader_agent` imported from `ami.cli.factory`, creating a cycle. Core drove the Interface layer directly.

### 1.2 Configuration Bypass in BootloaderAgent
Hardcoded `model="qwen-coder"` and `provider=ProviderType.QWEN`, overriding `automation.yaml` settings.

### 1.3 Custom TUI Implementation
From-scratch terminal editor using raw ANSI escape codes (`text_editor.py`, `cursor_manager.py`, `text_input_utils.py`). Manual `termios`/`tty` handling, cursor navigation, screen management.

### 1.4 Fragmented Streaming Logic
Execution and LLM output streaming scattered across 4 layers: `process_utils.py`, `streaming.py`, `base_provider.py`, `stream_renderer.py`. Callback-based spaghetti.

### 1.5 Configuration Sprawl
Config fragmented across `policies/`, `patterns/`, `automation.yaml`, and hardcoded `lru_cache` loaders in `logic.py`.

### 1.6 Runtime `sys.path` Manipulation
Scripts relied on `sys.path.insert` hacks instead of standard Python packaging.

### 1.7 Custom UUIDv7 Implementation
`ami/utils/uuid_utils.py` rolled its own RFC 9562 UUIDv7 generator instead of using `uuid6` library.

### 1.8 Disk-Bound Process I/O
`ami/utils/process.py` forced all subprocess output through `tempfile.TemporaryFile` instead of memory pipes.

---

## 2. Remediation Plan

For each issue, the following approach was taken:

1. **Circular dependency** — Dependency Injection: `AgentRuntimeProtocol` in `ami.core.interfaces`, `BootloaderAgent` accepts runtime via constructor, wiring moved to `mode_handlers.py`.
2. **Config bypass** — Config-driven: BootloaderAgent reads from `automation.yaml` via `get_config()`.
3. **TUI** — Encapsulation: `AnsiTerminal` abstraction layer, separated editor buffer from renderer.
4. **Streaming** — `StreamProcessor` class with Observer pattern (`RendererObserver`), linear pipeline replacing callbacks.
5. **Config sprawl** — `PolicyEngine` with central `manifest.yaml`.
6. **sys.path** — Switched to `uv pip install -e .`, removed path hacking within `ami/` package.
7. **UUIDv7** — Added verification test suite against RFC 9562 properties.
8. **Process I/O** — Rewrote `ProcessExecutor` to use `subprocess.PIPE` with `selectors` event loop.

---

## 3. Execution Tracking

| Phase | Status |
|-------|--------|
| Phase 1: Dead code and config cleanup | Partially complete (ghost paths in patterns remain) |
| Phase 2: Architectural fixes | Complete |
| Phase 3: Component refactoring | Complete |

Unchecked items from Phase 1:
- Delete `ami/tools/command_executor.py` (if still exists)
- Purge ghost paths from `banned_words.yaml` and `code_check.yaml`
- Move utility functions from `helpers.py` to proper locations

---

## 4. Final Report

**Overall completion:** ~95%

### Completed
1. Unified streaming pipeline — `StreamProcessor` + `RendererObserver`, eliminated 200+ lines of fragmented logic
2. Optimized process I/O — memory pipes + `selectors` event loop
3. Circular dependency resolution — `AgentRuntimeProtocol` + `AgentFactory`
4. Config-driven authority — hardcoded strings removed from BootloaderAgent
5. TUI hardening — `AnsiTerminal` abstraction
6. Unified policy engine — `PolicyEngine` + `manifest.yaml`
7. UUID correctness — bit-shifting fix + verification tests
8. Test suite overhaul — obsolete tests removed, 100+ tests passing

### Remaining
- External scripts (`scripts/run_tests.py` etc.) still contain `sys.path` hacks
- Phase 1 dead code cleanup partially incomplete
