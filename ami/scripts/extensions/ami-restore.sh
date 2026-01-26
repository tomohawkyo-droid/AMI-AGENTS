#!/usr/bin/env bash
# @name: ami-restore
# @description: Restore from Google Drive
# @category: dev
# @binary: ami/scripts/backup/restore/main.py
# @features: --file-id, --latest-local, --local-path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-restore() { \"$AMI_ROOT/ami/scripts/bin/ami-run\" \"$AMI_ROOT/ami/scripts/backup/restore/main.py\" \"\$@\"; }"
