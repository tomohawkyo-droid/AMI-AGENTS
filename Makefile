# Makefile for AMI Agents

# Default target
.PHONY: help
help: ## Show this help message
	@echo "AMI Agents - Available targets:"
	@echo ""
	@echo "Other Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %%-28s %%s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Main Installation Flow ---

.PHONY: install
install: ## Install AMI Agents in editable mode with all setup
	@echo "🚀 Installing AMI Agents..."
	$(MAKE) sync-package
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-bootstrap
	$(MAKE) install-shell
	@echo "✨ Installation complete!"
	@bash ami/scripts/shell/shell-setup --welcome

.PHONY: install-ci
install-ci: ## Non-interactive install for CI (uses install-defaults.yaml)
	@echo "🚀 Installing AMI Agents (CI mode)..."
	$(MAKE) sync-package
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-bootstrap-ci
	$(MAKE) install-shell
	@echo "✨ Installation complete (CI mode)!"

.PHONY: ensure-ci
ensure-ci: ## Auto-clone AMI-CI if missing
	@if [ ! -f "projects/AMI-CI/lib/checks.sh" ]; then \
		echo "📦 AMI-CI not found — cloning..."; \
		git clone git@github.com:Independent-AI-Labs/AMI-CI.git projects/AMI-CI; \
		echo "✅ AMI-CI cloned to projects/AMI-CI"; \
	fi

.PHONY: sync-package
sync-package: bootstrap-core ensure-ci ## Sync package dependencies via uv
	@echo "🔧 Syncing ami-agents..."
	.boot-linux/bin/uv sync --extra dev
	@echo "✅ Package 'ami-agents' installed with dev dependencies"

# --- Component Targets ---

.PHONY: install-bootstrap
install-bootstrap: ## Interactive TUI to select and install optional bootstrap components
	@.venv/bin/python ami/scripts/bootstrap_installer.py

.PHONY: install-bootstrap-ci
install-bootstrap-ci: ## Non-interactive bootstrap using defaults file
	@.venv/bin/python ami/scripts/bootstrap_installer.py --defaults ami/config/install-defaults.yaml

.PHONY: bootstrap-core
bootstrap-core: ## Bootstrap core tools (uv, python, git, git-lfs/xet) into .boot-linux
	@echo "🔧 Bootstrapping core tools..."
	@bash ami/scripts/bootstrap/bootstrap_uv.sh
	@bash ami/scripts/bootstrap/bootstrap_python.sh
	@bash ami/scripts/bootstrap/bootstrap_git.sh
	@bash ami/scripts/bootstrap/bootstrap_git_xet.sh
	@echo "✅ Core bootstrap complete"

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

.PHONY: sync
sync: sync-package ## Alias for sync-package

# --- Config & Utilities ---

.PHONY: setup-config
setup-config: setup-automation setup-extensions setup-linter-config ## Setup configuration files

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

.PHONY: setup-extensions
setup-extensions: ## Setup extensions configuration
	@echo "⚙️  Setting up extensions configuration..."
	@if [ ! -f "ami/config/extensions.yaml" ]; then \
		if [ -f "ami/config/extensions.template.yaml" ]; then \
			cp "ami/config/extensions.template.yaml" "ami/config/extensions.yaml"; \
			echo "✅ Created ami/config/extensions.yaml from template"; \
		else \
			echo "⚠️  Template ami/config/extensions.template.yaml not found, creating empty config"; \
			echo "extensions: []" > "ami/config/extensions.yaml"; \
		fi \
	else \
		echo "ℹ️  Extensions configuration already exists at ami/config/extensions.yaml"; \
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
install-hooks: ## Install pre-commit and pre-push hooks
	@echo "🔗 Installing pre-commit hooks..."
	.boot-linux/bin/uv run pre-commit install
	.boot-linux/bin/uv run pre-commit install --hook-type pre-push
	@# Inject auto-staging before pre-commit's stash mechanism
	@if [ -f .git/hooks/pre-commit ] && ! grep -q 'Auto-stage' .git/hooks/pre-commit; then \
		sed -i '/^if \[ -x "$$INSTALL_PYTHON" \]/i # Auto-stage all files before pre-commit stashes\ngit add -A\n' .git/hooks/pre-commit; \
		echo "✅ Injected auto-staging into .git/hooks/pre-commit"; \
	fi
	@echo "✅ Pre-commit and pre-push hooks installed"

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

.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks on all files
	@echo "🔍 Running pre-commit hooks on all files..."
	.boot-linux/bin/uv run pre-commit run --all-files

.PHONY: dead-code
dead-code: ## Run AST-based dead code analysis
	.boot-linux/bin/uv run python -m ami.ci.check_dead_code

.PHONY: update
update: ## Update dependencies
	@echo "🔄 Updating dependencies..."
	.boot-linux/bin/uv update

.PHONY: uninstall
uninstall: ## Uninstall ami-agents
	@echo "🗑️  Uninstalling ami-agents..."
	.boot-linux/bin/uv pip uninstall ami-agents -y
