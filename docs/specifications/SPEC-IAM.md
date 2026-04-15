# AMI Identity, Access & Secrets Management: Technical Specification

**Date:** 2026-03-01
**Updated:** 2026-04-13
**Status:** ACTIVE
**Type:** Specification
**Companion:** [REQ-IAM.md](../requirements/REQ-IAM.md)
**Scope:** Cross-project IAM unification (AMI-PORTAL, AMI-TRADING, AMI-STREAMS, Orchestrator)

---

## Implementation Status (2026-04-13)

### Deployed

| Component | Status | Details |
|-----------|--------|---------|
| **Keycloak** | DEPLOYED | v26.2 (DATAOPS compose, updated from 26.1). v26.2 in TRADING compose (independent instance — must migrate to DATAOPS per FR-15). Realm `ami`. Brute force on, registration off. |
| **`ami-kcadm`** | DEPLOYED | CLI wrapper (`ami/scripts/bin/ami-kcadm`) executes `kcadm.sh` inside `ami-keycloak` container |
| **NextAuth** | DEPLOYED | v5.0.0-beta.30 in AMI-PORTAL. Keycloak OIDC + guest credentials provider. JWT sessions. |
| **Keycloak Admin API** | DEPLOYED | `keycloak-admin.ts` (378 lines) in PORTAL — full CRUD for users, roles, clients, sessions |
| **Account Manager UI** | DEPLOYED | 11 API routes under `/api/account-manager/` — users, roles, clients, sessions, passwords, providers |
| **RBAC (basic)** | DEPLOYED | 4 roles (admin/editor/viewer/guest), 8 permissions in `permissions.ts`, `resolvePermissions()` + `hasPermission()` |
| **Bootstrap script** | DEPLOYED | `projects/AMI-PORTAL/scripts/bootstrap-keycloak.sh` — converts client to confidential, enables service accounts, assigns realm-management roles |
| **OpenBao** | DEPLOYED (dev) | v2.4.4 in DATAOPS compose, `-dev` flag, hardcoded root token. No production config, no JWT auth, no policies. |
| **Vaultwarden** | DEPLOYED | v1.35.4 in DATAOPS compose, signups disabled |
| **PostgreSQL** | DEPLOYED | Keycloak DB backend via `config/postgres-init/01-keycloak.sql` |
| **Ansible provisioning** | DEPLOYED | DATAOPS `res/ansible/compose.yml` auto-provisions realm + `ami-portal` OIDC client |
| **AMI-TRADING auth** | DEPLOYED | BFF pattern with ROPC grant (deprecated — must migrate to Auth Code + PKCE per FR-16), RS256 JWKS validation |

### Not Built

| Requirement | Priority | Notes |
|-------------|----------|-------|
| OpenBao JWT auth (Keycloak→OpenBao) | ASAP | Dev mode only, no JWT auth method configured |
| OpenBao policies / namespaces | ASAP | No `config.hcl`, no policies committed |
| Per-user secret vaults (FR-12) | ASAP | No identity-templated policies |
| Team/group secrets (FR-13) | ASAP | No external group mappings |
| Portal Secrets UI (FR-14) | ASAP | Zero OpenBao references in PORTAL code |
| AppRole for services (FR-10) | ASAP | Services use `.env` files |
| `.env` → OpenBao migration | ASAP | Everything still in `.env` |
| Full permission registry (74 perms) | DISCUSSION | Only 8 permissions exist; requires design discussion |
| Organization/tenant scoping (FR-5.5) | FUTURE | Multi-tenancy — real requirement but not immediate |
| Service identity hierarchy (FR-5.4) | DISCUSSION | Aspirational, needs prioritization |
| Multi-IdP (FR-3, 11 providers) | FUTURE | Only Keycloak direct + guest currently |
| MFA enforcement (FR-7) | FUTURE | Not configured in Keycloak realm |
| Backchannel logout (FR-1.3/1.4) | FUTURE | Missing Portal endpoint |
| Monitoring/alerting (NFR-6) | FUTURE | Not built |
| Multi-client provisioning (FR-15.4) | TODO | DATAOPS Ansible only provisions `ami-portal` client |
| `make bootstrap-iam` (FR-17.3) | TODO | No unified IAM bootstrap target |
| PORTAL `.env.example` (FR-17.5) | TODO | `.env.local` exists (gitignored, runtime) but no tracked template |

