#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Pre-requisites Check & Installation Script
# =============================================================================
# Checks for required system dependencies, probes apt for exact package names,
# and offers interactive auto-install with sudo.
#
# Usage:
#   ./pre-req.sh              # Check + interactive prompt if missing
#   ./pre-req.sh --install    # Auto-install missing packages (sudo)
#   ./pre-req.sh --ci         # CI mode: check only, exit 1 if missing
#
# Called by: make pre-req-check (via make install / make install-ci)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_ok()    { echo -e "${GREEN}  ✓${NC} $*"; }
log_miss()  { echo -e "${RED}  ✗${NC} $*"; }
log_probe() { echo -e "${CYAN}  →${NC} $*"; }
log_section() { echo -e "\n${CYAN}${BOLD}═══ $* ═══${NC}\n"; }

# Mode
MODE="interactive"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --install|-i) MODE="install";  shift ;;
        --ci)         MODE="ci";       shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install, -i    Auto-install missing dependencies (requires sudo)"
            echo "  --ci             CI mode: check only, non-interactive, exit 1 if missing"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

# =============================================================================
# Data structures for missing packages
# =============================================================================
# Arrays of "command|package_name|description|resolved_version"
declare -a MISSING_ENTRIES=()

# =============================================================================
# Check Functions
# =============================================================================

# Search paths beyond PATH for system binaries
SYSTEM_PATHS="/usr/bin /usr/sbin /usr/local/bin /usr/local/sbin /snap/bin"

find_binary() {
    local cmd="$1"
    # First check PATH
    if command -v "$cmd" &> /dev/null; then
        command -v "$cmd"
        return 0
    fi
    # Then check system paths
    for dir in $SYSTEM_PATHS; do
        if [[ -x "${dir}/${cmd}" ]]; then
            echo "${dir}/${cmd}"
            return 0
        fi
    done
    # Check bootstrapped tools
    if [[ -x "${PROJECT_ROOT}/.boot-linux/bin/${cmd}" ]]; then
        echo "${PROJECT_ROOT}/.boot-linux/bin/${cmd}"
        return 0
    fi
    return 1
}

check_command() {
    local cmd="$1"
    local package="$2"
    local description="$3"

    local found_path=""
    if found_path=$(find_binary "$cmd"); then
        local version=""
        # Capture both stdout and stderr (ssh/sshd output version to stderr)
        version=$("$found_path" --version 2>&1 | head -n1 | cut -c1-60) || version=""
        # Fallback: try -V flag (some tools use -V instead of --version)
        if [[ -z "$version" ]]; then
            version=$("$found_path" -V 2>&1 | head -n1 | cut -c1-60) || version=""
        fi
        # Fallback: try version flag
        if [[ -z "$version" ]]; then
            version=$("$found_path" version 2>&1 | head -n1 | cut -c1-60) || version=""
        fi
        if [[ -n "$version" ]]; then
            log_ok "$description ${DIM}($version)${NC}"
        else
            log_ok "$description ${DIM}(found at $found_path)${NC}"
        fi
        return 0
    else
        log_miss "$description ${DIM}(not found — needs: $package)${NC}"
        MISSING_ENTRIES+=("${cmd}|${package}|${description}")
        return 1
    fi
}

check_c_compiler() {
    local compilers=("gcc" "cc" "clang")

    for compiler in "${compilers[@]}"; do
        local found_path=""
        if found_path=$(find_binary "$compiler"); then
            local version
            version=$("$found_path" --version 2>&1 | head -n1 | cut -c1-60)
            log_ok "C compiler: $version"
            return 0
        fi
    done

    log_miss "No C compiler found (need gcc, cc, or clang)"
    # C compiler can be bootstrapped from direct download — special handling
    MISSING_ENTRIES+=("gcc|gcc-bootstrap|C compiler (gcc/cc/clang)")
    return 1
}

# =============================================================================
# Apt Probing — resolve exact package name and version available
# =============================================================================

declare -A RESOLVED_PACKAGES=()  # package_name → "version (arch)"
declare -A RESOLVED_STATUS=()     # package_name → "available" | "unavailable"

