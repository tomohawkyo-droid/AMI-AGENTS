# Authorization — Technical Specification

**Date:** 2026-03-01
**Status:** DRAFT
**Parent:** [SPECIFICATION-IAM.md](SPECIFICATION-IAM.md)
**Requirements:** FR-4, FR-5

---

## 1. Current Implementation

### 1.1 Permission Model (`app/lib/permissions.ts`)

The portal currently uses a flat RBAC model with 8 permissions and 4 roles:

```typescript
type Permission =
  | 'read'
  | 'write'
  | 'delete'
  | 'upload'
  | 'export'
  | 'serve'
  | 'admin:accounts'
  | 'admin:config'

const ROLE_PERMISSIONS: Record<string, readonly Permission[]> = {
  admin:  ['read', 'write', 'delete', 'upload', 'export', 'serve', 'admin:accounts', 'admin:config'],
  editor: ['read', 'write', 'upload', 'export', 'serve'],
  viewer: ['read', 'export'],
  guest:  ['read'],
}
```

**Resolution function:**
```typescript
function resolvePermissions(roles: string[]): Set<Permission> {
  const perms = new Set<Permission>()
  for (const role of roles) {
    const granted = ROLE_PERMISSIONS[role]
    if (granted) for (const p of granted) perms.add(p)
  }
  return perms
}
```

Permissions from all matched roles are merged (union). Unknown roles (e.g., Keycloak system roles like `offline_access`, `uma_authorization`, `default-roles-ami`) grant nothing and are silently ignored.

### 1.2 API Route Guards (`app/lib/auth-guard.ts`)

Three guard functions protect API routes:

| Guard | Signature | Behavior |
|-------|-----------|----------|
| `withSession` | `(handler) => RouteHandler` | Ensures authentication (any role). Returns 401 if not authenticated. |
| `withPermission` | `(permission, handler) => RouteHandler` | Checks `hasPermission(session.user.roles, permission)`. Returns 403 if permission missing. |
| `withRole` | `(allowedRoles, handler) => RouteHandler` | Checks `userRoles.some(r => allowedRoles.includes(r))`. Returns 403 if no matching role. |

#### Test Bypass

When `NODE_ENV=test && AMI_TEST_BYPASS_AUTH=1`, `requireSession()` returns a test session with `admin` role, bypassing all permission checks. Both conditions MUST be true.

### 1.3 Gaps in Current Implementation

| Gap | Impact |
|-----|--------|
| Only 8 permissions — too coarse | `admin:accounts` grants full user AND client management as a single permission |
| No organization scoping | All permissions are global — no tenant isolation |
| No escalation guards | An admin can assign any role to any user, including self-elevation |
| No role assignment ceiling | A viewer could theoretically be made admin by any admin |
| No explicit deny | Permissions are purely additive — no way to deny specific access |
| `withRole` and `withPermission` overlap | Some routes use role checks, others use permission checks |

---

## 2. Target Permission Registry (FR-5.2)

All permissions use `resource:action` format. This maps to Keycloak Authorization Services (resource + scope), OpenBao policies (path + capability), and the portal's `withPermission()` guard.

### 2.1 User Management

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

### 2.2 Client / Service Account Management

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

### 2.3 Identity Provider Configuration

| Permission | Description |
|---|---|
| `idp:list` | List configured identity providers |
| `idp:read` | View IdP configuration details |
| `idp:create` | Add new identity providers |
| `idp:update` | Modify IdP settings (mappers, sync) |
| `idp:delete` | Remove identity providers |
| `idp:sync` | Trigger manual user sync from external IdP |

### 2.4 Platform / Realm Configuration

| Permission | Description |
|---|---|
| `config:read` | View platform settings |
| `config:session-policy` | Modify session timeouts |
| `config:password-policy` | Set password complexity, history |
| `config:brute-force` | Configure brute force thresholds |
| `config:email` | Configure SMTP / email templates |
| `config:themes` | Manage login/account/admin themes |
| `config:events` | Configure event listener settings |
| `config:realm-keys` | Manage signing/encryption keys |

