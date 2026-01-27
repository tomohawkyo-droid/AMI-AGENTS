"""Unit tests for ci/verify_coverage module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.scripts.ci.verify_coverage import (
    DEFAULT_CONFIG,
    EXIT_CODE_COVERAGE_FAILURE,
    load_config,
    main,
    run_coverage,
)

EXPECTED_UNIT_MIN_COVERAGE = 90
EXPECTED_INTEGRATION_MIN_COVERAGE = 75
EXPECTED_COVERAGE_FAILURE_CODE = 2
EXPECTED_CUSTOM_UNIT_COVERAGE = 80
EXPECTED_CUSTOM_INTEGRATION_COVERAGE = 60


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_has_unit_config(self) -> None:
        """Test DEFAULT_CONFIG has unit test config."""
        assert "unit" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["unit"]["min_coverage"] == EXPECTED_UNIT_MIN_COVERAGE

    def test_has_integration_config(self) -> None:
        """Test DEFAULT_CONFIG has integration test config."""
        assert "integration" in DEFAULT_CONFIG
        expected = EXPECTED_INTEGRATION_MIN_COVERAGE
        assert DEFAULT_CONFIG["integration"]["min_coverage"] == expected

    def test_unit_path(self) -> None:
        """Test unit test path is correct."""
        assert DEFAULT_CONFIG["unit"]["path"] == "tests/unit"

    def test_integration_path(self) -> None:
        """Test integration test path is correct."""
        assert DEFAULT_CONFIG["integration"]["path"] == "tests/integration"


class TestExitCodeConstants:
    """Tests for exit code constants."""

    def test_coverage_failure_code(self) -> None:
        """Test EXIT_CODE_COVERAGE_FAILURE value."""
        assert EXIT_CODE_COVERAGE_FAILURE == EXPECTED_COVERAGE_FAILURE_CODE


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_default_when_file_missing(self) -> None:
        """Test returns default config when file doesn't exist."""
        with patch("ami.scripts.ci.verify_coverage.os.path.exists", return_value=False):
            config = load_config()

        assert config == DEFAULT_CONFIG

    def test_loads_from_file(self, tmp_path: Path) -> None:
        """Test loads config from file when it exists."""
        config_content = """
unit:
  path: "tests/unit"
  min_coverage: 80
  source_path: "src"
integration:
  path: "tests/integration"
  min_coverage: 60
  source_path: "src"
"""
        config_file = tmp_path / "coverage_thresholds.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config["unit"]["min_coverage"] == EXPECTED_CUSTOM_UNIT_COVERAGE
        expected = EXPECTED_CUSTOM_INTEGRATION_COVERAGE
        assert config["integration"]["min_coverage"] == expected


class TestRunCoverage:
    """Tests for run_coverage function."""

    @patch("ami.scripts.ci.verify_coverage.subprocess.run")
    def test_returns_true_on_success(self, mock_run) -> None:
        """Test returns True when tests pass."""
        mock_run.return_value = MagicMock(returncode=0)

        result = run_coverage("tests/unit", 90, "ami", "Unit")

        assert result is True

    @patch("ami.scripts.ci.verify_coverage.subprocess.run")
    def test_returns_false_on_test_failure(self, mock_run) -> None:
        """Test returns False when tests fail."""
        mock_run.return_value = MagicMock(returncode=1)

        result = run_coverage("tests/unit", 90, "ami", "Unit")

        assert result is False

    @patch("ami.scripts.ci.verify_coverage.subprocess.run")
    def test_returns_false_on_coverage_failure(self, mock_run) -> None:
        """Test returns False when coverage fails."""
        mock_run.return_value = MagicMock(returncode=EXIT_CODE_COVERAGE_FAILURE)

        result = run_coverage("tests/unit", 90, "ami", "Unit")

        assert result is False

    @patch("ami.scripts.ci.verify_coverage.subprocess.run")
    def test_builds_correct_command(self, mock_run) -> None:
        """Test builds correct pytest command."""
        mock_run.return_value = MagicMock(returncode=0)

        run_coverage("tests/unit", 90, "ami", "Unit")

        call_args = mock_run.call_args
        cmd = call_args[0][0]

        assert "pytest" in cmd
        assert "tests/unit" in cmd
        assert "--cov=ami" in cmd
        assert "--cov-fail-under=90" in cmd


class TestMain:
    """Tests for main function."""

    @patch("ami.scripts.ci.verify_coverage.run_coverage")
    @patch("ami.scripts.ci.verify_coverage.load_config")
    def test_exits_zero_when_all_pass(self, mock_config, mock_run) -> None:
        """Test exits 0 when all coverage checks pass."""
        mock_config.return_value = DEFAULT_CONFIG
        mock_run.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch("ami.scripts.ci.verify_coverage.run_coverage")
    @patch("ami.scripts.ci.verify_coverage.load_config")
    def test_exits_one_when_unit_fails(self, mock_config, mock_run) -> None:
        """Test exits 1 when unit tests fail."""
        mock_config.return_value = DEFAULT_CONFIG
        mock_run.side_effect = [False, True]  # Unit fails, integration passes

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("ami.scripts.ci.verify_coverage.run_coverage")
    @patch("ami.scripts.ci.verify_coverage.load_config")
    def test_exits_one_when_integration_fails(self, mock_config, mock_run) -> None:
        """Test exits 1 when integration tests fail."""
        mock_config.return_value = DEFAULT_CONFIG
        mock_run.side_effect = [True, False]  # Unit passes, integration fails

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("ami.scripts.ci.verify_coverage.run_coverage")
    @patch("ami.scripts.ci.verify_coverage.load_config")
    def test_exits_one_when_both_fail(self, mock_config, mock_run) -> None:
        """Test exits 1 when both fail."""
        mock_config.return_value = DEFAULT_CONFIG
        mock_run.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("ami.scripts.ci.verify_coverage.run_coverage")
    @patch("ami.scripts.ci.verify_coverage.load_config")
    def test_uses_config_values(self, mock_config, mock_run) -> None:
        """Test uses values from config."""
        custom_config = {
            "unit": {"path": "custom/unit", "min_coverage": 80, "source_path": "src"},
            "integration": {
                "path": "custom/integration",
                "min_coverage": 60,
                "source_path": "src",
            },
        }
        mock_config.return_value = custom_config
        mock_run.return_value = True

        with pytest.raises(SystemExit):
            main()

        # Check run_coverage was called with custom values
        calls = mock_run.call_args_list
        assert calls[0][0][0] == "custom/unit"
        assert calls[0][0][1] == EXPECTED_CUSTOM_UNIT_COVERAGE
        assert calls[1][0][0] == "custom/integration"
        assert calls[1][0][1] == EXPECTED_CUSTOM_INTEGRATION_COVERAGE
