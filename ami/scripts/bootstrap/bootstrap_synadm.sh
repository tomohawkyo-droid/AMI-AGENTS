#!/usr/bin/env bash
set -euo pipefail

# Bootstrap synadm (Matrix Admin CLI) into .boot-linux
# Usage: ./scripts/bootstrap_synadm.sh

# Script is in ami/scripts/bootstrap/, project root is 3 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
PYTHON_CMD="$BOOT_LINUX_DIR/bin/python"

echo "Bootstrapping synadm..."

if [ ! -f "$PYTHON_CMD" ]; then
    echo "Error: .boot-linux python not found at $PYTHON_CMD"
    exit 1
fi

# Install synadm using pip (in boot-linux venv)
"$PYTHON_CMD" -m pip install synadm

# Create a simple wrapper in bin/ if it didn't get one
if [ ! -f "$BOOT_LINUX_DIR/bin/synadm" ]; then
    cat > "$BOOT_LINUX_DIR/bin/synadm" <<EOF
#!/bin/bash
"$PYTHON_CMD" -m synadm "\$@"
EOF
    chmod +x "$BOOT_LINUX_DIR/bin/synadm"
fi

echo "synadm installed in .boot-linux"
