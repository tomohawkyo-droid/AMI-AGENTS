# Specification: Enterprise Mail Extension (`ami-mail`)

**Status:** MOVED
**Moved to:** `projects/AMI-STREAMS/docs/SPEC-MAIL.md`

ami-mail is now built as a himalaya fork in the AMI-STREAMS project. Requirements and specifications live there.

---

## Implementation Status (2026-04-13)

### Current (v1 — stdlib)

| Feature | Status | Details |
|---------|--------|---------|
| SMTP send | DONE | `smtplib.SMTP` via exim relay (127.0.0.1:2525) |
| HTML email | DONE | `--html` flag, `add_alternative(subtype="html")` |
| File attachments | DONE | `--attachment` flag, multiple, MIME type detection |
| IMAP fetch | DONE | `imaplib.IMAP4_SSL`, folder selection, limit |
| Send-block | DONE | Polls IMAP, **subject matching** (not Message-ID threading) |
| Multi-account | NOT BUILT | Single account via CLI args / env vars |
| Named recipients | NOT BUILT | |
| Jinja2 templates | NOT BUILT | |
| JSON output | NOT BUILT | |
| Search/filter | NOT BUILT | Basic FROM search only (in send-block) |
| Reply/forward/move/delete/flags | NOT BUILT | |
| himalaya backend | NOT BUILT | No bootstrap script, no component def |
| Config generation | NOT BUILT | No mail.yaml, no TOML generation |
| Domain verification | NOT BUILT | |

### Planned (v2 — himalaya)

Migration from stdlib to himalaya backend. All v1 features preserved, all REQ-MAIL requirements addressed.

---

## 1. Architecture

### Current (v1)

```
ami-mail (Python stdlib)
  ├── send       → smtplib.SMTP → exim relay :2525 → Gmail
  ├── send-block → smtplib.SMTP + imaplib.IMAP4_SSL (poll loop)
  └── fetch      → imaplib.IMAP4_SSL
```

Single file: `ami/scripts/bin/ami_mail.py` (309 lines). No config file. SMTP host/port/sender via env vars (`AMI_SMTP_HOST`, `AMI_SMTP_PORT`, `AMI_MAIL_FROM`). IMAP credentials passed as CLI args.

### Target (v2)

```
ami-mail (Python wrapper)
  ├── reads ami/config/mail.yaml
  ├── generates himalaya TOML config (per-account)
  ├── translates secret refs → himalaya auth.command fields
  └── invokes himalaya as subprocess for all operations

himalaya (Rust CLI, .boot-linux/bin/himalaya)
  ├── SMTP send (with MIME, attachments, threading)
  ├── IMAP operations (list, read, search, move, delete, flags)
  └── auth.command for credential retrieval at runtime
```

Same pattern as ami-docs wrapping pandoc: Python facade generating config, Rust binary doing the work.

---

## 2. himalaya Bootstrap

### Component Definition

```python
Component(
    name="himalaya",
    label="Himalaya",
    description="CLI email client (IMAP/SMTP)",
    type=ComponentType.SCRIPT,
    group="Enterprise Tools",
    script="bootstrap_himalaya.sh",
    detect_path=".boot-linux/bin/himalaya",
    version_cmd=[".boot-linux/bin/himalaya", "--version"],
    version_pattern=r"himalaya (\d+\.\d+\.\d+)",
)
```

### Bootstrap Script (`ami/scripts/bootstrap/bootstrap_himalaya.sh`)

Download from GitHub releases (same pattern as `bootstrap_pandoc.sh`):

```
URL: https://github.com/pimalaya/himalaya/releases/download/v${VERSION}/himalaya-${ARCH}-linux.tar.gz
Install to: .boot-linux/himalaya/
Symlink: .boot-linux/bin/himalaya
Architectures: x86_64, aarch64
```

---

## 3. Configuration

### mail.yaml (gitignored, template tracked)

