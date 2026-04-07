# Specification: Playwright Integration

**Date:** 2026-02-01
**Status:** DRAFT
**Type:** Specification

> **Implementation status (2026-04-05):** The basic Playwright integration works — `ami-browser` extension is registered, three browser scripts exist (`dom-query.js`, `screenshot.js`, `console.js`), and `playwright` binary is bootstrapped. However, the security layer described in this spec (YAML policy engine, user confirmation for sensitive ops, domain allowlist/blocklist via env vars, audit trail logging) is **not implemented**. Browser scripts execute directly with no validation layer.

## Overview

This document specifies the integration of Playwright browser automation capabilities within the AMI-Orchestrator framework. The integration provides secure, auditable browser automation capabilities while maintaining the security and compliance standards of the AMI ecosystem.

## Architecture

### Core Components

1. **ami-browser** - Main entry point for Playwright commands
   - Located at `.boot-linux/bin/ami-browser`
   - Wrapper for the Playwright CLI
   - Implements security guards and audit logging

2. **Browser Scripts** - Specialized Node.js scripts for specific browser tasks
   - `dom-query.js` - DOM querying and evaluation
   - `screenshot.js` - Screenshot capture
   - `console.js` - Console/network error logging

3. **Security Layer** - Command validation and user confirmation
   - YAML-based policy engine
   - Command guard patterns
   - Sensitive file protection

## Security Protocols

### Command Validation
- All browser commands must pass through the policy engine
- URL patterns must match allowed domains (configurable in YAML)
- Network requests are logged and audited

### User Confirmation
- Interactive confirmation required for all browser operations
- Explicit user consent for navigation to external sites
- Timeout mechanisms to prevent hanging operations

### Audit Trail
- All browser activities logged in transcript system
- Session IDs associated with browser operations
- Compliance with NIST AI CSF/RMF, ISO 42001/27001, and EU AI Act

## Available Commands

### Basic Navigation
```bash
ami-browser open [options] [url]     # Open page in browser
ami-browser cr [url]                 # Open in Chromium
ami-browser ff [url]                 # Open in Firefox
ami-browser wk [url]                 # Open in WebKit
```

### Automation Tools
```bash
ami-browser codegen [options] [url]  # Generate code for user actions
ami-browser screenshot [url] [file]  # Capture page screenshot
ami-browser pdf [url] [file]         # Save page as PDF
```

### Installation
```bash
ami-browser install [browser...]     # Install required browsers
ami-browser install-deps [browser...] # Install OS dependencies
ami-browser uninstall                # Remove browsers
```

## Browser Scripts API

### DOM Query Tool
```bash
node dom-query.js <url> <expression> [--timeout <ms>] [--wait <ms>]
```
- Evaluates JavaScript expressions against page DOM
- Returns JSON-formatted results
- Configurable timeouts and wait periods

### Screenshot Tool
```bash
node screenshot.js <url> <output.png> [--timeout <ms>] [--wait <ms>] [--width <px>] [--height <px>]
```
- Captures full-page screenshots
- Configurable viewport dimensions
- Adjustable wait times for dynamic content

### Console Logger
```bash
node console.js <url> [--timeout <ms>] [--wait <ms>] [--no-network]
```
- Captures console output, errors, and network issues
- Optional network request logging
- Configurable timeouts

## Configuration

### Security Policies
Located in `ami/config/policies/`:
- `default.yaml` - General command patterns
- `browser_patterns.yaml` - Browser-specific restrictions
- `sensitive_files.yaml` - Protected file patterns

### Environment Variables
- `AMI_BROWSER_TIMEOUT` - Default timeout for browser operations
- `AMI_BROWSER_ALLOWED_DOMAINS` - Comma-separated list of allowed domains
- `AMI_BROWSER_BLOCKED_DOMAINS` - Comma-separated list of blocked domains

## Compliance Standards

### NIST AI CSF/RMF
- All browser automation activities logged
- Access controls for sensitive operations
- Risk assessment for external site access

### ISO 42001/27001
- Data protection during browser sessions
- Secure handling of cookies and session data
- Regular security assessments of browser components

### EU AI Act
- Transparency in automated browser operations
- Human oversight for sensitive operations
- Audit trails for decision-making processes

## Best Practices

### For Developers
1. Always validate URLs before passing to browser automation
2. Implement proper error handling for network failures
3. Use appropriate timeouts to prevent hanging operations
4. Log all browser activities for audit purposes

### For Operations
1. Regularly update Playwright and browser binaries
2. Monitor browser automation logs for anomalies
3. Maintain current domain whitelists/blacklists
4. Conduct periodic security reviews of browser scripts

## Limitations and Known Issues

1. **Sandbox Restrictions**: Some advanced browser features may be disabled due to security sandboxing
2. **Resource Limits**: Browser operations subject to system resource constraints
3. **Network Isolation**: External network access may be restricted in certain environments
4. **Authentication**: Complex authentication flows may require manual intervention

## Future Enhancements

1. **Enhanced Security**: Additional isolation mechanisms for sensitive operations
2. **Performance Monitoring**: Built-in performance metrics for browser operations
3. **Integration API**: Programmatic interface for embedding browser automation in workflows
4. **Custom Extensions**: Support for custom browser extensions in automated contexts

## References

- [Playwright Documentation](https://playwright.dev/docs/intro)
- [AMI Security Guidelines](SECURITY_GUIDELINES.md)
- [Compliance Framework](COMPLIANCE_FRAMEWORK.md)
- [Extension System](EXTENSION_SYSTEM.md)