#!/usr/bin/env bash
# Helper functions for module detection and path resolution in AMI Orchestrator

# Detect which module PWD is in by walking up
# Returns module name (base, browser, etc.) or "." for root
_detect_current_module() {
    local current="$PWD"

    while [[ "$current" != "/" && "$current" != "$AMI_ROOT" ]]; do
        # Check if this is a module root (has backend/ or is a known module)
        local rel_path="${current#$AMI_ROOT/}"

        # If we're at a first-level directory under AMI_ROOT, that's likely the module
        if [[ "$rel_path" != "$current" && "$rel_path" != */* ]]; then
            echo "$rel_path"
            return 0
        fi

        current="$(dirname "$current")"
    done

    # Default to root
    echo "."
}

_find_module_root() {
    # Find module root by walking up looking for pyproject.toml or .venv
    # Returns path to module root or AMI_ROOT as default
    local current="$PWD"

    while [[ "$current" != "/" ]]; do
        # Module root has pyproject.toml or .venv
        if [[ -f "$current/pyproject.toml" ]]; then
            echo "$current"
            return 0
        fi
        if [[ -d "$current/.venv" ]]; then
            echo "$current"
            return 0
        fi
        current="$(dirname "$current")"
    done

    # Default to AMI_ROOT
    echo "$AMI_ROOT"
}
