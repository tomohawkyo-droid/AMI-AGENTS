#!/usr/bin/env bash
set -euo pipefail

# pdfjam Bootstrap Script for AMI-ORCHESTRATOR
# Installs pdfjam in the .boot-linux environment through TeXLive

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

TEXLIVE_DIR="${VENV_DIR}/texlive/texmf"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_info "Installing pdfjam through TeXLive package manager"

BINARY_BASE_DIR="${TEXLIVE_DIR}/bin"
TLGMGR=""
if [[ -f "${BINARY_BASE_DIR}/x86_64-linux/tlmgr" ]]; then
    TLGMGR="${BINARY_BASE_DIR}/x86_64-linux/tlmgr"
elif [[ -f "${BINARY_BASE_DIR}/aarch64-linux/tlmgr" ]]; then
    TLGMGR="${BINARY_BASE_DIR}/aarch64-linux/tlmgr"
else
    # Look for tlmgr in any architecture directory
    for arch_dir in "${BINARY_BASE_DIR}"/*; do
        if [[ -d "$arch_dir" && -f "$arch_dir/tlmgr" ]]; then
            TLGMGR="$arch_dir/tlmgr"
            break
        fi
    done
fi

if [[ -z "$TLGMGR" ]]; then
    log_error "Could not find tlmgr (TeXLive package manager)"
    exit 1
fi

# Install pdfjam package
log_info "Installing pdfjam package..."
"$TLGMGR" install pdfjam || {
    log_error "Failed to install pdfjam package"
    exit 1
}

# Create symlink for pdfjam in .boot-linux/bin
PDFJAM_BIN=""
if [[ -f "${BINARY_BASE_DIR}/x86_64-linux/pdfjam" ]]; then
    PDFJAM_BIN="${BINARY_BASE_DIR}/x86_64-linux/pdfjam"
elif [[ -f "${BINARY_BASE_DIR}/aarch64-linux/pdfjam" ]]; then
    PDFJAM_BIN="${BINARY_BASE_DIR}/aarch64-linux/pdfjam"
else
    # Look for pdfjam in any architecture directory
    for arch_dir in "${BINARY_BASE_DIR}"/*; do
        if [[ -d "$arch_dir" && -f "$arch_dir/pdfjam" ]]; then
            PDFJAM_BIN="$arch_dir/pdfjam"
            break
        fi
    done
fi

if [[ -n "$PDFJAM_BIN" ]]; then
    ln -sf "$PDFJAM_BIN" "${VENV_DIR}/bin/pdfjam"
    log_info "Created symlink for pdfjam"
else
    log_error "Could not find pdfjam binary after installation"
    exit 1
fi

log_info "pdfjam bootstrap complete!"
log_info "Installed components:"
log_info "  - pdfjam"
log_info "  - Binary: ${VENV_DIR}/bin/pdfjam"
log_info ""
log_info "To use pdfjam:"
log_info "  1. Run: ami-run pdfjam [args] (pdfjam auto-available)"
log_info "  2. Or use scripts directly that need pdfjam"