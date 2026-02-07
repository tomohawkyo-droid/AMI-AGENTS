#!/usr/bin/env bash
set -euo pipefail

# AI Agents Bootstrap Script for AMI-ORCHESTRATOR
# Installs Node.js CLI agents (Claude, Gemini, Qwen) via package.json
# Wraps the logic in setup/node.sh to conform to the bootstrap script pattern

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Source the node setup script which contains the core logic
NODE_SETUP_SCRIPT="${PROJECT_ROOT}/ami/scripts/setup/node.sh"

if [ -f "$NODE_SETUP_SCRIPT" ]; then
    # shellcheck source=../../setup/node.sh
    source "$NODE_SETUP_SCRIPT"
else
    echo "ERROR: node.sh not found at $NODE_SETUP_SCRIPT"
    exit 1
fi

# Use the function from node.sh to install agents
# This ensures we use scripts/package.json as the single source of truth
install_node_agents
