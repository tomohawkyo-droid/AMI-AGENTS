#!/usr/bin/env bash
# @name: ami-repo
# @description: Git repository and server management
# @category: core
# @binary: ami/scripts/bin/ami-repo
# @features: git, gitlab-api, github-api, hf-api
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-repo() { \"$AMI_ROOT/ami/scripts/bin/ami-repo\" \"\$@\"; }"
