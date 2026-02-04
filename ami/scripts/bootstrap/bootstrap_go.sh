#!/usr/bin/env bash

# Script to bootstrap Go for the Matrix Compliance Test Suite
# Installs Go into .boot-linux/go

set -euo pipefail

# Logging functions
log_info() { echo "$1" >&2; }
log_error() { echo "ERROR: $1" >&2; }
log_success() { echo "✓ $1" >&2; }

# Calculate paths - script is in ami/scripts/bootstrap/, project root is 3 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
GO_DEST="$BOOT_DIR/go"
GO_VERSION="1.23.4" 

# Ensure .boot-linux exists
if [ ! -d "$BOOT_DIR" ]; then
    log_error ".boot-linux directory not found. Please run install first."
    exit 1
fi

if [ -d "$GO_DEST" ] && [ -x "$GO_DEST/bin/go" ]; then
    EXISTING_VER=$("$GO_DEST/bin/go" version)
    log_info "Go is already installed: $EXISTING_VER"
    exit 0
fi

log_info "Bootstrapping Go $GO_VERSION..."

# Detect Architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case $ARCH in
    x86_64)  GOARCH="amd64" ;;
    aarch64) GOARCH="arm64" ;;
    arm64)   GOARCH="arm64" ;;
    *)       log_error "Unsupported architecture: $ARCH"; exit 1 ;;
esac

TARBALL="go$GO_VERSION.$OS-$GOARCH.tar.gz"
URL="https://go.dev/dl/$TARBALL"

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

cd "$TEMP_DIR"

log_info "Downloading $URL..."
if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 -o "$TARBALL" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$TARBALL" "$URL"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Extracting..."
tar -xzf "$TARBALL"

# Move to destination
# tarball extracts to "go/" folder
if [ -d "$GO_DEST" ]; then
    rm -rf "$GO_DEST"
fi

mv go "$GO_DEST"
cd - >/dev/null

log_success "Go installed to $GO_DEST"
"$GO_DEST/bin/go" version

# Create symlinks in .boot-linux/bin/
BIN_DIR="${BOOT_DIR}/bin"
mkdir -p "${BIN_DIR}"

ln -sf "../go/bin/go" "${BIN_DIR}/go"
ln -sf "../go/bin/gofmt" "${BIN_DIR}/gofmt"

log_success "Go symlinks created in ${BIN_DIR}"
