#!/usr/bin/env bash
set -euo pipefail

# OpenVPN Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and extracts OpenVPN into .boot-linux without sudo
# This follows the pattern established in bootstrap_git.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
OPENVPN_DIR="${VENV_DIR}/openvpn"

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
    log_error "This script only supports Linux."
    exit 1
fi

log_info "Bootstrapping OpenVPN for local environment..."

# Check if already installed in .boot-linux
if [ -x "${VENV_DIR}/bin/openvpn" ]; then
    log_info "✓ OpenVPN already exists in .boot-linux/bin"
else
    # Create directory structure
    mkdir -p "${OPENVPN_DIR}"/sbin

    # Download openvpn package using apt download (non-root)
    log_info "Downloading OpenVPN package..."
    TEMP_DOWNLOAD_DIR=$(mktemp -d)
    cd "${TEMP_DOWNLOAD_DIR}"

    # Use apt download - this doesn't require sudo
    if ! apt download openvpn 2>/dev/null; then
        log_warn "apt download failed. Attempting manual download from Ubuntu mirrors..."
        # Find latest version URL (simplified fallback)
        # Using a more stable mirror link for Ubuntu Noble
        URL="http://archive.ubuntu.com/ubuntu/pool/main/o/openvpn/openvpn_2.6.9-1ubuntu4_amd64.deb"
        [ "$(uname -m)" != "x86_64" ] && URL="http://ports.ubuntu.com/ubuntu-ports/pool/main/o/openvpn/openvpn_2.6.9-1ubuntu4_arm64.deb"
        
        log_info "Downloading from: $URL"
        curl -L -f -o openvpn.deb "$URL" || { log_error "Failed to download OpenVPN package"; exit 1; }
    else
        mv openvpn_*.deb openvpn.deb
    fi

    log_info "Extracting OpenVPN binary..."
    # Extract deb (it's a multi-stage process: ar, then tar for data.tar.xz)
    ar x openvpn.deb
    
    # Locate data.tar.* (could be .xz, .gz, or .zst)
    DATA_TAR=$(ls data.tar.*)
    
    # Extract only the openvpn binary
    # We try both common locations: /usr/sbin and /sbin
    mkdir -p bin_extract
    tar -xf "$DATA_TAR" -C bin_extract
    
    if [ -f bin_extract/usr/sbin/openvpn ]; then
        mv bin_extract/usr/sbin/openvpn "${OPENVPN_DIR}/sbin/openvpn"
    elif [ -f bin_extract/sbin/openvpn ]; then
        mv bin_extract/sbin/openvpn "${OPENVPN_DIR}/sbin/openvpn"
    else
        log_error "Could not find openvpn binary in package"
        find bin_extract -name openvpn
        exit 1
    fi
    rm -rf bin_extract

    # Create symlink in .boot-linux/bin
    ln -sf "${OPENVPN_DIR}/sbin/openvpn" "${VENV_DIR}/bin/openvpn"
    
    # Cleanup
    cd "${PROJECT_ROOT}"
    rm -rf "${TEMP_DOWNLOAD_DIR}"
    
    log_info "✓ OpenVPN binary extracted to .boot-linux/openvpn"
fi

# Create a simple OpenVPN client wrapper script that will be available in the .boot-linux environment
WRAPPER_SCRIPT="${VENV_DIR}/bin/openvpn-client-wrapper"

log_info "Creating OpenVPN client wrapper script: ${WRAPPER_SCRIPT}"

cat > "${WRAPPER_SCRIPT}" << 'EOF_WRAPPER'
#!/usr/bin/env bash

# OpenVPN Client Wrapper for AMI-ORCHESTRATOR
# This script provides a managed OpenVPN client service that can be controlled
# through the launcher system. It supports configuration via .ovpn files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Use bootstrapped openvpn if available
if [ -x "${SCRIPT_DIR}/openvpn" ]; then
    OPENVPN_BIN="${SCRIPT_DIR}/openvpn"
else
    OPENVPN_BIN="openvpn"
fi

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