### 2.5 Secrets Management

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

### 2.6 Audit

| Permission | Description |
|---|---|
| `audit:read` | View audit logs |
| `audit:export` | Export audit log data |
| `audit:configure` | Configure audit log retention |

### 2.7 Roles & Groups Management

| Permission | Description |
|---|---|
| `roles:list` | List available roles |
| `roles:read` | View role definitions |
| `roles:create` | Create new roles |
| `roles:update` | Modify role permission mappings |
| `roles:delete` | Delete roles |
| `groups:list` | List groups |
| `groups:read` | View group details and membership |
| `groups:create` | Create groups |
| `groups:update` | Modify group attributes |
| `groups:delete` | Delete groups |
| `groups:manage-members` | Add/remove group members |
| `groups:manage-roles` | Assign/revoke roles on groups |

### 2.8 Organization / Tenant Management

| Permission | Description |
|---|---|
| `orgs:list` | List organizations |
| `orgs:read` | View organization details |
| `orgs:create` | Create new organizations |
| `orgs:update` | Modify organization settings |
| `orgs:delete` | Delete organizations |
| `orgs:manage-members` | Invite/remove org members |
| `orgs:manage-idps` | Link/unlink identity providers |

### 2.9 Media (Portal-Specific)

| Permission | Description |
|---|---|
| `media:read` | Read/view media assets |
| `media:write` | Create/update media assets |
| `media:delete` | Delete media assets |
| `media:upload` | Upload new media files |
| `media:export` | Export media assets |
| `media:serve` | Serve media assets via public URLs |

**Total: 74 atomic permissions** across 9 resource categories.

---

## 3. Role-to-Permission Mapping (FR-5.3, FR-5.4)

### 3.1 Platform-Scoped Roles

#### `platform-superadmin`

Break-glass role. Maximum 2-3 humans. All 74 permissions granted.

```typescript
'platform-superadmin': ['*']  // Wildcard — all permissions
```

Unique capabilities (not granted to any other role):
- `config:realm-keys` — manage signing/encryption keys
- `secrets:admin:mount` — mount/unmount secrets engines
- `orgs:create`, `orgs:delete` — create/destroy organizations
- `audit:configure` — configure audit log retention
- `users:impersonate` — impersonate users

#### `platform-admin`

Day-to-day platform administration. Cannot modify realm keys or mount secrets engines.

```typescript
'platform-admin': [
  'users:list', 'users:read', 'users:create', 'users:update', 'users:delete',
  'users:assign-roles', 'users:assign-groups', 'users:reset-credentials', 'users:terminate-sessions',
  'clients:list', 'clients:read', 'clients:create', 'clients:update', 'clients:delete',
  'clients:rotate-secret', 'clients:manage-roles', 'clients:view-service-account',
  'idp:list', 'idp:read', 'idp:create', 'idp:update', 'idp:delete', 'idp:sync',
  'config:read', 'config:session-policy', 'config:password-policy', 'config:brute-force',
  'config:email', 'config:themes', 'config:events',
  'roles:list', 'roles:read', 'roles:create', 'roles:update', 'roles:delete',
  'groups:list', 'groups:read', 'groups:create', 'groups:update', 'groups:delete',
  'groups:manage-members', 'groups:manage-roles',
  'orgs:list', 'orgs:read', 'orgs:update', 'orgs:manage-members', 'orgs:manage-idps',
  'audit:read', 'audit:export',
  'secrets:personal:read', 'secrets:personal:write', 'secrets:personal:delete',
  'secrets:team:read', 'secrets:team:write', 'secrets:team:delete',
  'secrets:service:read', 'secrets:service:write', 'secrets:service:delete', 'secrets:service:rotate',
  'secrets:admin:read', 'secrets:admin:write',
  'media:read', 'media:write', 'media:delete', 'media:upload', 'media:export', 'media:serve',
]
```

