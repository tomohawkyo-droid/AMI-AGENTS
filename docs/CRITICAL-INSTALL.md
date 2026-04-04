# CRITICAL ARCHITECTURE FAILURES & INSTALLATION REDUNDANCIES

**STATUS: ACTIVE THREAT**
**SEVERITY: HIGH**

This document tracks systemic "bullshit" discovered in the installation and bootstrap logic. These patterns threaten data integrity, code persistence, and developer sanity.

---

## 1. The "Self-Destructing" Code Trap (OpenVPN)
**File:** `ami/scripts/bootstrap/bootstrap_openvpn.sh`
**The Failure:**
This shell script contains a hardcoded `cat > ... << 'EOF_PYTHON'` heredoc at the end (lines 225-262).
**The Consequence:**
Every time `bootstrap_openvpn.sh` runs, it **OVERWRITES** the source code of `ami/scripts/bin/run_openvpn_client.py` with the heredoc content.
*   **Risk:** If a developer modifies the Python file directly to fix a bug or add a feature, the bootstrap script will **silently delete their work** on the next run.
*   **The Fix:** Remove the heredoc. The Python script exists in the repo; the bootstrap script should only symlink it or verify its existence.

## 2. Versioning "Split-Brain" (Agent CLIs)
**Files:** `ami/scripts/bootstrap_components.py` vs `scripts/package.json`
**The Failure:**
`package.json` declares the authoritative versions of Claude, Gemini, and Qwen. However, `bootstrap_components.py` **Hardcodes** older versions in the `AI_AGENTS` list (e.g., hardcoded `2.1.19` vs package `2.1.34`).
**The Consequence:**
The bootstrap installer ignores the `package.json` manifest and installs whatever is hardcoded in the Python file, or creates a conflict state. Updates to `package.json` have no effect on the bootstrap menu.
*   **The Fix:** `bootstrap_components.py` must dynamically read `scripts/package.json`.

## 3. The "Copy-Paste" Debian Extractor
**Files:**
*   `ami/scripts/bootstrap/bootstrap_git.sh`
*   `ami/scripts/bootstrap/bootstrap_openvpn.sh`
*   `ami/scripts/bootstrap/bootstrap_wkhtmltopdf.sh`
*   `ami/scripts/bootstrap/bootstrap_sd.sh`
*   `ami/scripts/bootstrap/bootstrap_openssl.sh`
**The Failure:**
Each script independently re-implements the logic to download a `.deb` file, run `ar x`, and extract `data.tar.*` to install binaries without `sudo`.
**The Consequence:**
*   **Inconsistency:** Some scripts handle `data.tar.zst` (modern Ubuntu), others crash on it.
*   **Maintenance:** Fixing extraction logic requires editing 5+ files.
*   **The Fix:** Create a shared `ami/scripts/bootstrap/utils/extract_deb.sh` library function.

## 4. Root Detection Schizophrenia
**The Failure:**
The codebase has at least **5 competing implementations** of "Where is the Project Root?":
1.  `ami-pwd`: Uses `~/.config/ami/root` state file.
2.  `bootstrap_components.py`: Walks up looking for `pyproject.toml` or `.git`.
3.  `backup/common/paths.py`: Walks up looking for `base/` or `scripts/`.
4.  `module_helpers.sh`: Recursive bash walk looking for `.venv`.
5.  `ami-run`: Relies on `ami-pwd`.
**The Consequence:**
Scripts disagree on the root directory, causing "File not found" errors when running from subdirectories.
*   **The Fix:** Standardize on **ONE** detection method (preferably `pyproject.toml` marker) and have all scripts import/source it.

