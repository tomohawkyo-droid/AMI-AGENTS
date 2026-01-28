# Makefile for AMI Agents

# Default target
.PHONY: help
help: ## Show this help message
	@echo "AMI Agents - Available targets:"
	@echo ""
	@echo "Vendor Architecture Targets:"
	@echo "  install-cpu                    Install with CPU PyTorch (default)"
	@echo "  install-cpu-linux-x86_64       Install with CPU PyTorch for Linux x86_64"
	@echo "  install-cpu-macos-arm64        Install with CPU PyTorch for macOS ARM64 (Apple Silicon)"
	@echo "  install-cpu-macos-x86_64       Install with CPU PyTorch for macOS x86_64 (Intel - deprecated)"
	@echo "  install-cuda                   Install with CUDA PyTorch (NVIDIA)"
	@echo "  install-mps                    Install with MPS PyTorch (Apple Silicon)"
	@echo "  install-rocm                   Install with ROCm PyTorch (AMD)"
	@echo "  install-intel-xpu              Install with Intel XPU PyTorch"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Install targets
.PHONY: install
install: ## Install AMI Agents in editable mode with all setup (CPU version)
	@echo "🚀 Installing AMI Agents (CPU version)..."
	$(MAKE) install-package
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	$(MAKE) install-bootstrap
	$(MAKE) install-shell
	@echo "✨ Installation complete!"
	@echo "   Run 'source ~/.bashrc' to activate shell environment."
	@echo "   Then use 'ami-*' commands or './ami-agent' to start."

.PHONY: install-bootstrap
install-bootstrap: ## Interactive TUI to select and install optional bootstrap components
	@python3 ami/scripts/bootstrap_installer.py

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
	@bash -c 'source ami/scripts/setup/node.sh && install_node_agents'
	@echo "✅ Node.js CLI agents installed"

.PHONY: install-cuda
install-cuda: ## Install AMI Agents with CUDA support
	@echo "🚀 Installing AMI Agents (CUDA version)..."
	$(MAKE) install-package-cuda
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "✨ Installation complete with CUDA support. Run './ami-agent' to start."

.PHONY: install-rocm
install-rocm: ## Install AMI Agents with ROCm support (AMD)
	@echo "🚀 Installing AMI Agents (ROCm version)..."
	$(MAKE) install-package-rocm
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "✨ Installation complete with ROCm support. Run './ami-agent' to start."

.PHONY: install-intel-xpu
install-intel-xpu: ## Install AMI Agents with Intel XPU support
	@echo "🚀 Installing AMI Agents (Intel XPU version)..."
	$(MAKE) install-package-intel-xpu
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "✨ Installation complete with Intel XPU support. Run './ami-agent' to start."

.PHONY: install-cpu
install-cpu: install ## Install AMI Agents with CPU support (alias for install)

.PHONY: install-cpu-linux-x86_64
install-cpu-linux-x86_64: ## Install AMI Agents with CPU support for Linux x86_64
	@echo "🚀 Installing AMI Agents (CPU Linux x86_64 version)..."
	$(MAKE) install-package
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "✨ Installation complete with CPU Linux x86_64 support. Run './ami-agent' to start."

.PHONY: install-cpu-macos-arm64
install-cpu-macos-arm64: ## Install AMI Agents with CPU support for macOS ARM64 (Apple Silicon)
	@echo "🚀 Installing AMI Agents (CPU macOS ARM64 version)..."
	$(MAKE) install-package
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "✨ Installation complete with CPU macOS ARM64 support. Run './ami-agent' to start."

.PHONY: install-cpu-macos-x86_64
install-cpu-macos-x86_64: ## Install AMI Agents with CPU support for macOS x86_64 (Intel - deprecated after PyTorch 2.2.0)
	@echo "🚀 Installing AMI Agents (CPU macOS x86_64 version)..."
	$(MAKE) install-package
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "⚠️  Note: macOS x86_64 builds are deprecated after PyTorch 2.2.0"
	@echo "✨ Installation complete with CPU macOS x86_64 support. Run './ami-agent' to start."

