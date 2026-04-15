# Requirements: Enterprise Mail Extension (`ami-mail`)

**Status:** MOVED
**Moved to:** `projects/AMI-STREAMS/docs/REQ-MAIL.md`

ami-mail is now built as a himalaya fork in the AMI-STREAMS project. Requirements and specifications live there.

---

## Background

The current `ami-mail` CLI supports basic SMTP send, IMAP fetch, and send-block (human-in-the-loop). It lacks multi-account configuration, secrets management, templating, and full IMAP operations. The server already runs an exim relay (port 2525/2526, relaying through Gmail) and Postmoogle (email-to-Matrix bridge, separate concern — not part of ami-mail).

**Architecture decision:** ami-mail wraps himalaya (Rust CLI) as backend, same pattern as ami-docs wrapping pandoc.

---

## Core Requirements

### 1. Multi-Account Configuration

- **REQ-MAIL-001**: System shall support named mail accounts with per-account IMAP and SMTP configuration
- **REQ-MAIL-002**: System shall support a default account used when no account is specified
- **REQ-MAIL-003**: Account configuration shall be defined in `ami/config/mail.yaml` (gitignored; template tracked)
- **REQ-MAIL-004**: System shall support send-only accounts (SMTP only, no IMAP)
- **REQ-MAIL-005**: System shall support multiple SMTP backends per account (exim relay, Gmail, O365, SES, etc.)

### 2. Secrets Management

- **REQ-MAIL-010**: IMAP/SMTP credentials shall be fetched from OpenBao at runtime via shell commands. (Depends on REQ-IAM OpenBao integration; until then, credentials via config file or env vars.)
- **REQ-MAIL-011**: Account config shall reference secret paths, not store credentials inline
- **REQ-MAIL-012**: Secret retrieval shall use himalaya's native `auth.command` field for credential lookup at runtime

### 3. Email Sending

- **REQ-MAIL-020**: System shall send plain text and HTML emails
- **REQ-MAIL-021**: System shall support file attachments (multiple per message)
- **REQ-MAIL-022**: System shall support named recipient targets (e.g., `@team` resolving to a list of addresses)
- **REQ-MAIL-023**: System shall support Jinja2 template rendering for email body from template file + data file (YAML/JSON)
- **REQ-MAIL-024**: System shall support dry-run mode (render and display without sending)
- **REQ-MAIL-025**: System shall support subject line variable interpolation
- **REQ-MAIL-026**: System shall support CC and BCC recipient fields
- **REQ-MAIL-027**: System shall support BCC for group sends (send to `@team` without exposing individual addresses)

### 3a. Batch Sending & Personalization

- **REQ-MAIL-100**: System shall support batch sending to a recipient list (file, group, or inline)
- **REQ-MAIL-101**: System shall support per-recipient personalization — each recipient receives an individually rendered message with their own template variables (mail merge)
- **REQ-MAIL-102**: Recipient data shall be loadable from CSV or YAML/JSON files, where each row/entry provides per-recipient template variables
- **REQ-MAIL-103**: System shall support configurable rate limiting for batch sends (max messages per second/minute, configurable delay between sends)
- **REQ-MAIL-104**: System shall report batch progress (sent/total, failures) during execution
- **REQ-MAIL-105**: System shall log each send result (recipient, status, error) for audit
- **REQ-MAIL-106**: Failed sends in a batch shall not abort the remaining batch — failures are logged and reported at the end
- **REQ-MAIL-107**: System shall support `--dry-run` for batch sends — render all messages, report what would be sent, send nothing
- **REQ-MAIL-108**: Batch sends shall support BCC mode (single message to all recipients) or individual mode (one message per recipient with personalization)

### 4. Email Reading

- **REQ-MAIL-030**: System shall list email envelopes (sender, subject, date) from any IMAP folder
- **REQ-MAIL-031**: System shall display full email message content
- **REQ-MAIL-032**: System shall search emails by sender, subject, date range, and flags
- **REQ-MAIL-033**: System shall list available IMAP folders

