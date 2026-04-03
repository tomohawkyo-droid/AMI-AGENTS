# AMI Identity, Access & Secrets Management — Requirements

**Date:** 2026-03-01
**Status:** DRAFT
**Scope:** Cross-project IAM unification (AMI-PORTAL, AMI-TRADING, AMI-STREAMS, Orchestrator)

---

## 1. Problem Statement

The AMI ecosystem has **6 independent auth systems** across its services (see [AUTH-FRAGMENTATION-AUDIT.md](AUTH-FRAGMENTATION-AUDIT.md)). Zero shared identity, zero SSO, zero token interoperability. Secrets are scattered across `.env` files, Ansible vaults, Docker Compose, and pickle files. A comprehensive auth framework exists in `base/backend/opsec/` (~4,700 lines) and is unused.

The goal is to consolidate into a single IAM stack that provides:

1. **Centralised Account & Login Management** — one identity, one login, all applications
2. **Credentials Storage & Retrieval** — service accounts and unattended access
3. **Secrets Management** — per-user, per-team, and per-service secret storage

---

## 2. Stack

| Component | Role | Deployed At |
|-----------|------|-------------|
| **Keycloak** | Identity Provider — SSO, user management, identity brokering, RBAC | `localhost:8082` |
| **OpenBao** | Secrets Engine — KV secrets, dynamic credentials, transit encryption, PKI | TBD |
| **AMI-PORTAL** | Unified UI — account management, admin panels, secrets browser | `localhost:3000` |

### 2.1 What Keycloak Owns

- Authentication (SSO via OIDC/SAML)
- User lifecycle (create, disable, delete, password reset, MFA enrollment)
- Identity brokering (social + enterprise IdPs)
- Group and role management (realm roles, client roles, composite roles)
- Service account tokens (OAuth 2.0 client credentials grant)
- Session management (active sessions, idle/max timeouts, forced logout, backchannel logout)
- Authorization policies (RBAC, ABAC via built-in policy engine)
- Brute force detection and account lockout
- Password policies (length, blocklist, history)
- Admin and login event logging

### 2.2 What Keycloak Does NOT Own

- Arbitrary secret storage (API keys, database passwords, encryption keys)
- API key generation or rotation
- Certificate issuance
- Credential vaulting for third-party services

### 2.3 What OpenBao Owns

- Secret storage (KV v2 — versioned, soft-delete, metadata)
- Dynamic credential generation (database, cloud, SSH)
- Encryption as a service (transit engine)
- PKI / certificate authority
- SSH certificate signing
- Per-user secret namespaces (identity-templated policies)
- Per-team/group shared secrets
- Service credential storage and rotation
- Lease management (TTL, renewal, revocation)
- Audit logging of all secret access

### 2.4 How They Integrate

- Keycloak is the OIDC provider for OpenBao (JWT auth method)
- Keycloak groups/roles map to OpenBao policies via external identity groups
- Users authenticate once via Keycloak; portal presents the Keycloak JWT to OpenBao's JWT auth method server-side to obtain a scoped OpenBao token
- Service accounts authenticate to OpenBao via AppRole (machine identity) or JWT (Keycloak service account token)
- Keycloak token claims (`groups`, `realm_access.roles`) drive OpenBao policy resolution — claim mappers in Keycloak MUST be configured to emit these

---

## 3. Functional Requirements

### 3.1 Centralised Account & Login Management

#### FR-1: Single Sign-On (SSO)

