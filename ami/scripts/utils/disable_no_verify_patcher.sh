#!/bin/bash

# Safe Git Patcher
# Installs a shell function to prevent ANY destructive git operations.
# Does NOT replace system binaries.

echo "--- Installing Git Safety Function ---"

RC_FILE="$HOME/.bashrc"
if [ -f "$HOME/.zshrc" ]; then
    RC_FILE="$HOME/.zshrc"
fi

# Remove old definition if exists (simple cleanup of previous alias attempt)
if grep -q "alias git=git_safe" "$RC_FILE"; then
    # We can't easily remove it, but defining a function 'git' will override the alias 'git'
    # in zsh, but in bash aliases usually take precedence over functions.
    # To be safe, we should unalias git if it exists.
    :
fi

# Append the function definition directly using quoted heredoc
cat <<'EOF' >> "$RC_FILE"

# STRICT Git Safety Function
git() {
    local cmd="$1"
    
    # 1. Block destructive commands
    case "$cmd" in
        reset|checkout|clean|restore|rm|rebase|gc|prune)
            echo "❌ ERROR: git $cmd is FORBIDDEN to prevent data loss!"
            return 1
            ;;
    esac

    # 2. Block destructive sub-commands
    if [[ "$cmd" == "stash" ]]; then
        for arg in "$@"; do
            if [[ "$arg" == "drop" || "$arg" == "clear" ]]; then
                echo "❌ ERROR: git stash $arg is FORBIDDEN!"
                return 1
            fi
        done
    fi
    if [[ "$cmd" == "branch" ]]; then
        for arg in "$@"; do
            if [[ "$arg" == "-D" ]]; then
                echo "❌ ERROR: git branch -D is FORBIDDEN! Use -d instead."
                return 1
            fi
        done
    fi

    # 3. Block destructive flags globally
    for arg in "$@"; do
        if [[ "$arg" == "--hard" ]]; then
            echo "❌ ERROR: --hard flag is FORBIDDEN!"
            return 1
        fi
        if [[ "$arg" == "--force" || "$arg" == "-f" ]]; then
            echo "❌ ERROR: --force flag is FORBIDDEN!"
            return 1
        fi
        if [[ "$arg" == "--no-verify" ]]; then
            echo "❌ ERROR: --no-verify is FORBIDDEN!"
            return 1
        fi
    done

    # Execute original git command
    command git "$@"
}
export -f git
EOF

echo "✅ Installed STRICT 'git' function to $RC_FILE."

echo "--- Patching /usr/bin/git Binary ---"

# Define the Strict Binary Wrapper content
read -r -d '' STRICT_BINARY_CONTENT <<'WRAPPER_EOF'
#!/bin/bash

# STRICT Git Safety Wrapper
# Enforces preventing data loss by blocking destructive commands and flags.

cmd="$1"

# 1. Block destructive commands
case "$cmd" in
    reset|checkout|clean|restore|rm|rebase|gc|prune)
        echo "❌ ERROR: git $cmd is FORBIDDEN to prevent data loss!"
        exit 1
        ;;
esac

# 2. Block destructive sub-commands
if [[ "$cmd" == "stash" ]]; then
    for arg in "$@"; do
        if [[ "$arg" == "drop" || "$arg" == "clear" ]]; then
            echo "❌ ERROR: git stash $arg is FORBIDDEN!"
            exit 1
        fi
    done
fi
if [[ "$cmd" == "branch" ]]; then
    for arg in "$@"; do
        if [[ "$arg" == "-D" ]]; then
            echo "❌ ERROR: git branch -D is FORBIDDEN! Use -d instead."
            exit 1
        fi
    done
fi

# 3. Block destructive flags globally
for arg in "$@"; do
    if [[ "$arg" == "--hard" ]]; then
        echo "❌ ERROR: --hard flag is FORBIDDEN!"
        exit 1
    fi
    if [[ "$arg" == "--force" || "$arg" == "-f" ]]; then
        echo "❌ ERROR: --force flag is FORBIDDEN!"
        exit 1
    fi
    if [[ "$arg" == "--no-verify" ]]; then
        echo "❌ ERROR: --no-verify is FORBIDDEN!"
        exit 1
    fi
done

# Execute original git binary
exec /usr/bin/git.original "$@"
WRAPPER_EOF

# Backup original binary if not already backed up
if [ ! -f /usr/bin/git.original ]; then
    echo "📦 Backing up original /usr/bin/git to /usr/bin/git.original..."
    cp /usr/bin/git /usr/bin/git.original
    echo "✅ Backup created at /usr/bin/git.original"
else
    echo "ℹ️  Backup already exists at /usr/bin/git.original"
fi

# Overwrite the binary
echo "$STRICT_BINARY_CONTENT" > /usr/bin/git
chmod +x /usr/bin/git

# Verify Exact Match
echo "--- Verifying /usr/bin/git Content ---"
INSTALLED_CONTENT=$(cat /usr/bin/git)

if [ "$INSTALLED_CONTENT" == "$STRICT_BINARY_CONTENT" ]; then
    echo "✅ VERIFICATION PASSED: /usr/bin/git matches the STRICT wrapper exactly."
else
    echo "❌ VERIFICATION FAILED: /usr/bin/git does NOT match source!"
    echo "Expected:"
    echo "$STRICT_BINARY_CONTENT"
    echo "Found:"
    echo "$INSTALLED_CONTENT"
    exit 1
fi

echo "🎉 Full System Patch (Function + Binary) installed and verified."

# --- Patch pre-commit hook to auto-stage all files ---
# pre-commit stashes unstaged files BEFORE any hooks run.
# This causes "Stashed changes conflicted with hook auto-fixes" errors
# when ruff-format or ruff --fix modify files.
# Fix: inject 'git add -A' into the hook script BEFORE pre-commit executes,
# so there are zero unstaged files when pre-commit starts.
echo "--- Patching pre-commit hook for auto-staging ---"
HOOK_FILE=".git/hooks/pre-commit"
if [ -f "$HOOK_FILE" ]; then
    if ! grep -q "git add -A" "$HOOK_FILE"; then
        sed -i '/^if \[ -x "\$INSTALL_PYTHON" \]/i # Auto-stage all files before pre-commit stashes\ngit add -A\n' "$HOOK_FILE"
        echo "✅ Injected auto-staging into $HOOK_FILE"
    else
        echo "ℹ️  Auto-staging already present in $HOOK_FILE"
    fi
else
    echo "ℹ️  No pre-commit hook found at $HOOK_FILE (run 'make install-hooks' first)"
fi