probe_apt_package() {
    local pkg="$1"

    if [[ -n "${RESOLVED_STATUS[$pkg]:-}" ]]; then
        return  # Already probed
    fi

    # Special case: gcc-bootstrap is not an apt package — it's bootstrapped from direct download
    if [[ "$pkg" == "gcc-bootstrap" ]]; then
        RESOLVED_PACKAGES[$pkg]="GCC 15.1.0 (Dyne.org musl — direct download)"
        RESOLVED_STATUS[$pkg]="bootstrap"
        return 0
    fi

    # Try to get package info from apt
    local pkg_info=""
    pkg_info=$(apt-cache show "$pkg" 2>/dev/null) || true

    if [[ -z "$pkg_info" ]]; then
        RESOLVED_STATUS[$pkg]="unavailable"
        return 1
    fi

    local version="" arch=""
    version=$(echo "$pkg_info" | grep -m1 "^Version:" | awk '{print $2}') || version=""
    arch=$(echo "$pkg_info" | grep -m1 "^Architecture:" | awk '{print $2}') || arch=""

    RESOLVED_PACKAGES[$pkg]="${version:-?} ${arch:-any}"
    RESOLVED_STATUS[$pkg]="available"
    return 0
}

probe_all_missing() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        return
    fi

    log_section "Probing apt for Available Packages"

    local unique_pkgs=()
    declare -A seen=()

    for entry in "${MISSING_ENTRIES[@]}"; do
        local pkg="${entry#*|}"
        pkg="${pkg%%|*}"
        if [[ -z "${seen[$pkg]:-}" ]]; then
            unique_pkgs+=("$pkg")
            seen[$pkg]=1
        fi
    done

    for pkg in "${unique_pkgs[@]}"; do
        if probe_apt_package "$pkg"; then
            log_probe "$pkg → ${RESOLVED_PACKAGES[$pkg]}"
        else
            log_probe "$pkg → ${RED}not available in apt${NC}"
            RESOLVED_STATUS[$pkg]="unavailable"
        fi
    done
}

# =============================================================================
# Installation
# =============================================================================

