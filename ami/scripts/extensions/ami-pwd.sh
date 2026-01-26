#!/usr/bin/env bash
# @name: ami-pwd
# @description: AMI root directory finder
# @category: core
# @binary: ami/scripts/bin/ami-pwd
# @features: find root, export AMI_ROOT
# @hidden: true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-pwd() { \"$AMI_ROOT/ami/scripts/bin/ami-pwd\" \"\$@\"; }"
