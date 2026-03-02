"""Unit tests for PolicyEngine."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ami.core.policies.engine import PolicyEngine


class TestPolicyEngine:
    @pytest.fixture
    def engine(self) -> Generator[PolicyEngine, None, None]:
        with patch("ami.core.policies.engine.get_config") as mock_conf:
            mock_conf.return_value.root = Path("/mock/root")
            yield PolicyEngine()

    def test_get_policy_path(self, engine: PolicyEngine) -> None:
        """Test manifest lookup logic."""
        engine._manifest = {"policies": {"test": {"nested": "path/to/file.yaml"}}}

        path = engine._get_policy_path("test", "nested")
        assert path == Path("/mock/root/path/to/file.yaml")

        assert engine._get_policy_path("invalid") is None