#### `platform-operator`

Monitoring and triage. Read-heavy, limited write.

```typescript
'platform-operator': [
  'users:list', 'users:read', 'users:terminate-sessions',
  'clients:list', 'clients:read',
  'config:read',
  'audit:read', 'audit:export',
  'secrets:service:read',
  'media:read', 'media:export',
]
```

### 3.2 Organization-Scoped Roles

All permissions below are implicitly scoped to the user's organization.

#### `org-admin`

Full control within own organization.

```typescript
'org-admin': [
  'users:list', 'users:read', 'users:create', 'users:update', 'users:delete',
  'users:assign-roles', 'users:assign-groups', 'users:reset-credentials', 'users:terminate-sessions',
  'clients:list', 'clients:read', 'clients:create', 'clients:update', 'clients:delete',
  'clients:rotate-secret', 'clients:manage-roles', 'clients:view-service-account',
  'idp:list', 'idp:read', 'idp:create', 'idp:update', 'idp:delete',
  'config:read', 'config:session-policy', 'config:password-policy', 'config:brute-force',
  'roles:list', 'roles:read', 'roles:create', 'roles:update', 'roles:delete',
  'groups:list', 'groups:read', 'groups:create', 'groups:update', 'groups:delete',
  'groups:manage-members', 'groups:manage-roles',
  'orgs:read', 'orgs:update', 'orgs:manage-members', 'orgs:manage-idps',
  'audit:read', 'audit:export',
  'secrets:personal:read', 'secrets:personal:write', 'secrets:personal:delete',
  'secrets:team:read', 'secrets:team:write', 'secrets:team:delete',
  'secrets:service:read', 'secrets:service:write', 'secrets:service:delete', 'secrets:service:rotate',
  'media:read', 'media:write', 'media:delete', 'media:upload', 'media:export', 'media:serve',
]
```

#### `team-lead`

Manages team access and secrets. Cannot assign admin roles.

```typescript
'team-lead': [
  'users:list', 'users:read', 'users:assign-roles', 'users:assign-groups',
  'groups:list', 'groups:read', 'groups:manage-members',
  'roles:list', 'roles:read',
  'audit:read',
  'secrets:personal:read', 'secrets:personal:write', 'secrets:personal:delete',
  'secrets:team:read', 'secrets:team:write', 'secrets:team:delete',
  'secrets:service:read',
  'media:read', 'media:write', 'media:upload', 'media:export', 'media:serve',
]
```

#### `developer`

Active contributor, needs service secret access.

```typescript
'developer': [
  'users:list', 'users:read',
  'groups:list', 'groups:read',
  'roles:list', 'roles:read',
  'clients:list', 'clients:read',
  'secrets:personal:read', 'secrets:personal:write', 'secrets:personal:delete',
  'secrets:team:read', 'secrets:team:write',
  'secrets:service:read',
  'media:read', 'media:write', 'media:upload', 'media:export', 'media:serve',
]
```

#### `member`

Standard organization member.

```typescript
'member': [
  'users:list', 'users:read',
  'groups:list', 'groups:read',
  'secrets:personal:read', 'secrets:personal:write', 'secrets:personal:delete',
  'secrets:team:read',
  'media:read', 'media:export',
]
```

#### `viewer`

Read-only access.

```typescript
'viewer': [
  'users:list', 'users:read',
  'groups:list', 'groups:read',
  'roles:list', 'roles:read',
  'config:read',
  'secrets:personal:read',
  'media:read', 'media:export',
]
```

#### `guest`

Minimal access, external collaborators.

```typescript
'guest': [
  'users:read',  // self only
  'secrets:personal:read',
  'media:read',
]
```

### 3.3 Service Identity Roles (FR-5.4)

