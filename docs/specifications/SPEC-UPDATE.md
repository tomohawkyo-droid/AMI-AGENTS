# Specification: Auto-Update System

**Date:** 2026-04-16
**Status:** ACTIVE
**Type:** Specification
**Requirements:** [REQ-UPDATE](../requirements/REQ-UPDATE.md)

---

## Implementation Status (2026-04-16)

NOT BUILT. Current `make update` only runs `uv update` (Python deps). Current `ensure-ci`/`ensure-dataops` do `git pull --ff-only` but with no safety checks, no user interaction, and no multi-repo coordination.

---

## 1. Dependency Tiers

### SYSTEM (updated first)

| Repo | Path | Why SYSTEM |
|------|------|-----------|
| AMI-CI | `projects/AMI-CI` | Hooks and CI checks — all other repos depend on these |
| AMI-DATAOPS | `projects/AMI-DATAOPS` | Infrastructure services (Keycloak, OpenBao, compose stack) |
| AMI-AGENTS | `.` (root) | Workspace root, bootstrap, extensions, core agent |

**Update order within SYSTEM**: AMI-CI → AMI-DATAOPS → AMI-AGENTS (CI first because hooks depend on it, AGENTS last because it depends on both)

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

APPS tier has no internal ordering — all are independent.

### Excluded (not managed by update)

| Repo | Path | Reason |
|------|------|--------|
| python-ta-reference | `projects/RUST-TRADING/python-ta-reference` | Vendored third-party (bukosabino/ta) |
| matrix-docker-ansible-deploy | `projects/AMI-STREAMS/ansible/...` | Vendored third-party submodule |
| himalaya | `projects/AMI-STREAMS/himalaya` | Submodule of AMI-STREAMS (updated with STREAMS) |
| config, docs, scripts, SUCK | `projects/RUST-TRADING/*` | Monorepo dirs (remote points to AMI-AGENTS parent) |
| polymarket-insider-tracker | `projects/polymarket-insider-tracker` | Standalone project |
| AMI-SRP + research submodules | `projects/AMI-SRP/research/...` | Third-party research repos (Bloomberg, Palantir) |
| AMI-FOLD | `projects/AMI-FOLD` | Inactive project |
| CV | `projects/CV` | Inactive project |
| docs | `projects/docs` | Documentation submodule |
| res | `projects/res` | Shared resources |

---

## 2. Update Pipeline

```
┌─────────────────┐
│ 1. Discover      │  Find all repos (reuse git-status-all discovery)
├─────────────────┤
│ 2. Dirty Check   │  Check each repo for uncommitted changes
│                  │  If dirty → abort tier, list all dirty repos
├─────────────────┤
│ 3. Fetch         │  git fetch --all for each clean repo
│                  │  Collect ahead/behind per remote
├─────────────────┤
│ 4. Merge Check   │  For each remote with new commits:
│                  │    Can HEAD..remote be fast-forwarded?
│                  │    git merge-base --is-ancestor HEAD remote/branch
├─────────────────┤
│ 5. Report        │  Show status table (repo, remote, commits, mergeable)
├─────────────────┤
│ 6. Select        │  Interactive multiselect (or auto-select in CI mode)
├─────────────────┤
│ 7. Pull          │  git pull --ff-only for selected repos
├─────────────────┤
│ 8. Post-Update   │  SYSTEM: make sync (hooks + deps)
│                  │  Report summary
└─────────────────┘
```

---

## 3. Implementation

### Entry Point: `ami/scripts/update.py`

Same pattern as `bootstrap_installer.py` — `--defaults` flag for CI mode:

```python
def _main_impl() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-update AMI repos (SYSTEM then APPS)"
    )
    parser.add_argument(
        "--defaults",
        type=Path,
        metavar="FILE",
        help="Non-interactive mode using YAML config file",
    )
    args = parser.parse_args()

    root = find_ami_root()
    repos = discover_repos(root)
    system_repos = categorize(repos, tier='system')
    app_repos = categorize(repos, tier='apps')

    # Non-interactive (CI) mode
    if args.defaults:
        return _run_from_defaults(args.defaults, system_repos, app_repos, root)

    # Interactive mode — TUI multiselect
    return _run_interactive(system_repos, app_repos, root)
```

