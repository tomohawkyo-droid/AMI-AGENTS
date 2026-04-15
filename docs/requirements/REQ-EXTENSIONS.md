# Requirements: Extension Registry

**Date:** 2026-04-14
**Updated:** 2026-04-14
**Status:** ACTIVE
**Type:** Requirements
**Spec:** [SPEC-EXTENSIONS](../specifications/SPEC-EXTENSIONS.md)

---

## Background

The current extension system uses a single centralized `extensions.yaml` file listing all 33 CLI tools. This doesn't scale — adding a new extension requires editing a shared config file, there's no dependency tracking, and tools in external submodules (AMI-STREAMS, AMI-DATAOPS) have no way to self-register.

---

## Core Requirements

### 1. Decentralized Manifests

- **REQ-EXT-001**: Each component shall declare its extensions via an `extension.manifest.yaml` file alongside its code
- **REQ-EXT-002**: A manifest may declare one or more extensions
- **REQ-EXT-003**: The centralized `extensions.yaml` and `extensions.template.yaml` shall be removed and replaced by manifest discovery
- **REQ-EXT-004**: Manifests shall be validated against a schema — missing required fields or unknown fields shall be reported as errors and the entry skipped
- **REQ-EXT-005**: Malformed YAML in a manifest shall be reported and the manifest skipped — not crash the process

### 2. Discovery

- **REQ-EXT-010**: The system shall recursively discover all `extension.manifest.yaml` files from the project root
- **REQ-EXT-011**: Discovery shall only find manifests in directories that exist (missing submodules are silently skipped, not errors)
- **REQ-EXT-012**: Discovery shall exclude build artifacts, caches, VCS directories, and dot-prefixed directories
- **REQ-EXT-013**: Discovery shall happen at runtime (banner load, registration) — no pre-cached merged file
- **REQ-EXT-014**: Discovery order shall be deterministic (sorted paths)

### 3. Dependencies

- **REQ-EXT-020**: The extension's `binary` field is its implicit hard dependency — if the binary doesn't exist, the extension is unavailable. No need to declare it separately in `deps`.
- **REQ-EXT-021**: Extensions may declare additional dependencies (other binaries, submodules, containers, system packages, files)
- **REQ-EXT-022**: Each additional dependency shall be either required (hard) or optional (soft)
- **REQ-EXT-023**: If any required dependency is missing, the extension shall be silently skipped
- **REQ-EXT-024**: If an optional dependency is missing, the extension shall register but report degraded status
- **REQ-EXT-025**: Extensions with no `deps` declared and a valid `binary` shall register unconditionally
- **REQ-EXT-026**: Duplicate extension names across manifests shall be reported as an error and the later entry skipped
- **REQ-EXT-027**: Container-backed extensions shall check container status via deps (type: container), not via special-cased binary logic

### 4. Health & Version Checks

- **REQ-EXT-030**: Each extension manifest may declare a single check block combining health and version detection in one command
- **REQ-EXT-031**: Health check matches output against an expected substring
- **REQ-EXT-032**: Version detection extracts a version string via regex pattern
- **REQ-EXT-033**: Check timeout shall be max 5 seconds, configurable per-extension
- **REQ-EXT-034**: Failed health checks shall not prevent registration — status is reported as degraded
- **REQ-EXT-035**: Check commands shall not use shell execution — arguments are split and executed directly

### 5. Banner Display

- **REQ-EXT-040**: Each extension shall declare a `bannerPriority` (integer) controlling display order within its category
- **REQ-EXT-041**: Lower priority values display first
- **REQ-EXT-042**: The current banner display order shall be preserved via default priority assignments
- **REQ-EXT-043**: Extensions with `hidden: true` shall not appear in the default banner
- **REQ-EXT-044**: A new `ami-extra` command shall list all hidden, degraded, and unavailable extensions with their status and reasons
- **REQ-EXT-045**: Banner display shall be driven by a single Python process — bash only renders the output, no YAML parsing in bash
- **REQ-EXT-046**: During banner load, each extension being checked shall display a countdown timer (e.g., `00:05`) in place until the check completes, then replaced with the result
- **REQ-EXT-047**: Each extension may declare an `installHint` string shown when unavailable, telling the user how to install it

### 6. Categories

- **REQ-EXT-050**: Categories shall be declared per-extension in the manifest (not a fixed set)
- **REQ-EXT-051**: The current categories (core, enterprise, dev, infra, docs, agents) shall remain as defaults with predefined display properties
- **REQ-EXT-052**: New categories introduced by manifests shall use sensible default display properties (generic color, no icon)
- **REQ-EXT-053**: Category display order: known categories first (in defined order), then unknown categories alphabetically
- **REQ-EXT-054**: Category display properties (color, icon, title) may be overridden by manifests

### 7. Registration

- **REQ-EXT-060**: Registration shall create symlinks or wrappers in `.boot-linux/bin/` for all resolved extensions
- **REQ-EXT-061**: Python script extensions (binary ending in `.py`) shall get wrapper scripts that invoke `ami-run`
- **REQ-EXT-062**: Registration shall be idempotent
- **REQ-EXT-063**: Container runtime detection shall check for podman first, fall back to docker

---

## Constraints

- Python 3.11+ (registration, discovery, banner helper)
- Bash (banner rendering only — no YAML parsing)
- YAML manifest format (PyYAML)
- No external dependency management (no auto-install, no SAT solver)
- Discovery + resolution must complete in under 1 second for banner load
- No `shell=True` in subprocess calls for check commands
- Max check timeout: 5 seconds per extension

## Non-Requirements

- **Auto-installation of missing dependencies** — discovery reports what's missing, doesn't install it
- **Version constraint solving** — no semver ranges, no conflict resolution
- **Remote manifest fetching** — manifests are local files only
- **Circular dependency detection** — not needed (deps are external tools, not extensions depending on each other)
