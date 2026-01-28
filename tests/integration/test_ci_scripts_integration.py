"""Integration tests for CI scripts.

Exercises: scripts/ci/check_banned_words.py, scripts/ci/check_file_length.py,
scripts/ci/check_init_files.py, scripts/ci/block_coauthored.py,
scripts/ci/verify_coverage.py
"""

import os
import textwrap
from pathlib import Path

import pytest

from ami.scripts.ci.block_coauthored import (
    DEFAULT_CONFIG as BLOCK_COAUTHORED_DEFAULT_CONFIG,
)
from ami.scripts.ci.block_coauthored import load_config as block_coauthored_load_config
from ami.scripts.ci.check_banned_words import (
    PatternRule,
    check_file_content,
    check_filename,
    compile_dir_rules,
    find_matching_rules,
    get_dir_rules,
    load_config,
)
from ami.scripts.ci.check_file_length import (
    DEFAULT_CONFIG,
    check_file_length,
    should_check_file,
)
from ami.scripts.ci.check_init_files import check_file as check_init_file
from ami.scripts.ci.verify_coverage import DEFAULT_CONFIG as COVERAGE_DEFAULT_CONFIG
from ami.scripts.ci.verify_coverage import (
    EXIT_CODE_COVERAGE_FAILURE,
)
from ami.scripts.ci.verify_coverage import load_config as coverage_load_config

# ---------------------------------------------------------------------------
# Constants for magic number comparisons
# ---------------------------------------------------------------------------
EXPECTED_VIOLATION_COUNT = 2
EXPECTED_MATCHING_RULES_COUNT = 2
EXPECTED_LONG_FILE_LINES = 600
EXPECTED_MAX_LINES = 512
EXPECTED_UNIT_COVERAGE = 90
EXPECTED_INTEGRATION_COVERAGE = 75
EXPECTED_EXIT_CODE_FAILURE = 2

# ---------------------------------------------------------------------------
# check_banned_words.py
# ---------------------------------------------------------------------------


class TestBannedWordsConfig:
    """Test loading real banned_words.yaml configuration."""

    def test_load_real_config(self, project_root: Path):
        config_path = str(project_root / "res" / "config" / "banned_words.yaml")
        if os.path.exists(config_path):
            config = load_config(config_path)
            assert isinstance(config, dict)
        else:
            pytest.skip("banned_words.yaml not found")

    def test_load_config_contains_expected_keys(self, project_root: Path):
        config_path = str(project_root / "res" / "config" / "banned_words.yaml")
        if not os.path.exists(config_path):
            pytest.skip("banned_words.yaml not found")
        config = load_config(config_path)
        # Should have at least one of the expected keys
        assert any(k in config for k in ("banned", "directory_rules", "filename_rules"))


class TestPatternRule:
    """Test PatternRule matching logic."""

    def test_simple_match(self):
        rule = PatternRule({"pattern": r"TODO", "reason": "No TODOs"})
        assert rule.matches("# TODO: fix this", "test.py")

    def test_no_match(self):
        rule = PatternRule({"pattern": r"TODO", "reason": "No TODOs"})
        assert not rule.matches("clean code here", "test.py")

    def test_regex_pattern(self):
        rule = PatternRule({"pattern": r"\beval\b", "reason": "No eval"})
        assert rule.matches("result = eval(expr)", "code.py")
        assert not rule.matches("evaluation = True", "code.py")

    def test_exception_regex(self):
        rule = PatternRule(
            {
                "pattern": r"TODO",
                "reason": "No TODOs",
                "exception_regex": r"test_.*\.py$",
            }
        )
        assert not rule.matches("# TODO", "test_foo.py")
        assert rule.matches("# TODO", "main.py")

    def test_invalid_regex_falls_back(self):
        rule = PatternRule({"pattern": "[invalid", "reason": "bad"})
        # Should fall back to literal match
        assert rule.matches("contains [invalid here", "test.py")


