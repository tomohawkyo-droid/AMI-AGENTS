# Playwright Integration Summary

**Date:** 2026-02-01
**Status:** DRAFT
**Type:** Specification

> **Implementation status (2026-04-05):** The security features described below (policy engine, user confirmation, audit trail) are not yet implemented. See [SPEC-PLAYWRIGHT.md](SPEC-PLAYWRIGHT.md) for details.

## Overview
The AMI-Orchestrator project includes a Playwright integration for browser automation. Three scripts are operational (`dom-query.js`, `screenshot.js`, `console.js`) via the `ami-browser` extension. The security and audit layers described in the full spec remain planned work.

## Key Features
- **Secure Browser Automation**: All browser operations go through security validation
- **Multiple Browser Support**: Chromium, Firefox, and WebKit
- **Specialized Scripts**: DOM querying, screenshot capture, and console logging
- **Audit Trail**: All browser activities are logged for compliance
- **Policy Engine**: YAML-based rules for controlling browser access

## Integration Points
- `ami-browser` command provides access to Playwright CLI
- Browser scripts in `ami/scripts/browser/` for specialized tasks
- Security guards integrated with the policy engine
- Audit logging connected to the transcript system

## Security Measures
- Command validation against allowed patterns
- User confirmation for sensitive operations
- Domain-based access controls
- Network activity logging

## Compliance
- NIST AI CSF/RMF compliant
- ISO 42001/27001 compliant  
- EU AI Act compliant

## Usage Examples
```
# Open a webpage
ami-browser open https://example.com

# Take a screenshot
ami-browser screenshot https://example.com /tmp/screenshot.png

# Generate automation code
ami-browser codegen https://example.com

# Query DOM elements
node ami/scripts/browser/dom-query.js https://example.com "document.title"
```

## Documentation
For detailed specifications, see [SPEC-PLAYWRIGHT.md](SPEC-PLAYWRIGHT.md).