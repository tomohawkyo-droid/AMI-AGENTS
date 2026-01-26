#!/usr/bin/env bash
# AMI Orchestrator Banner - Dynamically Generated from Extensions
#
# This banner parses extension metadata from ami/scripts/extensions/*.sh
# Each extension defines: @name, @description, @category, @binary, @features

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
GOLD='\033[38;5;214m'
PINK='\033[38;5;205m'
RED='\033[38;5;203m'
PURPLE='\033[38;5;99m'
CYAN='\033[0;36m'
ORANGE='\033[0;33m'
DIM='\033[2m'
NC='\033[0m'

# Category display configuration
declare -A CATEGORY_COLORS=(
    ["core"]="$GOLD"
    ["enterprise"]="$CYAN"
    ["dev"]="$PINK"
    ["agents"]="$RED"
)

declare -A CATEGORY_ICONS=(
    ["core"]="🟡"
    ["enterprise"]="🌐"
    ["dev"]="🌸"
    ["agents"]="🤖"
)

declare -A CATEGORY_TITLES=(
    ["core"]="Core Execution & Management"
    ["enterprise"]="Enterprise Services"
    ["dev"]="Development Tools"
    ["agents"]="AI Coding Agents (REQUIRE HUMAN SUPERVISION)"
)

# Category display order
CATEGORY_ORDER=("core" "enterprise" "dev" "agents")

# Define quiet mode echo function
_ami_echo() {
    if [[ "$AMI_QUIET_MODE" != "1" ]]; then
        echo -e "$@"
    fi
}

# Check if a binary/script exists
_check_bin() {
    local path="$AMI_ROOT/$1"
    if [[ "$1" == *.py ]]; then
        [[ -f "$path" ]]
    else
        [[ -x "$path" ]] || [[ -f "$path" ]]
    fi
}

# Get version from binary/script
_get_version() {
    local bin="$AMI_ROOT/$1"
    local output
    if [[ "$1" == *.py ]]; then
        [[ -f "$bin" ]] || return
        output=$(python3 "$bin" --version 2>&1 | head -1) || return
    else
        [[ -x "$bin" ]] || [[ -f "$bin" ]] || return
        output=$("$bin" --version 2>&1 | head -1) || return
    fi
    echo "$output" | grep -oP '\d+\.\d+\.\d+' | head -1
}

# Parse metadata from extension file
# Returns: name|description|category|binary|features|hidden
_parse_extension_metadata() {
    local file="$1"
    local name="" desc="" category="" binary="" features="" hidden=""

    while IFS= read -r line; do
        case "$line" in
            "# @name: "*)        name="${line#\# @name: }" ;;
            "# @description: "*) desc="${line#\# @description: }" ;;
            "# @category: "*)    category="${line#\# @category: }" ;;
            "# @binary: "*)      binary="${line#\# @binary: }" ;;
            "# @features: "*)    features="${line#\# @features: }" ;;
            "# @hidden: "*)      hidden="${line#\# @hidden: }" ;;
        esac
    done < "$file"

    echo "$name|$desc|$category|$binary|$features|$hidden"
}

# Print a component line with healthcheck
_print_component() {
    local name="$1"
    local color="$2"
    local desc="$3"
    local bin_path="$4"
    local features="$5"
    local version=""
    local status_icon=""

    # Check binary and get version
    if [[ -n "$bin_path" ]]; then
        if _check_bin "$bin_path"; then
            version=$(_get_version "$bin_path")
            if [[ -n "$version" ]]; then
                status_icon="${GREEN}v${version}${NC}"
            else
                status_icon="${GREEN}✓${NC}"
            fi
        else
            # Binary not found - skip this component
            return 1
        fi
    else
        status_icon="${GREEN}✓${NC}"
    fi

    # Print component line
    _ami_echo "  ${color}> ${name}${NC}$(printf '%*s' $((12 - ${#name})) '')→ ${desc} ${status_icon}"

    # Print features if available
    if [[ -n "$features" ]]; then
        _ami_echo "                    ${DIM}${features}${NC}"
    fi
    _ami_echo ""
    return 0
}

# Load extension metadata for banner display
_load_extension_metadata() {
    local ext_dir="$AMI_ROOT/ami/scripts/extensions"

    declare -gA EXT_DATA
    declare -ga EXT_CORE=()
    declare -ga EXT_ENTERPRISE=()
    declare -ga EXT_DEV=()
    declare -ga EXT_AGENTS=()

    for ext_file in "$ext_dir"/*.sh; do
        [[ -f "$ext_file" ]] || continue

        local metadata
        metadata=$(_parse_extension_metadata "$ext_file")

        local name desc category binary features hidden
        IFS='|' read -r name desc category binary features hidden <<< "$metadata"

        [[ -z "$name" ]] && continue
        [[ "$hidden" == "true" ]] && continue

        EXT_DATA["${name}_desc"]="$desc"
        EXT_DATA["${name}_binary"]="$binary"
        EXT_DATA["${name}_features"]="$features"

        case "$category" in
            core)       EXT_CORE+=("$name") ;;
            enterprise) EXT_ENTERPRISE+=("$name") ;;
            dev)        EXT_DEV+=("$name") ;;
            agents)     EXT_AGENTS+=("$name") ;;
        esac
    done
}

# Display a category section
_display_category() {
    local category="$1"
    local -n items="$2"
    local color="${CATEGORY_COLORS[$category]}"
    local icon="${CATEGORY_ICONS[$category]}"
    local title="${CATEGORY_TITLES[$category]}"

    # Check if any items in this category are installed
    local has_installed=0
    for name in "${items[@]}"; do
        local binary="${EXT_DATA[${name}_binary]}"
        if [[ -z "$binary" ]] || _check_bin "$binary"; then
            has_installed=1
            break
        fi
    done

    # Skip category if nothing installed
    [[ $has_installed -eq 0 ]] && return

    _ami_echo "${color}${icon} ${title}:${NC}"
    _ami_echo ""

    for name in "${items[@]}"; do
        local desc="${EXT_DATA[${name}_desc]}"
        local binary="${EXT_DATA[${name}_binary]}"
        local features="${EXT_DATA[${name}_features]}"

        _print_component "$name" "$color" "$desc" "$binary" "$features"
    done
}

# Function to display the banner
display_banner() {
    _ami_echo "${GREEN}✓${NC} AMI Orchestrator shell environment configured successfully!"
    _ami_echo ""
    _ami_echo " __       ___                         _     __  __  ___ "
    _ami_echo " \\ \\     / _ \\  _ __   ___  _ __     / \\   |  \\/  ||_ _|        __   ___   __"
    _ami_echo "  \\ \\   | | | || '_ \\ / _ \\| '_ \\   / _ \\  | |\\/| | | |   __ __/  \\ |_  ) /  \\\\\\\\"
    _ami_echo "  / /   | |_| || |_) |  __/| | | | / ___ \\ | |  | | | |   \\ V / () | / / | () |"
    _ami_echo " /_/     \\___/ | .__/ \\___||_| |_|/_/   \\_\\|_|  |_||___|   \\_/ \\__(_)___(_)__/"
    _ami_echo "               |_|"
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

    # Load extension metadata for display
    _load_extension_metadata

    # Display each category
    _display_category "core" EXT_CORE
    _display_category "enterprise" EXT_ENTERPRISE
    _display_category "dev" EXT_DEV
    _display_category "agents" EXT_AGENTS
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