### 5. Email Operations

- **REQ-MAIL-040**: System shall reply to messages (with optional template)
- **REQ-MAIL-041**: System shall forward messages to specified recipients
- **REQ-MAIL-042**: System shall move messages between folders
- **REQ-MAIL-043**: System shall delete messages
- **REQ-MAIL-044**: System shall set/remove flags (read, starred, answered, custom)

### 6. Send-Block (Human-in-the-Loop)

This is a core agent automation capability: an agent sends an email asking a human a question, waits for their reply, then continues its workflow. Current implementation uses subject matching; must migrate to proper threading.

- **REQ-MAIL-050**: System shall support send-and-wait: send an email, then poll IMAP for a reply
- **REQ-MAIL-051**: Reply matching shall use Message-ID/In-Reply-To threading (not subject matching)
- **REQ-MAIL-052**: System shall support configurable timeout and poll interval
- **REQ-MAIL-053**: System shall output the reply content in structured format (JSON when requested)

### 7. Template System

- **REQ-MAIL-060**: System shall support shared Jinja2 templates in `ami/config/mail/templates/`
- **REQ-MAIL-061**: System shall support per-project template directories (configurable in mail.yaml)
- **REQ-MAIL-062**: Templates shall receive: subject, date, and arbitrary data from a YAML/JSON data file
- **REQ-MAIL-063**: PDF generation for attachments shall be delegated to ami-docs (pandoc wrapper, already bootstrapped)

### 8. Output and Scripting

- **REQ-MAIL-070**: All read operations shall support JSON output mode
- **REQ-MAIL-071**: All operations shall be non-interactive (no TUI, no pager, no $EDITOR prompts)
- **REQ-MAIL-072**: Exit codes shall distinguish success (0), user error (1), and system error (2)

### 9. Infrastructure

- **REQ-MAIL-080**: himalaya shall be bootstrapped to `.boot-linux/bin/` following the established component pattern (GitHub releases binary, like pandoc)
- **REQ-MAIL-081**: ami-mail shall generate himalaya TOML configuration from the mail config YAML
- **REQ-MAIL-082**: Configuration generation shall translate secret references to himalaya `auth.command` fields
- **REQ-MAIL-083**: System shall operate without local mail storage (direct IMAP, no Maildir/sync)
- **REQ-MAIL-084**: System shall support the existing exim relay as an SMTP backend (default for local sending)

### 10. Domain Verification

- **REQ-MAIL-090**: System shall validate SPF and DMARC DNS records for a given domain
- **REQ-MAIL-091**: Validation results shall indicate pass/fail with details

---

## Constraints

- Python 3.11+
- himalaya invoked as subprocess (same pattern as ami-docs/pandoc)
- Jinja2 for templating
- No LLM SDK dependencies
- Non-interactive — all operations scriptable

## Dependencies

### Internal
- ami-docs (PDF generation via pandoc)
- Bootstrap system (himalaya component)
- REQ-IAM (OpenBao for credentials — interim: config file / env vars)

### External
- himalaya (Rust CLI, bootstrapped binary)
- Jinja2 (Python)
- Exim relay (existing SMTP infrastructure)

## Non-Requirements (Explicitly Out of Scope)

- **Local mail storage** — no Maildir, no mbsync, no notmuch sync
- **Interactive TUI** — use himalaya directly for interactive use
- **Postmoogle integration** — Postmoogle is a Matrix-internal email bridge for Matrix's own needs (deployed via AMI-STREAMS). Not related to ami-mail.
- **PGP/S/MIME encryption** — deferred to future phase
- **Bounce handling** — deferred to future phase
- **Mail queue/retry** — deferred to future phase
- **OAuth2 IMAP auth** — himalaya supports it natively; no AMI-specific wrapper needed
