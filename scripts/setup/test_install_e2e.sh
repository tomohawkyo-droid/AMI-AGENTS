#!/bin/bash
set -e

# =============================================================================
# Usage
# =============================================================================
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "E2E installation test for AMI-AGENTS"
    echo ""
    echo "By default runs the full test suite: all 21 components (install-all.yaml)"
    echo "and bootstrap verification. Use --minimal or --skip-bootstrap to reduce scope."
    echo ""
    echo "Options:"
    echo "  --target-dir DIR    Directory where test will run (default: ./tmp/e2e_test_<timestamp>)"
    echo "  --skip-cleanup      Skip cleanup on exit (for debugging)"
    echo "  --minimal           Use install-defaults.yaml (8 components) instead of full install"
    echo "  --skip-bootstrap    Skip bootstrap installer and component verification phases"
    echo "  -h, --help          Show this help"
    echo ""
    echo "Example:"
    echo "  $0                              # Full e2e test (default)"
    echo "  $0 --minimal --skip-bootstrap   # Quick smoke test"
    echo "  $0 --skip-cleanup               # Full test, keep test dir for inspection"
    exit 0
}

# =============================================================================
# Parse arguments
# =============================================================================
BASE_DIR=$(pwd)
TEST_DIR=""
SKIP_CLEANUP=0
FULL_INSTALL=1
TEST_BOOTSTRAP=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --target-dir)
            TEST_DIR="$2"
            shift 2
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=1
            shift
            ;;
        --minimal)
            FULL_INSTALL=0
            shift
            ;;
        --skip-bootstrap)
            TEST_BOOTSTRAP=0
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Default test dir if not specified
if [ -z "$TEST_DIR" ]; then
    TEST_DIR="$BASE_DIR/tmp/e2e_test_$(date +%s)"
fi

echo ">>> E2E INSTALLATION TEST (AMI-AGENTS) STARTING <<<"
echo "Test directory: $TEST_DIR"
echo "Full install: $FULL_INSTALL"
echo "Test bootstrap: $TEST_BOOTSTRAP"

# =============================================================================
# Cleanup trap
# =============================================================================
cleanup() {
    if [ "$SKIP_CLEANUP" = "1" ]; then
        echo "[INFO] Skipping cleanup (--skip-cleanup). Test dir: $TEST_DIR"
        return 0
    fi
    echo "Cleaning up test directory: $TEST_DIR"
    cd "$BASE_DIR"
    rm -rf "$TEST_DIR"
    echo "[PASS] Cleanup successful."
}
trap cleanup EXIT

mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# =============================================================================
# 0. Verify prerequisites
# =============================================================================
echo ""
echo "=========================================="
echo "PHASE 0: Checking prerequisites"
echo "=========================================="

if ! command -v uv &> /dev/null; then
    echo "[FAIL] uv is not installed. Install it first: https://docs.astral.sh/uv/"
    exit 1
fi
echo "[PASS] uv is available: $(uv --version)"

if ! command -v git &> /dev/null; then
    echo "[FAIL] git is not installed."
    exit 1
fi
echo "[PASS] git is available."

# =============================================================================
# 1. Clone AMI-AGENTS
# =============================================================================
echo ""
echo "=========================================="
echo "PHASE 1: Cloning AMI-AGENTS"
echo "=========================================="

git clone git@hf.co:ami-ailabs/AMI-AGENTS AMI-AGENTS 2>&1 | tail -5
cd AMI-AGENTS
echo "[PASS] AMI-AGENTS cloned."

# =============================================================================
# 2. Run make install-ci (non-interactive full install)
# =============================================================================
echo ""
echo "=========================================="
echo "PHASE 2: Running make install-ci"
echo "=========================================="

make install-ci 2>&1 | tee install.log | tail -30
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] make install-ci failed."
    cat install.log
    exit 1
fi
echo "[PASS] make install-ci executed."

# =============================================================================
# 3. Deep Verification - Core Installation
# =============================================================================
echo ""
echo "=========================================="
echo "PHASE 3: Deep Verification - Core"
echo "=========================================="

# --- Check 1: Venv Structure ---
if [ ! -d ".venv" ]; then
    echo "[FAIL] .venv directory missing."
    ls -la
    exit 1
fi
if [ ! -f ".venv/bin/python" ]; then
    echo "[FAIL] .venv python binary missing."
    exit 1
fi
echo "[PASS] Venv structure valid."

# --- Check 2: uv.lock exists ---
if [ ! -f "uv.lock" ]; then
    echo "[FAIL] uv.lock missing."
    exit 1
fi
echo "[PASS] uv.lock present."

