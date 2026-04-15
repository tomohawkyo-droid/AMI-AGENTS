#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Playwright browsers into .boot-linux/playwright-browsers/
# Downloads chromium and chrome binaries. Does NOT install system deps (no sudo).
# System deps must be installed separately via 'sudo make pre-req'.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BROWSERS_DIR="${BOOT_DIR}/playwright-browsers"
PLAYWRIGHT="${PROJECT_ROOT}/.venv/bin/playwright"

log_info()    { echo "  $1" >&2; }
log_warn()    { echo "  ⚠ $1" >&2; }
log_error()   { echo "  ERROR: $1" >&2; }
log_success() { echo "  ✓ $1" >&2; }

# Check playwright is installed
if [[ ! -x "$PLAYWRIGHT" ]]; then
    log_error "playwright not found at $PLAYWRIGHT"
    log_error "Run 'uv sync' first to install Python dependencies."
    exit 1
fi

# Set browsers path — no ~/.cache, everything in .boot-linux
export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"

# Check if already installed
if compgen -G "$BROWSERS_DIR/chromium-"* > /dev/null 2>&1; then
    EXISTING=$("$PLAYWRIGHT" --version 2>/dev/null || echo "unknown")
    log_info "Playwright browsers already installed ($EXISTING)"
    log_info "  Path: $BROWSERS_DIR"
    exit 0
fi

# Check for key system dependencies BEFORE downloading
MISSING_LIBS=()
for lib in libnss3 libgbm1 libatk-bridge2.0-0; do
    if ! dpkg -s "${lib}" &>/dev/null 2>&1; then
        MISSING_LIBS+=("$lib")
    fi
done

if [[ ${#MISSING_LIBS[@]} -gt 0 ]]; then
    log_warn "Missing system libraries for Playwright: ${MISSING_LIBS[*]}"
    log_warn "Browsers will be downloaded but may not work until you run:"
    log_warn "  sudo make pre-req"
    echo "" >&2
fi

# Download browsers (no --with-deps — never trigger sudo)
log_info "Downloading Playwright browsers to $BROWSERS_DIR..."
mkdir -p "$BROWSERS_DIR"

if "$PLAYWRIGHT" install chromium chrome 2>&1; then
    log_success "Playwright browsers downloaded"
else
    log_error "Playwright browser download failed"
    exit 1
fi

# Verify chromium is operational (only if system deps are present)
if [[ ${#MISSING_LIBS[@]} -eq 0 ]]; then
    log_info "Verifying chromium..."
    VERIFY_IMG="/tmp/playwright-verify-$$.png"
    if timeout 30 "$PLAYWRIGHT" screenshot --browser chromium "data:text/html,<h1>AMI</h1>" "$VERIFY_IMG" 2>/dev/null; then
        rm -f "$VERIFY_IMG"
        log_success "Chromium operational"
    else
        rm -f "$VERIFY_IMG"
        log_warn "Chromium verification failed — browser may need system deps"
        log_warn "Run: sudo make pre-req"
    fi
else
    log_warn "Skipping browser verification — system deps missing"
    log_warn "Run: sudo make pre-req"
fi

log_success "Playwright bootstrap complete"
log_info "  Browsers: $BROWSERS_DIR"
log_info "  Installed: chromium, chrome"
