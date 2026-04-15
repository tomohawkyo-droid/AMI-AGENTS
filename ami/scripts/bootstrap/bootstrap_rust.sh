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

# Check if already installed AND working (toolchain must be configured)
if [ -x "$RUST_HOME/bin/rustc" ] && [ -x "$RUST_HOME/bin/cargo" ]; then
    export RUSTUP_HOME="$RUST_HOME"
    export CARGO_HOME="$RUST_HOME"
    if EXISTING_VER=$("$RUST_HOME/bin/rustc" --version 2>/dev/null); then
        log_info "Rust is already installed: $EXISTING_VER"
        exit 0
    else
        log_info "Rust binaries exist but toolchain is broken, reinstalling..."
        rm -rf "$RUST_HOME"
    fi
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

# Check if a C linker is available (required by Rust toolchain)
if ! command -v cc &>/dev/null && ! command -v gcc &>/dev/null && ! command -v clang &>/dev/null; then
    log_error "No C compiler (cc/gcc/clang) found — required by Rust toolchain."
    log_error "Run: sudo make pre-req"
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

# Bootstrap glibc GCC if not present — required as Rust's linker driver
# (.boot-linux/bin/gcc is musl, which is incompatible with Rust's glibc toolchain)
if [ ! -x "$BOOT_DIR/bin/gcc-glibc" ]; then
    log_info "Bootstrapping glibc GCC for Rust linker..."
    bash "$SCRIPT_DIR/bootstrap_gcc_glibc.sh"
fi

# Configure cargo to use glibc GCC as the linker for x86_64-unknown-linux-gnu
# Use just the binary name — gcc-glibc is in .boot-linux/bin/ which is in $PATH
cat > "$RUST_HOME/config.toml" << 'TOML'
[target.x86_64-unknown-linux-gnu]
linker = "gcc-glibc"
TOML
log_success "Global cargo config created (glibc gcc linker for x86_64-unknown-linux-gnu)"

# Install additional components required for development tooling
log_info "Installing additional Rust components..."
"$RUST_HOME/bin/rustup" component add llvm-tools-preview rust-src
log_success "Components installed: llvm-tools-preview, rust-src"

# Detect the active toolchain directory name
TOOLCHAIN_NAME=$("$RUST_HOME/bin/rustup" toolchain list | grep '(default)' | awk '{print $1}')
if [ -z "$TOOLCHAIN_NAME" ]; then
    TOOLCHAIN_NAME="stable-x86_64-unknown-linux-gnu"
fi
TOOLCHAIN_DIR="rust/toolchains/${TOOLCHAIN_NAME}"
TOOLCHAIN_BIN="${TOOLCHAIN_DIR}/bin"
TOOLCHAIN_LLVM_BIN="${TOOLCHAIN_DIR}/lib/rustlib/x86_64-unknown-linux-gnu/bin"

# Create symlinks in .boot-linux/bin/
BIN_DIR="${BOOT_DIR}/bin"
mkdir -p "${BIN_DIR}"

# Rustup proxy (for `cargo +toolchain` dispatch)
ln -sf "../rust/bin/rustup" "${BIN_DIR}/rustup"

# Core Rust binaries
for bin in cargo rustc rustfmt cargo-clippy cargo-fmt clippy-driver rustdoc; do
    if [ -x "${BOOT_DIR}/${TOOLCHAIN_BIN}/${bin}" ]; then
        ln -sf "../${TOOLCHAIN_BIN}/${bin}" "${BIN_DIR}/${bin}"
    fi
done

# LLVM tools (llvm-profdata, llvm-cov, llvm-ar, etc.)
# Required by cargo-llvm-cov and other instrumentation tools
if [ -d "${BOOT_DIR}/${TOOLCHAIN_LLVM_BIN}" ]; then
    for bin in "${BOOT_DIR}/${TOOLCHAIN_LLVM_BIN}"/*; do
        [ -x "$bin" ] || continue
        [ -d "$bin" ] && continue  # skip gcc-ld directory
        bin_name="$(basename "$bin")"
        ln -sf "../${TOOLCHAIN_LLVM_BIN}/${bin_name}" "${BIN_DIR}/${bin_name}"
    done
    log_success "LLVM tool symlinks created (llvm-profdata, llvm-cov, etc.)"
else
    log_info "Warning: LLVM tools directory not found at ${TOOLCHAIN_LLVM_BIN}"
fi

log_success "Rust symlinks created in ${BIN_DIR}"
