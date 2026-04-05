# Requirements: Enterprise Mail Extension (`ami-mail`)

**Date:** 2026-04-05
**Status:** REQUIREMENTS COMPLETE — ready for implementation
**Workflow:** [WF-RESEARCH-REQUIREMENTS.md](../workflows/WF-RESEARCH-REQUIREMENTS.md)

---

## 1. Existing State Audit

### 1.1 `ami-mail` CLI (current)

**File:** `ami/scripts/bin/ami_mail.py` (309 lines)
**Registration:** enterprise category, features: `send, send-block, fetch`

Built on Python stdlib (`smtplib`, `imaplib`, `email`):

| Command | What it does | Limitations |
|---------|-------------|-------------|
| `send` | SMTP send (text/HTML, attachments) | Single recipient, no templating, no auth beyond basic, creds via CLI args |
| `send-block` | Send + poll IMAP for reply | Subject-matching only, fragile, IMAP creds on CLI |
| `fetch` | IMAP fetch recent N messages | Read-only listing, no search, no actions |

**Config:** Env vars only — `AMI_SMTP_HOST` (127.0.0.1), `AMI_SMTP_PORT` (2525), `AMI_MAIL_FROM` (ami-cli@localhost).

### 1.2 Deployed Mail Infrastructure (AMI-STREAMS)

The server runs a complete mail relay stack via Ansible:

| Service | What | Port(s) | Config Location |
|---------|------|---------|-----------------|
| **Exim Relay** | SMTP relay → Gmail | Host 2525/2526 → Container 8025 | `AMI-STREAMS/ansible/.../roles/galaxy/exim_relay/` |
| **Postmoogle** | Email↔Matrix bridge | SMTP 2525, TLS 25587, Host 25, 587 | `AMI-STREAMS/ansible/.../roles/custom/matrix-bridge-postmoogle/` |
| **Alertmanager** | Alert → email routing | Via exim-relay | `AMI-STREAMS/alertmanager/config.yml` |
| **Postfix** | Historical/inactive | — | `AMI-STREAMS/postfix/` (spool dirs only) |

**Exim relay details:**
- Relays through `smtp.gmail.com:587` with auth
- Sender: `independentailabs@gmail.com`
- Docker container `matrix-exim-relay`
- Used by: Matrix Synapse, Matrix Auth Service, Alertmanager, Polymarket reports

**Postmoogle details:**
- Bidirectional email↔Matrix bridge (v0.9.28)
- Receives email on port 25/587, delivers to Matrix rooms
- Can send email from Matrix rooms

**No local IMAP server** (no Dovecot). IMAP access is to external providers (Gmail etc).

### 1.3 Polymarket Prototype (Best Existing Example)

**Location:** `projects/polymarket-insider-tracker/scripts/`

Most complete mail workflow in the codebase — shows real production patterns:

- **YAML config** (`report-config.yaml`) — SMTP host:port, sender, per-target recipients with enable/disable
- **Jinja2 templates** — HTML + plain text email templates with configurable styling
- **Multi-target delivery** — Named targets with per-target subject/sender overrides
- **PDF pipeline** — pandoc → wkhtmltopdf → attach to email
- **Dry-run mode** — `--dry-run` to preview
- **Subject templating** — `[AMI] Polymarket Snapshot — {date}`
- **Uses ami-mail** — Calls `ami-mail send` as subprocess for actual delivery

**Key pattern:** YAML config + Jinja2 templates + ami-mail send = working report pipeline. Needs generalization.

### 1.4 Services Already Using Email

| Consumer | How | SMTP Target |
|----------|-----|-------------|
| Matrix Synapse | Notifications, verification | `matrix-exim-relay:25` (internal docker) |
| Matrix Auth Service | Password reset, verification | `matrix-exim-relay:25` |
| Alertmanager | Alert notifications | `matrix-exim-relay:8025` |
| Polymarket reports | Scheduled report delivery | `192.168.50.66:2526` (exim external) |
| ami-mail CLI | Ad-hoc sends | `127.0.0.1:2525` (default) |

