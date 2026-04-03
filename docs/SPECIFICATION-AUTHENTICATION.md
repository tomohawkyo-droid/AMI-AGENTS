# Authentication — Technical Specification

**Date:** 2026-03-01
**Status:** DRAFT
**Parent:** [SPECIFICATION-IAM.md](SPECIFICATION-IAM.md)
**Requirements:** FR-1 through FR-9, NFR-2

---

## 1. Deployment Topology

### 1.1 Container Configuration

Keycloak runs as a Docker container managed by systemd, backed by PostgreSQL.

```yaml
# docker-compose.keycloak.yml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:26.2
    container_name: ami-keycloak
    command: start-dev --import-realm
    ports:
      - "8082:8080"
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://keycloak-db:5432/keycloak
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: ${KEYCLOAK_DB_PASSWORD}
      KC_HEALTH_ENABLED: "true"
      KC_HTTP_ENABLED: "true"
      KC_PROXY_HEADERS: xforwarded
      KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN:-admin}
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    volumes:
      - ./keycloak/ami-realm.json:/opt/keycloak/data/import/ami-realm.json:ro
    depends_on:
      keycloak-db:
        condition: service_healthy

  keycloak-db:
    image: postgres:17-alpine
    container_name: keycloak-db
    environment:
      POSTGRES_DB: keycloak
      POSTGRES_USER: keycloak
      POSTGRES_PASSWORD: ${KEYCLOAK_DB_PASSWORD}
    volumes:
      - keycloak_db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U keycloak"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  keycloak_db_data:
```

### 1.2 Network Topology

| Service | Address | Port | Protocol |
|---------|---------|------|----------|
| Keycloak HTTP | `localhost` | `8082` | HTTP (TLS terminated at reverse proxy) |
| Keycloak Management | `localhost` | `9082` | HTTP (health/metrics) |
| PostgreSQL (KC) | `keycloak-db` (container) | `5432` | TCP |
| OIDC Issuer URL | `http://localhost:8082/realms/ami` | — | — |
| JWKS Endpoint | `http://localhost:8082/realms/ami/protocol/openid-connect/certs` | — | — |
| Admin Console | `http://localhost:8082/admin/` | — | — |

> **NFR-1.9**: The Admin Console (`/admin`) MUST be restricted to the management network. In production, reverse proxy rules MUST block `/admin/*` from public access.

### 1.3 Production Hardening (Future)

For production deployment, the `start-dev` command MUST be replaced with `start` and the following configured:

| Setting | Value | Notes |
|---------|-------|-------|
| `KC_HOSTNAME` | `auth.ami.example.com` | Public hostname |
| `KC_HOSTNAME_STRICT` | `true` | Reject mismatched Host headers |
| `KC_HTTPS_CERTIFICATE_FILE` | `/opt/keycloak/certs/tls.crt` | TLS certificate |
| `KC_HTTPS_CERTIFICATE_KEY_FILE` | `/opt/keycloak/certs/tls.key` | TLS private key |
| `KC_HTTP_ENABLED` | `false` | Disable plain HTTP |
| `KC_PROXY_HEADERS` | `xforwarded` | Trust X-Forwarded-* from reverse proxy |

---

## 2. Realm Configuration

### 2.1 Realm Identity

```json
{
  "realm": "ami",
  "enabled": true,
  "displayName": "AMI Platform",
  "registrationAllowed": false,
  "loginWithEmailAllowed": true,
  "duplicateEmailsAllowed": false,
  "resetPasswordAllowed": true,
  "editUsernameAllowed": false,
  "sslRequired": "external"
}
```

### 2.2 Token Lifespans (NFR-2)

| Parameter | JSON Field | Value | Rationale |
|-----------|-----------|-------|-----------|
| Access token | `accessTokenLifespan` | `300` (5 min) | NFR-2.1: Short-lived, forces refresh |
| SSO session idle | `ssoSessionIdleTimeout` | `1800` (30 min) | FR-2.1 |
| SSO session max | `ssoSessionMaxLifespan` | `36000` (10 hr) | FR-2.2 |
| Refresh token reuse | `revokeRefreshToken` | `true` | NFR-2.7: Rotation on each use |
| Refresh token max reuse | `refreshTokenMaxReuse` | `0` | One-time use only |
| Client session idle | `clientSessionIdleTimeout` | `1800` (30 min) | Aligned with SSO idle |
| Client session max | `clientSessionMaxLifespan` | `36000` (10 hr) | Aligned with SSO max |
| Offline session idle | `offlineSessionIdleTimeout` | `2592000` (30 days) | Offline access scope |
| Remember-me idle | `ssoSessionIdleTimeoutRememberMe` | `604800` (7 days) | Extended for remember-me |
| Remember-me max | `ssoSessionMaxLifespanRememberMe` | `2592000` (30 days) | Extended for remember-me |

```json
{
  "accessTokenLifespan": 300,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 36000,
  "revokeRefreshToken": true,
  "refreshTokenMaxReuse": 0,
  "clientSessionIdleTimeout": 1800,
  "clientSessionMaxLifespan": 36000,
  "offlineSessionIdleTimeout": 2592000,
  "ssoSessionIdleTimeoutRememberMe": 604800,
  "ssoSessionMaxLifespanRememberMe": 2592000
}
```

> **Current deviation**: The existing realm export sets `accessTokenLifespan: 3600` (1 hour). This MUST be reduced to `300` (5 minutes) per NFR-2.1.

### 2.3 Brute Force Protection (FR-8)

```json
{
  "bruteForceProtected": true,
  "permanentLockout": false,
  "failureFactor": 5,
  "waitIncrementSeconds": 60,
  "maxFailureWaitSeconds": 900,
  "minimumQuickLoginWaitSeconds": 60,
  "quickLoginCheckMilliSeconds": 1000,
  "maxDeltaTimeSeconds": 43200
}
```

