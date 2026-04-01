#!/usr/bin/env bash
set -euo pipefail

# OpenSSH Bootstrap Script for AMI-ORCHESTRATOR
# Downloads OpenSSH and all shared library dependencies into a self-contained directory.
# Binaries are wrapped with LD_LIBRARY_PATH so they work on WSL and minimal installs.
# Runs on non-privileged port (2222) for git-only access.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use environment variables if set, otherwise default
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"
OPENSSH_DIR="${BOOT_LINUX_DIR}/openssh"
SSH_PORT="${SSH_PORT:-2222}"

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
    log_error "This script only supports Linux. For other platforms, use system OpenSSH."
    exit 1
fi

# Detect architecture
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64|amd64)
        OPENSSH_ARCH="amd64"
        ;;
    aarch64|arm64)
        OPENSSH_ARCH="arm64"
        ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

log_info "Bootstrapping OpenSSH for ${ARCH} on port ${SSH_PORT}"

# Create OpenSSH directory structure
mkdir -p "${OPENSSH_DIR}"/{bin,sbin,lib,etc/ssh,var/empty,var/run}

# ---------------------------------------------------------------------------
# Download OpenSSH packages
# ---------------------------------------------------------------------------
log_info "Downloading OpenSSH packages..."
cd "${OPENSSH_DIR}"
apt download openssh-server openssh-client 2>/dev/null || {
    log_error "Failed to download OpenSSH packages"
    log_error "Ensure apt is configured and you have network access"
    exit 1
}

# Rename downloaded files to predictable names
mv openssh-server_*.deb openssh-server.deb
mv openssh-client_*.deb openssh-client.deb

# ---------------------------------------------------------------------------
# Extract binaries
# ---------------------------------------------------------------------------
log_info "Extracting OpenSSH binaries..."

TMPEXT="$(mktemp -d)"

# Extract server package
dpkg-deb -x openssh-server.deb "${TMPEXT}"
[[ -f "${TMPEXT}/usr/sbin/sshd" ]] && cp "${TMPEXT}/usr/sbin/sshd" "${OPENSSH_DIR}/sbin/"

# Extract client package
dpkg-deb -x openssh-client.deb "${TMPEXT}"
mkdir -p "${OPENSSH_DIR}/bin"
for bin in ssh ssh-keygen scp sftp; do
    if [[ -f "${TMPEXT}/usr/bin/${bin}" ]]; then
        cp "${TMPEXT}/usr/bin/${bin}" "${OPENSSH_DIR}/bin/"
    fi
done

