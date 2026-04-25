# Specification: Extension Registry

**Date:** 2026-04-14
**Status:** ACTIVE
**Type:** Specification
**Requirements:** [REQ-EXTENSIONS](../requirements/REQ-EXTENSIONS.md)

---

## Implementation Status (2026-04-14)

BUILT. This spec replaced the previous centralized `extensions.yaml` system; discovery is now via per-component `extension.manifest.yaml` files (see § 4 Discovery Algorithm).

---

## 1. Manifest Format

### `extension.manifest.yaml`

```yaml
extensions:
  - name: ami-mail                          # REQUIRED. Unique across all manifests.
    binary: .boot-linux/bin/himalaya        # REQUIRED. Path relative to AMI_ROOT.
                                            # Existence is the implicit hard dep.
    description: Enterprise mail CLI        # REQUIRED. Human-readable, ≥5 chars.
    category: enterprise                    # REQUIRED. Any string.
    features:                               # Optional. YAML list of feature strings.
      - send
      - send-block
      - batch
    bannerPriority: 100                     # Optional. Default: 500. Lower = first.
    hidden: false                           # Optional. Default: false.
    container: null                         # Optional. Container name.
    installHint: "make build-himalaya"      # Optional. Shown when UNAVAILABLE.

    check:                                  # Optional. Combined health + version.
      command: ["{binary}", "--version"]    # REQUIRED in check. List of args (no shell).
                                            # {binary} → resolved absolute path.
                                            # {python} → AMI_ROOT/.venv/bin/python
                                            # (fallback .boot-linux/python-env/bin/python).
                                            # Use {python} {binary} when binary is a .py.
      versionPattern: "v(\\d+\\.\\d+\\.\\d+)"  # Optional. Regex capture group.
      healthExpect: "himalaya"              # Optional. Substring match.
      timeout: 5                            # Optional. Default: 5. Max: 5.

    deps:                                   # Optional. ADDITIONAL deps only.
      - name: himalaya-source               # REQUIRED in dep. Human-readable.
        type: submodule                     # REQUIRED. binary|submodule|container|system-package|file
        path: projects/AMI-STREAMS/himalaya # For binary/submodule/file types.
        required: false                     # Optional. Default: true.

      - name: ami-keycloak                  # Container dep example:
        type: container                     #   checks podman/docker for named container.
        container: ami-keycloak             #   'container' field (not 'path').
        required: false

# Optional: category display properties.
categories:
  my-custom-cat:
    title: My Custom Category
    icon: "🔹"
    color: green
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique command name |
| `binary` | string | Path to executable, relative to AMI_ROOT |
| `description` | string (≥5 chars) | Human-readable description |
| `category` | string | Category name |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `features` | list[string] | `[]` | Feature list (joined with `", "` for banner display) |
| `bannerPriority` | integer | `500` | Display order (lower = first) |
| `hidden` | boolean | `false` | Hide from default banner |
| `container` | string | `null` | Container name for container-backed commands |
| `installHint` | string | `null` | How to install (shown when UNAVAILABLE) |
| `check` | object | `null` | Health + version check |
| `deps` | list | `[]` | Additional dependencies |

### Schema Validation

Every entry is validated. Invalid entries are logged to stderr and **skipped** (not crash):

```python
REQUIRED_FIELDS = {'name', 'binary', 'description', 'category'}
KNOWN_FIELDS = REQUIRED_FIELDS | {
    'features', 'bannerPriority', 'hidden', 'container',
    'installHint', 'check', 'deps',
}

def validate_entry(entry: dict, manifest_path: Path) -> list[str]:
    errors = []
    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        errors.append(f"{manifest_path}: missing required fields: {missing}")
    unknown = set(entry.keys()) - KNOWN_FIELDS
    if unknown:
        errors.append(f"{manifest_path}: unknown fields: {unknown}")
    desc = entry.get('description', '')
    if desc and len(desc) < 5:
        errors.append(f"{manifest_path}: description too short: {desc!r}")
    timeout = entry.get('check', {}).get('timeout', 5)
    if timeout > 5:
        errors.append(f"{manifest_path}: check timeout {timeout}s exceeds max of 5s")
    return errors
