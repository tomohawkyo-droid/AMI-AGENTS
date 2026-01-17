"""Integration tests for AMI Agent Security Guards.

Tests the "Second Layer of Defense":
1. Static Command Guard (regex checks)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from ami.core.bootloader_agent import BootloaderAgent


@pytest.fixture
def agent_fixture():
    """Setup a BootloaderAgent instance."""
    return BootloaderAgent()

@pytest.fixture
def interactive_guard_rules():
    """Path to the interactive agent rules."""
    # We need the REAL project root to find the config, not the mocked one
    # tests/integration/test... -> agents/tests/integration -> agents/tests -> agents
    agents_root = Path(__file__).resolve().parent.parent.parent
    return agents_root / "ami/config/policies/interactive.yaml"

def test_static_command_guard_blocks_dangerous_commands(agent_fixture, interactive_guard_rules):
    """Test that static regex guards block dangerous commands like 'rm'."""
    script = "rm -rf /"
    
    # Pass the interactive rules path
    result = agent_fixture.execute_shell(script, guard_rules_path=interactive_guard_rules)
    
    assert "🛑 BLOCKED" in result
    assert "SECURITY VIOLATION" in result
    assert "Use Delete/FileSys tools instead of rm" in result

def test_static_command_guard_allows_whitelisted_commands(agent_fixture, interactive_guard_rules):
    """Test that sed/echo/awk are ALLOWED."""
    test_file = agent_fixture.project_root / "test.txt"
    try:
        test_file.write_text("hello")
        
        script = f"sed -i 's/hello/world/' {test_file}"
        
        with patch("base.backend.workers.file_subprocess.FileSubprocessSync.run") as mock_run:
            mock_run.return_value = {"stdout": "", "stderr": "", "returncode": 0}
            
            # Pass the interactive rules path
            result = agent_fixture.execute_shell(script, guard_rules_path=interactive_guard_rules)
            
            assert "🛑 BLOCKED" not in result
            assert ">" in result
    finally:
        if test_file.exists():
            test_file.unlink()

def test_interactive_mode_awk_allowed(agent_fixture, interactive_guard_rules):
    """Verify specifically that AWK is allowed."""
    script = "echo '1 2' | awk '{print $2}'"
    
    with patch("base.backend.workers.file_subprocess.FileSubprocessSync.run") as mock_run:
        mock_run.return_value = {"stdout": "2", "stderr": "", "returncode": 0}
        
        result = agent_fixture.execute_shell(script, guard_rules_path=interactive_guard_rules)
        
        assert "🛑 BLOCKED" not in result
