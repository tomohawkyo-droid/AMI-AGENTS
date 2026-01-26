# AMI-Agents: Shared Code Quality Infrastructure

This package provides shared code quality configurations and tools for use across AMI projects.

## Installation

```bash
pip install ami-agents
# or for development
pip install -e .

# For specific tooling extras:
pip install ami-agents[lint]      # For linting tools (ruff, black)
pip install ami-agents[type-check]  # For type checking (mypy)
pip install ami-agents[test]      # For testing (pytest)
pip install ami-agents[ci]        # For CI/CD tools (pre-commit)
```

## Usage

### Using Shared Configurations

The shared configurations are available in the package under `ami.res.config`. You can access them programmatically:

```python
from ami.res.config import get_config_path

# Get path to shared ruff configuration
ruff_config_path = get_config_path("ruff.toml")
```

### Using Shared Scripts

The package provides command-line tools for common operations:

```bash
# Generate pyproject.toml from base template
ami-generate-pyproject --name myproject --description "My project"

# Inject vendor-specific dependencies
ami-inject-vendor-deps --vendor-file requirements-cuda.txt
```

### Using CI/CD Scripts

The package includes various CI/CD scripts in the `ami.scripts.ci` module:

- `check_banned_words.py` - Checks for prohibited patterns
- `check_dependency_versions.py` - Validates dependency configurations
- `check_init_files.py` - Ensures `__init__.py` files don't contain logic
- `block_coauthored.py` - Prevents co-authored commits
- `verify_coverage.py` - Enforces test coverage thresholds

## Configuration Files Included

The package includes the following configuration files:

- `ami/res/config/ruff.toml` - Ruff linting and formatting configuration
- `ami/res/config/mypy.toml` - MyPy type checking configuration
- `ami/res/config/pyproject.base.toml` - Base pyproject.toml template
- `ami/res/config/vendor/` - Vendor-specific dependency configurations

## For Project Integration

To integrate with your project:

1. Add ami-agents as a dependency in your pyproject.toml:
   ```
   dependencies = [
       "ami-agents>=1.0.0",
       # ... other dependencies
   ]
   ```

2. Use the shared configurations in your project:
   - Copy configurations from `ami/res/config/` to your project
   - Or reference them in your build process

3. Use the shared CI/CD scripts in your workflows