| Service Role | Permissions |
|---|---|
| `svc-platform-core` | `users:list`, `users:read`, `secrets:service:read`, `secrets:admin:read` |
| `svc-platform-infra` | `config:read`, `audit:read`, `secrets:admin:read`, `secrets:admin:write`, `secrets:service:read`, `secrets:service:write`, `secrets:service:rotate` |
| `svc-platform-monitor` | `audit:read`, `audit:export`, `config:read`, `users:list`, `clients:list` |
| `svc-tenant-app` | `users:list` (own org), `users:read` (own org), `secrets:service:read`, `secrets:team:read` |
| `svc-tenant-worker` | `secrets:service:read` |
| `svc-cicd-deployer` | `secrets:service:read`, `secrets:service:write`, `secrets:service:rotate`, `clients:read`, `clients:rotate-secret` |
| `svc-cicd-scanner` | `audit:read`, `config:read`, `users:list`, `clients:list` |
| `svc-cicd-builder` | `secrets:service:read` |

---

## 4. Permission Evaluation Model (FR-5.6)

### 4.1 Evaluation Algorithm

Adopt **explicit-deny-overrides** (AWS pattern):

```
function evaluate(principal, resource, action):
  1. Collect all policies:
     - identity-based (user's direct roles)
     - group-based (roles inherited from group membership)
     - org-scoped (roles from organization membership)

  2. If ANY policy has explicit DENY → DENY

  3. Compute scope:
     - Platform role → scope = global (all orgs)
     - Org role → scope = principal's org only
     - Resource outside scope → DENY

  4. If ANY policy has ALLOW for resource:action → ALLOW

  5. Default → DENY
```

### 4.2 Scope Resolution

Platform roles operate globally. Organization roles are restricted to the user's organization:

```typescript
function isInScope(principal: Principal, resource: Resource): boolean {
  // Platform roles: global scope
  if (principal.roles.some(r => PLATFORM_ROLES.includes(r))) return true

  // Org roles: scoped to principal's organization
  if (resource.orgId && principal.tenantId !== resource.orgId) return false

  return true
}

const PLATFORM_ROLES = ['platform-superadmin', 'platform-admin', 'platform-operator']
```

### 4.3 Escalation Guards (FR-5.7)

#### Role Assignment Ceiling

A user can only assign roles **at or below** their own level. This prevents privilege escalation:

```typescript
const ROLE_CEILING: Record<string, string[]> = {
  'platform-superadmin': ['platform-superadmin', 'platform-admin', 'platform-operator',
                           'org-admin', 'team-lead', 'developer', 'member', 'viewer', 'guest'],
  'platform-admin':      ['platform-operator',
                           'org-admin', 'team-lead', 'developer', 'member', 'viewer', 'guest'],
  'org-admin':            ['org-admin', 'team-lead', 'developer', 'member', 'viewer', 'guest'],
  'team-lead':            ['developer', 'member', 'viewer', 'guest'],
  'developer':            [],  // Cannot assign roles
  'member':               [],
  'viewer':               [],
  'guest':                [],
}
```

Rules:
- `org-admin` CANNOT escalate to platform roles (FR-5.5 scoping rules)
- `team-lead` can assign `developer` but not `org-admin` (FR-5.5 role assignment ceiling)
- Platform roles can only be granted by `platform-superadmin`
- `platform-admin` cannot grant `platform-superadmin` or `platform-admin`

#### Implementation in API Routes

```typescript
// app/api/account-manager/users/[userId]/roles/route.ts
export const POST = withPermission('users:assign-roles', async (req, session, ctx) => {
  const targetRoles = await req.json()  // roles to assign
  const callerRoles = session.user.roles

  // Determine caller's ceiling
  const ceiling = callerRoles.flatMap(r => ROLE_CEILING[r] ?? [])
  const uniqueCeiling = new Set(ceiling)

  // Reject if any target role exceeds ceiling
  for (const role of targetRoles) {
    if (!uniqueCeiling.has(role.name)) {
      return Response.json(
        { error: `Cannot assign role '${role.name}': exceeds your authority` },
        { status: 403 }
      )
    }
  }

  // Proceed with assignment
  await keycloakAdmin.assignUserRealmRoles(userId, targetRoles)
})
```

