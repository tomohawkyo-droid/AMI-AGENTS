# Secrets Management: Technical Specification

**Date:** 2026-03-01
**Status:** DRAFT
**Type:** Specification
**Parent:** [SPEC-IAM.md](SPEC-IAM.md)
**Requirements:** FR-10 through FR-14, NFR-1

---

## 1. OpenBao Server Configuration

### 1.1 Deployment

OpenBao runs as a Docker container managed by systemd, using Raft integrated storage.

```yaml
# docker-compose.openbao.yml
services:
  openbao:
    image: openbao/openbao:2.4.4
    container_name: ami-openbao
    command: server
    ports:
      - "8200:8200"
    environment:
      BAO_ADDR: "http://127.0.0.1:8200"
      BAO_API_ADDR: "http://localhost:8200"
      BAO_CLUSTER_ADDR: "http://localhost:8201"
    volumes:
      - openbao_data:/var/lib/openbao/data
      - ./openbao/config.hcl:/etc/openbao.d/config.hcl:ro
      - ./openbao/tls:/etc/openbao.d/tls:ro
    cap_add:
      - IPC_LOCK
    healthcheck:
      test: ["CMD", "bao", "status", "-address=http://127.0.0.1:8200"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  openbao_data:
```

### 1.2 Server Configuration (`config.hcl`)

```hcl
# /etc/openbao.d/config.hcl

cluster_name = "ami-openbao"

# Raft integrated storage, single node, no HA for initial deployment
storage "raft" {
  path    = "/var/lib/openbao/data"
  node_id = "ami-openbao-1"
}

# TCP listener: TLS disabled initially (behind reverse proxy)
# Production: enable TLS directly
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = true
  # Production TLS:
  # tls_cert_file = "/etc/openbao.d/tls/tls.crt"
  # tls_key_file  = "/etc/openbao.d/tls/tls.key"
  # tls_min_version = "tls12"
}

# API and cluster addresses
api_addr     = "http://localhost:8200"
cluster_addr = "http://localhost:8201"

# UI
ui = true

# Telemetry: Prometheus scrape endpoint
telemetry {
  prometheus_retention_time    = "30s"
  disable_hostname             = true
  unauthenticated_metrics_access = false
}

# Logging
log_level = "info"

# Default lease TTL
default_lease_ttl = "1h"
max_lease_ttl     = "24h"
```

### 1.3 Network Topology

| Service | Address | Port | Access |
|---------|---------|------|--------|
| OpenBao API | `localhost` | `8200` | Application backends only (NFR-1.9) |
| OpenBao Cluster | `localhost` | `8201` | Inter-node (future HA) |
| Health Check | `/v1/sys/health` | `8200` | Monitoring |
| Metrics | `/v1/sys/metrics` | `8200` | Prometheus (authenticated) |

> **NFR-1.9**: OpenBao MUST be reachable only from application backends, NOT from end users or the public internet. Firewall rules MUST restrict port 8200 to the application network.

---

## 2. Initialization & Unsealing

### 2.1 Shamir Secret Sharing (NFR-1.3)

Initial setup uses Shamir's Secret Sharing with 5 key shares and threshold of 3:

```bash
bao operator init \
  -key-shares=5 \
  -key-threshold=3 \
  -format=json > /secure/init-output.json
```

Output:
```json
{
  "unseal_keys_b64": ["share1", "share2", "share3", "share4", "share5"],
  "root_token": "hvs.XXXXXXXXXXXXXXXXXXXXX"
}
```

**Key distribution** (NFR-4.4): Each share MUST be stored in a separate physical/logical location. Minimum 3-of-5 split.

| Share | Holder | Storage |
|-------|--------|---------|
| Share 1 | Platform Engineer A | Hardware security device |
| Share 2 | Platform Engineer B | Encrypted USB |
| Share 3 | Security Lead | Password manager (separate) |
| Share 4 | CTO / Tech Lead | Hardware security device |
| Share 5 | Offline backup | Sealed envelope, physical safe |

### 2.2 Root Token Revocation (NFR-1.3)

After initial setup is complete (engines mounted, policies created, auth methods configured), the root token MUST be revoked:

```bash
bao token revoke <root-token>
```

