#!/usr/bin/env bash
# AMI Orchestrator Banner - Dynamically Generated from Extensions
#
# Reads extension metadata from ami/config/extensions.yaml (single source of truth)

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

# Check if a Docker container is running
_check_container() {
    local name="$1"
    docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null | grep -q "true"
}

# Get version from Docker container image tag
_get_container_version() {
    local name="$1"
    local image
    image=$(docker inspect --format '{{.Config.Image}}' "$name" 2>/dev/null) || return
    echo "$image" | grep -oP ':\K[\d.]+' | head -1
}

# Parse extensions.yaml and output as pipe-delimited lines
# Output format: name|description|category|binary|features|hidden
_parse_extensions_yaml() {
    local yaml_file="$AMI_ROOT/ami/config/extensions.yaml"
    [[ -f "$yaml_file" ]] || return 1

    python3 -c "
import yaml
with open('$yaml_file') as f:
    data = yaml.safe_load(f)
for ext in data.get('extensions', []):
    name = ext.get('name', '')
    desc = ext.get('description', '')
    cat = ext.get('category', '')
    binary = ext.get('binary', '')
    features = ext.get('features', '')
    hidden = ext.get('hidden', '')
    container = ext.get('container', '')
    print(f'{name}|{desc}|{cat}|{binary}|{features}|{hidden}|{container}')
" 2>/dev/null
}

# Print a component line with healthcheck
_print_component() {
    local name="$1"
    local color="$2"
    local desc="$3"
    local bin_path="$4"
    local features="$5"
    local container="$6"
    local version=""
    local status_icon=""

    if [[ -n "$container" ]]; then
        # Container-backed command: wrapper script must exist
        if [[ -n "$bin_path" ]] && ! _check_bin "$bin_path"; then
            return 1
        fi
        # Check container status
        if _check_container "$container"; then
            version=$(_get_container_version "$container")
            if [[ -n "$version" ]]; then
                status_icon="${GREEN}v${version}${NC}"
            else
                status_icon="${GREEN}✓ running${NC}"
            fi
        else
            status_icon="${RED}✗ container not running${NC}"
        fi
    elif [[ -n "$bin_path" ]]; then
        # Standard binary check
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

# Load extension metadata for banner display from extensions.yaml
_load_extension_metadata() {
    declare -gA EXT_DATA
    declare -ga EXT_CORE=()
    declare -ga EXT_ENTERPRISE=()
    declare -ga EXT_DEV=()
    declare -ga EXT_AGENTS=()

    while IFS='|' read -r name desc category binary features hidden container; do
        [[ -z "$name" ]] && continue
        [[ "$hidden" == "true" ]] && continue
        [[ "$hidden" == "True" ]] && continue

        EXT_DATA["${name}_desc"]="$desc"
        EXT_DATA["${name}_binary"]="$binary"
        EXT_DATA["${name}_features"]="$features"
        EXT_DATA["${name}_container"]="$container"

        case "$category" in
            core)       EXT_CORE+=("$name") ;;
            enterprise) EXT_ENTERPRISE+=("$name") ;;
            dev)        EXT_DEV+=("$name") ;;
            agents)     EXT_AGENTS+=("$name") ;;
        esac
    done < <(_parse_extensions_yaml)
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
        local container="${EXT_DATA[${name}_container]}"
        # Container-backed commands are always shown if wrapper exists
        if [[ -n "$container" ]]; then
            if [[ -z "$binary" ]] || _check_bin "$binary"; then
                has_installed=1
                break
            fi
        elif [[ -z "$binary" ]] || _check_bin "$binary"; then
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
        local container="${EXT_DATA[${name}_container]}"

        _print_component "$name" "$color" "$desc" "$binary" "$features" "$container"
    done
}

# Function to display the banner
display_banner() {
    local exclude_categories=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --exclude-categories) shift; exclude_categories="$1" ;;
        esac
        shift
    done

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

    # Display each category, skipping excluded ones
    for cat in "${CATEGORY_ORDER[@]}"; do
        if [[ -n "$exclude_categories" ]] && echo ",$exclude_categories," | grep -q ",$cat,"; then
            continue
        fi
        local arr_name="EXT_${cat^^}"
        _display_category "$cat" "$arr_name"
    done
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
