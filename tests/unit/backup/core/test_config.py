"""Unit tests for backup/core/config module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.backup.backup_exceptions import BackupConfigError
from ami.scripts.backup.core.config import BackupRestoreConfig

EXPECTED_DEFAULT_TIMEOUT = 3600
EXPECTED_CUSTOM_TIMEOUT = 7200


class TestBackupRestoreConfigInit:
    """Tests for BackupRestoreConfig initialization."""

    def test_sets_default_restore_path(self, tmp_path: Path) -> None:
        """Test sets default restore path."""
        config = BackupRestoreConfig(tmp_path)

        assert config.restore_path == tmp_path / "_restored"

    def test_sets_default_timeout(self, tmp_path: Path) -> None:
        """Test sets default timeout."""
        config = BackupRestoreConfig(tmp_path)

        assert config.restore_timeout == EXPECTED_DEFAULT_TIMEOUT

    def test_sets_default_preserve_options(self, tmp_path: Path) -> None:
        """Test sets default preserve options."""
        config = BackupRestoreConfig(tmp_path)

        assert config.preserve_permissions is True
        assert config.preserve_timestamps is True


class TestBackupRestoreConfigLoad:
    """Tests for BackupRestoreConfig.load method."""

    @pytest.fixture(autouse=True)
    def _isolate_project_root(self, monkeypatch):
        """Prevent get_project_root from finding the real project root."""

        def _raise_runtime_error():
            raise RuntimeError

        monkeypatch.setattr(
            "ami.scripts.backup.common.paths.get_project_root",
            _raise_runtime_error,
        )

    def test_raises_error_when_env_missing(self, tmp_path: Path) -> None:
        """Test raises error when .env file missing."""
        with pytest.raises(BackupConfigError, match=r"\.env file not found"):
            BackupRestoreConfig.load(tmp_path)

    def test_raises_error_for_invalid_auth_method(self, tmp_path: Path) -> None:
        """Test raises error for invalid auth method."""
        env_file = tmp_path / ".env"
        env_file.write_text("GDRIVE_AUTH_METHOD=invalid")

        with pytest.raises(BackupConfigError, match="Invalid GDRIVE_AUTH_METHOD"):
            BackupRestoreConfig.load(tmp_path)

    @patch.dict(os.environ, {"GDRIVE_AUTH_METHOD": "oauth"}, clear=True)
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_loads_oauth_config(self, mock_dotenv, tmp_path: Path) -> None:
        """Test loads OAuth config."""
        env_file = tmp_path / ".env"
        env_file.write_text("GDRIVE_AUTH_METHOD=oauth")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.auth_method == "oauth"

    @patch.dict(
        os.environ,
        {
            "GDRIVE_AUTH_METHOD": "impersonation",
            "GDRIVE_SERVICE_ACCOUNT_EMAIL": "test@project.iam.gserviceaccount.com",
        },
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.find_gcloud")
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_loads_impersonation_config(
        self, mock_dotenv, mock_gcloud, tmp_path: Path
    ) -> None:
        """Test loads impersonation config."""
        mock_gcloud.return_value = "/usr/bin/gcloud"
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.auth_method == "impersonation"
        assert config.service_account_email == "test@project.iam.gserviceaccount.com"

    @patch.dict(os.environ, {"GDRIVE_AUTH_METHOD": "impersonation"}, clear=True)
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_raises_error_when_service_account_missing(
        self, mock_dotenv, tmp_path: Path
    ) -> None:
        """Test raises error when service account email missing for impersonation."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with pytest.raises(BackupConfigError, match="GDRIVE_SERVICE_ACCOUNT_EMAIL"):
            BackupRestoreConfig.load(tmp_path)

    @patch.dict(
        os.environ,
        {
            "GDRIVE_AUTH_METHOD": "impersonation",
            "GDRIVE_SERVICE_ACCOUNT_EMAIL": "test@project.iam.gserviceaccount.com",
        },
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.find_gcloud", return_value=None)
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_raises_error_when_gcloud_missing(
        self, mock_dotenv, mock_gcloud, tmp_path: Path
    ) -> None:
        """Test raises error when gcloud CLI not found."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with pytest.raises(BackupConfigError, match="gcloud CLI required"):
            BackupRestoreConfig.load(tmp_path)

    @patch.dict(os.environ, {"GDRIVE_AUTH_METHOD": "key"}, clear=True)
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_raises_error_when_credentials_file_missing(
        self, mock_dotenv, tmp_path: Path
    ) -> None:
        """Test raises error when credentials file path not set."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with pytest.raises(BackupConfigError, match="GDRIVE_CREDENTIALS_FILE"):
            BackupRestoreConfig.load(tmp_path)

    @patch.dict(
        os.environ,
        {
            "GDRIVE_AUTH_METHOD": "key",
            "GDRIVE_CREDENTIALS_FILE": "/nonexistent/credentials.json",
        },
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_raises_error_when_credentials_file_not_found(
        self, mock_dotenv, tmp_path: Path
    ) -> None:
        """Test raises error when credentials file doesn't exist."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with pytest.raises(BackupConfigError, match="Credentials file not found"):
            BackupRestoreConfig.load(tmp_path)

    @patch.dict(
        os.environ,
        {"GDRIVE_AUTH_METHOD": "key", "GDRIVE_CREDENTIALS_FILE": "credentials.json"},
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_loads_key_config_with_relative_path(
        self, mock_dotenv, tmp_path: Path
    ) -> None:
        """Test loads key config with relative credentials path."""
        env_file = tmp_path / ".env"
        env_file.write_text("")
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.auth_method == "key"
        assert config.credentials_file == str(creds_file)


class TestLoadRestoreConfig:
    """Tests for _load_restore_config method."""

    @pytest.fixture(autouse=True)
    def _isolate_project_root(self, monkeypatch):
        """Prevent get_project_root from finding the real project root."""

        def _raise_runtime_error():
            raise RuntimeError

        monkeypatch.setattr(
            "ami.scripts.backup.common.paths.get_project_root",
            _raise_runtime_error,
        )

    @patch.dict(os.environ, {"GDRIVE_AUTH_METHOD": "oauth"}, clear=True)
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_uses_default_restore_path(self, mock_dotenv, tmp_path: Path) -> None:
        """Test uses default restore path when not specified."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.restore_path == tmp_path / "_restored"

    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_uses_custom_restore_path(self, mock_dotenv, tmp_path: Path) -> None:
        """Test uses custom restore path from env."""
        custom_restore = tmp_path / "custom_restore"
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with patch.dict(
            os.environ,
            {"GDRIVE_AUTH_METHOD": "oauth", "RESTORE_PATH": str(custom_restore)},
            clear=True,
        ):
            config = BackupRestoreConfig.load(tmp_path)

        assert config.restore_path == custom_restore

    @patch.dict(
        os.environ,
        {"GDRIVE_AUTH_METHOD": "oauth", "RESTORE_TIMEOUT": "7200"},
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_uses_custom_timeout(self, mock_dotenv, tmp_path: Path) -> None:
        """Test uses custom timeout from env."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.restore_timeout == EXPECTED_CUSTOM_TIMEOUT

    @patch.dict(
        os.environ,
        {"GDRIVE_AUTH_METHOD": "oauth", "RESTORE_TIMEOUT": "invalid"},
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_raises_error_for_invalid_timeout(
        self, mock_dotenv, tmp_path: Path
    ) -> None:
        """Test raises error for invalid timeout value."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with pytest.raises(BackupConfigError, match="Invalid RESTORE_TIMEOUT"):
            BackupRestoreConfig.load(tmp_path)

    @patch.dict(
        os.environ,
        {"GDRIVE_AUTH_METHOD": "oauth", "RESTORE_PRESERVE_PERMISSIONS": "false"},
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_parses_preserve_permissions(self, mock_dotenv, tmp_path: Path) -> None:
        """Test parses preserve_permissions from env."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.preserve_permissions is False

    @patch.dict(
        os.environ,
        {"GDRIVE_AUTH_METHOD": "oauth", "RESTORE_PRESERVE_TIMESTAMPS": "no"},
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_parses_preserve_timestamps(self, mock_dotenv, tmp_path: Path) -> None:
        """Test parses preserve_timestamps from env."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.preserve_timestamps is False

    @patch.dict(
        os.environ,
        {
            "GDRIVE_AUTH_METHOD": "oauth",
            "RESTORE_PRESERVE_PERMISSIONS": "yes",
            "RESTORE_PRESERVE_TIMESTAMPS": "1",
        },
        clear=True,
    )
    @patch("ami.scripts.backup.core.config.load_dotenv")
    def test_parses_truthy_values(self, mock_dotenv, tmp_path: Path) -> None:
        """Test parses various truthy values."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = BackupRestoreConfig.load(tmp_path)

        assert config.preserve_permissions is True
        assert config.preserve_timestamps is True