# Set up signal handlers for graceful shutdown
handle_signal() {
    log_info "Received signal, shutting down OpenVPN client..."
    if [ -n "${OPENVPN_PID:-}" ]; then
        if kill -0 "$OPENVPN_PID" 2>/dev/null; then
            kill "$OPENVPN_PID" 2>/dev/null || true
            sleep 2
            if kill -0 "$OPENVPN_PID" 2>/dev/null; then
                kill -9 "$OPENVPN_PID" 2>/dev/null || true
            fi
        fi
    fi
    exit 0
}

trap 'handle_signal' SIGTERM SIGINT SIGQUIT

is_openvpn_running() {
    if [ -n "${OPENVPN_PID:-}" ] && kill -0 "$OPENVPN_PID" 2>/dev/null; then
        return 0
    else
        if pgrep -f "openvpn.*--config" > /dev/null; then
            return 0
        else
            return 1
        fi
    fi
}

check_connection_status() {
    if ip link show tun0 &> /dev/null; then
        echo "connected"
    else
        echo "disconnected"
    fi
}

health_check() {
    STATUS=$(check_connection_status)
    if [ "$STATUS" = "connected" ]; then
        EXTERNAL_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "unknown")
        echo "status: connected, external_ip: $EXTERNAL_IP"
    else
        echo "status: disconnected"
    fi
}

ACTION="start"
OVPN_FILE=""
AUTH_FILE=""
ADDITIONAL_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --action)
            ACTION="$2"
            shift 2
            ;;
        --ovpn-file)
            OVPN_FILE="$2"
            shift 2
            ;;
        --auth-file)
            AUTH_FILE="$2"
            shift 2
            ;;
        --additional-args)
            ADDITIONAL_ARGS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

case "$ACTION" in
    start)
        OVPN_FILE="${OVPN_FILE:-${OPENVPN_CONFIG_FILE:-}}"
        if [ -z "$OVPN_FILE" ]; then
            log_error "No OpenVPN configuration file specified."
            exit 1
        fi
        if [ ! -f "$OVPN_FILE" ]; then
            log_error "OpenVPN configuration file does not exist: $OVPN_FILE"
            exit 1
        fi
        
        log_info "Starting OpenVPN client with config: $OVPN_FILE"
        CMD="$OPENVPN_BIN --config '$OVPN_FILE'"
        if [ -n "$AUTH_FILE" ] && [ -f "$AUTH_FILE" ]; then
            CMD="$CMD --auth-user-pass '$AUTH_FILE'"
        fi
        if [ -n "$ADDITIONAL_ARGS" ]; then
            CMD="$CMD $ADDITIONAL_ARGS"
        fi
        
        eval "$CMD" &
        OPENVPN_PID=$!
        echo $OPENVPN_PID > "/tmp/ami-openvpn-client.pid"
        wait $OPENVPN_PID
        ;;
    stop)
        log_info "Stopping OpenVPN client..."
        pkill -f "openvpn.*--config" 2>/dev/null || true
        rm -f "/tmp/ami-openvpn-client.pid"
        log_info "OpenVPN client stopped"
        ;;
    status)
        STATUS=$(check_connection_status)
        log_info "VPN Status: $STATUS"
        if [ "$STATUS" = "connected" ]; then exit 0; else exit 1; fi
        ;;
    health)
        health_check
        ;;
    *)
        log_error "Unknown action: $ACTION."
        exit 1
        ;;
esac
EOF_WRAPPER

chmod +x "${WRAPPER_SCRIPT}"

# Verify Python wrapper exists
PYTHON_WRAPPER="${PROJECT_ROOT}/ami/scripts/bin/run_openvpn_client.py"
log_info "Verifying Python wrapper: ${PYTHON_WRAPPER}"

if [[ ! -f "${PYTHON_WRAPPER}" ]]; then
    log_error "Python wrapper not found at ${PYTHON_WRAPPER}"
    log_error "This file should be part of the repository."
    exit 1
fi

chmod +x "${PYTHON_WRAPPER}"
log_info "✓ Python wrapper verified"

log_info "OpenVPN bootstrap complete!"

