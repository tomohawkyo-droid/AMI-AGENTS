# AMI Agents Framework

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-orange.svg)](https://docs.astral.sh/ruff/)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)

**Version**: 0.2.0
**Package**: `ami-agents`

Production-ready orchestration system for autonomous AI agents with multi-provider support, interactive TUI, enterprise security guards, and comprehensive shell integration.

---

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd agents
make install

# Start interactive session (default)
ami-agent
# or simply
@

# Send a direct message
@ "List all Python files in current directory"
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider AI** | Unified abstraction over Claude, Gemini, and Qwen CLIs |
| **Interactive TUI** | Full-featured text editor with streaming output |
| **Security Guards** | Command validation, sensitive file protection, policy engine |
| **Enterprise Backup** | Google Drive integration with Zstandard compression |
| **Shell Extensions** | 16 discoverable `ami-*` commands with metadata |
| **Bootstrap System** | Portable installation for 24+ development tools |
| **Multi-Architecture** | CPU, CUDA, ROCm, Intel XPU, MPS acceleration |
| **Session Management** | UUID-based conversation continuity |
| **Audit Logging** | Full transcript trail for compliance |
| **CI/CD Integration** | Pre-commit hooks, coverage verification |

---

## Architecture

```
agents/
├── ami/
│   ├── cli/                    # CLI providers and mode handlers
│   │   ├── main.py             # Entry point (3 modes)
│   │   ├── claude_cli.py       # Claude Code provider
│   │   ├── gemini_cli.py       # Gemini CLI provider
│   │   ├── qwen_cli.py         # Qwen Code provider
│   │   └── factory.py          # Provider factory
│   ├── cli_components/         # TUI components
│   │   ├── text_editor.py      # Multi-line editor
│   │   ├── stream_renderer.py  # Streaming output
│   │   └── dialogs.py          # Confirmation dialogs
│   ├── core/                   # Core orchestration
│   │   ├── bootloader_agent.py # ReAct loop implementation
│   │   ├── guards.py           # Security validation
│   │   └── policies/           # YAML-based policy engine
│   └── scripts/                # Operational scripts
│       ├── bin/                # Core extension binaries
│       ├── bootstrap/          # Low-level tool bootstrappers
│       ├── backup/             # Google Drive backup system
│       ├── shell/              # Shell integration scripts
│       └── utils/              # Security and system utilities
├── res/config/                 # Shared configurations
├── tests/                      # Unit, integration, e2e tests
└── Makefile                    # Build targets
```

---

## Installation

### Prerequisites

- Python 3.11 (exact version required)
- [uv](https://github.com/astral-sh/uv) package manager
- Node.js 18+ (for AI CLI agents)

### Standard Installation (CPU)

```bash
make install
```

This will:
1. Install Python package with CPU PyTorch
2. Set up configuration files
3. Register shell extensions in `~/.bashrc`
4. Install safety scripts (git hooks, podman wrappers)
5. Launch interactive bootstrap component installer
6. Install shell environment

### Hardware-Accelerated Variants

| Hardware | Command | Notes |
|----------|---------|-------|
| CPU (Generic) | `make install-cpu` | Default for all platforms |
| NVIDIA GPU | `make install-cuda` | CUDA 12.1+ required |
| AMD GPU | `make install-rocm` | ROCm 6.4+ required |
| Apple Silicon | `make install-mps` | Metal Performance Shaders |
| Intel GPU | `make install-intel-xpu` | Intel XPU extensions |

### Development Setup

```bash
make dev              # Full install + pre-commit hooks
make install-hooks    # Install pre-commit and pre-push hooks only
```

### Node.js Agents

```bash
make install-node-agents   # Install Claude, Gemini, Qwen CLIs
```

### Bootstrap Components

```bash
make install-bootstrap   # Interactive TUI to select tools
```

Available bootstrap scripts (24 tools):
- **Core Dependencies**: uv, python, git, git-xet (HuggingFace)
- **AI Assistants**: claude-code, gemini-cli, qwen-code
- **Development**: go, rust, sd, ansible
- **Containers**: podman, kubernetes (kubectl, helm)
- **Security**: openssl, openssh, openvpn, cloudflared
- **Document**: pandoc, texlive, pdfjam, wkhtmltopdf
- **Communication**: matrix-commander, synadm
- **Mobile**: adb

---

## Operational Modes

AMI Agent supports three operational modes:

### Interactive Editor Mode (Default)

```bash
ami-agent
# or simply
@
```

Opens a full-featured text editor with the following controls:

| Key | Action |
|-----|--------|
| **Enter** | Send message to agent |
| **Alt+Enter** / **Ctrl+Enter** | Insert newline |
| **Ctrl+C** (with content) | Clear editor |
| **Ctrl+C** (empty, twice) | Exit |
| **F1** | Toggle help |

The agent maintains session state across turns for multi-turn conversations.

### Query Mode

```bash
@ "What is the current git branch?"
```

- Single-shot execution via the `@` alias
- Streaming output with timer
- No session persistence
- Ideal for scripting and automation

### Print Mode

```bash
./ami-agent --print path/to/instruction.txt < input.txt
```

- Reads instruction from file
- Accepts stdin for additional context
- Full worker agent capabilities (hooks, all tools)
- Designed for pipeline integration

---

## Security System

AMI implements defense-in-depth security:

### Command Guard

Commands are validated against YAML-defined patterns before execution:

```yaml
# ami/config/policies/default.yaml
deny_patterns:
  - pattern: "rm -rf /"
    message: "Recursive root deletion blocked"
  - pattern: "curl.*\\|.*bash"
    message: "Piped curl-to-bash blocked"
```

### Sensitive File Guard

Edits to security-sensitive files are blocked:

```yaml
# ami/config/patterns/sensitive_files.yaml
- pattern: "\\.env"
  description: "Environment secrets"
- pattern: "credentials\\.json"
  description: "Service account keys"
```

### Confirmation Guard

All shell commands require interactive user confirmation before execution on the host system.

### Policy Engine

Centralized policy management:

```python
from ami.core.policies.engine import get_policy_engine

engine = get_policy_engine()
patterns = engine.load_bash_patterns("default")
```

---

## Extension System

Extensions provide discoverable `ami-*` shell commands.

### Available Extensions

| Command | Category | Description |
|---------|----------|-------------|
| `ami-agent` | Core | AMI Orchestrator main entry point |
| `ami` | Core | Unified CLI for services and system management |
| `ami-run` | Core | Universal project execution wrapper |
| `ami-repo` | Core | Git repository and server management |
| `ami-pwd` | Core | AMI root directory finder |
| `ami-transcripts` | Core | Transcript session management and search |
| `ami-mail` | Enterprise | Enterprise mail operations CLI |
| `ami-chat` | Enterprise | Matrix CLI chat (matrix-commander) |
| `ami-admin` | Enterprise | Matrix Server Admin CLI (synadm) |
| `ami-browser` | Enterprise | Browser automation (Playwright) |
| `ami-backup` | Development | Backup to Google Drive |
| `ami-restore` | Development | Restore from Google Drive |
| `ami-check-storage` | Development | Storage validation and monitoring |
| `ami-claude` | Agents | Claude Code AI assistant |
| `ami-gemini` | Agents | Gemini CLI AI assistant |
| `ami-qwen` | Agents | Qwen Code AI assistant |

### Extension Metadata

Each extension contains self-describing metadata:

```bash
#!/usr/bin/env bash
# @name: ami-claude
# @description: Claude Code AI assistant
# @category: agents
# @binary: .venv/node_modules/.bin/claude
# @features: -p, --continue, --resume, --allowedTools
```

### Registering Extensions

```bash
make register-extensions   # Updates ~/.bashrc
source ~/.bashrc           # Activate
```

---

## Backup System

Enterprise-grade backup with Google Drive integration.

### Setup Authentication

```bash
ami-backup --setup-auth   # Interactive flow via gcloud
```

### Create Backup

```bash
ami-backup                           # Default backup (cwd)
ami-backup --keep-local              # Keep local archive
ami-backup --name my-backup          # Custom filename
ami-backup /path/to/data             # Backup specific directory
```

### Restore Backup

```bash
ami-restore --interactive            # Interactive selector
ami-restore --list-revisions         # List available backups
ami-restore --file-id <id>           # Restore specific ID
ami-restore --revision 1             # Go back 1 revision (~1)
ami-restore --latest-local           # Restore from local storage
```

### Features

- Zstandard compression for efficient storage
- Exclusion patterns for sensitive files
- Secondary backup to mounted drives (AMI-BACKUP)
- Automatic credential refresh on token expiry

---

## Configuration

### Configuration Files

| File | Purpose |
|------|---------|
| `ami/config/automation.yaml` | Agent behavior settings |
| `ami/config/extensions.yaml` | Shell extension registry |
| `ami/config/policies/manifest.yaml` | Policy file locations |
| `ami/config/patterns/*.yaml` | Security patterns |

### Environment Variables

```bash
# Provider selection (claude, gemini, qwen)
AMI_AGENT_PROVIDER=claude

# Worker provider (for task execution)
AMI_AGENT_WORKER_PROVIDER=claude

# Model override
AMI_AGENT_MODEL=claude-sonnet-4-5

# Project root (auto-detected)
AMI_ROOT=/path/to/agents
```

### Provider Configuration

Edit `ami/config/automation.yaml`:

```yaml
agent:
  provider: qwen
  worker:
    provider: claude
    model: claude-sonnet-4-5
  timeout: 300
```

---

## Development

### Setup

```bash
make dev                # Full development setup
make install-hooks      # Pre-commit + pre-push hooks
```

### Code Quality

```bash
make lint               # Run ruff linter + formatter
make type-check         # Run mypy
make test               # Run pytest
make check              # All checks (lint + type-check + test)
make pre-commit         # Run all pre-commit hooks
make dead-code          # Run AST-based dead code analysis
```

### Maintenance

```bash
make update             # Update all dependencies via uv
make clean              # Remove build artifacts and __pycache__
make uninstall          # Remove ami-agents from environment
make uninstall-shell    # Remove AMI shell environment from ~/.bashrc
```

### Pre-commit Hooks

- `ruff-format` - Code formatting
- `ruff` - Linting with auto-fix
- `mypy` - Type checking
- `check-banned-words` - Security word list
- `check-file-length` - Max 512 lines
- `check-init-files` - Empty `__init__.py` enforcement
- `verify-coverage` - Unit >90%, Integration >75% (pre-push)

### Testing

```bash
pytest                              # All tests
pytest tests/unit/                  # Unit tests only
pytest tests/integration/           # Integration tests
pytest tests/e2e/                   # End-to-end tests
pytest --cov=ami --cov-report=html  # Coverage report
```

### Project Conventions

- Maximum file length: 512 lines
- All `__init__.py` files must be empty
- No co-authored commits (human authorship required)
- Type hints required for all functions

---

## API Reference

### Core Classes

```python
# Agent Factory
from ami.core.factory import AgentFactory
agent = AgentFactory.create_bootloader()
response, session_id = agent.run("List files")

# CLI Factory
from ami.cli.factory import get_agent_cli
from ami.core.interfaces import RunPrintParams
cli = get_agent_cli()
output, metadata = cli.run_print(params=RunPrintParams(instruction="Hello"))

# Policy Engine
from ami.core.policies.engine import get_policy_engine
engine = get_policy_engine()
patterns = engine.load_bash_patterns()
```

### Provider Interface

All providers implement `AgentCLI`:

```python
class AgentCLI(ABC):
    def run_interactive(
        self, params: RunInteractiveParams | None = None
    ) -> tuple[str, ProviderMetadata | None]

    def run_print(
        self, params: RunPrintParams | None = None
    ) -> tuple[str, ProviderMetadata | None]
```

---

## Troubleshooting

### Extensions not found after installation

```bash
source ~/.bashrc   # Reload shell configuration
```

### Authentication errors with backup

```bash
ami-backup --setup   # Re-authenticate with Google
```

### Provider not responding

```bash
# Check provider CLI is installed
which claude   # or gemini, qwen

# Install if missing
make install-node-agents
```

### Pre-commit hooks failing

```bash
make pre-commit   # See detailed errors
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Ensure all checks pass (`make check`)
4. Commit changes (no co-authored commits)
5. Push to the branch
6. Open a Pull Request

### Commit Guidelines

- Human authorship required (no AI co-authoring in commit message)
- Descriptive commit messages
- One logical change per commit

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Documentation

- [USAGE.md](docs/USAGE.md) - Detailed usage and package integration guide
- [SPEC-HOOKS.md](docs/SPEC-HOOKS.md) - Hook specifications
- [REQUIREMENTS-HOOKS.md](docs/REQUIREMENTS-HOOKS.md) - Pre-commit hook requirements

### Archive

Historical documentation from the v0.2.0 refactoring effort:

- [docs/archive/](docs/archive/) - Audit reports, migration tracking, remediation plans

---

*Maintained by the AMI Orchestrator Team.*
