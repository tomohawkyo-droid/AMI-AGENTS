# Specification: Auto-Update System

**Date:** 2026-04-16
**Status:** ACTIVE
**Type:** Specification
**Requirements:** [REQ-UPDATE](../requirements/REQ-UPDATE.md)

This specification describes **behaviour**, not code. For the implementation,
see `ami/scripts/update.py`, `ami/scripts/bin/ami-update`, and
`ami/config/update-defaults.yaml`.

---

## 1. Dependency Tiers

### SYSTEM (updated first)

| Repo | Path | Why SYSTEM |
|------|------|-----------|
| AMI-CI | `projects/AMI-CI` | Hooks and CI checks — all other repos depend on these |
| AMI-DATAOPS | `projects/AMI-DATAOPS` | Infrastructure services (Keycloak, OpenBao, compose stack) |
| AMI-AGENTS | `.` (root) | Workspace root, bootstrap, extensions, core agent |

**Update order within SYSTEM**: `AMI-CI → AMI-DATAOPS → AMI-AGENTS`. CI first because hooks depend on it; DATAOPS second because infra depends on CI; AGENTS last because it depends on both.

### APPS (updated after SYSTEM)

| Repo | Path |
|------|------|
| AMI-PORTAL | `projects/AMI-PORTAL` |
| AMI-TRADING | `projects/AMI-TRADING` |
| AMI-STREAMS | `projects/AMI-STREAMS` |
| AMI-BROWSER | `projects/AMI-BROWSER` |
| ZK-PORTAL | `projects/ZK-PORTAL` |
| rust-ta | `projects/RUST-TRADING/rust-ta` |
| rust-zk-compliance-api | `projects/RUST-TRADING/rust-zk-compliance-api` |
| rust-zk-protocol | `projects/RUST-TRADING/rust-zk-protocol` |
| rust-zk-provider | `projects/RUST-TRADING/rust-zk-provider` |

APPS have no internal ordering — all are independent.

### Excluded (not managed by update)

| Repo | Path | Reason |
|------|------|--------|
| python-ta-reference | `projects/RUST-TRADING/python-ta-reference` | Vendored third-party (bukosabino/ta) |
| matrix-docker-ansible-deploy | `projects/AMI-STREAMS/ansible/...` | Vendored third-party submodule |
| himalaya | `projects/AMI-STREAMS/himalaya` | Vendored submodule |
| config, docs, scripts, SUCK | `projects/RUST-TRADING/*` | Monorepo dirs (remote points to AMI-AGENTS parent) |
| polymarket-insider-tracker | `projects/polymarket-insider-tracker` | Standalone project |
| AMI-SRP + research submodules | `projects/AMI-SRP/research/...` | Third-party research repos (Bloomberg, Palantir) |
| AMI-FOLD | `projects/AMI-FOLD` | Inactive project |
| CV | `projects/CV` | Inactive project |
| docs | `projects/docs` | Documentation submodule |
| res | `projects/res` | Shared resources |

The exclusion list is maintained as constants in `ami/scripts/update.py`. Runtime config files do not override it.

---

## 2. Update Pipeline

```
┌─────────────────┐
│ 1. Discover      │  Find every repo under root + projects/ (git-status-all style);
│                  │  drop excluded and vendored entries.
├─────────────────┤
│ 2. Dirty Check   │  Run `git status --porcelain` per repo; collect all dirty repos,
│                  │  fail the tier if any dirty and the tier requires clean state.
├─────────────────┤
│ 3. Fetch         │  `git fetch --all` per clean repo.
│                  │  On failure: record reason, omit repo from selection set.
├─────────────────┤
│ 4. Merge Check   │  For each (repo, remote, current-branch) triple whose remote ref
│                  │  exists and is strictly ahead of HEAD:
│                  │    - count commits behind (HEAD..<remote>/<branch>)
│                  │    - mark FF-eligible iff HEAD is ancestor of <remote>/<branch>
├─────────────────┤
│ 5. Report        │  Status table: one row per triple; FF-eligible / diverged label.
├─────────────────┤
│ 6. Select        │  Interactive multiselect (FF-eligible preselected; diverged
│                  │  shown disabled) — or auto-select in CI mode.
├─────────────────┤
│ 7. Pull          │  `git pull --ff-only <remote> <branch>` per selected triple;
│                  │  continue on failure.
├─────────────────┤
│ 8. Post-SYSTEM   │  After the SYSTEM tier: `uv sync --extra dev`, reinstall
│                  │  AMI-DATAOPS as editable if present, regenerate native git hooks
│                  │  in every SYSTEM repo from each repo's own .pre-commit-config.yaml.
│                  │  Then proceed to APPS tier.
└─────────────────┘
```