```

---

### 1.1 File-mode rule

Tracked `.py` files in this repo must not have the exec bit set. `.py` modules are invoked through the universal `ami-run` wrapper (which resolves `$AMI_ROOT/.venv/bin/python`), or through the manifest `check:` command using the `{python}` substitution. An executable `.py` relies on `/usr/bin/env python3` at the top of the file, which resolves to **system Python** and bypasses the project's pinned dependencies.

Enforced by the `ci_check_py_not_executable` pre-commit hook in AMI-CI.

---

## 2. Dependency Types

| Type | Check | Field |
|------|-------|-------|
| `binary` | File exists and is executable at `AMI_ROOT/{path}` | `path` |
| `submodule` | Directory exists and is non-empty at `AMI_ROOT/{path}` | `path` |
| `container` | Container runtime finds the named container | `container` |
| `system-package` | `shutil.which(name)` succeeds | Uses dep `name` |
| `file` | File exists at `AMI_ROOT/{path}` | `path` |

Container runtime detection (cached per process):

```python
_container_runtime: str | None = None

def get_container_runtime() -> str | None:
    global _container_runtime
    if _container_runtime is None:
        if shutil.which('podman'):
            _container_runtime = 'podman'
        elif shutil.which('docker'):
            _container_runtime = 'docker'
        else:
            _container_runtime = ''
    return _container_runtime or None


def check_container(name: str) -> bool:
    runtime = get_container_runtime()
    if not runtime:
        return False
    try:
        result = subprocess.run(
            [runtime, 'ps', '-a', '--filter', f'name={name}', '--format', '{{.Names}}'],
            capture_output=True, text=True, timeout=5,
        )
        return name in result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False
```

---

## 3. Extension Status Model

| Status | Meaning | Banner | `ami extras` | `ami doctor` |
|--------|---------|--------|--------------|--------------|
| `READY` | Binary exists, all required deps present, health passes | Shown (name + desc + version) | — | — |
| `DEGRADED` | Binary exists, optional dep missing OR health fails | Shown with ⚠ indicator | — | Listed with reason |
| `VERSION_MISMATCH` | Binary exists but violates minVersion/maxVersion | Not shown (downgraded in doctor) | — | Listed with reason |
| `UNAVAILABLE` | Binary missing OR required dep missing | Not shown | — | Listed with reason + installHint |
| `HIDDEN` | Explicitly `hidden: true`, deps satisfied | Not shown | Listed | — |

---

## 4. Discovery Algorithm

```python
EXCLUDE_DIRS = {'.git', 'node_modules', 'target', '.venv', '.boot-linux',
                '__pycache__', '.mypy_cache', '.ruff_cache', 'build', 'dist'}

def discover_manifests(root: Path) -> list[Path]:
    manifests = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs AND all dot-prefixed dirs
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDE_DIRS and not d.startswith('.')
        ]
        if 'extension.manifest.yaml' in filenames:
            manifests.append(Path(dirpath) / 'extension.manifest.yaml')
    return sorted(manifests)
