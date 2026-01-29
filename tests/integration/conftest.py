"""Shared fixtures for integration tests.

Provides common configuration fixtures and singleton resets.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

import ami.core.policies.engine as eng
from ami.core.config import Config, _ConfigSingleton
from ami.core.env import get_project_root


@pytest.fixture
def real_config(monkeypatch: pytest.MonkeyPatch) -> Generator[Config, None, None]:
    """Return a Config() loaded from real YAML, resetting the singleton."""
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    cfg = Config()
    _ConfigSingleton.instance = cfg
    yield cfg
    _ConfigSingleton.instance = None


@pytest.fixture
def project_root() -> Path:
    """Return the validated project root path."""
    root = get_project_root()
    assert root.exists()
    assert (root / "pyproject.toml").exists()
    return root


@pytest.fixture
def reset_policy_engine():
    """Clear the policy engine singleton between tests."""
    eng._singleton.clear()
    yield
    eng._singleton.clear()
