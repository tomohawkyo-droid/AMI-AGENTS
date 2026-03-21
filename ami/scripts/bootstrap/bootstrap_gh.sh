#!/usr/bin/env bash
set -euo pipefail

# GitHub CLI Bootstrap Script for AMI-AGENTS
# Downloads and installs gh in the .boot-linux environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"
GH_DIR="${BOOT_DIR}/gh"
mkdir -p "${BIN_DIR}" "${GH_DIR}"

GH_VERSION="2.88.1"

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
    Linux)  OS_TYPE="linux" ;;
    Darwin) OS_TYPE="macOS" ;;
    *)
        log_error "Unsupported OS: ${OS}"
        exit 1
        ;;
esac

case "${ARCH}" in
    x86_64)        ARCH_TYPE="amd64" ;;
    aarch64|arm64) ARCH_TYPE="arm64" ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

ARCHIVE_NAME="gh_${GH_VERSION}_${OS_TYPE}_${ARCH_TYPE}.tar.gz"
DOWNLOAD_URL="https://github.com/cli/cli/releases/download/v${GH_VERSION}/${ARCHIVE_NAME}"

log_info "Bootstrapping gh ${GH_VERSION} (${OS_TYPE}/${ARCH_TYPE}) into ${GH_DIR}"
log_info "Downloading from ${DOWNLOAD_URL}..."

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if command -v curl &> /dev/null; then
    curl -L -o "${TEMP_DIR}/${ARCHIVE_NAME}" "${DOWNLOAD_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${TEMP_DIR}/${ARCHIVE_NAME}" "${DOWNLOAD_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Extracting ${ARCHIVE_NAME}..."
tar -xzf "${TEMP_DIR}/${ARCHIVE_NAME}" -C "${TEMP_DIR}"

# Move extracted directory contents to GH_DIR
EXTRACTED_DIR="${TEMP_DIR}/gh_${GH_VERSION}_${OS_TYPE}_${ARCH_TYPE}"
rm -rf "${GH_DIR:?}"/*
cp -r "${EXTRACTED_DIR}"/* "${GH_DIR}/"
chmod +x "${GH_DIR}/bin/gh"

# Symlink into bin/
ln -sf "../gh/bin/gh" "${BIN_DIR}/gh"

# Verify
if "${BIN_DIR}/gh" --version > /dev/null 2>&1; then
    log_info "gh installed successfully: $("${BIN_DIR}/gh" --version | head -n 1)"
    log_info "Location: ${BIN_DIR}/gh -> ${GH_DIR}/bin/gh"
else
    log_error "gh installation failed or binary incompatible"
    rm -f "${BIN_DIR}/gh"
    exit 1
fi