rm -rf "${TMPEXT}"
rm -f "${OPENSSH_DIR}"/*.deb

log_info "OpenSSH binaries extracted"

# ---------------------------------------------------------------------------
# Bundle shared library dependencies
# All .so files are copied into OPENSSH_DIR/lib so the binaries are
# self-contained and work on WSL / minimal installs without system libs.
# ---------------------------------------------------------------------------
log_info "Bundling shared library dependencies..."

# Known runtime dependencies for openssh-server and openssh-client.
# These are small (~2-3 MB total) and always bundled so the binaries
# work regardless of what the host system has installed.
OPENSSH_LIB_DEPS=(
    libcrypt1
    libaudit1
    libpam0g
    libselinux1
    libwrap0
    libgssapi-krb5-2
    libkrb5-3
    libcom-err2
    libk5crypto3
    libkrb5support0
    libkeyutils1
    libpcre2-8-0
    zlib1g
    libssl3t64
)

LIBTMP="$(mktemp -d)"
cd "${LIBTMP}"
for pkg in "${OPENSSH_LIB_DEPS[@]}"; do
    apt download "$pkg" 2>/dev/null || log_warn "Could not download $pkg (may not be needed on this system)"
done

# Extract all .so files into OPENSSH_DIR/lib
for deb in *.deb; do
    [[ -f "$deb" ]] || continue
    dpkg-deb -x "$deb" "${LIBTMP}/extract"
    find "${LIBTMP}/extract" -name '*.so*' -exec cp --update=none {} "${OPENSSH_DIR}/lib/" \;
    rm -rf "${LIBTMP}/extract"
done
rm -rf "${LIBTMP}"

LIB_COUNT="$(find "${OPENSSH_DIR}/lib" -name '*.so*' | wc -l)"
log_info "Bundled ${LIB_COUNT} shared libraries into ${OPENSSH_DIR}/lib/"

# ---------------------------------------------------------------------------
# Verify binaries work with bundled libraries
# ---------------------------------------------------------------------------
export LD_LIBRARY_PATH="${OPENSSH_DIR}/lib:${LD_LIBRARY_PATH:-}"

if ! "${OPENSSH_DIR}/bin/ssh" -V 2>&1 | head -n1; then
    log_error "ssh binary failed to execute with bundled libraries"
    log_error "Missing libraries:"
    ldd "${OPENSSH_DIR}/bin/ssh" 2>&1 | grep "not found" || true
    exit 1
fi
log_info "Binaries verified with bundled libraries"

# ---------------------------------------------------------------------------
# Generate host keys (explicit per-type, not ssh-keygen -A)
# ---------------------------------------------------------------------------
log_info "Generating SSH host keys..."
KEYGEN="${OPENSSH_DIR}/bin/ssh-keygen"
for ktype in rsa ecdsa ed25519; do
    keyfile="${OPENSSH_DIR}/etc/ssh/ssh_host_${ktype}_key"
    if [[ ! -f "$keyfile" ]]; then
        "$KEYGEN" -t "$ktype" -f "$keyfile" -N "" -q
        log_info "  Generated ${ktype} host key"
    fi
done

# ---------------------------------------------------------------------------
# Create sshd_config
# ---------------------------------------------------------------------------
log_info "Creating sshd configuration..."
cat > "${OPENSSH_DIR}/etc/sshd_config" <<EOF
# AMI-ORCHESTRATOR OpenSSH Server Configuration
# Non-privileged SSH server for git-only access

# Network
Port ${SSH_PORT}
AddressFamily any
ListenAddress 0.0.0.0

# Host keys
HostKey ${OPENSSH_DIR}/etc/ssh/ssh_host_rsa_key
HostKey ${OPENSSH_DIR}/etc/ssh/ssh_host_ecdsa_key
HostKey ${OPENSSH_DIR}/etc/ssh/ssh_host_ed25519_key

# Authentication
PubkeyAuthentication yes
AuthorizedKeysFile ${OPENSSH_DIR}/etc/authorized_keys
PasswordAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM no

# Security
PermitRootLogin no
X11Forwarding no
AllowTcpForwarding no
PermitTunnel no
PrintMotd no
PrintLastLog no
Compression no

# Logging
SyslogFacility AUTH
LogLevel INFO

# Process management (no strict mode checks for non-root)
PidFile ${OPENSSH_DIR}/var/run/sshd.pid
StrictModes no

# Subsystem
Subsystem sftp internal-sftp
EOF

log_info "Created ${OPENSSH_DIR}/etc/sshd_config"

# ---------------------------------------------------------------------------
# Create sshd-venv startup script (with LD_LIBRARY_PATH)
# ---------------------------------------------------------------------------
log_info "Creating startup script..."
mkdir -p "${BIN_DIR}"
cat > "${BIN_DIR}/sshd-venv" <<EOFSCRIPT
#!/usr/bin/env bash
set -euo pipefail

# OpenSSH startup script in .boot-linux/bin
OPENSSH_DIR="${OPENSSH_DIR}"
export LD_LIBRARY_PATH="\${OPENSSH_DIR}/lib:\${LD_LIBRARY_PATH:-}"
SSHD_BIN="\${OPENSSH_DIR}/sbin/sshd"
SSHD_CONFIG="\${OPENSSH_DIR}/etc/sshd_config"
PID_FILE="\${OPENSSH_DIR}/var/run/sshd.pid"

if [[ ! -f "\${SSHD_BIN}" ]]; then
    echo "Error: sshd not found at \${SSHD_BIN}" >&2
    echo "Run: scripts/bootstrap_openssh.sh" >&2
    exit 1
fi

case "\${1:-}" in
    start)
        if [[ -f "\${PID_FILE}" ]] && kill -0 "\$(cat "\${PID_FILE}")" 2>/dev/null; then
            echo "sshd is already running (PID: \$(cat "\${PID_FILE}"))"
            exit 0
        fi
        # Verify sshd binary can execute and config is valid
        if ! "\${SSHD_BIN}" -t -f "\${SSHD_CONFIG}" 2>"\${OPENSSH_DIR}/var/run/sshd.log"; then
            echo "Error: sshd config test failed. Check \${OPENSSH_DIR}/var/run/sshd.log" >&2
            if command -v ldd &>/dev/null; then
                MISSING=\$(ldd "\${SSHD_BIN}" 2>&1 | grep "not found" || true)
                if [[ -n "\${MISSING}" ]]; then
                    echo "Missing shared libraries:" >&2
                    echo "\${MISSING}" >&2
                fi
            fi
            exit 1
        fi
        PORT=\$(grep "^Port" "\${SSHD_CONFIG}" | awk '{print \$2}')
        echo "Starting sshd on port \${PORT}..."
        "\${SSHD_BIN}" -f "\${SSHD_CONFIG}" -E "\${OPENSSH_DIR}/var/run/sshd.log"
        sleep 0.5
        if [[ -f "\${PID_FILE}" ]] && kill -0 "\$(cat "\${PID_FILE}")" 2>/dev/null; then
            echo "sshd started (PID: \$(cat "\${PID_FILE}"))"
        else
            echo "Error: sshd failed to start. Check \${OPENSSH_DIR}/var/run/sshd.log" >&2
            exit 1
        fi
        ;;
    stop)
        if [[ -f "\${PID_FILE}" ]]; then
            echo "Stopping sshd (PID: \$(cat "\${PID_FILE}"))"
            kill "\$(cat "\${PID_FILE}")"
            rm -f "\${PID_FILE}"
            echo "sshd stopped"
        else
            echo "sshd is not running"
        fi
        ;;
    restart)
        "\$0" stop
        sleep 1
        "\$0" start
        ;;
    status)
        if [[ -f "\${PID_FILE}" ]] && kill -0 "\$(cat "\${PID_FILE}")" 2>/dev/null; then
            echo "sshd is running (PID: \$(cat "\${PID_FILE}"))"
            PORT=\$(grep "^Port" "\${SSHD_CONFIG}" | awk '{print \$2}')
            echo "Listening on port: \${PORT}"
            exit 0
        else
            echo "sshd is not running"
            exit 1
        fi
        ;;
    *)
        echo "Usage: \$0 {start|stop|restart|status}"
        exit 1
        ;;
esac
EOFSCRIPT

chmod +x "${BIN_DIR}/sshd-venv"
log_info "Created ${BIN_DIR}/sshd-venv"

# ---------------------------------------------------------------------------
# Create LD_LIBRARY_PATH wrapper scripts (not raw symlinks)
# ---------------------------------------------------------------------------
for cmd in ssh ssh-keygen scp sftp; do
    cat > "${BIN_DIR}/${cmd}" <<WRAPPER
#!/bin/bash
export LD_LIBRARY_PATH="${OPENSSH_DIR}/lib:\${LD_LIBRARY_PATH:-}"
exec "${OPENSSH_DIR}/bin/${cmd}" "\$@"
WRAPPER
    chmod +x "${BIN_DIR}/${cmd}"
done

cat > "${BIN_DIR}/sshd" <<WRAPPER
#!/bin/bash
export LD_LIBRARY_PATH="${OPENSSH_DIR}/lib:\${LD_LIBRARY_PATH:-}"
exec "${OPENSSH_DIR}/sbin/sshd" "\$@"
WRAPPER
chmod +x "${BIN_DIR}/sshd"

# ---------------------------------------------------------------------------
# Final verification
# ---------------------------------------------------------------------------
INSTALLED_VERSION="$("${OPENSSH_DIR}/sbin/sshd" -V 2>&1 | head -n1 || true)"
if [[ -z "$INSTALLED_VERSION" ]]; then
    log_error "sshd binary failed to execute after bundling"
    log_error "Missing libraries:"
    ldd "${OPENSSH_DIR}/sbin/sshd" 2>&1 | grep "not found" || true
    exit 1
fi

log_info "OpenSSH bootstrap complete!"
log_info "Installed components:"
log_info "  - ${INSTALLED_VERSION}"
log_info "  - SSH server port: ${SSH_PORT}"
log_info "  - Bundled libs: ${OPENSSH_DIR}/lib/ (${LIB_COUNT} files)"
log_info "  - Configuration: ${OPENSSH_DIR}/etc/sshd_config"
log_info "  - Authorized keys: ${OPENSSH_DIR}/etc/authorized_keys"
log_info ""
log_info "To use SSH server:"
log_info "  1. Start server: sshd-venv start"
log_info "  2. Check status: sshd-venv status"
log_info "  3. Stop server: sshd-venv stop"
log_info ""
log_info "Configure git repositories with ami-repo:"
log_info "  ami-repo --base-path ~/git-repos init"
log_info "  ami-repo generate-key mykey"
log_info "  ami-repo add-key ~/git-repos/ssh-keys/mykey_id_ed25519.pub mykey"
log_info "  ln -sf ~/git-repos/authorized_keys ${OPENSSH_DIR}/etc/authorized_keys"
log_info ""
log_info "Connect using: ssh -p ${SSH_PORT} user@host"
