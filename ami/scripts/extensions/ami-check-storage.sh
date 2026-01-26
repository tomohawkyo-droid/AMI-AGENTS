#!/usr/bin/env bash
# @name: ami-check-storage
# @description: Storage validation and monitoring
# @category: dev
# @binary: ami/scripts/bin/check_storage.py
# @features: disk, memory, alerts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-check-storage() { \"$AMI_ROOT/ami/scripts/bin/ami-run\" \"$AMI_ROOT/ami/scripts/bin/check_storage.py\" \"\$@\"; }"
