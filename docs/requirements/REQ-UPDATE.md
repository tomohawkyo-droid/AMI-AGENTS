# Requirements: Auto-Update System

**Date:** 2026-04-16
**Status:** ACTIVE
**Type:** Requirements
**Spec:** [SPEC-UPDATE](../specifications/SPEC-UPDATE.md)

---

## Background

Updating the AMI workspace requires pulling each project, checking for conflicts, reinstalling hooks, and re-syncing dependencies. Several repos have more than one remote (e.g., `origin` and `hf`) and each remote can be in a different state; the user needs a way to decide per remote, not just per repo. With 10+ repos across two dependency tiers, this is error-prone and slow. An automated update system should handle the full sequence safely.

---

## Core Requirements

### 1. Dependency Tiers

- **REQ-UPD-001**: Projects shall be split into two update tiers:
  - **SYSTEM** — AMI-CI, AMI-DATAOPS, AMI-AGENTS (infrastructure, updated first).
  - **APPS** — AMI-PORTAL, AMI-TRADING, AMI-STREAMS, AMI-BROWSER, ZK-PORTAL, RUST-TRADING subprojects, and everything else (updated after SYSTEM).
- **REQ-UPD-002**: SYSTEM tier shall always be updated before APPS tier (APPS depend on SYSTEM).
- **REQ-UPD-003**: Within SYSTEM, update order shall be `AMI-CI → AMI-DATAOPS → AMI-AGENTS` — CI first because hooks depend on it, DATAOPS second because services depend on CI, AGENTS last because it depends on both.
- **REQ-UPD-004**: Within APPS, there is no required order; APPS are independent and may be pulled in any order (or in parallel).

### 2. Pre-Update Safety Checks

- **REQ-UPD-010**: Before updating any repo, check if it has uncommitted changes (dirty working tree).
- **REQ-UPD-011**: If any repo in the current tier is dirty, abort the update for that tier and tell the user to commit first.
- **REQ-UPD-012**: Report ALL dirty repos at once (not one at a time).
- **REQ-UPD-013**: Skip repos that don't exist locally (missing submodules are not errors).
- **REQ-UPD-014**: Exclude vendored third-party repos and monorepo subdirectories whose remote points to the parent repo. The exclusion list is tool-managed (changes require a code change, not a runtime config file).

### 3. Remote Fetch & Merge Analysis

- **REQ-UPD-020**: Fetch all configured remotes for every repo in the tier.
- **REQ-UPD-021**: Each (repo, remote, current-branch) triple shall be analyzed **independently**. A repo with two remotes produces two triples; each gets its own merge-path verdict and is offered to the user separately.
- **REQ-UPD-022**: A triple is **fast-forward eligible** iff the local `HEAD` is an ancestor of the remote ref `<remote>/<current-branch>`. Non-eligible triples are labelled "diverged" and are never auto-merged.
- **REQ-UPD-023**: A triple whose remote ref does not exist (e.g., remote has no matching branch) shall be omitted silently.
- **REQ-UPD-024**: A triple shall be omitted with a single-line reason when:
  - the repo is on a detached `HEAD`;
  - the repo has no remotes configured;
  - the `git fetch` call fails (e.g., offline, auth error).
- **REQ-UPD-025**: "Commits behind" shall mean the count of commits reachable from the remote ref but not from local `HEAD` (i.e., `HEAD..<remote>/<branch>`).
- **REQ-UPD-026**: Report the full per-triple status before asking the user to proceed.

### 4. Interactive Remote Selection

- **REQ-UPD-030**: Present a multiselect dialog with **one item per analyzed triple** — not one per repo. A repo with multiple fast-forwardable remotes appears on multiple lines.
- **REQ-UPD-031**: Each item shall show: repo name, remote name, current branch, commits behind, and merge status (FF-eligible or diverged).
- **REQ-UPD-032**: Diverged triples shall be shown in the dialog but rendered as **disabled** (visible, not toggleable). FF-eligible triples shall be **pre-selected by default**; the user may deselect them.
- **REQ-UPD-033**: Reuse the existing TUI multiselect component (from bootstrap installer) with keyboard shortcuts:
  - **Space** — toggle selection
  - **a** — select all (FF-eligible only)
  - **n** — deselect all
  - **Enter** — confirm and proceed
  - **Esc** — cancel
