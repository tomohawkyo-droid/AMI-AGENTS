"""
Authentication module for backup/restore operations.

This module provides a unified interface for different authentication methods
used in backup and restore operations, including Google Drive authentication.
"""

import os
import pickle
from pathlib import Path
from typing import Protocol, cast

import google.auth
from google.auth import impersonated_credentials
from google.auth.credentials import Credentials as GoogleAuthCredentials
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ami.scripts.backup.backup_config import BackupConfig
from ami.scripts.backup.backup_exceptions import BackupConfigError, BackupError


class CredentialsProvider(Protocol):
    """Protocol for different types of credentials providers."""

    def get_credentials(self) -> GoogleAuthCredentials:
        """Get credentials for authentication."""
        ...


class ImpersonationCredentialsProvider:
    """Provides credentials through service account impersonation."""

    def __init__(self, config: BackupConfig):
        self.config = config

    def get_credentials(self) -> GoogleAuthCredentials:
        """Get impersonated credentials."""
        if not self.config.service_account_email:
            raise BackupConfigError(
                "Service account email is required for impersonation auth method"
            )

        try:
            # Get source credentials (user credentials from gcloud)
            auth_result = google.auth.default()
            source_creds = auth_result[0]

            # Impersonate the service account
            credentials = cast(
                GoogleAuthCredentials,
                impersonated_credentials.Credentials(
                    source_credentials=source_creds,
                    target_principal=self.config.service_account_email,
                    target_scopes=["https://www.googleapis.com/auth/drive"],
                    lifetime=3600,  # 1 hour
                ),
            )

            # Explicitly refresh to test if impersonation works
            request = Request()
            credentials.refresh(request)
        except Exception as e:
            raise BackupError(
                f"Failed to impersonate service account: {e}. "
                "Ensure you have roles/iam.serviceAccountTokenCreator permission"
            ) from e
        else:
            return credentials


class ServiceAccountCredentialsProvider:
    """Provides credentials from a service account key file."""

    def __init__(self, config: BackupConfig):
        self.config = config

    def get_credentials(self) -> GoogleAuthCredentials:
        """Get service account credentials from file."""
        if not self.config.credentials_file:
            raise BackupConfigError(
                "Credentials file path is required for key auth method"
            )

        credentials_file_path = Path(self.config.credentials_file)
        if not credentials_file_path.exists():
            raise BackupError(
                f"Credentials file does not exist: {credentials_file_path}"
            )

        return cast(
            GoogleAuthCredentials,
            ServiceAccountCredentials.from_service_account_file(
                credentials_file_path, scopes=["https://www.googleapis.com/auth/drive"]
            ),
        )


class OAuthCredentialsProvider:
    """Provides credentials through OAuth flow."""

    def __init__(self, config: BackupConfig):
        self.config = config

    def get_credentials(self) -> GoogleAuthCredentials:
        """Get OAuth credentials, either from existing token or by running auth flow."""
        scopes = ["https://www.googleapis.com/auth/drive"]

        creds = None
        # Allow custom token file path via environment variable, default to token.pickle
        token_filename = os.getenv("GDRIVE_TOKEN_FILE", "token.pickle")
        token_path = self.config.root_dir / token_filename

        # The file token.pickle stores the user's access and refresh tokens.
        if token_path.exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        # If there are no valid credentials available, request authorization
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh the token
                creds.refresh(Request())
            else:
                # Check if credentials.json exists for the OAuth flow
                credentials_json_path = self.config.root_dir / "credentials.json"
                if not credentials_json_path.exists():
                    raise BackupError(
                        f"credentials.json not found at {credentials_json_path}\n"
                        "For OAuth method, create credentials.json from Google Cloud Console.\n"
                        "Go to APIs & Services > Credentials, create OAuth 2.0 Client ID for Desktop application."
                    )

                # Use Local Server Flow (OOB is deprecated)
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_json_path), scopes
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        return cast(GoogleAuthCredentials, creds)


class AuthenticationManager:
    """Manages different authentication methods for backup/restore operations."""

    def __init__(self, config: BackupConfig):
        self.config = config
        self._provider = self._create_provider()

    def _create_provider(self) -> CredentialsProvider:
        """Create the appropriate credentials provider based on auth method."""
        if self.config.auth_method == "impersonation":
            return ImpersonationCredentialsProvider(self.config)
        elif self.config.auth_method == "key":
            return ServiceAccountCredentialsProvider(self.config)
        elif self.config.auth_method == "oauth":
            return OAuthCredentialsProvider(self.config)
        else:
            raise BackupConfigError(f"Unknown auth method: {self.config.auth_method}")

    def update_config(self, config: BackupConfig) -> None:
        """Update the configuration and recreate the provider."""
        self.config = config
        self._provider = self._create_provider()

    def get_credentials(self) -> GoogleAuthCredentials:
        """Get credentials based on the configured method."""
        return self._provider.get_credentials()