| Setting | Value | Requirement |
|---------|-------|-------------|
| Max failures before lockout | 5 | FR-8.2 |
| Max lockout duration | 900s (15 min) | FR-8.3 |
| Quick login check window | 1000ms | FR-8.4 |
| Wait increment (progressive) | 60s per failure | FR-8.3 |
| Failure tracking window | 43200s (12 hr) | Prevents permanent accumulation |

### 2.4 Password Policy (FR-6)

```json
{
  "passwordPolicy": "length(12) and notCompromised and passwordHistory(5) and notUsername"
}
```

| Policy | Value | Requirement |
|--------|-------|-------------|
| Minimum length | 12 characters | FR-6.1 |
| Breached password check | `notCompromised` (HIBP API) | FR-6.2 |
| No forced rotation | Omitted from policy | FR-6.3 (NIST 800-63B) |
| History | Last 5 passwords | FR-6.4 |
| Not username | `notUsername` | Best practice |

> **Note**: `forceExpiredPasswordChange` is intentionally omitted per FR-6.3 / NIST 800-63B guidance against forced periodic rotation.

### 2.5 Multi-Factor Authentication (FR-7)

#### Required Actions

```json
{
  "requiredActions": [
    {
      "alias": "CONFIGURE_TOTP",
      "name": "Configure OTP",
      "providerId": "CONFIGURE_TOTP",
      "enabled": true,
      "defaultAction": false,
      "priority": 20
    },
    {
      "alias": "webauthn-register",
      "name": "WebAuthn Register",
      "providerId": "webauthn-register",
      "enabled": true,
      "defaultAction": false,
      "priority": 30
    }
  ]
}
```

#### OTP Policy

```json
{
  "otpPolicyType": "totp",
  "otpPolicyAlgorithm": "HmacSHA1",
  "otpPolicyDigits": 6,
  "otpPolicyPeriod": 30,
  "otpPolicyInitialCounter": 0,
  "otpPolicyLookAheadWindow": 1,
  "otpSupportedApplications": ["totpAppGoogleName", "totpAppMicrosoftAuthenticatorName"]
}
```

#### WebAuthn Policy

```json
{
  "webAuthnPolicyRpEntityName": "AMI Platform",
  "webAuthnPolicyAttestationConveyancePreference": "none",
  "webAuthnPolicyAuthenticatorAttachment": "not specified",
  "webAuthnPolicyRequireResidentKey": "not specified",
  "webAuthnPolicyUserVerificationRequirement": "preferred",
  "webAuthnPolicySignatureAlgorithms": ["ES256"]
}
```

#### MFA Enforcement by Role (FR-7.3)

| Role | MFA Requirement | Implementation |
|------|----------------|----------------|
| `platform-superadmin` | **Required** | `CONFIGURE_TOTP` set as required action on user |
| `platform-admin` | **Required** | `CONFIGURE_TOTP` set as required action on user |
| `platform-operator` | Recommended | Prompted but skippable |
| `org-admin` | **Required** | `CONFIGURE_TOTP` set as required action on user |
| `team-lead` | Recommended | Prompted but skippable |
| All others | Optional | User self-service via account console |

MFA enforcement is applied via Keycloak required actions on the user entity when admin roles are assigned. The bootstrap script MUST set `CONFIGURE_TOTP` as a required action for users with `platform-superadmin`, `platform-admin`, or `org-admin` roles.

### 2.6 Session Limits (FR-2)

```json
{
  "maxRealmSessions": -1,
  "maxClientSessions": -1
}
```

Concurrent session limiting (FR-2.3) requires the **User Session Limits** authentication flow execution. Configuration:

| Setting | Value |
|---------|-------|
| Max sessions per user | 5 |
| Behavior on limit | `terminateOldest` |
| Error message | `sessionLimitExceeded` |

This is configured via the Authentication → Browser Flow → User Session Limits step.

### 2.7 Event Configuration (NFR-6.5, NFR-6.6)

```json
{
  "eventsEnabled": true,
  "adminEventsEnabled": true,
  "adminEventsDetailsEnabled": true,
  "eventsExpiration": 2592000,
  "eventsListeners": ["jboss-logging"],
  "enabledEventTypes": [
    "LOGIN", "LOGIN_ERROR",
    "LOGOUT", "LOGOUT_ERROR",
    "REGISTER", "REGISTER_ERROR",
    "CODE_TO_TOKEN", "CODE_TO_TOKEN_ERROR",
    "CLIENT_LOGIN", "CLIENT_LOGIN_ERROR",
    "REFRESH_TOKEN", "REFRESH_TOKEN_ERROR",
    "VALIDATE_ACCESS_TOKEN",
    "INTROSPECT_TOKEN",
    "UPDATE_PASSWORD", "UPDATE_PASSWORD_ERROR",
    "SEND_RESET_PASSWORD", "SEND_RESET_PASSWORD_ERROR",
    "VERIFY_EMAIL", "VERIFY_EMAIL_ERROR",
    "CUSTOM_REQUIRED_ACTION",
    "UPDATE_TOTP", "REMOVE_TOTP",
    "GRANT_CONSENT", "REVOKE_GRANT",
    "IMPERSONATE",
    "DELETE_ACCOUNT",
    "FEDERATED_IDENTITY_LINK", "REMOVE_FEDERATED_IDENTITY_LINK"
  ]
}
```

Event retention: 30 days (`2592000` seconds). Events are exported to central logging via the `jboss-logging` listener (stdout → Docker log driver → log aggregation pipeline).

### 2.8 Security Headers

Keycloak 26 configures security headers at the realm level:

```json
{
  "browserSecurityHeaders": {
    "contentSecurityPolicy": "frame-src 'self'; frame-ancestors 'self' https://localhost:3000; object-src 'none';",
    "contentSecurityPolicyReportOnly": "",
    "xContentTypeOptions": "nosniff",
    "xRobotsTag": "none",
    "xFrameOptions": "SAMEORIGIN",
    "xXSSProtection": "1; mode=block",
    "strictTransportSecurity": "max-age=31536000; includeSubDomains"
  }
}
```