### 4.4 Least Privilege Enforcement (FR-5.7)

| Rule | Implementation |
|------|---------------|
| FR-5.7.1 New org members default to `viewer` | Bootstrap creates org members with `viewer` role. Elevation requires `org-admin` approval. |
| FR-5.7.2 Superadmin uses JIT elevation | `platform-superadmin` users SHOULD use `platform-operator` for day-to-day work. Break-glass access audited. |
| FR-5.7.3 One identity per service | Each service has its own Keycloak client + OpenBao AppRole. No shared service accounts. |
| FR-5.7.4 No human-equivalent roles for services | Service accounts MUST NOT receive `org-admin`, `platform-admin`, or `platform-superadmin` roles. |
| FR-5.7.5 Short token TTLs | Keycloak access: 5 min. OpenBao service: 1h max. OpenBao admin: 15 min max. |
| FR-5.7.6 Single-use SecretIDs for CI/CD | AppRole `secret_id_num_uses: 1` for CI/CD roles. |
| FR-5.7.7 CIDR-bound AppRoles | `token_bound_cidrs` set where network topology is stable. |

---

## 5. API Route Permission Matrix

### 5.1 Current State

Every API route in the portal with its current guard and required permission:

| Method | Route | Guard | Current Permission | Target Permission |
|--------|-------|-------|--------------------|-------------------|
| GET | `/api/config` | `withPermission` | `read` | `config:read` |
| POST | `/api/config` | `withPermission` | `admin:config` | `config:read` + resource-specific |
| PATCH | `/api/config` | `withPermission` | `admin:config` | `config:read` + resource-specific |
| GET | `/api/file` | `withPermission` | `read` | `media:read` |
| GET | `/api/file-hash` | `withPermission` | `read` | `media:read` |
| GET | `/api/tree` | `withPermission` | `read` | `media:read` |
| POST | `/api/tree` | `withPermission` | `write` | `media:write` |
| GET | `/api/media` | `withPermission` | `read` | `media:read` |
| GET | `/api/media/list` | `withPermission` | `read` | `media:read` |
| GET | `/api/media/asset/[root]/[[...path]]` | `withPermission` | `read` | `media:read` |
| GET | `/api/library` | `withPermission` | `read` | `media:read` |
| POST | `/api/library` | `withPermission` | `write` | `media:write` |
| PATCH | `/api/library/[id]` | `withPermission` | `write` | `media:write` |
| DELETE | `/api/library/[id]` | `withPermission` | `delete` | `media:delete` |
| POST | `/api/library/[id]/delete` | `withPermission` | `delete` | `media:delete` |
| GET | `/api/upload` | `withPermission` | `read` | `media:upload` |
| PUT | `/api/upload` | `withPermission` | `upload` | `media:upload` |
| GET | `/api/export` | `withPermission` | `export` | `media:export` |
| POST | `/api/export` | `withPermission` | `export` | `media:export` |
| POST | `/api/convert` | `withPermission` | `export` | `media:export` |
| GET | `/api/serve` | `withPermission` | `read` | `media:read` |
| POST | `/api/serve` | `withPermission` | `serve` | `media:serve` |
| GET | `/api/serve/[id]` | `withPermission` | `read` | `media:read` |
| DELETE | `/api/serve/[id]` | `withPermission` | `serve` | `media:serve` |
| GET | `/api/served/[id]/[[...path]]` | `withPermission` | `read` | `media:read` |
| GET | `/api/pathinfo` | `withPermission` | `read` | `media:read` |
| GET | `/api/events` | `withPermission` | `read` | `media:read` |
| GET | `/api/app/status` | `withPermission` | `read` | `media:read` |
| GET | `/api/automation` | `withPermission` | `read` | `media:read` |
| POST | `/api/automation` | `withPermission` | `write` | `media:write` |
| GET | `/api/latex` | `withPermission` | `read` | `media:read` |
| POST | `/api/latex` | `withPermission` | `write` | `media:write` |
| GET | `/api/account-manager/roles` | `withSession` | (any) | `roles:list` |
| GET | `/api/account-manager/providers` | `withSession` | (any) | `idp:list` |
| GET | `/api/account-manager/users` | `withPermission` | `admin:accounts` | `users:list` |
| POST | `/api/account-manager/users` | `withPermission` | `admin:accounts` | `users:create` |
| GET | `/api/account-manager/users/[userId]` | `withPermission` | `admin:accounts` | `users:read` |
| PUT | `/api/account-manager/users/[userId]` | `withPermission` | `admin:accounts` | `users:update` |
| DELETE | `/api/account-manager/users/[userId]` | `withPermission` | `admin:accounts` | `users:delete` |
| PUT | `/api/account-manager/users/[userId]/password` | `withPermission` | `admin:accounts` | `users:reset-credentials` |
| GET | `/api/account-manager/users/[userId]/roles` | `withPermission` | `admin:accounts` | `users:read` |
| POST | `/api/account-manager/users/[userId]/roles` | `withPermission` | `admin:accounts` | `users:assign-roles` |
| DELETE | `/api/account-manager/users/[userId]/roles` | `withPermission` | `admin:accounts` | `users:assign-roles` |
| GET | `/api/account-manager/users/[userId]/sessions` | `withPermission` | `admin:accounts` | `users:read` |
| DELETE | `/api/account-manager/users/[userId]/sessions` | `withPermission` | `admin:accounts` | `users:terminate-sessions` |
| GET | `/api/account-manager/clients` | `withPermission` | `admin:accounts` | `clients:list` |
| POST | `/api/account-manager/clients` | `withPermission` | `admin:accounts` | `clients:create` |
| GET | `/api/account-manager/clients/[clientUUID]` | `withPermission` | `admin:accounts` | `clients:read` |
| PUT | `/api/account-manager/clients/[clientUUID]` | `withPermission` | `admin:accounts` | `clients:update` |
| DELETE | `/api/account-manager/clients/[clientUUID]` | `withPermission` | `admin:accounts` | `clients:delete` |
| GET | `/api/account-manager/clients/[clientUUID]/secret` | `withPermission` | `admin:accounts` | `clients:read` |
| POST | `/api/account-manager/clients/[clientUUID]/secret` | `withPermission` | `admin:accounts` | `clients:rotate-secret` |
| GET | `/api/account-manager/accounts` | `withSession` | (any) | `users:read` (self) |
| POST | `/api/account-manager/accounts` | `withPermission` | `admin:accounts` | `users:create` |
| DELETE | `/api/account-manager/accounts/[accountId]` | `withPermission` | `admin:accounts` | `users:delete` |
| PATCH | `/api/account-manager/accounts/[accountId]` | `withPermission` | `admin:accounts` | `users:update` |