install_missing() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        log_info "Nothing to install — all pre-requisites satisfied."
        return 0
    fi

    # Collect installable packages by type
    local apt_installable=()
    local bootstrap_installable=()
    local unavail=()

    for entry in "${MISSING_ENTRIES[@]}"; do
        local pkg="${entry#*|}"
        pkg="${pkg%%|*}"
        local status="${RESOLVED_STATUS[$pkg]:-unknown}"

        case "$status" in
            available)
                # Avoid duplicates
                local already=false
                for existing in "${apt_installable[@]:-}"; do
                    [[ "$existing" == "$pkg" ]] && already=true && break
                done
                [[ "$already" == "false" ]] && apt_installable+=("$pkg")
                ;;
            bootstrap)
                bootstrap_installable+=("$pkg")
                ;;
            *)
                local already=false
                for existing in "${unavail[@]:-}"; do
                    [[ "$existing" == "$pkg" ]] && already=true && break
                done
                [[ "$already" == "false" ]] && unavail+=("$pkg")
                ;;
        esac
    done

    # Report unavailable packages
    if [[ ${#unavail[@]} -gt 0 ]]; then
        log_warn "The following packages are not available:"
        for pkg in "${unavail[@]}"; do
            log_warn "  • $pkg"
        done
        log_warn "You may need to install these manually."
        echo ""
    fi

    # Bootstrap gcc if needed
    if [[ ${#bootstrap_installable[@]} -gt 0 ]]; then
        log_info "Bootstrapping GCC/musl C compiler from direct download..."
        echo ""
        if bash "${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_gcc.sh"; then
            log_info "✓ GCC/musl bootstrapped successfully"
        else
            log_error "✗ GCC/musl bootstrap failed"
            return 1
        fi
        echo ""
    fi

    # Apt install remaining packages
    if [[ ${#apt_installable[@]} -gt 0 ]]; then
        log_info "Installing ${#apt_installable[@]} package(s) via apt: ${apt_installable[*]}"
        echo ""

        if sudo apt-get update -qq && sudo apt-get install -y "${apt_installable[@]}"; then
            echo ""
            log_info "${GREEN}${BOLD}Successfully installed: ${apt_installable[*]}${NC}"
        else
            echo ""
            log_error "Failed to install packages via apt."
            return 1
        fi
    elif [[ ${#bootstrap_installable[@]} -gt 0 ]]; then
        log_info "${GREEN}${BOLD}All missing dependencies resolved via bootstrap.${NC}"
    else
        log_error "No installable or bootstrappable packages available."
        return 1
    fi

    return 0
}

# =============================================================================
# Interactive Prompt
# =============================================================================

prompt_install() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        return 0
    fi

    echo ""
    log_warn "${BOLD}Missing ${#MISSING_ENTRIES[@]} package(s):${NC}"
    echo ""

    for entry in "${MISSING_ENTRIES[@]}"; do
        IFS='|' read -r cmd pkg desc <<< "$entry"
        local resolved="${RESOLVED_PACKAGES[$pkg]:-not available}"
        local status="${RESOLVED_STATUS[$pkg]:-unknown}"
        if [[ "$status" == "available" ]]; then
            echo -e "  ${RED}✗${NC} $desc"
            echo -e "    ${DIM}apt package: $pkg ($resolved)${NC}"
        elif [[ "$status" == "bootstrap" ]]; then
            echo -e "  ${RED}✗${NC} $desc"
            echo -e "    ${CYAN}bootstrap: $resolved (no sudo needed)${NC}"
        else
            echo -e "  ${RED}✗${NC} $desc"
            echo -e "    ${RED}not available — install manually${NC}"
        fi
    done

    echo ""

    # Check if any are installable (apt or bootstrap)
    local any_installable=false
    for entry in "${MISSING_ENTRIES[@]}"; do
        local pkg="${entry#*|}"
        pkg="${pkg%%|*}"
        local status="${RESOLVED_STATUS[$pkg]:-}"
        if [[ "$status" == "available" || "$status" == "bootstrap" ]]; then
            any_installable=true
            break
        fi
    done

    if [[ "$any_installable" == "false" ]]; then
        log_error "None of the missing packages are available in apt."
        log_error "Install them manually, then retry: make install"
        return 1
    fi

    # Interactive prompt
    if [[ "$MODE" == "interactive" ]] && [[ -t 0 ]]; then
        echo -ne "${CYAN}${BOLD}Auto-install missing packages using sudo? [y/N] ${NC}"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY])
                echo ""
                install_missing
                return $?
                ;;
            *)
                echo ""
                log_info "Skipping auto-install."
                log_info "To install later, run: ${BOLD}sudo make pre-req${NC}"
                return 1
                ;;
        esac
    else
        # Non-interactive (piped input, CI)
        log_info "To install missing packages, run:"
        log_info "${BOLD}  sudo make pre-req${NC}"
        return 1
    fi
}

# =============================================================================
# Main Check Phase
# =============================================================================

log_section "System Pre-requisites Check"
log_info "Project: ${PROJECT_ROOT}"
echo ""

# --- Core Build Tools ---
log_section "Core Build Tools"
check_command "make"  "make"  "GNU Make"       || true
check_command "curl"  "curl"  "curl"            || true
check_c_compiler                                       || true

# --- System Dependencies (no bootstrap alternative) ---
log_section "System Dependencies"
check_command "git"     "git"             "Git version control"    || true
check_command "ssh"     "openssh-client"  "OpenSSH client"         || true
check_command "sshd"    "openssh-server"  "OpenSSH server"         || true
check_command "openssl" "openssl"         "OpenSSL toolkit"        || true
check_command "openvpn" "openvpn"         "OpenVPN client"         || true

# --- Additional Tools (bootstrap scripts need these) ---
log_section "Additional Tools"
check_command "tar"      "tar"      "tar archiver"    || true
check_command "gzip"     "gzip"     "gzip compression"  || true
check_command "dpkg-deb" "dpkg"     "dpkg-deb extractor" || true

# Check wget as curl alternative
if ! find_binary curl &> /dev/null && ! find_binary wget &> /dev/null; then
    log_miss "Neither curl nor wget found (need at least one)"
    _curl_already=false
    for entry in "${MISSING_ENTRIES[@]:-}"; do
        if [[ "$entry" == curl\|* ]]; then
            _curl_already=true
            break
        fi
    done
    if [[ "$_curl_already" == "false" ]]; then
        MISSING_ENTRIES+=("curl|curl|curl or wget")
    fi
else
    find_binary curl &> /dev/null && log_ok "curl available"
    find_binary wget &> /dev/null && log_ok "wget available"
fi

# =============================================================================
# Probe apt for all missing packages
# =============================================================================
probe_all_missing

# =============================================================================
# Report & Act
# =============================================================================

echo ""
log_section "Check Results"

if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
    log_info "${GREEN}${BOLD}All pre-requisites are satisfied!${NC}"
    echo ""
    log_info "You can proceed with: ${BOLD}make install${NC}"
    exit 0
fi

# Handle based on mode
case "$MODE" in
    ci)
        log_error "${BOLD}Missing ${#MISSING_ENTRIES[@]} package(s) — CI mode, failing.${NC}"
        echo ""
        for entry in "${MISSING_ENTRIES[@]}"; do
            IFS='|' read -r cmd pkg desc <<< "$entry"
            echo -e "  ${RED}✗${NC} $desc (needs: $pkg)"
        done
        echo ""
        log_error "Run: sudo make pre-req"
        exit 1
        ;;
    install)
        # Direct install mode — no prompt, just install
        install_missing
        exit $?
        ;;
    interactive|*)
        prompt_install
        exit $?
        ;;
esac
