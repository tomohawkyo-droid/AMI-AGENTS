#!/usr/bin/env bash
set -euo pipefail

# ADB Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs Android Platform Tools to .boot-linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

BIN_DIR="${VENV_DIR}/bin"
mkdir -p "${BIN_DIR}"

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

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux)
        PLATFORM="linux"
        ;;
    Darwin)
        PLATFORM="darwin"
        ;;
    *)
        log_error "Unsupported OS: ${OS}"
        exit 1
        ;;
esac

URL="https://dl.google.com/android/repository/platform-tools-latest-${PLATFORM}.zip"
TARGET_PATH="${BIN_DIR}/adb"

log_info "Bootstrapping ADB into ${BIN_DIR}"
log_info "Downloading from ${URL}..."

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

curl -L -o "${TEMP_DIR}/tools.zip" "${URL}"
unzip -q "${TEMP_DIR}/tools.zip" -d "${TEMP_DIR}"

# Move binaries
mv "${TEMP_DIR}/platform-tools/adb" "${BIN_DIR}/"
mv "${TEMP_DIR}/platform-tools/fastboot" "${BIN_DIR}/"

chmod +x "${BIN_DIR}/adb" "${BIN_DIR}/fastboot"

# Verify
if "${BIN_DIR}/adb" version > /dev/null 2>&1; then
    log_info "ADB installed successfully: $(${BIN_DIR}/adb version | head -n 1)"
else
    log_error "ADB installation failed"
    exit 1
fi