- **REQ-UPD-034**: Cancelling the dialog (Esc) shall exit 0 and make no changes.

### 5. Update Execution

- **REQ-UPD-040**: For each selected triple, perform `git pull --ff-only <remote> <branch>`.
- **REQ-UPD-041**: After pulling SYSTEM tier triples, automatically re-sync Python dependencies and reinstall git hooks (see §7).
- **REQ-UPD-042**: Report success or failure for each **triple** (not per repo) after update.
- **REQ-UPD-043**: If any triple fails to pull, continue with the remaining triples (don't abort the batch).

### 6. Non-Interactive Mode (CI)

- **REQ-UPD-050**: `make update-ci` shall perform a fully non-interactive update using a YAML defaults file (same pattern as `make install-ci` with `install-defaults.yaml`).
- **REQ-UPD-051**: The defaults file shall specify: **one** remote name to pull from (CI mode is single-remote), the tiers to update, and failure behavior (`fail_on_diverge`, `fail_on_dirty`).
- **REQ-UPD-052**: CI mode shall only proceed if ALL selected triples are fast-forward eligible; otherwise it shall exit non-zero when `fail_on_diverge` is true.
- **REQ-UPD-053**: CI mode shall abort with non-zero exit code if any repo is dirty and `fail_on_dirty` is true.

### 7. Post-Update Actions

- **REQ-UPD-060**: After SYSTEM tier update, regenerate native git hooks in **every SYSTEM repo** (AMI-CI, AMI-DATAOPS, AMI-AGENTS) from each repo's own `.pre-commit-config.yaml`, so that commits made inside any SYSTEM repo use the freshly pulled hook definitions.
- **REQ-UPD-061**: After SYSTEM tier update, re-sync Python dependencies (`uv sync --extra dev`) and reinstall AMI-DATAOPS as an editable package when present.
- **REQ-UPD-062**: After any tier update, report a summary identifying each triple's outcome: pulled (with commit count), skipped (already up to date), or failed (with failure reason).

### 8. CLI Entry Point

- **REQ-UPD-070**: An `ami-update` command shall be available as a shell extension.
- **REQ-UPD-071**: `ami-update` shall always run from AMI-AGENTS root regardless of the user's current working directory.
- **REQ-UPD-072**: `ami-update --defaults FILE` shall invoke non-interactive mode from a YAML config.
- **REQ-UPD-073**: `ami-update` shall be registered in the extension manifest.
- **REQ-UPD-074**: `make update` shall invoke interactive mode.
- **REQ-UPD-075**: `make update-ci` shall invoke CI mode using a YAML defaults file (same pattern as `install-defaults.yaml`).
- **REQ-UPD-076**: `ami-update --ci` shall invoke non-interactive CI mode; when `--defaults FILE` is also supplied, `FILE` is used, otherwise a repository-provided default defaults file is used.

### 9. Exit Codes

- **REQ-UPD-080**: Exit **0** when: all selected pulls succeed, nothing needed updating, or the user cancelled the dialog.
- **REQ-UPD-081**: Exit **non-zero** when: any pull fails; or in CI mode, any repo is dirty with `fail_on_dirty` true; or in CI mode, any triple is diverged with `fail_on_diverge` true; or the configured defaults file is missing.

---

## Constraints

- Python 3.11+ (update script).
- Reuse existing TUI multiselect component.
- Only fast-forward merges — never rebase or merge with conflicts automatically.
- Git operations use the bootstrapped git with git-guard.
- Must work offline — fetch failure for a given triple is non-fatal; the triple is reported and skipped.

## Non-Requirements

- **Auto-commit dirty repos** — user must commit manually.
- **Conflict resolution** — diverged triples are reported, not fixed.
- **Branch switching** — update always pulls the current branch.
- **Remote management** — does not add/remove remotes.
- **Submodule update** — `git submodule update` is not run; submodules listed as vendored are excluded outright.
- **Parallel pulls** — APPS may be pulled in any order, but this spec does not require parallelism.