| ID | Requirement |
|----|-------------|
| FR-1.1 | All AMI applications (Portal, Trading, Streams) MUST authenticate against Keycloak as the sole OIDC provider |
| FR-1.2 | A user authenticated in one application MUST NOT be prompted to log in again when accessing another (redirect-based OIDC flow — Keycloak session cookie on Keycloak's domain enables seamless re-auth, NOT cross-domain cookie sharing) |
| FR-1.3 | Logout from any application MUST terminate the Keycloak session via OIDC Back-Channel Logout |
| FR-1.4 | Each application MUST register a backchannel logout URL with Keycloak and handle logout tokens to invalidate local sessions |
| FR-1.5 | SSO works via redirect-based OIDC flows — each service independently validates tokens with Keycloak; cross-domain SSO does NOT rely on shared cookies |

#### FR-2: Session Management

| ID | Requirement |
|----|-------------|
| FR-2.1 | Keycloak SSO session idle timeout MUST be configured (default: 30 minutes) |
| FR-2.2 | Keycloak SSO session max lifetime MUST be configured (default: 10 hours) |
| FR-2.3 | Concurrent session limit MUST be enforced (configurable per realm, default: 5 sessions per user) |
| FR-2.4 | Users MUST be able to view and revoke their own active sessions via Keycloak's account console |
| FR-2.5 | Admins MUST be able to view and terminate any user's sessions via the portal UI |
| FR-2.6 | Sessions MUST be bound to the authentication context (re-authentication required on role elevation) |

#### FR-3: Identity Providers

| ID | Requirement |
|----|-------------|
| FR-3.1 | The bootstrap process MUST configure all supported social IdPs in the Keycloak realm |
| FR-3.2 | Supported IdPs: Google, GitHub, Microsoft, GitLab, Bitbucket, Discord, Slack, LinkedIn, Apple, Facebook, Twitter/X |
| FR-3.3 | Each IdP MUST be configurable via environment variables (`KC_IDP_<PROVIDER>_CLIENT_ID`, `KC_IDP_<PROVIDER>_CLIENT_SECRET`) |
| FR-3.4 | IdPs with credentials configured MUST be enabled; IdPs without credentials MUST be created but disabled |
| FR-3.5 | The portal's Add Account dialog MUST dynamically discover and display all enabled IdPs from Keycloak |
| FR-3.6 | Generic OIDC and SAML brokers MUST be supported for enterprise federation |
| FR-3.7 | LDAP/AD user federation SHOULD be documented as a future extension point |

#### FR-4: User Management

| ID | Requirement |
|----|-------------|
| FR-4.1 | Admins MUST be able to create, edit, disable, and delete users via the portal UI |
| FR-4.2 | Admins MUST be able to assign realm roles and group memberships via the portal UI |
| FR-4.3 | Admins MUST be able to force password resets and terminate active sessions |
| FR-4.4 | Users MUST be able to manage their own profile (name, email, password, MFA) via Keycloak's account console or a portal-embedded equivalent |
| FR-4.5 | User provisioning MUST trigger corresponding entity creation in OpenBao (for secret namespace) |
| FR-4.6 | User deprovisioning MUST revoke all OpenBao tokens and optionally archive their secret namespace |

#### FR-5: Roles, Permissions & Actor Hierarchy

##### FR-5.1 Permission Format

All permissions use the `resource:action` format. This maps cleanly to Keycloak Authorization Services (resource + scope), OpenBao policies (path + capability), and the portal's `withPermission()` guard.

##### FR-5.2 Atomic Permission Registry

**User Management**

| Permission | Description |
|---|---|
| `users:list` | List/search users within scope |
| `users:read` | View user profile details |
| `users:create` | Create new user accounts |
| `users:update` | Modify user profiles (email, name, metadata) |
| `users:delete` | Deactivate or permanently remove users |
| `users:assign-roles` | Assign/revoke roles on users |
| `users:assign-groups` | Add/remove users from groups |
| `users:reset-credentials` | Reset passwords, clear OTP |
| `users:terminate-sessions` | Force-logout, revoke active sessions |
| `users:impersonate` | Impersonate a user for debugging |

**Client / Service Account Management**

| Permission | Description |
|---|---|
| `clients:list` | List registered clients (service accounts) |
| `clients:read` | View client configuration |
| `clients:create` | Register new clients / service accounts |
| `clients:update` | Modify client settings (redirect URIs, scopes) |
| `clients:delete` | Remove clients |
| `clients:rotate-secret` | Regenerate client secrets |
| `clients:manage-roles` | Create/delete client-scoped roles |
| `clients:view-service-account` | View the service account user of a client |

**Identity Provider Configuration**

| Permission | Description |
|---|---|
| `idp:list` | List configured identity providers |
| `idp:read` | View IdP configuration details |
| `idp:create` | Add new identity providers (SAML, OIDC, LDAP) |
| `idp:update` | Modify IdP settings (mappers, sync) |
| `idp:delete` | Remove identity providers |
| `idp:sync` | Trigger manual user sync from external IdP |

**Platform / Realm Configuration**

| Permission | Description |
|---|---|
| `config:read` | View platform settings |
| `config:session-policy` | Modify session timeout, idle timeout, remember-me |
| `config:password-policy` | Set password complexity, history, expiration |
| `config:brute-force` | Configure brute force detection thresholds |
| `config:email` | Configure SMTP / email templates |
| `config:themes` | Manage login/account/admin themes |
| `config:events` | Configure event listener settings |
| `config:realm-keys` | Manage signing/encryption keys |

**Secrets Management**

| Permission | Description |
|---|---|
| `secrets:personal:read` | Read own personal secrets |
| `secrets:personal:write` | Create/update own personal secrets |
| `secrets:personal:delete` | Delete own personal secrets |
| `secrets:team:read` | Read team/group shared secrets |
| `secrets:team:write` | Create/update team shared secrets |
| `secrets:team:delete` | Delete team shared secrets |
| `secrets:service:read` | Read service/application secrets |
| `secrets:service:write` | Create/update service secrets |
| `secrets:service:delete` | Delete service secrets |
| `secrets:service:rotate` | Trigger rotation of service secrets |
| `secrets:admin:read` | Read infrastructure/admin secrets |
| `secrets:admin:write` | Create/update infrastructure secrets |
| `secrets:admin:delete` | Delete infrastructure secrets |
| `secrets:admin:mount` | Mount/unmount secrets engines |

**Audit**

| Permission | Description |
|---|---|
| `audit:read` | View audit logs |
| `audit:export` | Export audit log data |
| `audit:configure` | Configure audit log retention, destinations |

**Roles & Groups Management**

| Permission | Description |
|---|---|
| `roles:list` | List available roles |
| `roles:read` | View role definitions and permission mappings |
| `roles:create` | Create new roles |
| `roles:update` | Modify role permission mappings |
| `roles:delete` | Delete roles |
| `groups:list` | List groups |
| `groups:read` | View group details and membership |
| `groups:create` | Create groups |
| `groups:update` | Modify group attributes, sub-groups |
| `groups:delete` | Delete groups |
| `groups:manage-members` | Add/remove group members |
| `groups:manage-roles` | Assign/revoke roles on groups |

**Organization / Tenant Management**

| Permission | Description |
|---|---|
| `orgs:list` | List organizations |
| `orgs:read` | View organization details |
| `orgs:create` | Create new organizations |
| `orgs:update` | Modify organization settings, domains |
| `orgs:delete` | Delete organizations |
| `orgs:manage-members` | Invite/remove org members |
| `orgs:manage-idps` | Link/unlink identity providers to org |

**Media (Portal-Specific, Retained for Backward Compatibility)**

| Permission | Description |
|---|---|
| `media:read` | Read/view media assets |
| `media:write` | Create/update media assets |
| `media:delete` | Delete media assets |
| `media:upload` | Upload new media files |
| `media:export` | Export media assets |
| `media:serve` | Serve media assets via public URLs |

##### FR-5.3 Human Actor Hierarchy

The hierarchy has two scoping tiers: **platform** (global) and **organization** (tenant-scoped).

```
PLATFORM SCOPE                    ORG / TENANT SCOPE
─────────────────                 ──────────────────
platform-superadmin               org-admin
  │                                 │
platform-admin                    team-lead
  │                                 │
platform-operator                 developer
                                    │
                                  member
                                    │
                                  viewer
                                    │
                                  guest
```

**Platform-Scoped Roles**

| Role | Description | Key Permissions |
|---|---|---|
| `platform-superadmin` | Break-glass role. Max 2-3 humans. | All permissions. `config:realm-keys`, `audit:configure`, `secrets:admin:mount`, `orgs:create`, `orgs:delete`. |
| `platform-admin` | Day-to-day platform administration. Cannot modify realm keys. | `users:*`, `clients:*`, `idp:*`, `roles:*`, `groups:*`, `orgs:list/read/update/manage-*`, `config:*` (except `realm-keys`), `audit:read/export`, `secrets:admin:read/write`, `secrets:service:*`, `secrets:team:*`, `secrets:personal:*`, `media:*`. |
| `platform-operator` | Monitoring and triage. Read-heavy, limited write. | `users:list/read/terminate-sessions`, `clients:list/read`, `config:read`, `audit:read/export`, `secrets:service:read`, `media:read/export`. |

**Organization-Scoped Roles** (permissions implicitly scoped to user's org)

| Role | Description | Key Permissions |
|---|---|---|
| `org-admin` | Full control within own organization. | `users:*` (own org), `clients:*` (own org), `idp:*` (own org), `roles:*`, `groups:*`, `orgs:read/update/manage-*`, `config:read/session-policy/password-policy/brute-force`, `audit:read/export`, `secrets:team:*`, `secrets:service:*`, `secrets:personal:*`, `media:*`. |
| `team-lead` | Manages team access and secrets. | `users:list/read/assign-roles/assign-groups` (cannot assign admin roles), `groups:list/read/manage-members`, `roles:list/read`, `audit:read`, `secrets:team:*`, `secrets:service:read`, `secrets:personal:*`, `media:read/write/upload/export/serve`. |
| `developer` | Active contributor, needs service secret access. | `users:list/read`, `groups:list/read`, `roles:list/read`, `clients:list/read`, `secrets:service:read`, `secrets:team:read/write`, `secrets:personal:*`, `media:read/write/upload/export/serve`. |
| `member` | Standard organization member. | `users:list/read`, `groups:list/read`, `secrets:team:read`, `secrets:personal:*`, `media:read/export`. |
| `viewer` | Read-only access. | `users:list/read`, `groups:list/read`, `roles:list/read`, `config:read`, `secrets:personal:read`, `media:read/export`. |
| `guest` | Minimal access, external collaborators. | `users:read` (self only), `secrets:personal:read`, `media:read`. |

##### FR-5.4 Service Identity Hierarchy

Each service identity maps to a Keycloak confidential client with service account enabled + an OpenBao AppRole.

| Role | Scope | Key Permissions |
|---|---|---|
| `svc-platform-core` | Global | `users:list/read`, `secrets:service:read`, `secrets:admin:read` |
| `svc-platform-infra` | Global | `config:read`, `audit:read`, `secrets:admin:read/write`, `secrets:service:read/write/rotate` |
| `svc-platform-monitor` | Global | `audit:read/export`, `config:read`, `users:list`, `clients:list` |
| `svc-tenant-app` | Single org | `users:list/read` (own org), `secrets:service:read`, `secrets:team:read` |
| `svc-tenant-worker` | Single org | `secrets:service:read` |
| `svc-cicd-deployer` | Controlled | `secrets:service:read/write/rotate`, `clients:read/rotate-secret` |
| `svc-cicd-scanner` | Controlled | `audit:read`, `config:read`, `users:list`, `clients:list` |
| `svc-cicd-builder` | Controlled | `secrets:service:read` |

Naming convention for tenant service accounts: `svc-{purpose}--{org-slug}` (e.g., `svc-tenant-app--acme-corp`).

##### FR-5.5 Organization / Tenant Scoping

```
Platform (global scope)
  │
  ├── Organization: acme-corp
  │     ├── Team: backend-team
  │     ├── Team: frontend-team
  │     └── Team: ops-team
  │
  └── Organization: globex-inc
        ├── Team: engineering
        └── Team: data-science
```

Scoping rules:

| Rule | Description |
|---|---|
| Platform roles | Operate across all organizations (global scope) |
| Org roles | Scoped to exactly one organization; user may hold different roles in different orgs |
| Team membership | Further restricts which group-scoped secrets a user can access |
| Service identities | Bound to exactly one org (tenant services) or the platform (platform services), never both |
| Escalation guard | An `org-admin` CANNOT escalate to platform roles; platform roles can only be granted by `platform-superadmin` |
| Role assignment ceiling | A `team-lead` can assign roles up to `developer`, never `org-admin`. An `org-admin` can assign up to `org-admin` within their org, never platform roles |

##### FR-5.6 Permission Evaluation Model

Adopt **explicit-deny-overrides** (AWS pattern):

```
1. Collect all policies: identity-based + group-based + org-scoped
2. If ANY policy has explicit DENY → DENY
3. Compute scope: is resource within principal's org?
   - Platform role → scope = global
   - Org role → scope = principal's org
   - Resource outside scope → DENY
4. If ANY policy has ALLOW → ALLOW
5. Default → DENY
```

Inheritance: platform policies act as boundaries (like AWS SCPs) constraining what org-level policies can grant. Group/role permissions are additive within scope. Explicit deny at any level overrides.

##### FR-5.7 Least Privilege Enforcement

| ID | Requirement |
|----|-------------|
| FR-5.7.1 | New org members MUST default to `viewer`. Elevation requires `org-admin` approval |
| FR-5.7.2 | `platform-superadmin` SHOULD use JIT elevation; day-to-day work uses `platform-operator`. Break-glass access MUST be audited |
| FR-5.7.3 | Service accounts MUST use one identity per function. No shared service accounts |
| FR-5.7.4 | Service accounts MUST NOT receive human-equivalent roles (`org-admin`, `platform-admin`) |
| FR-5.7.5 | All service tokens MUST have short TTLs: Keycloak 5min, OpenBao 1h max for service secrets, 15min max for admin secrets |
| FR-5.7.6 | OpenBao AppRole SecretIDs for CI/CD MUST be single-use (Pull mode) |
| FR-5.7.7 | OpenBao AppRoles SHOULD be CIDR-bound where network topology is stable |

##### FR-5.8 Backward Compatibility

| Legacy Role | Maps To | Notes |
|---|---|---|
| `admin` | `platform-superadmin` | Wildcard permissions |
| `editor` | `developer` | `media:*` + `secrets:personal:*` |
| `viewer` | `viewer` | No change |
| `guest` | `guest` | No change |

The `resolvePermissions()` function MUST accept both legacy and new role names. Legacy roles will be deprecated after full migration.

#### FR-6: Password Policy

| ID | Requirement |
|----|-------------|
| FR-6.1 | Minimum password length: 12 characters |
| FR-6.2 | Passwords MUST be checked against a breached password list (Keycloak password policy: `notCompromised`) |
| FR-6.3 | No forced periodic rotation (per NIST 800-63B) — rotate only on suspected compromise |
| FR-6.4 | Password history: prevent reuse of last 5 passwords |
| FR-6.5 | Keycloak's password blacklist policy MUST be enabled |

#### FR-7: Multi-Factor Authentication (MFA)

| ID | Requirement |
|----|-------------|
| FR-7.1 | Keycloak MUST support TOTP (Google Authenticator, Authy) |
| FR-7.2 | Keycloak MUST support WebAuthn (hardware keys, passkeys) |
| FR-7.3 | MFA MUST be enforceable per role via Keycloak required actions (required for `admin`, optional for `viewer`) |
| FR-7.4 | Recovery/backup codes MUST be available |
| FR-7.5 | MFA enrollment MUST be prompted on first login when required by role |

#### FR-8: Brute Force Protection

| ID | Requirement |
|----|-------------|
| FR-8.1 | Keycloak brute force detection MUST be enabled on the `ami` realm |
| FR-8.2 | Max login failures before temporary lockout: 5 attempts |
| FR-8.3 | Lockout duration: 15 minutes (progressive increase on repeated lockouts) |
| FR-8.4 | Quick login check: reject logins faster than 1 per second from same IP |
| FR-8.5 | Admin notification on repeated lockout events SHOULD be configured |

### 3.2 Credentials Storage & Retrieval (Service Accounts)

#### FR-9: Keycloak Service Accounts (OAuth M2M)

| ID | Requirement |
|----|-------------|
| FR-9.1 | Each AMI service (Portal, Trading, Streams, Orchestrator) MUST have a dedicated Keycloak client with service account enabled |
| FR-9.2 | Service accounts MUST authenticate via client credentials grant (`grant_type=client_credentials`) |
| FR-9.3 | Service account client secrets MUST be stored in OpenBao, NOT in `.env` files |
| FR-9.4 | The portal Clients tab MUST allow admins to create, view, rotate secrets, and delete service account clients |
| FR-9.5 | Client secret rotation MUST be supported without downtime (Keycloak supports dual active secrets during rotation) |

#### FR-10: OpenBao Service Credentials

| ID | Requirement |
|----|-------------|
| FR-10.1 | Services MUST authenticate to OpenBao using AppRole (RoleID + SecretID) or JWT (Keycloak service account token) |
| FR-10.2 | Each service MUST have an isolated secret path: `secret/data/services/<service-name>/*` |
| FR-10.3 | Service credentials (database passwords, API keys, third-party tokens) MUST be stored in OpenBao KV v2, NOT in environment variables or files |
| FR-10.4 | Dynamic database credentials SHOULD be used where possible (PostgreSQL, MySQL, MongoDB, Redis, RabbitMQ) |
| FR-10.5 | Service secret access MUST be fully audited in OpenBao's audit log |
| FR-10.6 | Service policies MUST grant read AND write to their own namespace (services may need to store runtime-generated secrets) |
| FR-10.7 | Lease duration for dynamic credentials: default 1h, max 24h, renewable |

#### FR-11: Unattended Access

| ID | Requirement |
|----|-------------|
| FR-11.1 | CI/CD pipelines MUST authenticate to OpenBao via AppRole with CIDR-bound, single-use SecretIDs |
| FR-11.2 | Cron jobs and backup scripts MUST obtain credentials from OpenBao at runtime, NOT from `.env` files |
| FR-11.3 | Orchestrator infrastructure secrets (SSH passwords, Cloudflare tokens, Google service account keys) MUST be migrated to OpenBao |
| FR-11.4 | Initial secret introduction for services MUST use response wrapping (single-use wrapped tokens with short TTL) to deliver SecretIDs securely |
| FR-11.5 | SSH access SHOULD migrate from password-based to SSH certificate signing via OpenBao's SSH secrets engine |

### 3.3 Secrets Management (User-Facing)

#### FR-12: Personal Secret Vaults

| ID | Requirement |
|----|-------------|
| FR-12.1 | Each authenticated user MUST have an isolated secret namespace in OpenBao: `secret/data/users/<entity-id>/*` |
| FR-12.2 | Users MUST be able to create, read, update, and delete secrets in their namespace via the portal UI |
| FR-12.3 | Secret versioning MUST be supported (KV v2 — view history, rollback, soft-delete) |
| FR-12.4 | Users MUST NOT be able to access other users' secret namespaces |
| FR-12.5 | Policy enforcement MUST use identity-templated policies (no per-user policy creation) |

#### FR-13: Team/Group Secrets

| ID | Requirement |
|----|-------------|
| FR-13.1 | Keycloak groups MUST map to shared secret namespaces via OpenBao external identity groups |
| FR-13.2 | Each Keycloak group maps to an OpenBao external group with an assigned policy granting access to `secret/data/teams/<group-name>/*` |
| FR-13.3 | Group members MUST have read/write access to their team's secrets |
| FR-13.4 | Group membership changes in Keycloak MUST automatically reflect in OpenBao access (via external group alias on OIDC mount) |

#### FR-14: Portal Secrets UI

| ID | Requirement |
|----|-------------|
| FR-14.1 | The portal MUST provide a secrets browser UI (tree view of KV paths) |
| FR-14.2 | Secret values MUST be masked by default and revealed on click |
| FR-14.3 | Copy-to-clipboard MUST be supported (using Clipboard API, NOT innerHTML) |
| FR-14.4 | Version history MUST be viewable per secret |
| FR-14.5 | Admins MUST be able to browse all secret paths they have policy access to |
| FR-14.6 | Secret values MUST be treated as untrusted input — React JSX escaping handles rendering; no `dangerouslySetInnerHTML` |
| FR-14.7 | Rate limiting MUST be applied to secret read/write API routes to prevent enumeration attacks |

---

## 4. Non-Functional Requirements

#### NFR-1: Security

| ID | Requirement |
|----|-------------|
| NFR-1.1 | All inter-service communication MUST use TLS |
| NFR-1.2 | OpenBao MUST be auto-unsealed — manual unseal is not acceptable for production |
| NFR-1.3 | The OpenBao root token MUST be revoked after initial setup; emergency access MUST use `operator generate-root` with Shamir key holders |
| NFR-1.4 | All secret access MUST be logged to an immutable audit trail (OpenBao file audit backend, exported to central logging) |
| NFR-1.5 | Secrets in transit between portal and OpenBao MUST never be logged or cached client-side |
| NFR-1.6 | OpenBao MUST NOT be run in dev mode in any non-local environment |
| NFR-1.7 | CSRF tokens MUST be required on all state-changing portal API routes (NextAuth provides CSRF for auth routes; custom `/api/secrets/*` routes need explicit protection) |
| NFR-1.8 | Content Security Policy (CSP) headers MUST be configured on the portal, especially for the secrets UI |
| NFR-1.9 | Network segmentation: OpenBao MUST be reachable only from application backends, NOT from end users or the public internet; Keycloak admin console (`/admin`) MUST be restricted to management network or VPN |

#### NFR-2: Token Lifecycle

| ID | Requirement |
|----|-------------|
| NFR-2.1 | Keycloak access token lifetime: 5 minutes |
| NFR-2.2 | Keycloak refresh token lifetime: aligned with SSO session idle timeout (30 minutes), with rotation enabled |
| NFR-2.3 | OpenBao token TTL: 5 minutes (matching Keycloak access token), renewable — portal re-obtains on each request cycle using the current Keycloak JWT |
| NFR-2.4 | When a Keycloak session is revoked (admin termination or backchannel logout), the corresponding OpenBao token MUST NOT remain valid beyond its short TTL |
| NFR-2.5 | Refresh tokens MUST be stored server-side only (encrypted in NextAuth session or server-side store), NEVER in browser-accessible cookies or localStorage |
| NFR-2.6 | The portal's OpenBao token MUST be stored server-side only (in-memory or encrypted server-side session), NEVER sent to the browser |
| NFR-2.7 | Keycloak refresh token rotation MUST be enabled (each use issues a new refresh token and invalidates the old one) |

#### NFR-3: Availability & Operations

| ID | Requirement |
|----|-------------|
| NFR-3.1 | Keycloak and OpenBao MUST survive individual service restarts without session loss |
| NFR-3.2 | The bootstrap process MUST be fully idempotent (safe to re-run) |
| NFR-3.3 | Configuration MUST be declarative (scripts, not manual admin console clicks) |
| NFR-3.4 | Health checks MUST be exposed: Keycloak `/health`, OpenBao `/v1/sys/health` |

#### NFR-4: Backup & Disaster Recovery

| ID | Requirement |
|----|-------------|
| NFR-4.1 | Keycloak database MUST be backed up daily (realm config, users, credentials, signing keys) |
| NFR-4.2 | OpenBao MUST be backed up via Raft snapshots (if using Raft backend) or storage backend snapshots, daily minimum |
| NFR-4.3 | Backup restore procedure MUST be tested and documented |
| NFR-4.4 | OpenBao unseal keys (Shamir shares) MUST be escrowed securely — minimum 3-of-5 split, stored in separate physical/logical locations |
| NFR-4.5 | Recovery Time Objective (RTO): 1 hour for Keycloak, 1 hour for OpenBao |
| NFR-4.6 | Recovery Point Objective (RPO): 24 hours (daily backup) |

#### NFR-5: Key Rotation

| ID | Requirement |
|----|-------------|
| NFR-5.1 | Keycloak realm signing keys MUST be rotated annually with a grace period for active token validation |
| NFR-5.2 | OpenBao transit engine keys MUST support versioned rotation (new key version, old versions remain for decryption) |
| NFR-5.3 | AppRole SecretIDs for long-lived services MUST be rotated quarterly |
| NFR-5.4 | Keycloak client secrets MUST be rotatable without downtime (dual-active secret support) |
| NFR-5.5 | OpenBao seal key rotation procedure MUST be documented (rekey operation) |

#### NFR-6: Monitoring & Alerting

| ID | Requirement |
|----|-------------|
| NFR-6.1 | Authentication failures exceeding threshold (10/min per user) MUST trigger alerts |
| NFR-6.2 | Privileged access events (admin role assignment, policy changes, client creation) MUST trigger alerts |
| NFR-6.3 | OpenBao seal events MUST trigger immediate alerts (sealed = total secrets outage) |
| NFR-6.4 | Secret access anomalies (unusual volume or timing) SHOULD trigger alerts |
| NFR-6.5 | Keycloak admin events MUST be enabled and exported to central logging |
| NFR-6.6 | Keycloak login events MUST be enabled and exported to central logging |
| NFR-6.7 | OpenBao audit logs MUST be exported to central logging |
| NFR-6.8 | Log aggregation pipeline (ELK, Loki, or equivalent) MUST be defined |

#### NFR-7: Migration

| ID | Requirement |
|----|-------------|
| NFR-7.1 | Existing AMI-PORTAL users MUST be migrated to Keycloak without password reset |
| NFR-7.2 | Existing `.env` secrets MUST be migrated to OpenBao with zero downtime |
| NFR-7.3 | AMI-TRADING MUST be migrated from its independent auth to Keycloak OIDC |
| NFR-7.4 | AMI-STREAMS (Matrix) SHOULD be configured to delegate auth to Keycloak via OIDC |
| NFR-7.5 | The `base/backend/opsec/` framework code SHOULD be evaluated for reuse where applicable (secrets broker, audit trail) |

---

## 5. Architecture

```
                    ┌──────────────────┐
                    │    Keycloak      │
                    │   (Identity)     │
                    │                  │
                    │ Users, Groups,   │
                    │ Roles, SSO,      │
                    │ IdP Brokering,   │
                    │ Service Accounts │
                    └───────┬──────────┘
                            │
               OIDC tokens / Admin API
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
       v                    v                    v
┌──────────────┐   ┌────────────────┐   ┌────────────────┐
│  AMI-PORTAL  │   │  AMI-TRADING   │   │  AMI-STREAMS   │
│  (Next.js)   │   │  (FastAPI)     │   │  (Matrix)      │
│              │   │                │   │                │
│ Account Mgmt │   │ Validates KC   │   │ Delegates auth │
│ Admin Panels │   │ JWTs for API   │   │ to KC via OIDC │
│ Secrets UI   │   │ access         │   │                │
└──────┬───────┘   └────────────────┘   └────────────────┘
       │
       │  JWT auth (presents KC JWT to OpenBao)
       │  + AppRole (portal backend service identity)
       v
┌──────────────────┐
│    OpenBao       │
│   (Secrets)      │
│                  │
│ KV v2 secrets    │
│ Dynamic creds    │
│ Transit encrypt  │
│ PKI certs        │
│ SSH cert signing │
│ Audit log        │
└──────────────────┘
```

### 5.1 Portal ↔ OpenBao Integration

The portal backend acts as a proxy between the browser and OpenBao:

1. User authenticates to portal via Keycloak (NextAuth OIDC)
2. Portal backend presents the user's Keycloak JWT to OpenBao's JWT auth method (`POST /v1/auth/jwt/login`) to obtain a scoped OpenBao token
3. OpenBao validates the JWT signature via Keycloak's JWKS endpoint, extracts claims (`sub`, `groups`, `realm_access.roles`)
4. OpenBao token policies are determined by external group mappings (Keycloak groups → OpenBao external groups → policies)
5. Portal stores the OpenBao token server-side (in-memory, per-session), NEVER sends it to the browser
6. Portal API routes proxy secret operations to OpenBao using the user's scoped token
7. Secret values are never stored in the portal — read-through only
8. OpenBao token has short TTL (5 min) matching Keycloak access token; portal re-obtains as needed

### 5.2 OpenBao Namespace Hierarchy

```
root (/)
  │
  ├── platform/                          (platform-level secrets)
  │     ├── secrets/service/             (KV v2: platform service secrets)
  │     ├── secrets/infra/               (KV v2: infrastructure secrets)
  │     ├── pki/                         (PKI engine for internal certs)
  │     └── transit/                     (encryption-as-a-service)
  │
  └── tenants/
        ├── acme-corp/                   (namespace: tenant isolation)
        │     ├── secrets/service/       (KV v2: tenant service secrets)
        │     ├── secrets/team/          (KV v2: team shared secrets)
        │     ├── secrets/personal/      (KV v2: user personal vaults)
        │     └── pki/                   (tenant-scoped certificates)
        │
        └── globex-inc/                  (namespace)
              ├── secrets/service/
              ├── secrets/team/
              └── secrets/personal/
```

### 5.3 OpenBao Policy Definitions

Each human/service role maps to a named ACL policy. Team/group secret access uses external identity groups, NOT wildcard template expressions (which are not valid in OpenBao policy templates).

**`policy/platform-superadmin.hcl`**
```hcl
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
```

**`policy/platform-admin.hcl`**
```hcl
path "platform/secrets/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "tenants/+/secrets/*" {
  capabilities = ["read", "list"]
}
path "platform/pki/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "platform/transit/*" {
  capabilities = ["create", "read", "update", "list"]
}
path "sys/health" {
  capabilities = ["read"]
}
path "sys/policies/acl/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
# Cannot mount/unmount engines (superadmin only)
path "sys/mounts/*" {
  capabilities = ["deny"]
}
```

**`policy/platform-operator.hcl`**
```hcl
path "platform/secrets/service/data/*" {
  capabilities = ["read", "list"]
}
path "platform/secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
path "sys/health" {
  capabilities = ["read"]
}
path "sys/audit" {
  capabilities = ["read"]
}
```

**`policy/org-admin.hcl`** (applied within tenant namespace)
```hcl
path "secrets/service/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secrets/team/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
# Can read any user's personal vault for recovery
path "secrets/personal/+/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/+/metadata/*" {
  capabilities = ["read", "list"]
}
# Own personal vault (full)
path "secrets/personal/{{identity.entity.id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "pki/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

**`policy/team-lead.hcl`** (applied within tenant namespace)
```hcl
path "secrets/team/data/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secrets/team/metadata/*" {
  capabilities = ["read", "list"]
}
path "secrets/service/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/{{identity.entity.id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

**`policy/developer.hcl`** (applied within tenant namespace)
```hcl
path "secrets/service/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
path "secrets/team/data/*" {
  capabilities = ["create", "read", "update", "list"]
}
path "secrets/team/metadata/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/{{identity.entity.id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

**`policy/member.hcl`** (applied within tenant namespace)
```hcl
path "secrets/team/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/team/metadata/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/{{identity.entity.id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

**`policy/viewer.hcl`** (applied within tenant namespace)
```hcl
path "secrets/personal/{{identity.entity.id}}/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/{{identity.entity.id}}/metadata/*" {
  capabilities = ["read", "list"]
}
```

**`policy/guest.hcl`** (applied within tenant namespace)
```hcl
path "secrets/personal/{{identity.entity.id}}/data/*" {
  capabilities = ["read"]
}
```

**Service identity policies:**

**`policy/svc-platform-core.hcl`**
```hcl
path "platform/secrets/service/data/*" {
  capabilities = ["read"]
}
path "platform/transit/encrypt/*" {
  capabilities = ["update"]
}
path "platform/transit/decrypt/*" {
  capabilities = ["update"]
}
```

**`policy/svc-platform-infra.hcl`**
```hcl
path "platform/secrets/infra/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "platform/secrets/service/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "sys/health" {
  capabilities = ["read", "sudo"]
}
```

**`policy/svc-cicd-deployer.hcl`**
```hcl
path "platform/secrets/service/data/*" {
  capabilities = ["create", "read", "update"]
}
path "platform/secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
path "tenants/+/secrets/service/data/*" {
  capabilities = ["create", "read", "update"]
}
path "tenants/+/secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
```

**`policy/svc-tenant-app.hcl`** (per-tenant, applied in tenant namespace)
```hcl
path "secrets/service/data/*" {
  capabilities = ["read"]
}
path "secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
```

Team secrets use a **per-group policy** assigned to an external group, NOT a single templated policy:

```hcl
# Example: policy "team-engineering-secrets" assigned to external group "engineering"
path "secrets/team/data/engineering/*" {
  capabilities = ["create", "read", "update", "delete"]
}
path "secrets/team/metadata/engineering/*" {
  capabilities = ["list", "read", "delete"]
}
```

The bootstrap script creates one such policy per Keycloak group and maps it via external group aliases on the OIDC auth mount.

### 5.4 OpenBao Auth Methods

```
auth/oidc/       (OIDC via Keycloak — for humans)
  role: platform-admin
    bound_claims: {"realm_access.roles": "platform-admin"}
    token_policies: [platform-admin]
  role: org-user
    bound_claims: {"organization": "*"}
    claim_mappings: {"tenant_id": "tenant_id"}
    token_policies: []  (resolved via identity groups)

auth/approle/    (AppRole — for services)
  role: svc-platform-core
    secret_id_num_uses: 1
    secret_id_ttl: 600
    token_ttl: 300
    token_max_ttl: 600
    token_policies: [svc-platform-core]
    bind_secret_id: true
    token_bound_cidrs: ["10.0.0.0/8"]

  role: svc-cicd-deployer
    secret_id_num_uses: 1
    secret_id_ttl: 300
    token_ttl: 300
    token_max_ttl: 600
    token_policies: [svc-cicd-deployer]
    bind_secret_id: true
```

### 5.5 Keycloak Implementation

#### 5.5.1 Architecture: Single Realm with Organizations

Use Keycloak 26+ native Organizations feature (not realm-per-tenant). Avoids performance degradation at scale and enables cross-org user identity.

```
Realm: ami-platform
  │
  ├── Organization: acme-corp
  │     ├── Members (users with org-scoped roles)
  │     ├── Identity Provider: acme-saml-idp
  │     └── Domain: acme-corp.com
  │
  └── Organization: globex-inc
        ├── Members
        ├── Identity Provider: globex-oidc-idp
        └── Domain: globex.com
```

#### 5.5.2 Realm Roles (Platform-Scoped)

```
Realm Roles:
  platform-superadmin     (composite: includes platform-admin)
  platform-admin          (composite: includes platform-operator)
  platform-operator       (leaf role)
```

Composite role chain ensures inheritance: `platform-superadmin` automatically includes `platform-admin` and `platform-operator` permissions.

#### 5.5.3 Client Roles (Org-Scoped)

```
Client: ami-portal
  Client Roles:
    org-admin
    team-lead
    developer
    member
    viewer
    guest
```

These are assigned within the context of organization membership. A user gets `ami-portal:org-admin` scoped to their organization.

#### 5.5.4 Groups (Team Mapping)

```
Groups:
  /platform-ops                    → realm role: platform-operator
  /acme-corp
    /acme-corp/backend-team        → client role: ami-portal:developer
    /acme-corp/ops-team            → client role: ami-portal:team-lead
    /acme-corp/admins              → client role: ami-portal:org-admin
  /globex-inc
    /globex-inc/engineering        → client role: ami-portal:developer
    /globex-inc/admins             → client role: ami-portal:org-admin
```

Users inherit roles from group membership. Adding a user to `/acme-corp/ops-team` automatically grants `ami-portal:team-lead`.

#### 5.5.5 Service Account Clients

Each service identity is a separate Keycloak confidential client:

```
Client: svc-platform-core
  Access Type: confidential
  Service Accounts Enabled: true
  Client Authentication: client_secret_basic
  Token Lifespan: 300 seconds

Client: svc-tenant-app--acme-corp
  Access Type: confidential
  Service Accounts Enabled: true
  Token Lifespan: 300 seconds
```

#### 5.5.6 Token Claims Configuration

The following protocol mappers MUST be configured on the `ami-portal` client (and any client that authenticates to OpenBao):

| Mapper | Type | Token Claim Name | Purpose |
|--------|------|-----------------|---------|
| Group Membership | Group Membership | `groups` | Maps to OpenBao external groups |
| Realm Roles | User Realm Role | `realm_access.roles` | Maps to OpenBao role-based policies |
| Client Roles | User Client Role | `resource_access.${client_id}.roles` | Per-app authorization |
| Organization | Organization Membership | `organization` | Org scoping for tenant isolation |
| Tenant ID | User Attribute | `tenant_id` | Primary organization identifier |

The `groups` claim MUST NOT include full group paths (set "Full group path" to OFF in mapper config).

Expected access token structure:

```json
{
  "sub": "user-uuid",
  "realm_access": {
    "roles": ["platform-operator"]
  },
  "resource_access": {
    "ami-portal": {
      "roles": ["developer"]
    }
  },
  "organization": {
    "acme-corp": {
      "id": "org-uuid",
      "roles": ["developer"]
    }
  },
  "groups": ["acme-corp/backend-team"],
  "tenant_id": "acme-corp"
}
```

#### 5.5.7 Authorization Services (Future Enhancement)

For resource-level authorization beyond role checks, Keycloak Authorization Services can be enabled on the `ami-portal` client:

- **Resources**: `users`, `clients`, `idp`, `config`, `secrets`, `audit`, `roles`, `groups`, `orgs`
- **Scopes (Actions)**: `list`, `read`, `create`, `update`, `delete`, `assign-roles`, `assign-groups`, `reset-credentials`, `terminate-sessions`, `impersonate`, `rotate-secret`, `manage-roles`, `manage-members`, `manage-idps`, `sync`, `export`, `configure`, `mount`, `rotate`
- **Policies**: Role-based policies combined with org-scope policies via `UNANIMOUS` decision strategy (both role AND scope must pass)

This is documented as a future upgrade path. Initially, the portal's `withPermission()` middleware performs role-to-permission resolution using the `ROLE_PERMISSIONS` map in application code.

---

## 6. Bootstrap Requirements

The `make bootstrap-keycloak` process MUST be extended (or a new `make bootstrap-iam` created) to:

| Step | Action |
|------|--------|
| 1 | Create/verify the `ami` Keycloak realm |
| 2 | Configure realm settings: brute force detection, password policy, session timeouts |
| 3 | Create/upgrade the `ami-portal` client (confidential, service account enabled) |
| 4 | Configure protocol mappers on `ami-portal` client (`groups`, `realm_access.roles`) |
| 5 | Assign realm-management roles to the service account (including `manage-identity-providers`) |
| 6 | Create all social IdPs — enabled if credentials provided via env vars, disabled otherwise |
| 7 | Create realm roles: `platform-superadmin` (composite), `platform-admin` (composite), `platform-operator` (leaf). Keep legacy `admin`/`editor`/`viewer`/`guest` as aliases during migration |
| 8 | Create `ami-portal` client roles: `org-admin`, `team-lead`, `developer`, `member`, `viewer`, `guest` |
| 8a | Create default groups mapped to roles (e.g., `/platform-ops` → `platform-operator`) |
| 9 | Enable Keycloak admin events and login events logging |
| 10 | Initialize OpenBao (if not already): enable JWT auth, KV v2, transit engine |
| 11 | Configure OpenBao JWT auth to validate Keycloak JWTs (JWKS URL, issuer, audience) |
| 12 | Create OpenBao policies: `platform-superadmin`, `platform-admin`, `platform-operator`, `org-admin`, `team-lead`, `developer`, `member`, `viewer`, `guest`, `svc-platform-core`, `svc-platform-infra`, `svc-cicd-deployer`, per-group team policies |
| 12a | Create OpenBao namespaces: `platform/`, `tenants/<org-slug>/` for each organization |
| 13 | Create OpenBao external groups with aliases on the JWT auth mount for each Keycloak group/role |
| 14 | Create AppRole for portal backend with appropriate policies |
| 15 | Deliver portal AppRole credentials via response wrapping |

All steps MUST be idempotent.

---

## 7. Migration Plan

### Phase 1: Foundation (Current)
- [x] Keycloak deployed and running
- [x] Portal authenticates via Keycloak OIDC (NextAuth)
- [x] Portal RBAC derives from Keycloak JWT claims
- [x] Bootstrap script configures service account
- [ ] Bootstrap enables brute force detection, password policy, session timeouts
- [ ] Bootstrap creates identity providers
- [ ] Bootstrap creates default roles/groups
- [ ] Bootstrap configures protocol mappers (groups claim)
- [ ] Bootstrap enables admin + login event logging

### Phase 2: OpenBao Integration
- [ ] Deploy OpenBao (decide: standalone binary vs Docker, Raft vs file backend)
- [ ] Configure auto-unseal mechanism
- [ ] Configure JWT auth method (Keycloak JWKS)
- [ ] Set up KV v2, transit engine
- [ ] Create policies (admin, user-template, per-group, service)
- [ ] Create external group mappings
- [ ] Build portal secrets UI (browse, create, read, delete)
- [ ] Migrate `.env` secrets to OpenBao KV
- [ ] Migrate portal service credentials to OpenBao

### Phase 3: Service Migration
- [ ] AMI-TRADING: Replace FastAPI auth with Keycloak JWT validation
- [ ] AMI-STREAMS: Configure Matrix Synapse OIDC delegation to Keycloak
- [ ] Orchestrator: Replace `.env` secrets with OpenBao lookups
- [ ] CI/CD: AppRole-based secret injection
- [ ] SSH: Migrate from passwords to SSH certificate signing

### Phase 4: Hardening
- [ ] Enable MFA enforcement for admin role (Keycloak required action)
- [ ] Implement backchannel logout across all services
- [ ] Revoke OpenBao root token
- [ ] Set up backup schedule (Keycloak DB + OpenBao snapshots)
- [ ] Test backup restore procedure
- [ ] Configure monitoring and alerting pipeline
- [ ] Audit log export to central logging
- [ ] Key rotation procedures documented and tested
- [ ] Define and test break-glass / emergency access procedure
- [ ] Remove all `.env` secret files

---

## 8. Verification

| Check | Method |
|-------|--------|
| **SSO** | Log in to Portal, access Trading API — no second login prompt |
| **Single logout** | Log out from Portal, verify Trading session is terminated via backchannel |
| **IdPs listed** | Open drawer → Add Account → verify Google/GitHub/etc. listed |
| **Personal secrets CRUD** | Create secret via portal, read it back, verify isolation |
| **Cross-user isolation** | User A cannot read User B's secrets (403 from OpenBao) |
| **Team secrets shared** | Two users in same Keycloak group can read same secret path |
| **Group removal** | Remove user from Keycloak group, verify OpenBao access revoked on next token |
| **Service account auth** | Service authenticates via AppRole, reads secret from its namespace |
| **Dynamic credentials** | Request dynamic DB creds, verify auto-expiry after lease TTL |
| **Audit trail** | Every secret read/write logged in OpenBao audit |
| **Bootstrap idempotent** | Run `make bootstrap-iam` twice — no errors, no duplicates |
| **MFA enforcement** | Admin role requires TOTP on login; viewer role does not |
| **Brute force lockout** | 5 failed logins → account locked for 15 minutes |
| **Password policy** | Reject passwords under 12 chars, reject compromised passwords |
| **Backup restore** | Restore Keycloak + OpenBao from backup, verify all data intact |
| **Session revocation** | Admin terminates user session, verify immediate effect |
| **Secret UI XSS** | Store secret value containing `<script>`, verify it renders as text |
| **CSRF protection** | Replay a secret write request without CSRF token, verify 403 |
| **Org isolation** | `org-admin` of org A cannot read secrets in org B namespace |
| **Escalation guard** | `org-admin` cannot assign `platform-admin` role — API returns 403 |
| **Role assignment ceiling** | `team-lead` can assign `developer` but not `org-admin` |
| **Service account isolation** | `svc-tenant-app--acme-corp` cannot read `globex-inc` secrets |
| **Legacy role compat** | User with legacy `editor` role resolves to `developer` permissions |
| **Platform operator** | `platform-operator` can view users and terminate sessions but cannot create users |
| **Guest self-only** | `guest` can read own profile but not list other users |

---

## 9. Operational Procedures (To Be Documented)

| Procedure | Description |
|-----------|-------------|
| Emergency access (break-glass) | Generate new OpenBao root token via `operator generate-root` with Shamir key holders; documented procedure with tamper-evident audit |
| Keycloak key rotation | Rotate realm signing keys with grace period; document impact on active sessions |
| OpenBao rekey | Generate new Shamir shares; document key holder ceremony |
| OpenBao transit key rotation | Version transit keys; old versions retained for decryption |
| Incident response: compromised credentials | Revoke user sessions in Keycloak, revoke OpenBao tokens, rotate affected secrets, audit log review |
| Incident response: compromised service account | Disable Keycloak client, rotate AppRole SecretID, rotate all secrets the service had access to |

---

## 10. Open Questions

1. **OpenBao deployment**: Standalone binary, Docker, or Kubernetes? Storage backend: Raft (recommended for single-node), file, or PostgreSQL?
2. **Auto-unseal mechanism**: For single-host deployment, TPM-based or GCP/AWS KMS? Transit auto-unseal with a second instance on the same host provides no availability benefit.
3. **`base/backend/opsec/` reuse**: Should the secrets broker from `base/` be adapted, or build fresh against OpenBao API?
4. **Matrix federation**: Can Matrix Authentication Service (MAS) delegate to Keycloak, or does Synapse need OIDC configured directly?
5. **AMI-TRADING migration timeline**: Can Trading tolerate a flag day cutover, or does it need dual-auth during migration?
6. **Domain architecture**: Will all services share a domain (subdomains) or remain on separate origins? Affects CORS configuration for OIDC callbacks.
7. **Log aggregation**: ELK, Loki+Grafana, or something else? Needed before Phase 4 alerting.
8. ~~**Multi-tenancy**~~: Addressed — Keycloak Organizations (v26+) and OpenBao namespaces are included in the permission model (see FR-5.5 and sections 5.2/5.5.1).
9. **Just-In-Time (JIT) access**: Should admin-level OpenBao access be time-limited with approval workflows, or is static role assignment acceptable?
