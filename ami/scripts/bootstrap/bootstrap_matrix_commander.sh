#!/usr/bin/env bash
set -euo pipefail

# Bootstrap matrix-commander into .boot-linux
# Usage: ./scripts/bootstrap_matrix_commander.sh

# Script is in ami/scripts/bootstrap/, project root is 3 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
PYTHON_CMD="$BOOT_LINUX_DIR/bin/python"

echo "Bootstrapping matrix-commander..."

if [ ! -f "$PYTHON_CMD" ]; then
    echo "Error: .boot-linux python not found at $PYTHON_CMD"
    exit 1
fi

# Install matrix-commander using pip (in boot-linux venv)
"$PYTHON_CMD" -m pip install matrix-commander

echo "matrix-commander installed in .boot-linux"