```yaml
# ami/config/mail.yaml
default_account: relay

accounts:
  relay:
    display_name: "AMI CLI"
    email: "ami-cli@localhost"
    smtp:
      host: 127.0.0.1
      port: 2525
      encryption: none    # exim relay, local only
    # No IMAP — send-only account

  gmail:
    display_name: "AMI Notifications"
    email: "notifications@example.com"
    smtp:
      host: smtp.gmail.com
      port: 587
      encryption: starttls
      auth:
        command: "bao kv get -mount=secret -field=password platform/secrets/service/gmail-smtp"
    imap:
      host: imap.gmail.com
      port: 993
      encryption: tls
      auth:
        command: "bao kv get -mount=secret -field=password platform/secrets/service/gmail-imap"

  # Interim (pre-OpenBao): credentials from .env
  gmail-env:
    display_name: "AMI Gmail"
    email: "${GMAIL_USER}"
    smtp:
      host: smtp.gmail.com
      port: 587
      encryption: starttls
      auth:
        user: "${GMAIL_USER}"
        password: "${GMAIL_APP_PASSWORD}"
    imap:
      host: imap.gmail.com
      port: 993
      encryption: tls
      auth:
        user: "${GMAIL_USER}"
        password: "${GMAIL_APP_PASSWORD}"

recipient_groups:
  team:
    - alice@example.com
    - bob@example.com
  ops:
    - oncall@example.com

templates:
  shared: ami/config/mail/templates/
  # Per-project dirs added here
```

### TOML Generation

`ami-mail` reads `mail.yaml` and generates himalaya-compatible TOML:

```toml
# Generated — do not edit
[accounts.gmail]
display-name = "AMI Notifications"
email = "notifications@example.com"
backend.type = "imap"
backend.host = "imap.gmail.com"
backend.port = 993
backend.encryption = "tls"
backend.auth.type = "command"
backend.auth.command = "bao kv get -mount=secret -field=password platform/secrets/service/gmail-imap"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 587
message.send.backend.encryption = "starttls"
message.send.backend.auth.type = "command"
message.send.backend.command = "bao kv get -mount=secret -field=password platform/secrets/service/gmail-smtp"
```

For `.env`-based interim auth, the Python wrapper resolves env vars before writing the TOML, using himalaya's `passwd.type = "command"` with `echo` as a simple passthrough.

---

## 4. Send-Block (Human-in-the-Loop)

### Current Implementation (v1)

- Sends email via SMTP
- Polls IMAP in a loop (`time.sleep(poll_interval)`)
- Searches for `FROM "{recipient}"` messages
- Matches reply via **subject line containment** (strips "Re:", case-insensitive compare)
- Returns body text to stdout
- Exits 1 on timeout

### Target Implementation (v2)

- Send email via himalaya, capture returned `Message-ID` header
- Poll IMAP via himalaya `envelope list` with JSON output
- Match replies by `In-Reply-To` or `References` header containing the original `Message-ID`
- Return reply as JSON (`--json` flag) or plain text
- Exit codes: 0 (reply received), 1 (timeout), 2 (system error)

### Invocation

```bash
# Agent sends question, waits up to 10 minutes for human reply
ami-mail send-block \
  --account gmail \
  --to human@example.com \
  --subject "Approval needed: deploy v2.1?" \
  --body "Please reply YES or NO" \
  --timeout 600 \
  --poll-interval 15 \
  --json
```

Returns:
```json
{
  "from": "human@example.com",
  "subject": "Re: Approval needed: deploy v2.1?",
  "date": "2026-04-13T10:30:00Z",
  "body": "YES, approved.",
  "message_id": "<reply-id@example.com>",
  "in_reply_to": "<original-id@localhost>"
}
```

---

## 5. CLI Design (v2)