### Known Issues

1. **Duplicated Keycloak infrastructure**: TRADING maintains its own Keycloak + keycloak-db + `ami-realm.json` in docker-compose instead of depending on DATAOPS. Must migrate per FR-15.
2. **AMI-TRADING uses ROPC grant**: `directAccessGrantsEnabled: true` on `ami-trading` client, `grant_type: "password"` in `src/delivery/api/auth.py`. Deprecated in OAuth 2.1. Must migrate per FR-16.
3. **Bootstrap script duplication**: PORTAL `bootstrap-keycloak.sh` and DATAOPS Ansible provisioning both configure Keycloak clients. Should be consolidated per FR-17.2.

## Overview

This specification is split into four domain-specific documents. Each translates the corresponding requirements from REQ-IAM.md into concrete technical implementation: exact product versions, configuration schemas, API contracts, data models, wire formats, and operational procedures.

| Document | Covers | Requirements |
|----------|--------|-------------|
| [SPEC-AUTHENTICATION.md](SPEC-AUTHENTICATION.md) | Keycloak realm configuration, OIDC flows, client integration, SSO, session management, IdPs, MFA, brute force, password policy | FR-1 through FR-9, NFR-2 |
| [SPEC-AUTHORIZATION.md](SPEC-AUTHORIZATION.md) | Permission registry, role hierarchy, RBAC guards, escalation controls, multi-tenancy scoping, API route matrix | FR-5, FR-4 |
| [SPEC-SECRETS.md](SPEC-SECRETS.md) | OpenBao server config, KV v2 layout, namespaces, auth methods, policies, PKI, transit, secrets UI API contract, dynamic credentials | FR-10 through FR-14, NFR-1 |
| [SPEC-OPERATIONS.md](SPEC-OPERATIONS.md) | Bootstrap automation, migration plan, backup/restore, key rotation, monitoring/alerting, audit, emergency access, compliance traceability | NFR-3 through NFR-7, Section 6-9 |

## Conventions

- **MUST**, **SHOULD**, **MAY** per RFC 2119
- Configuration examples use actual deployment values where known; placeholders use `<angle-brackets>`
- HCL blocks are OpenBao policy syntax
- JSON blocks are Keycloak realm export format
- All ports, paths, and addresses reflect the current network topology (LAN: `localhost`)

## Product Versions

| Component | Version | Source |
|-----------|---------|--------|
| Keycloak | 26.2 | `quay.io/keycloak/keycloak:26.2` |
| OpenBao | 2.4.4 | `openbao/openbao:2.4.4` |
| PostgreSQL (Keycloak backend) | 17-alpine | `postgres:17-alpine` |
| NextAuth (Auth.js) | 5.0.0-beta.29 | `next-auth@5.0.0-beta.29` |
| Next.js | 16 | Portal runtime |
| Node.js | 22 LTS | Portal runtime |

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │         Management Network          │
                         │  (admin consoles, bootstrap CLI)    │
                         └───────────┬─────────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
          v                          v                          v
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    Keycloak       │    │    OpenBao        │    │   PostgreSQL     │
│  :8082 (HTTP)     │    │  :8200 (API)      │    │  :5432 (KC DB)   │
│  Realm: ami       │    │  Storage: Raft    │    │  DB: keycloak    │
└────────┬──────────┘    └────────┬──────────┘    └──────────────────┘
         │                        │
         │   OIDC / Admin API     │   JWT Auth / AppRole
         │                        │
┌────────┴────────────────────────┴───────────────────────────────┐
│                      Application Network                        │
│  AMI-PORTAL :3000 │ AMI-TRADING :8080 │ AMI-STREAMS (Matrix)   │
│  Orchestrator     │ CI/CD             │ Cron/Backup            │
└─────────────────────────────────────────────────────────────────┘
```

## Trust Boundaries

| Zone | Contains | Receives |
|------|----------|----------|
| **Identity Infrastructure** | Keycloak, PostgreSQL, OpenBao | Trust anchors: realm signing keys, seal keys |
| **Application Backends** | Portal, Trading, Streams, Orchestrator | Signed JWTs, opaque OpenBao tokens (server-side only) |
| **End Users (Untrusted)** | Browsers, mobile clients | Encrypted session cookies only; no tokens, no secrets |
