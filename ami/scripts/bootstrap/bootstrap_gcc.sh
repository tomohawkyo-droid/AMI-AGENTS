#!/usr/bin/env bash
set -euo pipefail

# GCC/musl Bootstrap Script for AMI-ORCHESTRATOR
# Downloads pre-built static GCC 15.1.0 + musl libc toolchain from Dyne.org
# Provides a compatible C compiler without requiring apt/sudo
#
# Direct download: https://dl.dyne.org/musl
# No system dependencies needed — fully self-contained static toolchain

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"
GCC_MUSL_DIR="${BOOT_LINUX_DIR}/gcc-musl"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check if already installed
if [[ -x "${GCC_MUSL_DIR}/bin/gcc" ]]; then
    VERSION=$("${GCC_MUSL_DIR}/bin/gcc" --version 2>&1 | head -n1)
    log_info "GCC/musl already installed: $VERSION"
    exit 0
fi

log_info "Bootstrapping GCC/musl static toolchain for x86_64"

mkdir -p "${GCC_MUSL_DIR}"

DOWNLOAD_URL="https://musl.cc/x86_64-linux-musl-native.tgz"
TARBALL="${GCC_MUSL_DIR}/musl-native.tgz"

log_info "Downloading from ${DOWNLOAD_URL}..."
if command -v curl &> /dev/null; then
    curl -fSL -o "${TARBALL}" "${DOWNLOAD_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${TARBALL}" "${DOWNLOAD_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Extracting toolchain to ${GCC_MUSL_DIR}..."
tar -xzf "${TARBALL}" -C "${GCC_MUSL_DIR}"

rm -f "${TARBALL}"

# The toolchain extracts to a subdirectory — find the actual bin dir
if [[ -d "${GCC_MUSL_DIR}/x86_64-linux-musl-native/bin" ]]; then
    GCC_BIN_DIR="${GCC_MUSL_DIR}/x86_64-linux-musl-native/bin"
elif [[ -d "${GCC_MUSL_DIR}/bin" ]]; then
    GCC_BIN_DIR="${GCC_MUSL_DIR}/bin"
else
    log_error "Could not find GCC binaries after extraction"
    find "${GCC_MUSL_DIR}" -name "gcc" -type f 2>/dev/null || true
    exit 1
fi

# Verify gcc works
if ! "${GCC_BIN_DIR}/gcc" --version &> /dev/null; then
    log_error "Extracted gcc failed to execute"
    exit 1
fi

VERSION=$("${GCC_BIN_DIR}/gcc" --version 2>&1 | head -n1)
log_info "GCC extracted successfully: $VERSION"

# Create symlinks in .boot-linux/bin
mkdir -p "${BIN_DIR}"

# Core compiler symlinks
if [[ -x "${GCC_BIN_DIR}/gcc" ]]; then
    ln -sf "${GCC_BIN_DIR}/gcc" "${BIN_DIR}/gcc"
    ln -sf "${GCC_BIN_DIR}/gcc" "${BIN_DIR}/cc"
    log_info "  Symlinked gcc → cc"
fi
if [[ -x "${GCC_BIN_DIR}/g++" ]]; then
    ln -sf "${GCC_BIN_DIR}/g++" "${BIN_DIR}/g++"
    log_info "  Symlinked g++"
fi

# Also symlink c99 and cpp if available
for bin in c99 c11 cpp; do
    if [[ -x "${GCC_BIN_DIR}/${bin}" ]]; then
        ln -sf "${GCC_BIN_DIR}/${bin}" "${BIN_DIR}/${bin}"
    fi
done

# Symlink binutils (ar, as, ld, nm, objdump, ranlib, strip, etc.)
# musl.cc native toolchain uses x86_64-linux-musl- prefix
for bin in ar as ld nm objdump ranlib strip size strings addr2line; do
    if [[ -x "${GCC_BIN_DIR}/x86_64-linux-musl-${bin}" ]]; then
        ln -sf "${GCC_BIN_DIR}/x86_64-linux-musl-${bin}" "${BIN_DIR}/${bin}"
    elif [[ -x "${GCC_BIN_DIR}/${bin}" ]]; then
        ln -sf "${GCC_BIN_DIR}/${bin}" "${BIN_DIR}/${bin}"
    fi
done

# Verify the symlinked cc works
if "${BIN_DIR}/cc" --version &> /dev/null; then
    log_info "✓ C compiler bootstrapped successfully: $(${BIN_DIR}/cc --version 2>&1 | head -n1)"
else
    log_error "Bootstrapped cc failed to execute"
    exit 1
fi

log_info "GCC/musl bootstrap complete!"
log_info "Installed to: ${GCC_MUSL_DIR}"
log_info "Binaries in: ${BIN_DIR}"
