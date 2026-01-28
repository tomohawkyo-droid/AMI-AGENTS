#!/usr/bin/env bash
# @name: ami-transcripts
# @description: Transcript session management and search
# @category: core
# @binary: ami/scripts/bin/ami_transcripts.py
# @features: transcript-search, session-resume, session-replay
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
echo "ami-transcripts() { python3 \"$AMI_ROOT/ami/scripts/bin/ami_transcripts.py\" \"\$@\"; }"
