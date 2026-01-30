#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Python venv into .boot-linux using uv
# Creates .boot-linux/bin/python for use by other bootstrap scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if Python already exists
if [ -x "${BIN_DIR}/python" ]; then
    log_info "Python already installed at ${BIN_DIR}/python"
    "${BIN_DIR}/python" --version
    exit 0
fi

# Find uv - prefer .boot-linux/bin/uv, then PATH
if [ -x "${BIN_DIR}/uv" ]; then
    UV_CMD="${BIN_DIR}/uv"
elif command -v uv &> /dev/null; then
    UV_CMD="uv"
else
    log_error "uv not found. Run bootstrap_uv.sh first."
    exit 1
fi

log_info "Creating Python venv in ${BOOT_LINUX_DIR} using uv..."

# Create venv using uv (this creates bin/python, bin/pip, etc.)
"$UV_CMD" venv "${BOOT_LINUX_DIR}" --seed

# Verify
if [ -x "${BIN_DIR}/python" ]; then
    log_info "Python installed successfully at ${BIN_DIR}/python"
    "${BIN_DIR}/python" --version
else
    log_error "Python installation failed"
    exit 1
fi
