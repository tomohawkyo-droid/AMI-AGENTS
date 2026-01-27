"""Unit tests for PolicyEngine edge cases and file-based pattern loading."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.core.policies.engine import (
    PolicyEngine,
)

EXPECTED_API_LIMIT_PATTERN_COUNT = 2


class TestPolicyEngineGetPolicyPathEdgeCases:
    """Edge case tests for PolicyEngine._get_policy_path method."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_none_when_key_not_dict(self, mock_config) -> None:
        """Test returns None when intermediate key is not a dict."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        engine._manifest = {"policies": {"bash": {"default": {"nested": "value"}}}}

        result = engine._get_policy_path("bash", "default")

        assert result is None

    @patch("ami.core.policies.engine.get_config")
    def test_returns_path_when_immediate_string(self, mock_config) -> None:
        """Test returns path when value is immediate string."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        # Set manifest where key directly maps to path
        engine._manifest = {"policies": {"bash": "direct_path.yaml"}}

        result = engine._get_policy_path("bash")

        assert result == Path("/test/direct_path.yaml")

    @patch("ami.core.policies.engine.get_config")
    def test_returns_none_when_final_value_not_string(self, mock_config) -> None:
        """Test returns None when final value is not a string."""
        mock_config.return_value = MagicMock(root=Path("/test"))

        with patch.object(Path, "exists", return_value=False):
            engine = PolicyEngine()

        # Set manifest where final value is a dict
        engine._manifest = {"policies": {"bash": {"nested": {"more": "stuff"}}}}

        result = engine._get_policy_path("bash", "nested")

        # Final value is dict {"more": "stuff"}, not string
        assert result is None


class TestPolicyEngineLoadWithFileExists:
    """Tests for load methods when files exist."""

    @patch("ami.core.policies.engine.get_config")
    def test_load_python_patterns_with_file(self, mock_config, tmp_path: Path) -> None:
        """Test load_python_patterns when file exists."""
        mock_config.return_value = MagicMock(root=tmp_path)

        # Create policy file
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "python.yaml"
        policy_file.write_text("""
patterns:
  - name: eval_check
    pattern: eval
    reason: Avoid eval
""")

        # Create empty manifest
        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {"policies": {"python": {"fast": "policies/python.yaml"}}}

        patterns = engine.load_python_patterns()

        assert len(patterns) == 1
        assert patterns[0]["name"] == "eval_check"

    @patch("ami.core.policies.engine.get_config")
    def test_load_sensitive_patterns_with_file(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test load_sensitive_patterns when file exists."""
        mock_config.return_value = MagicMock(root=tmp_path)

        # Create policy file
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "sensitive.yaml"
        policy_file.write_text("""
sensitive_patterns:
  - pattern: dotenv
    reason: Environment file
""")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {
            "policies": {"sensitive": {"files": "policies/sensitive.yaml"}}
        }

        patterns = engine.load_sensitive_patterns()

        assert len(patterns) == 1
        assert patterns[0]["pattern"] == "dotenv"

    @patch("ami.core.policies.engine.get_config")
    def test_load_communication_patterns_with_file(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test load_communication_patterns when file exists."""
        mock_config.return_value = MagicMock(root=tmp_path)

        # Create policy file
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "comm.yaml"
        policy_file.write_text("""
prohibited_patterns:
  - pattern: secret
    reason: Do not share secrets
""")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {
            "policies": {"communication": {"prohibited": "policies/comm.yaml"}}
        }

        patterns = engine.load_communication_patterns()

        assert len(patterns) == 1
        assert patterns[0]["pattern"] == "secret"

    @patch("ami.core.policies.engine.get_config")
    def test_load_api_limit_patterns_with_file(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test load_api_limit_patterns when file exists."""
        mock_config.return_value = MagicMock(root=tmp_path)

        # Create policy file
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "api.yaml"
        policy_file.write_text("""
api_limit_patterns:
  - pattern: rate_limit
  - pattern: quota_exceeded
""")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {"policies": {"api_limits": {"files": "policies/api.yaml"}}}

        patterns = engine.load_api_limit_patterns()

        assert len(patterns) == EXPECTED_API_LIMIT_PATTERN_COUNT
        assert "rate_limit" in patterns
        assert "quota_exceeded" in patterns

    @patch("ami.core.policies.engine.get_config")
    def test_load_exemptions_with_file(self, mock_config, tmp_path: Path) -> None:
        """Test load_exemptions when file exists."""
        mock_config.return_value = MagicMock(root=tmp_path)

        # Create policy file
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "exemptions.yaml"
        policy_file.write_text("""
pattern_check_exemptions:
  - conftest.py
  - test_helper.py
""")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {
            "policies": {"exemptions": {"files": "policies/exemptions.yaml"}}
        }

        exemptions = engine.load_exemptions()

        assert "conftest.py" in exemptions
        assert "test_helper.py" in exemptions

    @patch("ami.core.policies.engine.get_config")
    def test_load_python_patterns_non_dict_data(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test load_python_patterns when YAML data is not a dict."""
        mock_config.return_value = MagicMock(root=tmp_path)

        # Create policy file with non-dict content
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "python.yaml"
        policy_file.write_text("just_a_string")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {"policies": {"python": {"fast": "policies/python.yaml"}}}

        patterns = engine.load_python_patterns()

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_load_sensitive_patterns_non_dict_data(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test load_sensitive_patterns when YAML data is not a dict."""
        mock_config.return_value = MagicMock(root=tmp_path)

        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "sensitive.yaml"
        policy_file.write_text("123")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {
            "policies": {"sensitive": {"files": "policies/sensitive.yaml"}}
        }

        patterns = engine.load_sensitive_patterns()

        assert patterns == []

    @patch("ami.core.policies.engine.get_config")
    def test_load_communication_patterns_non_dict_data(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test load_communication_patterns when YAML data is not a dict."""
        mock_config.return_value = MagicMock(root=tmp_path)

        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        policy_file = policy_dir / "comm.yaml"
        policy_file.write_text("null")

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("")

        engine = PolicyEngine(root_dir=tmp_path)
        engine._manifest = {
            "policies": {"communication": {"prohibited": "policies/comm.yaml"}}
        }

        patterns = engine.load_communication_patterns()

        assert patterns == []


class TestPolicyEngineLoadManifestNonDict:
    """Tests for _load_manifest when YAML is not a dict."""

    @patch("ami.core.policies.engine.get_config")
    def test_returns_empty_dict_when_yaml_not_dict(
        self, mock_config, tmp_path: Path
    ) -> None:
        """Test returns empty dict when YAML is not a dict."""
        mock_config.return_value = MagicMock(root=tmp_path)

        manifest_dir = tmp_path / "ami" / "config" / "policies"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.yaml"
        manifest_file.write_text("just_a_string")

        engine = PolicyEngine(root_dir=tmp_path)

        assert engine._manifest == {}
