#!/usr/bin/env bash
# @name: ami-run
# @description: Universal project execution wrapper
# @category: core
# @binary: ami/scripts/bin/ami-run
# @features: python, uv, podman, node, npm, npx, tests, ansible
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-run() { \"$AMI_ROOT/ami/scripts/bin/ami-run\" \"\$@\"; }"
