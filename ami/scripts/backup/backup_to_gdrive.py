#!/usr/bin/env bash
# Backup AMI Orchestrator to Google Drive - see module docstring for details
"""'exec "$(dirname "$0")/../bin/ami-run" "$0" "$@" #"""

import sys

from ami.scripts.backup.create.main import main

__doc__ = """Backup AMI Orchestrator to Google Drive.

Creates a timestamped tar.zst archive (multi-threaded zstandard compression) of the entire
repository and uploads it to Google Drive. Uses OAuth as default for user accessibility.

Required packages (install separately):
    ami-run uv add google-auth==2.41.1
    ami-run uv add google-api-python-client==2.185.0
    ami-run uv add zstandard>=0.23.0

Authentication Setup:

OPTION 1: Regular User OAuth (DEFAULT & RECOMMENDED - User accessibility)
    Prerequisites:
        1. Create OAuth 2.0 Client ID in Google Cloud Console (Desktop application)
        2. Download credentials.json file
        3. Store credentials.json in the project root directory

    Configuration in .env:
        GDRIVE_AUTH_METHOD=oauth                           # Optional (default)
        GDRIVE_BACKUP_FOLDER_ID=folder-id                  # Optional
        GDRIVE_TOKEN_FILE=custom_token.pickle              # Optional (default: token.pickle)

    Setup Process:
        1. First run will open browser for authentication
        2. Token will be stored in token.pickle for subsequent runs
        3. Token will auto-refresh when expired

OPTION 2: Service Account Impersonation (For Google Workspace accounts)
    Prerequisites:
        1. Install gcloud CLI
        2. Authenticate: gcloud auth application-default login
        3. Grant impersonation permission:
           gcloud iam service-accounts add-iam-policy-binding \\
             SERVICE_ACCOUNT_EMAIL \\
             --member="user:YOUR_EMAIL" \\
             --role="roles/iam.serviceAccountTokenCreator"

    Configuration in .env:
        GDRIVE_AUTH_METHOD=impersonation                           # Required for impersonation auth
        GDRIVE_SERVICE_ACCOUNT_EMAIL=backup@project.iam.gserviceaccount.com  # Required
        GDRIVE_BACKUP_FOLDER_ID=folder-id                          # Optional
        GDRIVE_USER_APP_TOKEN_FILE=custom_user_app_token.pickle    # Optional (default: user_app_token.pickle)

OPTION 3: Service Account Keys (Less secure - only if you must)
    WARNING: Keys pose security risk if leaked. Use Option 1 if possible.

    Prerequisites:
        1. Create service account in Google Cloud Console
        2. Download JSON key file
        3. Store securely outside git (chmod 600)

    Configuration in .env:
        GDRIVE_AUTH_METHOD=key                                     # Required for key-based auth
        GDRIVE_CREDENTIALS_FILE=/path/to/service-account.json      # Required
        GDRIVE_BACKUP_FOLDER_ID=folder-id                          # Optional

OPTION 4: Pre-Registered Application OAuth (For application integration)
    Prerequisites:
        1. Use pre-registered application credentials

    Configuration in .env:
        GDRIVE_AUTH_METHOD=user_app                                # Required for user_app auth
        GDRIVE_USER_APP_TOKEN_FILE=custom_user_app_token.pickle    # Optional (default: user_app_token.pickle)

    Setup Process:
        1. First run will open browser for authentication
        2. Token will be stored in user_app_token.pickle for subsequent runs
        3. Token will auto-refresh when expired

Usage:
    scripts/backup_to_gdrive.py                       # Upload and delete local zip (default oauth)
    scripts/backup_to_gdrive.py --keep-local          # Upload and keep local zip
    scripts/backup_to_gdrive.py --setup-auth          # Set up authentication
    scripts/backup_to_gdrive.py --no-auth-retry       # Disable auth retry on failure
    scripts/backup_to_gdrive.py --auth-mode oauth     # Use OAuth authentication
    scripts/backup_to_gdrive.py --auth-mode impersonation  # Use service account impersonation
    scripts/backup_to_gdrive.py --auth-mode key       # Use service account keys
    scripts/backup_to_gdrive.py --auth-mode user_app  # Use pre-registered app
    scripts/backup_to_gdrive.py -h|--help             # Show this help
"""

if __name__ == "__main__":
    sys.exit(main())
