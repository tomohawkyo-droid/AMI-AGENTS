#!/usr/bin/env bash
set -euo pipefail

# Cloudflared Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs cloudflared in the .boot-linux environment
# FORCE INSTALLS TO .boot-linux - NO FALLBACKS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

BIN_DIR="${VENV_DIR}/bin"
mkdir -p "${BIN_DIR}"

CLOUDFLARED_VERSION="latest"

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

# Detect OS and Architecture
OS="$(uname -s)"
ARCH="$(uname -m)"

case "${OS}" in
    Linux)
        OS_TYPE="linux"
        FILE_EXT=""
        ;;
    Darwin)
        OS_TYPE="darwin"
        FILE_EXT=".tgz"
        ;;
    *)
        log_error "Unsupported OS: ${OS}"
        exit 1
        ;;
esac

case "${ARCH}" in
    x86_64)
        ARCH_TYPE="amd64"
        ;;
    aarch64|arm64)
        ARCH_TYPE="arm64"
        ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

BINARY_NAME="cloudflared-${OS_TYPE}-${ARCH_TYPE}${FILE_EXT}"
DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/${CLOUDFLARED_VERSION}/download/${BINARY_NAME}"
TARGET_PATH="${BIN_DIR}/cloudflared"

log_info "Bootstrapping cloudflared (${OS_TYPE}/${ARCH_TYPE}) into ${BIN_DIR}"
log_info "Downloading from ${DOWNLOAD_URL}..."

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if command -v curl &> /dev/null; then
    curl -L -o "${TEMP_DIR}/${BINARY_NAME}" "${DOWNLOAD_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${TEMP_DIR}/${BINARY_NAME}" "${DOWNLOAD_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

if [[ "${FILE_EXT}" == ".tgz" ]]; then
    log_info "Extracting ${BINARY_NAME}..."
    tar -xzf "${TEMP_DIR}/${BINARY_NAME}" -C "${TEMP_DIR}"
    # The tarball contains a binary named 'cloudflared'
    mv "${TEMP_DIR}/cloudflared" "${TARGET_PATH}"
else
    mv "${TEMP_DIR}/${BINARY_NAME}" "${TARGET_PATH}"
fi

chmod +x "${TARGET_PATH}"

# Verify
if "${TARGET_PATH}" --version > /dev/null 2>&1; then
    log_info "cloudflared installed successfully: $(${TARGET_PATH} --version | head -n 1)"
    log_info "Location: ${TARGET_PATH}"
else
    log_error "cloudflared installation failed or binary incompatible"
    rm -f "${TARGET_PATH}"
    exit 1
fi