---

## 3. Key Modules

The implementation lives in `ami/scripts/update.py`. This section lists the
responsibilities of each logical unit; it is not a code listing.

### 3.1 Discovery

- Walk `root` + `projects/**` looking for `.git` directories and `.git` files (the latter indicates a submodule).
- Prune descent into `.git`, `node_modules`, `__pycache__`, `.venv`.
- Skip entries in the excluded list and anything ending in an excluded-submodule name.
- Sort results by path for stable output.

### 3.2 Dirty check

- For each repo, run `git status --porcelain` with a short timeout.
- A non-empty output makes the repo dirty.
- Report all dirty repos together; do not stop at the first one.

### 3.3 Fetch & analyse

- For each repo: run `git fetch --all --quiet`.
- Determine current branch via `git branch --show-current`; on detached HEAD, omit the repo with a reason line.
- Determine remotes via `git remote`; on empty, omit with a reason line.
- For each remote, form `<remote>/<current-branch>`; skip if the ref does not exist.
- Count `HEAD..<remote>/<branch>`; zero means already up to date → omit.
- Check fast-forward eligibility via `git merge-base --is-ancestor HEAD <remote>/<branch>`.
- The result of analysis is a flat list of **triples** `(repo, remote, branch, commits_behind, can_ff)`.

### 3.4 Status report

Rendered once after analysis, before any prompt, and one section per tier:

```
SYSTEM Tier -- Update Status
────────────────────────────────────────────────────
  AMI-CI          origin/main    ↓3     clean ff
  AMI-DATAOPS     origin/main    ↓1     clean ff
  AMI-AGENTS      already up to date
  AMI-AGENTS      hf/main        ↓2     diverged

APPS Tier -- Update Status
────────────────────────────────────────────────────
  AMI-PORTAL      origin/main    ↓5     clean ff
  AMI-TRADING     already up to date
  AMI-TRADING     hf/main        ↓1     clean ff
  AMI-STREAMS     already up to date
  rust-zk-proto   origin/main    ↓3     clean ff
  rust-zk-proto   hf/main        ↓3     clean ff
  ZK-PORTAL       origin/main    ↓2     clean ff
```

A repo with multiple remotes appears once per remote. A repo that is already up to date on every remote appears once with "already up to date".

### 3.5 Interactive selection

- Use `ami.cli_components.dialogs.multiselect` with `MenuItem` instances.
- One item per triple. Label = repo name. Description = `<remote>/<branch>  ↓N` (with a diverged suffix when applicable).
- FF-eligible items are pre-selected; diverged items are `disabled` (visible, not toggleable).
- Keyboard shortcuts are inherited from `SelectionDialog`: **Space**, **a**, **n**, **Enter**, **Esc**.
- **Esc** returns no selection and causes exit code 0 (no-op).

### 3.6 Pull execution

- For each selected triple, run `git pull --ff-only <remote> <branch>` with a per-call timeout.
- Success is determined by `git`'s exit code.
- Record `stdout + stderr` for reporting.
- A failure on one triple does not stop the batch.

### 3.7 Post-SYSTEM update

Run after the SYSTEM tier has at least one successful pull:

1. `uv sync --extra dev` at root.
2. If `projects/AMI-DATAOPS/pyproject.toml` exists: `uv pip install -e projects/AMI-DATAOPS`.
3. For **each SYSTEM repo** (AMI-CI, AMI-DATAOPS, AMI-AGENTS): run `projects/AMI-CI/scripts/generate-hooks` with that repo's directory as the working directory, so each repo regenerates its own `.git/hooks/*` from its own `.pre-commit-config.yaml`.

### 3.8 Non-interactive (CI) mode

Triggered by `--defaults FILE` or `--ci` (which selects the repo-provided default file):

- Load the YAML. Default keys: `remote: origin`, `tiers: [system]`, `fail_on_diverge: true`, `fail_on_dirty: true`.
- Run discovery, dirty check, fetch, analyse — but **filter every triple to the configured remote only**.
- If any repo is dirty and `fail_on_dirty` is true → exit 1.
- If any triple is diverged and `fail_on_diverge` is true → exit 1.
- Pull every FF-eligible triple; continue on per-triple failure.
- Run post-SYSTEM update if the SYSTEM tier had at least one success.
- Print summary.
- Exit 0 iff every attempted pull succeeded.

### 3.9 Scope flags

