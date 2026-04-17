# Makefile for AMI Agents
SHELL := /bin/bash

# Contract compliance
-include projects/AMI-CI/lib/makefile_contract.mk

# Default target
.PHONY: help
help: ## Show this help message
	@echo "AMI Agents - Available targets:"
	@echo ""
	@echo "Other Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %%-28s %%s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Preflight ---

.PHONY: preflight
preflight: pre-req-check ## Verify environment and pre-requisites

# --- Pre-requisites Check ---

.PHONY: pre-req-check
pre-req-check: ## Check system pre-requisites (runs automatically on install)
	@bash ami/scripts/pre-req.sh

.PHONY: pre-req
pre-req: ## Install system pre-requisites (requires sudo)
	@bash ami/scripts/pre-req.sh --install

# --- Main Installation Flow ---

INSTALL_LOG := install-$(shell date +%Y%m%d-%H%M%S).log

.PHONY: install
install: ## Install AMI Agents in editable mode with all setup
	@exec > >(tee -a "$(INSTALL_LOG)") 2>&1; \
	echo "🚀 Installing AMI Agents..."; \
	echo "📝 Log: $(INSTALL_LOG)"; \
	$(MAKE) pre-req-check && \
	$(MAKE) sync-package && \
	$(MAKE) setup-config && \
	$(MAKE) register-extensions && \
	$(MAKE) install-bootstrap && \
	$(MAKE) install-git-guard && \
	$(MAKE) install-hooks && \
	$(MAKE) install-shell && \
	echo "✨ Installation complete!" && \
	bash ami/scripts/shell/shell-setup --welcome

.PHONY: install-ci
install-ci: ## Non-interactive install for CI (uses install-defaults.yaml)
	@exec > >(tee -a "$(INSTALL_LOG)") 2>&1; \
	echo "🚀 Installing AMI Agents (CI mode)..."; \
	echo "📝 Log: $(INSTALL_LOG)"; \
	$(MAKE) pre-req-check && \
	$(MAKE) sync-package && \
	$(MAKE) setup-config && \
	$(MAKE) register-extensions && \
	$(MAKE) install-bootstrap-ci && \
	$(MAKE) install-git-guard && \
	$(MAKE) install-hooks && \
	$(MAKE) install-shell && \
	echo "✨ Installation complete (CI mode)!"

.PHONY: ensure-ci
ensure-ci: ## Clone AMI-CI if missing, pull latest if present
	@if [ ! -f "projects/AMI-CI/lib/checks.sh" ]; then \
		echo "📦 AMI-CI not found — cloning..."; \
		git clone git@github.com:Independent-AI-Labs/AMI-CI.git projects/AMI-CI; \
		echo "✅ AMI-CI cloned to projects/AMI-CI"; \
	else \
		echo "🔄 Pulling latest AMI-CI..."; \
		cd projects/AMI-CI && git pull --ff-only 2>/dev/null || echo "⚠️  AMI-CI pull failed (offline or dirty)"; \
	fi

.PHONY: ensure-dataops
ensure-dataops: ## Clone AMI-DATAOPS if missing, pull latest if present
	@if [ ! -f "projects/AMI-DATAOPS/pyproject.toml" ]; then \
		echo "📦 AMI-DATAOPS not found — cloning..."; \
		git clone git@github.com:Independent-AI-Labs/AMI-DATAOPS.git projects/AMI-DATAOPS; \
		echo "✅ AMI-DATAOPS cloned to projects/AMI-DATAOPS"; \
	else \
		echo "🔄 Pulling latest AMI-DATAOPS..."; \
		cd projects/AMI-DATAOPS && git pull --ff-only 2>/dev/null || echo "⚠️  AMI-DATAOPS pull failed (offline or dirty)"; \
	fi

.PHONY: sync-package
sync-package: bootstrap-core ensure-ci ensure-dataops ## Sync package dependencies via uv
	@echo "🔧 Syncing ami-agents..."
	.boot-linux/bin/uv sync --extra dev
	@if [ -f "projects/AMI-DATAOPS/pyproject.toml" ]; then \
		echo "🔧 Installing ami-dataops (editable)..."; \
		.boot-linux/bin/uv pip install -e projects/AMI-DATAOPS; \
	fi
	@echo "✅ Package 'ami-agents' installed with dev dependencies"

# --- Component Targets ---

.PHONY: install-bootstrap
install-bootstrap: ## Interactive TUI to select and install optional bootstrap components
	@.venv/bin/python ami/scripts/bootstrap_installer.py

.PHONY: install-bootstrap-ci
install-bootstrap-ci: ## Non-interactive bootstrap using defaults file
	@.venv/bin/python ami/scripts/bootstrap_installer.py --defaults ami/config/install-defaults.yaml

.PHONY: bootstrap-core
bootstrap-core: ## Bootstrap core tools (uv, python, git-lfs/xet) into .boot-linux
	@echo "🔧 Bootstrapping core tools..."
	@bash ami/scripts/bootstrap/bootstrap_uv.sh
	@bash ami/scripts/bootstrap/bootstrap_python.sh
	@bash ami/scripts/bootstrap/bootstrap_git_xet.sh
	@echo "✅ Core bootstrap complete"

