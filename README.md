# AMI Agents Framework

**Version**: 3.0.0
**Package**: `ami`

The **AMI Agents Framework** is a minimal, high-performance orchestration layer for building and running autonomous AI agents. It provides a unified interface for multiple AI providers (Claude, Qwen, Gemini) and a safe runtime for interactive technical tasks.

## 🚀 Key Capabilities

- **Bootloader Agent**: A self-assembling, persistent agent runtime capable of maintaining context across sessions (`BootloaderAgent`).
- **Multi-Provider Support**: Seamlessly switch between **Claude Code**, **Qwen**, and **Gemini** CLIs via a unified abstraction layer.
- **Interactive TUI**: A clean terminal user interface for interactive agent sessions, featuring an inline text editor and real-time stream rendering.
- **Native Security Guards**: Integrated command validation to prevent forbidden operations and ensure compliance with project standards.

## 📂 Architecture

The framework is designed for simplicity and safety, focusing on the core agent loop and provider abstractions.

```text
agents/
├── ami/
│   ├── cli/                # CLI Provider Implementations (Claude, Qwen, Gemini)
│   ├── cli_components/     # TUI widgets (TextEditor, Menus, Dialogs)
│   ├── config/             # Configuration & Prompts
│   └── core/               # Core Logic
│       └── bootloader_agent.py  # The primary agent runtime
├── tests/                  # Unit and Integration tests
└── pyproject.toml          # Package Metadata
```

## 🛠️ Usage

### 1. Interactive Session (Default)
Launch the **Bootloader Agent** in interactive mode. This provides a persistent session where the agent can explore, read files, and execute commands.

```bash
./ami-agent

# Direct invocation
python -m ami.cli.main
```

### 2. Query Mode
Run a single instruction and get a response without entering the interactive editor.

```bash
./ami-agent --query "Check the status of the postgres service"
```

### 3. Print Mode
Run an instruction from a file (e.g., a prompt template).

```bash
./ami-agent --print path/to/instruction.txt
```

## ⚙️ Configuration

Configuration is managed via `ami/config/automation.yaml`.

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `AMI_AGENT_PROVIDER` | Global provider selection (claude, qwen, gemini) | `qwen` |
| `AMI_AGENT_WORKER_PROVIDER` | Provider for worker tasks | `claude` |

## 🛡️ Security & Guards

The framework implements a robust security model for agent execution:

- **Command Guard**: Validates all shell commands against forbidden patterns (e.g., blocking direct `git commit`, requiring use of approved scripts).
- **Confirmation Guard**: Requires user confirmation ('y/n') before executing any shell command on the host.
- **Sensitive File Guard**: Blocks direct modification of security-critical configuration files via shell commands.

## 🧪 Development

The project uses `uv` for dependency management and `pytest` for testing.

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest
```

---
*Maintained by the AMI Orchestrator Team.*
