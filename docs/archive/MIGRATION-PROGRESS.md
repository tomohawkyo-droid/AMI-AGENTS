# Code Quality Migration Progress Tracker

## Overview
Tracking the migration of code quality configurations and scripts from AMI-TRADING to AMI-AGENTS.

## Phase 1: Extract and Generalize

### 1.1 Ruff Configuration Migration
- [ ] Copy ruff.toml from AMI-TRADING
- [ ] Compare with existing ruff configuration in agents
- [ ] Merge configurations if needed
- [ ] Update paths and exclusions appropriately

### 1.2 MyPy Configuration Migration
- [ ] Extract mypy configuration from pyproject.base.toml in AMI-TRADING
- [ ] Create standalone mypy configuration file
- [ ] Reference in agents' pyproject.toml
- [ ] Test mypy functionality

### 1.3 PyTest Configuration Migration
- [ ] Extract pytest configuration from pyproject.base.toml in AMI-TRADING
- [ ] Create standalone pytest configuration file
- [ ] Update agents' test configuration as needed
- [ ] Test pytest functionality

## Phase 2: Migrate Scripts

### 2.1 Dependency Version Checker
- [ ] Locate script in AMI-TRADING
- [ ] Copy to agents project
- [ ] Update paths and references to be generic
- [ ] Test functionality

### 2.2 Banned Words Checker
- [ ] Locate script in AMI-TRADING
- [ ] Copy to agents project
- [ ] Update banned patterns to be generic
- [ ] Test functionality

### 2.3 Init Files Checker
- [ ] Locate script in AMI-TRADING
- [ ] Copy to agents project
- [ ] Update paths and references
- [ ] Test functionality

### 2.4 Co-authored Commit Blocker
- [ ] Locate script in AMI-TRADING
- [ ] Copy to agents project
- [ ] Update paths and references
- [ ] Test functionality

### 2.5 Coverage Verification Script
- [ ] Locate script in AMI-TRADING
- [ ] Copy to agents project
- [ ] Update coverage thresholds if needed
- [ ] Test functionality

## Phase 3: PyProject Generation System

### 3.1 Base PyProject Template
- [ ] Copy pyproject.base.toml from AMI-TRADING
- [ ] Generalize dependencies and settings
- [ ] Create reusable template system

### 3.2 Vendor Dependency Injection System
- [ ] Understand current implementation in AMI-TRADING
- [ ] Create reusable dependency injection system
- [ ] Test with different target environments

### 3.3 Configuration Generation Scripts
- [ ] Identify all config generation scripts
- [ ] Make them project-agnostic
- [ ] Test functionality

## Phase 4: Establish Dependency

### 4.1 Update AMI-TRADING to Depend on AMI-AGENTS
- [ ] Modify AMI-TRADING's pyproject.toml to include AMI-AGENTS as dependency
- [ ] Update configuration files to reference shared code quality configs from AMI-AGENTS
- [ ] Remove duplicated configurations from AMI-TRADING
- [ ] Remove duplicated scripts from AMI-TRADING
- [ ] Ensure AMI-AGENTS becomes the single source of truth

### 4.2 Verification
- [ ] Test all code quality checks in both projects
- [ ] Ensure pre-commit hooks function properly
- [ ] Verify vendor dependency injection still works
- [ ] Confirm no duplicate configurations remain in AMI-TRADING