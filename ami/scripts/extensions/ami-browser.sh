#!/usr/bin/env bash
# @name: ami-browser
# @description: Browser automation (Playwright)
# @category: enterprise
# @binary: .venv/bin/playwright
# @features: open, codegen, screenshot, pdf, install
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-browser() { \"$AMI_ROOT/.venv/bin/playwright\" \"\$@\"; }"
