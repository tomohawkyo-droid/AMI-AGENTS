# Technical Audit & Architectural Debt Report

## 1. Architectural Entanglement (Circular Dependency)
The separation of concerns between `ami.core` (logic/models) and `ami.cli` (interface/execution) is compromised by circular dependencies and inverted control.
*   **The Cycle:** `ami.core.bootloader_agent` imports `ami.cli.factory`, which in turn depends on `ami.core.config` and `ami.core.models`.
*   **Inverted Control:** The Core domain logic (`BootloaderAgent`) directly instantiates and drives the Interface layer (`CLIProvider`), tightly coupling business rules with specific execution implementations.

## 2. Configuration Bypass in `BootloaderAgent`
Critical agent parameters are hardcoded in the implementation, overriding the sophisticated configuration system intended to manage them.
*   **Violation:** `ami/core/bootloader_agent.py` explicitly hardcodes `model="qwen-coder"` and `provider=ProviderType.QWEN`.
*   **Impact:** This renders global settings in `automation.yaml` (like `AMI_AGENT_PROVIDER`) ineffective for the bootloader, creating hidden behaviors that contradict the configuration state.

## 3. "Not Invented Here" TUI Implementation
The project maintains a custom, from-scratch implementation of a terminal text editor and window manager using raw ANSI escape codes.
*   **Components:** `ami/cli_components/text_editor.py`, `cursor_manager.py`, `text_input_utils.py`.
*   **The Debt:** The codebase manually handles low-level terminal operations:
    *   Complex cursor navigation (`UP`, `DOWN`, `CTRL_LEFT`) and text buffer manipulation.
    *   Raw `termios`/`tty` input parsing and bracketed paste mode handling.
    *   Screen clearing and redrawing logic.
*   **Risk:** This introduces significant maintenance overhead and brittleness across different terminal emulators and operating systems, prone to rendering artifacts and "off-by-one" errors that standard inputs wouldn't suffer from.

## 4. Fragmented Streaming Logic
The control flow for executing commands and streaming LLM output is scattered across four distinct layers, making debugging and tracing nearly impossible.
*   **Dispersion:**
    1.  `ami/cli/process_utils.py`: Low-level subprocess management.
    2.  `ami/cli/streaming.py`: Main loop and timeout logic.
    3.  `ami/cli/base_provider.py`: Injection of parsing callbacks.
    4.  `ami/cli_components/stream_renderer.py`: Visual presentation.
*   **Complexity:** The architecture relies on passing callbacks deep into the execution stack to invert control back to the provider, creating a "spaghetti" call stack.

## 5. Configuration & Pattern Sprawl
The configuration architecture is fragmented across multiple file formats and directory structures, lacking a unified schema.
*   **Fragmentation:**
    *   Policies: `ami/config/policies/`
    *   Patterns: `ami/config/patterns/`
    *   Core Config: `ami/config/automation.yaml`
    *   Hardcoded Loaders: `ami/core/logic.py` contains specific `lru_cache` loaders for individual files.
*   **Maintenance:** Adding or modifying a rule requires synchronized changes across YAML definition files and their specific Python loaders.

## 6. Runtime Path Manipulation (`sys.path`)
The project relies on runtime `sys.path` patching to resolve modules, rather than standard Python packaging.
*   **Evidence:** `ami/config/patterns/code_check.yaml` exempts files like `scripts/run_tests.py` and `agents/ami/agent_main.py` specifically to allow "dual sys.path setup".
*   **Impact:** This breaks standard import resolution, making the codebase difficult to test or install as a standard package without the specific directory structure and bootstrap scripts.

## 7. Cryptographic Primitive Re-implementation
The project implements its own UUIDv7 generator in `ami/utils/uuid_utils.py`.
*   **Debt:** Maintaining custom implementations of cryptographic or unique identifier standards (RFC 9562) within project code increases the surface area for bugs and collision risks compared to using standard library features or established dependencies.

