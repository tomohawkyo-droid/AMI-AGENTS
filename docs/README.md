# Documentation Index

All documents use a standard header: **Date**, **Status** (DRAFT / ACTIVE / DEPRECATED), **Type** (Specification / Requirements / Architecture / Audit / Guide).

Status meanings:
- **ACTIVE** — describes current, implemented state
- **DRAFT** — planned/aspirational work, not yet fully implemented (implementation status notes in each doc clarify what exists)
- **DEPRECATED** — superseded or code has moved

---

## Architecture

| Document | Status | Description |
|----------|--------|-------------|
| [ARCH-AGENT-ECOSYSTEM.md](ARCH-AGENT-ECOSYSTEM.md) | DRAFT | Target architecture: containers, gateway, A2A. Currently: host-only agents, no containers/gateway. |

## Requirements

| Document | Status | Description |
|----------|--------|-------------|
| [REQ-IAM.md](requirements/REQ-IAM.md) | DRAFT | Identity, access, and secrets management (FR-1 through FR-14) |
| [REQ-BACKUP.md](requirements/REQ-BACKUP.md) | ACTIVE | Backup and sync system (REQ-BAK-001 through REQ-BAK-062). GDrive implemented, rsync planned. |
| [REQ-HOOKS.md](requirements/REQ-HOOKS.md) | ACTIVE | Hook validation pipeline (REQ-HOOK-001 through REQ-HOOK-010) |
| [REQ-MAIL.md](requirements/REQ-MAIL.md) | ACTIVE | Enterprise mail extension (REQ-MAIL-001 through REQ-MAIL-091) |
| [REQ-AGENT-CONTAINERS.md](requirements/REQ-AGENT-CONTAINERS.md) | DRAFT | Containerised agent isolation. Podman bootstrapped, agent containers not yet built. |

## Specifications

### IAM Suite (DRAFT)

| Document | Status | Description |
|----------|--------|-------------|
| [SPEC-IAM.md](specifications/SPEC-IAM.md) | DRAFT | IAM index — links to all 4 domain specs below |
| [SPEC-AUTHENTICATION.md](specifications/SPEC-AUTHENTICATION.md) | DRAFT | Keycloak 26.2 realm config, OIDC flows, IdPs, MFA. BFF pattern + JWT validation implemented. |
| [SPEC-AUTHORIZATION.md](specifications/SPEC-AUTHORIZATION.md) | DRAFT | 74-permission RBAC registry. Not yet implemented — current auth is JWT-only, no route-level checks. |
| [SPEC-SECRETS.md](specifications/SPEC-SECRETS.md) | DRAFT | OpenBao 2.4.4 config, KV v2, namespaces, PKI, transit. OpenBao deployed in dev mode. |
| [SPEC-OPERATIONS.md](specifications/SPEC-OPERATIONS.md) | DRAFT | Bootstrap automation blueprint. Not yet automated — OpenBao in dev mode, no init/unseal scripts. |

### Auth Migration (DRAFT)

| Document | Status | Description |
|----------|--------|-------------|
| [SPEC-AUTH-OIDC-PROVIDER.md](specifications/SPEC-AUTH-OIDC-PROVIDER.md) | DRAFT | Unified OIDC provider design (consolidates 6 auth systems) |
| [SPEC-AUTH-BASE-MIGRATION.md](specifications/SPEC-AUTH-BASE-MIGRATION.md) | DRAFT | Code migration from base/opsec to AMI-AUTH |
| [SPEC-AUTH-CONSUMER-MIGRATION.md](specifications/SPEC-AUTH-CONSUMER-MIGRATION.md) | DRAFT | Portal/Trading/Matrix migration to OIDC provider |

### Implemented Specs

| Document | Status | Description |
|----------|--------|-------------|
| [SPEC-HOOKS.md](specifications/SPEC-HOOKS.md) | ACTIVE | Hook validation pipeline v4.0.0. Phase 1 complete (4 validators, tiered commands). Phase 2 (LLM-based) planned. |
| [SPEC-BACKUP.md](specifications/SPEC-BACKUP.md) | DRAFT | Backup system. GDrive mode (tar.zst + upload) implemented. Rsync snapshots and multi-target planned. |
| [SPEC-PLAYWRIGHT.md](specifications/SPEC-PLAYWRIGHT.md) | DRAFT | Playwright browser automation. Basic scripts work. Security layer (policy engine, audit) not implemented. |
| [SPEC-PLAYWRIGHT-SUMMARY.md](specifications/SPEC-PLAYWRIGHT-SUMMARY.md) | DRAFT | Playwright integration overview |

### Deprecated

| Document | Status | Description |
|----------|--------|-------------|
| [SPEC-DATAOPS-FOUNDATION.md](specifications/SPEC-DATAOPS-FOUNDATION.md) | DEPRECATED | Polyglot persistence framework — code migrated to `projects/AMI-DATAOPS/` |

## Guides

| Document | Status | Description |
|----------|--------|-------------|
| [GUIDE-USAGE.md](GUIDE-USAGE.md) | ACTIVE | Getting started, installation, configuration overview |

## Audits

| Document | Status | Description |
|----------|--------|-------------|
| [AUDIT-INSTALL-ISSUES.md](AUDIT-INSTALL-ISSUES.md) | ACTIVE | Bootstrap/install issues: 8/10 fixed, 2 partially fixed |

## Archive

Historical documents retained for reference:

| Document | Description |
|----------|-------------|
| [AUTH-FRAGMENTATION-AUDIT.md](archive/AUTH-FRAGMENTATION-AUDIT.md) | Audit of 6 fragmented auth systems (prerequisite for OIDC spec) |
| [AUDIT-REMEDIATION-2026-Q1.md](archive/AUDIT-REMEDIATION-2026-Q1.md) | Q1 2026 architectural debt audit and remediation cycle |
