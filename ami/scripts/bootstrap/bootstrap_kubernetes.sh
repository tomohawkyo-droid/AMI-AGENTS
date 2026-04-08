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

BLUE='\033[0;34m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_debug() { echo -e "${BLUE}[DEBUG]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${GREEN}[>>>>]${NC} $*"; }

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
log_debug "BOOT_DIR=${BOOT_DIR}"
log_debug "BIN_DIR=${BIN_DIR}"
log_debug "KUBERNETES_DIR=${KUBERNETES_DIR}"

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64) ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    arm64) ARCH="arm64" ;;
    *) log_error "Unsupported architecture: $ARCH"; exit 1 ;;
esac

OS="linux"

# Detect WSL — warn about known performance issues
_IS_WSL=0
if grep -qi microsoft /proc/version 2>/dev/null; then
    _IS_WSL=1
    log_warn "WSL detected. If extraction stalls, add a Windows Defender exclusion:"
    log_warn "  PowerShell (admin): Add-MpExclusion -Path '\\\\wsl\$'"
fi

log_debug "OS=${OS} ARCH=${ARCH} WSL=${_IS_WSL}"

# Download kubectl
KUBECTL_VERSION="1.31.0"
KUBECTL_URL="https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"
KUBECTL_BIN="${KUBERNETES_DIR}/kubectl"

log_step "Downloading kubectl v${KUBECTL_VERSION}..."
log_debug "URL: ${KUBECTL_URL}"
log_debug "Dest: ${KUBECTL_BIN}"
_dl_start=$(date +%s)
if command -v curl &> /dev/null; then
    curl -fSL --connect-timeout 30 --max-time 120 -o "${KUBECTL_BIN}" "${KUBECTL_URL}"
elif command -v wget &> /dev/null; then
    wget --timeout=30 -O "${KUBECTL_BIN}" "${KUBECTL_URL}"
else
    log_error "Neither curl nor wget found. Please install one of them."
    exit 1
fi
_dl_end=$(date +%s)
log_info "kubectl downloaded ($(du -h "${KUBECTL_BIN}" | cut -f1)) in $((_dl_end - _dl_start))s"
log_debug "kubectl file type: $(file -b "${KUBECTL_BIN}")"

# Validate kubectl is an actual binary, not an error page or wrapper script.
# dl.k8s.io can return HTML behind proxies, and snap/system kubectl may be a wrapper.
# Real kubectl is ~54M; a wrapper/error page is typically <1M.
_kubectl_size=$(stat -c%s "${KUBECTL_BIN}" 2>/dev/null || stat -f%z "${KUBECTL_BIN}" 2>/dev/null || echo 0)
if ! file -b "${KUBECTL_BIN}" | grep -qi "ELF"; then
    log_error "kubectl download is not a valid ELF binary: $(file -b "${KUBECTL_BIN}")"
    log_error "Size: ${_kubectl_size} bytes (expected ~54MB)"
    log_error "First 3 lines of downloaded file:"
    head -3 "${KUBECTL_BIN}" >&2
    log_error ""
    log_error "This usually means:"
    log_error "  1. A corporate proxy/firewall intercepted the download"
    log_error "  2. A snap/system kubectl script was picked up instead"
    log_error "  3. DNS is broken (try: curl -v '${KUBECTL_URL}' 2>&1 | head -30)"
    log_error ""
    log_error "Workaround: download manually and place at ${BIN_DIR}/kubectl"
    log_error "  curl -fSL -o '${BIN_DIR}/kubectl' '${KUBECTL_URL}'"
    exit 1
fi

chmod +x "${KUBECTL_BIN}"

# Download Helm
HELM_VERSION="3.16.0"
HELM_URL="https://get.helm.sh/helm-v${HELM_VERSION}-${OS}-${ARCH}.tar.gz"
HELM_TARBALL="${KUBERNETES_DIR}/helm.tar.gz"

log_step "Downloading Helm v${HELM_VERSION}..."
log_debug "URL: ${HELM_URL}"
log_debug "Dest: ${HELM_TARBALL}"
_dl_start=$(date +%s)
if command -v curl &> /dev/null; then
    curl -fSL --connect-timeout 30 --max-time 120 -o "${HELM_TARBALL}" "${HELM_URL}"
