#!/bin/bash
set -e

# Resolve the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "--- DISK CLEANUP STARTED ---"

if command -v uv &> /dev/null; then
    echo "[1/2] Cleaning 'uv' package cache (~24GB)..."
    uv cache clean
else
    echo "[WARN] 'uv' not found. Skipping cache clean."
fi

echo "[2/2] Cleaning Podman artifacts (~19GB)..."
# The python script is in prototypes/ relative to this script
python3 "$SCRIPT_DIR/prototypes/clean_disk_space.py" --force

echo "--- CLEANUP COMPLETE ---"
