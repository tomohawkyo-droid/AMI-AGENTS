# Operations — Technical Specification

**Date:** 2026-03-01
**Status:** DRAFT
**Parent:** [SPECIFICATION-IAM.md](SPECIFICATION-IAM.md)
**Requirements:** NFR-3 through NFR-7, Sections 6-9

---

## 1. Bootstrap Procedure

### 1.1 Overview

The IAM bootstrap is a single idempotent command (`make bootstrap-iam`) that configures both Keycloak and OpenBao from a cold start. All steps are safe to re-run.

```bash
make bootstrap-iam
# Equivalent to:
#   1. make bootstrap-keycloak    (existing)
#   2. make bootstrap-openbao     (new)
#   3. make bootstrap-iam-link    (new — cross-system wiring)
```

### 1.2 Prerequisites

| Dependency | Check | Error Message |
|------------|-------|---------------|
| `curl` | `command -v curl` | "curl is required" |
| `jq` | `command -v jq` | "jq is required" |
| `bao` | `command -v bao` | "OpenBao CLI (bao) is required" |
| Keycloak running | `curl -sf $KEYCLOAK_URL/health` | "Keycloak not reachable at $KEYCLOAK_URL" |
| OpenBao running | `curl -sf $BAO_ADDR/v1/sys/health` | "OpenBao not reachable at $BAO_ADDR" |

### 1.3 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `KEYCLOAK_URL` | `http://192.168.50.66:8082` | Keycloak base URL |
| `KEYCLOAK_REALM` | `ami` | Target realm |
| `KEYCLOAK_ADMIN_USER` | `admin` | Keycloak admin username |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Keycloak admin password |
| `KEYCLOAK_CLIENT_ID` | `ami-portal` | Portal client ID |
| `KEYCLOAK_CLIENT_SECRET` | (from `.env.local`) | Portal client secret |
| `BAO_ADDR` | `http://192.168.50.66:8200` | OpenBao API address |
| `BAO_TOKEN` | (from init output) | OpenBao root/admin token |
| `KC_IDP_<PROVIDER>_CLIENT_ID` | (optional) | IdP client IDs |
| `KC_IDP_<PROVIDER>_CLIENT_SECRET` | (optional) | IdP client secrets |

### 1.4 Step-by-Step Procedure

All steps MUST be idempotent (NFR-3.2, NFR-3.3).

#### Phase 1: Keycloak Realm Configuration

| Step | Action | API | Idempotent |
|------|--------|-----|------------|
| 1 | Obtain admin token from master realm | `POST /realms/master/.../token` | Yes (stateless) |
| 2 | Verify `ami` realm exists | `GET /admin/realms/ami` | Yes |
| 3 | Configure realm: brute force, password policy, session timeouts, events | `PUT /admin/realms/ami` | Yes (PUT is replace) |
| 4 | Look up `ami-portal` client | `GET /admin/realms/ami/clients?clientId=ami-portal` | Yes |
| 5 | Update client: confidential, service account enabled | `PUT /admin/realms/ami/clients/{uuid}` | Yes |
| 6 | Configure protocol mappers (groups, roles, tenant_id, audience) | `POST` or `PUT` per mapper | Yes (check exists first) |
| 7 | Get service account user, assign realm-management roles | `POST /admin/realms/ami/users/{sa}/role-mappings/clients/{rm}` | Yes (additive) |
| 8 | Create realm roles: `platform-superadmin` (composite), `platform-admin` (composite), `platform-operator` | `POST` if not exists | Yes (check first) |
| 9 | Create client roles on `ami-portal`: `org-admin`, `team-lead`, `developer`, `member`, `viewer`, `guest` | `POST` if not exists | Yes |
| 10 | Create default groups with role mappings | `POST /admin/realms/ami/groups` if not exists | Yes |
| 11 | Create/update social IdPs (enabled if credentials provided, disabled otherwise) | `POST` or `PUT` per IdP | Yes |
| 12 | Enable admin events and login events | `PUT /admin/realms/ami` | Yes |