### 1.5 Integration Points

| System | Path | How it helps mail |
|--------|------|-------------------|
| **OpenBao** | `platform/secrets/service/` KV v2 | Store SMTP/IMAP credentials per account |
| **Keycloak** | JWT auth, OIDC | OAuth2 for Gmail/O365 IMAP (future) |
| **ami-cron** | `ami/scripts/bin/ami_cron.py` | Schedule recurring sends, inbox polling |
| **ami-docs** | pandoc, wkhtmltopdf, pdflatex | Generate PDF/HTML attachments |
| **Jinja2** | Available (Ansible dep) | Email body + subject templating |
| **Exim relay** | Port 2525/2526 | Already-working SMTP relay to Gmail |
| **Postmoogle** | Port 25/587 | Email↔Matrix bridging (separate concern) |

---

## 2. Gap Analysis

| Need | Status | Notes |
|------|--------|-------|
| SMTP send | **Solved** | ami-mail + exim relay works |
| HTML email | **Solved** | ami-mail `--html` works |
| Attachments | **Solved** | ami-mail `-a` works |
| Jinja2 templates | **Prototype** | Polymarket has it, needs generalization |
| Multi-target delivery | **Prototype** | Polymarket has it, needs generalization |
| YAML-driven config | **Prototype** | Polymarket has it, needs generalization |
| Dry-run mode | **Prototype** | Polymarket has it |
| Multi-account SMTP | **Gap** | Only one SMTP config at a time (env vars) |
| Secrets from OpenBao | **Gap** | Creds are CLI args / env vars |
| IMAP search/filter | **Gap** | Only fetch-recent exists |
| IMAP actions (move/delete/mark) | **Gap** | Fetch is read-only |
| Contact/distribution lists | **Gap** | No address book |
| Queue/retry/outbox | **Gap** | No delivery tracking |
| Bounce handling | **Gap** | No bounce detection |
| DKIM/SPF/DMARC checks | **Gap** | No sending domain verification |
| OAuth2 IMAP auth | **Gap** | Only basic auth |
| Scheduled delivery | **Gap** | ami-cron exists but no built-in integration |
| PGP/S/MIME encryption | **Gap** | No encryption support |

---

## 3. External Research

### 3.1 Terminal Mail Clients

| Feature | NeoMutt | aerc | **himalaya** |
|---------|---------|------|-------------|
| Language | C | Go | **Rust** |
| Interface | TUI (full screen) | TUI (tabbed) | **Stateless CLI** |
| Multi-account | folder-hook sourcing | Native tabs | **Native `--account` flag** |
| Config | Complex muttrc | Moderate INI | **Single TOML** |
| Built-in IMAP | No (delegates to mbsync) | Yes | **Yes (via email-lib)** |
| Built-in SMTP | No (delegates to msmtp) | Yes | **Yes** |
| JSON output | No | No | **Yes (`--output json`)** |
| OAuth2 | Needs mailctl | Limited | **Built-in** |
| PGP | Native | Native | GPG bindings |
| Maturity | Decades | ~6 years | ~5 years, **v1.2.0 (Feb 2026)** |

**himalaya** is the only stateless CLI — every command is `himalaya <action>`, no TUI event loop. Ideal for scripting and as a backend.

### 3.2 himalaya / pimalaya Ecosystem

**Repo:** https://github.com/pimalaya/himalaya (5,857 stars, v1.2.0)

Core library ecosystem:

| Crate | Purpose |
|-------|---------|
| `email-lib` | Core library — backends, all operations (19K SLoC) |
| `mml-lib` | MIME Meta Language — message composition |
| `io-secret` | Secret retrieval from multiple sources |
| `io-oauth` | OAuth flow management |
| `maildirs` | Maildir filesystem management |