```bash
# Sending
ami-mail send --account relay --to user@example.com --subject "Test" --body "Hello"
ami-mail send --account gmail --to @team --subject "Report" --template weekly-report --data report.yaml
ami-mail send --account relay --to user@example.com --subject "Test" --body "Hello" --attachment report.pdf --dry-run
ami-mail send --account gmail --to user@example.com --cc boss@example.com --bcc audit@example.com --subject "Proposal" --body "See attached" --attachment proposal.pdf

# Reading
ami-mail list --account gmail                          # envelopes from INBOX
ami-mail list --account gmail --folder Sent --limit 20
ami-mail read --account gmail --id 1234                # full message
ami-mail search --account gmail --from boss@co.com --since 2026-04-01
ami-mail folders --account gmail                       # list IMAP folders

# Operations
ami-mail reply --account gmail --id 1234 --body "Acknowledged"
ami-mail reply --account gmail --id 1234 --template ack --data ctx.yaml
ami-mail forward --account gmail --id 1234 --to colleague@co.com
ami-mail move --account gmail --id 1234 --folder Archive
ami-mail delete --account gmail --id 1234
ami-mail flag --account gmail --id 1234 --set starred
ami-mail flag --account gmail --id 1234 --remove read

# Send-block
ami-mail send-block --account gmail --to human@co.com --subject "Approve?" --body "Yes/No" --timeout 600 --json

# Domain verification
ami-mail check-domain example.com

# All read commands support --json
ami-mail list --account gmail --json
```

```bash
# Batch / mail merge
ami-mail batch --account gmail --template newsletter --data subscribers.csv --subject "Update: {{title}}" --dry-run
ami-mail batch --account gmail --template newsletter --data subscribers.csv --subject "Update: {{title}}" --rate 10/min
ami-mail batch --account gmail --to @dev-team --template announcement --data release.yaml --bcc-mode
ami-mail batch --account relay --template invoice --data clients.yaml --attachment-pdf --rate 5/min
```

All commands delegate to himalaya subprocess. `ami-mail` handles:
- Config loading and TOML generation
- Recipient group resolution (`@team` → address list)
- Jinja2 template rendering (before passing body to himalaya)
- CC/BCC header assembly
- Batch iteration, per-recipient personalization, and rate limiting
- PDF attachment generation (delegates to ami-docs)
- Send-block polling loop and Message-ID tracking
- JSON output formatting
- Batch progress reporting and failure logging

---

## 6. Batch Sending & Personalization

### Two Modes

**BCC mode** (`--bcc-mode`): Single message, all recipients in BCC. No personalization — everyone gets the same body. Fast, one himalaya invocation.

```bash
ami-mail batch --account relay --to @dev-team --subject "All-hands tomorrow" --body "See you at 3pm" --bcc-mode
```

Flow:
1. Resolve `@dev-team` → list of addresses
2. Assemble RFC 2822 headers with all addresses in BCC
3. Pipe single message to `himalaya template send`

**Individual mode** (default): One message per recipient with per-recipient template variables. Supports full mail merge from CSV or YAML/JSON data files.

```bash
ami-mail batch --account gmail --template newsletter --data subscribers.csv --subject "Hi {{name}}, your {{month}} update" --rate 10/min
```

Flow:
1. Load recipient data from CSV/YAML/JSON — each row is one recipient
2. For each recipient:
   a. Render Jinja2 template with row data + global data
   b. Render subject with row data
   c. Assemble RFC 2822 message (headers + MML body)
   d. Pipe to `himalaya template send`
   e. Log result (recipient, status, message-id or error)
   f. Sleep per rate limit
3. Report summary: sent, failed, skipped

### Recipient Data Format

**CSV:**
```csv
email,name,plan,renewal_date
alice@example.com,Alice,pro,2026-05-01
bob@example.com,Bob,free,2026-06-15
```

**YAML:**
```yaml
recipients:
  - email: alice@example.com
    name: Alice
    plan: pro
  - email: bob@example.com
    name: Bob
    plan: free
```

**Group reference:** `--to @dev-team` loads addresses from `mail.yaml` recipient_groups. No per-recipient variables in this mode (use `--bcc-mode` or provide a data file for personalization).

### Rate Limiting

Format: `--rate N/unit` where unit is `sec`, `min`, or `hour`.

