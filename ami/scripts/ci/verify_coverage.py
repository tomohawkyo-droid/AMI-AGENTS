#!/usr/bin/env python3
"""
Coverage Verification Script
Runs pytest with coverage and enforces strict thresholds for Unit and Integration tests.
Configuration loaded from res/config/coverage_thresholds.yaml
"""

import os
import subprocess
import sys
from typing import Any

import yaml

# Exit code from pytest-cov when coverage is below threshold
EXIT_CODE_COVERAGE_FAILURE = 2

DEFAULT_CONFIG = {
    "unit": {"path": "tests/unit", "min_coverage": 90, "source_path": "."},
    "integration": {
        "path": "tests/integration",
        "min_coverage": 75,
        "source_path": ".",
    },
}


def load_config(config_path: str = "res/config/coverage_thresholds.yaml") -> Any:
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG


def run_coverage(
    test_path: str, min_coverage: int, source_path: str, context_name: str
) -> bool:
    print(f"\n--- Running {context_name} Tests (Threshold: {min_coverage}%) ---")

    # Run pytest with coverage
    cmd = [
        "uv",
        "run",
        "--extra",
        "torch-cpu",
        "pytest",
        test_path,
        f"--cov={source_path}",
        "--cov-report=term-missing",
        f"--cov-fail-under={min_coverage}",
        "--tb=short",  # Show short tracebacks for debugging
        "-q",  # Quiet mode
    ]

    result = subprocess.run(cmd, capture_output=False, check=False)

    # Fail on ANY non-zero exit code (test failures OR coverage failures)
    if result.returncode != 0:
        if result.returncode == EXIT_CODE_COVERAGE_FAILURE:
            print(f"❌ {context_name} Coverage FAILED (Required: {min_coverage}%)")
        else:
            print(f"❌ {context_name} Tests FAILED (exit code {result.returncode})")
        return False

    print(f"✅ {context_name} Tests and Coverage Passed (>={min_coverage}%)")
    return True


def main() -> None:
    config = load_config()

    unit_conf = config.get("unit", DEFAULT_CONFIG["unit"])
    int_conf = config.get("integration", DEFAULT_CONFIG["integration"])

    # 1. Unit Tests
    unit_pass = run_coverage(
        unit_conf["path"], unit_conf["min_coverage"], unit_conf["source_path"], "Unit"
    )

    # 2. Integration Tests
    int_pass = run_coverage(
        int_conf["path"],
        int_conf["min_coverage"],
        int_conf["source_path"],
        "Integration",
    )

    if not unit_pass or not int_pass:
        print("\n🚫 PRE-PUSH CHECK FAILED: Coverage thresholds not met.")
        sys.exit(1)

    print("\n🎉 ALL COVERAGE CHECKS PASSED.")
    sys.exit(0)


if __name__ == "__main__":
    main()
