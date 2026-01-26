#!/usr/bin/env bash
# @name: ami
# @description: Unified CLI for services and system management
# @category: core
# @binary: ami/scripts/bin/ami-run
# @features: ansible, systemd, podman, status
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami() { \"$AMI_ROOT/ami/scripts/bin/ami-run\" \"\$@\"; }"
