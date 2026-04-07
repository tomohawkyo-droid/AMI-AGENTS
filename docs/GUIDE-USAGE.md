# Guide: Getting Started with AMI-AGENTS

**Date:** 2026-04-05
**Status:** ACTIVE
**Type:** Guide

## Installation

```bash
# Clone and install
git clone <repo-url> AMI-AGENTS && cd AMI-AGENTS
make install

# Development mode (includes AMI-CI tooling)
uv pip install -e ".[dev]"
```

The `make install` flow runs: `sync-package` -> `setup-config` -> `register-extensions` -> `install-bootstrap` (TUI selector) -> `install-shell`.

## Bootstrap System

Tools are installed to `.boot-linux/bin/` without requiring `sudo`. The TUI installer (`make install-bootstrap`) lets you select components:

- **Core:** uv, Python, git, git-lfs/xet
- **AI Agents:** Claude, Gemini, Qwen (versions from `scripts/package.json`)
- **Development:** gh, sd, pandoc, wkhtmltopdf
- **Security:** OpenSSL, OpenVPN
- **Containers:** Podman

## Extensions

CLI extensions are registered in `ami/config/extensions.yaml` (gitignored; template at `extensions.template.yaml`). Categories: core, enterprise, dev, infra, docs, agents.

Run `ami-welcome` to see the banner with all available extensions.

## Shared Configurations

Code quality configs live in `res/config/` and are accessed via:

```python
from ami.config_utils import get_config_path

ruff_config = get_config_path("ruff.toml")
```

## CI/CD Scripts

Pre-commit hooks run automatically. Key checks:
- `check_banned_words.py` — prohibited patterns (bare `tuple[]`, `.parent.parent`, etc.)
- `check_dependency_versions.py` — dependency validation
- `check_init_files.py` — ensures `__init__.py` files don't contain logic
- `block_coauthored.py` — prevents co-authored commit lines
- `verify_coverage.py` — enforces test coverage thresholds

Run all checks manually: `make check`

## Key Configuration Files

| File | Purpose |
|------|---------|
| `ami/config/extensions.yaml` | CLI extension registry (gitignored) |
| `ami/config/extensions.template.yaml` | Extension registry template (tracked) |
| `ami/config/automation.yaml` | Agent CLI settings, logging, hooks |
| `ami/config/hooks.yaml` | Hook validation pipeline (v4.0.0) |
| `ami/config/policies/command_tiers.yaml` | Command access tiers |
| `ami/config/policies/manifest.yaml` | Policy manifest |
| `ami/config/patterns/` | Pattern matching configs |

## Documentation

See [docs/README.md](README.md) for a full index of all documentation.
