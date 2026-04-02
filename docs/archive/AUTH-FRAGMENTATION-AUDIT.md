# AUTH SYSTEM FRAGMENTATION AUDIT

**Date:** 2026-02-10
**Status:** CRITICAL
**Scope:** All AMI projects (Orchestrator, Portal, Trading, Streams, Auth, Base, Rust-Trading)

---

## Executive Summary

The AMI ecosystem has **at least 6 independent authentication systems** across its services, with **zero shared identity, zero SSO, and zero token interoperability**. The most damning finding: a comprehensive enterprise-grade auth framework exists in `base/backend/opsec/` (with JWT, OAuth2, MFA, password policies, secrets management, multi-tenancy, audit trails) -- and **nothing uses it**. Instead, AMI-AUTH reimplements OAuth in TypeScript, AMI-TRADING reimplements JWT+bcrypt in Python, and Matrix runs its own auth entirely.

A user logging into the Portal cannot access the Trading API. A Trading API user cannot access the Portal. Matrix has its own users entirely. Backup scripts use Google OAuth with no relation to any user system.

This document catalogues every auth implementation found.

---

## 1. AMI-AUTH (@ami/auth) -- TypeScript Library

**Location:** `projects/AMI-AUTH/`
**Type:** NPM library (not a standalone service)
**Framework:** NextAuth.js v5 wrapper
**Consumer:** AMI-PORTAL (only)

### Architecture

AMI-AUTH is a **shared library** that wraps NextAuth.js conventions. It is NOT a running service -- it's imported by Next.js applications at build time.

```
@ami/auth (library)
  -> Consumed by AMI-PORTAL via package.json: "file:../AMI-AUTH"
  -> Talks to DataOps service for user storage (optional)
  -> Falls back to local JSON files when DataOps unavailable
```

### Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/index.ts` | 8 | Barrel re-export |
| `src/config.ts` | 607 | Provider loading, NextAuth config generation |
| `src/server.ts` | 214 | auth(), handlers, signIn(), signOut() exports |
| `src/middleware.ts` | 83 | Next.js route protection middleware |
| `src/client.ts` | 26 | Browser fetch wrapper with cookie auth |
| `src/env.ts` | 99 | Environment variable parsing |
| `src/dataops-client.ts` | 410 | DataOps service client + local file fallback |
| `src/types.ts` | 91 | TypeScript type definitions |
| `src/errors.ts` | 58 | Custom error classes |
| `src/security-logger.ts` | 82 | Security event audit logging |
| `src/next-auth.d.ts` | 38 | NextAuth type augmentation |

### Providers Supported