**email-lib operations:**
- Folders: add, list, expunge, purge, delete
- Envelopes: list, get (search/filter)
- Flags: add, set, remove (read, flagged, answered, deleted, custom)
- Messages: add, peek, get, copy, move, delete, send
- Backends: IMAP, Maildir, notmuch, SMTP, sendmail
- Extra: sync, watch (IDLE), retry, autoconfig, TLS

**himalaya account config (TOML):**
```toml
[accounts.work]
email = "user@company.com"
display-name = "User"
backend.type = "imap"
backend.host = "imap.company.com"
backend.port = 993
backend.auth.type = "password"
backend.auth.command = "pass show email/work"  # shell command for secrets
message.send.backend.type = "smtp"
message.send.backend.host = "smtp.company.com"
message.send.backend.port = 587
```

**Key features for AMI:**
- Secrets via shell commands (pass, gpg, **openbao CLI**), OAuth2, env vars
- ALL commands support `--output json` — trivially scriptable from Python
- Multi-account native (`--account` flag)
- No TUI lock — stateless, scriptable

### 3.3 Sync & Search Tools (Not needed for initial scope)

| Tool | Purpose | Status |
|------|---------|--------|
| **mbsync/isync** | IMAP → Maildir sync (C) | Mature, the standard |
| **neverest** (pimalaya) | Rust sync (any backend ↔ any) | Pre-1.0, not production-stable |
| **notmuch** | Xapian full-text mail search + tagging | Mature, 15x faster indexing than mu |

### 3.4 Python Libraries

| Library | Purpose | Verdict |
|---------|---------|---------|
| **imap-tools** v1.11.1 | High-level IMAP (zero deps, query builder, XOAUTH2) | Best Python IMAP lib — fallback if himalaya has issues |
| **IMAPClient** v3.1.0 | Pythonic IMAP (lower-level, more server compat) | Second fallback |
| **Jinja2** | Email templating | Already available (Ansible dep) |
| **checkdmarc** | SPF/DMARC validation | For `ami-mail check-domain` |

### 3.5 Mail Queue Patterns

- **msmtpq** — ships with msmtp, queues to disk if offline, retries via systemd timer
- No mature standalone Python mail queue outside Django
- himalaya does NOT have built-in queueing
- Future: SQLite/Redis + asyncio if needed

### 3.6 OAuth2 for CLI Mail

- **himalaya** — built-in OAuth2 flow (keyring-backed token storage)
- **email-oauth2-proxy** (1,382 stars) — transparent local proxy for clients without native OAuth2
- **imap-tools** — `.xoauth2()` method for direct XOAUTH2 auth

---

## 4. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Full mail management | Send, receive, search, filter, reply, folders, flags |
| Architecture | **himalaya as backend** | Rust CLI wraps IMAP+SMTP natively; Python wraps himalaya for AMI features. Same pattern as ami-docs wrapping pandoc. |
| SMTP backends | Multiple per-account | Exim relay for automation, Gmail/O365/SES for personal/bulk |
| Postmoogle | Separate concern | Independent email↔Matrix bridge, not integrated into ami-mail |
| Credentials | **himalaya secret commands → OpenBao CLI** | `bao kv get` in himalaya `auth.command`. Native, no temp files, no Python involvement in credential retrieval. |
| Local storage | None | Direct IMAP, no Maildir/sync/notmuch. Simplest path. |
| CLI pattern | `<verb> [account] ...` | Account as 2nd arg, default account used when omitted |
| Template pipeline | **Template + data file** | Jinja2 renders email body from template + YAML/JSON data. PDF generation delegated to ami-docs (external). |
| send-block | Keep, improve | Upgrade to himalaya IMAP with Message-ID threading instead of fragile subject matching |
| Interactive mode | Scripted only | Non-interactive, JSON-outputtable. No TUI, no pager, no $EDITOR. Use himalaya directly for interactive. |

---

## 5. Architecture

### Overview

