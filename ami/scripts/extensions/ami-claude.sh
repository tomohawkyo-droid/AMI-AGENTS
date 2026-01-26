#!/usr/bin/env bash
# @name: ami-claude
# @description: Claude Code AI assistant
# @category: agents
# @binary: .venv/node_modules/.bin/claude
# @features: -p, --continue, --resume, --allowedTools
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-claude() { \"$AMI_ROOT/.venv/node_modules/.bin/claude\" \"\$@\"; }"