The `frame-ancestors` directive MUST include the Portal origin to allow embedding the Keycloak account console in iframes if needed.

---

## 3. Roles & Groups

### 3.1 Realm Roles (Platform-Scoped)

Realm roles represent platform-wide privileges. Composite roles inherit child role permissions automatically.

```json
{
  "roles": {
    "realm": [
      {
        "name": "platform-superadmin",
        "description": "Break-glass role. Max 2-3 humans. All permissions.",
        "composite": true,
        "composites": {
          "realm": ["platform-admin"]
        }
      },
      {
        "name": "platform-admin",
        "description": "Day-to-day platform administration. Cannot modify realm keys.",
        "composite": true,
        "composites": {
          "realm": ["platform-operator"]
        }
      },
      {
        "name": "platform-operator",
        "description": "Monitoring and triage. Read-heavy, limited write.",
        "composite": false
      }
    ]
  }
}
```

Composite chain: `platform-superadmin` → `platform-admin` → `platform-operator`. A user with `platform-superadmin` automatically holds all three roles.

#### Legacy Role Aliases (FR-5.8)

During migration, legacy roles MUST coexist with new roles:

| Legacy Role | Maps To | Implementation |
|-------------|---------|----------------|
| `admin` | `platform-superadmin` | Composite including `platform-superadmin` |
| `editor` | `developer` | Composite including `developer` client role |
| `viewer` | `viewer` | Renamed, same permissions |
| `guest` | `guest` | Renamed, same permissions |

Legacy roles are realm roles that compose to new roles. `resolvePermissions()` in the portal MUST accept both legacy and new role names until legacy roles are deprecated.

### 3.2 Client Roles (Organization-Scoped)

Organization-scoped roles are defined as client roles on the `ami-portal` client:

```json
{
  "clients": [
    {
      "clientId": "ami-portal",
      "roles": [
        { "name": "org-admin", "description": "Full control within own organization" },
        { "name": "team-lead", "description": "Manages team access and secrets" },
        { "name": "developer", "description": "Active contributor, service secret access" },
        { "name": "member", "description": "Standard organization member" },
        { "name": "viewer", "description": "Read-only access" },
        { "name": "guest", "description": "Minimal access, external collaborators" }
      ]
    }
  ]
}
```

These roles are assigned within the context of organization membership. A user receives `ami-portal:org-admin` scoped to their organization.

### 3.3 Groups (Team Mapping)

Groups map to both role assignments and OpenBao team secret namespaces:

```
Groups:
  /platform-ops                    → realm role: platform-operator
  /acme-corp
    /acme-corp/admins              → client role: ami-portal:org-admin
    /acme-corp/ops-team            → client role: ami-portal:team-lead
    /acme-corp/backend-team        → client role: ami-portal:developer
    /acme-corp/frontend-team       → client role: ami-portal:developer
  /globex-inc
    /globex-inc/admins             → client role: ami-portal:org-admin
    /globex-inc/engineering        → client role: ami-portal:developer
```

Group role assignments use Keycloak's group-level role mappings. Users inherit roles from group membership. Adding a user to `/acme-corp/ops-team` automatically grants `ami-portal:team-lead`.

### 3.4 Organizations (Keycloak 26+ — FR-5.5)

Multi-tenancy uses Keycloak's native Organizations feature (single realm, not realm-per-tenant):

```
POST /admin/realms/ami/organizations

{
  "name": "Acme Corporation",
  "alias": "acme-corp",
  "enabled": true,
  "domains": [
    { "name": "acme-corp.com", "verified": false }
  ]
}
```

Organization membership is managed via the Organizations API:

```
POST /admin/realms/ami/organizations/{org-id}/members
{ "id": "user-uuid" }
```

Benefits over realm-per-tenant:
- Single user identity across organizations
- No performance degradation at scale
- Cross-org user movement without re-provisioning
- Simpler administration

### 3.5 Protocol Mappers

The following protocol mappers MUST be configured on the `ami-portal` client (and any client that authenticates to OpenBao):

#### Group Membership Mapper

```json
{
  "name": "group-membership",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-group-membership-mapper",
  "config": {
    "full.path": "false",
    "claim.name": "groups",
    "id.token.claim": "true",
    "access.token.claim": "true",
    "userinfo.token.claim": "true"
  }
}
```

> **Critical**: `full.path` MUST be `false`. OpenBao external group aliases match on group name, not full path.

#### Realm Roles Mapper

```json
{
  "name": "realm-roles",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-usermodel-realm-role-mapper",
  "config": {
    "multivalued": "true",
    "claim.name": "roles",
    "id.token.claim": "true",
    "access.token.claim": "true",
    "userinfo.token.claim": "true",
    "jsonType.label": "String"
  }
}
```

#### Client Roles Mapper

```json
{
  "name": "client-roles",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-usermodel-client-role-mapper",
  "config": {
    "multivalued": "true",
    "claim.name": "resource_access.${client_id}.roles",
    "id.token.claim": "true",
    "access.token.claim": "true",
    "userinfo.token.claim": "false",
    "jsonType.label": "String"
  }
}
```

#### Audience Resolve Mapper

```json
{
  "name": "audience-resolve",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-audience-resolve-mapper",
  "config": {
    "access.token.claim": "true"
  }
}
```

#### Tenant ID Mapper

```json
{
  "name": "tenant-id",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-usermodel-attribute-mapper",
  "config": {
    "user.attribute": "tenant_id",
    "claim.name": "tenant_id",
    "id.token.claim": "true",
    "access.token.claim": "true",
    "jsonType.label": "String"
  }
}
```

### 3.6 Expected Access Token Structure

After all mappers are configured, a Keycloak-issued access token for an authenticated user MUST contain:

```json
{
  "exp": 1709337600,
  "iat": 1709337300,
  "iss": "http://localhost:8082/realms/ami",
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "aud": ["ami-portal", "ami-trading"],
  "azp": "ami-portal",
  "realm_access": {
    "roles": ["platform-operator"]
  },
  "resource_access": {
    "ami-portal": {
      "roles": ["developer"]
    }
  },
  "groups": ["backend-team"],
  "tenant_id": "acme-corp",
  "organization": {
    "acme-corp": {
      "id": "org-uuid"
    }
  },
  "scope": "openid email profile",
  "email": "user@acme-corp.com",
  "preferred_username": "jdoe",
  "name": "Jane Doe"
}
```

The portal's JWT callback extracts `realm_access.roles`, `resource_access.ami-portal.roles`, `groups`, and `tenant_id` from this structure.

---

## 4. Client Configurations

### 4.1 AMI-Portal (Confidential Client)

The Portal is a **confidential** OIDC client with service account enabled for Keycloak Admin API access.

```json
{
  "clientId": "ami-portal",
  "name": "AMI Portal",
  "enabled": true,
  "protocol": "openid-connect",
  "publicClient": false,
  "clientAuthenticatorType": "client-secret",
  "standardFlowEnabled": true,
  "implicitFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": true,
  "redirectUris": [
    "https://localhost:3000/api/auth/callback/keycloak",
    "http://localhost:3000/api/auth/callback/keycloak"
  ],
  "webOrigins": [
    "https://localhost:3000",
    "http://localhost:3000"
  ],
  "defaultClientScopes": ["openid", "profile", "email", "roles"],
  "optionalClientScopes": ["offline_access"],
  "attributes": {
    "pkce.code.challenge.method": "S256",
    "backchannel.logout.session.required": "true",
    "backchannel.logout.url": "https://localhost:3000/api/auth/backchannel-logout",
    "post.logout.redirect.uris": "https://localhost:3000",
    "access.token.lifespan": "300"
  }
}
```

#### Service Account Realm-Management Roles

The Portal's service account MUST be assigned these `realm-management` client roles to power the Account Manager UI:

| Role | Purpose |
|------|---------|
| `manage-users` | Create, update, delete users; reset passwords |
| `view-users` | List and search users |
| `manage-clients` | Create, update, delete OAuth clients |
| `view-clients` | List OAuth clients |
| `view-realm` | Read realm configuration |
| `view-identity-providers` | List configured IdPs for the Add Account dialog |
| `manage-identity-providers` | Create/update IdPs via bootstrap |

These are assigned by the bootstrap script (`scripts/bootstrap-keycloak.sh`).

### 4.2 AMI-Trading (Confidential Client)

```json
{
  "clientId": "ami-trading",
  "name": "AMI Trading Platform",
  "enabled": true,
  "publicClient": false,
  "clientAuthenticatorType": "client-secret",
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": true,
  "redirectUris": [
    "http://localhost:8080/api/v1/auth/callback",
    "http://localhost:8080/api/v1/auth/callback"
  ],
  "webOrigins": [
    "http://localhost:8080",
    "http://localhost:8080"
  ],
  "defaultClientScopes": ["openid", "profile", "email", "roles"],
  "attributes": {
    "pkce.code.challenge.method": "S256",
    "backchannel.logout.session.required": "true",
    "backchannel.logout.url": "http://localhost:8080/api/v1/auth/backchannel-logout"
  },
  "protocolMappers": [
    {
      "name": "audience-mapper",
      "protocolMapper": "oidc-audience-mapper",
      "config": {
        "included.client.audience": "ami-trading",
        "id.token.claim": "true",
        "access.token.claim": "true"
      }
    }
  ]
}
```

Trading validates Keycloak JWTs directly using the JWKS endpoint. Environment variables:

| Variable | Value |
|----------|-------|
| `OIDC_ISSUER` | `http://localhost:8082/realms/ami` |
| `OIDC_JWKS_URI` | `http://localhost:8082/realms/ami/protocol/openid-connect/certs` |
| `OIDC_AUDIENCE` | `ami-trading` |
| `OIDC_CLIENT_ID` | `ami-trading` |
| `OIDC_CLIENT_SECRET` | Stored in OpenBao (target), currently in `.env` |

### 4.3 Matrix Synapse (Confidential Client)

```json
{
  "clientId": "matrix-synapse",
  "name": "Matrix Synapse",
  "enabled": true,
  "publicClient": false,
  "clientAuthenticatorType": "client-secret",
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": false,
  "redirectUris": [
    "https://mx1.p9q3fjcwcla0.uk/_matrix/*",
    "http://localhost:8008/_matrix/*"
  ],
  "webOrigins": [
    "https://mx1.p9q3fjcwcla0.uk"
  ],
  "defaultClientScopes": ["openid", "profile", "email"],
  "attributes": {
    "backchannel.logout.session.required": "true"
  }
}
```

Synapse delegates authentication to Keycloak via OIDC. The Matrix Authentication Service (MAS) or Synapse's native OIDC provider can be configured.

### 4.4 Service Account Clients

Each service identity is a dedicated confidential client with service account enabled and no interactive flows:

```json
{
  "clientId": "svc-platform-core",
  "name": "Platform Core Service",
  "enabled": true,
  "publicClient": false,
  "clientAuthenticatorType": "client-secret",
  "standardFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": true,
  "attributes": {
    "access.token.lifespan": "300"
  }
}
```

Service account clients created by bootstrap:

| Client ID | Purpose | Token TTL |
|-----------|---------|-----------|
| `svc-platform-core` | Portal backend operations | 300s |
| `svc-platform-infra` | Infrastructure automation | 300s |
| `svc-platform-monitor` | Monitoring and alerting | 300s |
| `svc-cicd-deployer` | CI/CD deployment pipeline | 300s |
| `svc-cicd-scanner` | Security scanning | 300s |
| `svc-cicd-builder` | Build pipeline | 300s |

Tenant-scoped service accounts follow the naming convention `svc-{purpose}--{org-slug}` (e.g., `svc-tenant-app--acme-corp`).

---

## 5. Authentication Flows

### 5.1 Authorization Code + PKCE (FR-1.1, FR-1.5)