### 5.2 Migration Strategy

The permission system migration happens in two phases:

**Phase 1 — Backward Compatible**: Add new `resource:action` permissions to `ROLE_PERMISSIONS` alongside legacy permissions. Both work:

```typescript
const ROLE_PERMISSIONS: Record<string, readonly Permission[]> = {
  // Legacy roles continue to work
  admin:  ['read', 'write', 'delete', 'upload', 'export', 'serve', 'admin:accounts', 'admin:config',
           // New fine-grained permissions (superset)
           'users:list', 'users:read', 'users:create', /* ... */],
  // New roles added
  'platform-superadmin': ['*'],
  'platform-admin': ['users:list', 'users:read', /* ... */],
  // ...
}
```

**Phase 2 — Full Migration**: Remove legacy permission names. Update all `withPermission()` calls to use `resource:action` format. Remove legacy roles from `ROLE_PERMISSIONS`.

---

## 6. Backward Compatibility (FR-5.8)

### 6.1 Legacy Role Mapping

| Legacy Role | Maps To | Notes |
|-------------|---------|-------|
| `admin` | `platform-superadmin` | Wildcard permissions |
| `editor` | `developer` | `media:*` + `secrets:personal:*` |
| `viewer` | `viewer` | No change in permissions |
| `guest` | `guest` | No change in permissions |