```
ami-mail (Python wrapper)
  |-- Config layer: ami/config/mail.yaml --> generates himalaya TOML
  |-- Secrets layer: OpenBao paths in YAML --> himalaya auth.command = "bao kv get ..."
  |-- Template layer: Jinja2 templates (shared + per-project)
  |-- Send path: render template --> himalaya message send
  |-- Read path: himalaya envelope list/get --output json --> format
  |-- Search path: himalaya envelope list --output json --> filter
  +-- Schedule layer: ami-cron integration for recurring sends/polls
         |
         v
himalaya (Rust CLI, bootstrapped to .boot-linux/bin/)
  |-- IMAP backend (direct, no local storage)
  |-- SMTP backend (per-account: exim relay, Gmail, O365, SES, etc.)
  |-- OAuth2 (built-in)
  +-- JSON output for all operations
```

### Config Model

**Source of truth:** `ami/config/mail.yaml`

```yaml
accounts:
  automation:
    email: ami-reports@ami.local
    display_name: AMI Automation
    default: true
    smtp:
      host: 192.168.50.66
      port: 2526
      encryption: none        # local relay, no TLS needed
      auth: none              # exim relay, no auth needed
    # No IMAP -- send-only account

  work:
    email: vladislav.donchev@gmail.com
    display_name: Vlad
    imap:
      host: imap.gmail.com
      port: 993
      encryption: tls
      auth:
        type: password
        secret: platform/secrets/service/mail/work  # OpenBao path
        field: imap_password
    smtp:
      host: smtp.gmail.com
      port: 587
      encryption: starttls
      auth:
        type: password
        secret: platform/secrets/service/mail/work
        field: smtp_password
    folders:
      inbox: INBOX
      sent: "[Gmail]/Sent Mail"
      drafts: "[Gmail]/Drafts"
      trash: "[Gmail]/Trash"

templates:
  dir: ami/config/mail/templates     # shared templates
  project_dirs:                       # per-project overrides
    - projects/polymarket-insider-tracker/scripts/templates

targets:                              # named recipient groups
  team:
    - vlad@gmail.com
    - archive@ami.local
  alerts:
    - vlad@gmail.com
```

**Auto-generates** himalaya TOML, translating:
- `auth.secret` + `auth.field` --> `backend.auth.command = "bao kv get -mount=secret -field={field} {secret}"`
- Account structure --> himalaya TOML sections
- Folder aliases --> himalaya folder.aliases

### Command Surface

```
ami-mail send <account> <recipient|@target> -s <subject> [-t template.jinja2] [-d data.yaml] [-a file] [--html] [--dry-run]
ami-mail list <account> [--folder INBOX] [--limit 20]
ami-mail read <account> <message-id>
ami-mail search <account> <query>
ami-mail reply <account> <message-id> [-t template.jinja2]
ami-mail forward <account> <message-id> <recipient>
ami-mail move <account> <message-id> <folder>
ami-mail delete <account> <message-id>
ami-mail flag <account> <message-id> <flag>    # read, starred, answered, etc.
ami-mail folders <account>                      # list folders
ami-mail accounts                               # list configured accounts
ami-mail check-domain <domain>                  # SPF/DMARC/DKIM validation
ami-mail config generate                        # regenerate himalaya TOML from mail.yaml
```

---

## 6. Implementation Plan

### Phase 1: Bootstrap himalaya

Follow the established bootstrap pattern (same as gh, sd, pandoc):

1. **Component definition** -- Add to `ami/scripts/bootstrap_component_defs.py`:
   ```python
   Component(
       name="himalaya",
       label="Himalaya",
       description="CLI email client (IMAP/SMTP)",
       type=ComponentType.SCRIPT,
       group="Security & Networking",
       script="bootstrap_himalaya.sh",
       detect_path=".boot-linux/bin/himalaya",
       version_cmd=[".boot-linux/bin/himalaya", "--version"],
       version_pattern=r"himalaya (\d+\.\d+\.\d+)",
   )
   ```

