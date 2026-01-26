"""Unit tests for backup configuration."""

import os

import pytest

from ami.scripts.backup.backup_config import BackupConfig
from ami.scripts.backup.backup_exceptions import BackupConfigError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Clear GDRIVE env vars before each test."""
    for key in list(os.environ.keys()):
        if key.startswith("GDRIVE_"):
            monkeypatch.delenv(key, raising=False)


class TestBackupConfig:
    """Test backup configuration loading."""

    def test_load_missing_env_file_raises(self, tmp_path):
        """Test that missing .env file raises BackupConfigError."""
        with pytest.raises(BackupConfigError) as exc_info:
            BackupConfig.load(tmp_path)

        assert ".env file not found" in str(exc_info.value)

    def test_load_with_env_file(self, tmp_path):
        """Test loading config from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("GDRIVE_AUTH_METHOD=oauth\n")

        config = BackupConfig.load(tmp_path)

        assert config.auth_method == "oauth"
        assert config.root_dir == tmp_path

    def test_load_invalid_auth_method_raises(self, tmp_path):
        """Test that invalid auth method raises BackupConfigError."""
        env_file = tmp_path / ".env"
        env_file.write_text("GDRIVE_AUTH_METHOD=invalid\n")

        with pytest.raises(BackupConfigError) as exc_info:
            BackupConfig.load(tmp_path)

        assert "Invalid GDRIVE_AUTH_METHOD" in str(exc_info.value)

    def test_load_impersonation_without_email_raises(self, tmp_path):
        """Test that impersonation without service account email raises."""
        env_file = tmp_path / ".env"
        env_file.write_text("GDRIVE_AUTH_METHOD=impersonation\n")

        with pytest.raises(BackupConfigError) as exc_info:
            BackupConfig.load(tmp_path)

        assert "GDRIVE_SERVICE_ACCOUNT_EMAIL" in str(exc_info.value)

    def test_load_key_without_credentials_file_raises(self, tmp_path):
        """Test that key auth without credentials file raises."""
        env_file = tmp_path / ".env"
        env_file.write_text("GDRIVE_AUTH_METHOD=key\n")

        with pytest.raises(BackupConfigError) as exc_info:
            BackupConfig.load(tmp_path)

        assert "GDRIVE_CREDENTIALS_FILE" in str(exc_info.value)

    def test_load_key_with_missing_credentials_file_raises(self, tmp_path):
        """Test that key auth with missing credentials file raises."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "GDRIVE_AUTH_METHOD=key\nGDRIVE_CREDENTIALS_FILE=/nonexistent/path.json\n"
        )

        with pytest.raises(BackupConfigError) as exc_info:
            BackupConfig.load(tmp_path)

        assert "Credentials file not found" in str(exc_info.value)

    def test_load_key_with_valid_credentials_file(self, tmp_path):
        """Test loading key auth with valid credentials file."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        env_file = tmp_path / ".env"
        env_file.write_text(
            f"GDRIVE_AUTH_METHOD=key\nGDRIVE_CREDENTIALS_FILE={creds_file}\n"
        )

        config = BackupConfig.load(tmp_path)

        assert config.auth_method == "key"
        assert config.credentials_file == str(creds_file)

    def test_load_folder_id(self, tmp_path):
        """Test loading folder ID from .env."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "GDRIVE_AUTH_METHOD=oauth\nGDRIVE_BACKUP_FOLDER_ID=folder123\n"
        )

        config = BackupConfig.load(tmp_path)

        assert config.folder_id == "folder123"

    def test_valid_auth_methods(self):
        """Test that valid auth methods constant is correct."""
        assert BackupConfig.VALID_AUTH_METHODS == ("impersonation", "key", "oauth")
