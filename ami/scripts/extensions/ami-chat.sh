#!/usr/bin/env bash
# @name: ami-chat
# @description: Matrix CLI chat (matrix-commander)
# @category: enterprise
# @binary: .boot-linux/bin/matrix-commander
# @features: --message, --room, --listen, --tail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-chat() { \"$AMI_ROOT/.boot-linux/bin/matrix-commander\" \"\$@\"; }"