.PHONY: install-git-guard
install-git-guard: ## Install git safety wrapper to .boot-linux/bin/git
	@mkdir -p .boot-linux/bin
	@if command -v git &> /dev/null; then \
		SYSTEM_GIT=$$(command -v git); \
		echo "🔒 Installing git-guard (system git: $$SYSTEM_GIT)"; \
		cp ami/scripts/utils/git-guard .boot-linux/bin/git; \
		chmod +x .boot-linux/bin/git; \
		echo "✅ Git safety wrapper installed"; \
	else \
		echo "⚠️  System git not found — skipping git-guard installation"; \
		echo "    Run: sudo make pre-req"; \
	fi

.PHONY: install-shell
install-shell: ## Install AMI shell environment to ~/.bashrc
	@echo "🐚 Installing shell environment..."
	@bash ami/scripts/shell/shell-setup --install
	@echo "✅ Shell environment installed"

.PHONY: uninstall-shell
uninstall-shell: ## Remove AMI shell environment from ~/.bashrc
	@bash ami/scripts/shell/shell-setup --uninstall

.PHONY: install-node-agents
install-node-agents: ## Install Node.js CLI agents (claude, gemini, qwen)
	@echo "📦 Installing Node.js CLI agents..."
	@bash ami/scripts/bootstrap/bootstrap_agents.sh
	@echo "✅ Node.js CLI agents installed"

.PHONY: update-node-agents
update-node-agents: ## Update Node.js CLI agents to latest versions and reinstall
	@echo "🔍 Checking for CLI updates..."
	@uv run ami/tools/update_cli_versions.py --auto-update --force
	@$(MAKE) install-node-agents

.PHONY: sync
sync: sync-package install-hooks ## Sync deps + reinstall hooks

# --- Config & Utilities ---

.PHONY: setup-config
setup-config: setup-automation setup-linter-config ## Setup configuration files

.PHONY: setup-linter-config
setup-linter-config: ## Create symlinks for linter configs in project root
	@echo "🔗 Setting up linter configuration symlinks..."
	@if [ -f "res/config/ruff.toml" ] && [ ! -e "ruff.toml" ]; then \
		ln -s res/config/ruff.toml ruff.toml; \
		echo "✅ Created ruff.toml symlink"; \
	elif [ -e "ruff.toml" ]; then \
		echo "ℹ️  ruff.toml already exists"; \
	else \
		echo "⚠️  res/config/ruff.toml not found"; \
	fi
	@if [ -f "res/config/mypy.toml" ] && [ ! -e "mypy.toml" ]; then \
		ln -s res/config/mypy.toml mypy.toml; \
		echo "✅ Created mypy.toml symlink"; \
	elif [ -e "mypy.toml" ]; then \
		echo "ℹ️  mypy.toml already exists"; \
	elif [ -f "res/config/mypy.toml" ]; then \
		echo "ℹ️  mypy config exists in res/config/mypy.toml"; \
	fi

.PHONY: setup-automation
setup-automation: ## Setup automation configuration
	@echo "⚙️  Setting up automation configuration..."
	@if [ ! -f "ami/config/automation.yaml" ]; then \
		if [ -f "ami/config/automation.template.yaml" ]; then \
			cp "ami/config/automation.template.yaml" "ami/config/automation.yaml"; \
			echo "✅ Created ami/config/automation.yaml from template"; \
		else \
			echo "⚠️  Template ami/config/automation.template.yaml not found"; \
		fi \
	else \
		echo "ℹ️  Automation configuration already exists at ami/config/automation.yaml"; \
	fi

.PHONY: register-extensions
register-extensions: ## Register extensions in .bashrc
	@echo "🔌 Registering extensions in ~/.bashrc..."
	@.venv/bin/python ami/scripts/register_extensions.py

.PHONY: clean
clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: dev
dev: install install-hooks ## Install for development with code quality tools and hooks

.PHONY: install-hooks
install-hooks: ensure-ci ## Install native git hooks (no pre-commit dependency)
	@bash projects/AMI-CI/scripts/cleanup-precommit 2>/dev/null || true
	bash projects/AMI-CI/scripts/generate-hooks

# --- Quality & Test ---

.PHONY: test
test: ## Run tests
	@echo "🧪 Running tests..."
	pytest

.PHONY: lint
lint: ## Run linters
	@echo "🔍 Running linters..."
	uv run ruff check --config res/config/ruff.toml .
	uv run ruff format --config res/config/ruff.toml --check .

.PHONY: type-check
type-check: ## Run type checker
	@echo "📝 Running type checker..."
	mypy .

.PHONY: check
check: lint type-check test ## Run all checks (lint, type-check, test)

.PHONY: check-hooks
check-hooks: ensure-ci ## Preview generated hooks (dry-run)
	bash projects/AMI-CI/scripts/generate-hooks --dry-run

.PHONY: cleanup-precommit
cleanup-precommit: ## Remove pre-commit package and cache
	bash projects/AMI-CI/scripts/cleanup-precommit

.PHONY: dead-code
dead-code: ## Run AST-based dead code analysis
	.boot-linux/bin/uv run python -m ami.ci.check_dead_code

.PHONY: update
update: ## Interactive update of all repos (SYSTEM then APPS)
	@bash ami/scripts/bin/ami-update

.PHONY: update-ci
update-ci: ## Non-interactive update (uses update-defaults.yaml)
	@bash ami/scripts/bin/ami-update --ci --defaults ami/config/update-defaults.yaml

.PHONY: update-deps
update-deps: ## Update Python dependencies only
	@echo "🔄 Updating Python dependencies..."
	.boot-linux/bin/uv update

.PHONY: uninstall
uninstall: ## Uninstall ami-agents
	@echo "🗑️  Uninstalling ami-agents..."
	.boot-linux/bin/uv pip uninstall ami-agents -y