Emergency access uses `bao operator generate-root` with Shamir key holders (see SPECIFICATION-OPERATIONS.md Section 7).

### 2.3 Auto-Unseal (NFR-1.2)

For production, transit auto-unseal using a second OpenBao instance:

```hcl
seal "transit" {
  address   = "https://unseal-openbao:8200"
  token     = "<orphan-token-with-transit-access>"
  key_name  = "ami-autounseal"
  mount_path = "transit/"
}
```

The unseal OpenBao instance is a minimal install with only the transit engine. Its sole purpose is holding the auto-unseal key.

> **Note**: For single-host deployment, TPM-based unseal or a simple systemd timer that provides unseal keys from encrypted storage MAY be used as an alternative.

### 2.4 Audit Devices (NFR-1.4)

Two audit devices MUST be enabled:

```bash
# File audit (primary)
bao audit enable file \
  file_path=/var/log/openbao/audit.log \
  mode=0600 \
  format=json \
  log_raw=false \
  hmac_accessor=true

# Stdout audit: for Docker log driver → log aggregation
bao audit enable -path=stdout file \
  file_path=stdout \
  format=json \
  log_raw=false
```

Every secret read/write/delete is logged (NFR-1.4, FR-10.5). Audit log entries include:
- Timestamp
- Operation (create, read, update, delete, list)
- Path accessed
- Client token accessor (HMAC'd)
- Remote address
- Request/response (sensitive values HMAC'd)

---

## 3. Secrets Engines

### 3.1 KV v2 (FR-12, FR-13)

KV v2 provides versioned secret storage with soft-delete and metadata.

#### Mount Points

```bash
# Platform service secrets
bao secrets enable -path=platform/secrets/service -description="Platform service secrets" kv-v2

# Platform infrastructure secrets
bao secrets enable -path=platform/secrets/infra -description="Infrastructure secrets" kv-v2

# Per-tenant mounts (created per org during bootstrap)
bao secrets enable -ns=tenants/acme-corp -path=secrets/service kv-v2
bao secrets enable -ns=tenants/acme-corp -path=secrets/team kv-v2
bao secrets enable -ns=tenants/acme-corp -path=secrets/personal kv-v2
```

#### Engine Configuration

```bash
# Set max versions and auto-cleanup
bao write platform/secrets/service/config \
  max_versions=20 \
  delete_version_after=365d \
  cas_required=false
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `max_versions` | 20 | Reasonable history depth |
| `delete_version_after` | 365d | Auto-purge old versions |
| `cas_required` | false | CAS optional (per-secret) |

### 3.2 Transit Engine

Encryption-as-a-service for application-level encryption:

```bash
bao secrets enable -path=platform/transit -description="Encryption service" transit

# Create encryption key for portal data
bao write platform/transit/keys/portal-data \
  type=aes256-gcm96 \
  exportable=false \
  allow_plaintext_backup=false

# Create signing key for tokens
bao write platform/transit/keys/token-signing \
  type=ed25519 \
  exportable=false
```

API operations:
```
POST /v1/platform/transit/encrypt/portal-data    # encrypt data
POST /v1/platform/transit/decrypt/portal-data    # decrypt data
POST /v1/platform/transit/keys/portal-data/rotate # rotate key (old versions kept)
POST /v1/platform/transit/rewrap/portal-data     # re-encrypt with latest key
```

### 3.3 PKI Engine

Internal certificate authority for service-to-service TLS:

```bash
# Root CA (long-lived, rarely used)
bao secrets enable -path=platform/pki -description="Root CA" pki
bao secrets tune -max-lease-ttl=87600h platform/pki

# Generate root CA
bao write platform/pki/root/generate/internal \
  common_name="AMI Platform Root CA" \
  ttl=87600h \
  key_type=rsa \
  key_bits=4096

# Intermediate CA (for issuing)
bao secrets enable -path=platform/pki_int -description="Intermediate CA" pki
bao secrets tune -max-lease-ttl=43800h platform/pki_int

# Generate intermediate CSR
bao write platform/pki_int/intermediate/generate/internal \
  common_name="AMI Platform Intermediate CA"

# Sign with root, import, configure CRL
# (see SPECIFICATION-OPERATIONS.md for full procedure)

# Create issuance role
bao write platform/pki_int/roles/internal-service \
  allowed_domains="ami.local,192.168.50.0/24" \
  allow_subdomains=true \
  allow_ip_sans=true \
  max_ttl=720h \
  ttl=168h \
  key_type=rsa \
  key_bits=2048
```

---

## 4. Namespace Hierarchy (FR-5.5)

### 4.1 Structure

```
root (/)
  │
  ├── platform/                          Platform-level secrets & engines
  │     ├── secrets/service/             KV v2: platform service secrets
  │     ├── secrets/infra/               KV v2: infrastructure secrets
  │     ├── pki/                         PKI: root CA
  │     ├── pki_int/                     PKI: intermediate CA
  │     └── transit/                     Transit: encryption-as-a-service
  │
  └── tenants/
        ├── acme-corp/                   Namespace: tenant isolation
        │     ├── secrets/service/       KV v2: tenant service secrets
        │     ├── secrets/team/          KV v2: team shared secrets
        │     │     ├── data/backend-team/*
        │     │     ├── data/ops-team/*
        │     │     └── data/frontend-team/*
        │     ├── secrets/personal/      KV v2: user personal vaults
        │     │     ├── data/<entity-id-1>/*
        │     │     └── data/<entity-id-2>/*
        │     └── pki/                   PKI: tenant-scoped certificates
        │
        └── globex-inc/                  Namespace
              ├── secrets/service/
              ├── secrets/team/
              └── secrets/personal/
```

### 4.2 Namespace Operations

```bash
# Create platform namespace
bao namespace create platform

# Create tenant namespaces
bao namespace create tenants
bao namespace create -ns=tenants acme-corp
bao namespace create -ns=tenants globex-inc

# Mount engines in tenant namespace
bao secrets enable -ns=tenants/acme-corp -path=secrets/service kv-v2
bao secrets enable -ns=tenants/acme-corp -path=secrets/team kv-v2
bao secrets enable -ns=tenants/acme-corp -path=secrets/personal kv-v2
```

### 4.3 Tenant Provisioning

When a new organization is created in Keycloak, the bootstrap process MUST:

1. Create the tenant namespace: `tenants/<org-slug>`
2. Mount KV v2 engines: `secrets/service`, `secrets/team`, `secrets/personal`
3. Create role-based policies scoped to the namespace
4. Create external identity groups for Keycloak group → OpenBao policy mapping

---

## 5. Auth Methods

### 5.1 JWT Auth (Keycloak JWKS)

For human users authenticating via the portal:

```bash
# Enable JWT auth
bao auth enable jwt

# Configure with Keycloak JWKS
bao write auth/jwt/config \
  jwks_url="http://localhost:8082/realms/ami/protocol/openid-connect/certs" \
  bound_issuer="http://localhost:8082/realms/ami" \
  default_role="portal-user"
```

#### JWT Roles

```bash
# Platform admin role
bao write auth/jwt/role/platform-admin \
  user_claim="sub" \
  groups_claim="groups" \
  bound_audiences="ami-portal" \
  bound_claims='{"realm_access.roles":"platform-admin"}' \
  token_policies="platform-admin" \
  token_ttl=300 \
  token_max_ttl=600

# Organization user role (policies via identity groups)
bao write auth/jwt/role/portal-user \
  user_claim="sub" \
  groups_claim="groups" \
  bound_audiences="ami-portal" \
  claim_mappings='{"tenant_id":"tenant_id"}' \
  token_policies="" \
  token_ttl=300 \
  token_max_ttl=300
```

#### External Identity Groups

Keycloak groups map to OpenBao policies via external identity groups:

```bash
# 1. Get JWT auth mount accessor
JWT_ACCESSOR=$(bao auth list -format=json | jq -r '.["jwt/"].accessor')

# 2. Create external group for Keycloak group
bao write identity/group \
  name="acme-corp-backend-team" \
  type="external" \
  policies="developer,team-backend-secrets"

# 3. Create group alias linking Keycloak group to OpenBao group
bao write identity/group-alias \
  name="backend-team" \
  mount_accessor="$JWT_ACCESSOR" \
  canonical_id="<group-id-from-step-2>"
```

When a user authenticates with a JWT containing `groups: ["backend-team"]`, OpenBao resolves the external group alias, applies the group's policies, and issues a token with those policies attached.

### 5.2 AppRole Auth (Service Identities)

For machine-to-machine authentication:

```bash
# Enable AppRole
bao auth enable approle

# Portal backend service
bao write auth/approle/role/svc-platform-core \
  bind_secret_id=true \
  secret_id_num_uses=0 \
  secret_id_ttl=86400 \
  token_ttl=300 \
  token_max_ttl=600 \
  token_policies="svc-platform-core" \
  token_bound_cidrs="192.168.50.0/24"

# CI/CD deployer (single-use SecretIDs, FR-5.7.6)
bao write auth/approle/role/svc-cicd-deployer \
  bind_secret_id=true \
  secret_id_num_uses=1 \
  secret_id_ttl=300 \
  token_ttl=300 \
  token_max_ttl=600 \
  token_policies="svc-cicd-deployer" \
  token_bound_cidrs="192.168.50.0/24"
```

### 5.3 Response Wrapping (FR-11.4)

SecretIDs for services are delivered via response wrapping (single-use wrapped tokens):

```bash
# Generate wrapped SecretID (bootstrap delivers this to the service)
bao write -wrap-ttl=300 -f auth/approle/role/svc-platform-core/secret-id

# Service unwraps to get actual SecretID
bao unwrap <wrapping-token>
```

The wrapping token is single-use and expires after the TTL. This prevents secret interception during delivery.

---

## 6. Policy Definitions

### 6.1 Human Role Policies

#### `policy/platform-superadmin.hcl`
```hcl
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
```

#### `policy/platform-admin.hcl`
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
path "sys/mounts/*" {
  capabilities = ["deny"]
}
```

#### `policy/platform-operator.hcl`
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

### 6.2 Organization Role Policies (Applied in Tenant Namespace)

#### `policy/org-admin.hcl`
```hcl
path "secrets/service/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secrets/team/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secrets/personal/+/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/+/metadata/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/{{identity.entity.id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "pki/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

#### `policy/team-lead.hcl`
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

#### `policy/developer.hcl`
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

#### `policy/member.hcl`
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

#### `policy/viewer.hcl`
```hcl
path "secrets/personal/{{identity.entity.id}}/data/*" {
  capabilities = ["read", "list"]
}
path "secrets/personal/{{identity.entity.id}}/metadata/*" {
  capabilities = ["read", "list"]
}
```

#### `policy/guest.hcl`
```hcl
path "secrets/personal/{{identity.entity.id}}/data/*" {
  capabilities = ["read"]
}
```

### 6.3 Service Identity Policies

#### `policy/svc-platform-core.hcl`
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

#### `policy/svc-platform-infra.hcl`
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

#### `policy/svc-cicd-deployer.hcl`
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

#### `policy/svc-tenant-app.hcl` (Per-tenant, in namespace)
```hcl
path "secrets/service/data/*" {
  capabilities = ["read"]
}
path "secrets/service/metadata/*" {
  capabilities = ["read", "list"]
}
```

### 6.4 Team Secret Policies

Team secrets use **per-group policies** assigned to external groups, NOT templated policies:

```hcl
# policy/team-backend-team-secrets.hcl
# Assigned to external group "backend-team"
path "secrets/team/data/backend-team/*" {
  capabilities = ["create", "read", "update", "delete"]
}
path "secrets/team/metadata/backend-team/*" {
  capabilities = ["list", "read", "delete"]
}
```

The bootstrap script creates one such policy per Keycloak group and maps it via external group aliases on the JWT auth mount.

---

## 7. Portal Secrets UI: API Contract (FR-14)

The portal acts as a proxy between the browser and OpenBao. Secret values are **never stored in the portal**, read-through only. The OpenBao token is held server-side (NFR-2.6).

### 7.1 API Routes

All routes require authentication. The portal obtains a scoped OpenBao token by presenting the user's Keycloak JWT to OpenBao's JWT auth method.

#### List Secrets

```
GET /api/secrets?path=<kv-path>&namespace=<ns>

Response 200:
{
  "keys": ["database/", "api-keys/", "credentials"],
  "path": "secrets/team/metadata/backend-team"
}
```

#### Read Secret

```
GET /api/secrets/data?path=<kv-path>&namespace=<ns>&version=<n>

Response 200:
{
  "data": {
    "username": "admin",
    "password": "••••••••"   // Masked by default (FR-14.2)
  },
  "metadata": {
    "version": 3,
    "created_time": "2026-03-01T10:00:00Z",
    "deletion_time": "",
    "destroyed": false
  }
}
```

Secret values MUST be masked by default in the UI. Reveal on click (FR-14.2).

#### Write Secret

```
POST /api/secrets/data
Content-Type: application/json

{
  "path": "secrets/team/backend-team/database-creds",
  "namespace": "tenants/acme-corp",
  "data": {
    "username": "app_user",
    "password": "new-password"
  },
  "cas": 3  // Optional: Check-And-Set version
}

Response 200:
{
  "version": 4,
  "created_time": "2026-03-01T10:05:00Z"
}
```

#### Delete Secret (Soft Delete)

```
DELETE /api/secrets/data?path=<kv-path>&namespace=<ns>&versions=1,2,3

Response 204
```

#### Version History (FR-14.4)

```
GET /api/secrets/metadata?path=<kv-path>&namespace=<ns>

Response 200:
{
  "versions": {
    "1": { "created_time": "...", "deletion_time": "", "destroyed": false },
    "2": { "created_time": "...", "deletion_time": "...", "destroyed": false },
    "3": { "created_time": "...", "deletion_time": "", "destroyed": false }
  },
  "current_version": 3,
  "max_versions": 20,
  "oldest_version": 1,
  "custom_metadata": null
}
```

### 7.2 Security Constraints

| Constraint | Implementation | Requirement |
|------------|---------------|-------------|
| Values masked by default | UI renders `••••••••`, reveals on click | FR-14.2 |
| Copy-to-clipboard | `navigator.clipboard.writeText()`, NOT innerHTML | FR-14.3 |
| No dangerouslySetInnerHTML | React JSX escaping for all secret values | FR-14.6 |
| Rate limiting | 60 reads/min, 30 writes/min per user | FR-14.7 |
| No client-side caching | `Cache-Control: no-store` on all secret responses | NFR-1.5 |
| No logging of values | Secret values MUST NOT appear in server logs | NFR-1.5 |
| CSRF protection | NextAuth CSRF for auth routes; custom token for secrets routes | NFR-1.7 |
| CSP headers | `script-src 'self'; style-src 'self' 'unsafe-inline'` | NFR-1.8 |
| OpenBao token server-side | Token stored in server memory, never sent to browser | NFR-2.6 |

### 7.3 OpenBao Token Lifecycle (Portal)

```
1. User authenticates to portal via Keycloak (NextAuth OIDC)
2. Portal backend has user's Keycloak access token (from JWT callback)
3. On first secret request:
   a. POST /v1/auth/jwt/login with user's Keycloak JWT
   b. OpenBao validates JWT against Keycloak JWKS
   c. OpenBao returns scoped token (TTL: 5 min)
   d. Portal stores token in server-side per-session cache
4. On subsequent requests within TTL:
   a. Use cached OpenBao token
5. On token expiry:
   a. Re-authenticate with current Keycloak JWT
   b. If Keycloak JWT expired, refresh it first
6. On user logout:
   a. Revoke OpenBao token
   b. Clear server-side cache
```

---

## 8. Dynamic Credentials (FR-10.4)

### 8.1 Database Secrets Engine

Dynamic database credentials are generated on-demand and automatically revoked after TTL:

```bash
# Enable database engine
bao secrets enable -path=platform/database database

# Configure PostgreSQL connection
bao write platform/database/config/ami-portal-db \
  plugin_name=postgresql-database-plugin \
  connection_url="postgresql://{{username}}:{{password}}@localhost:5432/ami_portal" \
  allowed_roles="app-readonly,app-readwrite" \
  username="openbao_admin" \
  password="<admin-password>"

# Create read-only role
bao write platform/database/roles/app-readonly \
  db_name=ami-portal-db \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  revocation_statements="REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM \"{{name}}\"; DROP ROLE IF EXISTS \"{{name}}\";" \
  default_ttl=1h \
  max_ttl=24h

# Create read-write role
bao write platform/database/roles/app-readwrite \
  db_name=ami-portal-db \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  revocation_statements="REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM \"{{name}}\"; DROP ROLE IF EXISTS \"{{name}}\";" \
  default_ttl=1h \
  max_ttl=24h
```

### 8.2 Requesting Dynamic Credentials

```bash
# Application requests credentials at runtime
bao read platform/database/creds/app-readonly

# Response:
# Key             Value
# ---             -----
# lease_id        platform/database/creds/app-readonly/xxxxx
# lease_duration  1h
# username        v-approle-app-readonly-xxxxx
# password        <generated>
```

### 8.3 Lease Management (FR-10.7)

| Setting | Value | Rationale |
|---------|-------|-----------|
| Default TTL | 1h | FR-10.7 |
| Max TTL | 24h | FR-10.7 |
| Renewable | Yes | Applications can renew before expiry |

```bash
# Renew lease
bao lease renew <lease-id>

# Revoke lease (cleanup)
bao lease revoke <lease-id>
```

### 8.4 Supported Database Plugins

| Database | Plugin | Status |
|----------|--------|--------|
| PostgreSQL | `postgresql-database-plugin` | FR-10.4, primary |
| MySQL | `mysql-database-plugin` | FR-10.4, supported |
| MongoDB | `mongodb-database-plugin` | FR-10.4, supported |
| Redis | `redis-database-plugin` | FR-10.4, supported |

---

## 9. Requirement Traceability

| Requirement | Section | Status |
|-------------|---------|--------|
| FR-10.1 AppRole/JWT auth for services | 5.1, 5.2 | Specified |
| FR-10.2 Isolated service paths | 4.1 | Specified |
| FR-10.3 Secrets in OpenBao, not .env | 3.1, 4.1 | Specified |
| FR-10.4 Dynamic database credentials | 8 | Specified |
| FR-10.5 Full audit of secret access | 2.4 | Specified |
| FR-10.6 Service read+write to own namespace | 6.3, 6.4 | Specified |
| FR-10.7 Lease duration 1h/24h | 8.3 | Specified |
| FR-11.1 CI/CD AppRole with single-use SecretIDs | 5.2 | Specified |
| FR-11.2 Runtime credential retrieval | 8.2 | Specified |
| FR-11.3 Migrate .env to OpenBao | N/A | Deferred to SPEC-OPERATIONS |
| FR-11.4 Response wrapping for secret delivery | 5.3 | Specified |
| FR-11.5 SSH certificate signing | N/A | Future (PKI engine) |
| FR-12.1 Isolated personal namespace | 4.1 | Specified |
| FR-12.2 Personal secrets CRUD via portal | 7.1 | Specified |
| FR-12.3 Secret versioning (KV v2) | 3.1, 7.1 | Specified |
| FR-12.4 Cross-user isolation | 6.2 (identity-templated) | Specified |
| FR-12.5 Identity-templated policies | 6.2 | Specified |
| FR-13.1 Group → shared namespace mapping | 5.1, 6.4 | Specified |
| FR-13.2 External group → policy | 5.1, 6.4 | Specified |
| FR-13.3 Group members read/write | 6.4 | Specified |
| FR-13.4 Auto-reflect group changes | 5.1 (external groups) | Specified |
| FR-14.1 Secrets browser UI | 7.1 | Specified |
| FR-14.2 Masked values | 7.2 | Specified |
| FR-14.3 Copy-to-clipboard | 7.2 | Specified |
| FR-14.4 Version history | 7.1 | Specified |
| FR-14.5 Admin browse all accessible paths | 7.1 | Specified |
| FR-14.6 XSS prevention | 7.2 | Specified |
| FR-14.7 Rate limiting | 7.2 | Specified |
| NFR-1.1 TLS for inter-service | 1.2 | Specified (prod config) |
| NFR-1.2 Auto-unseal | 2.3 | Specified |
| NFR-1.3 Root token revocation | 2.2 | Specified |
| NFR-1.4 Immutable audit trail | 2.4 | Specified |
| NFR-1.5 No logging/caching secrets | 7.2 | Specified |
| NFR-1.6 No dev mode | 1.2 (server command) | Specified |
| NFR-1.9 Network segmentation | 1.3 | Specified |