elif command -v wget &> /dev/null; then
    wget --timeout=30 -O "${HELM_TARBALL}" "${HELM_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi
_dl_end=$(date +%s)

# Verify download succeeded
if [ ! -s "${HELM_TARBALL}" ]; then
    log_error "Helm download failed or produced empty file."
    exit 1
fi
log_info "Helm tarball downloaded ($(du -h "${HELM_TARBALL}" | cut -f1)) in $((_dl_end - _dl_start))s"
log_debug "Tarball type: $(file -b "${HELM_TARBALL}")"

# Extract Helm — use /tmp (native Linux FS) to avoid WSL/DrvFS/Defender stalls.
# Helm is the only bootstrap that uses --strip-components + member-path filtering,
# which forces tar to scan entry-by-entry — extremely slow on NTFS-backed mounts.
_HELM_TMP="$(mktemp -d)"
log_step "Extracting Helm to ${_HELM_TMP} (bypassing project dir for speed)..."
log_debug "tar -xzf ${HELM_TARBALL} -C ${_HELM_TMP} --no-same-owner --strip-components=1 ${OS}-${ARCH}/helm"
_ext_start=$(date +%s)
tar -xzf "${HELM_TARBALL}" -C "${_HELM_TMP}" --no-same-owner --strip-components=1 "${OS}-${ARCH}/helm"
_ext_end=$(date +%s)
log_info "Helm extracted in $((_ext_end - _ext_start))s"

if [ ! -f "${_HELM_TMP}/helm" ]; then
    log_error "Extraction succeeded but helm binary not found in ${_HELM_TMP}"
    ls -la "${_HELM_TMP}/" >&2
    rm -rf "${_HELM_TMP}"
    exit 1
fi
log_debug "Extracted binary: $(ls -lh "${_HELM_TMP}/helm")"

mv "${_HELM_TMP}/helm" "${KUBERNETES_DIR}/helm"
rm -rf "${_HELM_TMP}"

# Move binaries to .boot-linux/bin
log_step "Installing binaries to ${BIN_DIR}..."
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

# Verification — use file(1) check + timeout to avoid Defender scan hangs on WSL.
# First execution of a new binary on WSL triggers a full Defender scan that can
# block for 30s+. We verify the binary is real via file(1) (instant), then run
# the version check with a timeout as a best-effort.
log_step "Verifying installations..."

log_debug "kubectl: $(ls -lh "${BIN_DIR}/kubectl") — $(file -b "${BIN_DIR}/kubectl")"
log_debug "helm:    $(ls -lh "${BIN_DIR}/helm") — $(file -b "${BIN_DIR}/helm")"

# Sanity check: are these actually ELF binaries?
for bin in kubectl helm; do
    if ! file -b "${BIN_DIR}/${bin}" | grep -qi "ELF"; then
        log_error "${bin} is not a valid Linux binary: $(file -b "${BIN_DIR}/${bin}")"
        exit 1
    fi
done
log_info "✓ kubectl and helm are valid ELF binaries"

# Best-effort version check with 15s timeout (Defender may delay first exec)
log_debug "Running kubectl version (15s timeout)..."
if timeout 15 "${BIN_DIR}/kubectl" version --client --output=json 2>/dev/null | grep -q "clientVersion"; then
    log_info "✓ kubectl $(timeout 5 "${BIN_DIR}/kubectl" version --client 2>/dev/null | head -1 || echo "v${KUBECTL_VERSION}")"
else
    log_warn "kubectl version check timed out or failed (binary is valid ELF — likely Defender delay on WSL)"
fi

log_debug "Running helm version (15s timeout)..."
if timeout 15 "${BIN_DIR}/helm" version 2>/dev/null | grep -q "version"; then
    log_info "✓ helm $(timeout 5 "${BIN_DIR}/helm" version --short 2>/dev/null || echo "v${HELM_VERSION}")"
else
    log_warn "helm version check timed out or failed (binary is valid ELF — likely Defender delay on WSL)"
fi

# Cleanup
rm -rf "${KUBERNETES_DIR}"

log_info "Kubernetes tools bootstrap complete."
log_debug "kubectl: ${BIN_DIR}/kubectl"
log_debug "helm:    ${BIN_DIR}/helm"
log_debug "wrapper: ${BIN_DIR}/ami-kubectl"