#!/bin/bash

# Podman Safety Wrapper (Non-Invasive)
# Installs a shell alias to block destructive commands.

echo "--- Installing Podman Safety Alias ---"

RC_FILE="$HOME/.bashrc"
if [ -f "$HOME/.zshrc" ]; then
    RC_FILE="$HOME/.zshrc"
fi

ALIAS_CMD="podman_safe() {
    # Check for destructive combinations
    if [[ \"\$1\" == \"rm\" && ( \"\$*\" == *\"-a\"* || \"\$*\" == *\"--all\"* ) ]]; then
        echo \"❌ BLOCKED: Bulk container removal (rm -a) is forbidden.\"
        return 1
    fi
    if [[ \"\$1\" == \"system\" && \"\$2\" == \"prune\" ]]; then
        echo \"❌ BLOCKED: System prune is forbidden.\"
        return 1
    fi
    if [[ \"\$1\" == \"volume\" && \"\$2\" == \"rm\" && ( \"\$*\" == *\"-a\"* || \"\$*\" == *\"--all\"* ) ]]; then
        echo \"❌ BLOCKED: Bulk volume removal is forbidden.\"
        return 1
    fi

    command podman \"\$@\"
}"

# Check idempotency
if grep -q "podman_safe()" "$RC_FILE"; then
    echo "ℹ️  Alias already exists in $RC_FILE."
else
    echo "" >> "$RC_FILE"
    echo "# Podman Safety Alias" >> "$RC_FILE"
    echo "$ALIAS_CMD" >> "$RC_FILE"
    echo "alias podman=podman_safe" >> "$RC_FILE"
    echo "✅ Installed 'podman' alias to block destructive commands."
    echo "🔄 Please run: source $RC_FILE"
fi
