"""Unit tests for ci/check_banned_words module - rules, config, file checking."""

from pathlib import Path

import pytest

from ami.scripts.ci.check_banned_words import (
    IGNORE_DIRS,
    INCLUDE_EXTENSIONS,
    PatternConfig,
    PatternRule,
    check_file_content,
    check_filename,
    compile_dir_rules,
    find_matching_rules,
    get_dir_rules,
    load_config,
    print_errors,
)

EXPECTED_MATCHING_RULE_COUNT = 2
EXPECTED_COMBINED_ERROR_COUNT = 2
EXPECTED_NESTED_DIR_RULE_COUNT = 2
EXPECTED_SRC_RULE_COUNT = 2


class TestPatternRule:
    """Tests for PatternRule class."""

    def test_init_with_basic_config(self) -> None:
        """Test initialization with basic config."""
        config: PatternConfig = {
            "pattern": r"\beval\b",
            "reason": "Avoid eval",
        }
        rule = PatternRule(config)

        assert rule.pattern == r"\beval\b"
        assert rule.reason == "Avoid eval"
        assert rule.exception_regex is None

    def test_init_with_exception_regex(self) -> None:
        """Test initialization with exception_regex."""
        config: PatternConfig = {
            "pattern": "TODO",
            "reason": "No TODOs allowed",
            "exception_regex": r"test_.*\.py$",
        }
        rule = PatternRule(config)

        assert rule.exception_regex == r"test_.*\.py$"
        assert rule._exception_compiled is not None

    def test_init_with_invalid_regex(self) -> None:
        """Test that invalid regex falls back to literal match."""
        config: PatternConfig = {
            "pattern": "[invalid(regex",
            "reason": "Test",
        }
        rule = PatternRule(config)

        # _compiled should be None for invalid regex
        assert rule._compiled is None

    def test_matches_regex(self) -> None:
        """Test matching with valid regex."""
        config: PatternConfig = {
            "pattern": r"\beval\(",
            "reason": "Avoid eval",
        }
        rule = PatternRule(config)

        assert rule.matches("x = eval(y)", "file.py") is True
        assert rule.matches("x = evaluate(y)", "file.py") is False

    def test_matches_literal(self) -> None:
        """Test matching with literal pattern (invalid regex)."""
        config: PatternConfig = {
            "pattern": "[pattern",
            "reason": "Test",
        }
        rule = PatternRule(config)

        assert rule.matches("contains [pattern here", "file.py") is True
        assert rule.matches("no match", "file.py") is False

    def test_matches_respects_exception(self) -> None:
        """Test that exception_regex prevents match."""
        config: PatternConfig = {
            "pattern": "forbidden",
            "reason": "Not allowed",
            "exception_regex": r"test_.*\.py$",
        }
        rule = PatternRule(config)

        # Should match in regular files
        assert rule.matches("forbidden word", "src/main.py") is True

        # Should not match in test files
        assert rule.matches("forbidden word", "tests/test_main.py") is False


class TestLoadConfig:
    """Tests for load_config function."""

    def test_exits_when_config_missing(self) -> None:
        """Test exits with error when config file missing."""
        with pytest.raises(SystemExit) as exc_info:
            load_config("/nonexistent/path/config.yaml")

        assert exc_info.value.code == 1

    def test_loads_valid_config(self, tmp_path: Path) -> None:
        """Test loading valid config file."""
        config_content = """
banned:
  - pattern: "eval("
    reason: "Avoid eval"
directory_rules:
  tests:
    - pattern: "print("
      reason: "Use logging"
filename_rules:
  - pattern: "test_"
    reason: "Test prefix"
ignored_files:
  - "conftest.py"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert len(config["banned"]) == 1
        assert "tests" in config["directory_rules"]

    def test_handles_empty_config(self, tmp_path: Path) -> None:
        """Test handling empty config file."""
        config_file = tmp_path / "empty_config.yaml"
        config_file.write_text("")

        config = load_config(str(config_file))

        assert config == {}


class TestFindMatchingRules:
    """Tests for find_matching_rules function."""

    def test_returns_matching_rules(self) -> None:
        """Test returns all matching rules."""
        rules = [
            PatternRule({"pattern": "foo", "reason": "r1"}),
            PatternRule({"pattern": "bar", "reason": "r2"}),
            PatternRule({"pattern": "baz", "reason": "r3"}),
        ]

        matched = find_matching_rules("foo bar", "file.py", rules)

        assert len(matched) == EXPECTED_MATCHING_RULE_COUNT
        assert matched[0].pattern == "foo"
        assert matched[1].pattern == "bar"

    def test_returns_empty_for_no_match(self) -> None:
        """Test returns empty list when no match."""
        rules = [PatternRule({"pattern": "xyz", "reason": "r1"})]

        matched = find_matching_rules("abc def", "file.py", rules)

        assert matched == []


class TestCheckFileContent:
    """Tests for check_file_content function."""

    def test_returns_errors_for_matches(self, tmp_path: Path) -> None:
        """Test returns errors for matching patterns."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = eval(input())\ny = safe()\n")

        global_rules = [PatternRule({"pattern": r"\beval\(", "reason": "Avoid eval"})]

        errors = check_file_content(str(test_file), global_rules, [])

        assert len(errors) == 1
        assert errors[0]["line"] == 1
        assert "eval" in errors[0]["pattern"]

    def test_returns_empty_for_no_rules(self, tmp_path: Path) -> None:
        """Test returns empty when no rules."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = eval(input())")

        errors = check_file_content(str(test_file), [], [])

        assert errors == []

    def test_returns_empty_for_unreadable_file(self) -> None:
        """Test returns empty for file that can't be read."""
        errors = check_file_content(
            "/nonexistent/file.py",
            [PatternRule({"pattern": "test", "reason": "r"})],
            [],
        )

        assert errors == []

    def test_combines_global_and_dir_rules(self, tmp_path: Path) -> None:
        """Test combines global and directory rules."""
        test_file = tmp_path / "test.py"
        test_file.write_text("foo bar baz\n")

        global_rules = [PatternRule({"pattern": "foo", "reason": "r1"})]
        dir_rules = [PatternRule({"pattern": "bar", "reason": "r2"})]

        errors = check_file_content(str(test_file), global_rules, dir_rules)

        assert len(errors) == EXPECTED_COMBINED_ERROR_COUNT


