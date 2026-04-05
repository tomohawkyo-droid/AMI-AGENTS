# Workflow: Research Requirements

**Purpose:** Standard process for researching requirements before building or extending any AMI extension or feature. This is the generic workflow — feature-specific research documents go in `docs/REQUIREMENTS-*.md`.

---

## Phase 1: Audit Existing State

Before designing anything, map what already exists across all layers.

### 1.1 Codebase Scan

Find ALL code, config, scripts, ansible roles, docker-compose services, and CLI tools related to the feature area. Search across:

| Location | What lives there |
|----------|-----------------|
| `ami/scripts/bin/` | CLI tools (Python + Bash) |
| `ami/config/` | Configuration files (extensions.yaml, hooks.yaml, automation.yaml, policies/) |
| `ami/config/extensions.yaml` | Registered CLI extensions (single source of truth for banner + `.boot-linux/bin/`) |
| `projects/*/` | Project-specific implementations — **often contain prototypes** that already solve part of the problem |
| `projects/AMI-STREAMS/ansible/` | Infrastructure-as-code — deployed services, roles, playbooks |
| `docs/` and `docs/specifications/` | Specs, architecture docs, requirement docs |
| `.boot-linux/bin/` | Bootstrapped binaries (134+ executables) |
| `ami/scripts/bootstrap/` | Bootstrap scripts that install tools |
| `ami/scripts/bootstrap_component_defs.py` | Component definitions for the bootstrap installer |

### 1.2 Infrastructure Scan

Identify deployed services that are already running and relevant:
- Docker/Podman containers (`podman ps`, docker-compose files)
- Systemd units (ansible-managed services)
- Ansible roles and playbooks (especially in `projects/AMI-STREAMS/ansible/`)
- Network services (ports, listeners, relays)

### 1.3 Prototype Scan

Check `projects/*/` for project-specific implementations that already solve part of the problem. These are often the best starting point — they show **real usage patterns** under production conditions.

Look for:
- Scripts that do the thing manually
- Config files that define the workflow
- Templates that can be generalized
- Integration patterns that work

### 1.4 Integration Points

Map how the feature connects to existing AMI systems:

| System | What it provides |
|--------|-----------------|
| **OpenBao** | Secrets — KV v2 at `platform/secrets/service/` and `platform/secrets/infra/` |
| **Keycloak** | Auth/identity — JWT auth, OIDC, OAuth2 |
| **ami-cron** | Scheduled automation — AMI-tagged crontab entries |
| **ami-docs** | Document generation — pandoc, wkhtmltopdf, pdflatex, etc. |
| **Ansible** | Infrastructure provisioning — playbooks in AMI-STREAMS |
| **Docker/Podman** | Containerized services |
| **Exim relay** | SMTP relay to external providers (port 2525/2526) |
| **Postmoogle** | Email↔Matrix bridge |
| **Matrix (Synapse)** | Messaging, notifications |

---

## Phase 2: External Research

### 2.1 Web Research

Search for:
- Best-in-class CLI tools in the domain
- Python libraries (prefer stdlib, then well-maintained packages with minimal deps)
- Rust/Go CLI tools that can be bootstrapped as single binaries
- Architecture patterns from similar projects
- Security considerations (auth, encryption, compliance)

### 2.2 Evaluate Candidates

Evaluate against AMI constraints:

| Constraint | Question |
|------------|----------|
| **Bootstrappable** | Can it be downloaded as a binary and installed to `.boot-linux/bin/`? |
| **Offline-capable** | Does it work on internal networks without internet? |
| **Dependency footprint** | How many deps does it pull in? Prefer minimal. |
| **AMI patterns** | Does it integrate with YAML config, OpenBao secrets, Jinja2 templates? |
| **JSON output** | Does it support `--output json` for scripting? |
| **Multi-account** | Does it support multiple configurations/accounts natively? |
| **Maturity** | Stars, version, maintenance activity, known issues? |

### 2.3 Architecture Options

Always consider at least:
- **Option A: Pure Python** — extend existing code, no new binary deps
- **Option B: External tool as backend** — bootstrap a CLI tool, wrap with Python for AMI integration (like ami-docs wraps pandoc)
- **Option C: Hybrid** — split responsibilities between Python and external tool

The ami-docs pattern (thin Python wrapper → external tool passthrough) is the established AMI pattern for tool integration.

---

## Phase 3: Gap Analysis

Compare what exists vs what's needed. Categorize every requirement:

| Status | Meaning | Action |
|--------|---------|--------|
| **Solved** | Already works in codebase | Wire it up, don't rebuild |
| **Prototype** | Solved in a project, needs generalization | Extract and generalize the pattern |
| **Tool exists** | External tool does it, needs bootstrapping + wrapper | Bootstrap + thin wrapper |
| **Must build** | No existing solution | New code required |

---

## Phase 4: Interactive Q&A

Ask the user targeted questions to resolve ambiguity. Run multiple rounds if needed. Focus on:

- **Scope boundaries** — What's in, what's out
- **Architecture** — Pure Python vs external tools, thin wrapper vs full abstraction
- **Priority** — What ships first
- **Integration depth** — Shallow CLI wrapper vs deep platform integration
- **Credential management** — How do secrets flow
- **Interactive vs scripted** — TUI vs CLI-only vs both

**Rules:**
- Ask 3-4 questions per round max
- Provide concrete options with previews (CLI examples, config snippets)
- Don't ask about things you can determine from the codebase
- After each round, record decisions in the requirements doc before asking more

---

## Phase 5: Design Decisions + Architecture

After Q&A rounds are complete:

1. **Decisions table** — Record every decision with the choice and rationale
2. **Architecture diagram** — Show how components connect (ASCII is fine)
3. **Config model** — Show the YAML/TOML config schema with real examples
4. **Command surface** — List every CLI command with usage examples
5. **Bootstrap plan** — If adding external tools, document the exact bootstrap pattern

---

## Phase 6: Implementation Plan

Break into ordered phases with:
- **File paths** — every file to create or modify
- **Dependencies** — which phases depend on which
- **Verification** — how to test each phase independently
- **Migration** — how existing code/config transitions to the new design

---

## Output

The final output of this workflow is a `docs/REQUIREMENTS-<FEATURE>.md` document containing:
- Existing state audit
- Gap analysis
- External research findings
- All design decisions (with rationale)
- Proposed architecture
- Implementation plan with verification steps

This document becomes the specification for implementation.
