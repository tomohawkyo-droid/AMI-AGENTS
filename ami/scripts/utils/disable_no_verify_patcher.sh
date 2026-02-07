#!/bin/bash

# Git Safety Patcher
# Installs a wrapper script in .boot-linux/bin/git to block destructive commands.
# Also installs shell function as backup for interactive shells.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"

echo "--- Installing Git Safety Wrapper ---"

# Create bin directory if needed
mkdir -p "${BIN_DIR}"

# Use bootstrapped git (built from source in .boot-linux/git)
REAL_GIT="${BOOT_LINUX_DIR}/git/bin/git"
if [ ! -x "$REAL_GIT" ]; then
    # Fallback to system git if bootstrapped git not yet installed
    REAL_GIT="/usr/bin/git"
    if [ ! -x "$REAL_GIT" ]; then
        REAL_GIT=$(command -v git 2>/dev/null || true)
        if [ -z "$REAL_GIT" ] || [ ! -x "$REAL_GIT" ]; then
            echo "ERROR: Cannot find git binary"
            exit 1
        fi
    fi
    echo "⚠️  Using system git: $REAL_GIT (bootstrapped git not found)"
    echo "   Run 'make bootstrap-core' to install bootstrapped git"
fi

# IMPORTANT: Check if the target is a symlink and remove it
# This prevents overwriting the real binary if .boot-linux/bin/git points to it
if [[ -L "${BIN_DIR}/git" ]]; then
    echo "Removing existing git symlink..."
    rm "${BIN_DIR}/git"
fi

# Create the wrapper script
cat > "${BIN_DIR}/git" <<WRAPPER_EOF
#!/usr/bin/env bash
# Git Safety Guard - Blocks destructive commands
# Calls ${REAL_GIT} after safety checks

set -euo pipefail

REAL_GIT="${REAL_GIT}"

block() {
    echo "❌ BLOCKED: \$1"
    echo "This command is forbidden to prevent data loss."
    exit 1
}

# Handle empty args
if [[ \$# -eq 0 ]]; then
    exec "\$REAL_GIT"
fi

cmd="\$1"

# 1. Block destructive commands
case "\$cmd" in
    reset)    block "git reset" ;;
    checkout) block "git checkout" ;;
    clean)    block "git clean" ;;
    restore)  block "git restore" ;;
    rm)       block "git rm" ;;
    rebase)   block "git rebase" ;;
    gc)       block "git gc" ;;
    prune)    block "git prune" ;;
esac

# 2. Block destructive sub-commands
if [[ "\$cmd" == "stash" ]]; then
    for arg in "\$@"; do
        [[ "\$arg" == "drop" ]] && block "git stash drop"
        [[ "\$arg" == "clear" ]] && block "git stash clear"
    done
fi

if [[ "\$cmd" == "branch" ]]; then
    for arg in "\$@"; do
        [[ "\$arg" == "-D" ]] && block "git branch -D (use -d instead)"
    done
fi

if [[ "\$cmd" == "push" ]]; then
    for arg in "\$@"; do
        [[ "\$arg" == "--force" || "\$arg" == "-f" ]] && block "git push --force"
        [[ "\$arg" == "--force-with-lease" ]] && block "git push --force-with-lease"
    done
fi

# 3. Block destructive flags globally
for arg in "\$@"; do
    [[ "\$arg" == "--hard" ]] && block "--hard flag"
    [[ "\$arg" == "--no-verify" ]] && block "--no-verify flag"
done

# Safe - pass through to real git
exec "\$REAL_GIT" "\$@"
WRAPPER_EOF

chmod +x "${BIN_DIR}/git"
echo "✅ Installed git wrapper to ${BIN_DIR}/git"

# Verify wrapper is in PATH before system git
WHICH_GIT=$(which git 2>/dev/null || true)
if [[ "$WHICH_GIT" == "${BIN_DIR}/git" ]]; then
    echo "✅ Wrapper is first in PATH"
else
    echo "⚠️  WARNING: ${BIN_DIR} may not be first in PATH"
    echo "   Current 'which git': $WHICH_GIT"
    echo "   Ensure .boot-linux/bin is in PATH before /usr/bin"
fi

echo ""
echo "🎉 Git safety guard installed."
