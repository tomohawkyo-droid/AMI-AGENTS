#!/bin/bash
# scripts/bootstrap_podman.sh (updated version)
set -euo pipefail

# Podman Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs Podman and podman-compose in the .boot-linux environment ONLY
# This script ensures Podman is available without requiring system-wide installation
# FORCE INSTALLS TO .boot-linux - NO FALLBACKS, NO .venv, ONLY .boot-linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

PODMAN_DIR="${VENV_DIR}/podman"
PODMAN_VERSION="5.6.2"
PODMAN_COMPOSE_VERSION="1.5.0"
CONMON_VERSION="2.1.13"
NETAVARK_VERSION="1.16.1"
AARDVARK_DNS_VERSION="1.16.0"

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

# =============================================================================
# Reset function - cleans corrupted Podman state while preserving volumes
# =============================================================================
reset_podman_state() {
    log_warn "Resetting corrupted Podman state (volumes will be preserved)..."

    # Kill any stuck container processes
    pkill -9 conmon 2>/dev/null || true
    pkill -9 catatonit 2>/dev/null || true
    pkill -9 -f podman 2>/dev/null || true

    # Remove corrupted state files (but NOT volumes!)
    rm -rf ~/.local/share/containers/storage/libpod
    rm -rf ~/.local/share/containers/storage/overlay-containers
    rm -rf ~/.local/share/containers/storage/db.sql

    # Clear runtime state (stale netns and pause files cause "reexec: Permission denied")
    rm -rf "/run/user/$(id -u)/containers"
    rm -rf "/run/user/$(id -u)/libpod"
    rm -rf "/run/user/$(id -u)/netns"
    mkdir -p "/run/user/$(id -u)/containers"

    log_info "Reset complete. Volumes at ~/.local/share/containers/storage/volumes/ preserved."
}

# =============================================================================
# CLI argument parsing
# =============================================================================
DO_RESET=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --reset|-r)
            DO_RESET=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --reset, -r    Reset corrupted Podman state before install (preserves volumes)"
            echo "  --help, -h     Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run reset if requested
if [[ "$DO_RESET" == "true" ]]; then
    reset_podman_state
fi

# Check if running on Linux
if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "This script only supports Linux. For other platforms, install Podman manually."
    exit 1
fi

# Detect architecture
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64)
        PODMAN_ARCH="amd64"
        ;;
    aarch64|arm64)
        PODMAN_ARCH="arm64"
        ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

log_info "Bootstrapping Podman ${PODMAN_VERSION} for ${ARCH}"

# Check and install system dependencies for rootless mode
log_info "Checking system dependencies for Podman rootless mode"

# Check for uidmap (newuidmap/newgidmap)
if ! command -v newuidmap &> /dev/null; then
    log_warn "newuidmap not found - required for Podman rootless mode"
    log_info "Installing uidmap package (requires sudo)..."
    if echo "$SUDO_PASS" | sudo -S apt-get update && echo "$SUDO_PASS" | sudo -S apt-get install -y uidmap; then
        log_info "✓ uidmap package installed successfully"
    else
        log_error "Failed to install uidmap package"
        log_error "Please install manually: echo \"\$SUDO_PASS\" | sudo -S apt-get install uidmap"
        exit 1
    fi
else
    log_info "✓ newuidmap found at $(command -v newuidmap)"
fi

# Check for slirp4netns (rootless networking)
if ! command -v slirp4netns &> /dev/null; then
    log_warn "slirp4netns not found - required for Podman rootless networking"
    log_info "Installing slirp4netns package (requires sudo)..."
    if echo "$SUDO_PASS" | sudo -S apt-get install -y slirp4netns; then
        log_info "✓ slirp4netns package installed successfully"
    else
        log_error "Failed to install slirp4netns package"
        log_error "Please install manually: echo \"\$SUDO_PASS\" | sudo -S apt-get install slirp4netns"
        exit 1
    fi
else
    log_info "✓ slirp4netns found at $(command -v slirp4netns)"
fi

