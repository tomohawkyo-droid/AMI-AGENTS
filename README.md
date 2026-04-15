# AMI Agents Framework

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-orange.svg)](https://docs.astral.sh/ruff/)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)

**Version**: 0.3.0
**Package**: `ami-agents`

Production-ready orchestration system for autonomous AI agents with multi-provider support, interactive TUI, defense-in-depth security, and comprehensive shell integration.

---

## Quick Start

```bash
git clone <repo-url> && cd AMI-AGENTS
sudo make pre-req    # System dependencies (git, openssh, browser libs, etc.)
make install         # Full setup (package, config, extensions, bootstrap, shell)

# Interactive session (default)
ami-agent   # or simply: @

# Single-shot query
@ "List all Python files in current directory"
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider AI** | Unified abstraction over Claude, Gemini, and Qwen CLIs |
| **Interactive TUI** | Full-featured text editor with streaming output |
| **Hook Validation** | Fail-closed pipeline with 4 validators for bash, edit, and output events |
| **Command Tiers** | 4-tier classification (observe/modify/execute/admin) with scope-based actions |
| **Safety Wrappers** | Non-bypassable git-guard and podman-guard replacing binaries in PATH |
| **Policy Engine** | YAML-driven deny patterns, sensitive file protection, path traversal detection |
| **Enterprise Mail** | himalaya fork with batch sending, templates, recipient groups, send-block |
| **Enterprise Backup** | Google Drive integration with Zstandard compression (rsync planned) |
| **Browser Automation** | Playwright with Chromium + Chrome, bootstrapped to `.boot-linux/` |
| **Shell Extensions** | 25 discoverable `ami-*` commands across 6 categories |
| **Bootstrap System** | Portable installation for 26 components into `.boot-linux/` |
| **Makefile Contract** | 10 required targets enforced across all projects |
| **IAM Stack** | Keycloak SSO + OpenBao secrets + NextAuth portal integration |
| **MCP Servers** | Model Context Protocol server integration for providers |
| **Session Management** | UUID-based conversation continuity with transcript search |
| **CI Pipeline** | Native bash git hooks via AMI-CI, framework-agnostic (Python, Rust, Node.js) |
| **Monorepo** | 10+ sub-projects with shared CI infrastructure |

---

## Architecture

```
ami/
  cli/                    # CLI providers and mode handlers
    main.py               # Entry point (3 modes)
    claude_cli.py          # Claude Code provider
    gemini_cli.py          # Gemini CLI provider
    qwen_cli.py            # Qwen Code provider
    factory.py             # Provider factory
  cli_components/          # TUI components (editor, renderer, dialogs)
  core/                    # Core orchestration
    bootloader_agent.py    # ReAct loop implementation
    guards.py              # Security validation functions
    policies/              # YAML-based policy engine and tier classification
  hooks/                   # Validation pipeline
    manager.py             # HookManager (event dispatch, validator registry)
    validators.py          # CommandTier, EditSafety, PathTraversal, ContentSafety
    types.py               # HookEvent, HookResult, HookContext, ValidatorProtocol
  config/                  # Configuration
    hooks.yaml             # Hook-to-validator mapping
    policies/              # Command tiers, deny patterns
    patterns/              # Sensitive files, prohibited communication
    automation.yaml        # Agent behavior and provider settings
  types/                   # Pydantic models (api, config, events, results)
  scripts/
    bin/                   # Core extension binaries (ami-agent, ami-repo, etc.)
    bootstrap/             # 24 tool bootstrappers
    backup/                # Google Drive backup system
    shell/                 # Shell integration scripts
    utils/                 # git-guard, podman-guard, system utilities
docs/
  requirements/            # REQ-* documents (what the system must do)
  specifications/          # SPEC-* documents (how it's built)
  DEPENDENCY-MAP.md        # Visual dependency graphs (5 Mermaid diagrams)
res/config/                # Shared linter configs (ruff, mypy)
tests/                     # Unit, integration, e2e tests
projects/                  # Monorepo sub-projects
Makefile                   # Build targets (10 required per Makefile contract)
```

---

## Monorepo

The `projects/` directory contains sub-projects with shared CI infrastructure.

| Project | Description |
|---------|-------------|
| [**AMI-CI**](https://github.com/Independent-AI-Labs/AMI-CI) | Universal code quality enforcement. Shell + Python architecture enforcing 50+ patterns, native git hook generation, dead code detection, dependency version pinning, Makefile contract (no pre-commit runtime needed) |
| **AMI-PORTAL** | Next.js 16 web workspace with Keycloak OIDC, NextAuth, account management UI (11 API routes), RBAC with 4 roles/8 permissions, tabbed file browsing, DOM automation |
| **AMI-TRADING** | Container-first ML time-series forecasting with 8 transformer architectures, 10 composable data transforms, 6 hardware backends, distributed task orchestration, MLflow tracking, React/Vite dashboard |
| **AMI-DATAOPS** | Data operations toolkit deploying 9 services (PostgreSQL/pgvector, Redis, Dgraph, MongoDB, Prometheus, OpenBao, Keycloak, Vaultwarden, SearXNG) via Ansible + Docker Compose + systemd |
| **AMI-STREAMS** | Communication infrastructure: Synapse homeserver, Element Web, Matrix Auth, LiveKit SFU, Traefik, Cloudflare Tunnel. himalaya fork for enterprise mail (batch, templates, send-block) |
| **AMI-SRP** | Strategic Resource Planning: unified command center for the AMI ecosystem |
| **AMI-BROWSER** | Production Chromium automation with security-first JS execution, anti-detection, isolated profiles, 11 MCP tool families, SearXNG search |
| **RUST-TRADING** | Rust ecosystem: **rust-ta** (zero-copy streaming technical analysis, 20+ indicators, 8-339x over Python); **rust-zk-provider** (autonomous ZK privacy pool for Solana, FROST threshold signing, EU/US compliance); **rust-zk-compliance-api** (12-crate ZK energy compliance platform, 421 tests) |
| **ZK-PORTAL** | Next.js 16 landing page and early-backer portal for ZK Pool Protocol on Solana. KYC via Sumsub, credit card pre-orders, SAFT signing, portfolio dashboard |

---

## Installation

### Prerequisites

```bash
sudo make pre-req    # Checks and installs: git, openssh, openssl, openvpn,
                     # rsync, curl, C compiler, Playwright browser libs
```

- Python 3.11 (exact version required)
- [uv](https://github.com/astral-sh/uv) package manager (bootstrapped automatically)
- Node.js 18+ (for AI CLI agents, installed via uv)

### Standard Installation

```bash
make install          # Full setup (package, config, extensions, bootstrap, shell)
make install-ci       # Non-interactive CI mode (uses install-defaults.yaml)
```

The interactive bootstrap TUI (`make install-bootstrap`) lets you select which components to install. Hardware-accelerated PyTorch variants (CPU, CUDA, ROCm, MPS) are selected here.

---

## Operational Modes

### Interactive Editor (Default)

```bash
ami-agent   # or: @
```

| Key | Action |
|-----|--------|
| **Enter** | Send message |
| **Alt+Enter** / **Ctrl+Enter** | Insert newline |
| **Ctrl+C** (with content) | Clear editor |
| **Ctrl+C** (empty, twice) | Exit |
| **F1** | Toggle help |

Session state persists across turns for multi-turn conversations.

### Query Mode

```bash
@ "What is the current git branch?"
```

Single-shot execution with streaming output. No session persistence.

### Print Mode

```bash
./ami-agent --print path/to/instruction.txt < input.txt
```

Reads instruction from file, accepts stdin context. Full agent capabilities.

---

## Security Architecture

AMI implements defense-in-depth across four layers:

```
Binary Guards (PATH-level) -> Hook Pipeline (runtime) -> Tier System (policy) -> File/Content Guards (data)
```

### Command Tier System

Commands are classified into tiers. Highest matching tier wins. Unclassified commands are **denied** (fail-closed).

| Tier | Scope | Default Action | Examples |
|------|-------|----------------|----------|
| **observe** | Read-only | allow | `ls`, `cat`, `grep`, `git status/log/diff` |
| **modify** | File changes | confirm | `touch`, `mkdir`, `cp`, `mv`, `sed`, `>` |
| **execute** | Run programs | confirm | `python`, `pytest`, `make`, `cargo`, `curl` |
| **admin** | Destructive | deny | `rm`, `sudo`, `chmod`, `git push/reset/commit` |

**21 hard deny patterns** (no override possible): command chaining (`&&`, `;`, `||`), background execution (`&`), inline python (`python -c`, `| python`), `pip` (use `uv`), `cd` (use absolute paths), direct shell invocation (`bash`, `sh`, `node`), disk destruction (`dd`, `shred`), `--no-verify`, `git rm --cached`.

Configuration: `ami/config/policies/command_tiers.yaml`

### Hook Validation Pipeline

The hook system dispatches events through a YAML-configured validator chain. All validators are fail-closed.

| Event | When | Validators |
|-------|------|------------|
| `PRE_BASH` | Before shell command | `command_tier` |
| `PRE_EDIT` | Before file modification | `path_traversal`, `edit_safety` |
| `POST_OUTPUT` | After LLM output | `content_safety` |

Configuration: `ami/config/hooks.yaml`

### Safety Wrappers

**git-guard** replaces the `git` binary in `.boot-linux/bin/` and cannot be bypassed because it IS the git command in PATH. It blocks destructive commands, force push, hook bypass flags, and background `git push`.

**podman-guard** similarly replaces `podman` and blocks bulk deletion, system prune/migrate/reset, and image prune.

---

## CI Pipeline

Each repo manages its own CI via `.pre-commit-config.yaml`. [AMI-CI](https://github.com/Independent-AI-Labs/AMI-CI) provides a shared check library and hook generator that produces **native bash git hooks** (no Python pre-commit runtime needed).

All projects must implement 10 required Makefile targets (enforced by `makefile_contract.mk`): `install`, `install-ci`, `install-hooks`, `sync`, `check`, `lint`, `type-check`, `test`, `clean`, `preflight`.

**Pre-commit (9 checks)**: unstaged changes, ruff format, ruff lint, sensitive files, dependency versions, banned words, file length, init files, mypy

**Commit-msg (2 checks)**: commit message format, block co-authored-by lines

**Pre-push (2 checks)**: co-authored history scan, coverage verification (unit >90%, integration per `coverage_thresholds.yaml`)

---

## Bootstrap System

All external tools are bootstrapped into `.boot-linux/` for complete portability with no system package dependencies. Safety wrappers are installed as the actual binaries in PATH.

```bash
make install-bootstrap    # Interactive TUI to select components
make bootstrap-core       # Core only: uv, python, gcc, git-xet
```

26 components across 9 groups:

| Group | Components |
|-------|-----------|
| **Core** | uv, python, gcc-musl, gcc-glibc (Rust linker), git-xet |
| **AI Agents** | claude-code, gemini-cli, qwen-code |
| **Containers** | podman (with guard), kubernetes (kubectl + helm) |
| **Development** | go, rust, sd, gcloud, github-cli, huggingface-cli |
| **Security** | cloudflared |
| **Documents** | pandoc, texlive, pdfjam, wkhtmltopdf |
| **Browser** | playwright (chromium + chrome) |
| **Communication** | matrix-commander, synadm |
| **Misc** | adb, ansible |

---

## Extensions

25 `ami-*` shell commands across 6 categories:

| Category | Commands |
|----------|----------|
| **Core** | `ami-agent` (`@`), `ami`, `ami-run`, `ami-repo`, `ami-transcripts` |
| **Enterprise** | `ami-mail`, `ami-chat`, `ami-synadm`, `ami-kcadm`, `ami-browser` |
| **Dev** | `ami-backup`, `ami-restore`, `ami-gcloud`, `ami-kubectl`, `ami-cron` |
| **Infra** (hidden) | `ami-ssh`, `ami-vpn`, `ami-tunnel`, `ami-ssl` |
| **Docs** | `ami-docs` |
| **Agents** | `ami-claude`, `ami-gemini`, `ami-qwen` |

```bash
make register-extensions   # Creates symlinks/wrappers in .boot-linux/bin/
source ~/.bashrc           # Activate
```

---

## Configuration

| File | Purpose |
|------|---------|
| `ami/config/automation.yaml` | Agent behavior, provider selection, timeouts |
| `ami/config/hooks.yaml` | Hook-to-validator mapping (v4.0.0) |
| `ami/config/policies/command_tiers.yaml` | Tier classification rules |
| `ami/config/patterns/*.yaml` | Security patterns (sensitive files, communication) |
| `coverage_thresholds.yaml` | Test coverage requirements per suite |

### Environment Variables

```bash
AMI_AGENT_PROVIDER=claude          # Provider selection (claude, gemini, qwen)
AMI_AGENT_WORKER_PROVIDER=claude   # Worker provider for task execution
AMI_AGENT_MODEL=claude-sonnet-4-5  # Model override
AMI_ROOT=/path/to/AMI-AGENTS      # Project root (auto-detected)
PLAYWRIGHT_BROWSERS_PATH=...       # Playwright browser location (auto-set)
```

---

## Development

```bash
make dev              # Full development setup
make install-hooks    # Git hooks only
make sync             # Sync deps + reinstall hooks
```

### Code Quality

```bash
make lint             # ruff linter + formatter
make type-check       # mypy
make test             # pytest
make check            # All checks (lint + type-check + test)
make dead-code        # AST-based dead code analysis
make contract-check   # Verify Makefile contract compliance
```

### Conventions

- Maximum file length: 512 lines
- All `__init__.py` files must be empty
- No co-authored commits
- Type hints required for all functions
- Python 3.11 exact version

---

## Documentation

```
docs/
  requirements/     # REQ-* — what the system must do
  specifications/   # SPEC-* — how it's built
  archive/          # Historical audits
```

Key documents:

| Document | Description |
|----------|-------------|
| [DEPENDENCY-MAP](docs/DEPENDENCY-MAP.md) | Visual dependency graphs (5 Mermaid diagrams) |
| [GUIDE-USAGE](docs/GUIDE-USAGE.md) | Getting started, installation, configuration |
| [ARCH-AGENT-ECOSYSTEM](docs/ARCH-AGENT-ECOSYSTEM.md) | Cross-repo agent architecture |
| [REQ-HOOKS](docs/requirements/REQ-HOOKS.md) | Hook validation pipeline requirements |
| [SPEC-HOOKS](docs/specifications/SPEC-HOOKS.md) | Hook validation pipeline specification |
| [REQ-IAM](docs/requirements/REQ-IAM.md) | IAM requirements (Keycloak + OpenBao) |
| [SPEC-IAM](docs/specifications/SPEC-IAM.md) | IAM specification suite |
| [REQ-EXTENSIONS](docs/requirements/REQ-EXTENSIONS.md) | Extension registry requirements |
| [SPEC-EXTENSIONS](docs/specifications/SPEC-EXTENSIONS.md) | Extension registry specification |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Extensions not found | `source ~/.bashrc` |
| Backup auth errors | `ami-backup --setup-auth` |
| Provider not responding | `which claude` / `make install-bootstrap` |
| Pre-commit failing | Run individual checks: `make lint`, `make type-check` |
| git-guard blocking | Use `/usr/bin/git` directly if intentional |
| Playwright browsers missing | `make install-bootstrap` (select Playwright) |
| Missing system deps | `sudo make pre-req` |

---

## License

MIT License - see [LICENSE](LICENSE) for details.
