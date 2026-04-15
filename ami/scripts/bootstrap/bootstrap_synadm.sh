#!/usr/bin/env bash
set -euo pipefail

# Bootstrap synadm (Matrix Admin CLI) into .boot-linux
# Usage: ./scripts/bootstrap_synadm.sh

# Script is in ami/scripts/bootstrap/, project root is 3 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
UV_CMD="$BOOT_LINUX_DIR/bin/uv"
PYTHON_ENV="$BOOT_LINUX_DIR/python-env"
PYTHON_CMD="$PYTHON_ENV/bin/python"

echo "Bootstrapping synadm..."

if [ ! -f "$UV_CMD" ]; then
    echo "Error: uv not found at $UV_CMD"
    exit 1
fi

# Install synadm using uv pip into the boot-linux python env
"$UV_CMD" pip install --python "$PYTHON_ENV" synadm

# Symlink the installed entry point to bin/
if [ -f "$PYTHON_ENV/bin/synadm" ] && [ ! -e "$BOOT_LINUX_DIR/bin/synadm" ]; then
    ln -sf "$PYTHON_ENV/bin/synadm" "$BOOT_LINUX_DIR/bin/synadm"
fi

echo "synadm installed in .boot-linux"