# Check for iptables (required by netavark)
if ! command -v iptables &> /dev/null; then
    log_warn "iptables not found - required for Podman networking (netavark)"
    log_info "Installing iptables package (requires sudo)..."
    if echo "$SUDO_PASS" | sudo -S apt-get update && echo "$SUDO_PASS" | sudo -S apt-get install -y iptables; then
        log_info "✓ iptables package installed successfully"
    else
        log_error "Failed to install iptables package"
        log_error "Please install manually: echo \"\$SUDO_PASS\" | sudo -S apt-get install iptables"
        exit 1
    fi
else
    log_info "✓ iptables found at $(command -v iptables)"
fi

# AppArmor profile for rootless Podman (Ubuntu 24.04+)
# When kernel.apparmor_restrict_unprivileged_userns=1, binaries need an
# explicit AppArmor profile granting "userns" or they get
# "failed to reexec: Permission denied" when creating user namespaces.
APPARMOR_USERNS=$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || echo 0)
if [[ "$APPARMOR_USERNS" == "1" ]]; then
    PODMAN_REAL_BIN="${PODMAN_DIR}/usr/local/bin/podman"
    APPARMOR_PROFILE="/etc/apparmor.d/ami-podman"

    if [[ -f "$APPARMOR_PROFILE" ]] && grep -qF "$PODMAN_REAL_BIN" "$APPARMOR_PROFILE" 2>/dev/null; then
        log_info "✓ AppArmor userns profile already exists for $PODMAN_REAL_BIN"
    else
        log_warn "AppArmor restricts unprivileged user namespaces on this kernel"
        log_info "Installing AppArmor profile to allow Podman to create user namespaces (requires sudo)..."
        if echo "$SUDO_PASS" | sudo -S tee "$APPARMOR_PROFILE" >/dev/null <<AAEOF
abi <abi/4.0>,
include <tunables/global>

profile ami-podman ${PODMAN_REAL_BIN} flags=(unconfined) {
  userns,
}
AAEOF
        then
            echo "$SUDO_PASS" | sudo -S apparmor_parser -r "$APPARMOR_PROFILE"
            log_info "✓ AppArmor profile installed and loaded: $APPARMOR_PROFILE"
        else
            log_error "Failed to install AppArmor profile"
            log_error "Podman systemd service will fail with 'reexec: Permission denied'"
            log_error "Fix manually: echo \"\$SUDO_PASS\" | sudo -S cp <profile> $APPARMOR_PROFILE && echo \"\$SUDO_PASS\" | sudo -S apparmor_parser -r $APPARMOR_PROFILE"
        fi
    fi
else
    log_info "AppArmor userns restriction not active, no profile needed"
fi

# Create venv if it doesn't exist
if [[ ! -d "${VENV_DIR}" ]]; then
    log_info "Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi

# Create Podman directory
mkdir -p "${PODMAN_DIR}"/{bin,lib}

# Download Podman static binary
PODMAN_URL="https://github.com/mgoltzsche/podman-static/releases/download/v${PODMAN_VERSION}/podman-linux-${PODMAN_ARCH}.tar.gz"
PODMAN_TARBALL="${PODMAN_DIR}/podman.tar.gz"

log_info "Downloading Podman from ${PODMAN_URL}"
if command -v curl &> /dev/null; then
    curl -L -o "${PODMAN_TARBALL}" "${PODMAN_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${PODMAN_TARBALL}" "${PODMAN_URL}"
else
    log_error "Neither curl nor wget found. Please install one of them."
    exit 1
fi

# Extract Podman
log_info "Extracting Podman to ${PODMAN_DIR}"
tar -xzf "${PODMAN_TARBALL}" -C "${PODMAN_DIR}" --strip-components=1

# Download conmon
CONMON_URL="https://github.com/containers/conmon/releases/download/v${CONMON_VERSION}/conmon.${PODMAN_ARCH}"
CONMON_BIN="${PODMAN_DIR}/bin/conmon"

log_info "Downloading conmon from ${CONMON_URL}"
rm -f "${CONMON_BIN}"
if command -v curl &> /dev/null; then
    curl -L -o "${CONMON_BIN}" "${CONMON_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${CONMON_BIN}" "${CONMON_URL}"
fi
chmod +x "${CONMON_BIN}"

# Download netavark (networking)
NETAVARK_URL="https://github.com/containers/netavark/releases/download/v${NETAVARK_VERSION}/netavark.gz"
NETAVARK_BIN="${PODMAN_DIR}/bin/netavark"