2. **Bootstrap script** -- Create `ami/scripts/bootstrap/bootstrap_himalaya.sh`:
   - Use `${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}` (set by installer)
   - Download from `https://github.com/pimalaya/himalaya/releases/download/v{VERSION}/himalaya-{VERSION}-linux-x86_64.tar.gz`
   - Extract to temp dir, move binary to `${BIN_DIR}/himalaya`, `chmod +x`
   - Verify with `himalaya --version`

3. **Install:** `make install-bootstrap` (TUI selector) or direct `bash ami/scripts/bootstrap/bootstrap_himalaya.sh`
4. **Verify:** `.boot-linux/bin/himalaya --version`

### Phase 2: Mail config schema

1. Create `ami/config/mail.template.yaml` (tracked in git) and `ami/config/mail.yaml` (gitignored)
2. Define account schema: email, display_name, imap{}, smtp{}, folders{}, auth with OpenBao paths
3. Define templates section: shared dir + per-project dirs
4. Define targets section: named recipient groups
5. Write config-to-TOML generator: `mail.yaml` --> himalaya `config.toml`

### Phase 3: Rewrite ami-mail

1. Replace `ami/scripts/bin/ami_mail.py` (309 lines --> new implementation)
2. Core modules: config loader, himalaya wrapper (subprocess + JSON parsing), Jinja2 renderer
3. Commands:
   - `send` -- template render --> himalaya message send (supports @targets)
   - `list` -- himalaya envelope list --> formatted output
   - `read` -- himalaya message get --> formatted output
   - `search` -- himalaya envelope list with filters
   - `reply` / `forward` -- himalaya message ops with optional template
   - `move` / `delete` / `flag` -- himalaya message operations
   - `folders` -- himalaya folder list
   - `accounts` -- list from mail.yaml
   - `send-block` -- send --> poll with himalaya IMAP (Message-ID threading)
   - `config generate` -- regenerate himalaya TOML
   - `check-domain` -- checkdmarc SPF/DMARC validation
4. Update `extensions.yaml` features line

### Phase 4: Shared templates

1. Create `ami/config/mail/templates/` with base templates:
   - `report.html.jinja2` -- generalized from polymarket prototype
   - `alert.html.jinja2` -- for system alerts/notifications
   - `plain.txt.jinja2` -- minimal plain text
2. Template variables: `{{ subject }}`, `{{ date }}`, `{{ data.<key> }}`, `{{ config.<key> }}`

### Phase 5: Cron integration

1. Document ami-cron patterns for scheduled mail:
   - `ami-cron add "0 8 * * 1-5" "ami-mail send automation @team -t weekly-report.jinja2 -d /path/to/data.yaml" --label weekly-report`
2. No built-in scheduling in ami-mail -- keep it separate (ami-cron is the scheduler)

### Phase 6: Migrate polymarket

1. Simplify `send-report.py` to: fetch data --> save to YAML --> `ami-docs pandoc` for PDF --> `ami-mail send`
2. Templates stay in project dir (referenced via mail.yaml `project_dirs`)

---

## 7. Verification

1. `.boot-linux/bin/himalaya --version` -- bootstrapped binary works
2. `ami-mail accounts` -- lists accounts from mail.yaml
3. `ami-mail config generate` -- produces valid himalaya TOML
4. `ami-mail send automation vlad@gmail.com -s "Test" -b "Hello"` -- sends via exim relay
5. `ami-mail send automation @team -t report.html.jinja2 -d test-data.yaml --html --dry-run` -- template + dry run
6. `ami-mail list work --folder INBOX --limit 5` -- lists envelopes via himalaya IMAP
7. `ami-mail search work "from:github"` -- searches via himalaya
8. `ami-mail send-block work vlad@gmail.com -s "Approval" -b "Reply YES" --timeout 60` -- improved send-block
9. `ami-mail check-domain gmail.com` -- SPF/DMARC check
10. Integration tests pass