## 8. Disk-Bound Process Isolation
`ami/utils/process.py` forces all subprocess output through temporary files on disk.
*   **Mechanism:** Uses `tempfile.TemporaryFile` for `stdout` and `stderr` instead of memory pipes.
*   **Performance:** While robust against buffer deadlocks, this forces disk I/O for every single shell command. For an agentic workflow executing hundreds of commands (e.g., `ls`, `grep`), this introduces unnecessary latency and disk wear.

---

# Proposed Remediation Plan

## Solution 1: Dependency Injection for Core/CLI Decoupling
*   **Goal:** Break the circular dependency between `core` and `cli` layers.
*   **Action:**
    *   Define a generic `AgentRuntime` interface in `ami.core.interfaces`.
    *   Update `BootloaderAgent` to accept an `AgentRuntime` instance in its constructor (Dependency Injection) rather than instantiating `get_agent_cli` directly.
    *   Move the `factory.py` logic to a higher-level `ami.setup` or `ami.main` module that wires the Core agent with the CLI implementation at application startup.

## Solution 2: Config-Driven Bootloader
*   **Goal:** Restore the authority of `automation.yaml`.
*   **Action:**
    *   Update `BootloaderAgent` to initialize `AgentConfig` using `get_config().get("agent.provider")` and `get("agent.worker.model")`.
    *   Remove hardcoded `"qwen"` strings.
    *   Implement a fallback mechanism: Config -> Defaults -> Hardcoded safety net.

## Solution 3: TUI Hardening & Encapsulation
*   **Goal:** Stabilize the custom TUI without introducing heavy external dependencies.
*   **Action:**
    *   **Encapsulate ANSI:** Create a dedicated `AnsiTerminal` class that abstracts all raw escape codes (colors, cursor movement, clearing).
    *   **Isolate Logic:** Separate the "Editor Buffer" logic (pure data manipulation) from the "Renderer" logic (I/O). This allows unit testing the editor state without a real terminal.
    *   **Input Normalization:** Centralize `termios` handling into a `KeyboardInput` service that produces standardized events (e.g., `Event(KEY_UP)`), decoupling the application logic from raw byte sequences.

## Solution 4: Unified Streaming Pipeline
*   **Goal:** Simplify the execution flow into a linear pipeline.
*   **Action:**
    *   Create a `StreamProcessor` class that owns the lifecycle of a command execution.
    *   Implement the **Observer Pattern**: The provider registers an `on_chunk(text)` handler.
    *   Refactor `execute_streaming` to yield standardized `StreamEvent` objects rather than invoking callbacks, allowing the caller (Agent) to decide how to render or parse them.

## Solution 5: Unified Policy Engine
*   **Goal:** Centralize rule management.
*   **Action:**
    *   Create a `PolicyEngine` service.
    *   Define a single `manifest.yaml` that lists all policy files and their types (Bash, Python, Sensitive).
    *   Replace individual `lru_cache` loaders in `logic.py` with a generic loader that reads the manifest and hydrates the policy engine at startup.

## Solution 6: Standard Package Architecture
*   **Goal:** Eliminate `sys.path` hacks.
*   **Action:**
    *   Add a `pyproject.toml` `[project.scripts]` entry point for the agent (e.g., `ami-agent = ami.cli.main:main`).
    *   Install the package in "editable" mode (`pip install -e .`) in the development environment.
    *   Refactor scripts to import `ami` as a standard package, removing all manual `sys.path.insert` code.

## Solution 7: UUID Verification
*   **Goal:** Ensure identifier uniqueness and correctness.
*   **Action:**
    *   Add a comprehensive test suite for `ami/utils/uuid_utils.py` verifying it against the RFC 9562 spec vectors (if available) or standard properties (sorting, uniqueness, version bits).
    *   *Alternative:* If project constraints allow, replace with the lightweight `uuid6` library which supports v7.

## Solution 8: Memory-Based I/O with Selectors
*   **Goal:** Improve performance and reduce disk wear.
*   **Action:**
    *   Replace `tempfile.TemporaryFile` with `subprocess.PIPE`.
    *   Implement a `selectors` (or `asyncio`) loop in `ProcessExecutor` to read from `stdout` and `stderr` pipes concurrently into memory buffers.
    *   This eliminates the deadlock risk (by draining pipes actively) without hitting the disk.