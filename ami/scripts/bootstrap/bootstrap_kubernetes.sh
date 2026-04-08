#!/usr/bin/env bash
# scripts/bootstrap_kubernetes.sh
set -euo pipefail

# Kubernetes Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs Kubernetes tools (kubectl, helm) to .boot-linux
# Ensures availability for Kubernetes operations without relying on system PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_DIR:-${PROJECT_ROOT}/.boot-linux}"
KUBERNETES_DIR="${BOOT_DIR}/kubernetes_tmp"
BIN_DIR="${BOOT_DIR}/bin"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "Linux only."
    exit 1
fi

# Ensure .boot-linux exists
if [ ! -d "$BOOT_DIR" ]; then
    log_error ".boot-linux directory not found. Please run install first."
    exit 1
fi

mkdir -p "${KUBERNETES_DIR}"
mkdir -p "${BIN_DIR}"

log_info "Bootstrapping Kubernetes tools..."

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64) ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    arm64) ARCH="arm64" ;;
    *) log_error "Unsupported architecture: $ARCH"; exit 1 ;;
esac

OS="linux"

# Download kubectl
KUBECTL_VERSION="1.31.0"
KUBECTL_URL="https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"
KUBECTL_BIN="${KUBERNETES_DIR}/kubectl"

log_info "Downloading kubectl from ${KUBECTL_URL}..."
if command -v curl &> /dev/null; then
    curl -fSL --connect-timeout 30 --max-time 120 -o "${KUBECTL_BIN}" "${KUBECTL_URL}"
elif command -v wget &> /dev/null; then
    wget --timeout=30 -O "${KUBECTL_BIN}" "${KUBECTL_URL}"
else
    log_error "Neither curl nor wget found. Please install one of them."
    exit 1
fi

chmod +x "${KUBECTL_BIN}"

# Download Helm
HELM_VERSION="3.16.0"
HELM_URL="https://get.helm.sh/helm-v${HELM_VERSION}-${OS}-${ARCH}.tar.gz"
HELM_TARBALL="${KUBERNETES_DIR}/helm.tar.gz"

log_info "Downloading Helm from ${HELM_URL}..."
if command -v curl &> /dev/null; then
    curl -fSL --connect-timeout 30 --max-time 120 -o "${HELM_TARBALL}" "${HELM_URL}"
elif command -v wget &> /dev/null; then
    wget --timeout=30 -O "${HELM_TARBALL}" "${HELM_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

# Verify download succeeded
if [ ! -s "${HELM_TARBALL}" ]; then
    log_error "Helm download failed or produced empty file."
    exit 1
fi

# Extract Helm — use /tmp to avoid WSL/Windows Defender filesystem slowdowns
log_info "Extracting Helm ($(du -h "${HELM_TARBALL}" | cut -f1))..."
_HELM_TMP="$(mktemp -d)"
tar -xzf "${HELM_TARBALL}" -C "${_HELM_TMP}" --no-same-owner --strip-components=1 "${OS}-${ARCH}/helm"
mv "${_HELM_TMP}/helm" "${KUBERNETES_DIR}/helm"
rm -rf "${_HELM_TMP}"

# Move binaries to .boot-linux/bin
mv "${KUBECTL_BIN}" "${BIN_DIR}/kubectl"
mv "${KUBERNETES_DIR}/helm" "${BIN_DIR}/helm"

# Create kubectl wrapper with proper config
KUBECTL_WRAPPER="${BIN_DIR}/ami-kubectl"
cat > "${KUBECTL_WRAPPER}" <<'EOF'
#!/usr/bin/env bash
# kubectl wrapper for AMI-ORCHESTRATOR with custom config
export KUBECONFIG="${HOME}/.kube/config:./.kube/config"
exec kubectl "$@"
EOF

chmod +x "${KUBECTL_WRAPPER}"

# Verification
if "${BIN_DIR}/kubectl" version --client --output=json 2>/dev/null | grep -q "clientVersion"; then
    log_info "✓ kubectl installed successfully"
    "${BIN_DIR}/kubectl" version --client 2>/dev/null || true
else
    log_error "Failed to verify kubectl installation"
    exit 1
fi

if "${BIN_DIR}/helm" version 2>/dev/null | grep -q "version"; then
    log_info "✓ Helm installed successfully"
else
    log_error "Failed to verify Helm installation"
    exit 1
fi

# Cleanup
rm -rf "${KUBERNETES_DIR}"

log_info "Kubernetes tools bootstrap complete."