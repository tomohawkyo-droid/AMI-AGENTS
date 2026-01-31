#!/usr/bin/env bash
set -euo pipefail

# Bootstrap matrix-commander into .boot-linux
# Usage: ./scripts/bootstrap_matrix_commander.sh

# Script is in ami/scripts/bootstrap/, project root is 3 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
UV_CMD="$BOOT_LINUX_DIR/bin/uv"
PYTHON_ENV="$BOOT_LINUX_DIR/python-env"

echo "Bootstrapping matrix-commander..."

if [ ! -f "$UV_CMD" ]; then
    echo "Error: uv not found at $UV_CMD"
    exit 1
fi

# Install matrix-commander using uv pip into the boot-linux python env
"$UV_CMD" pip install --python "$PYTHON_ENV" matrix-commander

echo "matrix-commander installed in .boot-linux"