```

---

## 5. Resolution Algorithm

```python
def resolve_extensions(manifests: list[Path], root: Path) -> list[ResolvedExtension]:
    seen_names: dict[str, Path] = {}
    resolved = []

    for manifest_path in manifests:
        # Parse YAML — skip malformed manifests
        try:
            data = yaml.safe_load(manifest_path.read_text())
        except yaml.YAMLError as e:
            print(f"ERROR: malformed YAML in {manifest_path}: {e}", file=sys.stderr)
            continue

        if not data or 'extensions' not in data:
            continue

        entries = data.get('extensions', [])

        for entry in entries:
            # Validate schema — skip invalid entries
            errors = validate_entry(entry, manifest_path)
            if errors:
                for e in errors:
                    print(f"ERROR: {e}", file=sys.stderr)
                continue

            name = entry['name']

            # Duplicate check — skip later entry, don't crash
            if name in seen_names:
                print(
                    f"ERROR: duplicate extension '{name}' in {manifest_path} "
                    f"(first seen in {seen_names[name]}), skipping",
                    file=sys.stderr,
                )
                continue
            seen_names[name] = manifest_path

            # Check implicit dep: binary must exist
            binary_path = root / entry['binary']
            if entry['binary'].endswith('.py'):
                binary_exists = binary_path.is_file()
            else:
                binary_exists = binary_path.exists() and os.access(binary_path, os.X_OK)

            if not binary_exists:
                hint = entry.get('installHint', '')
                reason = f"binary not found: {entry['binary']}"
                if hint:
                    reason += f" (install: {hint})"
                resolved.append(ResolvedExtension(
                    entry, manifest_path, Status.UNAVAILABLE, reason=reason))
                continue

            # Check additional deps
            status, reason = check_additional_deps(entry.get('deps', []), root)

            # Hidden override
            if entry.get('hidden', False) and status == Status.READY:
                status = Status.HIDDEN

            resolved.append(ResolvedExtension(
                entry, manifest_path, status, reason=reason))

    return resolved


def check_additional_deps(deps: list[dict], root: Path) -> tuple[Status, str]:
    """Check additional dependencies. Returns (status, reason)."""
    if not deps:
        return Status.READY, ""

    degraded_reasons = []
    for dep in deps:
        present = check_dep(dep, root)
        required = dep.get('required', True)
        if not present and required:
            return Status.UNAVAILABLE, f"missing required dep: {dep['name']}"
        if not present and not required:
            degraded_reasons.append(f"optional dep missing: {dep['name']}")

    if degraded_reasons:
        return Status.DEGRADED, "; ".join(degraded_reasons)
    return Status.READY, ""


def check_dep(dep: dict, root: Path) -> bool:
    dep_type = dep['type']

    if dep_type == 'binary':
        path = root / dep['path']
        return path.exists() and os.access(path, os.X_OK)
    elif dep_type == 'submodule':
        path = root / dep['path']
        return path.is_dir() and any(path.iterdir())
    elif dep_type == 'container':
        return check_container(dep.get('container', dep['name']))
    elif dep_type == 'system-package':
        return shutil.which(dep['name']) is not None
    elif dep_type == 'file':
        return (root / dep['path']).exists()
    return False
```

---

## 6. Check Execution (Health + Version, Single Call)

```python
def run_check(entry: dict, root: Path) -> tuple[bool, str | None]:
    """Run combined health + version check. One subprocess call. Max 5s."""
    check = entry.get('check')
    if not check:
        return True, None

    binary = str(root / entry['binary'])
    cmd = [arg.replace('{binary}', binary) for arg in check['command']]
    timeout = min(check.get('timeout', 5), 5)  # Hard cap at 5s

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, None
    except OSError:
        return False, None

    # Health: substring match
    health_ok = True
    if 'healthExpect' in check:
        health_ok = check['healthExpect'] in output

    # Version: regex extraction
    version = None
    if 'versionPattern' in check:
        match = re.search(check['versionPattern'], output)
        version = match.group(1) if match else None

    return health_ok, version
```

---

## 7. Banner Architecture

### Shared Library: `ami/scripts/shell/extension_registry.py`

Core logic shared between `register_extensions.py` and `banner_helper.py` (which backs both `ami-welcome` and the `ami extras` / `ami doctor` subcommands). Contains:

- `find_ami_root()` — `AMI_ROOT` env var, fallback walk-up for `pyproject.toml`
- `discover_manifests(root)` — recursive discovery
- `validate_entry(entry, path)` — schema validation
- `resolve_extensions(manifests, root)` — full resolution pipeline
- `check_additional_deps(deps, root)` — dep checking
- `run_check(entry, root)` — health + version in one call
- `Status` enum, `ResolvedExtension` dataclass

```python
# ami/scripts/shell/extension_registry.py
def find_ami_root() -> Path:
    env_root = os.environ.get('AMI_ROOT')
    if env_root:
        return Path(env_root)
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / 'pyproject.toml').exists():
            return current
        current = current.parent
    raise RuntimeError("Cannot determine AMI_ROOT")
