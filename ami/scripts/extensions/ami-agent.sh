#!/usr/bin/env bash
# @name: ami-agent
# @description: AMI Orchestrator main entry point
# @category: core
# @binary: ami-agent
# @features: interactive, bootloader, extensions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-agent() { \"$AMI_ROOT/ami-agent\" \"\$@\"; }"
