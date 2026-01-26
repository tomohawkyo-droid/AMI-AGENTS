#!/usr/bin/env bash
set -euo pipefail

# sd Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs sd (search & displace) in the .boot-linux environment
# FORCE INSTALLS TO .boot-linux - NO FALLBACKS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

BIN_DIR="${VENV_DIR}/bin"
mkdir -p "${BIN_DIR}"

SD_VERSION="v1.0.0"

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
        OS_TYPE="unknown-linux-musl" # Prefer musl for static linking
        ;;
    Darwin)
        OS_TYPE="apple-darwin"
        ;;
    *)
        log_error "Unsupported OS: ${OS}"
        exit 1
        ;;
esac

case "${ARCH}" in
    x86_64)
        ARCH_TYPE="x86_64"
        ;;
    aarch64|arm64)
        ARCH_TYPE="aarch64"
        ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

# Filename format: sd-v1.0.0-x86_64-unknown-linux-musl.tar.gz
BINARY_ARCHIVE="sd-${SD_VERSION}-${ARCH_TYPE}-${OS_TYPE}.tar.gz"
DOWNLOAD_URL="https://github.com/chmln/sd/releases/download/${SD_VERSION}/${BINARY_ARCHIVE}"
TARGET_PATH="${BIN_DIR}/sd"

log_info "Bootstrapping sd (${SD_VERSION}) into ${BIN_DIR}"
log_info "Downloading from ${DOWNLOAD_URL}..."

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if command -v curl &> /dev/null; then
    curl -L -o "${TEMP_DIR}/${BINARY_ARCHIVE}" "${DOWNLOAD_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${TEMP_DIR}/${BINARY_ARCHIVE}" "${DOWNLOAD_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Extracting ${BINARY_ARCHIVE}..."
tar -xzf "${TEMP_DIR}/${BINARY_ARCHIVE}" -C "${TEMP_DIR}"

# The archive contains a directory: sd-v1.0.0-x86_64-unknown-linux-musl/sd
EXTRACTED_DIR="${TEMP_DIR}/sd-${SD_VERSION}-${ARCH_TYPE}-${OS_TYPE}"
mv "${EXTRACTED_DIR}/sd" "${TARGET_PATH}"

chmod +x "${TARGET_PATH}"

# Verify
if "${TARGET_PATH}" --version > /dev/null 2>&1; then
    log_info "sd installed successfully: $(${TARGET_PATH} --version)"
    log_info "Location: ${TARGET_PATH}"
else
    log_error "sd installation failed or binary incompatible"
    rm -f "${TARGET_PATH}"
    exit 1
fi