class TestCheckFileContent:
    """Test check_file_content with temp files."""

    def test_file_with_violations(self, tmp_path: Path):
        test_file = tmp_path / "bad.py"
        test_file.write_text("x = eval('bad')\n")
        rules = [PatternRule({"pattern": r"\beval\b", "reason": "No eval"})]
        errors = check_file_content(str(test_file), rules, [])
        assert len(errors) >= 1
        assert errors[0]["reason"] == "No eval"

    def test_file_without_violations(self, tmp_path: Path):
        test_file = tmp_path / "good.py"
        test_file.write_text("x = safe_function()\n")
        rules = [PatternRule({"pattern": r"\beval\b", "reason": "No eval"})]
        errors = check_file_content(str(test_file), rules, [])
        assert len(errors) == 0

    def test_empty_rules(self, tmp_path: Path):
        test_file = tmp_path / "any.py"
        test_file.write_text("anything goes\n")
        errors = check_file_content(str(test_file), [], [])
        assert len(errors) == 0

    def test_multiple_violations(self, tmp_path: Path):
        test_file = tmp_path / "multi.py"
        test_file.write_text("eval(x)\nexec(y)\n")
        rules = [
            PatternRule({"pattern": r"\beval\b", "reason": "No eval"}),
            PatternRule({"pattern": r"\bexec\b", "reason": "No exec"}),
        ]
        errors = check_file_content(str(test_file), rules, [])
        assert len(errors) == EXPECTED_VIOLATION_COUNT

    def test_nonexistent_file(self):
        rules = [PatternRule({"pattern": r"test", "reason": "test"})]
        errors = check_file_content("/nonexistent/file.py", rules, [])
        assert len(errors) == 0  # Should handle gracefully


class TestCheckFilename:
    """Test filename pattern checking."""

    def test_banned_filename(self):
        rules = [PatternRule({"pattern": r"secret", "reason": "No secrets"})]
        errors = check_filename("path/to/secret_keys.py", rules)
        assert len(errors) >= 1

    def test_allowed_filename(self):
        rules = [PatternRule({"pattern": r"secret", "reason": "No secrets"})]
        errors = check_filename("path/to/config.py", rules)
        assert len(errors) == 0


class TestFindMatchingRules:
    """Test find_matching_rules helper."""

    def test_finds_matching(self):
        rules = [
            PatternRule({"pattern": "foo", "reason": "no foo"}),
            PatternRule({"pattern": "bar", "reason": "no bar"}),
        ]
        matches = find_matching_rules("foo bar", "test.py", rules)
        assert len(matches) == EXPECTED_MATCHING_RULES_COUNT

    def test_no_matches(self):
        rules = [PatternRule({"pattern": "baz", "reason": "no baz"})]
        matches = find_matching_rules("hello world", "test.py", rules)
        assert len(matches) == 0


class TestDirRules:
    """Test directory rule compilation and retrieval."""

    def test_compile_dir_rules(self):
        config = {
            "tests": [{"pattern": r"print\(", "reason": "No print in tests"}],
        }
        compiled = compile_dir_rules(config)
        assert "tests" in compiled
        assert len(compiled["tests"]) == 1
        assert isinstance(compiled["tests"][0], PatternRule)

    def test_get_dir_rules(self):
        compiled = compile_dir_rules(
            {
                "tests": [{"pattern": "print", "reason": "no print"}],
            }
        )
        rules = get_dir_rules("tests/unit/test_foo.py", compiled)
        assert len(rules) == 1

    def test_get_dir_rules_no_match(self):
        compiled = compile_dir_rules(
            {
                "tests": [{"pattern": "print", "reason": "no print"}],
            }
        )
        rules = get_dir_rules("ami/core/logic.py", compiled)
        assert len(rules) == 0


# ---------------------------------------------------------------------------
# check_file_length.py
# ---------------------------------------------------------------------------


class TestFileLength:
    """Test file length checking."""

    def test_file_within_limit(self, tmp_path: Path):
        test_file = tmp_path / "short.py"
        test_file.write_text("\n".join(f"line {i}" for i in range(10)))
        result = check_file_length(str(test_file), 512)
        assert result is None  # Within limit

    def test_file_exceeds_limit(self, tmp_path: Path):
        test_file = tmp_path / "long.py"
        test_file.write_text("\n".join(f"line {i}" for i in range(600)))
        result = check_file_length(str(test_file), 512)
        assert result is not None
        assert result == EXPECTED_LONG_FILE_LINES

    def test_exact_limit(self, tmp_path: Path):
        test_file = tmp_path / "exact.py"
        test_file.write_text("\n".join(f"line {i}" for i in range(512)))
        result = check_file_length(str(test_file), 512)
        assert result is None  # At limit, not over

    def test_nonexistent_file(self):
        result = check_file_length("/nonexistent/file.py", 512)
        assert result is None  # Handles gracefully

    def test_default_config_values(self):
        assert DEFAULT_CONFIG["max_lines"] == EXPECTED_MAX_LINES
        assert ".py" in DEFAULT_CONFIG["extensions"]
        assert ".git" in DEFAULT_CONFIG["ignore_dirs"]


