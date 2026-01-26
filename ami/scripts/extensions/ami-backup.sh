#!/usr/bin/env bash
# @name: ami-backup
# @description: Backup to Google Drive
# @category: dev
# @binary: ami/scripts/backup/create/main.py
# @features: --name, --keep-local, --dry-run
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-backup() { \"$AMI_ROOT/ami/scripts/bin/ami-run\" \"$AMI_ROOT/ami/scripts/backup/create/main.py\" \"\$@\"; }"
