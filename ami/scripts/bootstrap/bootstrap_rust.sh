#!/usr/bin/env bash

# Script to bootstrap Rust and Cargo
# Installs Rust toolchain into .boot-linux/rust using rustup

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
RUST_HOME="$BOOT_DIR/rust"

# Ensure .boot-linux exists
if [ ! -d "$BOOT_DIR" ]; then
    log_error ".boot-linux directory not found. Please run install first."
    exit 1
fi

# Check if already installed
if [ -x "$RUST_HOME/bin/rustc" ] && [ -x "$RUST_HOME/bin/cargo" ]; then
    EXISTING_VER=$("$RUST_HOME/bin/rustc" --version)
    log_info "Rust is already installed: $EXISTING_VER"
    exit 0
fi

log_info "Bootstrapping Rust toolchain..."

# Set rustup/cargo home to our isolated directory
export RUSTUP_HOME="$RUST_HOME"
export CARGO_HOME="$RUST_HOME"

# Create directory
mkdir -p "$RUST_HOME"

# Download and run rustup-init
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

cd "$TEMP_DIR"

log_info "Downloading rustup-init..."
if command -v curl >/dev/null 2>&1; then
    curl -sSf https://sh.rustup.rs -o rustup-init.sh
elif command -v wget >/dev/null 2>&1; then
    wget -q -O rustup-init.sh https://sh.rustup.rs
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Installing Rust (this may take a moment)..."
# Run rustup-init non-interactively
# -y: don't prompt
# --no-modify-path: don't touch shell profiles
# --default-toolchain stable: install stable Rust
sh rustup-init.sh -y --no-modify-path --default-toolchain stable

cd - >/dev/null

# Verify installation
if [ ! -x "$RUST_HOME/bin/rustc" ]; then
    log_error "rustc not found after installation"
    exit 1
fi

if [ ! -x "$RUST_HOME/bin/cargo" ]; then
    log_error "cargo not found after installation"
    exit 1
fi

log_success "Rust installed to $RUST_HOME"
"$RUST_HOME/bin/rustc" --version
"$RUST_HOME/bin/cargo" --version