class TestShouldCheckFile:
    """Test file filtering logic."""

    def test_python_file(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("pass")
        assert should_check_file(str(test_file), (".py",), set(), set()) is True

    def test_wrong_extension(self, tmp_path: Path):
        test_file = tmp_path / "readme.md"
        test_file.write_text("content")
        assert should_check_file(str(test_file), (".py",), set(), set()) is False

    def test_ignored_file(self, tmp_path: Path):
        test_file = tmp_path / "conftest.py"
        test_file.write_text("pass")
        assert (
            should_check_file(str(test_file), (".py",), {"conftest.py"}, set()) is False
        )

    def test_ignored_dir(self):
        assert (
            should_check_file(".venv/lib/test.py", (".py",), set(), {".venv"}) is False
        )


# ---------------------------------------------------------------------------
# check_init_files.py
# ---------------------------------------------------------------------------


class TestCheckInitFiles:
    """Test __init__.py content validation."""

    def test_empty_init(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text("")
        errors = check_init_file(str(init))
        assert len(errors) == 0

    def test_imports_only(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text(
            textwrap.dedent("""\
            from .module import MyClass
            import os
            __all__ = ["MyClass"]
        """)
        )
        errors = check_init_file(str(init))
        assert len(errors) == 0

    def test_function_definition_flagged(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text(
            textwrap.dedent("""\
            def helper():
                pass
        """)
        )
        errors = check_init_file(str(init))
        assert len(errors) >= 1
        assert "def " in errors[0] or "logic" in errors[0].lower()

    def test_class_definition_flagged(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text(
            textwrap.dedent("""\
            class MyPlugin:
                pass
        """)
        )
        errors = check_init_file(str(init))
        assert len(errors) >= 1

    def test_non_dunder_assignment_flagged(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text("x = 42\n")
        errors = check_init_file(str(init))
        assert len(errors) >= 1

    def test_dunder_assignment_allowed(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.0.0"\n')
        errors = check_init_file(str(init))
        assert len(errors) == 0

    def test_comments_allowed(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text("# This is a comment\n")
        errors = check_init_file(str(init))
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# block_coauthored.py
# ---------------------------------------------------------------------------


class TestBlockCoauthored:
    """Test co-author attribution detection."""

    def test_load_default_config(self):
        assert "forbidden_patterns" in BLOCK_COAUTHORED_DEFAULT_CONFIG
        assert (
            "Co-authored" + "-by:"
            in BLOCK_COAUTHORED_DEFAULT_CONFIG["forbidden_patterns"]
        )

    def test_detection_in_content(self):
        content = "Fix bug\n\n" + "Co-authored" + "-by: Bot <bot@example.com>"
        patterns = BLOCK_COAUTHORED_DEFAULT_CONFIG["forbidden_patterns"]
        found = any(p in content for p in patterns)
        assert found is True

    def test_clean_content(self):
        content = "Fix bug\n\nSigned-off-by: Dev <dev@example.com>"
        patterns = BLOCK_COAUTHORED_DEFAULT_CONFIG["forbidden_patterns"]
        found = any(p in content for p in patterns)
        assert found is False

    def test_load_config_missing_file(self):
        config = block_coauthored_load_config("/nonexistent/path.yaml")
        assert "forbidden_patterns" in config


# ---------------------------------------------------------------------------
# verify_coverage.py
# ---------------------------------------------------------------------------


class TestVerifyCoverage:
    """Test coverage verification config loading."""

    def test_load_default_config(self):
        assert "unit" in COVERAGE_DEFAULT_CONFIG
        assert "integration" in COVERAGE_DEFAULT_CONFIG
        assert COVERAGE_DEFAULT_CONFIG["unit"]["min_coverage"] == EXPECTED_UNIT_COVERAGE
        assert (
            COVERAGE_DEFAULT_CONFIG["integration"]["min_coverage"]
            == EXPECTED_INTEGRATION_COVERAGE
        )

    def test_load_config_from_missing_file(self):
        config = coverage_load_config("/nonexistent/coverage.yaml")
        assert "unit" in config  # Falls back to COVERAGE_DEFAULT_CONFIG

    def test_load_real_config(self, project_root: Path):
        config_path = str(project_root / "res" / "config" / "coverage_thresholds.yaml")
        config = coverage_load_config(config_path)
        assert isinstance(config, dict)

    def test_exit_code_constant(self):
        assert EXIT_CODE_COVERAGE_FAILURE == EXPECTED_EXIT_CODE_FAILURE
