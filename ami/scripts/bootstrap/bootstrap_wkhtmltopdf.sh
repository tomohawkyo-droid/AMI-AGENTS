#!/usr/bin/env bash
set -euo pipefail

# wkhtmltopdf Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs wkhtmltopdf in the .boot-linux environment ONLY
# This script ensures wkhtmltopdf is available without requiring system-wide installation
# FORCE INSTALLS TO .boot-linux - NO FALLBACKS, NO .venv, ONLY .boot-linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

WKHTMLTOPDF_VERSION="0.12.6.1-3"
WKHTMLTOPDF_DIR="${VENV_DIR}/wkhtmltopdf"

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

# Check if running on Linux
if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "This script only supports Linux. For other platforms, install wkhtmltopdf manually."
    exit 1
fi

# Detect architecture
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64|amd64)
        WKHTMLTOPDF_ARCH="amd64"
        ;;
    aarch64|arm64)
        WKHTMLTOPDF_ARCH="arm64"
        ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

log_info "Bootstrapping wkhtmltopdf ${WKHTMLTOPDF_VERSION} for ${ARCH}"

# Required system dependencies for wkhtmltopdf (Qt/X11 libraries)
WKHTMLTOPDF_DEPS=(
    "libxrender1"
    "libfontconfig1"
    "libx11-6"
    "libxext6"
    "libxtst6"
    "fontconfig"
    "xfonts-base"
    "xfonts-75dpi"
    "libjpeg-turbo8"
)

# Check for missing dependencies
log_info "Checking system dependencies..."
MISSING_DEPS=()
for dep in "${WKHTMLTOPDF_DEPS[@]}"; do
    if ! dpkg -s "$dep" &>/dev/null; then
        MISSING_DEPS+=("$dep")
    fi
done

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    log_error "Missing ${#MISSING_DEPS[@]} required dependencies:"
    for dep in "${MISSING_DEPS[@]}"; do
        echo "  - $dep"
    done
    echo ""
    log_error "Run this command to install them:"
    echo ""
    echo "  sudo apt-get update && sudo apt-get install -y ${MISSING_DEPS[*]}"
    echo ""
    exit 1
fi

log_info "All dependencies present"

# Create wkhtmltopdf directory structure
mkdir -p "${WKHTMLTOPDF_DIR}"/bin
mkdir -p "${VENV_DIR}/bin"

# Download wkhtmltox from GitHub releases (jammy works on most Ubuntu versions)
WKHTMLTOPDF_URL="https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}.jammy_${WKHTMLTOPDF_ARCH}.deb"

log_info "Downloading wkhtmltopdf from ${WKHTMLTOPDF_URL}"

if command -v curl &> /dev/null; then
    curl -fL -o "${WKHTMLTOPDF_DIR}/wkhtmltox.deb" "${WKHTMLTOPDF_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${WKHTMLTOPDF_DIR}/wkhtmltox.deb" "${WKHTMLTOPDF_URL}"
else
    log_error "Neither curl nor wget found. Please install one of them."
    exit 1
fi

# Extract the package
cd "${WKHTMLTOPDF_DIR}"
ar x wkhtmltox.deb

# Extract binaries - wkhtmltox puts them in /usr/local/bin/
tar -xf data.tar.* -C "${WKHTMLTOPDF_DIR}"

# Find and move the binary
if [[ -f "${WKHTMLTOPDF_DIR}/usr/local/bin/wkhtmltopdf" ]]; then
    mv "${WKHTMLTOPDF_DIR}/usr/local/bin/wkhtmltopdf" "${WKHTMLTOPDF_DIR}/bin/"
    mv "${WKHTMLTOPDF_DIR}/usr/local/bin/wkhtmltoimage" "${WKHTMLTOPDF_DIR}/bin/" 2>/dev/null || true
    rm -rf "${WKHTMLTOPDF_DIR}/usr"
fi

# Create symlink in venv/bin
log_info "Creating symlink in ${VENV_DIR}/bin"
if [[ -f "${WKHTMLTOPDF_DIR}/bin/wkhtmltopdf" ]]; then
    ln -sf "${WKHTMLTOPDF_DIR}/bin/wkhtmltopdf" "${VENV_DIR}/bin/wkhtmltopdf"
elif [[ -f "${WKHTMLTOPDF_DIR}/wkhtmltopdf" ]]; then
    ln -sf "${WKHTMLTOPDF_DIR}/wkhtmltopdf" "${VENV_DIR}/bin/wkhtmltopdf"
else
    log_error "wkhtmltopdf binary not found in expected location"
    log_info "Available files in ${WKHTMLTOPDF_DIR}:"
    ls -la "${WKHTMLTOPDF_DIR}" 2>&1 || true
    exit 1
fi

# Clean up
rm -f "${WKHTMLTOPDF_DIR}/wkhtmltox.deb"
rm -f "${WKHTMLTOPDF_DIR}"/*.tar.*
rm -f "${WKHTMLTOPDF_DIR}"/control.tar.*
rm -f "${WKHTMLTOPDF_DIR}"/debian-binary

# Verify installation
log_info "Verifying wkhtmltopdf installation"

if [[ ! -x "${VENV_DIR}/bin/wkhtmltopdf" ]]; then
    log_error "wkhtmltopdf binary not found or not executable"
    exit 1
fi

if ! "${VENV_DIR}/bin/wkhtmltopdf" --version &>/dev/null; then
    log_error "wkhtmltopdf binary failed to execute"
    exit 1
fi

log_info "wkhtmltopdf installed and verified:"
"${VENV_DIR}/bin/wkhtmltopdf" --version

log_info "wkhtmltopdf bootstrap complete!"
log_info "Installed components:"
log_info "  - wkhtmltopdf ${WKHTMLTOPDF_VERSION}"
log_info "  - Binary: ${VENV_DIR}/bin/wkhtmltopdf"
log_info ""
log_info "To use wkhtmltopdf:"
log_info "  1. Run: ami-run wkhtmltopdf [args] (wkhtmltopdf auto-available)"
log_info "  2. Or use scripts directly that need wkhtmltopdf"
