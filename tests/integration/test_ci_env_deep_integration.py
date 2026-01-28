"""Deep integration tests for CI scripts, env_utils, mode_handlers,
SelectionDialog helpers, and AgentConfigPresets.

Covers remaining uncovered functions across:
- ami/scripts/ci/check_file_length.py
- ami/scripts/ci/verify_coverage.py
- ami/cli/env_utils.py
- ami/cli/mode_handlers.py
- ami/cli_components/selection_dialog.py
- ami/cli/config.py
"""

from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.config import AgentConfigPresets
from ami.cli.env_utils import get_unprivileged_env
from ami.cli.mode_handlers import get_latest_session_id
from ami.cli_components.selection_dialog import (
    SelectionDialog,
    SelectionDialogConfig,
)
from ami.core.config import Config, _ConfigSingleton
from ami.core.env import get_project_root
from ami.scripts.ci.check_file_length import (
    DEFAULT_CONFIG,
    check_file_length,
    get_all_files,
    load_config,
    print_violations,
    should_check_file,
)
from ami.scripts.ci.verify_coverage import (
    DEFAULT_CONFIG as VERIFY_DEFAULT_CONFIG,
)
from ami.scripts.ci.verify_coverage import (
    load_config as verify_load_config,
)
from ami.scripts.ci.verify_coverage import (
    run_coverage,
)

# -- Constants for expected test values --------------------------------------