All interactive user authentication uses the OIDC Authorization Code flow with PKCE (S256). This is the standard flow for browser-based applications.

```
Browser                    Portal (NextAuth)              Keycloak
  │                              │                           │
  │  1. GET /                    │                           │
  │ ─────────────────────────>   │                           │
  │                              │                           │
  │  2. 302 → Keycloak /auth     │                           │
  │ <─────────────────────────   │                           │
  │                              │                           │
  │  3. GET /realms/ami/protocol/openid-connect/auth         │
  │      ?client_id=ami-portal                               │
  │      &redirect_uri=.../api/auth/callback/keycloak        │
  │      &response_type=code                                 │
  │      &scope=openid email profile                         │
  │      &code_challenge=<SHA256(verifier)>                  │
  │      &code_challenge_method=S256                         │
  │      &state=<csrf-token>                                 │
  │ ──────────────────────────────────────────────────────>   │
  │                                                          │
  │  4. Login form (or SSO session cookie skip)              │
  │ <──────────────────────────────────────────────────────   │
  │                                                          │
  │  5. POST credentials                                     │
  │ ──────────────────────────────────────────────────────>   │
  │                                                          │
  │  6. 302 → Portal callback?code=AUTH_CODE&state=...       │
  │ <──────────────────────────────────────────────────────   │
  │                              │                           │
  │  7. Follow redirect          │                           │
  │ ─────────────────────────>   │                           │
  │                              │  8. POST /token           │
  │                              │     grant_type=           │
  │                              │       authorization_code  │
  │                              │     code=AUTH_CODE        │
  │                              │     code_verifier=<plain> │
  │                              │     client_id=ami-portal  │
  │                              │     client_secret=<secret>│
  │                              │ ────────────────────────> │
  │                              │                           │
  │                              │  9. {access_token,        │
  │                              │      refresh_token,       │
  │                              │      id_token}            │
  │                              │ <──────────────────────── │
  │                              │                           │
  │  10. Set session cookie      │                           │
  │ <─────────────────────────   │                           │
```

**Key points:**
- The portal is a confidential client — the token exchange (step 8) uses `client_secret`
- PKCE adds `code_challenge` / `code_verifier` even for confidential clients (defense in depth)
- NextAuth handles the entire flow automatically via the Keycloak provider
- If the user has an active Keycloak SSO session, step 4 is skipped (SSO — FR-1.2)

### 5.2 Client Credentials Grant (FR-9.2)

Service-to-service authentication for the Portal's Keycloak Admin API access:

```
Portal Backend                                  Keycloak
  │                                                │
  │  POST /realms/ami/protocol/openid-connect/token │
  │    grant_type=client_credentials                │
  │    client_id=ami-portal                         │
  │    client_secret=<secret>                       │
  │    scope=openid                                 │
  │ ─────────────────────────────────────────────>  │
  │                                                 │
  │  { access_token, expires_in: 300 }              │
  │ <─────────────────────────────────────────────  │
```

The Portal caches the service account token with a 30-second buffer before expiry (`TOKEN_BUFFER_MS = 30000` in `keycloak-admin.ts`).

### 5.3 Guest Authentication

Guest access uses NextAuth's Credentials provider with no password:

```
Browser                    Portal (NextAuth)
  │                              │
  │  POST /auth/signin/guest     │
  │    callbackUrl=/             │
  │ ─────────────────────────>   │
  │                              │
  │  signIn('guest', {})         │
  │  → Credentials provider      │
  │  → Returns { id, email,     │
  │       name, roles: ['guest'] │
  │     }                        │
  │                              │
  │  Set session cookie          │
  │ <─────────────────────────   │
```

Guest session has no Keycloak session — it exists only in the NextAuth JWT cookie. Guest users receive the `guest` role with `read` permission only.

Environment variables:
- `AMI_GUEST_EMAIL`: Guest email (default: `guest@ami.local`)
- `AMI_GUEST_NAME`: Guest display name (default: `Guest AMI Account`)

### 5.4 Token Refresh (NFR-2.2, NFR-2.7)

```
Portal Backend                                  Keycloak
  │                                                │
  │  POST /realms/ami/protocol/openid-connect/token │
  │    grant_type=refresh_token                     │
  │    refresh_token=<current_refresh_token>        │
  │    client_id=ami-portal                         │
  │    client_secret=<secret>                       │
  │ ─────────────────────────────────────────────>  │
  │                                                 │
  │  { access_token: <new>,                         │
  │    refresh_token: <new_rotated>,                │
  │    expires_in: 300 }                            │
  │ <─────────────────────────────────────────────  │
```

**Refresh token rotation** (NFR-2.7): Each refresh request issues a new refresh token and invalidates the old one. This is enforced by `revokeRefreshToken: true` and `refreshTokenMaxReuse: 0` in the realm config.

> **Current gap**: The portal's NextAuth JWT callback stores `accessToken` and `refreshToken` but does **not** currently implement automatic refresh. This MUST be implemented: the JWT callback should check `accessTokenExpires`, and if expired, call the token endpoint with `grant_type=refresh_token`.

### 5.5 Backchannel Logout (FR-1.3, FR-1.4)

When a user logs out from any application, Keycloak sends a logout token to all registered backchannel logout URLs:

```
Keycloak                           Portal                    Trading
  │                                  │                          │
  │  POST /api/auth/backchannel-logout                          │
  │    Content-Type: x-www-form-urlencoded                      │
  │    logout_token=<JWT>            │                          │
  │ ──────────────────────────────>  │                          │
  │                                  │                          │
  │  POST /api/v1/auth/backchannel-logout                       │
  │    logout_token=<JWT>                                       │
  │ ─────────────────────────────────────────────────────────>  │
```

**Logout token claims:**
```json
{
  "iss": "http://localhost:8082/realms/ami",
  "sub": "user-uuid",
  "aud": "ami-portal",
  "iat": 1709337600,
  "exp": 1709337660,
  "events": {
    "http://schemas.openid.net/event/backchannel-logout": {}
  },
  "sid": "keycloak-session-id"
}
```