```

### Banner Helper: `ami/scripts/shell/banner_helper.py`

Imports from `extension_registry.py`. Accepts `--mode banner|extras|doctor` and `--quiet` flags.

```python
from extension_registry import (
    find_ami_root, discover_manifests, resolve_extensions, run_check, Status,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['banner', 'extras', 'doctor'], default='banner')
    parser.add_argument('--quiet', action='store_true',
                        help='Skip health/version checks for faster output')
    args = parser.parse_args()

    # Also respect AMI_QUIET_MODE env var
    quiet = args.quiet or os.environ.get('AMI_QUIET_MODE') == '1'

    root = find_ami_root()
    manifests = discover_manifests(root)
    resolved = resolve_extensions(manifests, root)

    if args.mode == 'banner':
        output_banner(resolved, root, quiet=quiet)
    elif args.mode == 'extras':
        output_extras(resolved, root)
    elif args.mode == 'doctor':
        resolved = enforce_versions(resolved, root)
        output_doctor(resolved, root)
```

### Registration Script: `ami/scripts/register_extensions.py`

Also imports from `extension_registry.py`:

```python
from ami.scripts.shell.extension_registry import (
    find_ami_root, discover_manifests, resolve_extensions, Status,
)

def register_extensions():
    root = find_ami_root()
    manifests = discover_manifests(root)
    resolved = resolve_extensions(manifests, root)

    for ext in resolved:
        if ext.status == Status.UNAVAILABLE:
            continue
        create_symlink_or_wrapper(ext, root)
```

### Banner Output with Countdown Timer (REQ-EXT-046)

The banner displays extensions progressively. For each extension with a `check`, a countdown timer shows in place until the check completes.

**Terminal detection**: Countdown animation only runs when `sys.stdout.isatty()` is True. When piped, checks run without animation and results print directly.

**Quiet mode**: When `--quiet` or `AMI_QUIET_MODE=1`, health/version checks are skipped entirely. Extensions show with `✓` (binary exists) but no version number. Fast banner load.

**Skip redundant checks**: If an extension has a `container` dep that resolved to missing (DEGRADED), the health check is skipped — it would just confirm the same thing by timing out against the unavailable container.

```python
def output_banner(resolved: list[ResolvedExtension], root: Path, quiet: bool = False):
    is_tty = sys.stdout.isatty()
    by_category = group_by_category(resolved)

    for cat_name, extensions in by_category:
        print_category_header(cat_name)

        for ext in extensions:
            if ext.status in (Status.UNAVAILABLE, Status.HIDDEN):
                continue

            has_check = ext.entry.get('check') and not quiet
            has_failed_container_dep = any(
                dep.get('type') == 'container' and not check_dep(dep, root)
                for dep in ext.entry.get('deps', [])
            )

            if has_check and not has_failed_container_dep:
                if is_tty:
                    # Animated countdown
                    health_ok, version = run_check_with_countdown(ext.entry, root)
                else:
                    # Non-TTY: run check, print result directly
                    health_ok, version = run_check(ext.entry, root)

                if not health_ok and ext.status == Status.READY:
                    ext.status = Status.DEGRADED
                ext.version = version
            elif has_failed_container_dep:
                ext.version = None  # Skip check — container is down
            else:
                ext.version = None

            print_extension_line(ext)

        sys.stdout.flush()


