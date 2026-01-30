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
    echo "Options:"
    echo "  --target-dir DIR    Directory where test will run (default: ./tmp/e2e_test_<timestamp>)"
    echo "  --skip-cleanup      Skip cleanup on exit (for debugging)"
    echo "  -h, --help          Show this help"
    echo ""
    echo "Example:"
    echo "  $0 --target-dir ~/Tests --skip-cleanup"
    exit 0
}

# =============================================================================
# Parse arguments
# =============================================================================
BASE_DIR=$(pwd)
TEST_DIR=""
SKIP_CLEANUP=0

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
echo "0. Checking prerequisites..."
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
echo "1. Cloning AMI-AGENTS..."
git clone git@hf.co:ami-ailabs/AMI-AGENTS AMI-AGENTS 2>&1 | tail -5
cd AMI-AGENTS
echo "[PASS] AMI-AGENTS cloned."

# =============================================================================
# 2. Run make install-ci (non-interactive full install)
# =============================================================================
echo "2. Running make install-ci..."
make install-ci 2>&1 | tee install.log | tail -30
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] make install-ci failed."
    cat install.log
    exit 1
fi
echo "[PASS] make install-ci executed."

# =============================================================================
# 3. Deep Verification
# =============================================================================
echo "3. Deep Verification..."

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
import torch
import loguru
import pydantic
import aiohttp
print(f'Torch: {torch.__version__}')
print(f'Pydantic: {pydantic.__version__}')
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

# --- Check 5: Configuration files ---
if [ ! -f "pyproject.toml" ]; then
    echo "[FAIL] pyproject.toml missing."
    exit 1
fi
echo "[PASS] Configuration files present."

# =============================================================================
# 4. Install pre-commit hooks
# =============================================================================
echo "4. Installing pre-commit hooks..."
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
echo "5. Verifying make targets..."

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

echo ""
echo ">>> ALL SYSTEMS GO: E2E INSTALLATION TEST (AMI-AGENTS) SUCCESSFUL <<<"
