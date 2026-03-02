#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Python venv into .boot-linux using uv
# Creates .boot-linux/bin/python for use by other bootstrap scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"
PYTHON_ENV="${BOOT_LINUX_DIR}/python-env"

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

# Check symlink target, not just bin/python
if [ -x "${PYTHON_ENV}/bin/python" ]; then
    log_info "Python already installed at ${PYTHON_ENV}"
    "${PYTHON_ENV}/bin/python" --version
    # Always recreate symlinks (fixes broken links after repo move)
    mkdir -p "${BIN_DIR}"
    ln -sf "${PYTHON_ENV}/bin/python" "${BIN_DIR}/python"
    ln -sf "${PYTHON_ENV}/bin/pip" "${BIN_DIR}/pip"
    exit 0
fi

# Find uv - must be in .boot-linux/bin
if [ -x "${BIN_DIR}/uv" ]; then
    UV_CMD="${BIN_DIR}/uv"
else
    log_error "uv not found at ${BIN_DIR}/uv. Run bootstrap_uv.sh first."
    exit 1
fi

log_info "Creating Python venv in ${PYTHON_ENV} using uv..."

# Create directories
mkdir -p "${BIN_DIR}"

# Create venv in subdirectory (not at .boot-linux root)
"$UV_CMD" venv "${PYTHON_ENV}" --seed

# Symlink to bin/ for compatibility with other scripts
ln -sf "${PYTHON_ENV}/bin/python" "${BIN_DIR}/python"
ln -sf "${PYTHON_ENV}/bin/pip" "${BIN_DIR}/pip"

# Verify
if [ -x "${BIN_DIR}/python" ]; then
    log_info "Python installed successfully"
    log_info "  Venv: ${PYTHON_ENV}"
    log_info "  Symlink: ${BIN_DIR}/python"
    "${BIN_DIR}/python" --version
else
    log_error "Python installation failed"
    exit 1
fi
