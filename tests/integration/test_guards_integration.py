"""Integration tests for AMI Security Guards.

Verifies that:
1. PolicyEngine correctly loads patterns from configuration files.
2. check_command_safety correctly uses these patterns to block forbidden commands.
3. check_edit_safety correctly blocks modifications to sensitive files.
4. check_content_safety correctly identifies prohibited communication patterns.
"""

import pytest

from ami.core.guards import check_command_safety, check_content_safety
from ami.core.policies.engine import PolicyEngine, get_policy_engine


@pytest.fixture
def real_policy_engine() -> PolicyEngine:
    """Fixture that uses the real PolicyEngine with actual config files."""
    # Reset singleton to ensure fresh load
    import ami.core.policies.engine

    ami.core.policies.engine._engine = None
    return get_policy_engine()


class TestGuardIntegration:
    def test_policy_engine_loads_real_configs(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify PolicyEngine loads actual patterns from disk."""
        # Check Bash Patterns (default.yaml)
        bash_patterns = real_policy_engine.load_bash_patterns("default")
        assert len(bash_patterns) > 0
        # 'rm' is a standard forbidden command
        assert any(p["pattern"] == r"\brm\b" for p in bash_patterns)

        # Check Sensitive Patterns (sensitive_files.yaml)
        sensitive_patterns = real_policy_engine.load_sensitive_patterns()
        assert len(sensitive_patterns) > 0
        # 'vars.yml' is a standard sensitive file
        assert any(p["pattern"] == "vars.yml" for p in sensitive_patterns)

        # Check Communication Patterns
        comm_patterns = real_policy_engine.load_communication_patterns()
        assert len(comm_patterns) > 0
        # Match the actual regex: "\\bthe\\s+issue\\s+is\\s+clear\\b"
        assert any(
            "issue" in p["pattern"] and "clear" in p["pattern"] for p in comm_patterns
        )

    def test_command_safety_blocks_forbidden_commands(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify check_command_safety blocks commands defined in default.yaml."""
        # ... (same as before) ...
        # 'rm' should be blocked
        is_safe, msg = check_command_safety("rm -rf /")
        assert not is_safe
        assert "SECURITY VIOLATION" in msg
        assert "permanent deletion is restricted" in msg

        # 'sudo' should be blocked
        is_safe, msg = check_command_safety("sudo apt-get install")
        assert not is_safe
        assert "Sudo commands not allowed" in msg

    def test_command_safety_allows_permitted_commands(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify check_command_safety allows benign commands."""
        is_safe, msg = check_command_safety("ls -la")
        assert is_safe
        assert msg == ""

        is_safe, msg = check_command_safety("grep 'pattern' file.txt")
        assert is_safe
        assert msg == ""

    def test_edit_safety_blocks_sensitive_files(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify check_edit_safety blocks edits to sensitive files."""
        # Use interactive policy which allows 'echo' but relies on check_edit_safety
        interactive_policy = (
            real_policy_engine.root / "ami/config/policies/interactive.yaml"
        )

        # Echo to vars.yml
        cmd = "echo 'secret' > vars.yml"
        is_safe, msg = check_command_safety(cmd, guard_rules_path=interactive_policy)
        assert not is_safe
        assert "SECURITY VIOLATION" in msg
        assert "Direct modification of 'Global variables and secrets' (vars.yml)" in msg

        # Sed on .env
        cmd = "sed -i 's/foo/bar/' .env"
        is_safe, msg = check_command_safety(cmd, guard_rules_path=interactive_policy)
        assert not is_safe
        assert "Direct modification of 'Environment secrets' (.env)" in msg

    def test_edit_safety_allows_nonsensitive_files(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify check_edit_safety allows edits to non-sensitive files."""
        # Use interactive policy which allows 'echo'
        interactive_policy = (
            real_policy_engine.root / "ami/config/policies/interactive.yaml"
        )

        cmd = "echo 'data' > data.txt"
        is_safe, msg = check_command_safety(cmd, guard_rules_path=interactive_policy)
        assert is_safe
        assert msg == ""

    def test_content_safety_blocks_prohibited_phrases(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify check_content_safety blocks bad communication patterns."""
        content = "I see the problem, the issue is clear."
        is_safe, msg = check_content_safety(content)
        assert not is_safe
        assert "COMMUNICATION VIOLATION" in msg
        assert "the issue is clear" in msg or "I see the problem" in msg

    def test_content_safety_allows_good_communication(
        self, real_policy_engine: PolicyEngine
    ) -> None:
        """Verify check_content_safety allows normal communication."""
        content = "I have analyzed the logs and identified a potential cause."
        is_safe, msg = check_content_safety(content)
        assert is_safe
        assert msg == ""
