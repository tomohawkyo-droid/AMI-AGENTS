#!/usr/bin/env bash
set -euo pipefail

# UV Bootstrap Script for AMI-ORCHESTRATOR
# Downloads uv binary and installs to .boot-linux/bin

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"

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

# Check if uv is already installed in .boot-linux
if [ -x "${BIN_DIR}/uv" ]; then
    log_info "uv already installed at ${BIN_DIR}/uv"
    "${BIN_DIR}/uv" --version
    exit 0
fi

# Create directories
mkdir -p "${BIN_DIR}"

# Detect architecture and OS
ARCH=$(uname -m)
OS=$(uname -s)

case $OS in
    Linux*)
        PLATFORM="unknown-linux-gnu"
        ;;
    Darwin*)
        PLATFORM="apple-darwin"
        ;;
    *)
        log_error "Unsupported platform: $OS"
        exit 1
        ;;
esac

case $ARCH in
    x86_64*)
        ARCH="x86_64"
        ;;
    arm64*|aarch64*)
        ARCH="aarch64"
        ;;
    *)
        log_error "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Download uv binary
UV_BINARY_NAME="uv-$ARCH-$PLATFORM"
UV_FILE_NAME="$UV_BINARY_NAME.tar.gz"

log_info "Downloading uv for $ARCH-$PLATFORM..."

TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Try latest release first, fall back to specific version
if ! curl -LsSf "https://github.com/astral-sh/uv/releases/latest/download/$UV_FILE_NAME" -o "$UV_FILE_NAME" 2>/dev/null; then
    log_info "Latest version failed, trying stable version..."
    VERSION=$(curl -s https://api.github.com/repos/astral-sh/uv/releases/latest | grep '"tag_name"' | sed -E 's/.*"tag_name": "([^"]+)",.*/\1/')
    VERSION=${VERSION#v}
    curl -LsSf "https://github.com/astral-sh/uv/releases/download/$VERSION/$UV_FILE_NAME" -o "$UV_FILE_NAME"
fi

# Extract
tar -xzf "$UV_FILE_NAME"

# Find the uv binary (it's in a subdirectory)
if [ -d "$UV_BINARY_NAME" ]; then
    UV_BIN="$UV_BINARY_NAME/uv"
elif [ -f "uv" ]; then
    UV_BIN="uv"
else
    log_error "Could not find uv binary after extraction"
    ls -la
    cd - > /dev/null
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Install to .boot-linux/bin
chmod +x "$UV_BIN"
cp "$UV_BIN" "${BIN_DIR}/uv"

# Also copy uvx if present
if [ -f "${UV_BINARY_NAME}/uvx" ]; then
    chmod +x "${UV_BINARY_NAME}/uvx"
    cp "${UV_BINARY_NAME}/uvx" "${BIN_DIR}/uvx"
elif [ -f "uvx" ]; then
    chmod +x "uvx"
    cp "uvx" "${BIN_DIR}/uvx"
fi

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Verify installation
if [ -x "${BIN_DIR}/uv" ]; then
    log_info "uv installed successfully to ${BIN_DIR}/uv"
    "${BIN_DIR}/uv" --version
else
    log_error "uv installation failed"
    exit 1
fi
