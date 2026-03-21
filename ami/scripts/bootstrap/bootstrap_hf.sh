#!/usr/bin/env bash
set -euo pipefail

# HuggingFace CLI Bootstrap Script for AMI-AGENTS
# Installs huggingface-cli into the .boot-linux python environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
UV_CMD="$BOOT_LINUX_DIR/bin/uv"
PYTHON_ENV="$BOOT_LINUX_DIR/python-env"
BIN_DIR="$BOOT_LINUX_DIR/bin"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_info "Bootstrapping huggingface-cli..."

if [ ! -f "$UV_CMD" ]; then
    log_error "uv not found at $UV_CMD"
    exit 1
fi

if [ ! -d "$PYTHON_ENV" ]; then
    log_error "Python env not found at $PYTHON_ENV"
    exit 1
fi

# Install huggingface_hub into the boot-linux python env (CLI is included by default)
"$UV_CMD" pip install --python "$PYTHON_ENV" huggingface_hub

# The CLI binary is installed as 'hf' in the python-env bin/
# Create symlink in boot-linux bin/ if not already there
if [ -f "${PYTHON_ENV}/bin/hf" ]; then
    ln -sf "../python-env/bin/hf" "${BIN_DIR}/hf"
elif [ -f "${PYTHON_ENV}/bin/huggingface-cli" ]; then
    ln -sf "../python-env/bin/huggingface-cli" "${BIN_DIR}/hf"
else
    log_error "No HuggingFace CLI binary found after install"
    exit 1
fi

# Verify
if "${BIN_DIR}/hf" version > /dev/null 2>&1; then
    log_info "huggingface-cli installed successfully: $("${BIN_DIR}/hf" version 2>&1 | head -n 1)"
    log_info "Location: ${BIN_DIR}/hf"
else
    log_error "huggingface-cli installation failed"
    rm -f "${BIN_DIR}/hf"
    exit 1
fi