### Repo Discovery

Reuse the same discovery as `git-status-all`, but filter out vendored/monorepo repos:

```python
# Repos where the remote points to a third-party or to the parent monorepo.
# These are not part of the AMI update chain.
EXCLUDED_REPOS = {
    'projects/RUST-TRADING/python-ta-reference',        # vendored third-party
    'projects/RUST-TRADING/config',                      # monorepo dir (remote = AMI-AGENTS)
    'projects/RUST-TRADING/docs',                        # monorepo dir
    'projects/RUST-TRADING/scripts',                     # monorepo dir
    'projects/RUST-TRADING/SUCK',                        # monorepo dir
    'projects/polymarket-insider-tracker',                # standalone, not in update chain
}

# Submodules that are vendored third-party code
EXCLUDED_SUBMODULES = {
    'ansible/matrix-docker-ansible-deploy',              # vendored Ansible playbook
}

def discover_repos(root: Path) -> list[RepoInfo]:
    repos = [RepoInfo(path=root, name='AMI-AGENTS')]
    projects_dir = root / 'projects'

    # Walk projects/ looking for .git dirs or files (submodules use .git files)
    for dirpath, dirnames, filenames in os.walk(projects_dir):
        # Prune: don't descend into .git dirs, node_modules, etc.
        dirnames[:] = [
            d for d in dirnames
            if d not in {'.git', 'node_modules', '__pycache__', '.venv'}
        ]
        path = Path(dirpath)
        # Check for .git dir or .git file (submodule)
        if (path / '.git').exists():
            rel = str(path.relative_to(root))
            if rel in EXCLUDED_REPOS:
                continue
            if any(rel.endswith(exc) for exc in EXCLUDED_SUBMODULES):
                continue
            repos.append(RepoInfo(path=path, name=rel))
            # Don't descend into this repo's subdirectories
            dirnames.clear()

    return sorted(repos, key=lambda r: r.name)
```

### Dirty Check

```python
def check_dirty(repos: list[RepoInfo]) -> list[RepoInfo]:
    dirty = []
    for repo in repos:
        result = subprocess.run(
            ['git', '-C', str(repo.path), 'status', '--porcelain'],
            capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip():
            dirty.append(repo)
    return dirty
```

If dirty repos found:
```
ERROR: Cannot update — the following repos have uncommitted changes:

  projects/AMI-CI          ~2 ?1
  projects/AMI-TRADING     ~1

Commit or stash your changes, then retry.
```

### Fetch & Merge Analysis

```python
class RemoteUpdate(NamedTuple):
    repo: RepoInfo
    remote: str          # e.g., "origin"
    branch: str          # e.g., "main"
    commits_behind: int
    can_ff: bool         # True if fast-forward possible

def analyze_repo(repo: RepoInfo) -> list[RemoteUpdate]:
    # Fetch all remotes
    subprocess.run(['git', '-C', str(repo.path), 'fetch', '--all', '--quiet'],
                   capture_output=True, timeout=30)

    branch = get_current_branch(repo)
    updates = []

    for remote in get_remotes(repo):
        remote_ref = f'{remote}/{branch}'
        if not ref_exists(repo, remote_ref):
            continue

        behind = count_behind(repo, f'HEAD..{remote_ref}')
        if behind == 0:
            continue

        # Check if fast-forward is possible:
        # HEAD must be an ancestor of remote_ref
        can_ff = is_ancestor(repo, 'HEAD', remote_ref)

        updates.append(RemoteUpdate(
            repo=repo, remote=remote, branch=branch,
            commits_behind=behind, can_ff=can_ff,
        ))

    return updates


def is_ancestor(repo: RepoInfo, a: str, b: str) -> bool:
    result = subprocess.run(
        ['git', '-C', str(repo.path), 'merge-base', '--is-ancestor', a, b],
        capture_output=True, timeout=10,
    )
    return result.returncode == 0
```

### Status Report

