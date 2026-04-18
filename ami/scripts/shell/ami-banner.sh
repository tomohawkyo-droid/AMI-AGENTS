#!/usr/bin/env bash
# AMI Orchestrator Banner - delegates to banner_helper.py for
# manifest-based extension discovery and rendering.

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[38;5;203m'
NC='\033[0m'

# Define quiet mode echo function
_ami_echo() {
    if [[ "$AMI_QUIET_MODE" != "1" ]]; then
        echo -e "$@"
    fi
}

# Function to display the banner
display_banner() {
    # Ignore any --exclude-categories args (rendering is now done in
    # Python via banner_helper.py which inspects manifests directly).
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --exclude-categories) shift ;;
        esac
        shift
    done

    _ami_echo "${GREEN}✓${NC} AMI Orchestrator shell environment configured successfully!"
    _ami_echo ""
    local banner_output
    banner_output=$(python3 "$AMI_ROOT/ami/utils/banner.py" --project-root "$AMI_ROOT" 2>/dev/null)
    if [[ -n "$banner_output" ]]; then
        while IFS= read -r line; do
            _ami_echo " $line"
        done <<< "$banner_output"
    else
        _ami_echo "  OpenAMI"
    fi
    _ami_echo ""
    _ami_echo "${GREEN}> Secure infrastructure for distributed enterprise automation and governance."
    _ami_echo "> Supports bare metal, cloud, and hybrid deployments without vendor lock-in."
    _ami_echo "> Safely integrates with any local or remote web, data, and API service."
    _ami_echo "${RED}"
    _ami_echo "================================================================================"
    _ami_echo "> Transparent and auditable open-source framework by Independent AI Labs."
    _ami_echo "> Full NIST AI CSF/RMF, ISO 42001/27001, and EU AI Act compliance."
    _ami_echo "================================================================================"
    _ami_echo "${NC}"

    # Display extensions via Python helper (manifest-based discovery)
    local _banner_helper="$AMI_ROOT/ami/scripts/shell/banner_helper.py"
    if [[ -f "$_banner_helper" ]]; then
        local _quiet_flag=""
        [[ "$AMI_QUIET_MODE" == "1" ]] && _quiet_flag="--quiet"
        python3 "$_banner_helper" --mode banner $_quiet_flag 2>/dev/null || true
    fi
}

# Function to display system status
display_system_status() {
    local sys_info_script="$AMI_ROOT/ami/scripts/utils/sys_info.py"
    if [[ -f "$sys_info_script" ]]; then
        # Use uv run to ensure we have psutil available
        uv run python "$sys_info_script" 2>/dev/null || {
            # Fallback if uv not available
            echo -e "${BLUE}📊 Storage Status:${NC}"
            echo -e "  > Free space (root): $(df -h . | awk 'NR==2 {print $4}') available ($(df -h . | awk 'NR==2 {print $5}') used)"
            echo -e "  > Repository size:   $(du -sh . 2>/dev/null | awk '{print $1}')"
            echo -e ""
        }
    else
        echo -e "${BLUE}📊 Storage Status:${NC}"
        echo -e "  > Free space (root): $(df -h . | awk 'NR==2 {print $4}') available ($(df -h . | awk 'NR==2 {print $5}') used)"
        echo -e "  > Repository size:   $(du -sh . 2>/dev/null | awk '{print $1}')"
        echo -e ""
    fi
}

# Standalone invocation support
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ -z "${AMI_ROOT:-}" ]]; then
        echo "Error: AMI_ROOT not set" >&2
        exit 1
    fi
    display_banner "$@"
fi
