# Specification: base/opsec Code Migration to AMI-AUTH

**Document Version:** 1.0
**Classification:** Technical Specification
**Domain:** Authentication & Identity -- Code Migration
**Last Updated:** February 2026
**Prerequisite Reading:** [SPEC-AUTH-OIDC-PROVIDER.md](SPEC-AUTH-OIDC-PROVIDER.md)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Source Inventory](#2-source-inventory)
3. [Migration Disposition](#3-migration-disposition)
4. [Dependency Simplification](#4-dependency-simplification)
5. [Deferred: MFA Module](#5-deferred-mfa-module)
6. [File-by-File Migration Guide](#6-file-by-file-migration-guide)
7. [Post-Migration Cleanup](#7-post-migration-cleanup)

---

## 1. Overview

The `base/backend/opsec/` directory contains ~4,700 lines of enterprise-grade Python authentication code that is **completely unused** by any service. This specification defines how to migrate the reusable portions into `projects/AMI-AUTH/backend/` as part of the OIDC provider build.

### 1.1. Guiding Principles

- **Migrate the algorithm, not the framework.** The business logic (JWT signing, password hashing, encryption) is sound. The persistence layer (UnifiedCRUD with Postgres+Dgraph+OpenBao) is over-engineered for this use case and must be replaced.
- **Simplify aggressively.** Drop multi-backend sync, triple storage backends, and GDPR/retention utilities. The OIDC service needs Postgres-only persistence via SQLAlchemy async.
- **Preserve security properties.** RS256 key generation, bcrypt/argon2 hashing, Fernet encryption, and constant-time comparisons must carry over unchanged.
- **Skip the OAuth client code.** `base/opsec/oauth/` implements the OAuth *client* side (browser flows, device flow, callback server). The OIDC provider is the *server* side. These are fundamentally different.

### 1.2. Migration Summary

| Category | Lines | Action |
|---|---|---|
| Migrated (copy or adapt) | ~530 | Exceptions, JWTManager, TokenEncryption, ProviderRegistry |
| Rewritten (same semantics, new persistence) | ~850 | AuthService, Repository, PasswordFacade |
| Skipped (not needed) | ~2,580 | OAuth client, browser flows, SecureStorage, SessionManager, GDPR, retention |
| Deferred (Phase 4) | ~740 | MFA (TOTP, WebAuthn, backup codes) |

---

## 2. Source Inventory

Complete file listing of `base/backend/opsec/` with line counts and external dependencies.

### 2.1. Auth Module

| File | Lines | External Imports |
|---|---|---|
| `auth/__init__.py` | ~0 | None |
| `auth/exceptions.py` | 55 | None (stdlib only) |
| `auth/auth_service.py` | 268 | `dataops.models.security.SecurityContext`, `dataops.models.user.AuthProvider/User/AuthProviderType`, `auth.repository`, `auth.provider_registry` |
| `auth/repository.py` | 150 | `dataops.models.security.SecurityContext`, `dataops.models.user.AuthProvider/User/AuthProviderType`, `dataops.services.unified_crud.get_crud` |
| `auth/provider_adapters.py` | 318 | `dataops.models.types.AuthProviderType`, `auth.exceptions`, `pydantic`, `aiohttp` |
| `auth/provider_registry.py` | 77 | `dataops.models.types.AuthProviderType`, `auth.exceptions`, `auth.provider_adapters` |

### 2.2. Crypto Module

| File | Lines | External Imports |
|---|---|---|
| `crypto/jwt_utils.py` | 401 | `cryptography` (rsa, serialization), `pyjwt`, `loguru`, `base.backend.utils.uuid_utils.uuid7` |
| `crypto/encryption.py` | 207 | `cryptography` (Fernet, PBKDF2), `loguru` |

### 2.3. Password Module

| File | Lines | External Imports |
|---|---|---|
| `password/__init__.py` | ~0 | None |
| `password/password_facade.py` | 428 | `dataops.core.unified_crud.UnifiedCRUD`, `dataops.models.password.*`, `dataops.models.user.User`, `loguru` |

### 2.4. OAuth Module (Client-Side)

| File | Lines | External Imports |
|---|---|---|
| `oauth/oauth_manager.py` | 533 | `aiohttp`, `loguru`, `oauth.oauth_config`, `auth.exceptions` |
| `oauth/oauth_config.py` | 154 | None (stdlib + pydantic) |
| `oauth/browser/callback_server.py` | ~180 | `aiohttp.web` |
| `oauth/browser/browser_launcher.py` | ~170 | `webbrowser`, `aiohttp` |

### 2.5. MFA Module

| File | Lines | External Imports |
|---|---|---|
| `mfa/__init__.py` | ~0 | None |
| `mfa/mfa_facade.py` | 197 | `dataops.core.unified_crud.UnifiedCRUD`, `dataops.models.mfa.MFADevice/MFAType`, `dataops.models.security.SecurityContext`, `pydantic.SecretStr`, `pyotp` (lazy import) |

### 2.6. GDPR / Retention Modules

| File | Lines | External Imports |
|---|---|---|
| `gdpr/__init__.py` | ~0 | None |
| `gdpr/gdpr_utils.py` | ~150 | `dataops.models.*`, `UnifiedCRUD` |
| `retention/__init__.py` | ~0 | None |
| `retention/retention_facade.py` | ~250 | `dataops.models.*`, `UnifiedCRUD` |

---

## 3. Migration Disposition

### 3.1. COPY -- Direct Copy with Minimal Changes

#### `auth/exceptions.py` (55 lines) -> `backend/auth/exceptions.py`

**Action**: Copy verbatim.

**Rationale**: Zero external dependencies. Clean exception hierarchy with `error_code` attribute. Exactly what the OIDC service needs.

**Changes**: None. The file imports only `from __future__ import annotations` and stdlib.

**Source classes**:
- `AuthProviderError` -- base class with `error_code`, `message`, `details`
- `InvalidCredentialsError` -- `error_code = "invalid_credentials"`
- `ProviderConfigurationError` -- `error_code = "invalid_config"`
- `ProviderCommunicationError` -- `error_code = "connectivity_failed"`
- `ProviderRateLimitError` -- `error_code = "rate_limited"`
- `ProviderConsentError` -- `error_code = "consent_required"`

---

### 3.2. MIGRATE -- Adapt with Modifications

#### `crypto/jwt_utils.py` JWTManager (lines 18-253) -> `backend/crypto/jwt_manager.py`

**Action**: Migrate the `JWTManager` class. Drop `SessionManager` class (lines 255-401).

**Changes required**:

| # | Change | Reason |
|---|---|---|
| 1 | Remove `from base.backend.utils.uuid_utils import uuid7` | Replace with `from uuid import uuid4`. **Behavioral change**: uuid7 is time-sortable, uuid4 is random. No existing code depends on ID ordering, but document this change in migration notes. |
| 2 | Add `kid: str \| None` parameter to `__init__` and `create_token` | JWKS requires key ID in JWT header |
| 3 | Add `headers={"kid": self.kid}` to `jwt.encode()` calls | JWKS key matching |
| 4 | Add `to_jwk() -> dict` method | Export public key as JWK dict for the `/oauth/jwks` endpoint |
| 5 | Remove `refresh_token` method (lines 185-209) | OIDC refresh is handled by Authlib grant, not by re-signing |
| 6 | Remove `get_token_expiry` and `is_token_expired` (lines 211-253) | Not needed; PyJWT handles expiry validation |

**Preserved unchanged**:
- `generate_rsa_keys()` static method (lines 63-92) -- RSA 2048-bit key generation
- `create_token()` core logic (lines 94-134) -- JWT creation with HS256/RS256
- `verify_token()` core logic (lines 136-183) -- JWT verification

#### `crypto/encryption.py` TokenEncryption (lines 15-96) -> `backend/crypto/encryption.py`

**Action**: Migrate the `TokenEncryption` class only. Drop `SecureStorage` (lines 148-205) and `hash_password`/`verify_password` static methods (lines 98-145).

**Changes required**:

| # | Change | Reason |
|---|---|---|
| 1 | Drop `hash_password()` static method (lines 98-126) | Password hashing is in `auth/password.py` using bcrypt |
| 2 | Drop `verify_password()` static method (lines 128-145) | Same reason |
| 3 | Drop `SecureStorage` class (lines 148-205) | In-memory dict wrapper, not useful for production service |

**Preserved unchanged**:
- `__init__()` with master key initialization (lines 18-31)
- `generate_key()` static method (lines 33-37)
- `derive_key()` static method with PBKDF2 (lines 39-58)
- `encrypt()` and `decrypt()` methods (lines 60-90)
- `generate_salt()` static method (lines 92-95)

#### `auth/provider_registry.py` (77 lines) -> `backend/auth/provider_registry.py`

**Action**: Migrate the registry pattern. Replace `AuthProviderType` import source.

**Changes required**:

| # | Change | Reason |
|---|---|---|
| 1 | Replace `from base.backend.dataops.models.types import AuthProviderType` | Define a local `AuthProviderType` enum in `backend/auth/types.py` |
| 2 | Replace `from base.backend.opsec.auth.provider_adapters import ...` | Import from local `backend/auth/provider_adapters` |
| 3 | Remove `SSH` adapter registration | SSH key auth not relevant for OIDC |
| 4 | Remove `OPENAI`, `ANTHROPIC` adapter registrations | API key adapters not needed for OIDC server |

**Preserved unchanged**:
- Registry pattern (`_ADAPTERS` dict, `get_adapter()`, `register_adapter()`)
- `authenticate()`, `refresh()`, `revoke()`, `headers()` dispatch functions

---

### 3.3. REWRITE -- Same Semantics, New Persistence

#### `auth/auth_service.py` (268 lines) -> `backend/auth/service.py`

**Action**: Rewrite. Keep the public method signatures; replace internals.

**Current dependencies to remove**:
- `from base.backend.dataops.models.security import SecurityContext` -- replace with simple function args
- `from base.backend.dataops.models.user import AuthProvider, AuthProviderType, User` -- replace with SQLAlchemy models
- `from base.backend.opsec.auth import repository` -- replace with new `db/repository.py`
- `from base.backend.opsec.auth.provider_registry import ...` -- replace with local registry

**Methods to preserve (with new implementation)**:
- `authenticate_user(email, password)` -- verify credentials, return user
- `get_user_by_email(email)` -- lookup user by email
- `get_user_by_id(user_id)` -- lookup user by ID
- `ensure_user(user_data)` -- upsert user record
- `record_successful_login(user)` -- update login_count and last_login

**Methods to drop**:
- `_system_context()` -- SecurityContext pattern removed
- Provider-specific authenticate/refresh/revoke -- handled by OIDC flows

#### `auth/repository.py` (150 lines) -> `backend/db/repository.py`

**Action**: Rewrite. Replace `UnifiedCRUD` with SQLAlchemy async queries.

**Current pattern** (to be replaced):
```python
from base.backend.dataops.services.unified_crud import get_crud
_USER_CRUD = get_crud(User)
users = await _USER_CRUD.find({"email": normalized}, context=context, limit=1)
```

**Target pattern**:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch_user_by_email(
    session: AsyncSession, email: str
) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

**Functions to rewrite**:
- `fetch_user_by_email(email, context)` -> `fetch_user_by_email(session, email)`
- `ensure_user(email, context)` -> `ensure_user(session, user_data)`
- `record_successful_login(user, context)` -> `record_successful_login(session, user)`
- `fetch_providers_for_user(user, context)` -> `fetch_providers_for_user(session, user_id)`
- `create_provider(user, bootstrap, context)` -> `create_provider(session, user_id, provider_data)`
- `revoke_provider(provider, context)` -> `revoke_provider(session, provider_id)`

The `SecurityContext` parameter is removed in all functions. Access control is handled at the API layer (OIDC tokens / internal token), not at the repository layer.

#### `password/password_facade.py` (428 lines) -> `backend/auth/password.py`

**Action**: Rewrite and simplify from ~428 lines to ~80 lines.

**What to keep** (business logic):
- `COMMON_PASSWORDS` set (lines 34-50) -- weak password blocklist
- Password strength validation rules (lines 86-150):
  - Minimum length (8 characters)
  - Must contain uppercase, lowercase, digit, special character
  - Must not be in common passwords list
  - Must not contain email local part

**What to drop**:
- `UnifiedCRUD` integration (lines 22-23): `_crud = UnifiedCRUD()`
- `PasswordRecord` model usage -- replace with simple bcrypt hash string
- `PasswordResetToken` management -- OIDC handles password reset differently
- `PasswordPolicy` Pydantic model -- inline the policy rules
- `PasswordStrength` enum -- simplify to bool pass/fail
- History-based validation (lines 200-250) -- requires `PasswordRecord` CRUD
- PBKDF2/scrypt fallback chains -- standardize on bcrypt only

**Target implementation**:
```python
import bcrypt

BCRYPT_ROUNDS = 12

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def validate_password_strength(password: str, email: str = "") -> list[str]:
    """Return list of validation failure messages. Empty = valid."""
    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append("Password must be at least 8 characters")
    # ... uppercase, lowercase, digit, special checks
    # ... common password check
    # ... email local part check
    return errors
```

---

### 3.4. PARTIAL -- Selective Migration

#### `auth/provider_adapters.py` (318 lines) -> `backend/auth/provider_adapters.py`

**Action**: Migrate the `ProviderBootstrap` Pydantic model and `OAuthProviderAdapter` class. Drop `SshProviderAdapter` and `ApiKeyProviderAdapter`.

**What to keep**:
- `ProviderAdapter` ABC (lines 1-30) -- interface definition
- `ProviderBootstrap` Pydantic model (~20 lines) -- authentication result container
- `OAuthProviderAdapter` class (lines ~60-180) -- OAuth flow logic

**What to change**:
- Replace `aiohttp` with `httpx` for HTTP calls
- Replace `AuthProviderType` import from base/dataops with local enum
- Remove `SecretStr` token handling (tokens stored in DB, not in-memory)

**What to drop**:
- `SshProviderAdapter` (~60 lines) -- SSH auth irrelevant for OIDC
- `ApiKeyProviderAdapter` (~50 lines) -- API key auth not needed

---

### 3.5. SKIP -- Not Migrated

| Module | Lines | Reason |
|---|---|---|
| `oauth/oauth_manager.py` | 533 | OAuth **client** code (browser flow, device flow, callback server). The OIDC provider is the **server** side. Fundamentally different purpose. |
| `oauth/oauth_config.py` | 154 | Client-side OAuth configs for Google/GitHub/Azure. Not needed for provider. |
| `oauth/browser/callback_server.py` | ~180 | Desktop CLI callback server for receiving OAuth redirects. Not relevant to web service. |
| `oauth/browser/browser_launcher.py` | ~170 | Desktop CLI browser launcher. Not relevant to web service. |
| `crypto/jwt_utils.py` SessionManager | ~150 | In-memory session store keyed by `uuid7`. Inappropriate for production. OIDC tokens replace sessions. |
| `crypto/encryption.py` SecureStorage | ~60 | In-memory encrypted dict wrapper. Not useful for production service. |
| `crypto/encryption.py` hash/verify_password | ~50 | PBKDF2-based password hashing. Replaced by bcrypt in `auth/password.py`. |
| `gdpr/gdpr_utils.py` | ~150 | GDPR data export/anonymization. Out of scope for auth service. |
| `retention/retention_facade.py` | ~250 | Data retention policies. Out of scope for auth service. |

---

## 4. Dependency Simplification

### 4.1. The UnifiedCRUD Problem

The biggest migration challenge is the `UnifiedCRUD` dependency. Every service module in base/ uses it:

```python
from base.backend.dataops.services.unified_crud import get_crud
_USER_CRUD = get_crud(User)
```

`UnifiedCRUD` provides:
- Multi-backend sync (Postgres primary, Dgraph secondary, OpenBao for secrets)
- `SecurityContext`-based access control on every operation
- `SyncStrategy.PRIMARY_FIRST` patterns
- Automatic conflict resolution across backends

**This is completely unnecessary for the OIDC service.** The service needs a single Postgres database with standard async queries.

### 4.2. Replacement Strategy

| base/ Pattern | AMI-AUTH Replacement |
|---|---|
| `get_crud(Model)` singleton | `AsyncSession` dependency injection via FastAPI `Depends` |
| `await _crud.find(filters, context)` | `await session.execute(select(Model).where(...))` |
| `await _crud.create(payload, context)` | `session.add(Model(**payload)); await session.flush()` |
| `await _crud.update(id, payload, context)` | `await session.execute(update(Model).where(...).values(...))` |
| `SecurityContext` on every operation | Access control at API layer (OIDC token / internal token) |
| Pydantic models with `SecretStr` | SQLAlchemy ORM models with plain columns |
| `uuid7()` for IDs | `uuid.uuid4()` (standard, no external dep) |

### 4.3. Model Mapping

| base/dataops Model | AMI-AUTH SQLAlchemy Model |
|---|---|
| `User` (Pydantic, ~200 lines) | `User` ORM (~30 lines, see SPEC-AUTH-OIDC-PROVIDER Section 7.1) |
| `AuthProvider` (Pydantic, ~150 lines) | Split into `OAuthClient` + provider catalog data |
| `AuthProviderType` (enum, ~10 lines) | Local `AuthProviderType` enum in `backend/auth/types.py` |
| `SecurityContext` (Pydantic, ~50 lines) | Removed (not needed) |
| `PasswordRecord` (Pydantic, ~30 lines) | `users.password_hash` column (single bcrypt string) |
| `PasswordPolicy` (Pydantic, ~20 lines) | Inline constants in `auth/password.py` |
| `MFADevice` (Pydantic, ~40 lines) | Deferred to Phase 4 |

### 4.4. Third-Party Package Changes

| base/ Package | AMI-AUTH Package | Change |
|---|---|---|
| `aiohttp` 3.13.2 | `httpx` 0.28.1 | Replace async HTTP client |
| `pyjwt` 2.10.1 | `pyjwt` 2.11.0 | Version bump |
| `cryptography` 46.0.3 | `cryptography` >=44.0.0 | Same library, flexible version |
| `pydantic` 2.12.3 | `pydantic` 2.12.5 | Version bump |
| `loguru` 0.7.3 | `loguru` 0.7.3 | Same |
| N/A | `sqlalchemy[asyncio]` 2.0.46 | New: replaces UnifiedCRUD |
| N/A | `asyncpg` 0.31.0 | New: Postgres async driver |
| N/A | `authlib` >=1.4.0 | New: OIDC server framework |
| N/A | `bcrypt` 5.0.0 | New: replaces PBKDF2 password hashing |
| N/A | `argon2-cffi` 23.1.0 | New: optional modern password hashing |

---

## 5. Deferred: MFA Module

### 5.1. Scope

The `mfa/mfa_facade.py` (197 lines) implements:
- **TOTP** registration and verification (Google Authenticator style) via `pyotp`
- **Backup codes** generation (10 single-use codes)
- Device management (register, verify, list, delete)

### 5.2. Why Deferred

MFA adds complexity to the OIDC authorization flow (step-up authentication challenge). It requires:
1. A session state machine (unauthenticated -> password verified -> MFA challenged -> fully authenticated)
2. Additional database tables (`mfa_devices`, `backup_codes`)
3. UI for TOTP setup (QR code display, verification input)
4. `pyotp` dependency (lazy-imported in source)

This is orthogonal to the core OIDC provider and can be added after the base flows work.

### 5.3. Migration Plan (Phase 4)

When ready:

1. Create `backend/mfa/totp.py` -- migrate TOTP logic from `mfa_facade.py:24-100`
2. Create `backend/mfa/backup_codes.py` -- migrate backup code logic from `mfa_facade.py:100-197`
3. Add `mfa_devices` and `backup_codes` tables to `db/models.py`
4. Wire into the OIDC authorize flow:
   - After password verification, check if user has MFA devices
   - If yes, redirect to MFA challenge page
   - After MFA verification, issue authorization code
5. Add `pyotp>=2.9.0` to dependencies
6. Add `amr` (Authentication Methods Reference) claim to id_token per RFC 8176

### 5.4. Dependencies from base/

| base/ Module | Action for Phase 4 |
|---|---|
| `dataops.models.mfa.MFADevice` | Redefine as SQLAlchemy model |
| `dataops.models.mfa.MFAType` | Redefine as local enum |
| `dataops.core.unified_crud.UnifiedCRUD` | Replace with SQLAlchemy queries |
| `dataops.models.security.SecurityContext` | Remove |
| `pydantic.SecretStr` | Use encrypted column or vault |
| `pyotp` (lazy import) | Direct dependency |

---

## 6. File-by-File Migration Guide

Step-by-step order for implementing the migration.

### 6.1. Phase 1 Files (Core Auth + DataOps API)

Execute in this order (each step depends on the previous):

| Step | Target File | Source File | Action |
|---|---|---|---|
| 1 | `backend/auth/exceptions.py` | `opsec/auth/exceptions.py` | Copy verbatim (55 lines) |
| 2 | `backend/db/models.py` | New | Define `User` SQLAlchemy model (see SPEC-OIDC-PROVIDER Section 7.1) |
| 3 | `backend/db/engine.py` | New | Async engine + sessionmaker (pattern from AMI-TRADING) |
| 4 | `backend/db/repository.py` | `opsec/auth/repository.py` | Rewrite: UnifiedCRUD -> SQLAlchemy async |
| 5 | `backend/auth/password.py` | `opsec/password/password_facade.py` | Rewrite: ~428 lines -> ~80 lines, bcrypt only |
| 6 | `backend/auth/service.py` | `opsec/auth/auth_service.py` | Rewrite: decouple from UnifiedCRUD + SecurityContext |
| 7 | `backend/config.py` | New | Pydantic Settings (DATABASE_URL, JWT keys, FERNET_KEY, etc.) |
| 8 | `backend/api/deps.py` | New | get_db, internal_token_auth, rate_limiter |
| 9 | `backend/api/dataops.py` | New | 5 endpoints matching dataops-client.ts |
| 10 | `backend/api/router.py` | New | Mount dataops router |
| 11 | `backend/main.py` | New | FastAPI app factory |

### 6.2. Phase 2 Files (OIDC Endpoints)

| Step | Target File | Source File | Action |
|---|---|---|---|
| 12 | `backend/crypto/jwt_manager.py` | `opsec/crypto/jwt_utils.py` | Migrate JWTManager (lines 18-253), add kid support |
| 13 | `backend/crypto/encryption.py` | `opsec/crypto/encryption.py` | Migrate TokenEncryption (lines 15-96) |
| 14 | `backend/crypto/keys.py` | New | RSA key management, JWKS document builder |
| 15 | `backend/db/models.py` | Extend | Add OAuthClient, AuthorizationCode, OAuthToken, SigningKey |
| 16 | `backend/oidc/models.py` | New | OIDC Pydantic request/response models |
| 17 | `backend/oidc/server.py` | New | Authlib AuthorizationServer wiring |
| 18 | `backend/oidc/discovery.py` | New | /.well-known/openid-configuration |
| 19 | `backend/oidc/jwks.py` | New | /oauth/jwks |
| 20 | `backend/oidc/authorize.py` | New | /oauth/authorize |
| 21 | `backend/oidc/token.py` | New | /oauth/token |
| 22 | `backend/oidc/userinfo.py` | New | /oauth/userinfo |
| 23 | `backend/oidc/revoke.py` | New | /oauth/revoke |

---

## 7. Post-Migration Cleanup

### 7.1. base/opsec Status

After migration is complete and all consumers are using the OIDC provider:

**SPEC-BASE-001**: The `base/backend/opsec/` directory shall NOT be deleted. It remains in the `base/` submodule as historical reference. No code shall import from it.

**Rationale**: The `base/` submodule is shared across the orchestrator ecosystem. Deleting files from it requires coordinating with other potential consumers. Since the code is already unused, leaving it in place is harmless.

### 7.2. Verification Checklist

After all migration steps are complete:

1. **No imports from base/opsec**: Grep `projects/AMI-AUTH/backend/` for `from base.` -- must return zero results
2. **No UnifiedCRUD usage**: Grep for `UnifiedCRUD`, `get_crud`, `SecurityContext` -- must return zero results
3. **No aiohttp usage**: Grep for `aiohttp` -- must return zero results (replaced by httpx)
4. **All tests pass**: `uv run pytest projects/AMI-AUTH/tests/ -v` with 90%+ unit coverage
5. **Pre-push hooks pass**: ruff format, ruff lint, mypy, banned words, file length
6. **DataOps contract**: TypeScript `DataOpsClient` works against the Python service
7. **OIDC compliance**: Discovery document, JWKS, and authorization code flow all work