```
SYSTEM Tier — Update Status
────────────────────────────────────────────────────
  AMI-CI          origin/main    ↓3     ✓ clean ff
  AMI-DATAOPS     origin/main    ↓1     ✓ clean ff
  AMI-AGENTS      origin/main    synced
  AMI-AGENTS      hf/main        ↓2     ✗ diverged

APPS Tier — Update Status
────────────────────────────────────────────────────
  AMI-PORTAL      origin/main    ↓5     ✓ clean ff
  AMI-TRADING     origin/main    synced
  AMI-TRADING     hf/main        ↓1     ✓ clean ff
  AMI-STREAMS     origin/main    synced
  himalaya        origin/ami     synced
  rust-zk-proto   origin/main    ↓3     ✓ clean ff
  rust-zk-proto   hf/main        ↓3     ✓ clean ff
  ZK-PORTAL       origin/main    ↓2     ✓ clean ff
```

Multi-remote repos (AMI-AGENTS has `origin` + `hf`, AMI-TRADING has `origin` + `hf`, rust-zk-protocol has `origin` + `hf`) show one line per remote. The user selects which remotes to pull from.

### Interactive Selection

Reuse `dialogs.multiselect()` from `ami/cli_components/dialogs.py` with `MenuItem` from `ami/cli_components/menu_selector.py`:

```python
from ami.cli_components.dialogs import multiselect
from ami.cli_components.menu_selector import MenuItem

def select_updates(updates: list[RemoteUpdate]) -> list[RemoteUpdate]:
    items = []
    selectable_ids = set()
    for u in updates:
        item_id = f'{u.repo.name}:{u.remote}'
        items.append(MenuItem(
            id=item_id,
            label=u.repo.name,
            value=u,
            description=f'{u.remote}/{u.branch}  ↓{u.commits_behind}'
                        + ('' if u.can_ff else '  ✗ diverged'),
            disabled=not u.can_ff,
        ))
        if u.can_ff:
            selectable_ids.add(item_id)

    selected = multiselect(
        items=items,
        title='Select repos to update',
        preselected=selectable_ids,  # Pre-select all mergeable
    )

    return [item.value for item in selected]
```

`MenuItem` implements the `SelectableItem` protocol accepted by `DialogItem`. The `disabled` field greys out diverged repos (not selectable). `preselected` is a `set[str]` of item IDs.

Keyboard shortcuts inherited from `SelectionDialog`:
- **Space** — toggle
- **a** — select all
- **n** — deselect all
- **Enter** — confirm
- **Esc** — cancel

Diverged repos shown as disabled (greyed out, not selectable).

### Pull Execution

```python
def pull_updates(updates: list[RemoteUpdate]) -> list[PullResult]:
    results = []
    for u in updates:
        result = subprocess.run(
            ['git', '-C', str(u.repo.path), 'pull', '--ff-only',
             u.remote, u.branch],
            capture_output=True, text=True, timeout=60,
        )
        results.append(PullResult(
            repo=u.repo, remote=u.remote,
            success=result.returncode == 0,
            output=result.stdout + result.stderr,
        ))
    return results
```

### Post-SYSTEM Update

After SYSTEM tier repos are pulled, run dependency sync and hook reinstall directly — NOT `make sync` (which calls `ensure-ci`/`ensure-dataops` and would re-pull repos we already updated):

```python
def run_post_system_update(root: Path):
    boot_uv = root / '.boot-linux' / 'bin' / 'uv'
    ci_hooks = root / 'projects' / 'AMI-CI' / 'scripts' / 'generate-hooks'

    # Re-sync Python deps (picks up any changes in pyproject.toml)
    print("Syncing Python dependencies...")
    subprocess.run([str(boot_uv), 'sync', '--extra', 'dev'], cwd=str(root), check=False)

    # Reinstall AMI-DATAOPS editable if present
    dataops = root / 'projects' / 'AMI-DATAOPS' / 'pyproject.toml'
    if dataops.exists():
        subprocess.run([str(boot_uv), 'pip', 'install', '-e', 'projects/AMI-DATAOPS'],
                       cwd=str(root), check=False)

    # Regenerate git hooks from latest AMI-CI
    if ci_hooks.exists():
        print("Reinstalling git hooks...")
        subprocess.run(['bash', str(ci_hooks)], cwd=str(root), check=False)
```

### Non-Interactive Mode (`--defaults`)

Same pattern as `bootstrap_installer.py --defaults`:

