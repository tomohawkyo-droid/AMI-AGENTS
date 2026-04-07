# Audit: Installation and Bootstrap Issues

**Date:** 2026-03-15
**Status:** ACTIVE
**Type:** Audit
**Verified:** 2026-04-05

Tracks architectural issues in the installation and bootstrap logic. Originally 10 items; 8 fully resolved, 2 partially fixed.

---

## 1. Self-Destructing Code Trap (OpenVPN) — FIXED

**File:** `ami/scripts/bootstrap/bootstrap_openvpn.sh`

Bootstrap script contained a heredoc that overwrote `ami/scripts/bin/run_openvpn_client.py` on every run, silently destroying developer changes.

**Resolution:** Heredoc removed. Script now uses `dpkg-deb -x` for extraction and verifies the Python file exists without overwriting it.

---

## 2. Versioning Split-Brain (Agent CLIs) — FIXED

**Files:** `ami/scripts/bootstrap_component_defs.py`, `scripts/package.json`

Bootstrap installer hardcoded AI agent versions separately from `package.json`.

**Resolution:** `_get_package_version()` dynamically reads `scripts/package.json`. All agent components use this function.

---

## 3. Copy-Paste Debian Extractor — PARTIALLY FIXED

**Files:** `bootstrap_git.sh`, `bootstrap_openvpn.sh`, `bootstrap_wkhtmltopdf.sh`, `bootstrap_sd.sh`, `bootstrap_openssl.sh`

Multiple bootstrap scripts independently re-implement `.deb` extraction logic.

**Current state:** All scripts now use `dpkg-deb -x` (handles all compression formats including `.zst`). Functionally consistent, but no shared utility function exists. `wkhtmltopdf.sh` defines a local `extract_deb()` that other scripts don't reuse.

**Remaining work:** Extract shared `extract_deb()` into `ami/scripts/bootstrap/utils/extract_deb.sh`.

---

## 4. Root Detection — PARTIALLY FIXED

Multiple competing implementations of "find the project root":

| Implementation | Method | Status |
|---------------|--------|--------|
| `ami-pwd` | `~/.config/ami/root` state file + walk for `pyproject.toml`/`.git` | Canonical |
| `ami.core.env.get_project_root()` | Python equivalent | Canonical |
| `backup/common/paths.py` | Imports from `ami.core.env` | Consolidated |
| `module_helpers.sh` | Uses `$AMI_ROOT` (set by ami-pwd) | Consolidated |
| `ami-run` | Calls `ami-pwd` | Consolidated |
| `submodule.sh` | Own `_find_orchestrator_root()` looking for `/base` | **Still divergent** |

**Current state:** Most tools converge on `ami-pwd` or `ami.core.env`. Only `submodule.sh` still has its own implementation.

**Remaining work:** Update `submodule.sh` to use `ami-pwd` or `$AMI_ROOT`.

---

## 5. Makefile Target Explosion — FIXED

Separate `install-cpu`, `install-cuda`, `install-rocm`, etc. targets all ran identical commands. Consolidated into a single `install` target with a 5-step flow: `sync-package`, `setup-config`, `register-extensions`, `install-bootstrap`, `install-shell`.

---

## 6. Agent Installation Duplication — FIXED

Two divergent implementations for installing AI agents (Python bootstrap vs shell `node.sh`).

**Resolution:** Created `bootstrap_agents.sh` wrapping `node.sh`. All agent components in `bootstrap_component_defs.py` point to this script. Custom NPM logic removed from `bootstrap_install.py`.

---

## 7. Hardcoded Infrastructure (ami_mail.py) — FIXED

SMTP host/port/sender hardcoded in source. Now externalized via `os.getenv()` with local-first defaults (`AMI_SMTP_HOST`, `AMI_SMTP_PORT`, `AMI_MAIL_FROM`).

---

## 8. Git Wrapper Recursion Loop — FIXED

Separate patcher script conflicted with bootstrap symlink. Eliminated the patcher; bootstrap now installs `git-guard` directly. Real git symlinked to `real-git`.

---

## 9. Shell Setup Comment Parsing Bug — FIXED

`grep "name:"` in `_verify_extensions` matched YAML comment lines. Updated grep pipeline to exclude comments with `grep -v "^#"`.
