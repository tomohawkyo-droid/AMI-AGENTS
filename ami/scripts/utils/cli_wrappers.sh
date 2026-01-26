#!/usr/bin/env bash
# CLI tool wrappers for AMI Orchestrator

# Tool wrappers that ensure consistent environment usage
# These maintain backward compatibility while forwarding to the unified ami-run command

# AI agent CLI wrappers that ensure version control and prevent unwanted auto-updates
# These use version-controlled binaries from the project's .venv/node_modules directory

ami-claude() {
    # Claude Code AI assistant CLI wrapper
    # Uses version-controlled binary to ensure consistent behavior across environments
    # Prevents auto-updates that could affect agent behavior in development
    "$AMI_ROOT/.venv/node_modules/.bin/claude" "$@"
}

ami-gemini() {
    # Gemini CLI AI assistant wrapper
    # Uses version-controlled binary to ensure consistent behavior across environments
    # Handles authentication setup and version management automatically
    "$AMI_ROOT/.venv/node_modules/.bin/gemini" "$@"
}

ami-qwen() {
    # Qwen Code AI assistant CLI wrapper
    # Uses version-controlled binary to ensure consistent behavior across environments
    # Part of the multi-agent integration in the AMI Orchestrator system
    "$AMI_ROOT/.venv/node_modules/.bin/qwen" "$@"
}

ami-browser() {
    # Playwright browser automation CLI wrapper
    # Provides browser automation, screenshots, PDF generation, and web scraping
    "$AMI_ROOT/.venv/bin/playwright" "$@"
}