The CLI exposes a mutually-exclusive scope group; if both `--projects` and `--all` are passed, argparse rejects the invocation. The selected scope plumbs through both interactive and CI paths.

| Invocation | Scope |
|------------|-------|
| `ami-update` (no flag) | SYSTEM only (AMI-CI, AMI-DATAOPS, AMI-AGENTS) |
| `ami-update --projects` | APPS only (everything in `projects/*` minus the SYSTEM trio) |
| `ami-update --all` | SYSTEM + APPS |

When `--ci` / `--defaults` is also set, an explicit scope flag overrides the YAML's `tiers:` list. With no scope flag, the YAML `tiers:` value wins.

---

## 4. Makefile Targets

```makefile
update:     @bash ami/scripts/bin/ami-update
update-ci:  @bash ami/scripts/bin/ami-update --ci --defaults ami/config/update-defaults.yaml
```

`update` is interactive. `update-ci` is non-interactive using the repo-provided defaults.

### CI defaults YAML (`ami/config/update-defaults.yaml`)

```yaml
remote: origin          # Only pull from this remote
tiers:                  # Which tiers to update (default: SYSTEM only)
  - system
fail_on_diverge: true   # Exit non-zero if any repo has diverged history
fail_on_dirty: true     # Exit non-zero if any repo is dirty
```

CLI flags `--projects` / `--all` override the `tiers:` value above.

---

## 5. Summary Output

After update completes:

```
Update Summary
────────────────────────────────────────────────────
SYSTEM:
  ✓ AMI-CI          origin/main    3 commits pulled
  ✓ AMI-DATAOPS     origin/main    1 commit pulled
  · AMI-AGENTS      already up to date
  ⚠ AMI-AGENTS      hf/main        skipped (diverged)

  → Hooks reinstalled, deps synced

APPS:
  ✓ AMI-PORTAL      origin/main    5 commits pulled
  ✓ ZK-PORTAL       origin/main    2 commits pulled
  · AMI-TRADING     already up to date
  · AMI-STREAMS     already up to date
```

Marker glyphs:
- `✓` pulled successfully
- `✗` pull attempted and failed
- `·` already up to date
- `⚠` skipped (diverged or fetch failure)

---

## 6. CLI Entry Point

### `ami/scripts/bin/ami-update`

A thin bash wrapper that:

1. Resolves the AMI root via `ami-pwd`.
2. `cd`s to root.
3. `exec`s the Python update script with all arguments forwarded.

Registered in `ami/scripts/bin/extension.manifest.yaml` as a core extension.

Usage:

```
ami-update                                      # interactive, SYSTEM only (default scope)
ami-update --projects                           # interactive, APPS only
ami-update --all                                # interactive, SYSTEM + APPS
ami-update --ci                                 # CI mode, repo default YAML (SYSTEM only)
ami-update --ci --all                           # CI mode, both tiers (CLI overrides YAML)
ami-update --ci --defaults path/to/config.yaml  # CI mode, custom YAML
ami-update --defaults path/to/config.yaml       # equivalent to --ci --defaults ...
```

`--projects` and `--all` are mutually exclusive.

---

## 7. File Map

| File | Purpose |
|------|---------|
| `ami/scripts/bin/ami-update` | Shell entry point (resolves AMI_ROOT, delegates to `update.py`) |
| `ami/scripts/update.py` | Main update logic |
| `ami/config/update-defaults.yaml` | CI defaults |
| `Makefile` | `update` and `update-ci` targets |
| `ami/scripts/bin/extension.manifest.yaml` | ami-update registered as core extension |
| `ami/cli_components/menu_selector.py` | REUSE: `MenuItem` |
| `ami/cli_components/dialogs.py` | REUSE: `multiselect()` facade |

---

## 8. Edge Cases

| Case | Behaviour |
|------|-----------|
| Repo doesn't exist (missing submodule) | Skipped silently by discovery |
| Fetch fails (offline / auth error) | Triple omitted; one-line reason in status |
| No remotes configured | Repo omitted; one-line reason |
| Detached HEAD | Repo omitted; one-line reason |
| Remote ref doesn't exist for current branch | Triple omitted silently |
| All triples already up to date | Print "Everything up to date", exit 0 |
| CI mode + diverged triple + `fail_on_diverge` | Exit 1 |
| CI mode + dirty repo + `fail_on_dirty` | Exit 1 |
| User cancels multiselect (Esc) | Exit 0, no changes |
| Pull fails for one triple | Reported in summary, remaining triples continue |
| CI defaults file missing | Exit 1 with error |