| Provider | Type | Config Source |
|----------|------|---------------|
| Google | OAuth 2.0 | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` or DataOps catalog |
| GitHub | OAuth 2.0 | `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` or DataOps catalog |
| Azure AD (Entra) | OAuth 2.0 | `AZURE_AD_CLIENT_ID` / `AZURE_AD_CLIENT_SECRET` or DataOps catalog |
| Generic OAuth2 | OAuth 2.0 | DataOps catalog only |
| AMI Credentials | Email/Password | DataOps `POST /auth/verify` or local JSON file |
| Guest | Synthetic | SHA256-derived guest ID from email |

### Session Strategy

- **Type:** JWT (stateless)
- **Algorithm:** Determined by NextAuth (default: encrypted JWE)
- **Expiry:** 12 hours (`config.ts:545`)
- **Cookie:** `next-auth.session-token` (httpOnly, Secure, SameSite=Strict)
- **Signing secret:** `AUTH_SECRET` env var (min 32 chars)

### Token Payload (JWT Claims)

```typescript
{
  sub: string              // User ID
  email: string
  name: string | null
  picture: string | null   // Avatar URL
  roles: string[]          // ["admin", "editor", ...]
  groups: string[]         // ["org-1", ...]
  tenantId: string | null
  metadata: Record<string, unknown>
}
```

### User Storage

**Primary:** DataOps service (external, accessed via `DATAOPS_AUTH_URL`)
- `POST /auth/verify` -- Credential verification
- `GET /auth/users/by-email?email=...` -- User lookup
- `POST /auth/users` -- User upsert
- `GET /auth/providers/catalog` -- OAuth provider catalog
- Auth: `Authorization: Bearer ${DATAOPS_INTERNAL_TOKEN}`

**Fallback:** Local JSON files
- `AUTH_CREDENTIALS_FILE` -- Array of user records with scrypt-hashed passwords
- `AUTH_PROVIDER_CATALOG_FILE` -- OAuth provider definitions

### Password Hashing

- **Format:** `scrypt:SALT:KEY` (base64-encoded salt and derived key)
- **Alternative:** `plain:PASSWORD` (development only)
- **Verification:** `crypto.timingSafeEqual()` for constant-time comparison

### Middleware Headers

When a request passes auth, middleware injects:
- `x-ami-user-id` -- User UUID
- `x-ami-user-email` -- User email
- `x-ami-user-roles` -- Comma-separated roles
- `x-ami-tenant-id` -- Tenant ID (if present)

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `AUTH_SECRET` | Yes | JWT encryption key (>= 32 chars) |
| `AUTH_TRUST_HOST` | No | Trust X-Forwarded headers |
| `DATAOPS_AUTH_URL` | No | DataOps service URL |
| `DATAOPS_INTERNAL_TOKEN` | No | Bearer token for DataOps |
| `AUTH_CREDENTIALS_FILE` | No | Local credentials JSON path |
| `AUTH_ALLOWED_EMAILS` | No | CSV email allow-list |
| `AUTH_PROVIDER_CATALOG_FILE` | No | Local provider catalog JSON |
| `AMI_GUEST_EMAIL` | No | Guest email (default: `guest@ami.local`) |
| `GOOGLE_CLIENT_ID` | No | Direct Google OAuth |
| `GITHUB_CLIENT_ID` | No | Direct GitHub OAuth |
| `AZURE_AD_CLIENT_ID` | No | Direct Azure AD OAuth |

---

## 2. AMI-PORTAL -- TypeScript/Next.js Application

**Location:** `projects/AMI-PORTAL/`
**Type:** Next.js web application
**Auth:** Delegates 100% to `@ami/auth`

### Auth Integration Points

| File | Purpose |
|------|---------|
| `app/api/auth/[...nextauth]/route.ts` | NextAuth route handler (3 lines, delegates to @ami/auth) |
| `app/auth/signin/page.tsx` | Sign-in page (55 lines) |
| `app/auth/signin/SignInForm.tsx` | Sign-in form component (275 lines) |
| `app/auth/signin/guest/route.ts` | Guest sign-in endpoint |
| `app/auth/signin/guest/guest-handler.ts` | Guest flow handler (74 lines) |
| `app/auth/error/page.tsx` | Auth error page (28 lines) |
| `app/lib/auth-guard.ts` | API route protection wrapper (44 lines) |
| `app/lib/request-origin.ts` | Origin resolution from headers (99 lines) |
| `middleware.ts` | Route-level auth enforcement (12 lines) |
| `src/components/account/AccountDrawer.tsx` | Account management UI (647 lines) |
| `.env.local` | Auth secrets |

### Protected Routes (22+ using `withSession()`)

All API routes under `/app/api/` except `/api/auth/*` require authentication:
- `/api/config`, `/api/serve`, `/api/tree`, `/api/export`, `/api/events`
- `/api/library`, `/api/file`, `/api/latex`, `/api/upload`, `/api/media`
- `/api/account-manager/accounts`

### Session Flow

```
Browser -> middleware.ts (checks JWT cookie)
  -> Public route? Pass through
  -> No session? Redirect to /auth/signin?callbackUrl=...
  -> Has session? Forward x-ami-* headers -> route handler
     -> withSession() wrapper validates session
     -> Returns 401 if invalid
```

### Multi-Account Support

The AccountDrawer manages multiple linked accounts:
- Account ID format: `{provider}::{userId}`
- Supports credentials, google, github, azure_ad, openai, anthropic, api_key, oauth2
- Default account selection
- Last-used tracking
- Guest account is system-managed (cannot be removed)

### Secrets in `.env.local`

```
AUTH_SECRET=2ymapwnELNzQCvZiAU6xNOMhR6kaPMILVhfg/rdYrkc=
NEXTAUTH_URL=https://p9q3fjcwcla0.uk
```

---

## 3. AMI-TRADING -- Python/FastAPI Application

**Location:** `projects/AMI-TRADING/`
**Type:** Python FastAPI web application
**Auth:** COMPLETELY INDEPENDENT -- zero integration with AMI-AUTH

### Architecture

AMI-TRADING has its own complete auth stack:

```
FastAPI app
  -> JWT tokens (pyjwt, HS256)
  -> bcrypt password hashing
  -> PostgreSQL user table
  -> httpOnly cookies + Bearer tokens
  -> In-memory rate limiting
```

### Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/core/security.py` | 46 | JWT + bcrypt functions |
| `src/delivery/api/auth.py` | 195 | Auth REST endpoints |
| `src/delivery/api/deps.py` | 209 | Auth dependencies & rate limiter |
| `src/types/auth.py` | 69 | User entity + request/response schemas |
| `src/types/config.py` | 338 | JWT config (secret, expiry) |
| `src/delivery/cli/user_commands.py` | 195 | CLI user management |

### Endpoints

```
POST /api/v1/auth/register    -- Create user (rate: 3/5min per IP)
POST /api/v1/auth/login       -- Login (rate: 5/1min per IP)
POST /api/v1/auth/logout      -- Logout (requires auth)
GET  /api/v1/auth/me          -- Current user (requires auth)
```

### User Model (SQLAlchemy)

```python
class UserEntity(Base):
    __tablename__ = "users"
    id: str           # UUID, PK
    email: str        # Unique, indexed
    password_hash: str  # bcrypt hash
    name: str | None
    created_at: datetime
    updated_at: datetime
```

### Session Strategy

- **Type:** JWT (stateless)
- **Algorithm:** HS256 (HMAC-SHA256 via `pyjwt`)
- **Expiry:** 24 hours (configurable via `APP_JWT_EXPIRE_MINUTES`)
- **Cookie:** `auth_token` (httpOnly, Secure, SameSite=Lax)
- **Signing secret:** `APP_JWT_SECRET` env var (min 32 chars)
- **Fallback:** Also accepts `Authorization: Bearer <token>` header

### Token Payload

```python
{
    "sub": user_id,    # String UUID
    "exp": expiration,  # Unix timestamp
    "iat": issued_at    # Unix timestamp
}
```

### Password Hashing

- **Algorithm:** bcrypt with automatic salt generation
- **Library:** `bcrypt==5.0.0`
- **Verification:** `bcrypt.checkpw()` (timing-safe)
- **Minimum length:** 8 characters

### Rate Limiting

- **Type:** In-memory sliding window (per IP)
- **Login:** 5 requests per 60 seconds
- **Register:** 3 requests per 300 seconds
- **Eviction:** Prunes at 10k entries
- **Persistence:** None (lost on restart)

### Security Concerns

1. **CORS wildcard:** `allow_origins=["*"]` with `allow_credentials=True` (`main.py:153-160`)
2. **Default weak secrets:** `forecasting_db_password`, `minio_password` in Docker Compose
3. **Default JWT secret:** `test-secret-for-development-only-32chars` (blocked in production)
4. **No OAuth/SSO support**
5. **No 2FA/MFA**
6. **WebSockets unauthenticated:** `/ws/realtime/*`, `/ws/tickers`, `/ws/tasks`

### Dependencies

```
pyjwt==2.11.0    # JWT encoding/decoding
bcrypt==5.0.0    # Password hashing
fastapi==0.128.0 # Web framework with security utilities
```

---

## 4. AMI-STREAMS -- Matrix Synapse Homeserver

**Location:** `projects/AMI-STREAMS/`
**Type:** Ansible-deployed Matrix homeserver
**Auth:** Matrix Synapse built-in + Matrix Authentication Service

### Authentication Services

Configuration in `ansible/inventory/host_vars/mx1.p9q3fjcwcla0.uk/vars.yml`:

1. **Matrix Authentication Service** -- Enabled
   - Password authentication: enabled
   - Account registration: enabled

2. **OAuth2 for Element X Android**
   - Client ID: `01HRE9DKY6S0FAFA0A0A0A0A0A`
   - Grant types: `authorization_code`, `refresh_token`, `device_code`
   - Client auth method: `none` (public client)
   - Redirect URIs: `io.element.android://callback`, `element://callback`

3. **LiveKit JWT Authentication**
   - JWT endpoint: `/_matrix/client/unstable/org.matrix.msc4143/token`
   - Used for voice/video call SFU authentication

4. **TURN Server**
   - Port 3479 (UDP), 5350 (TCP)
   - For WebRTC NAT traversal

### Hardcoded Secrets in Ansible Vars

```yaml
matrix_homeserver_generic_secret_key: 'fd9f2c...'
postgres_connection_password: '84971a...'
matrix_authentication_service_config_secrets_encryption: 'e7f8cf...'
exim_relay_relay_auth_username: "independentailabs@gmail.com"
exim_relay_relay_auth_password: "tppsmpbjuesuuobh"  # Gmail app password
```

### Rate Limiting

```yaml
rc_login:
  address: { per_second: 5, burst_count: 20 }
  account: { per_second: 5, burst_count: 20 }
  failed_attempts: { per_second: 5, burst_count: 20 }
```

---

## 5. Orchestrator Auth (Backup/Infrastructure)

**Location:** `ami/scripts/backup/common/auth.py`
**Type:** Google Drive OAuth2 for backup operations

### Three Authentication Methods

| Method | Config | Storage |
|--------|--------|---------|
| Impersonation | `GDRIVE_SERVICE_ACCOUNT_EMAIL` | gcloud ADC |
| Service Account Key | `GDRIVE_CREDENTIALS_FILE` | JSON key file on disk |
| OAuth 2.0 | `credentials.json` | `token.pickle` (refresh token) |

### Other Infrastructure Auth

| System | Method | Location |
|--------|--------|----------|
| OpenVPN | Certificate + optional user/pass | `bootstrap_openvpn.sh` |
| Cloudflare | API token | `.env:69` |
| SSH | Password | `.env:30` |
| Sudo | Password | `.env:27` |
| DataOps | Bearer token | `.env:44-47` |
| Secrets Broker | Token | `.env:46-49` |

### Master .env File (ROOT-LEVEL SECRETS)

```
SUDO_PASS="m!s|&75yv9qP"
SSH_DEFAULT_PASSWORD="m!s|&75yv9qP"
DATAOPS_INTERNAL_TOKEN=dev-stack-internal-token
SECRETS_BROKER_TOKEN=dev-stack-internal-token
SECRETS_BROKER_OPENBAO_TOKEN=openbao-root
CLOUDFLARE_API_TOKEN="KdbCP7ya..."
CLOUDFLARE_ACCOUNT_ID="54969636..."
CLOUDFLARE_ZONE_ID="825774e3..."
GDRIVE_SERVICE_ACCOUNT_EMAIL=ami-orchestrator-backup@system-service-475913.iam.gserviceaccount.com
```

---

## 6. RUST-TRADING -- ZK Credentials

**Location:** `projects/RUST-TRADING/rust-zk-protocol/`
**Type:** Zero-knowledge proof credential system

### Credential System

- `crates/zk-sdk/src/credential.rs` -- CredentialManager for Travel Rule compliance
- Stores/validates credentials by commitment hash
- Supports beneficiary/originator credentials
- Physical address verification
- VASP endpoint configuration
- Not related to user authentication -- this is regulatory compliance

---

## 7. BASE MODULE -- Enterprise Auth Framework (UNUSED)

**Location:** `/home/ami/Projects/AMI-ORCHESTRATOR/base/`
**Type:** Git submodule -- Python package `ami_base`
**Status:** Comprehensive enterprise auth framework that **NO PROJECT CURRENTLY USES**

This is the most critical finding. The `base/` submodule contains a fully architected authentication, authorization, and security framework -- with OAuth2, JWT, MFA, password policies, secrets management, multi-tenancy, and audit trails. It appears to have been designed as the shared foundation. Instead, every project reimplemented auth from scratch.

### 7.1 Auth Service (`backend/opsec/auth/`)

| File | Lines | Purpose |
|------|-------|---------|
| `auth_service.py` | 269 | Core auth service: authenticate, create/revoke providers, token refresh |
| `provider_registry.py` | 78 | Adapter registry: Google, GitHub, Azure, OpenAI, Anthropic, API Key, SSH |
| `provider_adapters.py` | 319 | OAuth, API key, SSH adapter implementations with ProviderBootstrap model |
| `repository.py` | 151 | User + provider persistence (fetch, ensure, attach, detach, login tracking) |
| `exceptions.py` | 55 | Auth exception taxonomy (InvalidCredentials, RateLimit, Consent, Config) |

**AuthService** provides:
- `authenticate_user()` -- OAuth flow initiation
- `create_auth_provider()` / `revoke_auth_provider()` -- Provider lifecycle
- `get_user_auth_providers()` -- List linked providers
- `refresh_provider_token()` -- Token refresh
- Global singleton: `auth_service = AuthService()`

**Provider Adapters**:
- `OAuthProviderAdapter` -- Full OAuth2 with token exchange, refresh, revocation, user info
- `ApiKeyProviderAdapter` -- OpenAI (`Authorization: Bearer`), Anthropic (`X-API-Key`), custom
- `SshProviderAdapter` -- SSH bastion/managed key with host, username, secret_reference

**ProviderBootstrap** model (normalized auth payload):
- `access_token`, `refresh_token`, `id_token`, `api_key` (all `SecretStr`)
- `token_type`, `scope`, `expires_at`, `obtained_at`
- `client_id`, `tenant`

### 7.2 OAuth2 Framework (`backend/opsec/oauth/`)

| File | Lines | Purpose |
|------|-------|---------|
| `oauth_manager.py` | 533 | Full OAuth2 managers: Google, GitHub, Azure AD |
| `oauth_config.py` | 154 | Predefined OAuth configs with PKCE + state support |
| `browser/callback_server.py` | 343 | aiohttp callback server for OAuth redirects |
| `browser/browser_launcher.py` | 73 | Cross-platform browser launcher with headless detection |

**OAuth Manager** implements:
- Browser flow with local callback server
- Device flow for headless/CI environments
- PKCE code challenge (SHA-256)
- CSRF state validation (constant-time comparison)
- Token exchange, refresh, and revocation
- User info retrieval

**Predefined Configs**:
- Google: `cloud-platform`, `userinfo.email`, `userinfo.profile` + Code Assist
- GitHub: `user`, `repo`, `gist`, `notifications`
- Azure AD: Multi-tenant with `{tenant}` URL placeholder

### 7.3 JWT & Session Management (`backend/opsec/crypto/`)

| File | Lines | Purpose |
|------|-------|---------|
| `jwt_utils.py` | 401 | JWT creation/verification (HS256 + RS256) + SessionManager |
| `encryption.py` | 205 | Fernet AES-256 token encryption + PBKDF2 key derivation |

**JWTManager**:
- `create_token()` -- JWT with `iat`, `nbf`, `exp` claims
- `verify_token()` -- Signature + expiration validation
- `refresh_token()` -- New token with same claims
- `generate_rsa_keys()` -- RSA 2048-bit key pair generation

**SessionManager** (JWT-based):
- `create_session()` -- Session JWT with user_id, email
- `verify_session()` -- Verify + track last_accessed
- `revoke_session()` -- Delete from store
- `cleanup_expired_sessions()` -- 24h default TTL
- In-memory storage (dict-based)

### 7.4 Password Management (`backend/opsec/password/`)

| File | Lines | Purpose |
|------|-------|---------|
| `password_facade.py` | 428 | Password hashing (Argon2), validation, policy enforcement |

**PasswordFacade**:
- **Hashing:** Argon2 (primary), bcrypt, PBKDF2-SHA256 via passlib
- **Policy:** Min 12 chars, max 128, uppercase/lowercase/digits/special required
- **History:** Cannot reuse last 5 passwords
- **Lockout:** 5 failed attempts -> 15-min lockout (30-min window)
- **Common password blacklist:** 100 weak passwords blocked
- **Reset tokens:** SHA-256 hashed, 1-hour expiry, max attempts

### 7.5 Multi-Factor Authentication (`backend/opsec/mfa/`)

| File | Lines | Purpose |
|------|-------|---------|
| `mfa_facade.py` | 197 | TOTP registration/verification, backup codes |

**MFA Types Supported:**
- TOTP (Google Authenticator, Authy) -- `pyotp` library
- SMS OTP
- Email OTP
- WebAuthn (hardware keys: YubiKey)
- Backup codes (10 x 8-char alphanumeric, one-time use)

### 7.6 Data Models (`backend/dataops/models/`)

**User Model** (`user.py:156-208`):
```python
# Fields:
email, username, full_name
auth_provider_ids: list[str]      # Linked providers
primary_provider_id: str | None   # Default provider
mfa_enabled: bool                 # MFA status
mfa_enforced: bool                # MFA required
mfa_device_ids: list[str]
is_active: bool
is_verified: bool
last_login: datetime
login_count: int
preferences: dict
```

**AuthProvider Model** (`user.py:45-154`):
```python
# Sensitive fields (SecretStr, DataClassification.RESTRICTED):
access_token, refresh_token, id_token, api_key

# Metadata:
token_type: str = "Bearer"
scope: list[str]
expires_at, obtained_at: datetime
is_active: bool
last_used, last_refreshed: datetime
refresh_count: int

# Methods:
is_token_expired()     # 5-min buffer
refresh_access_token() # Async refresh
revoke()               # Async revocation
get_headers()          # Build Authorization headers
apply_bootstrap()      # Apply ProviderBootstrap data
```

**Password Models** (`password.py`):
- `PasswordPolicy` -- Configurable policy with lockout, history, age limits
- `PasswordRecord` -- Hash storage with Argon2/bcrypt/PBKDF2, status tracking
- `PasswordResetToken` -- Token with SHA-256 hash, expiry, attempt tracking

**MFA Models** (`mfa.py`):
- `MFADevice` -- Device registration (TOTP secret, WebAuthn credential, phone/email)
- `MFAVerification` -- Audit record per verification attempt

**Security Models** (`security.py`):
- `SecurityContext` -- user_id, roles, groups, tenant_id, is_admin
- `ACLEntry` -- Principal-based access control (12 permission types)
- `DataClassification` -- PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED, TOP_SECRET
- `Role` -- RoleType enum: OWNER, ADMIN, MEMBER, VIEWER, GUEST, SERVICE

**Type Enums** (`types.py`):
- `AuthProviderType` -- GOOGLE, GITHUB, AZURE_AD, OPENAI, ANTHROPIC, API_KEY, OAUTH2, SSH
- `TokenType` -- ACCESS, REFRESH, ID_TOKEN, API_KEY

### 7.7 Enterprise Security (`backend/dataops/security/`)

| File | Lines | Purpose |
|------|-------|---------|
| `multi_tenancy.py` | 412 | Row-level, dedicated, or isolated tenant separation |
| `rate_limiter.py` | 289 | Token bucket + Redis distributed + adaptive (CPU/mem) |
| `audit_trail.py` | 367 | Blockchain-based immutable audit with PoW |
| `encryption.py` | 391 | Field-level encryption, PII detection/masking |

**Rate Limiters** (predefined):
- `auth_limiter` -- 10 attempts/min
- `api_limiter` -- 1000 calls/min
- `llm_limiter` -- 50 calls/min
- `crud_limiter` -- 500 ops/min

**Multi-Tenancy Isolation Levels:**
- SHARED -- Row-level security (tenant_id filter)
- DEDICATED -- Separate database/schema per tenant
- ISOLATED -- Separate instance per tenant

### 7.8 Secrets Broker (`backend/services/secrets_broker/`)

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 142 | FastAPI service for secrets management |
| `store.py` | ~200 | Secret storage with OpenBao/Vault backend |
| `config.py` | ~50 | Broker configuration |

**Endpoints** (Bearer token protected):
- `POST /v1/secrets/ensure` -- Store/update secret (201)
- `POST /v1/secrets/retrieve` -- Retrieve secret + integrity hash
- `DELETE /v1/secrets/{vault_reference}` -- Delete secret (204)
- `GET /healthz` -- Health check

### 7.9 Dependencies (`pyproject.toml`)

```
cryptography==46.0.3     # Fernet, RSA keys
pyjwt==2.10.1            # JWT tokens
passlib==1.7.4           # Password hashing (multi-algo)
argon2-cffi==25.1.0      # Argon2 password hashing
pyotp==2.9.0             # TOTP/MFA
python-jose==3.5.0       # JWT with JWE support
fastapi==0.121.0         # Web framework
```

### 7.10 Why This Matters

The `base/` module has **everything** needed for a unified auth system:
- Enterprise-grade password hashing (Argon2 > bcrypt > PBKDF2)
- Multi-algorithm JWT (HS256 + RS256)
- Full OAuth2 with PKCE, device flow, and browser callback
- MFA (TOTP, WebAuthn, backup codes)
- Password policies with lockout and history
- Multi-tenancy with three isolation levels
- Blockchain audit trail
- Distributed rate limiting (Redis-backed)
- Field-level encryption and PII masking
- Secrets management via OpenBao/Vault

**Yet AMI-TRADING uses raw `pyjwt` + `bcrypt` and AMI-AUTH reimplements OAuth in TypeScript.**

---

## FRAGMENTATION MATRIX

| Dimension | AMI-AUTH / Portal | AMI-TRADING | AMI-STREAMS | Base (unused) | Orchestrator |
|-----------|-------------------|-------------|-------------|---------------|--------------|
| **Language** | TypeScript | Python | Ansible/YAML | Python | Python |
| **Framework** | NextAuth.js v5 | FastAPI | Matrix Synapse | FastAPI | Custom |
| **JWT Library** | next-auth (JWE) | pyjwt (HS256) | Synapse built-in | pyjwt + python-jose (HS256/RS256) | N/A |
| **Password Hash** | scrypt (DataOps) | bcrypt | Synapse built-in | Argon2 + bcrypt + PBKDF2 | N/A |
| **User Store** | DataOps / local JSON | PostgreSQL | Synapse DB | Postgres + Dgraph + OpenBao | N/A |
| **Session Type** | JWT cookie (12h) | JWT cookie (24h) | Matrix tokens | JWT in-memory (24h) | OAuth tokens |
| **Cookie Name** | `next-auth.session-token` | `auth_token` | N/A | N/A | N/A |
| **Rate Limiting** | None | In-memory sliding | Synapse built-in | Token bucket + Redis + adaptive | N/A |
| **OAuth Providers** | Google, GitHub, Azure | None | Element X OAuth2 | Google, GitHub, Azure (PKCE) | Google (backup) |
| **MFA** | No | No | No | TOTP, WebAuthn, SMS, Backup | No |
| **Password Policy** | None | Min 8 chars | Synapse | Min 12, complexity, history, lockout | N/A |
| **Audit Trail** | security-logger.ts | None | Synapse logs | Blockchain PoW audit chain | None |
| **Multi-Tenancy** | tenant_id in JWT | None | None | Row/Dedicated/Isolated | None |
| **Secrets Mgmt** | DataOps token | Env vars | Ansible vault | OpenBao/Vault broker | .env file |
| **SSO** | No | No | No | No (capable) | No |
| **Token Interop** | No | No | No | No | No |
| **Shared Identity** | No | No | No | No | No |
| **In Production** | Yes | Yes | Yes | **NO** | Yes |

---

## CRITICAL PROBLEMS

### 0. THE ELEPHANT IN THE ROOM -- `base/` IS UNUSED

The `base/backend/opsec/` module contains a **complete enterprise auth framework** with:
- OAuth2 with PKCE, device flow, browser callback
- JWT with HS256 + RS256 + key generation
- Argon2 password hashing with policy enforcement
- MFA (TOTP, WebAuthn, backup codes)
- Multi-tenancy (3 isolation levels)
- Distributed rate limiting (Redis)
- Blockchain audit trail
- Secrets broker (OpenBao/Vault)
- Field-level encryption + PII masking
- User models with provider linking, MFA fields, login tracking

**None of this is used by any production service.** AMI-AUTH reimplemented OAuth in TypeScript. AMI-TRADING reimplemented JWT+bcrypt in Python. This represents months of engineering effort sitting dormant.

### 1. ZERO SHARED IDENTITY

A user who logs into the Portal with Google OAuth has **no way** to authenticate against the Trading API. They are completely separate user databases with completely separate credential stores.

### 2. INCOMPATIBLE TOKEN FORMATS

- AMI-AUTH produces **encrypted JWE tokens** via NextAuth
- AMI-TRADING produces **signed JWS tokens** via pyjwt with HS256
- Neither can validate the other's tokens
- Different cookie names (`next-auth.session-token` vs `auth_token`)
- Different payload structures (rich claims vs minimal `sub`/`exp`/`iat`)

### 3. DUPLICATE PASSWORD SYSTEMS

- AMI-AUTH: scrypt hashing with `crypto.timingSafeEqual()`
- AMI-TRADING: bcrypt hashing with `bcrypt.checkpw()`
- If a user has accounts in both systems, they have **two separate passwords**

### 4. NO SSO / NO TOKEN EXCHANGE

- No OIDC provider that all services trust
- No token exchange mechanism
- No shared session store
- Each service is an island

### 5. SECRETS SPRAWL

Secrets are scattered across:
- `.env` (orchestrator root) -- master passwords, API tokens
- `.env.local` (Portal) -- AUTH_SECRET, NEXTAUTH_URL
- `vars.yml` (Streams/Ansible) -- Matrix secrets, SMTP credentials
- `docker-compose.yml` (Trading) -- DB passwords, MinIO credentials
- Environment variables (Trading) -- JWT secret
- `token.pickle` (Backup) -- Google OAuth refresh tokens
- `credentials.json` (Backup) -- Google service account keys

No central secrets manager is consistently used despite `SECRETS_BROKER_*` env vars existing.

### 6. GUEST ACCOUNT INCONSISTENCY

- Portal: Has a full guest provider with SHA256-derived IDs, managed accounts, role-based access
- Trading: No guest concept at all -- must register
- Streams: Matrix guest accounts are a separate Synapse feature

### 7. AUDIT LOGGING GAPS

- AMI-AUTH: Has `security-logger.ts` with structured security events
- AMI-TRADING: No audit logging whatsoever
- AMI-STREAMS: Matrix Synapse has its own logging
- Base: Has blockchain-based audit trail -- **unused**
- No centralized audit trail

### 8. THREE PASSWORD HASHING ALGORITHMS

- AMI-AUTH/DataOps: `scrypt` with timing-safe comparison
- AMI-TRADING: `bcrypt` via bcrypt library
- Base (unused): `Argon2` via argon2-cffi (industry best practice)
- If `base/` were used, there'd be one algorithm (Argon2) with fallback support

### 9. MFA EXISTS BUT IS UNREACHABLE

The `base/` module has full MFA support (TOTP, WebAuthn, backup codes) that could protect all services. Instead:
- Portal: No MFA
- Trading: No MFA
- Streams: No MFA (Matrix can do it but not configured)

---

## SERVICE COUNT

| Category | Count | Services |
|----------|-------|----------|
| TypeScript auth systems | 2 | @ami/auth library, AMI-PORTAL consumer |
| Python auth systems | 3 | AMI-TRADING FastAPI, Base opsec (unused), Orchestrator backup |
| Infrastructure auth | 2 | Matrix Synapse, OpenVPN |
| Total independent user stores | 4 | DataOps/JSON, PostgreSQL, Synapse DB, Base Postgres+Dgraph (unused) |
| Total JWT implementations | 3 | NextAuth JWE, pyjwt HS256 (Trading), pyjwt+jose HS256/RS256 (Base, unused) |
| Total password hash algorithms | 3 | scrypt, bcrypt, Argon2 (unused) |
| Total OAuth implementations | 4 | NextAuth, Element X, Google backup, Base opsec (unused) |
| Total rate limiter implementations | 3 | Trading in-memory, Synapse built-in, Base token-bucket+Redis (unused) |
| Total secrets management | 2 | .env files (used), OpenBao broker (unused) |

---

## FILE REFERENCE INDEX

### AMI-AUTH
- `projects/AMI-AUTH/src/config.ts` -- Provider loading, NextAuth config (607 lines)
- `projects/AMI-AUTH/src/server.ts` -- auth(), handlers, signIn/Out (214 lines)
- `projects/AMI-AUTH/src/middleware.ts` -- Route protection (83 lines)
- `projects/AMI-AUTH/src/dataops-client.ts` -- User storage client (410 lines)
- `projects/AMI-AUTH/src/env.ts` -- Environment parsing (99 lines)
- `projects/AMI-AUTH/src/types.ts` -- Type definitions (91 lines)
- `projects/AMI-AUTH/src/security-logger.ts` -- Audit logging (82 lines)
- `projects/AMI-AUTH/src/client.ts` -- Browser fetch wrapper (26 lines)

### AMI-PORTAL
- `projects/AMI-PORTAL/app/api/auth/[...nextauth]/route.ts` -- NextAuth handler
- `projects/AMI-PORTAL/app/auth/signin/page.tsx` -- Sign-in page
- `projects/AMI-PORTAL/app/auth/signin/SignInForm.tsx` -- Sign-in form (275 lines)
- `projects/AMI-PORTAL/app/auth/signin/guest/guest-handler.ts` -- Guest flow
- `projects/AMI-PORTAL/app/lib/auth-guard.ts` -- API protection (44 lines)
- `projects/AMI-PORTAL/middleware.ts` -- Route middleware
- `projects/AMI-PORTAL/src/components/account/AccountDrawer.tsx` -- Account UI (647 lines)
- `projects/AMI-PORTAL/app/lib/store.ts:216-570` -- Account store

### AMI-TRADING
- `projects/AMI-TRADING/src/core/security.py` -- JWT + bcrypt (46 lines)
- `projects/AMI-TRADING/src/delivery/api/auth.py` -- Auth endpoints (195 lines)
- `projects/AMI-TRADING/src/delivery/api/deps.py` -- Auth deps + rate limit (209 lines)
- `projects/AMI-TRADING/src/types/auth.py` -- User entity + schemas (69 lines)
- `projects/AMI-TRADING/src/types/config.py` -- JWT config (338 lines)
- `projects/AMI-TRADING/src/delivery/cli/user_commands.py` -- CLI tools (195 lines)

### AMI-STREAMS
- `projects/AMI-STREAMS/ansible/inventory/host_vars/mx1.p9q3fjcwcla0.uk/vars.yml` -- All Matrix auth config

### Base Module (UNUSED -- at `/home/ami/Projects/AMI-ORCHESTRATOR/base/`)
- `backend/opsec/auth/auth_service.py` -- Core auth service (269 lines)
- `backend/opsec/auth/provider_registry.py` -- Provider adapter registry (78 lines)
- `backend/opsec/auth/provider_adapters.py` -- OAuth/APIKey/SSH adapters (319 lines)
- `backend/opsec/auth/repository.py` -- User/provider persistence (151 lines)
- `backend/opsec/auth/exceptions.py` -- Auth exception taxonomy (55 lines)
- `backend/opsec/oauth/oauth_manager.py` -- Google/GitHub/Azure OAuth2 (533 lines)
- `backend/opsec/oauth/oauth_config.py` -- OAuth configs with PKCE (154 lines)
- `backend/opsec/oauth/browser/callback_server.py` -- OAuth callback server (343 lines)
- `backend/opsec/oauth/browser/browser_launcher.py` -- Browser launcher (73 lines)
- `backend/opsec/crypto/jwt_utils.py` -- JWT + SessionManager (401 lines)
- `backend/opsec/crypto/encryption.py` -- AES-256 Fernet encryption (205 lines)
- `backend/opsec/password/password_facade.py` -- Argon2 + password policy (428 lines)
- `backend/opsec/mfa/mfa_facade.py` -- TOTP/WebAuthn/backup codes (197 lines)
- `backend/dataops/models/user.py` -- User + AuthProvider models (208 lines)
- `backend/dataops/models/password.py` -- Password models + policies (164 lines)
- `backend/dataops/models/mfa.py` -- MFA device + verification models (98 lines)
- `backend/dataops/models/security.py` -- SecurityContext + ACL + DataClassification (149 lines)
- `backend/dataops/models/types.py` -- AuthProviderType + TokenType enums (27 lines)
- `backend/dataops/security/multi_tenancy.py` -- Multi-tenant isolation (412 lines)
- `backend/dataops/security/rate_limiter.py` -- Token bucket + Redis + adaptive (289 lines)
- `backend/dataops/security/audit_trail.py` -- Blockchain audit trail (367 lines)
- `backend/dataops/security/encryption.py` -- Field encryption + PII masking (391 lines)
- `backend/services/secrets_broker/app.py` -- Secrets management FastAPI (142 lines)
- **Total: ~4,700+ lines of auth/security code sitting unused**

### Orchestrator
- `ami/scripts/backup/common/auth.py` -- Google Drive auth (184 lines)
- `.env` -- Master secrets file