def run_check_with_countdown(entry: dict, root: Path) -> tuple[bool, str | None]:
    """Run check in background thread, display countdown on current line."""
    result_holder = [None, None]
    check = entry.get('check', {})
    timeout = min(check.get('timeout', 5), 5)

    def do_check():
        result_holder[0], result_holder[1] = run_check(entry, root)

    thread = threading.Thread(target=do_check, daemon=True)
    thread.start()

    start = time.monotonic()
    while thread.is_alive() and (time.monotonic() - start) < timeout:
        remaining = max(0, timeout - (time.monotonic() - start))
        secs = int(remaining)
        centis = int((remaining - secs) * 100)
        countdown = f"[{secs:02d}:{centis:02d}]"

        sys.stdout.write(f'\r{format_extension_line_partial(entry, countdown)}')
        sys.stdout.flush()
        time.sleep(0.1)

    thread.join(timeout=0.5)

    if result_holder[0] is None:
        return False, None
    return result_holder[0], result_holder[1]
```

### Bash: `ami-banner.sh`

Simplified — calls Python helper which handles all output including ANSI colors and countdown.

```bash
_display_extensions() {
    python3 "$AMI_ROOT/ami/scripts/shell/banner_helper.py" --mode banner
}
```

### `ami extras` and `ami doctor` Subcommands

Two subcommands of the unified `ami` CLI, both dispatching to the same helper with different modes:

```bash
ami extras   # -> banner_helper.py --mode extras
ami doctor   # -> banner_helper.py --mode doctor
```

**`ami extras`** lists only hidden extensions (intentional extras):

```
Hidden Extensions:
  ami-ssh          SSH with AMI keys and config
  ami-vpn          OpenVPN client with AMI config
  ami-tunnel       Cloudflare tunnel management
  ami-ssl          OpenSSL with AMI cert paths
  ami-gcloud       Google Cloud CLI (gcloud SDK)
```

Prints `No hidden extensions.` when the list is empty.

**`ami doctor`** diagnoses problem extensions (degraded, version-mismatched, unavailable). Runs `enforce_versions` so version constraints are surfaced:

```
Degraded Extensions:
  ami-kcadm        Keycloak Admin CLI  DEGRADED (optional dep missing: ami-keycloak container)

Version-Mismatched Extensions:
  ami-claude       Claude Code AI assistant  VERSION_MISMATCH (1.5.0 < required minVersion 2.0.0)

Unavailable Extensions:
  ami-chat         Matrix chat client  UNAVAILABLE (binary not found: .boot-linux/bin/matrix-commander) (install: make bootstrap-communication)
