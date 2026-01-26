"""Unit tests for PolicyEngine."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import mock_open, patch

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

    def test_load_bash_patterns(self, engine: PolicyEngine) -> None:
        """Test loading bash patterns."""
        mock_yaml = {"deny_patterns": [{"pattern": "rm", "message": "no"}]}

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open", mock_open(read_data="data")),
            patch("yaml.safe_load", return_value=mock_yaml),
            patch.object(engine, "_get_policy_path", return_value=Path("test.yaml")),
        ):
            patterns = engine.load_bash_patterns()
            assert len(patterns) == 1
            assert patterns[0]["pattern"] == "rm"

    def test_load_missing_file(self, engine: PolicyEngine) -> None:
        """Test loading non-existent file returns empty list."""
        with patch("pathlib.Path.exists", return_value=False):
            assert engine.load_bash_patterns() == []