The receiving application MUST:
1. Validate the JWT signature against Keycloak's JWKS
2. Verify the `aud` claim matches its client ID
3. Invalidate any local session associated with the `sub` or `sid`
4. Return HTTP 200 (success) or 501 (not implemented)

> **Current gap**: The portal does not yet implement a backchannel logout endpoint. This MUST be added at `/api/auth/backchannel-logout`.

### 5.6 Portal ↔ OpenBao Authentication

When the portal needs to access secrets on behalf of a user:

```
Portal Backend                                  OpenBao
  │                                                │
  │  POST /v1/auth/jwt/login                       │
  │    { "role": "portal-user",                    │
  │      "jwt": "<user's Keycloak access_token>" } │
  │ ─────────────────────────────────────────────>  │
  │                                                 │
  │  OpenBao validates JWT via Keycloak JWKS        │
  │  Extracts claims → maps to policies             │
  │                                                 │
  │  { "auth": {                                    │
  │      "client_token": "<openbao-token>",         │
  │      "policies": ["developer", "team-..."],     │
  │      "lease_duration": 300                      │
  │  }}                                             │
  │ <─────────────────────────────────────────────  │
```

The OpenBao token is stored **server-side only** (NFR-2.6) — never sent to the browser. It has a 5-minute TTL matching the Keycloak access token (NFR-2.3). The portal re-obtains it as needed using the current Keycloak JWT.

---

## 6. Client Application Integration

### 6.1 AMI-Portal (NextAuth v5)

#### Configuration (`app/lib/auth.ts`)

```typescript
import NextAuth from 'next-auth'
import Keycloak from 'next-auth/providers/keycloak'
import Credentials from 'next-auth/providers/credentials'

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET,
      issuer: process.env.KEYCLOAK_ISSUER,
      authorization: {
        params: {
          scope: 'openid email profile',
          prompt: 'login',
        },
      },
    }),
    Credentials({
      id: 'guest',
      // No credentials required — returns guest user
    }),
  ],
  session: { strategy: 'jwt' },
  pages: {
    signIn: '/auth/signin',
    error: '/auth/error',
  },
  callbacks: {
    jwt({ token, account }) { /* see 6.1.1 */ },
    session({ session, token }) { /* see 6.1.2 */ },
  },
})
```

#### 6.1.1 JWT Callback — Claim Extraction

On Keycloak sign-in, the JWT callback extracts claims from the OIDC profile:

```typescript
// Keycloak token claims structure
interface KeycloakTokenClaims {
  realm_access?: { roles?: string[] }
  resource_access?: Record<string, { roles?: string[] }>
  groups?: string[]
  tenant_id?: string
}
```

Role resolution logic:
1. Extract `realm_access.roles` (realm roles)
2. Extract `resource_access[clientId].roles` (client roles)
3. Merge and deduplicate
4. Filter against valid application roles: `['admin', 'editor', 'viewer', 'guest']` (legacy) or new role names
5. If no valid roles found, assign `admin` as fallback (dev convenience — MUST be removed in production)
6. Store `groups` and `tenant_id` from claims

#### 6.1.2 Session Callback — User Object

```typescript
session.user = {
  id: token.sub,
  email: token.email,
  name: token.name,
  image: token.picture,
  roles: token.roles,       // string[]
  groups: token.groups,      // string[]
  tenantId: token.tenantId,  // string | null
  provider: token.provider,  // 'keycloak' | 'guest' | 'test'
}
```

#### Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `KEYCLOAK_CLIENT_ID` | Yes | `ami-portal` |
| `KEYCLOAK_CLIENT_SECRET` | Yes | `<from-bootstrap>` |
| `KEYCLOAK_ISSUER` | Yes | `http://localhost:8082/realms/ami` |
| `AUTH_SECRET` | Yes | Base64 random value (NextAuth JWT signing) |
| `NEXTAUTH_URL` | Yes | `https://localhost:3000` |
| `AUTH_TRUST_HOST` | No | `true` (trust X-Forwarded headers) |
| `AMI_GUEST_EMAIL` | No | `guest@ami.local` |
| `AMI_GUEST_NAME` | No | `Guest AMI Account` |
| `AMI_TEST_BYPASS_AUTH` | No | `1` (test mode only) |

### 6.2 Middleware (`middleware.ts`)

The middleware attaches the NextAuth session to all requests but does **not** block navigation:

```typescript
export const config = {
  matcher: ['/((?!_next/static|_next/image|api/auth|auth|favicon.ico|docs).*)'],
}
```

Route protection is enforced at the API level via `withSession`, `withPermission`, and `withRole` guards (see SPECIFICATION-AUTHORIZATION.md).

### 6.3 Keycloak Admin API Client (`app/lib/keycloak-admin.ts`)

A server-side client class that authenticates via client credentials and proxies admin operations:

**Authentication:**
- Grant type: `client_credentials`
- Token endpoint: `{KEYCLOAK_ISSUER}/protocol/openid-connect/token`
- Admin base URL: derived by replacing `/realms/` → `/admin/realms/` in the issuer URL
- Token caching: 30-second buffer before expiry

**Operations supported:**

| Category | Operations |
|----------|-----------|
| Users | list, get, create, update, delete, resetPassword |
| Sessions | getUserSessions, logoutUser |
| Roles | getUserRealmRoles, assignUserRealmRoles, removeUserRealmRoles, listRealmRoles |
| Clients | list, get, create, update, delete, getSecret, regenerateSecret |
| Service Accounts | getServiceAccountUser |

Error handling uses a custom `KeycloakError` class that parses Keycloak's error response format (`errorMessage`, `error_description`, `error`).

### 6.4 AMI-Trading JWT Validation

Trading validates Keycloak JWTs directly (no NextAuth):

```python
# FastAPI dependency
from jose import jwt, jwk

async def validate_token(token: str) -> dict:
    jwks = await fetch_jwks(OIDC_JWKS_URI)
    payload = jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=OIDC_AUDIENCE,
        issuer=OIDC_ISSUER,
    )
    return payload
```