#### Phase 2: OpenBao Configuration

| Step | Action | CLI/API | Idempotent |
|------|--------|---------|------------|
| 13 | Check OpenBao initialized | `bao status` | Yes |
| 14 | If not initialized: `bao operator init -key-shares=5 -key-threshold=3` | One-time | Skipped if already init'd |
| 15 | Unseal if sealed | `bao operator unseal` × 3 | Yes (no-op if unsealed) |
| 16 | Enable audit devices (file + stdout) | `bao audit enable` | Yes (no-op if enabled) |
| 17 | Enable JWT auth method | `bao auth enable jwt` | Yes (no-op if enabled) |
| 18 | Configure JWT auth (Keycloak JWKS URL, issuer, audience) | `bao write auth/jwt/config` | Yes (overwrite) |
| 19 | Create JWT roles (platform-admin, portal-user) | `bao write auth/jwt/role/*` | Yes (overwrite) |
| 20 | Enable AppRole auth method | `bao auth enable approle` | Yes (no-op if enabled) |
| 21 | Create AppRole roles (svc-platform-core, svc-cicd-deployer, etc.) | `bao write auth/approle/role/*` | Yes (overwrite) |
| 22 | Enable KV v2 engines (platform/secrets/service, platform/secrets/infra) | `bao secrets enable` | Yes (no-op if enabled) |
| 23 | Enable transit engine (platform/transit) | `bao secrets enable` | Yes |
| 24 | Create transit keys (portal-data, token-signing) | `bao write transit/keys/*` | Yes (no-op if exists) |
| 25 | Enable PKI engines (platform/pki, platform/pki_int) | `bao secrets enable` | Yes |
| 26 | Create namespaces (platform/, tenants/) | `bao namespace create` | Yes |

#### Phase 3: Cross-System Wiring

| Step | Action | Details | Idempotent |
|------|--------|---------|------------|
| 27 | Create OpenBao policies (all HCL policies from SPEC-SECRETS Section 6) | `bao policy write` | Yes (overwrite) |
| 28 | Create external identity groups for Keycloak groups | `bao write identity/group` | Yes (check exists) |
| 29 | Create group aliases on JWT auth mount | `bao write identity/group-alias` | Yes (check exists) |
| 30 | Generate portal AppRole credentials | `bao read auth/approle/role/svc-platform-core/role-id` | Yes |
| 31 | Deliver portal SecretID via response wrapping | `bao write -wrap-ttl=300 -f auth/approle/role/svc-platform-core/secret-id` | Yes (new each time) |

#### Per-Organization Bootstrap

When a new organization is created in Keycloak:

| Step | Action |
|------|--------|
| O1 | Create Keycloak organization via Organizations API |
| O2 | Create OpenBao tenant namespace: `tenants/<org-slug>` |
| O3 | Mount KV v2 engines in namespace: `secrets/service`, `secrets/team`, `secrets/personal` |
| O4 | Create org-scoped policies in namespace |
| O5 | Create external groups for org's Keycloak groups |
| O6 | Create group aliases mapping Keycloak groups → OpenBao policies |

---

## 2. Migration Specification (NFR-7)

### 2.1 Phase 1: Foundation (Current State → Enhanced Keycloak)

**Status**: Partially complete.

| Task | Status | Details |
|------|--------|---------|
| Keycloak deployed and running | Done | `192.168.50.66:8082` |
| Portal authenticates via Keycloak OIDC | Done | NextAuth + Keycloak provider |
| Portal RBAC derives from Keycloak JWT | Done | `resolvePermissions()` |
| Bootstrap configures service account | Done | `bootstrap-keycloak.sh` |
| Brute force, password policy, session timeouts | **TODO** | Add to bootstrap |
| Protocol mappers (groups claim) | **TODO** | Add to bootstrap |
| Admin + login event logging | **TODO** | Add to bootstrap |
| Identity providers | **TODO** | Add to bootstrap |
| Default roles/groups | **TODO** | Add to bootstrap |

