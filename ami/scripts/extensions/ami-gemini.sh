#!/usr/bin/env bash
# @name: ami-gemini
# @description: Gemini CLI AI assistant
# @category: agents
# @binary: .venv/node_modules/.bin/gemini
# @features: -p, --resume, --yolo, mcp, extensions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-gemini() { \"$AMI_ROOT/.venv/node_modules/.bin/gemini\" \"\$@\"; }"