```

Prints `No problems detected.` when everything is healthy.

---

## 8. Default Category Properties

| Category | Title | Icon | Color | Order |
|----------|-------|------|-------|-------|
| core | Core Execution & Management | 🟡 | gold | 1 |
| enterprise | Enterprise Services | 🌐 | cyan | 2 |
| dev | Development Tools | 🌸 | pink | 3 |
| infra | Infrastructure & Networking | 🔧 | purple | 4 |
| docs | Document Production | 📄 | blue | 5 |
| agents | AI Coding Agents (REQUIRE HUMAN SUPERVISION) | 🤖 | red | 6 |

Unknown categories: icon 🔹, color green, appended alphabetically after known categories.

---

## 9. Default Banner Priorities

| Extension | Category | bannerPriority |
|-----------|----------|---------------|
| ami-agent | core | 10 |
| ami | core | 20 |
| ami-run | core | 30 |
| ami-repo | core | 40 |
| ami-transcripts | core | 50 |
| ami-welcome | core | 60 (hidden) |
| ami-pwd | core | 70 (hidden) |
| ami-mail | enterprise | 100 |
| ami-chat | enterprise | 110 |
| ami-synadm | enterprise | 120 |
| ami-kcadm | enterprise | 130 |
| ami-browser | enterprise | 140 |
| ami-backup | dev | 200 |
| ami-restore | dev | 210 |
| ami-gcloud | dev | 220 (hidden) |
| ami-cron | dev | 240 |
| ami-ssh | infra | 300 (hidden) |
| ami-vpn | infra | 310 (hidden) |
| ami-tunnel | infra | 320 (hidden) |
| ami-ssl | infra | 330 (hidden) |
| ami-docs | docs | 400 |
| ami-claude | agents | 500 |
| ami-gemini | agents | 510 |
| ami-qwen | agents | 520 |

---

## 10. Manifest Locations

Manifests live where the component's install chain originates:

| Manifest Path | Extensions | Install Chain |
|---------------|-----------|---------------|
| `ami/scripts/bin/extension.manifest.yaml` | ami-agent, ami, ami-run, ami-repo, ami-transcripts, ami-welcome, ami-pwd | Direct scripts in AMI-AGENTS |
| `projects/AMI-DATAOPS/extension.manifest.yaml` | ami-backup, ami-restore | Python scripts (DATAOPS) |
| `ami/scripts/bin/ami-cron/extension.manifest.yaml` | ami-cron | Python script |
| `ami/scripts/bin/enterprise/extension.manifest.yaml` | ami-kcadm, ami-browser | Wrappers (kcadm=container, browser=pip) |
| `ami/scripts/bin/infra/extension.manifest.yaml` | ami-ssh, ami-vpn, ami-tunnel, ami-ssl | Python scripts (all hidden) |
| `ami/scripts/bin/docs/extension.manifest.yaml` | ami-docs | Wrapper for bootstrapped pandoc |
| `ami/scripts/bootstrap/agents/extension.manifest.yaml` | ami-claude, ami-gemini, ami-qwen | Node.js agents |
| `projects/AMI-STREAMS/extension.manifest.yaml` | ami-mail, ami-chat, ami-synadm | himalaya fork + pip packages |
| `ami/scripts/bootstrap/dev/extension.manifest.yaml` | ami-gcloud (hidden) | Bootstrapped external tools |

---

## 11. Example: ami-kcadm (container-backed)

Container-backed extensions use `deps` with `type: container` — no special binary logic:

```yaml
extensions:
  - name: ami-kcadm
    binary: ami/scripts/bin/ami-kcadm
    description: Keycloak Admin CLI (kcadm.sh)
    category: enterprise
    features:
      - config
      - get
      - create
      - update
      - delete
    bannerPriority: 130
    installHint: "make compose-deploy in AMI-DATAOPS"
    check:
      command: ["{binary}", "--help"]
      healthExpect: "kcadm"
      timeout: 5
    deps:
      - name: ami-keycloak
        type: container
        container: ami-keycloak
        required: false    # Wrapper script works, but container must be up for actual use
```

The wrapper script (`ami/scripts/bin/ami-kcadm`) always exists in the repo, so `binary` check passes. The container dep is `required: false` — extension shows as DEGRADED if container is down, not UNAVAILABLE.

---

## 12. Files Modified

| File | Change |
|------|--------|
| `ami/scripts/shell/extension_registry.py` | NEW: shared library (discover, validate, resolve, check) |
| `ami/scripts/register_extensions.py` | Rewrite: imports from extension_registry, creates symlinks/wrappers |
| `ami/scripts/shell/banner_helper.py` | NEW: imports from extension_registry, --mode banner\|extras\|doctor, --quiet |
| `ami/scripts/shell/ami-banner.sh` | Simplify: call banner_helper.py --mode banner |
| `ami/scripts/bin/ami-run` | Dispatches `ami extras` / `ami doctor` subcommands to banner_helper.py |
| `ami/config/extensions.yaml`, `extensions.template.yaml` | DELETED (no longer present on disk) |
| ~10 `extension.manifest.yaml` files | One per component group, discovered dynamically |
| `tests/unit/test_register_extensions.py` | Rewrite for manifest discovery + validation |
| `tests/integration/test_extensions_help.py` | Rewrite for manifest discovery |

---

## 13. Migration Path

1. Create `banner_helper.py` with discover/resolve/check/countdown pipeline
2. Create all `extension.manifest.yaml` files with current data + bannerPriority + check + deps + installHint
3. Rewrite `register_extensions.py` to use manifest discovery
4. Simplify `ami-banner.sh` to call `banner_helper.py --mode banner`
5. Wire `ami extras` and `ami doctor` subcommands into `ami-run`
6. Delete `extensions.yaml` and `extensions.template.yaml` (done — files no longer exist)
7. Update tests
8. Diff test: verify banner output matches current output (minus countdown animation)