### 6.2 `resolvePermissions()` Changes

The function MUST accept both legacy and new role names during migration:

```typescript
function resolvePermissions(roles: string[]): Set<Permission> {
  const perms = new Set<Permission>()
  for (const role of roles) {
    // Check new role names first
    const granted = ROLE_PERMISSIONS[role]
    if (granted) {
      if (granted.includes('*')) {
        // Wildcard: grant all permissions
        for (const allPerms of Object.values(ROLE_PERMISSIONS)) {
          for (const p of allPerms) if (p !== '*') perms.add(p)
        }
      } else {
        for (const p of granted) perms.add(p)
      }
    }
    // Legacy alias check
    const alias = LEGACY_ROLE_MAP[role]
    if (alias) {
      const aliasGranted = ROLE_PERMISSIONS[alias]
      if (aliasGranted) for (const p of aliasGranted) perms.add(p)
    }
  }
  return perms
}

const LEGACY_ROLE_MAP: Record<string, string> = {
  admin: 'platform-superadmin',
  editor: 'developer',
  // viewer and guest map to themselves
}
```

### 6.3 `hasPermission()` Changes

Must support both old and new permission names:

```typescript
function hasPermission(roles: string[], permission: Permission): boolean {
  const perms = resolvePermissions(roles)
  // Direct match
  if (perms.has(permission)) return true
  // Legacy fallback: map old permission to new equivalent
  const legacyMap: Record<string, Permission[]> = {
    'read': ['media:read', 'config:read'],
    'write': ['media:write'],
    'delete': ['media:delete'],
    'upload': ['media:upload'],
    'export': ['media:export'],
    'serve': ['media:serve'],
    'admin:accounts': ['users:list', 'users:read', 'users:create', /* ... */],
    'admin:config': ['config:session-policy', 'config:password-policy', /* ... */],
  }
  // If checking a legacy permission, see if any mapped new permission is granted
  const mapped = legacyMap[permission]
  if (mapped) return mapped.some(p => perms.has(p))
  return false
}
```

---

## 7. Requirement Traceability

| Requirement | Section | Status |
|-------------|---------|--------|
| FR-4.1 User CRUD via portal | 5.1 (route matrix) | Specified |
| FR-4.2 Role/group assignment | 5.1 (route matrix) | Specified |
| FR-4.3 Force password reset | 5.1 (route matrix) | Specified |
| FR-4.4 Self-service profile | Via Keycloak account console | Deferred to SPEC-AUTH |
| FR-4.5 User → OpenBao provisioning | — | Deferred to SPEC-SECRETS |
| FR-4.6 User deprovisioning | — | Deferred to SPEC-SECRETS |
| FR-5.1 Permission format | 2 (resource:action) | Specified |
| FR-5.2 Atomic permission registry | 2 (74 permissions) | Specified |
| FR-5.3 Human actor hierarchy | 3.1, 3.2 | Specified |
| FR-5.4 Service identity hierarchy | 3.3 | Specified |
| FR-5.5 Organization/tenant scoping | 4.2 | Specified |
| FR-5.6 Permission evaluation model | 4.1 | Specified |
| FR-5.7 Least privilege enforcement | 4.3, 4.4 | Specified |
| FR-5.8 Backward compatibility | 6 | Specified |
