#!/usr/bin/env bash
set -euo pipefail

# Git Bootstrap Script for AMI-ORCHESTRATOR
# Downloads Git from Ubuntu packages and installs in .boot-linux
# Creates self-contained git installation for git-daemon

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
GIT_DIR="${BOOT_DIR}/git"

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
    log_error "This script only supports Linux. For other platforms, use system git."
    exit 1
fi

# Detect architecture
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64|amd64)
        GIT_ARCH="amd64"
        ;;
    aarch64|arm64)
        GIT_ARCH="arm64"
        ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

log_info "Bootstrapping Git for ${ARCH}"

# Create git directory structure
mkdir -p "${GIT_DIR}"/{bin,libexec}

# Download git packages using apt
log_info "Downloading Git packages..."

cd "${GIT_DIR}"
apt download git git-man 2>/dev/null || {
    log_error "Failed to download git packages"
    log_error "Ensure apt is configured and you have network access"
    exit 1
}

# Rename downloaded files to predictable names
mv git_*.deb git.deb
mv git-man_*.deb git-man.deb

# Extract packages without installing system-wide (use dpkg-deb, always available on Debian/Ubuntu)
log_info "Extracting Git binaries..."

TMPEXT="$(mktemp -d)"

# Extract git package contents
dpkg-deb -x git.deb "${TMPEXT}"

# Copy main git binary
if [[ -f "${TMPEXT}/usr/bin/git" ]]; then
    cp "${TMPEXT}/usr/bin/git" "${GIT_DIR}/bin/git"
fi

# Copy git-core binaries (all git subcommands like git-daemon)
if [[ -d "${TMPEXT}/usr/lib/git-core" ]]; then
    cp -a "${TMPEXT}/usr/lib/git-core/"* "${GIT_DIR}/libexec/" 2>/dev/null || true
fi

rm -rf "${TMPEXT}"
log_info "✓ Git binaries extracted"

# Clean up
rm -f "${GIT_DIR}"/*.deb

# Get installed git version
INSTALLED_VERSION=$("${GIT_DIR}/bin/git" --version 2>&1 | awk '{print $3}')

log_info "Git bootstrap complete!"
log_info "Installed components:"
log_info "  - Git ${INSTALLED_VERSION}"
log_info "  - Binary: ${GIT_DIR}/bin/git"
log_info "  - Git core: ${GIT_DIR}/libexec/git-core/"
log_info ""
log_info "Git is now available in .boot-linux"

# Install git with safety guard (mirrors podman bootstrap pattern)
BIN_DIR="${BOOT_DIR}/bin"
mkdir -p "${BIN_DIR}"

# Link real git to real-git
log_info "Installing Git with safety guard"
ln -sf "../git/bin/git" "${BIN_DIR}/real-git"

# Install guard script as the main git command
GUARD_SCRIPT="${SCRIPT_DIR}/../utils/git-guard"
if [[ -f "$GUARD_SCRIPT" ]]; then
    rm -f "${BIN_DIR}/git"  # Remove existing symlink/wrapper first
    cp "$GUARD_SCRIPT" "${BIN_DIR}/git"
    chmod +x "${BIN_DIR}/git"
    log_info "✓ Installed git-guard as ${BIN_DIR}/git"
    log_info "  Real git available at: ${BIN_DIR}/real-git"
else
    log_warn "Guard script not found at $GUARD_SCRIPT, falling back to direct symlink"
    ln -sf "../git/bin/git" "${BIN_DIR}/git"
fi
