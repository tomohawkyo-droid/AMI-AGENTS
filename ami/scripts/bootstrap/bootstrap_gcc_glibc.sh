#!/usr/bin/env bash
set -euo pipefail

# GCC/glibc Bootstrap Script
# Downloads pre-built GCC 14.3.0 + glibc toolchain from Bootlin
# Required by Rust toolchain (glibc-based) as its linker driver
#
# The musl toolchain (bootstrap_gcc.sh) remains for non-Rust C compilation.
# This glibc toolchain is used exclusively by cargo via config.toml.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"
GCC_GLIBC_DIR="${BOOT_LINUX_DIR}/gcc-glibc"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Toolchain details
TOOLCHAIN_VERSION="2025.08-1"
TOOLCHAIN_TARBALL="x86-64--glibc--stable-${TOOLCHAIN_VERSION}.tar.xz"
TOOLCHAIN_URL="https://toolchains.bootlin.com/downloads/releases/toolchains/x86-64/tarballs/${TOOLCHAIN_TARBALL}"
TOOLCHAIN_DIR_NAME="x86-64--glibc--stable-${TOOLCHAIN_VERSION}"
# Use .br_real directly — Buildroot's toolchain-wrapper hangs outside its build environment
GCC_BIN_NAME="x86_64-buildroot-linux-gnu-gcc.br_real"

# Check if already installed
if [[ -x "${GCC_GLIBC_DIR}/${TOOLCHAIN_DIR_NAME}/bin/${GCC_BIN_NAME}" ]]; then
    VERSION=$("${GCC_GLIBC_DIR}/${TOOLCHAIN_DIR_NAME}/bin/${GCC_BIN_NAME}" --version 2>&1 | head -n1)
    log_info "GCC/glibc already installed: $VERSION"
    exit 0
fi

log_info "Bootstrapping GCC/glibc toolchain (Bootlin ${TOOLCHAIN_VERSION})"

mkdir -p "${GCC_GLIBC_DIR}"

TARBALL_PATH="${GCC_GLIBC_DIR}/${TOOLCHAIN_TARBALL}"

log_info "Downloading from ${TOOLCHAIN_URL} (~89MB)..."
if command -v curl &> /dev/null; then
    curl -fSL -o "${TARBALL_PATH}" "${TOOLCHAIN_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${TARBALL_PATH}" "${TOOLCHAIN_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Extracting toolchain to ${GCC_GLIBC_DIR}..."
tar -xJf "${TARBALL_PATH}" -C "${GCC_GLIBC_DIR}"

rm -f "${TARBALL_PATH}"

# Verify gcc works
GCC_BIN="${GCC_GLIBC_DIR}/${TOOLCHAIN_DIR_NAME}/bin/${GCC_BIN_NAME}"
if ! "${GCC_BIN}" --version &> /dev/null; then
    log_error "Extracted gcc failed to execute"
    exit 1
fi

VERSION=$("${GCC_BIN}" --version 2>&1 | head -n1)
log_info "GCC extracted successfully: $VERSION"

# Create wrapper script in .boot-linux/bin/ — do NOT overwrite gcc/cc (those are musl)
# Cannot use a symlink because Bootlin's toolchain-wrapper resolves paths relative to itself
# Wrapper resolves path relative to itself at runtime — no hardcoded absolute paths
mkdir -p "${BIN_DIR}"
cat > "${BIN_DIR}/gcc-glibc" << 'WRAPPER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
exec "$BOOT_DIR/gcc-glibc/x86-64--glibc--stable-2025.08-1/bin/x86_64-buildroot-linux-gnu-gcc.br_real" "$@"
WRAPPER
chmod +x "${BIN_DIR}/gcc-glibc"
log_info "  Created gcc-glibc wrapper (musl gcc/cc unchanged)"

# Verify
if "${BIN_DIR}/gcc-glibc" --version &> /dev/null; then
    log_info "✓ GCC/glibc bootstrapped: $(${BIN_DIR}/gcc-glibc --version 2>&1 | head -n1)"
else
    log_error "Bootstrapped gcc-glibc failed to execute"
    exit 1
fi

log_info "GCC/glibc bootstrap complete!"
log_info "Installed to: ${GCC_GLIBC_DIR}/${TOOLCHAIN_DIR_NAME}"
log_info "Symlink: ${BIN_DIR}/gcc-glibc"