log_info "Downloading netavark from ${NETAVARK_URL}"
rm -f "${NETAVARK_BIN}"
if command -v curl &> /dev/null; then
    curl -L "${NETAVARK_URL}" | gunzip > "${NETAVARK_BIN}"
elif command -v wget &> /dev/null; then
    wget -O - "${NETAVARK_URL}" | gunzip > "${NETAVARK_BIN}"
fi
chmod +x "${NETAVARK_BIN}"

# Download aardvark-dns (DNS for netavark)
AARDVARK_URL="https://github.com/containers/aardvark-dns/releases/download/v${AARDVARK_DNS_VERSION}/aardvark-dns.gz"
AARDVARK_BIN="${PODMAN_DIR}/bin/aardvark-dns"

log_info "Downloading aardvark-dns from ${AARDVARK_URL}"
rm -f "${AARDVARK_BIN}"
if command -v curl &> /dev/null; then
    curl -L "${AARDVARK_URL}" | gunzip > "${AARDVARK_BIN}"
elif command -v wget &> /dev/null; then
    wget -O - "${AARDVARK_URL}" | gunzip > "${AARDVARK_BIN}"
fi
chmod +x "${AARDVARK_BIN}"

# Create symlinks in venv/bin (with guard for podman)
log_info "Creating symlinks in ${VENV_DIR}/bin"

# First, link helper binaries directly
for binary in conmon netavark aardvark-dns; do
    if [[ -f "${PODMAN_DIR}/usr/local/bin/${binary}" ]]; then
        ln -sf "${PODMAN_DIR}/usr/local/bin/${binary}" "${VENV_DIR}/bin/${binary}"
    elif [[ -f "${PODMAN_DIR}/bin/${binary}" ]]; then
        ln -sf "${PODMAN_DIR}/bin/${binary}" "${VENV_DIR}/bin/${binary}"
    fi
done

# Link container runtime binaries
for binary in crun fuse-overlayfs fusermount3 pasta runc; do
    if [[ -f "${PODMAN_DIR}/usr/local/bin/${binary}" ]]; then
        ln -sf "${PODMAN_DIR}/usr/local/bin/${binary}" "${VENV_DIR}/bin/${binary}"
    fi
done

# Link real podman to real-podman
log_info "Installing Podman with safety guard"
if [[ -f "${PODMAN_DIR}/usr/local/bin/podman" ]]; then
    ln -sf "${PODMAN_DIR}/usr/local/bin/podman" "${VENV_DIR}/bin/real-podman"
elif [[ -f "${PODMAN_DIR}/bin/podman" ]]; then
    ln -sf "${PODMAN_DIR}/bin/podman" "${VENV_DIR}/bin/real-podman"
fi

# Install guard script as the main podman command
GUARD_SCRIPT="${SCRIPT_DIR}/../utils/podman-guard"
if [[ -f "$GUARD_SCRIPT" ]]; then
    rm -f "${VENV_DIR}/bin/podman"  # Remove existing symlink first
    cp "$GUARD_SCRIPT" "${VENV_DIR}/bin/podman"
    chmod +x "${VENV_DIR}/bin/podman"
    log_info "✓ Installed podman-guard as ${VENV_DIR}/bin/podman"
    log_info "  Real podman available at: ${VENV_DIR}/bin/real-podman"
else
    log_error "Guard script not found at $GUARD_SCRIPT. Bootstrap is broken."
    exit 1
fi

# Create symlink for rootlessport (required for port forwarding in rootless mode)
if [[ -f "${PODMAN_DIR}/usr/local/lib/podman/rootlessport" ]]; then
    ln -sf "${PODMAN_DIR}/usr/local/lib/podman/rootlessport" "${VENV_DIR}/bin/rootlessport"
fi

# Note: podman-compose is installed via pyproject.toml dependencies
# Run: uv sync or ami-run uv sync to install it

# Create Docker alias symlinks for seamless migration
log_info "Creating Docker alias symlinks"
ln -sf "${VENV_DIR}/bin/podman" "${VENV_DIR}/bin/docker"

