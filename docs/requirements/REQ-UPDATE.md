# Requirements: Auto-Update System

**Date:** 2026-04-16
**Status:** ACTIVE
**Type:** Requirements
**Spec:** [SPEC-UPDATE](../specifications/SPEC-UPDATE.md)

---

## Background

Updating the AMI workspace requires manually pulling each project, checking for conflicts, reinstalling hooks, and re-syncing dependencies. With 10+ repos across two dependency tiers, this is error-prone and slow. An automated update system should handle the full sequence safely.

---

## Core Requirements

### 1. Dependency Tiers

- **REQ-UPD-001**: Projects shall be split into two update tiers:
  - **SYSTEM** — AMI-AGENTS, AMI-CI, AMI-DATAOPS (infrastructure dependencies, updated first)
  - **APPS** — AMI-PORTAL, AMI-TRADING, AMI-STREAMS, AMI-BROWSER, ZK-PORTAL, RUST-TRADING, and everything else (updated after SYSTEM)
- **REQ-UPD-002**: SYSTEM tier shall always be updated before APPS tier (APPS depend on SYSTEM)
- **REQ-UPD-003**: Within each tier, update order shall respect dependency chains (e.g., AMI-CI before AMI-AGENTS, since AGENTS depends on CI hooks)

### 2. Pre-Update Safety Checks

- **REQ-UPD-010**: Before updating any repo, check if it has uncommitted changes (dirty working tree)
- **REQ-UPD-011**: If any repo in the current tier is dirty, abort the update for that tier and tell the user to commit first
- **REQ-UPD-012**: Report ALL dirty repos at once (not one at a time)
- **REQ-UPD-013**: Skip repos that don't exist locally (missing submodules are not errors)
- **REQ-UPD-014**: Exclude vendored third-party repos and monorepo subdirectories whose remote points to the parent repo

### 3. Remote Fetch & Merge Analysis

- **REQ-UPD-020**: Fetch all remotes for every repo in the tier
- **REQ-UPD-021**: For each repo, report which remotes have new commits and whether they can be cleanly fast-forward merged
- **REQ-UPD-022**: If a remote cannot be cleanly merged (diverged history), report it as "needs manual resolution" — do not attempt merge
- **REQ-UPD-023**: Report status for all repos before asking the user to proceed

### 4. Interactive Remote Selection

- **REQ-UPD-030**: Present the user with a multiselect dialog listing all repos with available updates
- **REQ-UPD-031**: Each item shows: repo name, current branch, remote name, commits behind, merge status (clean/conflict)
- **REQ-UPD-032**: Only repos with clean fast-forward paths shall be selectable
- **REQ-UPD-033**: Reuse the existing TUI multiselect component (from bootstrap installer) with keyboard shortcuts:
  - **Space** — toggle selection
  - **a** — select all
  - **n** — deselect all
  - **Enter** — confirm and proceed
  - **Esc** — cancel

### 5. Update Execution

- **REQ-UPD-040**: For each selected repo, perform `git pull --ff-only` from the selected remote
- **REQ-UPD-041**: After pulling SYSTEM tier repos, automatically re-sync Python dependencies and reinstall git hooks
- **REQ-UPD-042**: Report success/failure for each repo after update
- **REQ-UPD-043**: If any repo fails to pull, continue with remaining repos (don't abort the batch)

### 6. Non-Interactive Mode (CI)

- **REQ-UPD-050**: `make update-ci` shall perform a fully non-interactive update using a YAML defaults file (same pattern as `make install-ci` with `install-defaults.yaml`)
- **REQ-UPD-051**: The defaults file shall specify: remote to pull from, tiers to update, and failure behavior
- **REQ-UPD-052**: Non-interactive mode only proceeds if ALL repos have clean fast-forward paths — otherwise fails with non-zero exit code
- **REQ-UPD-053**: Non-interactive mode aborts if any repo is dirty

### 7. Post-Update Actions

- **REQ-UPD-060**: After SYSTEM tier update, reinstall git hooks (`make install-hooks`)
- **REQ-UPD-061**: After SYSTEM tier update, re-sync Python dependencies (`uv sync`)
- **REQ-UPD-062**: After any tier update, report a summary of what changed (repos updated, commits pulled, any failures)

### 8. CLI Entry Point

- **REQ-UPD-070**: An `ami-update` command shall be available as a shell extension
- **REQ-UPD-071**: `ami-update` shall always run from AMI-AGENTS root regardless of the user's current working directory
- **REQ-UPD-072**: `ami-update --defaults FILE` shall invoke non-interactive mode from YAML config
- **REQ-UPD-073**: `ami-update` shall be registered in the extension manifest
- **REQ-UPD-074**: `make update` shall invoke interactive mode
- **REQ-UPD-075**: `make update-ci` shall invoke CI mode using a YAML defaults file (same pattern as `install-defaults.yaml`)
- **REQ-UPD-076**: `ami-update --ci` shall invoke non-interactive CI mode; when `--defaults FILE` is also supplied, `FILE` is used, otherwise a repository-provided default defaults file is used

---

## Constraints

- Python 3.11+ (update script)
- Reuse existing TUI multiselect component
- Only fast-forward merges — never rebase or merge with conflicts automatically
- Git operations use the bootstrapped git with git-guard
- Must work offline (fetch failure is non-fatal, just reports "offline")

## Non-Requirements

- **Auto-commit dirty repos** — user must commit manually
- **Conflict resolution** — diverged repos are reported, not fixed
- **Branch switching** — update always pulls the current branch
- **Remote management** — does not add/remove remotes
