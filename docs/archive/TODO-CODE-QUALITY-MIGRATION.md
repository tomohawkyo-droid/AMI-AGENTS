# TODO: Code Quality Migration from AMI-TRADING to AMI-AGENTS

## Overview
This document outlines the code quality configurations and scripts that need to be migrated from the AMI-TRADING project to the AMI-AGENTS project to establish a reusable code quality framework.

## Code Quality Configurations to Migrate

### 1. Ruff Configuration
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/ruff.toml`
- **Purpose**: Python linting and formatting rules
- **Migration**: Copy and potentially merge with existing ruff configuration

### 2. MyPy Configuration
- **Source**: Embedded in `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/pyproject.base.toml` under `[tool.mypy]` section
- **Purpose**: Static type checking configuration
- **Migration**: Extract to standalone mypy configuration file and reference in pyproject.toml

### 3. PyTest Configuration
- **Source**: Embedded in `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/pyproject.base.toml` under `[tool.pytest.ini_options]` section
- **Purpose**: Test runner configuration
- **Migration**: Extract to standalone pytest configuration file

### 4. Pre-commit Hooks
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/.pre-commit-config.yaml`
- **Note**: Both projects seem to have similar pre-commit configurations already
- **Action**: Compare and reconcile differences between the two configurations

## Scripts to Migrate

### 1. Dependency Version Checker
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/scripts/ci/check_dependency_versions.py`
- **Purpose**: Ensures dependency versions match between different configuration files
- **Migration**: Move to agents project and update paths

### 2. Banned Words Checker
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/scripts/ci/check_banned_words.py`
- **Purpose**: Prevents banned words/patterns from entering the codebase
- **Migration**: Move to agents project and update patterns

### 3. Init Files Checker
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/scripts/ci/check_init_files.py`
- **Purpose**: Ensures __init__.py files don't contain business logic
- **Migration**: Move to agents project

### 4. Co-authored Commit Blocker
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/scripts/ci/block_coauthored.py`
- **Purpose**: Prevents co-authored commits
- **Migration**: Move to agents project

### 5. Coverage Verification Script
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/scripts/ci/verify_coverage.py`
- **Purpose**: Verifies test coverage thresholds
- **Migration**: Move to agents project and update coverage thresholds if needed

## PyProject Generation Code to Migrate

### 1. Base PyProject Template
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/pyproject.base.toml`
- **Purpose**: Base configuration with dependencies and tool settings
- **Migration**: Adapt to be more generic and reusable across projects

### 2. Vendor Dependency Injection System
- **Source**: Related to `VENDOR_DEPENDENCIES_PLACEHOLDER` in pyproject.base.toml and files in `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/vendor/`
- **Purpose**: Dynamically injects vendor-specific dependencies
- **Migration**: Create a reusable system for injecting dependencies based on environment/target

### 3. Configuration Generation Scripts
- **Source**: Likely scripts in `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/scripts/` that generate or manipulate configuration files
- **Purpose**: Automate configuration management
- **Migration**: Make these scripts project-agnostic and reusable

## Vendor-Specific Configurations to Migrate

### 1. CUDA Sources Configuration
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/vendor/sources-cuda.toml`

### 2. CPU Linux Sources Configuration
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/vendor/sources-cpu-linux.toml`

### 3. CPU macOS Sources Configuration
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/vendor/sources-cpu-macos.toml`

### 4. MPS Sources Configuration
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/vendor/sources-mps.toml`

### 5. ROCm Sources Configuration
- **Source**: `/home/ami/Projects/AMI-ORCHESTRATOR/agents/projects/AMI-TRADING/res/config/vendor/sources-rocm.toml`

## Implementation Plan

### Phase 1: Extract and Generalize
1. Extract all code quality configurations from AMI-TRADING
2. Generalize configurations to be project-agnostic
3. Create a shared code quality package/module in AMI-AGENTS

### Phase 2: Migrate Scripts
1. Move all CI/CD scripts to agents project
2. Update paths and references to be generic
3. Ensure scripts work with agents project structure

### Phase 3: Establish Dependency
1. Update AMI-TRADING to depend on AMI-AGENTS
2. Replace local code quality configurations in AMI-TRADING with references to shared configs from AMI-AGENTS
3. Remove all duplicated configurations and scripts from AMI-TRADING
4. Ensure AMI-AGENTS becomes the single source of truth for all code quality configurations

### Phase 4: Verification
1. Test that all code quality checks still work in both projects
2. Ensure pre-commit hooks function properly
3. Verify that vendor dependency injection still works
4. Confirm no duplicate configurations remain in AMI-TRADING

## Notes
- Need to preserve the specific configurations that are unique to each project
- The agents project should serve as the "infrastructure" for code quality across projects
- Maintain backward compatibility during the migration process
- At the end of migration, AMI-TRADING should only contain project-specific configurations and rely on AMI-AGENTS for all shared code quality infrastructure