# AUDIT-BASE.md

## Execution Tracking

- [ ] **Phase 1: Dead Code & Config Cleanup**
    - [ ] Delete `ami/tools/command_executor.py` (Broken/Obsolete).
    - [ ] Purge ghost paths from `ami/config/patterns/banned_words.yaml`.
    - [ ] Purge ghost paths from `ami/config/patterns/code_check.yaml`.
    - [ ] Move `calculate_timeout` to `ami/cli/utils.py`.
    - [ ] Move `validate_path_and_return_code` to `ami/cli/utils.py` (or existing location).
    - [ ] Delete `ami/utils/helpers.py`.

- [ ] **Phase 2: Architectural Fixes**
    - [ ] Move `AgentConfig` to `ami/core/models.py`.
    - [ ] Fix `BootloaderAgent` hardcoded model (use system config).
    - [ ] Update `ami/cli/main.py` environment loading.

- [x] **Phase 3: Component Refactoring**
    - [x] Refactor `ami/cli/streaming.py` (Extract UI logic into `StreamRenderer`).
    - [x] Standardize Process Execution (Using `ProcessExecutor` for internal shell, maintained `process_utils` for CLI streaming as per design).

---

## 1. Dead and Obsolete Code (DELETION REQUIRED)

### 1.1 Broken Tools
*   **`ami/tools/command_executor.py`**: **DEAD**. Imports from `launcher.backend.git.git_server.service_ops` (non-existent). Delete immediately.

### 1.2 Ghost Path References
*   **Config Artifacts**: `ami/config/patterns/banned_words.yaml` and `ami/config/patterns/code_check.yaml` contain dozens of references to legacy monolithic directories (`base/`, `launcher/`, `browser/`, etc.).
    *   **Action**: Purge all non-repo paths.

## 2. Architectural Debt

### 2.1 Circular Layering
*   **Violation**: `ami/core/bootloader_agent.py` (Core) imports from `ami/cli/` (Config/Factory).
*   **Fix**: Move `AgentConfig` to `ami/core/models.py`. Core should define the configuration contract; CLI should implement it.

### 2.2 Redundant Process Execution
*   **Conflict**: `ProcessExecutor` (file-based) vs `ami/cli/process_utils.py` (pipe-based).
*   **Impact**: Inconsistent I/O handling.
*   **Recommendation**: Standardize on `ProcessExecutor` if streaming support can be added, or strictly delineate: CLI=Stream, internal=File.

### 2.3 Streaming Monolith
*   **Violation**: `ami/cli/streaming.py` mixes IO reading, parsing, and UI rendering.
*   **Fix**: Extract UI rendering logic into `ami/cli_components/stream_renderer.py`.

### 2.4 Prompt/Config Duplication
*   **Redundancy**: `ami/config/prompts/patterns_core.txt` manually describes violations that are defined programmatically in `python_fast.yaml`.
*   **Risk**: Desynchronization between what the agent is told to avoid vs. what the hooks actually block.

## 3. Consolidation Points

### 3.1 Utility Unification
*   **`ami/utils/helpers.py`**: A "junk drawer" of duplicates (`calculate_timeout`, `validate_path`).
    *   **Action**: Distribute functions to `ami/cli/utils.py` or `ami/core/logic.py` and delete this file.

### 3.2 Configuration Logic
*   **Hardcoding**: `BootloaderAgent` hardcodes `qwen-coder`.
    *   **Fix**: Ensure `BootloaderAgent` reads the default provider/model from `ami/core/config.py`.

## 4. Missing Patterns

### 4.1 Stream Renderer
*   A dedicated class for handling the real-time TUI output stream would simplify the complex `run_streaming_loop_with_display` function.

### 4.2 Semantic Input Events
*   `TextEditor` processes raw key strings. Moving to an `InputEvent` enum/abstraction would make the editor logic more testable and robust.