**Rollback**: Keycloak realm export. No data at risk since auth is read-only from Keycloak.

### 2.2 Phase 2: OpenBao Integration

| Task | Dependencies | Rollback |
|------|-------------|----------|
| Deploy OpenBao container | Docker, systemd | Stop container |
| Initialize (Shamir keys) | Physical key ceremony | Cannot undo — keys are final |
| Configure auto-unseal | Unseal OpenBao running | Revert to Shamir |
| JWT auth (Keycloak JWKS) | Keycloak running | Disable auth method |
| KV v2 + transit engines | OpenBao initialized | Disable engines |
| Policies + external groups | JWT auth configured | Delete policies |
| Portal secrets UI | All above | Feature flag off |
| Migrate `.env` secrets to OpenBao | Secrets UI working | Keep `.env` as backup |
| Remove `.env` files | All secrets verified in OpenBao | Restore from git |

**Critical**: `.env` files MUST NOT be deleted until all secrets are verified readable from OpenBao. Keep `.env` as backup for at least one release cycle.

### 2.3 Phase 3: Service Migration

| Service | Migration | Dual-Auth Period |
|---------|-----------|-----------------|
| AMI-Portal | Already on Keycloak | N/A |
| AMI-Trading | Replace FastAPI auth with Keycloak JWT validation | 2 weeks: accept both old and KC tokens |
| AMI-Streams | Configure Matrix Synapse OIDC → Keycloak | 1 week: parallel auth |
| Orchestrator | Replace `.env` secrets with OpenBao lookups | Until verified |
| CI/CD | AppRole-based secret injection | Until pipeline stable |

### 2.4 Phase 4: Hardening

| Task | Verification |
|------|-------------|
| MFA enforcement for admin roles | Login as admin → TOTP prompt |
| Backchannel logout across all services | Logout from Portal → verify Trading session terminated |
| Revoke OpenBao root token | `bao token revoke` → verify no root token works |
| Backup schedule (KC DB + OpenBao snapshots) | Cron job running, backup files exist |
| Test backup restore | Restore to test instance, verify data intact |
| Monitoring + alerting | Alert fires on test seal event |
| Audit log export to central logging | Logs visible in aggregation system |
| Key rotation procedures tested | Document signed off |
| Break-glass procedure tested | Generate-root with 3 key holders succeeds |
| Remove all `.env` secret files | `find . -name .env* -not -name .env.example` returns empty |

### 2.5 User Migration (NFR-7.1)

Existing Portal users MUST be migrated to Keycloak without password reset:

**Option A — Keycloak User Storage Provider (Recommended)**:
1. Implement a custom User Storage SPI that reads from the Portal's existing user store
2. On first login, Keycloak validates against legacy store, then migrates credentials to Keycloak's internal store
3. Transparent to users — no password reset required

**Option B — Bulk Import**:
1. Export users from Portal (username, email, hashed password)
2. Import via Keycloak Admin API with `credentialData` containing the hash
3. Keycloak must be configured to recognize the hash algorithm

---

## 3. Backup & Disaster Recovery (NFR-4)

### 3.1 Keycloak Database Backup

```bash
#!/bin/bash
# /opt/ami/scripts/backup-keycloak.sh
set -euo pipefail

BACKUP_DIR="/var/backups/keycloak"
DATE=$(date +%Y%m%d-%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# PostgreSQL dump (realm config, users, credentials, signing keys)
docker exec keycloak-db pg_dump \
  -U keycloak \
  -d keycloak \
  --format=custom \
  --compress=9 \
  > "$BACKUP_DIR/keycloak-${DATE}.dump"

# Cleanup old backups
find "$BACKUP_DIR" -name "keycloak-*.dump" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Keycloak backup completed: keycloak-${DATE}.dump"
```

Schedule: Daily via systemd timer or cron (NFR-4.1).

### 3.2 OpenBao Raft Snapshot