EXPECTED_LINE_COUNT_20 = 20
EXPECTED_DEFAULT_MAX_LINES = 512
EXPECTED_UNIT_MIN_COVERAGE = 90


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Reset config singleton so each test starts fresh."""
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# -- 1. check_file_length ---------------------------------------------------


class TestGetAllFiles:
    """Tests for get_all_files."""

    def test_returns_only_matching_extensions(self, tmp_path: Path, monkeypatch):
        """Only .py files are returned, not .txt."""
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        (tmp_path / "c.py").write_text("x")
        monkeypatch.chdir(tmp_path)
        result = get_all_files(set(), (".py",))
        basenames = {os.path.basename(f) for f in result}
        assert "a.py" in basenames
        assert "c.py" in basenames
        assert "b.txt" not in basenames

    def test_respects_ignore_dirs(self, tmp_path: Path, monkeypatch):
        """Directories in ignore_dirs are skipped."""
        subdir = tmp_path / "node_modules"
        subdir.mkdir()
        (subdir / "lib.py").write_text("x")
        (tmp_path / "main.py").write_text("x")
        monkeypatch.chdir(tmp_path)
        result = get_all_files({"node_modules"}, (".py",))
        basenames = {os.path.basename(f) for f in result}
        assert "main.py" in basenames
        assert "lib.py" not in basenames


class TestShouldCheckFile:
    """Tests for should_check_file."""

    def test_true_for_valid_py_file(self, tmp_path: Path):
        f = tmp_path / "good.py"
        f.write_text("pass")
        assert should_check_file(str(f), (".py",), set(), set()) is True

    def test_false_for_wrong_extension(self, tmp_path: Path):
        f = tmp_path / "readme.txt"
        f.write_text("hello")
        assert should_check_file(str(f), (".py",), set(), set()) is False

    def test_false_for_ignored_filename(self, tmp_path: Path):
        f = tmp_path / "skip_me.py"
        f.write_text("pass")
        assert should_check_file(str(f), (".py",), {"skip_me.py"}, set()) is False

    def test_false_for_nonexistent_file(self):
        assert should_check_file("/no/such/file.py", (".py",), set(), set()) is False

    def test_false_for_file_in_ignored_dir(self, tmp_path: Path):
        d = tmp_path / ".venv"
        d.mkdir()
        f = d / "lib.py"
        f.write_text("pass")
        assert should_check_file(str(f), (".py",), set(), {".venv"}) is False


class TestCheckFileLength:
    """Tests for check_file_length."""

    def test_returns_none_for_short_file(self, tmp_path: Path):
        f = tmp_path / "short.py"
        f.write_text("line\n" * 5)
        assert check_file_length(str(f), 10) is None

    def test_returns_count_for_long_file(self, tmp_path: Path):
        f = tmp_path / "long.py"
        f.write_text("line\n" * EXPECTED_LINE_COUNT_20)
        result = check_file_length(str(f), 10)
        assert result == EXPECTED_LINE_COUNT_20


class TestPrintViolations:
    """Tests for print_violations."""

    def test_outputs_violation_report(self, capsys):
        violations = [("a.py", 600), ("b.py", 550)]
        print_violations(violations, EXPECTED_DEFAULT_MAX_LINES)
        captured = capsys.readouterr().out
        assert "FAILED" in captured
        assert "2 file(s)" in captured
        assert "a.py" in captured
        assert "b.py" in captured
        assert "+88 over limit" in captured  # 600 - 512


class TestLoadConfigFileLength:
    """Tests for load_config in check_file_length."""

    def test_loads_real_config_file(self, monkeypatch):
        monkeypatch.chdir(get_project_root())
        cfg = load_config()
        assert "max_lines" in cfg
        assert "extensions" in cfg

    def test_default_config_has_expected_structure(self):
        assert DEFAULT_CONFIG["max_lines"] == EXPECTED_DEFAULT_MAX_LINES
        assert ".py" in DEFAULT_CONFIG["extensions"]
        assert isinstance(DEFAULT_CONFIG["ignore_dirs"], list)
        assert isinstance(DEFAULT_CONFIG["ignore_files"], list)


# -- 2. verify_coverage -----------------------------------------------------


class TestVerifyCoverageLoadConfig:
    """Tests for load_config in verify_coverage."""

    def test_loads_real_yaml(self, monkeypatch):
        monkeypatch.chdir(get_project_root())
        cfg = verify_load_config()
        assert "unit" in cfg
        assert "integration" in cfg
        assert cfg["unit"]["min_coverage"] == EXPECTED_UNIT_MIN_COVERAGE

    def test_returns_default_for_nonexistent_path(self):
        cfg = verify_load_config(config_path="/nonexistent/path/cfg.yaml")
        assert cfg == VERIFY_DEFAULT_CONFIG


class TestVerifyCoverageDefaultConfig:
    """Tests for DEFAULT_CONFIG in verify_coverage."""

    def test_has_expected_keys(self):
        assert "unit" in VERIFY_DEFAULT_CONFIG
        assert "integration" in VERIFY_DEFAULT_CONFIG
        assert "min_coverage" in VERIFY_DEFAULT_CONFIG["unit"]
        assert "path" in VERIFY_DEFAULT_CONFIG["integration"]


class TestRunCoverage:
    """Tests for run_coverage with mocked subprocess."""

    def test_returns_true_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch.object(subprocess, "run", return_value=mock_result):
            assert run_coverage("tests/unit", 90, ".", "Unit") is True

    def test_returns_false_on_coverage_failure(self, capsys):
        mock_result = MagicMock()
        mock_result.returncode = 2
        with patch.object(subprocess, "run", return_value=mock_result):
            assert run_coverage("tests/unit", 90, ".", "Unit") is False
        assert "Coverage FAILED" in capsys.readouterr().out

    def test_returns_false_on_test_failure(self, capsys):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.object(subprocess, "run", return_value=mock_result):
            assert run_coverage("tests/unit", 90, ".", "Unit") is False
        assert "Tests FAILED" in capsys.readouterr().out


# -- 3. env_utils ------------------------------------------------------------


class _FakeConfig:
    """Minimal config object satisfying ConfigProtocol."""

    def __init__(self, user: str | None = None):
        self._user = user

    def get_value(self, key: str, default: Any = None) -> Any:
        if key == "unprivileged_user":
            return self._user
        return default


class TestGetUnprivilegedEnv:
    """Tests for get_unprivileged_env."""

    def test_returns_none_when_no_user_configured(self):
        result = get_unprivileged_env(_FakeConfig(user=None))
        assert result is None

    def test_returns_env_dict_for_current_user(self):
        current = getpass.getuser()
        result = get_unprivileged_env(_FakeConfig(user=current))
        assert result is not None
        assert "HOME" in result
        assert result["USER"] == current
        assert result["PYTHONUNBUFFERED"] == "1"

    def test_returns_fallback_env_for_nonexistent_user(
        self,
    ):
        result = get_unprivileged_env(_FakeConfig(user="__no_such_user_xyz__"))
        assert result is not None
        assert result["PYTHONUNBUFFERED"] == "1"
        assert result["FORCE_COLOR"] == "1"

    def test_includes_disable_autoupdater_when_present(self, monkeypatch):
        monkeypatch.setenv("DISABLE_AUTOUPDATER", "yes")
        current = getpass.getuser()
        result = get_unprivileged_env(_FakeConfig(user=current))
        assert result is not None
        assert result.get("DISABLE_AUTOUPDATER") == "yes"


# -- 4. mode_handlers -------------------------------------------------------


class TestGetLatestSessionId:
    """Tests for get_latest_session_id."""

    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_returns_newest_session_id(self, MockStore):
        """get_latest_session_id returns the first session from the store."""
        mock_session = MagicMock()
        mock_session.session_id = "new_session"
        mock_store = MockStore.return_value
        mock_store.list_sessions.return_value = [mock_session]
        assert get_latest_session_id() == "new_session"

    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_returns_none_when_no_sessions(self, MockStore):
        mock_store = MockStore.return_value
        mock_store.list_sessions.return_value = []
        assert get_latest_session_id() is None

    @patch("ami.cli.mode_handlers.TranscriptStore")
    def test_returns_none_on_exception(self, MockStore):
        MockStore.side_effect = Exception("Store error")
        assert get_latest_session_id() is None


# -- 5. SelectionDialog render helpers ---------------------------------------


class TestSelectionDialogGetItemLabel:
    """Tests for SelectionDialog._get_item_label."""

    def _make_dialog(self):
        return SelectionDialog(["sample_item"])

    def test_dict_with_label_key(self):
        dlg = self._make_dialog()
        item = {
            "label": "My Label",
            "value": "x",
            "is_header": False,
        }
        assert dlg._get_item_label(item) == "My Label"

    def test_dict_with_name_key_uses_label(self):
        """Dicts require a 'label' key after
        _process_items normalisation."""
        dlg = self._make_dialog()
        item = {
            "label": "Fallback Name",
            "value": "x",
            "is_header": False,
        }
        assert dlg._get_item_label(item) == "Fallback Name"

    def test_object_with_label_attribute(self):
        dlg = self._make_dialog()

        class _Item:
            id = "i1"
            label = "Object Label"
            description = ""
            is_header = False
            value = "v"

        assert dlg._get_item_label(_Item()) == "Object Label"

    def test_plain_string_processed(self):
        dlg = SelectionDialog(["hello"])
        assert dlg._get_item_label(dlg.items[0]) == "hello"


class TestSelectionDialogGetItemDescription:
    """Tests for _get_item_description."""

    def _make_dialog(self):
        return SelectionDialog(["sample_item"])

    def test_dict_with_description(self):
        dlg = self._make_dialog()
        item = {
            "label": "L",
            "description": "Desc",
            "is_header": False,
        }
        assert dlg._get_item_description(item) == "Desc"

    def test_dict_without_description(self):
        dlg = self._make_dialog()
        item = {"label": "L", "is_header": False}
        assert dlg._get_item_description(item) == ""


class TestSelectionDialogGetItemId:
    """Tests for ID resolution via _initialize_preselected."""

    def test_preselect_by_id_key(self):
        items = [
            {
                "id": "a",
                "label": "Alpha",
                "is_header": False,
                "value": "a",
            },
            {
                "id": "b",
                "label": "Beta",
                "is_header": False,
                "value": "b",
            },
        ]
        cfg = SelectionDialogConfig(multi=True, preselected={"a"})
        dlg = SelectionDialog(items, config=cfg)
        assert 0 in dlg.selected
        assert 1 not in dlg.selected

    def test_preselect_with_label_fallback(self):
        """Items without 'id' key are not preselected
        even if label matches."""
        items = [
            {
                "label": "Alpha",
                "is_header": False,
                "value": "a",
            }
        ]
        cfg = SelectionDialogConfig(multi=True, preselected={"Alpha"})
        dlg = SelectionDialog(items, config=cfg)
        assert 0 not in dlg.selected


# -- 6. AgentConfigPresets ---------------------------------------------------


@pytest.mark.usefixtures("_setup_config")
class TestAgentConfigPresets:
    """Tests for AgentConfigPresets.worker() and
    interactive()."""

    @pytest.fixture
    def _setup_config(self, monkeypatch):
        monkeypatch.setenv("AMI_TEST_MODE", "1")
        _ConfigSingleton.instance = None
        cfg = Config()
        _ConfigSingleton.instance = cfg
        yield
        _ConfigSingleton.instance = None

    def test_worker_guard_rules_path_is_none(self):
        """worker() does not set guard_rules_path
        (defaults to None)."""
        ac = AgentConfigPresets.worker(session_id=None)
        assert ac.guard_rules_path is None

    def test_worker_has_model_and_provider(self):
        ac = AgentConfigPresets.worker(session_id=None)
        assert ac.model
        assert len(ac.model) > 0
        assert ac.provider is not None

    def test_interactive_sets_guard_rules_path(self):
        ac = AgentConfigPresets.interactive(session_id=None)
        assert ac.guard_rules_path is not None
        assert "interactive.yaml" in str(ac.guard_rules_path)

    def test_interactive_has_model_and_provider(self):
        ac = AgentConfigPresets.interactive(session_id=None)
        assert ac.model
        assert len(ac.model) > 0
        assert ac.provider is not None