## 5. Makefile Target Explosion
**File:** `Makefile`
**The Failure:**
The Makefile defines separate targets for `install-cpu`, `install-cuda`, `install-rocm`, `install-intel-xpu`, `install-mps`, etc.
**The Reality:**
They all executed the *exact same* setup commands. The original 4-command flow was `install-package-*`, `setup-config`, `register-extensions`, `install-safety-scripts`. The `install-safety-scripts` target was later removed because bootstraps now install guards directly (e.g., `bootstrap_git.sh` installs `git-guard`, see item 9). The current consolidated 5-step flow is: `sync-package`, `setup-config`, `register-extensions`, `install-bootstrap`, `install-shell`.
**The Consequence:**
Massive visual noise and violation of DRY (Don't Repeat Yourself). Adding a new installation step required editing 8 different targets.
*   **The Fix:** Use variables or pattern rules to consolidate into a single install flow that accepts an `EXTRA=...` argument. (DONE, targets consolidated; safety scripts absorbed into bootstrap guards.)

---

## 6. Agent Installation Duplication
**Files:**
*   `ami/scripts/bootstrap_install.py` (Python implementation of `npm install`)
*   `ami/scripts/setup/node.sh` (Bash implementation of `npm install`)
**The Failure:**
We have two divergent implementations for installing AI agents. The Python bootstrap installer manually runs `npm install` based on hardcoded versions in `bootstrap_components.py`, while the shell scripts and Makefile use `node.sh` which reads from `package.json`.
**The Consequence:**
"Split-Brain" deployment. The TUI installer might install different versions than the CLI/Makefile installer.
**The Fix:**
1.  Create `ami/scripts/bootstrap/bootstrap_agents.sh` that wraps `node.sh`.
2.  Update `bootstrap_components.py` to define agents as `type=ComponentType.SCRIPT` pointing to this new script.
3.  Delete the custom NPM installation logic from `bootstrap_install.py`.

---

## 7. Hardcoded Infrastructure (ami_mail.py)
**File:** `ami/scripts/bin/ami_mail.py`
**The Failure:**
SMTP host (`192.168.50.66`), port (`2526`), and sender address were hardcoded directly in the source code.
**The Consequence:**
The mail tool only works on a specific local network and fails immediately in any other environment (CI, Cloud, or different local subnet). This is a portability and security violation.
**The Fix:**
Wrap infrastructure constants in `os.getenv()` lookups with sensible local-first defaults (`127.0.0.1`).

## 8. Root Detection Schizophrenia
**The Failure:**
There are at least 5 competing implementations of "Find the Project Root":
1.  `ami-pwd`: Uses `~/.config/ami/root`.
2.  `bootstrap_components.py`: Walks up for `pyproject.toml`.
3.  `backup/common/paths.py`: Walks up for `base/` or `scripts/`.
4.  `module_helpers.sh`: Bash walk for `.venv`.
5.  `submodule.sh`: `_find_orchestrator_root` function.
**The Consequence:**
Tools frequently break when executed from subdirectories because they disagree on where "home" is. Path resolution is unreliable across the stack.
**The Fix:**
Standardize on a single, authoritative detection method (preferably looking for `pyproject.toml` as the anchor) and have all scripts import it.

---

## 9. Git Wrapper Recursion Loop (Resolved)
**File:** `ami/scripts/utils/git-guard` (installed by `bootstrap_git.sh`)
**The Failure:**
A separate patcher script (`disable_no_verify_patcher.sh`) wrote the wrapper to `.boot-linux/bin/git`, but `bootstrap_git.sh` created a symlink at the same path. Running bootstrap after the patcher (or standalone via `make bootstrap-core`) silently destroyed the safety wrapper.
**The Fix:**
Eliminated the separate patcher. The bootstrap now installs the `git-guard` script directly (same pattern as `podman-guard`). Real git is symlinked to `real-git`, guard script is copied as `git`. Running bootstrap always installs the guard.

---

## 10. Shell Setup Comment Parsing Bug
**File:** `ami/scripts/shell/shell-setup`
**The Failure:**
The `_verify_extensions` function used `grep "name:"` to parse `extensions.yaml`. This incorrectly matched the comment line `#   - name: Command name (what you type in shell)`, causing the shell to complain about a missing command named "Command name (what you type in shell)".
**The Consequence:**
Confusing error messages during shell startup and installation.
**The Fix:**
Updated the grep pipeline to exclude comments (`grep -v "^#"`) before extracting names.

---

**IMMEDIATE ACTION REQUIRED:**
1.  **NEUTRALIZE** the OpenVPN overwrite trap. (DONE)
2.  **EXTERNALIZE** `ami_mail.py` infrastructure config. (DONE)
3.  **CREATE** `bootstrap_agents.sh` to unify agent installation. (DONE)
4.  **REFACTOR** `bootstrap_components.py` to use the new script and dynamic versions. (DONE)
5.  **CLEANUP** `bootstrap_install.py` (remove NPM logic). (DONE)
6.  **REFACTOR** the Makefile to eliminate target explosion. (DONE)
7.  **UNIFY** Root Detection logic. (DONE)
8.  **FIX** Git Wrapper Recursion. (DONE)
9.  **FIX** Shell Setup Comment Parsing. (DONE)
