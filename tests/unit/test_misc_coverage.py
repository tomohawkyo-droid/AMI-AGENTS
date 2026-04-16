"""Unit tests for small modules with zero coverage."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.cli.constants import DEFAULT_MAX_WORKERS, DEFAULT_TIMEOUT
from ami.cli_components.confirmation_dialog import ConfirmationDialog, confirm
from ami.cli_components.dialogs import ConfirmationDialog as OriginalCD
from ami.cli_components.dialogs import confirm as original_confirm
from ami.cli_components.editor_saving import save_content
from ami.core.constants import COMMON_EXCLUDE_PATTERNS
from ami.core.utils import detect_language
from ami.scripts.find_duplicates import (
    DuplicateResult,
    FileEntry,
    _move_to_trash,
    find_duplicates,
    get_all_filenames,
    is_subdirectory,
)

# ---------------------------------------------------------------------------
# ami.core.constants
# ---------------------------------------------------------------------------


class TestCoreConstants:
    """Tests for ami.core.constants."""

    def test_common_exclude_patterns_is_list(self):
        assert isinstance(COMMON_EXCLUDE_PATTERNS, list)

    def test_common_exclude_patterns_nonempty(self):
        assert len(COMMON_EXCLUDE_PATTERNS) > 0

    def test_patterns_contain_git(self):
        assert any(".git" in p for p in COMMON_EXCLUDE_PATTERNS)

    def test_patterns_are_all_strings(self):
        assert all(isinstance(p, str) for p in COMMON_EXCLUDE_PATTERNS)


# ---------------------------------------------------------------------------
# ami.core.utils
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    """Tests for ami.core.utils.detect_language."""

    def test_python(self):
        assert detect_language(Path("foo.py")) == "python"

    def test_javascript(self):
        assert detect_language(Path("app.js")) == "javascript"

    def test_typescript(self):
        assert detect_language(Path("app.ts")) == "typescript"

    def test_tsx(self):
        assert detect_language(Path("comp.tsx")) == "typescript"

    def test_jsx(self):
        assert detect_language(Path("comp.jsx")) == "javascript"

    def test_rust(self):
        assert detect_language(Path("main.rs")) == "rust"

    def test_go(self):
        assert detect_language(Path("main.go")) == "go"

    def test_java(self):
        assert detect_language(Path("Main.java")) == "java"

    def test_cpp(self):
        assert detect_language(Path("main.cpp")) == "cpp"

    def test_c(self):
        assert detect_language(Path("main.c")) == "c"

    def test_csharp(self):
        assert detect_language(Path("Main.cs")) == "csharp"

    def test_ruby(self):
        assert detect_language(Path("app.rb")) == "ruby"

    def test_php(self):
        assert detect_language(Path("index.php")) == "php"

    def test_html(self):
        assert detect_language(Path("page.html")) == "html"

    def test_css(self):
        assert detect_language(Path("style.css")) == "css"

    def test_markdown(self):
        assert detect_language(Path("README.md")) == "markdown"

    def test_unknown_returns_none(self):
        assert detect_language(Path("data.xyz")) is None

    def test_case_insensitive(self):
        assert detect_language(Path("APP.PY")) == "python"


# ---------------------------------------------------------------------------
# ami.cli.constants
# ---------------------------------------------------------------------------


class TestCliConstants:
    """Tests for ami.cli.constants."""

    def test_default_max_workers(self):
        assert isinstance(DEFAULT_MAX_WORKERS, int)
        assert DEFAULT_MAX_WORKERS > 0

    def test_default_timeout(self):
        assert isinstance(DEFAULT_TIMEOUT, int)
        assert DEFAULT_TIMEOUT > 0

    def test_default_timeout_value(self):
        expected_one_hour = 60 * 60
        assert expected_one_hour == DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# ami.cli_components.confirmation_dialog (deprecated proxy)
# ---------------------------------------------------------------------------


class TestConfirmationDialogProxy:
    """Tests for the deprecated confirmation_dialog proxy module."""

    def test_reexports_confirmation_dialog_class(self):
        assert ConfirmationDialog is OriginalCD

    def test_reexports_confirm_function(self):
        assert confirm is original_confirm


# ---------------------------------------------------------------------------
# ami.cli_components.editor_saving
# ---------------------------------------------------------------------------


class TestEditorSaving:
    """Tests for ami.cli_components.editor_saving.save_content."""

    def test_join_lines(self):
        assert save_content(["a", "b", "c"], 0) == "a\nb\nc"

    def test_empty_list(self):
        assert save_content([], 0) == ""

    def test_single_line(self):
        assert save_content(["hello"], 5) == "hello"

    def test_cursor_line_ignored(self):
        result_a = save_content(["x", "y"], 0)
        result_b = save_content(["x", "y"], 99)
        assert result_a == result_b


# ---------------------------------------------------------------------------
# ami.scripts.find_duplicates
# ---------------------------------------------------------------------------


class TestFileEntry:
    """Tests for the FileEntry named tuple."""

    def test_create(self):
        entry = FileEntry(name="foo.txt", path="/tmp/foo.txt")
        assert entry.name == "foo.txt"
        assert entry.path == "/tmp/foo.txt"


class TestDuplicateResult:
    """Tests for the DuplicateResult named tuple."""

    def test_create(self):
        res = DuplicateResult(duplicates={"a"}, entries_a=[], entries_b=[])
        assert res.duplicates == {"a"}
        assert res.entries_a == []
        assert res.entries_b == []


class TestIsSubdirectory:
    """Tests for is_subdirectory."""

    def test_child_of_parent(self, tmp_path: Path):
        child = tmp_path / "sub"
        child.mkdir()
        assert is_subdirectory(tmp_path, child) is True

    def test_not_child(self, tmp_path: Path):
        unrelated = Path(tempfile.mkdtemp())
        assert is_subdirectory(tmp_path, unrelated) is False

    def test_same_directory(self, tmp_path: Path):
        assert is_subdirectory(tmp_path, tmp_path) is True


class TestGetAllFilenames:
    """Tests for get_all_filenames."""

    def test_collects_files(self, tmp_path: Path):
        (tmp_path / "readme.txt").touch()
        (tmp_path / "data.csv").touch()
        entries = get_all_filenames(tmp_path)
        names = {e.name for e in entries}
        assert "readme.txt" in names
        assert "data.csv" in names

    def test_skips_underscore_files(self, tmp_path: Path):
        (tmp_path / "__init__.py").touch()
        (tmp_path / "real.py").touch()
        entries = get_all_filenames(tmp_path)
        names = {e.name for e in entries}
        assert "__init__.py" not in names
        assert "real.py" in names

    def test_skips_hidden_dirs(self, tmp_path: Path):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.txt").touch()
        (tmp_path / "visible.txt").touch()
        entries = get_all_filenames(tmp_path)
        names = {e.name for e in entries}
        assert "secret.txt" not in names
        assert "visible.txt" in names

    def test_recurses_subdirectories(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").touch()
        entries = get_all_filenames(tmp_path)
        names = {e.name for e in entries}
        assert "deep.txt" in names

    def test_dir_to_skip(self, tmp_path: Path):
        skip = tmp_path / "skipme"
        skip.mkdir()
        (skip / "hidden.txt").touch()
        (tmp_path / "keep.txt").touch()
        entries = get_all_filenames(tmp_path, dir_to_skip=skip)
        names = {e.name for e in entries}
        assert "hidden.txt" not in names
        assert "keep.txt" in names


class TestFindDuplicates:
    """Tests for find_duplicates."""

    def test_finds_common_filenames(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "shared.txt").touch()
        (dir_a / "only_a.txt").touch()
        (dir_b / "shared.txt").touch()
        (dir_b / "only_b.txt").touch()

        res = find_duplicates(dir_a, dir_b)
        assert "shared.txt" in res.duplicates
        assert "only_a.txt" not in res.duplicates

    def test_no_duplicates(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "file_a.txt").touch()
        (dir_b / "file_b.txt").touch()

        res = find_duplicates(dir_a, dir_b)
        assert len(res.duplicates) == 0

    def test_subdirectory_case(self, tmp_path: Path):
        parent = tmp_path / "parent"
        parent.mkdir()
        child = parent / "child"
        child.mkdir()
        (parent / "file.txt").touch()
        (child / "file.txt").touch()

        res = find_duplicates(parent, child)
        # child is subdirectory of parent, so entries_b is empty
        assert res.entries_b == []


class TestMoveToTrash:
    """Tests for _move_to_trash."""

    def test_moves_matching_file(self, tmp_path: Path):
        src = tmp_path / "dup.txt"
        src.write_text("content")
        trash = tmp_path / "trash"
        trash.mkdir()

        entries = [FileEntry(name="dup.txt", path=str(src))]
        count = _move_to_trash("dup.txt", entries, trash)
        assert count == 1
        assert not src.exists()
        assert (trash / "dup.txt").exists()

    def test_handles_naming_conflict(self, tmp_path: Path):
        src = tmp_path / "dup.txt"
        src.write_text("new")
        trash = tmp_path / "trash"
        trash.mkdir()
        (trash / "dup.txt").write_text("old")

        entries = [FileEntry(name="dup.txt", path=str(src))]
        count = _move_to_trash("dup.txt", entries, trash)
        assert count == 1
        assert (trash / "dup_1.txt").exists()

    def test_no_match_returns_zero(self, tmp_path: Path):
        trash = tmp_path / "trash"
        trash.mkdir()
        entries = [FileEntry(name="other.txt", path="/nonexistent")]
        count = _move_to_trash("dup.txt", entries, trash)
        assert count == 0

    @patch("ami.scripts.find_duplicates.shutil.move", side_effect=OSError("fail"))
    def test_handles_move_error(self, mock_move: MagicMock, tmp_path: Path):
        trash = tmp_path / "trash"
        trash.mkdir()
        entries = [FileEntry(name="dup.txt", path="/tmp/dup.txt")]
        count = _move_to_trash("dup.txt", entries, trash)
        assert count == 0
