"""Unit tests for ami/scripts/find_duplicates.py main() entrypoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.find_duplicates import main


class TestFindDuplicatesMain:
    def test_rejects_missing_dir(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "nope"
        with patch("sys.argv", ["find_duplicates", str(missing), str(tmp_path)]):
            main()
        assert (
            "Error: Both arguments must be valid directories" in capsys.readouterr().out
        )

    def test_reports_no_duplicates(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "x.txt").touch()
        (dir_b / "y.txt").touch()
        with patch("sys.argv", ["find_duplicates", str(dir_a), str(dir_b)]):
            main()
        assert "No duplicate filenames found." in capsys.readouterr().out

    def test_lists_duplicates_without_trash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "shared.txt").touch()
        (dir_b / "shared.txt").touch()
        with patch("sys.argv", ["find_duplicates", str(dir_a), str(dir_b)]):
            main()
        out = capsys.readouterr().out
        assert "Found 1 duplicate filenames" in out
        assert "shared.txt" in out
        # Nothing moved
        assert (dir_a / "shared.txt").exists()
        assert (dir_b / "shared.txt").exists()

    def test_moves_duplicates_to_trash(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "shared.txt").write_text("a")
        (dir_b / "shared.txt").write_text("b")
        with patch(
            "sys.argv",
            ["find_duplicates", str(dir_a), str(dir_b), "--trash"],
        ):
            main()
        out = capsys.readouterr().out
        assert "Moved 2 files to trash" in out
        assert (tmp_path / ".trash").is_dir()
        # Both duplicates moved out
        assert not (dir_a / "shared.txt").exists()
        assert not (dir_b / "shared.txt").exists()
