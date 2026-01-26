#!/usr/bin/env bash
# @name: ami-mail
# @description: Enterprise mail operations CLI
# @category: enterprise
# @binary: ami/scripts/bin/ami_mail.py
# @features: send, send-block, fetch
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-mail() { \"$AMI_ROOT/ami/scripts/bin/ami-run\" \"$AMI_ROOT/ami/scripts/bin/ami_mail.py\" \"\$@\"; }"
