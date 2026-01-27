"""Unit tests for ci/check_init_files module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.ci.check_init_files import (
    check_file,
    main,
)

EXPECTED_MIN_MULTIPLE_ERRORS = 3
EXPECTED_FILE_CHECK_COUNT = 3


class TestCheckFile:
    """Tests for check_file function."""

    def test_allows_empty_file(self, tmp_path: Path) -> None:
        """Test empty file passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_comments_only(self, tmp_path: Path) -> None:
        """Test file with only comments passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""# This is a comment
# Another comment
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_imports(self, tmp_path: Path) -> None:
        """Test file with imports passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""import os
from pathlib import Path
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_from_imports(self, tmp_path: Path) -> None:
        """Test file with from imports passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""from .module import SomeClass
from ..parent import other
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_dunder_all(self, tmp_path: Path) -> None:
        """Test file with __all__ passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""__all__ = ["module1", "module2"]
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_dunder_version(self, tmp_path: Path) -> None:
        """Test file with __version__ passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""__version__ = "1.0.0"
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_dunder_author(self, tmp_path: Path) -> None:
        """Test file with __author__ passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""__author__ = "Test Author"
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_allows_closing_brackets(self, tmp_path: Path) -> None:
        """Test file with closing brackets (multiline) passes."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""__all__ = [
    "module1",
    "module2",
]
""")

        errors = check_file(str(init_file))

        assert errors == []

    def test_detects_function_definition(self, tmp_path: Path) -> None:
        """Test detects function definition."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""def my_function():
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1
        assert "logic code" in errors[0]

    def test_detects_class_definition(self, tmp_path: Path) -> None:
        """Test detects class definition."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""class MyClass:
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1
        assert "logic code" in errors[0]

    def test_detects_if_statement(self, tmp_path: Path) -> None:
        """Test detects if statement."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""if True:
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1

    def test_detects_for_loop(self, tmp_path: Path) -> None:
        """Test detects for loop."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""for i in range(10):
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1

    def test_detects_while_loop(self, tmp_path: Path) -> None:
        """Test detects while loop."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""while True:
    break
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1

    def test_detects_try_block(self, tmp_path: Path) -> None:
        """Test detects try block."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""try:
    pass
except:
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) >= 1

    def test_detects_with_statement(self, tmp_path: Path) -> None:
        """Test detects with statement."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""with open("file") as f:
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1

    def test_detects_async_function(self, tmp_path: Path) -> None:
        """Test detects async function."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""async def my_async_func():
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1

    def test_detects_variable_assignment(self, tmp_path: Path) -> None:
        """Test detects non-dunder variable assignment."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""x = 1
""")

        errors = check_file(str(init_file))

        assert len(errors) == 1
        assert "variable assignment" in errors[0]

    def test_detects_multiple_errors(self, tmp_path: Path) -> None:
        """Test detects multiple errors."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""x = 1
y = 2
def func():
    pass
""")

        errors = check_file(str(init_file))

        assert len(errors) >= EXPECTED_MIN_MULTIPLE_ERRORS


class TestMain:
    """Tests for main function."""

    @patch("ami.scripts.ci.check_init_files.sys.argv", ["script"])
    def test_no_args_no_exit(self) -> None:
        """Test no exit when no files provided."""
        # Should not raise
        main()

    @patch("ami.scripts.ci.check_init_files.check_file")
    @patch(
        "ami.scripts.ci.check_init_files.sys.argv", ["script", "file1.py", "file2.py"]
    )
    def test_exits_one_when_errors_found(self, mock_check) -> None:
        """Test exits 1 when errors found."""
        mock_check.side_effect = [["Error 1"], []]

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("ami.scripts.ci.check_init_files.check_file")
    @patch("ami.scripts.ci.check_init_files.sys.argv", ["script", "file1.py"])
    def test_no_exit_when_no_errors(self, mock_check) -> None:
        """Test no exit when no errors."""
        mock_check.return_value = []

        # Should not raise
        main()

    @patch("ami.scripts.ci.check_init_files.check_file")
    @patch(
        "ami.scripts.ci.check_init_files.sys.argv", ["script", "a.py", "b.py", "c.py"]
    )
    def test_checks_all_files(self, mock_check) -> None:
        """Test checks all provided files."""
        mock_check.return_value = []

        main()

        assert mock_check.call_count == EXPECTED_FILE_CHECK_COUNT