```bash
#!/bin/bash
# /opt/ami/scripts/backup-openbao.sh
set -euo pipefail

BACKUP_DIR="/var/backups/openbao"
DATE=$(date +%Y%m%d-%H%M%S)
RETENTION_DAYS=30
BAO_ADDR="http://192.168.50.66:8200"

mkdir -p "$BACKUP_DIR"

# Raft snapshot (encrypted, contains all secrets)
bao operator raft snapshot save \
  "$BACKUP_DIR/openbao-${DATE}.snap"

# Verify snapshot
bao operator raft snapshot inspect \
  "$BACKUP_DIR/openbao-${DATE}.snap" > /dev/null

# Cleanup old snapshots
find "$BACKUP_DIR" -name "openbao-*.snap" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] OpenBao backup completed: openbao-${DATE}.snap"
```

Schedule: Daily via systemd timer or cron (NFR-4.2).

> **Security**: Raft snapshots contain all secrets (encrypted by the seal key). Backup files MUST be stored with restricted permissions (0600) and optionally encrypted at rest.

### 3.3 Restore Procedures (NFR-4.3)

#### Restore Keycloak

```bash
# Stop Keycloak
docker stop ami-keycloak

# Restore database
docker exec -i keycloak-db pg_restore \
  -U keycloak \
  -d keycloak \
  --clean \
  --if-exists \
  < /var/backups/keycloak/keycloak-YYYYMMDD-HHMMSS.dump

# Start Keycloak
docker start ami-keycloak

# Verify
curl -sf http://192.168.50.66:8082/health
```

#### Restore OpenBao

```bash
# Ensure OpenBao is unsealed
bao status

# Restore Raft snapshot (WARNING: replaces ALL data)
bao operator raft snapshot restore \
  /var/backups/openbao/openbao-YYYYMMDD-HHMMSS.snap

# Verify
bao status
bao secrets list
```

### 3.4 Recovery Objectives

| Metric | Target | Requirement |
|--------|--------|-------------|
| RTO (Keycloak) | 1 hour | NFR-4.5 |
| RTO (OpenBao) | 1 hour | NFR-4.5 |
| RPO | 24 hours | NFR-4.6 |
| Backup frequency | Daily | NFR-4.1, NFR-4.2 |
| Backup retention | 30 days | Operational |
| Restore test frequency | Quarterly | NFR-4.3 |

---

## 4. Key Rotation Procedures (NFR-5)

### 4.1 Keycloak Realm Signing Keys (NFR-5.1)

```bash
# Rotation: Annual with grace period

# 1. Generate new key pair (Keycloak creates automatically)
# Admin Console → Realm Settings → Keys → Providers → Add provider → rsa-generated

# 2. Set new key as active (highest priority)
# Admin Console → Realm Settings → Keys → Active → set priority

# 3. Grace period: Keep old key for token validation (2x max session lifetime)
#    Old tokens signed with old key remain valid until they expire

# 4. After grace period, disable old key provider
```

Grace period calculation: `ssoSessionMaxLifespan` (10h) + `accessTokenLifespan` (5min) ≈ **10.5 hours minimum**. Use 24 hours for safety.

### 4.2 OpenBao Transit Keys (NFR-5.2)

```bash
# Rotate transit key (old versions retained for decryption)
bao write -f platform/transit/keys/portal-data/rotate

# Verify new version
bao read platform/transit/keys/portal-data
# min_decryption_version: 1  (old ciphertext still decryptable)
# latest_version: 2

# Re-encrypt data with latest key version
bao write platform/transit/rewrap/portal-data \
  ciphertext="vault:v1:..."
# Returns: ciphertext="vault:v2:..."

# After all data re-encrypted, advance minimum decryption version
bao write platform/transit/keys/portal-data/config \
  min_decryption_version=2
```

### 4.3 AppRole SecretIDs (NFR-5.3)

```bash
# Quarterly rotation for long-lived services

# 1. Generate new SecretID (response-wrapped)
bao write -wrap-ttl=300 -f auth/approle/role/svc-platform-core/secret-id
# → Deliver wrapping token to service

# 2. Service unwraps and uses new SecretID
# 3. Old SecretID expires naturally (or revoke manually)

# For CI/CD: SecretIDs are single-use, no rotation needed
```

