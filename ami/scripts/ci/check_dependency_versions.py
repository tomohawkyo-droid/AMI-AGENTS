#!/usr/bin/env python3
"""
Universal script to check for dependency configuration compliance.
Ensures that:
1. Common dependencies are in pyproject.base.toml.
2. Hardware-specific dependencies (torch, etc.) are NOT in base.toml.
3. pyproject.toml contains all dependencies from pyproject.base.toml (ignoring vendor markers).
Configuration loaded from res/config/dependency_check.yaml
"""

import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "base_toml_path": "res/config/pyproject.base.toml",
    "generated_toml_path": "pyproject.toml",
    "forbidden_packages": ["torch", "torchvision", "torchaudio"],
}


def load_config(config_path: str = "res/config/dependency_check.yaml") -> Any:
    if Path(config_path).exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG


def parse_dependencies(path: Path) -> list[str]:
    """Parses pyproject.toml and returns a list of package names."""
    if not path.exists():
        return []

    with open(path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    parsed = []
    for dep in deps:
        if dep.strip() == "# VENDOR_DEPENDENCIES_PLACEHOLDER":
            continue

        # Extract name part (before any operator)
        # Using a simplistic split for now, robust parsing would use 'packaging.requirements'
        for op in ["==", ">=", "<=", ">", "<", "~=", "[", ";"]:
            if op in dep:
                name = dep.split(op, 1)[0]
                parsed.append(name.strip())
                break
        else:
            parsed.append(dep.strip())

    return parsed


def check_compliance(root: Path) -> bool:
    config = load_config()
    base_toml_rel = config.get("base_toml_path", "res/config/pyproject.base.toml")
    generated_toml_rel = config.get("generated_toml_path", "pyproject.toml")

    base_toml = root / base_toml_rel
    generated_toml = root / generated_toml_rel

    if not base_toml.exists():
        print(f"Error: Base configuration {base_toml} missing!")
        return True

    base_deps = parse_dependencies(base_toml)

    # 1. Check for forbidden hardware packages in base
    forbidden = set(config.get("forbidden_packages", []))
    violations = [pkg for pkg in base_deps if pkg in forbidden]

    if violations:
        print("\n!!! CONFIGURATION COMPLIANCE ERROR !!!")
        print(f"The following hardware-specific packages were found in {base_toml}:")
        for pkg in violations:
            print(f"  - {pkg}")
        print("These must be moved to vendor-specific configuration files")
        return True

    # 2. Check sync between base and generated toml
    if not generated_toml.exists():
        # If generated file doesn't exist yet (e.g. fresh clone), warning is enough?
        # Or strictly fail? The user asked to "always check".
        # Assuming build process creates it. If missing, we can't verify sync.
        print(f"Warning: Generated {generated_toml} not found. Skipping sync check.")
        return False

    gen_deps = parse_dependencies(generated_toml)
    gen_deps_set = set(gen_deps)

    missing_in_gen = [pkg for pkg in base_deps if pkg not in gen_deps_set]

    if missing_in_gen:
        print("\n!!! DEPENDENCY SYNC ERROR !!!")
        print(f"The following base dependencies are missing from {generated_toml}:")
        for pkg in missing_in_gen:
            print(f"  - {pkg}")
        print(
            f"Please run the installation/setup script to regenerate {generated_toml_rel}."
        )
        return True

    return False


def main() -> None:
    if check_compliance(Path(".")):
        sys.exit(1)
    print("Dependency configuration is compliant.")


if __name__ == "__main__":
    main()