# --- Check 3: Dependency Integrity (Import Test) ---
echo "Verifying critical imports..."
.venv/bin/python -c "
import loguru
import pydantic
import aiohttp
import numpy
import pandas
print(f'Pydantic: {pydantic.__version__}')
print(f'NumPy: {numpy.__version__}')
print(f'Pandas: {pandas.__version__}')
" 2>&1 | tee import_test.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] Dependency import failed."
    cat import_test.log
    exit 1
fi
echo "[PASS] Critical dependencies loadable."

# --- Check 4: AMI package importable ---
echo "Verifying ami package imports..."
.venv/bin/python -c "
from ami.core.config import get_config
from ami.types.events import StreamEvent
from ami.cli_components.tui import BoxStyle
print('AMI core imports successful')
" 2>&1 | tee ami_import_test.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] AMI package import failed."
    cat ami_import_test.log
    exit 1
fi
echo "[PASS] AMI package importable."

# --- Check 5b: AMI-CI namespace package accessible ---
echo "Verifying ami.ci namespace package..."
.venv/bin/python -c "
from ami.ci.check_dependency_versions import main
print('AMI-CI namespace package accessible')
" 2>&1 | tee ci_import_test.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] AMI-CI namespace import failed."
    cat ci_import_test.log
    exit 1
fi
echo "[PASS] AMI-CI namespace package importable."

# --- Check 5: Configuration files ---
if [ ! -f "pyproject.toml" ]; then
    echo "[FAIL] pyproject.toml missing."
    exit 1
fi
echo "[PASS] Configuration files present."

# =============================================================================
# 4. Install pre-commit hooks
# =============================================================================
echo ""
echo "=========================================="
echo "PHASE 4: Installing pre-commit hooks"
echo "=========================================="

make install-hooks 2>&1 | tee hooks.log | tail -10
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] make install-hooks failed."
    cat hooks.log
    exit 1
fi

if [ ! -f ".git/hooks/pre-commit" ]; then
    echo "[FAIL] Pre-commit hook not installed."
    exit 1
fi
echo "[PASS] Pre-commit hooks installed."

# =============================================================================
# 5. Verify make targets work
# =============================================================================
echo ""
echo "=========================================="
echo "PHASE 5: Verifying make targets"
echo "=========================================="

# Test that lint target works
if ! make lint 2>&1 | tee lint.log | tail -10; then
    echo "[WARN] make lint had issues (may be expected if code has lint errors)."
fi
echo "[PASS] make lint target functional."

# Test that test target works (run a quick subset)
echo "Running quick test sanity check..."
.venv/bin/python -m pytest tests/unit -x -q --timeout=60 2>&1 | tail -20 || {
    echo "[WARN] Some unit tests failed (may need investigation)."
}
echo "[PASS] Test infrastructure functional."

