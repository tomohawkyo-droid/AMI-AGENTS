#!/usr/bin/env bash
set -euo pipefail

# Git LFS and Git Xet Bootstrap Script for AMI-ORCHESTRATOR
# Downloads git-lfs and git-xet binaries for HuggingFace large file support

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

mkdir -p "${BIN_DIR}"

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64*) ARCH="amd64" ;;
    arm64*|aarch64*) ARCH="arm64" ;;
    *) log_error "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# ==============================================================================
# Install git-lfs
# ==============================================================================
install_git_lfs() {
    if [ -x "${BIN_DIR}/git-lfs" ]; then
        log_info "git-lfs already installed"
        "${BIN_DIR}/git-lfs" --version
        return 0
    fi

    log_info "Installing git-lfs..."

    # Get latest version
    LFS_VERSION=$(curl -sS https://api.github.com/repos/git-lfs/git-lfs/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
    LFS_URL="https://github.com/git-lfs/git-lfs/releases/download/v${LFS_VERSION}/git-lfs-linux-${ARCH}-v${LFS_VERSION}.tar.gz"

    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    log_info "Downloading git-lfs v${LFS_VERSION}..."
    curl -LsSf "$LFS_URL" -o git-lfs.tar.gz
    tar -xzf git-lfs.tar.gz

    # Find and install binary
    if [ -f "git-lfs-${LFS_VERSION}/git-lfs" ]; then
        cp "git-lfs-${LFS_VERSION}/git-lfs" "${BIN_DIR}/git-lfs"
    elif [ -f "git-lfs" ]; then
        cp "git-lfs" "${BIN_DIR}/git-lfs"
    else
        log_error "Could not find git-lfs binary"
        cd - > /dev/null
        rm -rf "$TEMP_DIR"
        return 1
    fi

    chmod +x "${BIN_DIR}/git-lfs"
    cd - > /dev/null
    rm -rf "$TEMP_DIR"

    log_info "git-lfs installed successfully"
    "${BIN_DIR}/git-lfs" --version
}

# ==============================================================================
# Install git-xet
# ==============================================================================
install_git_xet() {
    if [ -x "${BIN_DIR}/git-xet" ]; then
        log_info "git-xet already installed"
        "${BIN_DIR}/git-xet" --version
        return 0
    fi

    log_info "Installing git-xet..."

    # git-xet uses different arch naming
    case $ARCH in
        amd64) XET_ARCH="x86_64" ;;
        arm64) XET_ARCH="aarch64" ;;
    esac

    XET_URL="https://github.com/huggingface/xet-tools/releases/latest/download/git-xet-${XET_ARCH}-unknown-linux-musl.tar.gz"

    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    log_info "Downloading git-xet..."
    curl -LsSf "$XET_URL" -o git-xet.tar.gz
    tar -xzf git-xet.tar.gz

    # Find and install binary
    if [ -f "git-xet" ]; then
        cp "git-xet" "${BIN_DIR}/git-xet"
    else
        log_error "Could not find git-xet binary"
        cd - > /dev/null
        rm -rf "$TEMP_DIR"
        return 1
    fi

    chmod +x "${BIN_DIR}/git-xet"
    cd - > /dev/null
    rm -rf "$TEMP_DIR"

    log_info "git-xet installed successfully"
    "${BIN_DIR}/git-xet" --version
}

# ==============================================================================
# Main
# ==============================================================================
install_git_lfs
install_git_xet

log_info "Git LFS and Xet tools installed to ${BIN_DIR}"