.PHONY: install-mps
install-mps: ## Install AMI Agents with MPS support (Apple Silicon)
	@echo "🚀 Installing AMI Agents (MPS version)..."
	$(MAKE) install-package-mps
	$(MAKE) setup-config
	$(MAKE) register-extensions
	$(MAKE) install-safety-scripts
	@echo "✨ Installation complete with MPS support. Run './ami-agent' to start."

.PHONY: sync
sync: ## Sync dependencies using uv
	@echo "📦 Syncing dependencies..."
	uv sync

.PHONY: install-package
install-package: ## Install package in editable mode with CPU PyTorch (default)
	@echo "🔧 Installing ami-agents with CPU PyTorch..."
	uv sync --extra torch-cpu --extra dev
	@echo "✅ Package 'ami-agents' installed with CPU PyTorch and dev dependencies"

.PHONY: install-package-cuda
install-package-cuda: ## Install package in editable mode with CUDA PyTorch
	@echo "🔧 Installing ami-agents with CUDA PyTorch..."
	uv sync --extra torch-cuda --extra dev
	@echo "✅ Package 'ami-agents' installed with CUDA PyTorch and dev dependencies"

.PHONY: install-package-rocm
install-package-rocm: ## Install package in editable mode with ROCm PyTorch
	@echo "🔧 Installing ami-agents with ROCm PyTorch..."
	uv sync --extra torch-rocm --extra dev
	@echo "✅ Package 'ami-agents' installed with ROCm PyTorch and dev dependencies"

.PHONY: install-package-intel-xpu
install-package-intel-xpu: ## Install package in editable mode with Intel XPU PyTorch
	@echo "🔧 Installing ami-agents with Intel XPU PyTorch..."
	uv sync --extra torch-intel-xpu --extra dev
	@echo "✅ Package 'ami-agents' installed with Intel XPU PyTorch and dev dependencies"

.PHONY: install-package-mps
install-package-mps: ## Install package in editable mode with MPS PyTorch
	@echo "🔧 Installing ami-agents with MPS PyTorch..."
	uv sync --extra torch-mps --extra dev
	@echo "✅ Package 'ami-agents' installed with MPS PyTorch and dev dependencies"

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
	@python3 ami/scripts/register_extensions.py

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
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@# Inject auto-staging before pre-commit's stash mechanism (prevents rollback conflicts)
	@if [ -f .git/hooks/pre-commit ] && ! grep -q 'git add -A' .git/hooks/pre-commit; then \
		sed -i '/^if \[ -x "\$$INSTALL_PYTHON" \]/i # Auto-stage all files before pre-commit stashes\ngit add -A\n' .git/hooks/pre-commit; \
		echo "✅ Injected auto-staging into .git/hooks/pre-commit"; \
	fi
	@echo "✅ Pre-commit and pre-push hooks installed (with auto-staging)"

.PHONY: install-safety-scripts
install-safety-scripts: ## Install git and podman safety scripts
	@echo "🔒 Installing safety scripts..."
	@bash ami/scripts/utils/disable_no_verify_patcher.sh
	@bash ami/scripts/utils/podman_safety_wrapper.sh
	@echo "✅ Safety scripts installed"

.PHONY: test
test: ## Run tests
	@echo "🧪 Running tests..."
	pytest

.PHONY: lint
lint: ## Run linters
	@echo "🔍 Running linters..."
	ruff check .
	ruff format .

.PHONY: type-check
type-check: ## Run type checker
	@echo "📝 Running type checker..."
	mypy .

.PHONY: check
check: lint type-check test ## Run all checks (lint, type-check, test)

.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks on all files
	@echo "🔍 Running pre-commit hooks on all files..."
	uv run pre-commit run --all-files

.PHONY: dead-code
dead-code: ## Run AST-based dead code analysis
	uv run python ami/scripts/ci/check_dead_code.py

.PHONY: update
update: ## Update dependencies
	@echo "🔄 Updating dependencies..."
	uv update

.PHONY: uninstall
uninstall: ## Uninstall ami-agents
	@echo "🗑️  Uninstalling ami-agents..."
	uv pip uninstall ami-agents -y