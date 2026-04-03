# AMI Identity, Access & Secrets Management — Technical Specification

**Date:** 2026-03-01
**Status:** DRAFT
**Companion:** [REQUIREMENTS-IAM.md](REQUIREMENTS-IAM.md)
**Scope:** Cross-project IAM unification (AMI-PORTAL, AMI-TRADING, AMI-STREAMS, Orchestrator)

---

## Overview

This specification is split into four domain-specific documents. Each translates the corresponding requirements from REQUIREMENTS-IAM.md into concrete technical implementation: exact product versions, configuration schemas, API contracts, data models, wire formats, and operational procedures.

| Document | Covers | Requirements |
|----------|--------|-------------|
| [SPECIFICATION-AUTHENTICATION.md](SPECIFICATION-AUTHENTICATION.md) | Keycloak realm configuration, OIDC flows, client integration, SSO, session management, IdPs, MFA, brute force, password policy | FR-1 through FR-9, NFR-2 |
| [SPECIFICATION-AUTHORIZATION.md](SPECIFICATION-AUTHORIZATION.md) | Permission registry, role hierarchy, RBAC guards, escalation controls, multi-tenancy scoping, API route matrix | FR-5, FR-4 |
| [SPECIFICATION-SECRETS.md](SPECIFICATION-SECRETS.md) | OpenBao server config, KV v2 layout, namespaces, auth methods, policies, PKI, transit, secrets UI API contract, dynamic credentials | FR-10 through FR-14, NFR-1 |
| [SPECIFICATION-OPERATIONS.md](SPECIFICATION-OPERATIONS.md) | Bootstrap automation, migration plan, backup/restore, key rotation, monitoring/alerting, audit, emergency access, compliance traceability | NFR-3 through NFR-7, Section 6-9 |

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
