#!/usr/bin/env bash
# @name: ami-qwen
# @description: Qwen Code AI assistant
# @category: agents
# @binary: .venv/node_modules/.bin/qwen
# @features: -p, --resume, --yolo, mcp, extensions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-qwen() { \"$AMI_ROOT/.venv/node_modules/.bin/qwen\" \"\$@\"; }"
