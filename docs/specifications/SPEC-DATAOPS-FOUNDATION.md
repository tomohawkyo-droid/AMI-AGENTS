# Specification: AMI-DATAOPS Polyglot Persistence Foundation

**Date:** 2026-02-01
**Status:** DEPRECATED
**Type:** Specification

> **Deprecation note (2026-04-05):** The code described in this document (`base/backend/dataops/`) has been migrated to `projects/AMI-DATAOPS/`. This document is retained as historical reference for the migration.

**Source Codebase (original):** `base/backend/dataops/` (~24,000 LOC, 96 files)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Audit](#2-architecture-audit)
3. [File Inventory & Triage](#3-file-inventory--triage)
4. [Critical Bugs](#4-critical-bugs)
5. [Backend Adapters](#5-backend-adapters)
6. [Data Model Layer](#6-data-model-layer)
7. [Sync Strategy System](#7-sync-strategy-system)
8. [Security Layer Triage](#8-security-layer-triage)
9. [Migration to projects/AMI-DATAOPS](#9-migration-to-projectsami-dataops)
10. [Public API Design](#10-public-api-design)
11. [Integration with AMI Services](#11-integration-with-ami-services)
12. [Configuration System](#12-configuration-system)
13. [Testing Strategy](#13-testing-strategy)
14. [Multi-Backend ORM Landscape](#14-multi-backend-orm-landscape)

---

## 1. Executive Summary

### 1.1. What Exists

`base/backend/dataops/` is a custom **polyglot persistence framework** supporting 8 backend types with configurable multi-storage synchronization. It provides a unified CRUD interface across fundamentally different database paradigms: relational (PostgreSQL), graph (Dgraph), key-value (Redis), vector (PGVector), secrets (OpenBao/Vault), REST APIs, time-series (Prometheus), and document (MongoDB, no adapter implemented).

| Metric | Value |
|---|---|
| Total files | 96 Python files |
| Total LOC | ~24,000 |
| Backend adapters | 7 implemented + 1 slot (MongoDB) |
| Sync strategies | 6 (SEQUENTIAL, PARALLEL, PRIMARY_FIRST, EVENTUAL, QUORUM, MASTER_SLAVE) |
| Domain models | 19 files |
| Security modules | 10 files (~4,200 LOC) |
| Test files | 5 (sparse coverage) |
| Current consumers | **Zero** |

### 1.2. What's Wrong

| Category | Lines | % of Total |
|---|---|---|
| Dead security modules (zero imports) | 2,854 | 12% |
| Scaffolding (compliance_reporting.py) | 1,006 | 4% |
| Duplicate implementation (two UnifiedCRUD) | 853 | 4% |
| Runtime-breaking bugs (DAOFactory signature) | Critical | - |
| Speculative models (BPMN, 2 NotImplementedError) | 1,050 | 4% |
| **Total waste/broken** | **~5,763** | **~24%** |

### 1.3. Why Not Replace It

Exhaustive research confirms: **no off-the-shelf Python library provides polyglot persistence across relational + graph + secrets backends with configurable sync strategies.** The closest options:

- **SQLAlchemy**: relational only (no graph, no vault)
- **SQErzo**: multi-graph only (Neo4j, RedisGraph, Neptune), no relational
- **Prisma Python**: multi-relational only, no graph or vault
- **Tortoise ORM**: async relational only

The custom architecture (BaseDAO → DAOFactory → UnifiedCRUD → SyncStrategy) is the correct pattern. The implementation needs cleanup, not replacement.

### 1.4. Goal

Extract `base/backend/dataops/` into `projects/AMI-DATAOPS/` in the agents monorepo. Clean up the ~24% waste. Fix critical bugs. Establish a clean public API. Make it the shared persistence foundation for all AMI services.

---

## 2. Architecture Audit

### 2.1. Layer Diagram

```mermaid
flowchart TD
    subgraph "Consumer Services"
        Auth["AMI-AUTH"]
        Trading["AMI-TRADING"]
        Portal["AMI-PORTAL"]
    end

    subgraph "AMI-DATAOPS Public API"
        CRUD["UnifiedCRUD<br/>create / read / update / delete / find"]
        Models["StorageModel<br/>Base class + Meta config"]
        Config["StorageConfig<br/>+ StorageConfigFactory"]
    end

    subgraph "Core Layer"
        DAO["BaseDAO[T]<br/>Abstract interface"]
        Factory["DAOFactory<br/>Registry-based creation"]
        Registry["DAORegistry<br/>Auto-discovery"]
        Sync["SyncStrategy<br/>Multi-storage orchestration"]
    end

    subgraph "Backend Adapters"
        PG["PostgreSQLDAO"]
        DG["DgraphDAO"]
        RD["RedisDAO"]
        PGV["PGVectorDAO"]
        OB["OpenBaoDAO"]
        REST["RestDAO"]
        PROM["PrometheusDAO"]
    end

    subgraph "Storage Backends"
        PGS[(PostgreSQL)]
        DGS[(Dgraph)]
        RDS[(Redis)]
        PGVS[(PGVector)]
        OBS[(OpenBao)]
        RESTS[REST APIs]
        PROMS[(Prometheus)]
    end

    Auth --> CRUD
    Trading --> CRUD
    Portal --> CRUD
    CRUD --> Sync
    CRUD --> Factory
    Sync --> Factory
    Factory --> Registry
    Registry --> PG & DG & RD & PGV & OB & REST & PROM
    PG --> PGS
    DG --> DGS
    RD --> RDS
    PGV --> PGVS
    OB --> OBS
    REST --> RESTS
    PROM --> PROMS
    Models -.-> CRUD
    Config -.-> Factory
```

### 2.2. What's Good

| Component | Location | Why It's Good |
|---|---|---|
| **BaseDAO[T] interface** | `core/dao.py` (288 lines) | Clean generic abstract class. 12 well-defined methods. All adapters implement it consistently. |
| **DAOFactory + Registry** | `core/factory.py` + registry | Auto-discovers DAO classes by scanning `implementations/`. Extensible without modifying factory code. |
| **StorageConfig** | `models/storage_config.py` (109 lines) | Pydantic model with connection string generation, env var support, sensible defaults per storage type. |
| **StorageConfigFactory** | `models/storage_config_factory.py` (79 lines) | Loads from YAML with auto-merge of defaults. Clean `from_yaml(name)` API. |
| **Individual DAO adapters** | `implementations/*/` | Each adapter is self-contained, async, with proper connection pooling. PostgreSQL, Dgraph, Redis, PGVector, OpenBao, REST, Prometheus all work independently. |
| **StorageModel base** | `models/base_model.py` (269 lines) | `to_storage_dict()` / `from_storage_dict()` serialization. `Meta` class for declarative storage config. |
| **SyncStrategy enum** | `security/sync_strategy.py` | 6 well-defined strategies with clear semantics. Conflict resolution options. |

### 2.3. What's Broken

| Component | Location | Problem |
|---|---|---|
| **Duplicate UnifiedCRUD** | `core/unified_crud.py` (372L) vs `services/unified_crud.py` (481L) | Two competing implementations. Core handles single-storage DAO lifecycle. Services handles multi-storage sync. Models use core, tests use services. |
| **DAOFactory signature** | `core/factory.py:23` | Expects `(cls, config, collection_name, **kwargs)` but callers pass `(cls, config)` or `(model_class, config)`. Will crash at runtime. |
| **compliance_reporting.py** | `security/compliance_reporting.py` (1,006L) | 99% stubs. SOC2Reporter: 9/11 methods return `False` with "not yet implemented". Zero imports anywhere. |
| **Empty `__init__.py`** | All packages | Correct per project convention. All `__init__.py` must be empty. Fully qualified imports are the standard. |

### 2.4. What's Dead

| Module | Lines | Evidence |
|---|---|---|
| `security/multi_tenancy.py` | 411 | Zero imports across entire codebase |
| `security/audit_trail.py` | 377 | Blockchain-based audit with proof-of-work mining (!). Zero imports. |
| `security/query_sanitizer.py` | 391 | SQL injection prevention. Not integrated with any DAO. |
| `security/rate_limiter.py` | 288 | Token bucket. No middleware hooks. Zero imports. |
| `security/resilience.py` | 394 | Circuit breaker + retry. Not used by any DAO client. |
| `security/cache_layer.py` | 522 | Caching decorator. Zero imports. |
| `security/compliance_reporting.py` | 1,006 | 99% stubs as detailed above. |
| **Total dead** | **3,389** | |

---

## 3. File Inventory & Triage

### 3.1. Disposition Legend

| Code | Meaning |
|---|---|
| **MOVE** | Copy to AMI-DATAOPS as-is |
| **FIX** | Move + fix critical issues |
| **SLIM** | Move + remove dead code / simplify |
| **DELETE** | Do not migrate. Dead code. |
| **DEFER** | Do not migrate now. Revisit when needed. |
| **DOMAIN** | Domain-specific model. Stays with its owning service, not in dataops. |

### 3.2. Core Layer

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `core/dao.py` | 288 | **MOVE** | BaseDAO[T] abstract. Clean. |
| `core/unified_crud.py` | 372 | **FIX** | Merge with services/unified_crud.py into single class |
| `core/factory.py` | 41 | **FIX** | Fix signature mismatch with callers |
| `core/storage_types.py` | 49 | **MOVE** | StorageType + OperationType enums |
| `core/exceptions.py` | 35 | **MOVE** | StorageError, ValidationError, ConnectionError |
| `core/execution_manager.py` | 189 | **MOVE** | Transaction/execution context |
| `core/model_registry.py` | 86 | **MOVE** | Model metadata registry |
| `core/graph_relations.py` | 330 | **MOVE** | Graph relationship handlers |

### 3.3. Services Layer

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `services/unified_crud.py` | 481 | **FIX** | Merge into core/unified_crud.py. Keep: multi-storage sync, SyncStrategy, operation logging. Drop: duplicate find/create/update/delete. |
| `services/decorators.py` | 247 | **MOVE** | @sensitive_field, @record_event, @cached_result |

### 3.4. Models Layer

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `models/base_model.py` | 269 | **MOVE** | StorageModel base class. Foundation. |
| `models/storage_config.py` | 109 | **MOVE** | StorageConfig Pydantic model |
| `models/storage_config_factory.py` | 79 | **MOVE** | YAML config loader |
| `models/types.py` | 27 | **MOVE** | AuthProviderType enum (shared) |
| `models/security.py` | 207 | **MOVE** | Permission, SecurityContext, ACLEntry, DataClassification |
| `models/secured_mixin.py` | 201 | **MOVE** | SecuredModelMixin |
| `models/storage_mixin.py` | 17 | **MOVE** | StorageConfigMixin |
| `models/secret_pointer.py` | 38 | **MOVE** | VaultFieldPointer |
| `models/ip_config.py` | 48 | **MOVE** | IPConfig for network addressing |
| `models/ssh_config.py` | 58 | **MOVE** | SSHConfig |
| `models/user.py` | 207 | **DOMAIN** | Belongs in AMI-AUTH, not dataops |
| `models/password.py` | 163 | **DOMAIN** | Belongs in AMI-AUTH |
| `models/mfa.py` | 98 | **DOMAIN** | Belongs in AMI-AUTH |
| `models/bpmn.py` | 627 | **DEFER** | Speculative. 2 NotImplementedError. No process engine. Revisit when needed. |
| `models/bpmn_relational.py` | 423 | **DEFER** | Tied to bpmn.py |
| `models/gdpr.py` | 173 | **DEFER** | Compliance feature. No consumer. |
| `models/retention.py` | 134 | **DEFER** | Retention policies. No consumer. |

### 3.5. Implementations Layer (Backend Adapters)

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `implementations/sql/postgresql_dao.py` | 370 | **MOVE** | Core adapter. Production-ready. |
| `implementations/sql/postgresql_create.py` | 316 | **MOVE** | |
| `implementations/sql/postgresql_read.py` | 189 | **MOVE** | |
| `implementations/sql/postgresql_update.py` | 64 | **MOVE** | |
| `implementations/sql/postgresql_delete.py` | 34 | **MOVE** | |
| `implementations/sql/postgresql_util.py` | 153 | **MOVE** | |
| `implementations/graph/dgraph_dao.py` | 181 | **MOVE** | |
| `implementations/graph/dgraph_create.py` | 102 | **MOVE** | |
| `implementations/graph/dgraph_read.py` | 317 | **MOVE** | |
| `implementations/graph/dgraph_update.py` | 452 | **MOVE** | |
| `implementations/graph/dgraph_delete.py` | 89 | **MOVE** | |
| `implementations/graph/dgraph_graph.py` | 395 | **MOVE** | |
| `implementations/graph/dgraph_util.py` | 384 | **MOVE** | |
| `implementations/graph/dgraph_relations.py` | 533 | **MOVE** | |
| `implementations/mem/redis_dao.py` | 431 | **MOVE** | |
| `implementations/mem/redis_create.py` | 133 | **MOVE** | |
| `implementations/mem/redis_read.py` | 261 | **MOVE** | |
| `implementations/mem/redis_update.py` | 131 | **MOVE** | |
| `implementations/mem/redis_delete.py` | 58 | **MOVE** | |
| `implementations/mem/redis_inmem.py` | 55 | **MOVE** | |
| `implementations/mem/redis_util.py` | 91 | **MOVE** | |
| `implementations/vec/pgvector_dao.py` | 387 | **MOVE** | |
| `implementations/vec/pgvector_vector.py` | 185 | **MOVE** | |
| `implementations/vec/pgvector_create.py` | 99 | **MOVE** | |
| `implementations/vec/pgvector_read.py` | 314 | **MOVE** | |
| `implementations/vec/pgvector_update.py` | 126 | **MOVE** | |
| `implementations/vec/pgvector_delete.py` | 48 | **MOVE** | |
| `implementations/vec/pgvector_util.py` | 222 | **MOVE** | |
| `implementations/rest/rest_dao.py` | 701 | **MOVE** | |
| `implementations/rest/rest_operations.py` | 199 | **MOVE** | |
| `implementations/vault/openbao_dao.py` | 342 | **MOVE** | |
| `implementations/timeseries/prometheus_dao.py` | 577 | **MOVE** | |
| `implementations/timeseries/prometheus_read.py` | 393 | **MOVE** | |
| `implementations/timeseries/prometheus_write.py` | 288 | **MOVE** | |
| `implementations/timeseries/prometheus_models.py` | 188 | **MOVE** | |
| `implementations/timeseries/prometheus_connection.py` | 99 | **MOVE** | |
| `implementations/embedding_service.py` | 262 | **MOVE** | Vector embedding service |

### 3.6. Security Layer

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `security/sync_strategy.py` | 471 | **FIX** | Keep SyncStrategy + DataSynchronizer. Deduplicate enum from services/unified_crud.py. |
| `security/encryption.py` | 391 | **MOVE** | Field-level encryption. Useful. |
| `security/compliance_reporting.py` | 1,006 | **DELETE** | 99% stubs. Zero imports. |
| `security/audit_trail.py` | 377 | **DELETE** | Blockchain proof-of-work mining audit. Unused. |
| `security/multi_tenancy.py` | 411 | **DELETE** | Zero imports. |
| `security/query_sanitizer.py` | 391 | **DEFER** | Good idea, not integrated. Revisit when DAOs wire it in. |
| `security/rate_limiter.py` | 288 | **DELETE** | Zero imports. Each service has its own. |
| `security/resilience.py` | 394 | **DEFER** | Circuit breaker + retry. Good idea, not wired. Revisit. |
| `security/cache_layer.py` | 522 | **DELETE** | Zero imports. |

### 3.7. Secrets Management

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `secrets/client.py` | 291 | **MOVE** | Secrets client for vault |
| `secrets/adapter.py` | 121 | **MOVE** | Hydration/serialization |
| `secrets/repository.py` | 136 | **MOVE** | Repository pattern for secrets |
| `secrets/config.py` | 28 | **MOVE** | |
| `secrets/pointer.py` | 26 | **MOVE** | VaultFieldPointer |

### 3.8. Storage / Utils / Other

| File | Lines | Disposition | Notes |
|---|---|---|---|
| `storage/registry.py` | 171 | **MOVE** | StorageRegistry |
| `storage/validator.py` | 178 | **MOVE** | Config validation |
| `utils/http_client.py` | 140 | **MOVE** | HTTP client with retries |
| `acquisition/download_youtube_transcript.py` | 152 | **DELETE** | Data ingestion helper. Not persistence. |

### 3.9. Triage Summary

| Disposition | Files | Lines | % |
|---|---|---|---|
| **MOVE** (as-is) | ~60 | ~14,200 | 59% |
| **FIX** (move + fix bugs) | 4 | ~1,365 | 6% |
| **SLIM** (move + trim) | 0 | 0 | 0% |
| **DELETE** (dead code) | 6 | 2,982 | 12% |
| **DEFER** (not now) | 6 | 2,411 | 10% |
| **DOMAIN** (stays with service) | 3 | 468 | 2% |
| **Total** | ~79 | ~21,426 | |

**Net migration: ~15,565 lines across ~64 files into AMI-DATAOPS.**

---

## 4. Critical Bugs

### 4.1. P0: Duplicate UnifiedCRUD

**Problem**: Two classes both named `UnifiedCRUD` in different locations.

| File | Lines | Role | Used By |
|---|---|---|---|
| `core/unified_crud.py` | 372 | Single-storage DAO lifecycle, UID registry, model-to-storage mapping | `base_model.py` (line 12) |
| `services/unified_crud.py` | 481 | Multi-storage sync, SyncStrategy, SecurityContext, operation logging | Tests (`test_dataops_security.py:18`) |

**Fix**: Merge into a single `UnifiedCRUD` class in `core/unified_crud.py`:
- Keep from core: DAO caching, UID registry, event loop detection, `_get_dao()` method
- Keep from services: SyncStrategy integration, SecurityContext parameter, operation logging, `sync_instance()`, `bulk_create()`, `bulk_delete()`
- Deduplicate: `create()`, `read()`, `update()`, `delete()`, `find()` by merging parameter lists, where core logic handles single-storage and services logic wraps for multi-storage

**SPEC-DAO-001**: There shall be exactly one `UnifiedCRUD` class. Single-storage operations use `config_index=0` (default). Multi-storage operations are triggered when the model's `Meta.storage_configs` contains multiple entries.

### 4.2. P0: DAOFactory Signature Mismatch

**Problem**: Factory method signature doesn't match any call site.

```python
# factory.py:23, current signature:
def create(cls, config: StorageConfig, collection_name: str, **kwargs) -> Any:

# base_model.py:138, call:
dao = DAOFactory.create(cls, config)  # Missing collection_name!

# core/unified_crud.py:119, call:
dao = DAOFactory.create(model_class, config)  # model_class != config

# core/unified_crud.py:363, call:
dao = DAOFactory.create(model_class, config)  # Same mismatch
```

**Fix**: Update `DAOFactory.create()` to derive `collection_name` from the model class:

```python
@classmethod
def create(
    cls,
    model_class: type[StorageModel],
    config: StorageConfig,
    collection_name: str | None = None,
    **kwargs: Any,
) -> BaseDAO:
    if collection_name is None:
        meta = getattr(model_class, "Meta", None)
        collection_name = (
            getattr(meta, "path", None) or model_class.__name__.lower()
        )
    # ... existing registry lookup
```

**SPEC-DAO-002**: `DAOFactory.create()` shall accept `collection_name` as an optional parameter, defaulting to `model_class.Meta.path` when omitted.

### 4.3. P1: SyncStrategy Enum Defined Twice

**Problem**: `SyncStrategy` is defined in both `security/sync_strategy.py` and `services/unified_crud.py`.

**Fix**: Single definition in `core/storage_types.py` alongside `StorageType` and `OperationType`. Both consumers import from there.

---

## 5. Backend Adapters

### 5.1. Adapter Matrix

| Adapter | StorageType | Files | LOC | Driver | Port | Status |
|---|---|---|---|---|---|---|
| **PostgreSQLDAO** | RELATIONAL | 6 | ~1,126 | `asyncpg` | 5432 | Production-ready |
| **DgraphDAO** | GRAPH | 8 | ~2,653 | `pydgraph` (gRPC) | 9080 | Production-ready |
| **RedisDAO** | INMEM | 7 | ~1,160 | `redis` | 6379 | Production-ready |
| **PGVectorDAO** | VECTOR | 7 | ~1,381 | `asyncpg` + pgvector | 5432 | Production-ready |
| **OpenBaoDAO** | VAULT | 1 | 342 | HTTP (aiohttp/httpx) | 8200 | Production-ready |
| **RestDAO** | REST | 2 | ~900 | HTTP (aiohttp/httpx) | 443 | Production-ready |
| **PrometheusDAO** | TIMESERIES | 5 | ~1,545 | HTTP (PromQL) | 9090 | Production-ready ¹ |
| **MongoDB** | DOCUMENT | 0 | 0 | N/A | 27017 | **Not implemented** |

> ¹ Prometheus is pull-based metrics, not a general-purpose store. The adapter is read-heavy (PromQL queries) with limited write support (push gateway only). CRUD semantics (`update`, `delete`) do not map naturally.

### 5.2. BaseDAO[T] Interface

All adapters implement this abstract interface (`core/dao.py`, 288 lines):

```python
class BaseDAO(ABC, Generic[T]):
    # Lifecycle
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def test_connection(self) -> bool: ...

    # CRUD
    async def create(self, instance: T) -> str: ...
    async def find_by_id(self, id: str) -> T | None: ...
    async def find_one(self, query: dict) -> T | None: ...
    async def find(self, query: dict, limit: int, skip: int) -> list[T]: ...
    async def update(self, id: str, data: dict) -> None: ...
    async def delete(self, id: str) -> bool: ...

    # Bulk
    async def bulk_create(self, instances: list[T]) -> list[str]: ...
    async def bulk_update(self, updates: list[dict]) -> None: ...
    async def bulk_delete(self, ids: list[str]) -> int: ...

    # Query
    async def count(self, query: dict) -> int: ...
    async def exists(self, id: str) -> bool: ...
    async def raw_read_query(self, query: str, params: dict) -> list[dict]: ...
    async def raw_write_query(self, query: str, params: dict) -> int: ...

    # Introspection
    async def list_databases(self) -> list[str]: ...
    async def list_schemas(self, database: str) -> list[str]: ...
    async def list_models(self, database: str, schema: str) -> list[str]: ...
    async def get_model_schema(self, path: str) -> dict: ...
```

**SPEC-DAO-003**: All backend adapters shall implement the full `BaseDAO[T]` interface. Methods that are not meaningful for a given backend (e.g., `list_schemas` on Redis) shall raise `NotImplementedError` with a descriptive message.

### 5.3. Connection String Formats

| Backend | Format |
|---|---|
| PostgreSQL | `postgresql+asyncpg://user:pass@host:port/db` |
| Dgraph | `host:port` (gRPC) |
| Redis | `redis://host:port/db` |
| PGVector | `postgresql+asyncpg://user:pass@host:port/db` (same as PG) |
| OpenBao | `http://host:port` |
| REST | `http[s]://host:port/path` |
| Prometheus | `http://host:port` |

### 5.4. PostgreSQL Type Mapping

| Python Type | PostgreSQL Type |
|---|---|
| `str` | `TEXT` |
| `int` | `BIGINT` |
| `float` | `DOUBLE PRECISION` |
| `bool` | `BOOLEAN` |
| `dict` | `JSONB` |
| `list` | `JSONB` |
| `datetime` | `TIMESTAMPTZ` |
| `UUID` | `UUID` |

---

## 6. Data Model Layer

### 6.1. StorageModel Base Class

All models extend `StorageModel` (`models/base_model.py`, 269 lines):

```python
class StorageModel(SecuredModelMixin, StorageConfigMixin, BaseModel):
    uid: str | None = None
    updated_at: datetime | None = None

    class Meta:
        storage_configs: list[StorageConfig] = []
        path: str = ""         # Table/collection name
        indexes: list[dict] = []

    def to_storage_dict(self) -> dict: ...
    def from_storage_dict(cls, data: dict) -> Self: ...
    def get_all_daos(cls) -> list[BaseDAO]: ...
```

**SPEC-DAO-004**: `StorageModel` shall remain the base class for all domain models. The `Meta` inner class pattern shall be the sole mechanism for declaring storage backend configuration per model.

### 6.2. Model Destination Map

Models in `base/backend/dataops/models/` belong to different services:

| Model | File | Destination | Rationale |
|---|---|---|---|
| `StorageModel` | `base_model.py` | **AMI-DATAOPS** | Foundation class |
| `StorageConfig` | `storage_config.py` | **AMI-DATAOPS** | Infra config |
| `StorageConfigFactory` | `storage_config_factory.py` | **AMI-DATAOPS** | Config loader |
| `IPConfig` | `ip_config.py` | **AMI-DATAOPS** | Network config |
| `SSHConfig` | `ssh_config.py` | **AMI-DATAOPS** | SSH config |
| `SecurityContext` | `security.py` | **AMI-DATAOPS** | Access control context |
| `Permission`, `Role`, `ACLEntry` | `security.py` | **AMI-DATAOPS** | Security primitives |
| `SecuredModelMixin` | `secured_mixin.py` | **AMI-DATAOPS** | Audit fields mixin |
| `StorageConfigMixin` | `storage_mixin.py` | **AMI-DATAOPS** | Config mixin |
| `SecretPointer` | `secret_pointer.py` | **AMI-DATAOPS** | Vault field ref |
| `AuthProviderType` | `types.py` | **AMI-DATAOPS** | Shared enum |
| `User`, `AuthProvider` | `user.py` | **AMI-AUTH** | Auth domain |
| `PasswordRecord`, `PasswordPolicy` | `password.py` | **AMI-AUTH** | Auth domain |
| `MFADevice`, `MFAType` | `mfa.py` | **AMI-AUTH** | Auth domain |
| `BPMNProcess`, `BPMNTask`, etc. | `bpmn.py`, `bpmn_relational.py` | **DEFERRED** | No consumer |
| `ConsentRecord`, `LegalBasis` | `gdpr.py` | **DEFERRED** | No consumer |
| `RetentionPolicy` | `retention.py` | **DEFERRED** | No consumer |

---

## 7. Sync Strategy System

### 7.1. Strategies

Defined in `security/sync_strategy.py` (471 lines). The `DataSynchronizer` class orchestrates multi-storage writes:

| Strategy | Behavior | Use Case |
|---|---|---|
| `SEQUENTIAL` | Write to each backend one-by-one. Stop on first failure. | Maximum safety. Audit trails. |
| `PARALLEL` | Write to all backends simultaneously. Fail if any fails. | Performance-critical with strong consistency. |
| `PRIMARY_FIRST` | Write to primary first. Then secondaries in parallel. Secondary failures are logged, not fatal. | Default. Primary is source of truth. |
| `EVENTUAL` | Write to primary immediately. Queue secondaries for async background sync. | High throughput. Accept temporary inconsistency. |
| `QUORUM` | Wait for N-of-M backends to confirm. | Distributed consensus. |
| `MASTER_SLAVE` | Write to master. Replicate to slaves. | Read scaling. |

### 7.2. Conflict Resolution

| Strategy | Behavior |
|---|---|
| `LAST_WRITE_WINS` | Latest timestamp wins |
| `FIRST_WRITE_WINS` | Earliest timestamp wins |
| `HIGHEST_PRIORITY` | Storage type priority ordering decides |
| `MERGE` | Field-level merge of conflicting records |
| `MANUAL` | Flag conflict for human resolution |

### 7.3. Testing Status

**SPEC-DAO-005**: Only `PRIMARY_FIRST` and `SEQUENTIAL` have been exercised by existing tests. All 6 strategies shall have dedicated unit tests after migration.

---

## 8. Security Layer Triage

### 8.1. Keep

| Module | Lines | Reason |
|---|---|---|
| `security/encryption.py` | 391 | Field-level encryption. Useful for sensitive columns. |
| `security/sync_strategy.py` | 471 | Core multi-storage orchestration. Essential. |

### 8.2. Defer

| Module | Lines | Reason |
|---|---|---|
| `security/query_sanitizer.py` | 391 | Good concept but not wired into any DAO. Revisit when DAOs integrate it. |
| `security/resilience.py` | 394 | Circuit breaker + retry logic. Not connected. Revisit when needed. |

### 8.3. Delete

| Module | Lines | Reason |
|---|---|---|
| `security/compliance_reporting.py` | 1,006 | 99% stubs. SOC2/GDPR/HIPAA reporters with 9/11 methods returning `False`. Zero imports. |
| `security/audit_trail.py` | 377 | Blockchain-based audit with proof-of-work mining. Unused. Over-engineered. |
| `security/multi_tenancy.py` | 411 | Tenant isolation logic. Zero imports anywhere. |
| `security/rate_limiter.py` | 288 | Token bucket rate limiter. Zero imports. Each service has its own. |
| `security/cache_layer.py` | 522 | Caching with TTL. Zero imports. |
| **Total deleted** | **2,604** | |

---

## 9. Migration to projects/AMI-DATAOPS

### 9.1. Target Project Structure

```
projects/AMI-DATAOPS/
  pyproject.toml              # ami-dataops, Python 3.12
  config/
    storage-config.yaml       # Default storage configs (from base/config/)
  ami_dataops/
    __init__.py               # EMPTY (project convention)
    core/
      __init__.py
      dao.py                  # BaseDAO[T]
      unified_crud.py         # MERGED single UnifiedCRUD
      factory.py              # DAOFactory (FIXED)
      storage_types.py        # StorageType, OperationType, SyncStrategy enums
      exceptions.py
      execution_manager.py
      model_registry.py
      graph_relations.py
    models/
      __init__.py
      base_model.py           # StorageModel
      storage_config.py       # StorageConfig
      storage_config_factory.py
      security.py             # SecurityContext, Permission, ACL
      secured_mixin.py
      storage_mixin.py
      secret_pointer.py
      ip_config.py
      ssh_config.py
      types.py                # AuthProviderType
    implementations/
      __init__.py
      sql/                    # PostgreSQLDAO (6 files)
      graph/                  # DgraphDAO (8 files)
      mem/                    # RedisDAO (7 files)
      vec/                    # PGVectorDAO (7 files)
      vault/                  # OpenBaoDAO (1 file)
      rest/                   # RestDAO (2 files)
      timeseries/             # PrometheusDAO (5 files)
      embedding_service.py
    security/
      __init__.py
      sync_strategy.py        # DataSynchronizer + conflict resolution
      encryption.py           # Field-level encryption
    secrets/
      __init__.py
      client.py
      adapter.py
      repository.py
      config.py
      pointer.py
    storage/
      __init__.py
      registry.py             # StorageRegistry
      validator.py            # Config validation
    services/
      __init__.py
      decorators.py           # @sensitive_field, @record_event, @cached_result
    utils/
      __init__.py
      http_client.py
  tests/
    __init__.py
    conftest.py
    unit/
      __init__.py
      test_unified_crud.py
      test_dao_factory.py
      test_storage_config.py
      test_sync_strategy.py
      test_decorators.py
      test_encryption.py
      test_models.py
      adapters/
        __init__.py
        test_postgresql_dao.py
        test_dgraph_dao.py
        test_redis_dao.py
        test_pgvector_dao.py
        test_openbao_dao.py
        test_rest_dao.py
        test_prometheus_dao.py
    integration/
      __init__.py
      test_multi_storage.py
      test_sync_strategies.py
```

### 9.2. Package Name: `ami-dataops`

Python import: `ami_dataops` (underscore). This follows the agents monorepo convention.

### 9.3. pyproject.toml

```toml
[build-system]
requires = ["setuptools>=80.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ami-dataops"
version = "0.1.0"
description = "Polyglot persistence foundation for AMI services"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.12.0",
    "pydantic-settings>=2.12.0",
    "asyncpg>=0.30.0",
    "pydgraph>=24.3.0",
    "redis>=7.0.0",
    "aiohttp>=3.13.0",
    "httpx>=0.28.0",
    "loguru>=0.7.0",
    "pyyaml>=6.0.0",
    "cryptography>=44.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.4.0",
    "pytest-asyncio>=0.26.0",
    "pytest-cov>=6.1.0",
]

[tool.uv]
package = true

[tool.setuptools.packages.find]
where = ["."]
include = ["ami_dataops*"]
```

### 9.4. Workspace Integration

Add to root `pyproject.toml` at line 138:

```toml
[tool.uv.workspace]
members = ["projects/AMI-TRADING", "projects/AMI-AUTH", "projects/AMI-DATAOPS"]
```

### 9.5. Import Path Changes

All internal imports change from `base.backend.dataops.*` to `ami_dataops.*`:

| Old Import | New Import |
|---|---|
| `from base.backend.dataops.core.dao import BaseDAO` | `from ami_dataops.core.dao import BaseDAO` |
| `from base.backend.dataops.models.base_model import StorageModel` | `from ami_dataops.models.base_model import StorageModel` |
| `from base.backend.dataops.services.unified_crud import UnifiedCRUD` | `from ami_dataops.core.unified_crud import UnifiedCRUD` |
| `from base.backend.dataops.core.storage_types import StorageType` | `from ami_dataops.core.storage_types import StorageType` |

### 9.6. Handling base/ Consumers

Files in `base/` that import from dataops:

| Consumer | Files | Action |
|---|---|---|
| `base/backend/registry/` | DAO registry, discovery | Update imports to `ami_dataops` or keep in base/ as legacy |
| `base/backend/opsec/` | Auth, MFA, password, GDPR | Being migrated to AMI-AUTH (see SPEC-AUTH-BASE-MIGRATION) |
| `base/backend/mcp/` | MCP CRUD tools | Update imports or deprecate |
| `base/backend/llms/` | Google Code Assist | Update imports |
| `base/backend/services/secrets_broker/` | FastAPI secrets service | Update imports |

**SPEC-DAO-006**: After AMI-DATAOPS extraction, `base/backend/dataops/` shall remain in `base/` as a deprecated reference. No new code shall import from it.

---

## 10. Public API Design

### 10.1. Import Convention

All `__init__.py` files shall be **empty** (enforced by pre-push hook). There are no barrel re-exports. Consumers use fully qualified imports:

```python
from ami_dataops.core.dao import BaseDAO
from ami_dataops.core.unified_crud import UnifiedCRUD
from ami_dataops.core.factory import DAOFactory
from ami_dataops.core.storage_types import StorageType, OperationType, SyncStrategy
from ami_dataops.core.exceptions import StorageError, ValidationError
from ami_dataops.models.base_model import StorageModel
from ami_dataops.models.storage_config import StorageConfig
from ami_dataops.models.storage_config_factory import StorageConfigFactory
from ami_dataops.models.security import SecurityContext, Permission
```

**SPEC-DAO-011**: No `__init__.py` file shall contain any code. All imports shall be fully qualified. This is a hard project convention enforced by pre-push hooks.

### 10.2. Consumer Usage Pattern

```python
from ami_dataops.models.base_model import StorageModel
from ami_dataops.models.storage_config_factory import StorageConfigFactory
from ami_dataops.core.unified_crud import UnifiedCRUD

class MyModel(StorageModel):
    name: str
    value: float

    class Meta:
        storage_configs = [
            StorageConfigFactory.from_yaml("postgres"),
            StorageConfigFactory.from_yaml("dgraph"),
        ]
        path = "my_models"
        indexes = [{"fields": ["name"], "unique": True}]

# CRUD operations
crud = UnifiedCRUD(MyModel)
await crud.create({"name": "example", "value": 42.0})
results = await crud.find({"name": "example"})
```

---

## 11. Integration with AMI Services

### 11.1. AMI-AUTH

The OIDC provider spec (SPEC-AUTH-OIDC-PROVIDER) currently specifies plain SQLAlchemy for persistence. With AMI-DATAOPS available, there are two options:

| Approach | Pros | Cons |
|---|---|---|
| Plain SQLAlchemy (as specced) | Simple. No dependency on AMI-DATAOPS. | Doesn't benefit from multi-backend. |
| AMI-DATAOPS PostgreSQLDAO | Shared patterns. Could add vault for key storage. | Heavier dependency. |

**SPEC-DAO-007**: AMI-AUTH Phase 1-2 shall proceed with plain SQLAlchemy as specced. AMI-DATAOPS adoption is optional for Phase 3+ when vault integration for signing keys would benefit from OpenBaoDAO.

### 11.2. AMI-TRADING

AMI-TRADING currently uses raw SQLAlchemy + asyncpg. It could adopt AMI-DATAOPS for:
- Multi-storage for market data (Postgres + Redis cache + PGVector for embeddings)
- Prometheus integration for metrics
- Vault for API key storage

### 11.3. Future Services

Any new AMI service gets multi-backend persistence out of the box by declaring `StorageModel` subclasses with `Meta.storage_configs`.

---

## 12. Configuration System

### 12.1. storage-config.yaml

The master configuration lives at `config/storage-config.yaml` (migrated from `base/config/storage-config.yaml`):

```yaml
storages:
  postgres:
    type: relational
    host: "${POSTGRES_HOST:-localhost}"
    port: ${POSTGRES_PORT:-5432}
    database: "${POSTGRES_DB:-ami}"
    username: "${POSTGRES_USER:-ami}"
    password: "${POSTGRES_PASSWORD:-}"

  dgraph:
    type: graph
    host: "${DGRAPH_HOST:-localhost}"
    port: ${DGRAPH_PORT:-9080}

  redis:
    type: inmem
    host: "${REDIS_HOST:-localhost}"
    port: ${REDIS_PORT:-6379}
    database: "${REDIS_DB:-0}"

  pgvector:
    type: vector
    host: "${PGVECTOR_HOST:-localhost}"
    port: ${PGVECTOR_PORT:-5432}
    database: "${PGVECTOR_DB:-ami_vectors}"
    username: "${PGVECTOR_USER:-ami}"
    password: "${PGVECTOR_PASSWORD:-}"

  openbao:
    type: vault
    host: "${VAULT_HOST:-localhost}"
    port: ${VAULT_PORT:-8200}
    options:
      token: "${VAULT_TOKEN:-}"
      namespace: "${VAULT_NAMESPACE:-}"

  prometheus:
    type: timeseries
    host: "${PROMETHEUS_HOST:-localhost}"
    port: ${PROMETHEUS_PORT:-9090}

  rest:
    type: rest
    host: "${REST_API_HOST:-localhost}"
    port: ${REST_API_PORT:-443}
    options:
      ssl: true

defaults:
  sync_strategy: primary_first
  security_enabled: true
  audit_logging: true
```

### 12.2. Loading Pipeline

```mermaid
flowchart LR
    YAML["storage-config.yaml"]
    ENV["Environment Variables"]
    Factory["StorageConfigFactory"]
    Registry["StorageRegistry"]
    DAOReg["DAORegistry"]

    YAML --> Factory
    ENV --> Factory
    Factory -->|"from_yaml('postgres')"| Registry
    Registry -->|"get_config('postgres')"| DAOReg
    DAOReg -->|"auto-discover DAOs"| DAO["PostgreSQLDAO"]
```

**SPEC-DAO-008**: Environment variables shall always override YAML defaults. The `${VAR:-default}` substitution pattern shall be preserved.

---

## 13. Testing Strategy

### 13.1. Existing Tests

| File | Lines | Covers |
|---|---|---|
| `base/tests/test_dataops_decorators.py` | 300 | `@sensitive_field`, `@record_event`, `@cached_result` |
| `base/tests/test_dataops_security.py` | 319 | SecurityContext + UnifiedCRUD (services version) |
| `base/tests/test_bpmn_model.py` | 358 | BPMN model creation (not execution) |
| `base/tests/integration/test_dataops_simple.py` | ~100 | Basic CRUD |
| `base/tests/integration/test_dataops_multi_storage.py` | ~100 | Multi-storage sync |

### 13.2. Required Tests (Post-Migration)

| Test File | Target | Coverage |
|---|---|---|
| `test_unified_crud.py` | Merged UnifiedCRUD: single + multi-storage paths | 90%+ |
| `test_dao_factory.py` | DAOFactory creation, registry lookup, collection_name derivation | 90%+ |
| `test_storage_config.py` | Config loading, env var substitution, connection strings | 90%+ |
| `test_sync_strategy.py` | All 6 strategies + conflict resolution | 90%+ |
| `test_decorators.py` | Migrate from base/tests/ | 90%+ |
| `test_encryption.py` | Field-level encrypt/decrypt | 90%+ |
| `test_models.py` | StorageModel, to_storage_dict, from_storage_dict | 90%+ |
| `test_postgresql_dao.py` | PG adapter with mock asyncpg | 90%+ |
| `test_dgraph_dao.py` | Dgraph adapter with mock pydgraph | 90%+ |
| `test_redis_dao.py` | Redis adapter with mock redis | 90%+ |
| `test_pgvector_dao.py` | PGVector adapter with mock | 90%+ |
| `test_openbao_dao.py` | Vault adapter with mock HTTP | 90%+ |
| `test_rest_dao.py` | REST adapter with mock HTTP | 90%+ |
| `test_prometheus_dao.py` | Prometheus adapter with mock HTTP | 90%+ |
| `test_multi_storage.py` | Integration: write Postgres + Dgraph simultaneously | 50%+ |
| `test_sync_strategies.py` | Integration: all sync strategies with real (or testcontainer) backends | 50%+ |

**SPEC-DAO-009**: All test files shall be < 512 lines per agents repo pre-push hook. Use `postgres:16.6` (not `:latest`). No `/home/` paths. Empty `__init__.py` everywhere.

---

## 14. Multi-Backend ORM Landscape

### 14.1. Research Conclusion

Exhaustive search of the Python ecosystem (February 2026) confirms no library provides polyglot persistence across relational + graph + secrets backends:

| Library | Scope | Why Insufficient |
|---|---|---|
| SQLAlchemy 2.0 | Relational (multi-DB via binds) | No graph, no vault, no time-series |
| Tortoise ORM | Async relational | Same limitations as SQLAlchemy |
| Prisma Python | Multi-relational (PG, MySQL, MongoDB, SQLite) | No graph, no vault |
| Piccolo ORM | PostgreSQL only | Single backend |
| SQErzo | Multi-graph (Neo4j, RedisGraph, Neptune) | No relational, no vault |
| neomodel | Neo4j OGM | Single graph backend |
| Beanie | MongoDB ODM | Single document backend |

### 14.2. Architectural Validation

The dataops architecture follows established patterns:

| Pattern | Implementation |
|---|---|
| Repository/DAO | `BaseDAO[T]`: one adapter per backend |
| Abstract Factory | `DAOFactory`: runtime adapter selection via registry |
| Strategy | `SyncStrategy`: pluggable consistency models |
| Registry | `DAORegistry`: auto-discovery of adapter classes |
| Unit of Work | `ExecutionManager`: transaction context |

These are the correct patterns for polyglot persistence. The code needs cleanup, not redesign.

**SPEC-DAO-010**: AMI-DATAOPS shall remain a custom framework. Off-the-shelf ORMs may be used by individual services for backend-specific operations (e.g., SQLAlchemy for complex relational queries), but the unified multi-backend CRUD layer shall be AMI-DATAOPS.
