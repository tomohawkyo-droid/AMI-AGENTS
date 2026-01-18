"""Unit tests for PolicyEngine."""

from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import pytest
from ami.core.policies.engine import PolicyEngine

class TestPolicyEngine:
    
    @pytest.fixture
    def engine(self):
        with patch("ami.core.policies.engine.get_config") as mock_conf:
            mock_conf.return_value.root = Path("/mock/root")
            yield PolicyEngine()

    def test_get_policy_path(self, engine):
        """Test manifest lookup logic."""
        engine._manifest = {
            "policies": {
                "test": {
                    "nested": "path/to/file.yaml"
                }
            }
        }
        
        path = engine._get_policy_path("test", "nested")
        assert path == Path("/mock/root/path/to/file.yaml")
        
        assert engine._get_policy_path("invalid") is None

    def test_load_bash_patterns(self, engine):
        """Test loading bash patterns."""
        mock_yaml = {"deny_patterns": [{"pattern": "rm", "message": "no"}]}
        
        with patch("pathlib.Path.exists", return_value=True):
            # Mock Path.open directly
            with patch("pathlib.Path.open", mock_open(read_data="data")):
                with patch("yaml.safe_load", return_value=mock_yaml):
                     # Mock _get_policy_path to return a valid path
                     with patch.object(engine, "_get_policy_path", return_value=Path("test.yaml")):
                         patterns = engine.load_bash_patterns()
                         assert len(patterns) == 1
                         assert patterns[0]["pattern"] == "rm"

    def test_load_missing_file(self, engine):
        """Test loading non-existent file returns empty list."""
        with patch("pathlib.Path.exists", return_value=False):
            assert engine.load_bash_patterns() == []