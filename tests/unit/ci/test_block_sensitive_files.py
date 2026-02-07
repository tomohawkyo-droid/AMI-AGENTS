"""Unit tests for block_sensitive_files pre-commit hook."""

from unittest.mock import patch

from ami.scripts.ci.block_sensitive_files import (
    SAFE_EXCEPTIONS,
    SENSITIVE_EXTENSIONS,
    SENSITIVE_KEYWORDS,
    is_sensitive,
    main,
)


class TestIsSensitive:
    """Tests for is_sensitive function."""

    def test_safe_exceptions_always_allowed(self):
        """Test files in SAFE_EXCEPTIONS are never flagged."""
        for safe_file in SAFE_EXCEPTIONS:
            assert is_sensitive(safe_file) is False

    def test_hidden_files_with_sensitive_extensions(self):
        """Test hidden files with sensitive extensions are flagged."""
        assert is_sensitive(".env") is True
        assert is_sensitive(".env.local") is True
        assert is_sensitive(".secrets.yaml") is True
        assert is_sensitive(".config.json") is True

    def test_files_with_sensitive_keywords(self):
        """Test files with sensitive keywords in name are flagged."""
        assert is_sensitive("credentials.json") is True
        assert is_sensitive("secrets.yaml") is True
        assert is_sensitive("private_key.pem") is True
        assert is_sensitive("token.pickle") is True
        assert is_sensitive("password.env") is True

    def test_regular_code_files_not_flagged(self):
        """Test regular code files are not flagged."""
        assert is_sensitive("main.py") is False
        assert is_sensitive("test_utils.py") is False
        assert is_sensitive("README.md") is False
        assert is_sensitive("Makefile") is False

    def test_non_sensitive_extensions_not_flagged(self):
        """Test files with non-sensitive extensions are not flagged."""
        assert is_sensitive("app.py") is False
        assert is_sensitive("styles.css") is False
        assert is_sensitive("index.html") is False

    def test_sensitive_constants_defined(self):
        """Test that sensitive constants are properly defined."""
        assert ".env" in SENSITIVE_EXTENSIONS
        assert ".pem" in SENSITIVE_EXTENSIONS
        assert "secret" in SENSITIVE_KEYWORDS
        assert "password" in SENSITIVE_KEYWORDS


class TestMain:
    """Tests for main function."""

    def test_exits_zero_with_no_sensitive_files(self):
        """Test exits 0 when no sensitive files found."""
        with patch("sys.argv", ["hook", "main.py", "test.py"]), _expect_exit(0):
            main()

    def test_exits_one_with_sensitive_files(self, capsys):
        """Test exits 1 when sensitive files found."""
        with patch("sys.argv", ["hook", ".env"]), _expect_exit(1):
            main()

    def test_exits_zero_with_no_args(self):
        """Test exits 0 with no file arguments."""
        with patch("sys.argv", ["hook"]), _expect_exit(0):
            main()


class _expect_exit:
    """Context manager that expects sys.exit with a specific code."""

    def __init__(self, code: int):
        self.code = code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is SystemExit:
            assert exc_val.code == self.code
            return True
        return False