| Flag | Behavior |
|------|----------|
| `--rate 1/sec` | 1 message per second (sleep 1s between sends) |
| `--rate 10/min` | 10 per minute (sleep 6s between sends) |
| `--rate 500/hour` | 500 per hour (sleep 7.2s between sends) |
| (no flag) | No rate limiting — send as fast as possible |

Gmail limit: ~500/day for personal, ~2000/day for Workspace. SES varies by account. Exim relay has no limit but upstream relay may.

### Batch Reporting

During execution:
```
[1/200] alice@example.com ✓ <msg-id-1@localhost>
[2/200] bob@example.com ✓ <msg-id-2@localhost>
[3/200] carol@example.com ✗ SMTP error: 550 mailbox not found
...
[200/200] Complete: 198 sent, 2 failed
```

With `--json`:
```json
{
  "total": 200,
  "sent": 198,
  "failed": 2,
  "results": [
    {"email": "alice@example.com", "status": "sent", "message_id": "<msg-id-1@localhost>"},
    {"email": "carol@example.com", "status": "failed", "error": "550 mailbox not found"}
  ]
}
```

Failed sends are logged but do not abort the batch.

### Dry-Run

`--dry-run` on batch:
1. Loads all recipient data
2. Renders every template (catches Jinja2 errors)
3. Prints each rendered message (or first N with `--preview N`)
4. Reports total count and any render failures
5. Sends nothing

---

## 7. Template Rendering

```bash
ami-mail send --account relay --to @ops --subject "Weekly Report: {{week}}" --template weekly-report --data report.yaml
```

Flow:
1. Load template from `ami/config/mail/templates/weekly-report.html` (or `.txt`)
2. Load data from `report.yaml`
3. Render with Jinja2 (template receives: `subject`, `date`, `account`, and all data file keys)
4. If template is HTML, send as HTML body
5. If `--attachment-pdf` flag, render HTML → PDF via `ami-docs pandoc` and attach

---

## 7. Domain Verification

```bash
ami-mail check-domain example.com
```

Uses `dns.resolver` (dnspython) or subprocess `dig`/`nslookup`:
- Query `_dmarc.example.com` TXT record
- Query `example.com` TXT records for SPF (`v=spf1`)
- Report pass/fail with record values

---

## 8. File Map

### Current (v1)

| File | Purpose |
|------|---------|
| `ami/scripts/bin/ami_mail.py` | CLI entry point (309 lines, stdlib) |
| `ami/config/extensions.yaml` | Extension registration (enterprise category) |

### Target (v2)

| File | Purpose |
|------|---------|
| `ami/scripts/bin/ami_mail.py` | CLI entry point (rewritten, himalaya wrapper) |
| `ami/scripts/bootstrap/bootstrap_himalaya.sh` | himalaya binary bootstrap |
| `ami/scripts/bootstrap_component_defs.py` | himalaya component definition (new entry) |
| `ami/config/mail.template.yaml` | Mail config template (tracked) |
| `ami/config/mail.yaml` | Mail config (gitignored, runtime) |
| `ami/config/mail/templates/` | Shared Jinja2 email templates |
| `.boot-linux/bin/himalaya` | Bootstrapped himalaya binary |

---

## 9. Migration Path (v1 → v2)

1. **Bootstrap himalaya**: Create `bootstrap_himalaya.sh`, add component def
2. **Config system**: Create `mail.template.yaml`, implement YAML→TOML generation
3. **Rewrite send**: Replace `smtplib` with himalaya subprocess, support multi-account, CC/BCC
4. **Rewrite fetch**: Replace `imaplib` with himalaya subprocess, add JSON output
5. **Rewrite send-block**: Message-ID threading instead of subject matching
6. **Add operations**: reply, forward, move, delete, flags (all himalaya wrappers)
7. **Add templating**: Jinja2 rendering before send
8. **Add recipient groups**: `@team` resolution from config
9. **Add batch sending**: Individual mode (mail merge from CSV/YAML) + BCC mode, rate limiting, progress reporting, failure logging
10. **Add domain verification**: SPF/DMARC DNS checks
11. **Remove stdlib deps**: No more `smtplib`, `imaplib`, `email` imports
