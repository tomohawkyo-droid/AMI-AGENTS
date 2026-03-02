#!/usr/bin/env bash
# scripts/bootstrap_ansible.sh
set -euo pipefail

# Ansible Bootstrap Script for AMI-ORCHESTRATOR
# Installs Ansible into .boot-linux/python-env and creates symlinks in .boot-linux/bin

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
UV_CMD="$BOOT_LINUX_DIR/bin/uv"
PYTHON_ENV="$BOOT_LINUX_DIR/python-env"
BIN_DIR="$BOOT_LINUX_DIR/bin"

# Color output
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }

log_info "Installing Ansible and dependencies..."
"$UV_CMD" pip install --reinstall --python "$PYTHON_ENV" ansible passlib

# Verify installation
if "$PYTHON_ENV/bin/ansible" --version > /dev/null 2>&1; then
    VERSION=$("$PYTHON_ENV/bin/ansible" --version | head -1)
    log_info "Ansible installed: $VERSION"
else
    echo "ERROR: Ansible installation failed" >&2
    exit 1
fi

# Create symlinks in .boot-linux/bin for ansible binaries
log_info "Creating symlinks in $BIN_DIR"
mkdir -p "$BIN_DIR"

ANSIBLE_BINARIES=(
    ansible
    ansible-playbook
    ansible-galaxy
    ansible-vault
    ansible-config
    ansible-console
    ansible-doc
    ansible-inventory
    ansible-pull
)

for binary in "${ANSIBLE_BINARIES[@]}"; do
    if [[ -x "$PYTHON_ENV/bin/$binary" ]]; then
        ln -sf "$PYTHON_ENV/bin/$binary" "$BIN_DIR/$binary"
        log_info "  Symlinked $binary"
    fi
done

log_info "Ansible bootstrap complete."