Trading extracts roles from `realm_access.roles` and `resource_access.ami-trading.roles` claims.

### 6.5 AMI-Streams (Matrix Synapse)

Synapse delegates authentication to Keycloak via its OIDC provider configuration:

```yaml
# homeserver.yaml
oidc_providers:
  - idp_id: keycloak
    idp_name: "AMI Platform"
    issuer: "http://localhost:8082/realms/ami"
    client_id: "matrix-synapse"
    client_secret: "<from-openbao>"
    scopes: ["openid", "profile", "email"]
    user_mapping_provider:
      config:
        localpart_template: "{{ user.preferred_username }}"
        display_name_template: "{{ user.name }}"
```

### 6.6 Security Headers (Portal — `next.config.ts`)

The portal sets security headers on all responses:

```typescript
{
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Strict-Transport-Security': 'max-age=63072000; includeSubDomains'
}
```

### 6.7 Test Auth Bypass

For integration testing, authentication can be bypassed:

```bash
NODE_ENV=test AMI_TEST_BYPASS_AUTH=1
```

This returns a test session with `admin` role. MUST only be enabled when both conditions are true (`NODE_ENV=test` AND `AMI_TEST_BYPASS_AUTH=1`).

---

## 7. Identity Providers (FR-3)

### 7.1 Social IdP Configuration

Each social IdP is configured via the Keycloak Admin API during bootstrap. Credentials are provided via environment variables:

| Provider | Env: Client ID | Env: Client Secret | Keycloak Provider ID |
|----------|----------------|--------------------|--------------------|
| Google | `KC_IDP_GOOGLE_CLIENT_ID` | `KC_IDP_GOOGLE_CLIENT_SECRET` | `google` |
| GitHub | `KC_IDP_GITHUB_CLIENT_ID` | `KC_IDP_GITHUB_CLIENT_SECRET` | `github` |
| Microsoft | `KC_IDP_MICROSOFT_CLIENT_ID` | `KC_IDP_MICROSOFT_CLIENT_SECRET` | `microsoft` |
| GitLab | `KC_IDP_GITLAB_CLIENT_ID` | `KC_IDP_GITLAB_CLIENT_SECRET` | `gitlab` |
| Bitbucket | `KC_IDP_BITBUCKET_CLIENT_ID` | `KC_IDP_BITBUCKET_CLIENT_SECRET` | `bitbucket` |
| Discord | `KC_IDP_DISCORD_CLIENT_ID` | `KC_IDP_DISCORD_CLIENT_SECRET` | `discord` |
| Slack | `KC_IDP_SLACK_CLIENT_ID` | `KC_IDP_SLACK_CLIENT_SECRET` | `slack` |
| LinkedIn | `KC_IDP_LINKEDIN_CLIENT_ID` | `KC_IDP_LINKEDIN_CLIENT_SECRET` | `linkedin-openid-connect` |
| Apple | `KC_IDP_APPLE_CLIENT_ID` | `KC_IDP_APPLE_CLIENT_SECRET` | `apple` |
| Facebook | `KC_IDP_FACEBOOK_CLIENT_ID` | `KC_IDP_FACEBOOK_CLIENT_SECRET` | `facebook` |
| Twitter/X | `KC_IDP_TWITTER_CLIENT_ID` | `KC_IDP_TWITTER_CLIENT_SECRET` | `twitter` |

#### Bootstrap Logic (FR-3.3, FR-3.4)

```bash
# Pseudocode for each IdP:
if [ -n "$KC_IDP_${PROVIDER}_CLIENT_ID" ] && [ -n "$KC_IDP_${PROVIDER}_CLIENT_SECRET" ]; then
  # Create or update IdP with enabled=true
  create_or_update_idp "$PROVIDER" "$CLIENT_ID" "$CLIENT_SECRET" true
else
  # Create IdP with enabled=false (placeholder for future activation)
  create_or_update_idp "$PROVIDER" "" "" false
fi
```

IdPs with credentials → enabled. IdPs without credentials → created but disabled. All operations MUST be idempotent.

#### IdP Configuration Template

```json
{
  "alias": "github",
  "displayName": "GitHub",
  "providerId": "github",
  "enabled": true,
  "trustEmail": true,
  "storeToken": false,
  "linkOnly": false,
  "firstBrokerLoginFlowAlias": "first broker login",
  "config": {
    "clientId": "<from-env>",
    "clientSecret": "<from-env>",
    "defaultScope": "user:email",
    "syncMode": "IMPORT"
  }
}
```

### 7.2 Enterprise Federation (FR-3.6)

Generic OIDC and SAML brokers support enterprise federation:

#### Generic OIDC Broker

```json
{
  "alias": "enterprise-oidc",
  "displayName": "Enterprise SSO",
  "providerId": "oidc",
  "enabled": true,
  "config": {
    "authorizationUrl": "<enterprise-auth-url>",
    "tokenUrl": "<enterprise-token-url>",
    "jwksUrl": "<enterprise-jwks-url>",
    "clientId": "<enterprise-client-id>",
    "clientSecret": "<enterprise-client-secret>",
    "defaultScope": "openid email profile",
    "syncMode": "IMPORT",
    "validateSignature": "true",
    "useJwksUrl": "true"
  }
}
```

#### SAML Broker

```json
{
  "alias": "enterprise-saml",
  "displayName": "Enterprise SAML",
  "providerId": "saml",
  "enabled": true,
  "config": {
    "singleSignOnServiceUrl": "<saml-sso-url>",
    "singleLogoutServiceUrl": "<saml-slo-url>",
    "nameIDPolicyFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
    "signingCertificate": "<base64-cert>",
    "wantAssertionsSigned": "true",
    "validateSignature": "true",
    "syncMode": "IMPORT"
  }
}
```

### 7.3 IdP Discovery API (FR-3.5)

The Portal's Account Manager provides an endpoint to list enabled IdPs:

```
GET /api/account-manager/providers
```

**Response** (cached for 5 minutes):
```json
[
  {
    "alias": "google",
    "displayName": "Google",
    "providerId": "google",
    "enabled": true
  },
  {
    "alias": "github",
    "displayName": "GitHub",
    "providerId": "github",
    "enabled": true
  }
]
```

This endpoint uses `withSession` (any authenticated user can call it). The Add Account dialog in the Portal UI dynamically renders buttons for each enabled IdP.

### 7.4 Organization-Linked IdPs (FR-5.5)

Organizations can be linked to specific IdPs for automatic membership:

```
POST /admin/realms/ami/organizations/{org-id}/identity-providers
{ "alias": "enterprise-saml" }
```

When a user authenticates via an org-linked IdP, they are automatically added as a member of the associated organization. This enables domain-based automatic provisioning: users from `@acme-corp.com` signing in via the Acme SAML IdP are auto-assigned to the `acme-corp` organization.

### 7.5 LDAP/AD Federation (FR-3.7)

LDAP/AD user federation is documented as a future extension point. Keycloak supports:

- LDAP/AD user storage provider (read-only or writable)
- Group and role mapping from LDAP attributes
- Periodic sync (full or changed-only)
- Kerberos/SPNEGO integration

Configuration would use the Keycloak User Federation API:
```
POST /admin/realms/ami/components
{
  "name": "corporate-ldap",
  "providerId": "ldap",
  "providerType": "org.keycloak.storage.UserStorageProvider",
  "config": {
    "connectionUrl": ["ldaps://ldap.corp.example.com:636"],
    "usersDn": ["ou=People,dc=corp,dc=example,dc=com"],
    "bindDn": ["cn=keycloak,ou=ServiceAccounts,dc=corp,dc=example,dc=com"],
    "bindCredential": ["<from-openbao>"],
    "editMode": ["READ_ONLY"],
    "syncRegistrations": ["false"],
    "vendor": ["ad"]
  }
}
```

---

## 8. Requirement Traceability

| Requirement | Section | Status |
|-------------|---------|--------|
| FR-1.1 SSO via OIDC | 5.1 | Specified |
| FR-1.2 No re-login across apps | 5.1 (SSO session cookie) | Specified |
| FR-1.3 Backchannel logout | 5.5 | Specified (gap: portal endpoint missing) |
| FR-1.4 Backchannel logout URL registration | 4.1, 4.2, 4.3 | Specified |
| FR-1.5 Redirect-based SSO | 5.1 | Specified |
| FR-2.1 Session idle timeout | 2.2 | Specified (1800s) |
| FR-2.2 Session max lifetime | 2.2 | Specified (36000s) |
| FR-2.3 Concurrent session limit | 2.6 | Specified (5 per user) |
| FR-2.4 User session self-management | Via Keycloak account console | Specified |
| FR-2.5 Admin session termination | 6.3 (logoutUser) | Specified |
| FR-2.6 Re-auth on role elevation | Step-up authentication | Future |
| FR-3.1 Bootstrap configures IdPs | 7.1 | Specified |
| FR-3.2 Supported IdPs | 7.1 (11 providers) | Specified |
| FR-3.3 Env var configuration | 7.1 | Specified |
| FR-3.4 Enable/disable by credentials | 7.1 | Specified |
| FR-3.5 Dynamic IdP discovery | 7.3 | Specified |
| FR-3.6 OIDC/SAML brokers | 7.2 | Specified |
| FR-3.7 LDAP/AD documentation | 7.5 | Documented |
| FR-4.1 User CRUD via portal | 6.3 | Specified |
| FR-4.2 Role/group assignment | 6.3 | Specified |
| FR-4.3 Force password reset | 6.3 | Specified |
| FR-4.4 Self-service profile | Via Keycloak account console | Specified |
| FR-4.5 User → OpenBao provisioning | See SPECIFICATION-SECRETS.md | Deferred |
| FR-4.6 User deprovisioning | See SPECIFICATION-SECRETS.md | Deferred |
| FR-6.1 Min password length 12 | 2.4 | Specified |
| FR-6.2 Breached password check | 2.4 (notCompromised) | Specified |
| FR-6.3 No forced rotation | 2.4 | Specified |
| FR-6.4 Password history 5 | 2.4 | Specified |
| FR-6.5 Blacklist policy | 2.4 (notCompromised) | Specified |
| FR-7.1 TOTP support | 2.5 | Specified |
| FR-7.2 WebAuthn support | 2.5 | Specified |
| FR-7.3 MFA per role | 2.5 | Specified |
| FR-7.4 Recovery codes | Keycloak built-in | Specified |
| FR-7.5 MFA prompt on first login | 2.5 (required actions) | Specified |
| FR-8.1 Brute force enabled | 2.3 | Specified |
| FR-8.2 Max 5 failures | 2.3 | Specified |
| FR-8.3 15 min lockout | 2.3 | Specified |
| FR-8.4 Quick login 1/sec | 2.3 | Specified |
| FR-8.5 Admin notification | See SPECIFICATION-OPERATIONS.md | Deferred |
| FR-9.1 Dedicated service clients | 4.4 | Specified |
| FR-9.2 Client credentials grant | 5.2 | Specified |
| FR-9.3 Secrets in OpenBao | See SPECIFICATION-SECRETS.md | Deferred |
| FR-9.4 Client management UI | 6.3 | Specified |
| FR-9.5 Secret rotation | 6.3 (regenerateSecret) | Specified |
| NFR-2.1 Access token 5 min | 2.2 | Specified |
| NFR-2.2 Refresh token 30 min | 2.2 | Specified |
| NFR-2.3 OpenBao token 5 min | 5.6 | Specified |
| NFR-2.5 Refresh server-side only | 6.1 (JWT strategy) | Specified |
| NFR-2.6 OpenBao token server-side | 5.6 | Specified |
| NFR-2.7 Refresh token rotation | 2.2, 5.4 | Specified |
