#!/usr/bin/env bash
# Utility wrappers for AMI Orchestrator

# General utility functions that provide access to specialized tools and services

ami-check-storage() {
    # Validate DataOps storage backends defined in storage-config.yaml
    # Checks that all configured storage backends are accessible and properly configured
    echo -e "${BLUE}Checking storage backends...${NC}"
    ami-run "$AGENTS_SCRIPTS/bin/check_storage.py" "$@"
}

ami-backup() {
    # Backup to Google Drive with default auth (typically OAuth)
    # Usage: ami-backup
    ami-run "$AGENTS_SCRIPTS/backup/backup_to_gdrive.py" "$@"
}

ami-restore() {
    # Selective restoration from Google Drive backup
    # Usage: ami-restore [options] <path> [path...]
    # Overwrites matching documents, restores deleted files, preserves new files
    ami-run "$AGENTS_SCRIPTS/backup/restore/main.py" "$@"
}

ami-package() {
    # Create a filtered package (raw or podman)
    # Usage: ami-package [source] -d [dest] [options]
    ami-run "$AGENTS_SCRIPTS/package/main.py" "$@"
}

ami-gcloud() {
    # Google Cloud SDK wrapper with local installation preference
    # Uses local .gcloud installation if available, otherwise falls back to system gcloud
    # This ensures consistent gcloud version across environments
    # Usage: ami-gcloud [gcloud-args]
    local gcloud_path

    # Check for local installation first
    if [[ -f "$AMI_ROOT/.gcloud/google-cloud-sdk/bin/gcloud" ]]; then
        gcloud_path="$AMI_ROOT/.gcloud/google-cloud-sdk/bin/gcloud"
    else
        # Fall back to system gcloud
        gcloud_path=$(which gcloud 2>/dev/null || echo "")
        if [[ -z "$gcloud_path" ]]; then
            echo -e "${RED}Error: gcloud not found${NC}"
            echo -e "Install gcloud SDK manually or via package manager"
            return 1
        fi
    fi

    echo -e "${BLUE}Running gcloud via:${NC} $gcloud_path"
    "$gcloud_path" "$@"
}