### 4.4 Keycloak Client Secrets (NFR-5.4)

```bash
# Rotation without downtime using dual-active secrets

# 1. Generate new secret via portal UI or API
POST /api/account-manager/clients/{uuid}/secret
# Keycloak generates new secret; old secret remains valid briefly

# 2. Update all consuming services with new secret
# 3. Verify all services authenticate successfully
# 4. Old secret is automatically invalidated by Keycloak
```

### 4.5 OpenBao Seal Key (Rekey — NFR-5.5)

```bash
# Generate new Shamir shares (requires existing quorum)

# 1. Initialize rekey
bao operator rekey -init \
  -key-shares=5 \
  -key-threshold=3

# 2. Provide existing unseal keys (3 of 5)
bao operator rekey -nonce=<nonce> <unseal-key-1>
bao operator rekey -nonce=<nonce> <unseal-key-2>
bao operator rekey -nonce=<nonce> <unseal-key-3>

# 3. New shares are generated and distributed
# 4. Old shares are invalidated
```

> **Ceremony**: Rekey requires physical presence of 3 key holders. Schedule as a documented procedure with witnesses.

---

## 5. Monitoring & Alerting (NFR-6)

### 5.1 Health Checks (NFR-3.4)

| Service | Endpoint | Expected | Check Interval |
|---------|----------|----------|---------------|
| Keycloak | `GET /health` | 200 | 30s |
| Keycloak (ready) | `GET /health/ready` | 200 | 30s |
| OpenBao | `GET /v1/sys/health` | 200 (unsealed) | 15s |
| PostgreSQL (KC) | `pg_isready -U keycloak` | exit 0 | 30s |

OpenBao health response codes:
- `200` — initialized, unsealed, active
- `429` — unsealed, standby
- `472` — DR secondary, active
- `473` — performance standby
- `501` — not initialized
- `503` — sealed

### 5.2 Alert Thresholds

| Alert | Condition | Severity | Requirement |
|-------|-----------|----------|-------------|
| Auth failures spike | >10 failures/min per user | Warning | NFR-6.1 |
| Mass auth failures | >100 failures/min total | Critical | NFR-6.1 |
| Privileged access | Admin role assignment, policy change, client creation | Info | NFR-6.2 |
| OpenBao sealed | `/v1/sys/health` returns 503 | Critical | NFR-6.3 |
| OpenBao not initialized | `/v1/sys/health` returns 501 | Critical | NFR-6.3 |
| Secret access anomaly | >5x normal volume for user | Warning | NFR-6.4 |
| Keycloak down | Health check fails 3x | Critical | Operational |
| PostgreSQL down | `pg_isready` fails 3x | Critical | Operational |
| Backup failure | Backup script exits non-zero | Warning | Operational |
| Certificate expiry | <30 days to expiry | Warning | Operational |
| Certificate expiry | <7 days to expiry | Critical | Operational |

### 5.3 Log Aggregation Pipeline (NFR-6.8)

```
Keycloak Events                    OpenBao Audit
  │ (jboss-logging → stdout)         │ (file + stdout audit device)
  │                                   │
  └──── Docker log driver ────────────┘
              │
              v
       Log Aggregation
       (Loki + Grafana  OR  ELK)
              │
              v
       Alert Rules → Notification Channels
       (Grafana Alerting / Kibana Watcher)
```

