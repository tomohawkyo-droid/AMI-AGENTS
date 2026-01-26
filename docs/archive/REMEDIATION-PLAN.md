# Remediation Plan for AMI-AGENTS Code Quality Infrastructure

## Objective
Transform the AMI-AGENTS project into a proper shared code quality infrastructure that follows Python idioms for dependency management and configuration sharing.

## Current Issues
- Overcomplicated file copying approach instead of direct package access
- Redundant scripts and configurations
- Improper dependency management
- Violation of "never copy files between projects" principle

## Remediation Steps

### Phase 1: Simplify Package Structure
1. Remove all file copying scripts:
   - Delete: setup_configs.py
   - Delete: generate_pyproject.py 
   - Delete: inject_vendor_deps.py
2. Simplify pyproject.toml to only include necessary dependencies and extras
3. Remove redundant configuration files that duplicate functionality
4. Ensure all configurations are accessed directly from the installed package via importlib.resources

### Phase 2: Proper Dependency Management
1. Restructure extras_require in pyproject.toml to include:
   - `[lint]` - ruff==0.14.10, black==25.12.0
   - `[type-check]` - mypy==1.19.1, types-requests, types-setuptools, types-PyYAML, types-tqdm
   - `[test]` - pytest==9.0.2, pytest-asyncio==1.3.0, pytest-cov
   - `[ci]` - pre-commit==4.5.1
   - `[torch-cuda]` - torch==2.5.1+cu121, torchvision==0.20.1+cu121, torchaudio==2.5.1+cu121
   - `[torch-cpu]` - torch, torchvision, torchaudio
   - `[torch-mps]` - torch, torchvision, torchaudio (for Apple Silicon)
2. Remove any local installation references in trading project
3. Ensure trading project depends on ami-agents via standard PyPI-style dependency: `ami-agents[lint,type-check,test]`

### Phase 3: Direct Configuration Access
1. Remove all local copies of configuration files
2. Update tools to access configurations directly from the installed package using importlib.resources:
   - Ruff: `ruff check --config "$(python -c "from importlib.resources import files; from ami.res.config import ruff; print(files('ami.res.config') / 'ruff.toml')")"`
   - MyPy: `mypy --config-file "$(python -c "from importlib.resources import files; from ami.res.config import mypy; print(files('ami.res.config') / 'mypy.toml')")"`
3. Update pre-commit configuration to reference installed package configurations

### Phase 4: Eliminate Unnecessary Scripts
1. Remove all scripts that duplicate standard tooling functionality
2. Keep only scripts that provide unique value not available through standard configuration:
   - check_banned_words.py
   - check_dependency_versions.py
   - check_init_files.py
   - block_coauthored.py
   - verify_coverage.py
3. Ensure remaining scripts are accessible via console entry points in pyproject.toml

### Phase 5: Vendor Dependency Management
1. Create proper extras for different vendor configurations in pyproject.toml:
   - `[torch-cuda]` - torch==2.5.1+cu121, torchvision==0.20.1+cu121, torchaudio==2.5.1+cu121
   - `[torch-cpu]` - torch, torchvision, torchaudio
   - `[torch-mps]` - torch, torchvision, torchaudio
2. Use standard pip extras mechanism instead of custom injection scripts
3. Ensure vendor-specific dependencies are properly isolated

### Phase 6: Update Trading Project
1. Remove all copied configuration files
2. Update to use direct package references for all configurations
3. Update pre-commit configuration to use installed package configurations
4. Ensure proper dependency on ami-agents with required extras: `dependencies = ["ami-agents[lint,type-check,test,torch-cuda]"]`

## Expected Outcome
- Clean dependency chain: Trading project depends on ami-agents with specific extras
- Direct access to configurations from installed package via importlib.resources
- No file copying between projects
- Proper vendor dependency management through extras
- Standard Python packaging idioms throughout