#!/usr/bin/env bash
# @name: ami-admin
# @description: Matrix Server Admin CLI (synadm)
# @category: enterprise
# @binary: .boot-linux/bin/synadm
# @features: user, room, media, version
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-admin() { \"$AMI_ROOT/.boot-linux/bin/synadm\" \"\$@\"; }"