Docker log driver configuration:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  }
}
```

For centralized logging, switch to Loki driver:
```json
{
  "log-driver": "loki",
  "log-opts": {
    "loki-url": "http://localhost:3100/loki/api/v1/push",
    "loki-batch-size": "400"
  }
}
```

---

## 6. Audit Configuration

### 6.1 Keycloak Events (NFR-6.5, NFR-6.6)

Admin events and login events are enabled via realm configuration (see SPECIFICATION-AUTHENTICATION.md Section 2.7).

Key event types monitored:
- **Login events**: `LOGIN`, `LOGIN_ERROR`, `LOGOUT`, `CODE_TO_TOKEN`, `REFRESH_TOKEN`
- **Admin events**: User creation, role assignment, client modification, realm setting changes

Event retention: 30 days in Keycloak database. Exported to central logging for long-term retention.

### 6.2 OpenBao Audit (NFR-1.4, NFR-6.7)

Two audit devices provide redundancy (see SPECIFICATION-SECRETS.md Section 2.4):

1. **File audit**: `/var/log/openbao/audit.log` (JSON, HMAC'd sensitive values)
2. **Stdout audit**: Docker log driver → log aggregation

> **Critical**: If all audit devices fail, OpenBao blocks ALL requests. This is by design — auditability cannot be silently lost.

### 6.3 Audit Log Format

```json
{
  "type": "response",
  "time": "2026-03-01T10:00:00.000Z",
  "auth": {
    "client_token": "hmac-sha256:...",
    "accessor": "hmac-sha256:...",
    "display_name": "jwt-jdoe",
    "policies": ["developer", "team-backend-secrets"],
    "token_policies": ["developer"],
    "identity_policies": ["team-backend-secrets"],
    "metadata": { "role": "portal-user" }
  },
  "request": {
    "id": "uuid",
    "operation": "read",
    "path": "tenants/acme-corp/secrets/team/data/backend-team/db-creds",
    "remote_address": "192.168.50.66"
  },
  "response": {
    "data": {
      "data": "hmac-sha256:...",
      "metadata": { "version": 3 }
    }
  }
}
```

Sensitive values (secret data, tokens) are HMAC'd in the audit log — not plaintext.

---

## 7. Emergency Access (Break-Glass)

### 7.1 OpenBao Root Token Generation

When the root token has been revoked (NFR-1.3), emergency access requires a new root token generated via `operator generate-root`:

```bash
# 1. Initialize root token generation
bao operator generate-root -init
# → Returns OTP and nonce

# 2. Each key holder provides their unseal key (3 of 5 required)
bao operator generate-root -nonce=<nonce> <unseal-key-1>
bao operator generate-root -nonce=<nonce> <unseal-key-2>
bao operator generate-root -nonce=<nonce> <unseal-key-3>

# 3. Decode the encoded root token using the OTP
bao operator generate-root -decode=<encoded-token> -otp=<otp>
# → Root token

# 4. Perform emergency operations
BAO_TOKEN=<root-token> bao <command>

# 5. IMMEDIATELY revoke root token after use
bao token revoke <root-token>
```

### 7.2 Break-Glass Procedure

| Step | Action | Personnel |
|------|--------|-----------|
| 1 | Declare emergency, document reason | Incident commander |
| 2 | Contact minimum 3 key holders | Incident commander |
| 3 | Verify identities (video call or in-person) | All key holders |
| 4 | Generate root token (see 7.1) | Key holders |
| 5 | Perform minimum necessary operations | Authorized operator |
| 6 | Revoke root token immediately | Authorized operator |
| 7 | Document all actions taken | Incident commander |
| 8 | Review audit logs | Security lead |
| 9 | Post-incident review within 24 hours | All stakeholders |

### 7.3 Keycloak Emergency Access

Keycloak admin console access is always available via the `admin` account on the master realm. If the admin password is lost:

```bash
# Reset admin password via Keycloak CLI
docker exec ami-keycloak /opt/keycloak/bin/kcadm.sh \
  config credentials --server http://localhost:8080 \
  --realm master --user admin --password <old-password>