```python
def _run_from_defaults(defaults_file, system_repos, app_repos, root) -> int:
    config = yaml.safe_load(defaults_file.read_text())
    remote = config.get('remote', 'origin')
    fail_on_diverge = config.get('fail_on_diverge', True)
    fail_on_dirty = config.get('fail_on_dirty', True)
    tiers = config.get('tiers', ['system', 'apps'])

    all_repos = []
    if 'system' in tiers:
        all_repos.extend(system_repos)
    if 'apps' in tiers:
        all_repos.extend(app_repos)

    # Dirty check
    dirty = check_dirty(all_repos)
    if dirty and fail_on_dirty:
        print_dirty_error(dirty)
        return 1

    # Fetch + analyze — selected remote only
    updates = []
    for repo in all_repos:
        repo_updates = analyze_repo(repo)
        updates.extend(u for u in repo_updates if u.remote == remote)

    # Diverge check
    non_ff = [u for u in updates if not u.can_ff]
    if non_ff and fail_on_diverge:
        print_diverge_error(non_ff)
        return 1

    # Pull all clean ff
    mergeable = [u for u in updates if u.can_ff]
    results = pull_updates(mergeable)

    # Post-system update
    if 'system' in tiers and any(r.success for r in results):
        run_post_system_update(root)

    print_summary(results)
    return 0 if all(r.success for r in results) else 1
```

---

## 4. Makefile Targets

```makefile
.PHONY: update
update: ## Interactive update of all repos (SYSTEM then APPS)
	@bash ami/scripts/bin/ami-update

.PHONY: update-ci
update-ci: ## Non-interactive update (uses update-defaults.yaml)
	@bash ami/scripts/bin/ami-update --ci --defaults ami/config/update-defaults.yaml
```

### CI Defaults YAML (`ami/config/update-defaults.yaml`)

Same pattern as `install-defaults.yaml` for bootstrap:

```yaml
# Non-interactive update configuration.
# Used by: make update-ci

remote: origin          # Only pull from this remote
tiers:
  - system              # Update SYSTEM tier
  - apps                # Update APPS tier
fail_on_diverge: true   # Exit 1 if any repo has diverged history
fail_on_dirty: true     # Exit 1 if any repo has uncommitted changes
```

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

---

## 6. CLI Entry Point

### `ami/scripts/bin/ami-update`

```bash
#!/usr/bin/env bash
# ami-update: Auto-update all AMI repos (always runs from AGENTS root)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
AMI_ROOT="$("$SCRIPT_DIR/ami-pwd")"

cd "$AMI_ROOT"
exec "$AMI_ROOT/.venv/bin/python" "$AMI_ROOT/ami/scripts/update.py" "$@"
```

Registered in `ami/scripts/bin/extension.manifest.yaml` as a core extension.

Usage:
```bash
ami-update              # Interactive: TUI multiselect
ami-update --ci         # CI mode: origin only, ff-only, fails on diverge
ami-update --ci --defaults path/to/config.yaml  # CI with custom config
```

---

## 7. File Map

| File | Purpose |
|------|---------|
| `ami/scripts/bin/ami-update` | Shell entry point (resolves AMI_ROOT, delegates to update.py) |
| `ami/scripts/update.py` | Main update logic (discover, check, fetch, analyze, select, pull) |
| `ami/config/update-defaults.yaml` | CI mode defaults (repos to update, origin-only) |
| `Makefile` | `update` (interactive) and `update-ci` (YAML defaults) targets |
| `ami/scripts/bin/extension.manifest.yaml` | ami-update registered as core extension |
| `ami/cli_components/menu_selector.py` | REUSE: `MenuItem` class |
| `ami/cli_components/dialogs.py` | REUSE: `multiselect()` facade |

---

## 8. Edge Cases

| Case | Behavior |
|------|----------|
| Repo doesn't exist (missing submodule) | Skipped silently |
| Fetch fails (offline / auth error) | Reported as "fetch failed", repo skipped |
| No remotes configured | Reported as "no remotes", repo skipped |
| Detached HEAD | Reported as "detached HEAD", repo skipped |
| All repos up to date | Print "Everything up to date" and exit 0 |
| CI mode + diverged repo | Exit 1 with error message |
| CI mode + dirty repo | Exit 1 with error message |
| User cancels multiselect (Esc) | Exit 0, no changes made |
| Pull fails mid-batch | Report failure, continue with remaining repos |
