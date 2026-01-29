"""Tests for PolicyEngine init, manifest, and pattern loading."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from ami.core.policies.engine import (
    PolicyEngine,
    PythonPattern,
    _singleton,
    get_policy_engine,
)

EXPECTED_API_LIMIT_PATTERN_COUNT = 2
EXPECTED_EXEMPTION_COUNT = 2


class TestPythonPatternTypedDict:
    """Tests for PythonPattern TypedDict."""

    def test_create_python_pattern(self) -> None:
        """Test creating PythonPattern."""
        pattern: PythonPattern = {
            "name": "eval_usage",
            "pattern": r"\beval\(",
            "reason": "Avoid eval",
        }

        assert pattern["name"] == "eval_usage"
        assert pattern["pattern"] == r"\beval\("
        assert pattern["reason"] == "Avoid eval"


class TestPolicyEngineInit:
    """Tests for PolicyEngine initialization."""

    @patch("ami.core.policies.engine.get_config")
    def test_default_initialization(self, mock_config) -> None:
        """Test default initialization."""
        mock_config.return_value = MagicMock(root=Path("/test/root"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        assert engine.root == Path("/test/root")

    @patch("ami.core.policies.engine.get_config")
    def test_custom_root_dir(self, mock_config) -> None:
        """Test initialization with custom root_dir."""
        mock_config.return_value = MagicMock(root=Path("/default"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine(root_dir=Path("/custom"))

        assert engine.root == Path("/custom")


class TestPolicyEngineLoadManifest:
    """Tests for PolicyEngine._load_manifest method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_dict_when_manifest_missing(self, mock_config) -> None:
        """Test returns empty dict when manifest doesn't exist."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        assert engine._manifest == {}

    @patch("ami.core.policies.engine.get_config")
    def test_loads_manifest_when_exists(self, mock_config) -> None:
        """Test loads manifest when it exists."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        manifest_content = """
policies:
  bash:
    default: path/to/bash.yaml
"""
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open(read_data=manifest_content)),
        ):
            engine = PolicyEngine()

        assert isinstance(engine._manifest, dict)
        assert "policies" in engine._manifest


class TestPolicyEngineGetPolicyPath:
    """Tests for PolicyEngine._get_policy_path method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_none_when_policies_missing(self, mock_config) -> None:
        """Test returns None when policies key missing."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        result = engine._get_policy_path("bash", "default")

        assert result is None

    @patch("ami.core.policies.engine.get_config")
    def test_returns_path_for_valid_key(self, mock_config) -> None:
        """Test returns path for valid key."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        manifest_content = """
policies:
  bash:
    default: policies/bash.yaml
"""
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open(read_data=manifest_content)),
        ):
            engine = PolicyEngine()

        result = engine._get_policy_path("bash", "default")

        assert result == Path("/test/policies/bash.yaml")


class TestPolicyEngineLoadBashPatterns:
    """Tests for PolicyEngine.load_bash_patterns method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_when_no_path(self, mock_config) -> None:
        """Test returns empty list when path not found."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        patterns = engine.load_bash_patterns("default")

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_caches_result(self, mock_config) -> None:
        """Test caches bash patterns."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        # First call
        engine.load_bash_patterns("default")
        # Add to cache manually to verify caching
        engine._bash_cache["custom"] = [{"pattern": "test", "reason": "Test"}]

        # Should return cached value
        patterns = engine.load_bash_patterns("custom")

        assert patterns == [{"pattern": "test", "reason": "Test"}]


class TestPolicyEngineLoadPythonPatterns:
    """Tests for PolicyEngine.load_python_patterns method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_when_no_path(self, mock_config) -> None:
        """Test returns empty list when path not found."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        patterns = engine.load_python_patterns()

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_caches_result(self, mock_config) -> None:
        """Test caches python patterns."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        # First call sets cache
        engine.load_python_patterns()
        # Set cache manually
        engine._python_cache = [{"name": "test", "pattern": ".*", "reason": "test"}]

        # Should return cached value
        patterns = engine.load_python_patterns()

        assert len(patterns) == 1


class TestPolicyEngineLoadSensitivePatterns:
    """Tests for PolicyEngine.load_sensitive_patterns method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_when_no_path(self, mock_config) -> None:
        """Test returns empty list when path not found."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        patterns = engine.load_sensitive_patterns()

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_caches_result(self, mock_config) -> None:
        """Test caches sensitive patterns."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        engine.load_sensitive_patterns()
        engine._sensitive_cache = [{"pattern": r"\.env", "reason": "Sensitive file"}]

        patterns = engine.load_sensitive_patterns()

        assert len(patterns) == 1


class TestPolicyEngineLoadCommunicationPatterns:
    """Tests for PolicyEngine.load_communication_patterns method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_when_no_path(self, mock_config) -> None:
        """Test returns empty list when path not found."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        patterns = engine.load_communication_patterns()

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_caches_result(self, mock_config) -> None:
        """Test caches communication patterns."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        engine.load_communication_patterns()
        engine._communication_cache = [{"pattern": "ignore", "reason": "Communication"}]

        patterns = engine.load_communication_patterns()

        assert len(patterns) == 1


class TestPolicyEngineLoadApiLimitPatterns:
    """Tests for PolicyEngine.load_api_limit_patterns method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_when_no_path(self, mock_config) -> None:
        """Test returns empty list when path not found."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        patterns = engine.load_api_limit_patterns()

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_caches_result(self, mock_config) -> None:
        """Test caches API limit patterns."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        engine.load_api_limit_patterns()
        engine._api_limit_cache = ["pattern1", "pattern2"]

        patterns = engine.load_api_limit_patterns()

        assert len(patterns) == EXPECTED_API_LIMIT_PATTERN_COUNT


class TestPolicyEngineLoadExemptions:
    """Tests for PolicyEngine.load_exemptions method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_when_no_path(self, mock_config) -> None:
        """Test returns empty set when path not found."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        exemptions = engine.load_exemptions()

        assert exemptions == set()

    @patch("ami.core.policies.engine.get_config")
    def test_caches_result(self, mock_config) -> None:
        """Test caches exemptions."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        engine.load_exemptions()
        engine._exemptions_cache = {"file1.py", "file2.py"}

        exemptions = engine.load_exemptions()

        assert len(exemptions) == EXPECTED_EXEMPTION_COUNT


class TestGetPolicyEngine:
    """Tests for get_policy_engine function."""

    def test_returns_singleton(self) -> None:
        """Test returns same instance."""
        # Clear singleton
        _singleton.clear()

        with patch("ami.core.policies.engine.PolicyEngine") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            first = get_policy_engine()
            second = get_policy_engine()

        # Should be same instance
        assert first is second
        # Should only create once
        mock_class.assert_called_once()
