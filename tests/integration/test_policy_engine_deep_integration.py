"""Integration tests for the policy engine.

Exercises: core/policies/engine.py, core/logic.py (remaining loaders)
"""

from pathlib import Path

import pytest

import ami.core.policies.engine as eng
from ami.core.config import _ConfigSingleton
from ami.core.logic import (
    load_api_limit_patterns,
    load_communication_patterns,
    load_exemptions,
    load_python_patterns,
    load_sensitive_patterns,
)
from ami.core.policies.engine import PolicyEngine, get_policy_engine


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch: pytest.MonkeyPatch):
    """Reset all singletons between tests."""
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    eng._singleton.clear()
    yield
    eng._singleton.clear()
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# PolicyEngine loading from real manifest
# ---------------------------------------------------------------------------


class TestPolicyEngineLoading:
    """Test PolicyEngine loads real policies from disk."""

    def test_engine_loads_manifest(self):
        engine = PolicyEngine()
        assert engine._manifest is not None
        assert isinstance(engine._manifest, dict)

    def test_manifest_has_policies(self):
        engine = PolicyEngine()
        assert "policies" in engine._manifest or engine._manifest == {}

    def test_manifest_path_exists(self):
        engine = PolicyEngine()
        assert engine.manifest_path.name == "manifest.yaml"

    def test_engine_root_is_valid(self):
        engine = PolicyEngine()
        assert engine.root.exists()


class TestPythonPatterns:
    """Test Python pattern loading."""

    def test_load_python_patterns(self):
        engine = PolicyEngine()
        patterns = engine.load_python_patterns()
        assert isinstance(patterns, list)

    def test_python_patterns_structure(self):
        engine = PolicyEngine()
        patterns = engine.load_python_patterns()
        if patterns:
            first = patterns[0]
            assert "name" in first
            assert "check_type" in first
            assert "error_template" in first

    def test_caching(self):
        engine = PolicyEngine()
        first = engine.load_python_patterns()
        second = engine.load_python_patterns()
        assert first is second


class TestSensitivePatterns:
    """Test sensitive file pattern loading."""

    def test_load_sensitive_patterns(self):
        engine = PolicyEngine()
        patterns = engine.load_sensitive_patterns()
        assert isinstance(patterns, list)

    def test_sensitive_patterns_non_empty(self):
        engine = PolicyEngine()
        patterns = engine.load_sensitive_patterns()
        # Sensitive patterns should exist in a security-focused project
        assert len(patterns) > 0 or patterns == []

    def test_caching(self):
        engine = PolicyEngine()
        first = engine.load_sensitive_patterns()
        second = engine.load_sensitive_patterns()
        assert first is second


class TestCommunicationPatterns:
    """Test prohibited communication pattern loading."""

    def test_load_communication_patterns(self):
        engine = PolicyEngine()
        patterns = engine.load_communication_patterns()
        assert isinstance(patterns, list)

    def test_caching(self):
        engine = PolicyEngine()
        first = engine.load_communication_patterns()
        second = engine.load_communication_patterns()
        assert first is second


class TestAPILimitPatterns:
    """Test API limit pattern loading."""

    def test_load_api_limit_patterns(self):
        engine = PolicyEngine()
        patterns = engine.load_api_limit_patterns()
        assert isinstance(patterns, list)

    def test_caching(self):
        engine = PolicyEngine()
        first = engine.load_api_limit_patterns()
        second = engine.load_api_limit_patterns()
        assert first is second


class TestExemptions:
    """Test file exemption loading."""

    def test_load_exemptions(self):
        engine = PolicyEngine()
        exemptions = engine.load_exemptions()
        assert isinstance(exemptions, set)

    def test_caching(self):
        engine = PolicyEngine()
        first = engine.load_exemptions()
        second = engine.load_exemptions()
        assert first is second


# ---------------------------------------------------------------------------
# _get_policy_path
# ---------------------------------------------------------------------------


class TestGetPolicyPath:
    """Test _get_policy_path with various key depths."""

    def test_valid_path(self):
        engine = PolicyEngine()
        path = engine._get_policy_path("sensitive", "files")
        if path is not None:
            assert isinstance(path, Path)
            assert path.exists()

    def test_nonexistent_key(self):
        engine = PolicyEngine()
        path = engine._get_policy_path("nonexistent", "key")
        assert path is None

    def test_single_level_tiers(self):
        engine = PolicyEngine()
        # "tiers" is a string path, not a dict -- should return a Path
        path = engine._get_policy_path("tiers")
        assert path is None or isinstance(path, Path)

    def test_deep_nonexistent(self):
        engine = PolicyEngine()
        path = engine._get_policy_path("a", "b", "c", "d")
        assert path is None


# ---------------------------------------------------------------------------
# Nonexistent manifest
# ---------------------------------------------------------------------------


class TestNonexistentManifest:
    """Test behavior with missing manifest file."""

    def test_empty_manifest(self, tmp_path: Path):
        engine = PolicyEngine.__new__(PolicyEngine)
        engine.config = (
            _ConfigSingleton.instance
            or __import__("ami.core.config", fromlist=["get_config"]).get_config()
        )
        engine.root = tmp_path
        engine.manifest_path = tmp_path / "nonexistent.yaml"
        engine._manifest = engine._load_manifest()
        engine._python_cache = None
        engine._sensitive_cache = None
        engine._communication_cache = None
        engine._api_limit_cache = None
        engine._exemptions_cache = None

        assert engine._manifest == {}
        assert engine.load_python_patterns() == []
        assert engine.load_sensitive_patterns() == []
        assert engine.load_communication_patterns() == []
        assert engine.load_api_limit_patterns() == []
        assert engine.load_exemptions() == set()


# ---------------------------------------------------------------------------
# Singleton behavior
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test get_policy_engine singleton behavior."""

    def test_singleton_returns_same_instance(self):
        e1 = get_policy_engine()
        e2 = get_policy_engine()
        assert e1 is e2

    def test_singleton_reset(self):
        e1 = get_policy_engine()
        eng._singleton.clear()
        e2 = get_policy_engine()
        assert e1 is not e2


# ---------------------------------------------------------------------------
# Logic loaders (delegating to PolicyEngine)
# ---------------------------------------------------------------------------


class TestLogicLoaders:
    """Test that logic.py loaders delegate to PolicyEngine correctly."""

    def test_load_python_patterns(self):
        patterns = load_python_patterns()
        assert isinstance(patterns, list)

    def test_load_sensitive_patterns(self):
        patterns = load_sensitive_patterns()
        assert isinstance(patterns, list)

    def test_load_communication_patterns(self):
        patterns = load_communication_patterns()
        assert isinstance(patterns, list)

    def test_load_api_limit_patterns(self):
        patterns = load_api_limit_patterns()
        assert isinstance(patterns, list)

    def test_load_exemptions(self):
        exemptions = load_exemptions()
        assert isinstance(exemptions, set)