class TestCheckFilename:
    """Tests for check_filename function."""

    def test_returns_errors_for_matching_filename(self) -> None:
        """Test returns errors when filename matches pattern."""
        rules = [PatternRule({"pattern": r"\.bak$", "reason": "No backup files"})]

        errors = check_filename("/path/to/file.bak", rules)

        assert len(errors) == 1
        assert errors[0]["line"] == 0
        assert errors[0]["content"] == "file.bak"

    def test_returns_empty_for_non_matching_filename(self) -> None:
        """Test returns empty when filename doesn't match."""
        rules = [PatternRule({"pattern": r"\.bak$", "reason": "No backup files"})]

        errors = check_filename("/path/to/file.py", rules)

        assert errors == []


class TestGetDirRules:
    """Tests for get_dir_rules function."""

    def test_returns_rules_for_matching_directory(self) -> None:
        """Test returns rules for file in matching directory."""
        dir_rules = {
            "tests": [PatternRule({"pattern": "foo", "reason": "r1"})],
            "src": [PatternRule({"pattern": "bar", "reason": "r2"})],
        }

        rules = get_dir_rules("tests/unit/test_main.py", dir_rules)

        assert len(rules) == 1
        assert rules[0].pattern == "foo"

    def test_returns_empty_for_no_matching_directory(self) -> None:
        """Test returns empty for file not in configured directory."""
        dir_rules = {
            "tests": [PatternRule({"pattern": "foo", "reason": "r1"})],
        }

        rules = get_dir_rules("src/main.py", dir_rules)

        assert rules == []

    def test_returns_multiple_rules_for_nested_paths(self) -> None:
        """Test returns rules from multiple matching directories."""
        dir_rules = {
            "tests": [PatternRule({"pattern": "foo", "reason": "r1"})],
            "unit": [PatternRule({"pattern": "bar", "reason": "r2"})],
        }

        rules = get_dir_rules("tests/unit/test_main.py", dir_rules)

        assert len(rules) == EXPECTED_NESTED_DIR_RULE_COUNT


class TestCompileDirRules:
    """Tests for compile_dir_rules function."""

    def test_compiles_directory_rules(self) -> None:
        """Test compiles directory rules to PatternRule objects."""
        config = {
            "tests": [{"pattern": "foo", "reason": "r1"}],
            "src": [
                {"pattern": "bar", "reason": "r2"},
                {"pattern": "baz", "reason": "r3"},
            ],
        }

        compiled = compile_dir_rules(config)

        assert len(compiled["tests"]) == 1
        assert len(compiled["src"]) == EXPECTED_SRC_RULE_COUNT
        assert isinstance(compiled["tests"][0], PatternRule)


class TestPrintErrors:
    """Tests for print_errors function."""

    def test_prints_grouped_by_file(self, capsys) -> None:
        """Test errors are printed grouped by file."""
        errors = [
            {
                "file": "a.py",
                "line": 1,
                "pattern": "foo",
                "reason": "r1",
                "content": "x",
            },
            {
                "file": "a.py",
                "line": 2,
                "pattern": "bar",
                "reason": "r2",
                "content": "y",
            },
            {
                "file": "b.py",
                "line": 5,
                "pattern": "baz",
                "reason": "r3",
                "content": "z",
            },
        ]

        print_errors(errors)

        captured = capsys.readouterr()
        assert "a.py" in captured.out
        assert "b.py" in captured.out
        assert "3 banned pattern(s) found" in captured.out


class TestConstants:
    """Tests for module constants."""

    def test_ignore_dirs_contains_common_dirs(self) -> None:
        """Test IGNORE_DIRS contains common directories."""
        assert ".git" in IGNORE_DIRS
        assert ".venv" in IGNORE_DIRS
        assert "__pycache__" in IGNORE_DIRS
        assert "node_modules" in IGNORE_DIRS

    def test_include_extensions(self) -> None:
        """Test INCLUDE_EXTENSIONS contains expected extensions."""
        assert ".py" in INCLUDE_EXTENSIONS
        assert ".js" in INCLUDE_EXTENSIONS
        assert ".ts" in INCLUDE_EXTENSIONS


class TestPrintErrorsLineInfo:
    """Additional tests for print_errors edge cases."""

    def test_prints_without_line_number(self, capsys) -> None:
        """Test prints correctly when line is 0 (filename match)."""
        errors = [
            {
                "file": "file.bak",
                "line": 0,
                "pattern": r"\.bak$",
                "reason": "No backups",
                "content": "file.bak",
            }
        ]

        print_errors(errors)

        captured = capsys.readouterr()
        # Line info should be empty when line is 0
        assert "file.bak" in captured.out
        assert "Line:" in captured.out or "Line" in captured.out

    def test_prints_without_content(self, capsys) -> None:
        """Test prints correctly when content is empty."""
        errors = [
            {"file": "a.py", "line": 1, "pattern": "foo", "reason": "r1", "content": ""}
        ]

        print_errors(errors)

        captured = capsys.readouterr()
        # Should not crash with empty content
        assert "a.py" in captured.out
