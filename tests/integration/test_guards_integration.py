"""Integration tests for AMI Security Guards.

Verifies that:
1. check_edit_safety correctly blocks modifications to sensitive files.
2. check_content_safety correctly identifies prohibited communication patterns.
"""

import ami.core.policies.engine
from ami.core.guards import check_content_safety, check_edit_safety
from ami.core.policies.engine import get_policy_engine


class TestGuardIntegration:
    def setup_method(self) -> None:
        ami.core.policies.engine._singleton.clear()
        self.engine = get_policy_engine()

    def test_policy_engine_loads_real_configs(self) -> None:
        """Verify PolicyEngine loads actual patterns from disk."""
        # Check Sensitive Patterns (sensitive_files.yaml)
        sensitive_patterns = self.engine.load_sensitive_patterns()
        assert len(sensitive_patterns) > 0
        assert any(p["pattern"] == "vars.yml" for p in sensitive_patterns)

        # Check Communication Patterns
        comm_patterns = self.engine.load_communication_patterns()
        assert len(comm_patterns) > 0
        assert any(
            "issue" in p["pattern"] and "clear" in p["pattern"] for p in comm_patterns
        )

    def test_edit_safety_blocks_sensitive_files(self) -> None:
        """Verify check_edit_safety blocks edits to sensitive files."""
        is_safe, msg = check_edit_safety("echo 'secret' > vars.yml")
        assert not is_safe
        assert "SECURITY VIOLATION" in msg

    def test_edit_safety_allows_nonsensitive_files(self) -> None:
        """Verify check_edit_safety allows edits to non-sensitive files."""
        is_safe, msg = check_edit_safety("echo 'data' > data.txt")
        assert is_safe
        assert msg == ""

    def test_content_safety_blocks_prohibited_phrases(self) -> None:
        """Verify check_content_safety blocks bad communication patterns."""
        content = "I see the problem, the issue is clear."
        is_safe, msg = check_content_safety(content)
        assert not is_safe
        assert "COMMUNICATION VIOLATION" in msg

    def test_content_safety_allows_good_communication(self) -> None:
        """Verify check_content_safety allows normal communication."""
        content = "I have analyzed the logs and identified a potential cause."
        is_safe, msg = check_content_safety(content)
        assert is_safe
        assert msg == ""
