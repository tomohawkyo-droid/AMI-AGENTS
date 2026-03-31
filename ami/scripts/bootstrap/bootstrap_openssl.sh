#!/usr/bin/env bash
set -euo pipefail

# OpenSSL Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs OpenSSL binary to .boot-linux
# Ensures availability for secret generation without relying on system PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
OPENSSL_DIR="${BOOT_DIR}/openssl_tmp"
BIN_DIR="${BOOT_DIR}/bin"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "Linux only."
    exit 1
fi

mkdir -p "${OPENSSL_DIR}"
mkdir -p "${BIN_DIR}"

log_info "Downloading OpenSSL package..."
cd "${OPENSSL_DIR}"

# Download openssl binary package
if ! apt download openssl 2>/dev/null; then
    log_error "Failed to download openssl. Ensure apt is configured."
    exit 1
fi

log_info "Extracting..."
TMPEXT="$(mktemp -d)"
dpkg-deb -x openssl_*.deb "${TMPEXT}"

# Find and move binary
if [[ -f "${TMPEXT}/usr/bin/openssl" ]]; then
    cp "${TMPEXT}/usr/bin/openssl" "${BIN_DIR}/openssl"
    chmod +x "${BIN_DIR}/openssl"
    log_info "✓ Installed to ${BIN_DIR}/openssl"
else
    log_error "Could not find openssl binary in package."
    rm -rf "${TMPEXT}"
    exit 1
fi

# Cleanup
rm -rf "${TMPEXT}"
cd "${PROJECT_ROOT}"
rm -rf "${OPENSSL_DIR}"

# Verification
"${BIN_DIR}/openssl" version
log_info "OpenSSL bootstrap complete."