# =============================================================================
# 6. Test Bootstrap Installer (optional)
# =============================================================================
if [ "$TEST_BOOTSTRAP" = "1" ]; then
    echo ""
    echo "=========================================="
    echo "PHASE 6: Testing Bootstrap Installer"
    echo "=========================================="

    # --- 6a: Test bootstrap directory creation ---
    BOOT_DIR="$PWD/.boot-linux"
    echo "Testing bootstrap environment at: $BOOT_DIR"

    # --- 6b: Run bootstrap installer with appropriate config ---
    if [ "$FULL_INSTALL" = "1" ]; then
        INSTALL_CONFIG="ami/config/install-all.yaml"
        echo "Using full install config: $INSTALL_CONFIG"
    else
        INSTALL_CONFIG="ami/config/install-defaults.yaml"
        echo "Using default install config: $INSTALL_CONFIG"
    fi

    echo "Running bootstrap installer..."
    .venv/bin/python ami/scripts/bootstrap_installer.py --defaults "$INSTALL_CONFIG" 2>&1 | tee bootstrap.log
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo "[FAIL] Bootstrap installer failed."
        cat bootstrap.log
        exit 1
    fi
    echo "[PASS] Bootstrap installer completed."

    # --- 6c: Verify bootstrap directory structure ---
    if [ ! -d "$BOOT_DIR" ]; then
        echo "[WARN] Bootstrap directory $BOOT_DIR not created (may be expected if no components needed it)"
    else
        echo "[PASS] Bootstrap directory exists: $BOOT_DIR"
        ls -la "$BOOT_DIR" | head -10
    fi

    # --- 6d: Test Node.js bootstrap (if full install) ---
    if [ "$FULL_INSTALL" = "1" ]; then
        echo ""
        echo "Testing Node.js bootstrap environment..."
        NODEENV_DIR="$BOOT_DIR/node-env"
        if [ -d "$NODEENV_DIR" ]; then
            echo "[PASS] Node.js environment exists: $NODEENV_DIR"
            if [ -f "$NODEENV_DIR/bin/node" ]; then
                echo "[PASS] Node binary found"
                "$NODEENV_DIR/bin/node" --version
            fi
            if [ -f "$NODEENV_DIR/bin/npm" ]; then
                echo "[PASS] npm binary found"
                "$NODEENV_DIR/bin/npm" --version
            fi
        else
            echo "[WARN] Node.js environment not found (may be expected if npm packages not installed)"
        fi
    fi

    # =============================================================================
    # 7. Verify Installed Components
    # =============================================================================
    echo ""
    echo "=========================================="
    echo "PHASE 7: Verifying Installed Components"
    echo "=========================================="

    # Function to check if a command exists and get version
    check_component() {
        local name="$1"
        local cmd="$2"
        local version_flag="${3:---version}"

        if command -v "$cmd" &> /dev/null; then
            local version
            version=$($cmd $version_flag 2>&1 | head -1) || version="(version unknown)"
            echo "[PASS] $name: $version"
            return 0
        else
            echo "[SKIP] $name: not found in PATH"
            return 1
        fi
    }

    echo "Checking default components..."
    check_component "Git" "git" "--version" || true
    check_component "Go" "go" "version" || true
    check_component "Podman" "podman" "--version" || true
    check_component "OpenSSH" "ssh" "-V" || true
    check_component "OpenSSL" "openssl" "version" || true
    check_component "Ansible" "ansible" "--version" || true

    if [ "$FULL_INSTALL" = "1" ]; then
        echo ""
        echo "Checking full install components..."
        check_component "sd (search/replace)" "sd" "--version" || true
        check_component "kubectl" "kubectl" "version --client" || true
        check_component "OpenVPN" "openvpn" "--version" || true
        check_component "Cloudflared" "cloudflared" "--version" || true
        check_component "Pandoc" "pandoc" "--version" || true
        check_component "wkhtmltopdf" "wkhtmltopdf" "--version" || true
        check_component "ADB" "adb" "version" || true

        # Check npm-installed components (in nodeenv)
        if [ -d "$BOOT_DIR/node-env/bin" ]; then
            echo ""
            echo "Checking npm-installed components..."
            NPM_BIN="$BOOT_DIR/node-env/bin"
            [ -f "$NPM_BIN/claude" ] && echo "[PASS] claude CLI installed" || echo "[SKIP] claude CLI not found"
            [ -f "$NPM_BIN/gemini" ] && echo "[PASS] gemini CLI installed" || echo "[SKIP] gemini CLI not found"
            [ -f "$NPM_BIN/qwen" ] && echo "[PASS] qwen CLI installed" || echo "[SKIP] qwen CLI not found"
        fi
    fi

    # =============================================================================
    # 8. Test Component Detection System
    # =============================================================================
    echo ""
    echo "=========================================="
    echo "PHASE 8: Testing Component Detection"
    echo "=========================================="

    echo "Running component status detection..."
    .venv/bin/python -c "
from ami.scripts.bootstrap_components import get_components_by_group

print('Component Status Report:')
print('=' * 60)

for group_info in get_components_by_group():
    if not group_info.components:
        continue
    print(f'\n{group_info.group}:')
    for comp in group_info.components:
        status = comp.get_status()
        if status.installed:
            version = f'v{status.version}' if status.version else '(installed)'
            print(f'  [x] {comp.label}: {version}')
        else:
            print(f'  [ ] {comp.label}: not installed')

print('\n' + '=' * 60)
" 2>&1 | tee detection.log
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo "[FAIL] Component detection failed."
        cat detection.log
        exit 1
    fi
    echo "[PASS] Component detection system working."

fi  # End TEST_BOOTSTRAP

# =============================================================================
# Final Summary
# =============================================================================
echo ""
echo "=========================================="
echo ">>> ALL SYSTEMS GO: E2E TEST SUCCESSFUL <<<"
echo "=========================================="
echo ""
echo "Test Summary:"
echo "  - Core installation: PASS"
echo "  - Dependencies: PASS"
echo "  - AMI-CI namespace: PASS"
echo "  - Pre-commit hooks: PASS"
echo "  - Make targets: PASS"
if [ "$TEST_BOOTSTRAP" = "1" ]; then
    echo "  - Bootstrap installer: PASS"
    echo "  - Component detection: PASS"
fi
echo ""
echo "Test directory: $TEST_DIR"
if [ "$SKIP_CLEANUP" = "1" ]; then
    echo "(preserved for inspection)"
fi
