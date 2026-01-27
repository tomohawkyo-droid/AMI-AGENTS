"""Unit tests for ami/cli/env_utils.py."""

import os
from unittest.mock import MagicMock, patch

from ami.cli.env_utils import (
    drop_privileges,
    get_unprivileged_env,
)


class MockConfig:
    """Mock config object for testing."""

    def __init__(self, values: dict | None = None):
        self._values = values or {}

    def get_value(self, key: str, default=None):
        return self._values.get(key, default)


class TestDropPrivileges:
    """Tests for drop_privileges function."""

    def test_no_unprivileged_user_configured(self):
        """Test no action when no unprivileged user is configured."""
        config = MockConfig({"unprivileged_user": None})

        # Should not raise
        drop_privileges(config)

    def test_empty_unprivileged_user(self):
        """Test no action when unprivileged user is empty."""
        config = MockConfig({"unprivileged_user": ""})

        # Should not raise
        drop_privileges(config)

    @patch("pwd.getpwnam")
    @patch("os.setgid")
    @patch("os.setuid")
    @patch("os.getuid")
    @patch("os.getgid")
    def test_drop_privileges_success(
        self, mock_getgid, mock_getuid, mock_setuid, mock_setgid, mock_getpwnam
    ):
        """Test successful privilege drop."""
        mock_user_info = MagicMock()
        mock_user_info.pw_uid = 1000
        mock_user_info.pw_gid = 1000
        mock_getpwnam.return_value = mock_user_info
        mock_getuid.return_value = 1000
        mock_getgid.return_value = 1000

        config = MockConfig({"unprivileged_user": "testuser"})

        drop_privileges(config)

        mock_getpwnam.assert_called_once_with("testuser")
        mock_setgid.assert_called_once_with(1000)
        mock_setuid.assert_called_once_with(1000)

    @patch("pwd.getpwnam")
    @patch("os.setgid")
    @patch("os.setuid")
    @patch("os.getuid")
    @patch("os.getgid")
    def test_drop_privileges_verification_fails(
        self, mock_getgid, mock_getuid, mock_setuid, mock_setgid, mock_getpwnam
    ):
        """Test privilege drop verification failure."""
        mock_user_info = MagicMock()
        mock_user_info.pw_uid = 1000
        mock_user_info.pw_gid = 1000
        mock_getpwnam.return_value = mock_user_info
        # Verification should fail - UIDs don't match
        mock_getuid.return_value = 0
        mock_getgid.return_value = 0

        config = MockConfig({"unprivileged_user": "testuser"})

        # Should log error but not raise (errors are caught)
        drop_privileges(config)

    @patch("pwd.getpwnam", side_effect=KeyError("User not found"))
    def test_drop_privileges_user_not_found(self, mock_getpwnam):
        """Test handling when user is not found."""
        config = MockConfig({"unprivileged_user": "nonexistent"})

        # Should not raise, logs error
        drop_privileges(config)

    @patch("pwd.getpwnam")
    @patch("os.setgid", side_effect=PermissionError("Operation not permitted"))
    def test_drop_privileges_permission_error(self, mock_setgid, mock_getpwnam):
        """Test handling permission errors during privilege drop."""
        mock_user_info = MagicMock()
        mock_user_info.pw_uid = 1000
        mock_user_info.pw_gid = 1000
        mock_getpwnam.return_value = mock_user_info

        config = MockConfig({"unprivileged_user": "testuser"})

        # Should not raise, logs error
        drop_privileges(config)


class TestGetUnprivilegedEnv:
    """Tests for get_unprivileged_env function."""

    def test_no_unprivileged_user_returns_none(self):
        """Test returns None when no unprivileged user configured."""
        config = MockConfig({"unprivileged_user": None})

        result = get_unprivileged_env(config)

        assert result is None

    def test_empty_unprivileged_user_returns_none(self):
        """Test returns None when unprivileged user is empty."""
        config = MockConfig({"unprivileged_user": ""})

        result = get_unprivileged_env(config)

        assert result is None

    @patch("pwd.getpwnam")
    def test_returns_env_with_user_info(self, mock_getpwnam):
        """Test returns environment dict with user info."""
        mock_user_info = MagicMock()
        mock_user_info.pw_dir = "/tmp/testuser"
        mock_getpwnam.return_value = mock_user_info

        config = MockConfig({"unprivileged_user": "testuser"})

        result = get_unprivileged_env(config)

        assert result is not None
        assert result["HOME"] == "/tmp/testuser"
        assert result["USER"] == "testuser"
        assert "PYTHONUNBUFFERED" in result
        assert "FORCE_COLOR" in result

    @patch("pwd.getpwnam")
    @patch.dict(os.environ, {"DISABLE_AUTOUPDATER": "1"})
    def test_includes_disable_autoupdater(self, mock_getpwnam):
        """Test DISABLE_AUTOUPDATER is included when present."""
        mock_user_info = MagicMock()
        mock_user_info.pw_dir = "/tmp/testuser"
        mock_getpwnam.return_value = mock_user_info

        config = MockConfig({"unprivileged_user": "testuser"})

        result = get_unprivileged_env(config)

        assert result is not None
        assert result.get("DISABLE_AUTOUPDATER") == "1"

    @patch("pwd.getpwnam", side_effect=KeyError("User not found"))
    def test_user_not_found_returns_current_env(self, mock_getpwnam):
        """Test returns current environment when user not found."""
        config = MockConfig({"unprivileged_user": "nonexistent"})

        result = get_unprivileged_env(config)

        assert result is not None
        assert "PYTHONUNBUFFERED" in result
        assert "FORCE_COLOR" in result

    @patch("pwd.getpwnam")
    @patch.dict(os.environ, {"PATH": "/usr/bin", "LANG": "en_US.UTF-8"})
    def test_includes_path_and_lang(self, mock_getpwnam):
        """Test PATH and LANG are included from environment."""
        mock_user_info = MagicMock()
        mock_user_info.pw_dir = "/tmp/testuser"
        mock_getpwnam.return_value = mock_user_info

        config = MockConfig({"unprivileged_user": "testuser"})

        result = get_unprivileged_env(config)

        assert result is not None
        assert result["PATH"] == "/usr/bin"
        assert result["LANG"] == "en_US.UTF-8"


class TestConfigProtocol:
    """Tests for ConfigProtocol."""

    def test_mock_config_implements_protocol(self):
        """Test MockConfig can be used where ConfigProtocol is expected."""
        config = MockConfig({"key": "value"})

        # This should work with ConfigProtocol
        assert config.get_value("key") == "value"
        assert config.get_value("missing", "default") == "default"