# Link podman-compose from root .venv if available
if [ -f "${PROJECT_ROOT}/.venv/bin/podman-compose" ]; then
    ln -sf "${PROJECT_ROOT}/.venv/bin/podman-compose" "${VENV_DIR}/bin/podman-compose"
    ln -sf "${VENV_DIR}/bin/podman-compose" "${VENV_DIR}/bin/docker-compose"
    log_info "✓ Linked podman-compose from project .venv"
fi

# Create containers.conf to point Podman to helper binaries in venv
log_info "Configuring Podman to use venv helper binaries"
CONTAINERS_CONF_DIR="${HOME}/.config/containers"
CONTAINERS_CONF="${CONTAINERS_CONF_DIR}/containers.conf"
mkdir -p "${CONTAINERS_CONF_DIR}"

cat > "${CONTAINERS_CONF}" <<EOF
[engine]
helper_binaries_dir = ["${VENV_DIR}/bin"]
conmon_path = ["${VENV_DIR}/bin/conmon"]

[network]
network_backend = "netavark"
default_rootless_network_cmd = "slirp4netns"
EOF

# Create registries.conf for image pulling
REGISTRIES_CONF="${CONTAINERS_CONF_DIR}/registries.conf"
cat > "${REGISTRIES_CONF}" <<EOF
unqualified-search-registries = ["docker.io"]

[[registry]]
location = "docker.io"
EOF

log_info "✓ Created ${REGISTRIES_CONF}"

# Create policy.json for image signature verification
POLICY_JSON="${CONTAINERS_CONF_DIR}/policy.json"
cat > "${POLICY_JSON}" <<EOF
{
  "default": [
    {
      "type": "insecureAcceptAnything"
    }
  ],
  "transports": {
    "docker-daemon": {
      "": [{"type": "insecureAcceptAnything"}]
    }
  }
}
EOF

log_info "✓ Created ${POLICY_JSON}"

log_info "✓ Created ${CONTAINERS_CONF}"

# Verify installation (use real-podman for direct check)
log_info "Verifying Podman installation"
if "${VENV_DIR}/bin/real-podman" --version; then
    log_info "Podman installed successfully: $(${VENV_DIR}/bin/real-podman --version)"
else
    log_error "Podman installation verification failed"
    exit 1
fi

# Verify guard is working
log_info "Verifying safety guard"
if "${VENV_DIR}/bin/podman" --version >/dev/null 2>&1; then
    log_info "✓ Safety guard is operational"
else
    log_warn "Safety guard verification failed - check podman-guard script"
fi

# Verify podman-compose with PATH set
export PATH="${VENV_DIR}/bin:$PATH"
if command -v podman-compose &> /dev/null; then
    if podman-compose --version; then
        log_info "podman-compose installed successfully: $(podman-compose --version)"
    else
        log_warn "podman-compose installation verification failed"
        log_warn "This may be OK if podman-compose is not yet fully configured"
    fi
else
    log_warn "podman-compose not found - this is expected if it's not installed via pip"
fi

# Clean up
rm -f "${PODMAN_TARBALL}"

log_info "Podman bootstrap complete!"
log_info "Installed components:"
log_info "  - Podman ${PODMAN_VERSION}"
log_info "  - conmon ${CONMON_VERSION}"
log_info "  - netavark ${NETAVARK_VERSION}"
log_info "  - aardvark-dns ${AARDVARK_DNS_VERSION}"
log_info "  - podman-compose (installed via pip if available)"
log_info "  - podman-guard (safety wrapper)"
log_info ""
log_info "Docker alias symlinks created: docker -> podman, docker-compose -> podman-compose"
log_info ""
log_warn "SAFETY GUARD ACTIVE - The following commands are BLOCKED:"
log_warn "  - podman system migrate/reset/prune"
log_warn "  - podman rm -a / rmi -a"
log_warn "  - podman volume/container/network/image prune"
log_warn "  Use real-podman to bypass (at your own risk)"
log_info ""
log_info "To use Podman:"
log_info "  1. Run: ami-run commands (Podman is auto-available)"
log_info "  2. Or activate venv: source ${VENV_DIR}/bin/activate"
log_info "  3. Run podman commands: podman ps, podman-compose up, etc."
log_info "  4. Or use docker commands: docker ps, docker-compose up (they map to podman)"
log_info ""
log_info "To reset corrupted state: $0 --reset"