# Or reset via environment variable on restart
docker stop ami-keycloak
# Set KEYCLOAK_ADMIN_PASSWORD=<new-password> in compose
docker start ami-keycloak
```

### 7.4 Incident Response: Compromised Credentials

| Scenario | Response |
|----------|----------|
| **Compromised user credentials** | 1. Revoke all Keycloak sessions for user. 2. Force password reset. 3. Review audit logs for unauthorized access. 4. Notify user. |
| **Compromised service account** | 1. Disable Keycloak client. 2. Rotate AppRole SecretID. 3. Revoke all OpenBao tokens for the service. 4. Rotate all secrets the service had access to. 5. Review audit logs. |
| **Compromised unseal key** | 1. Initiate rekey ceremony (Section 4.5). 2. Generate new shares. 3. Distribute to new holders. 4. Verify old shares no longer work. |
| **Compromised OpenBao token** | 1. Revoke token: `bao token revoke <token>`. 2. Short TTL (5 min) limits exposure. 3. Review audit logs for unauthorized reads. |

---

## 8. Compliance Traceability Matrix

| Requirement | Specification Section | Verification Method |
|-------------|----------------------|-------------------|
| **FR-1.1** SSO via OIDC | AUTH §5.1 | Log in to Portal, access Trading — no second login |
| **FR-1.2** No re-login across apps | AUTH §5.1 | SSO session cookie skip |
| **FR-1.3** Backchannel logout | AUTH §5.5 | Logout Portal → verify Trading session terminated |
| **FR-1.4** Backchannel logout URL | AUTH §4.1-4.3 | Check client config in Keycloak |
| **FR-1.5** Redirect-based SSO | AUTH §5.1 | Network trace: no cross-domain cookies |
| **FR-2.1** Session idle 30 min | AUTH §2.2 | Idle 31 min → session expired |
| **FR-2.2** Session max 10 hr | AUTH §2.2 | Active for 10h → session expired |
| **FR-2.3** Max 5 sessions | AUTH §2.6 | Login 6 times → oldest terminated |
| **FR-2.4** User session self-view | AUTH (Keycloak console) | User views own sessions |
| **FR-2.5** Admin session termination | AUTH §6.3 | Admin terminates user → immediate effect |
| **FR-3.1** Bootstrap configures IdPs | AUTH §7.1 | Run bootstrap → IdPs created |
| **FR-3.2** 11 social IdPs | AUTH §7.1 | All 11 listed in Keycloak |
| **FR-3.5** Dynamic IdP discovery | AUTH §7.3 | Add Account shows enabled IdPs |
| **FR-4.1** User CRUD via portal | AUTHZ §5.1 | Create/edit/delete user in portal |
| **FR-5.2** 74 atomic permissions | AUTHZ §2 | Permission registry enumerated |
| **FR-5.3** Human actor hierarchy | AUTHZ §3.1-3.2 | Role assignments verified |
| **FR-5.5** Org/tenant scoping | AUTHZ §4.2 | Org-admin can't access other org |
| **FR-5.7** Escalation guard | AUTHZ §4.3 | Team-lead can't assign org-admin → 403 |
| **FR-5.8** Backward compatibility | AUTHZ §6 | Legacy `editor` maps to `developer` |
| **FR-6.1** Min 12 char password | AUTH §2.4 | 11-char password rejected |
| **FR-6.2** Breached password check | AUTH §2.4 | Known-breached password rejected |
| **FR-7.1** TOTP support | AUTH §2.5 | Admin prompted for TOTP setup |
| **FR-7.2** WebAuthn support | AUTH §2.5 | Hardware key registration works |
| **FR-8.1** Brute force enabled | AUTH §2.3 | 5 failures → lockout |
| **FR-8.2** Max 5 failures | AUTH §2.3 | 6th attempt blocked |
| **FR-8.3** 15 min lockout | AUTH §2.3 | Wait 15 min → login succeeds |
| **FR-9.1** Dedicated service clients | AUTH §4.4 | Each service has own client |
| **FR-9.2** Client credentials grant | AUTH §5.2 | Service authenticates via CC grant |
| **FR-10.1** AppRole/JWT for services | SECRETS §5 | Service authenticates to OpenBao |
| **FR-10.2** Isolated service paths | SECRETS §4.1 | Service can't read other's secrets |
| **FR-10.4** Dynamic DB credentials | SECRETS §8 | Request creds → get temp user/pass |
| **FR-10.5** Audit all secret access | SECRETS §2.4 | Every read/write in audit log |
| **FR-11.1** Single-use CI/CD SecretIDs | SECRETS §5.2 | SecretID works once, then fails |
| **FR-11.4** Response wrapping | SECRETS §5.3 | Wrapped token delivers SecretID |
| **FR-12.1** Personal secret namespace | SECRETS §4.1 | User has `personal/<entity-id>/*` |
| **FR-12.4** Cross-user isolation | SECRETS §6.2 | User A can't read User B's secrets |
| **FR-13.1** Group → shared secrets | SECRETS §5.1, §6.4 | Group members access same path |
| **FR-14.1** Secrets browser UI | SECRETS §7.1 | Portal shows secret tree |
| **FR-14.2** Masked values | SECRETS §7.2 | Values show •••, reveal on click |
| **FR-14.7** Rate limiting | SECRETS §7.2 | 61st read/min → 429 |
| **NFR-1.2** Auto-unseal | SECRETS §2.3 | OpenBao auto-unseals on restart |
| **NFR-1.3** Root token revoked | SECRETS §2.2 | Root token revoked after setup |
| **NFR-1.4** Immutable audit | SECRETS §2.4 | Audit log contains all operations |
| **NFR-1.9** Network segmentation | SECRETS §1.3, AUTH §1.2 | Firewall rules verified |
| **NFR-2.1** Access token 5 min | AUTH §2.2 | Token expires after 300s |
| **NFR-2.7** Refresh token rotation | AUTH §2.2, §5.4 | Each refresh issues new token |
| **NFR-3.2** Idempotent bootstrap | OPS §1.4 | Run twice → no errors, no dupes |
| **NFR-3.3** Declarative config | OPS §1.4 | All config in scripts |
| **NFR-3.4** Health checks | OPS §5.1 | Health endpoints return 200 |
| **NFR-4.1** Keycloak daily backup | OPS §3.1 | Cron job runs, backup exists |
| **NFR-4.2** OpenBao daily backup | OPS §3.2 | Cron job runs, snapshot exists |
| **NFR-4.3** Restore tested | OPS §3.3 | Quarterly restore test passes |
| **NFR-4.4** Unseal key escrow | SECRETS §2.1 | 5 shares in separate locations |
| **NFR-4.5** RTO 1 hour | OPS §3.4 | Restore completes within 1 hour |
| **NFR-4.6** RPO 24 hours | OPS §3.4 | Daily backups |
| **NFR-5.1** Realm key rotation | OPS §4.1 | Annual rotation with grace period |
| **NFR-5.2** Transit key rotation | OPS §4.2 | Versioned rotation |
| **NFR-5.3** AppRole SecretID rotation | OPS §4.3 | Quarterly rotation |
| **NFR-5.4** Client secret rotation | OPS §4.4 | Dual-active support |
| **NFR-5.5** Seal key rekey | OPS §4.5 | Documented ceremony |
| **NFR-6.1** Auth failure alerts | OPS §5.2 | Alert fires at threshold |
| **NFR-6.2** Privileged access alerts | OPS §5.2 | Alert on admin actions |
| **NFR-6.3** Seal event alerts | OPS §5.2 | Alert on 503 health |
| **NFR-6.5** Keycloak admin events exported | OPS §6.1 | Logs in aggregation |
| **NFR-6.6** Keycloak login events exported | OPS §6.1 | Logs in aggregation |
| **NFR-6.7** OpenBao audit exported | OPS §6.2 | Logs in aggregation |
| **NFR-6.8** Log aggregation pipeline | OPS §5.3 | Pipeline defined |
| **NFR-7.1** User migration no password reset | OPS §2.5 | Users login after migration |
| **NFR-7.2** .env migration zero downtime | OPS §2.2 | Services work during migration |
| **NFR-7.3** Trading → Keycloak | OPS §2.3 | Trading validates KC JWTs |
| **NFR-7.4** Streams → Keycloak | OPS §2.3 | Synapse delegates to KC |
