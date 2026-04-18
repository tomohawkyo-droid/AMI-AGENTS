# Proposal: Unify ZK error types

**Date:** 2026-04-17
**Status:** DRAFT for approval (SIN #16 of the 2026-04-17 audit)

## Problem

`rust-zk-protocol/crates/zk-core/src/error.rs` is a stub whose comment
says "protocol-specific errors are defined in the crates that use
them". Downstream crates (`zk-compliance`, `energy-oracle`,
`sanctions-oracle`, ...) each define their own error enum. Callers
that cross crate boundaries end up stitching `Result<T, ComplianceError>`
vs `Result<T, EnergyOracleError>` vs `Result<T, SanctionsError>` by
hand, or bail on `anyhow::Error` at the boundary which erases structure.

## Options

### Option A — Top-level `ZkError` enum

Add `ZkError` in `zk-core` with variants that wrap each downstream
crate's error:

```rust
pub enum ZkError {
    Compliance(ComplianceError),
    Energy(EnergyOracleError),
    Sanctions(SanctionsError),
    Io(std::io::Error),
}
```

Downstream errors implement `From<ComplianceError> for ZkError` etc.
Callers at crate boundaries use `Result<T, ZkError>`.

- **Pro:** single error currency at the boundary; `?` works across
  crates; boundary code stays typed.
- **Con:** `zk-core` must depend on every crate whose errors it wraps;
  inverts the normal dependency direction.

### Option B — Shared `ZkError` trait in `zk-core`

`zk-core` declares a trait `trait ZkError: std::error::Error +
std::fmt::Debug + Send + Sync`. Each downstream error implements it.
Boundary code uses `Box<dyn ZkError>`.

- **Pro:** no reverse dependency; each crate keeps its own concrete
  error; boundary is still structured.
- **Con:** `Box<dyn>` forces allocation and erases downcasts in the
  common case; match-on-kind at boundary requires `downcast_ref`.

### Option C — Use `thiserror` conventions without a top-level type

Adopt the discipline: every crate's error enum follows the same
template (variants prefixed `Io`, `Protocol`, `Validation`, etc.),
every crate re-exports `type Result<T> = std::result::Result<T, Self::Error>`.
Boundary callers convert with `.map_err(Into::into)` into whichever
error type their caller expects.

- **Pro:** no new crate-level type; uses stdlib + thiserror idioms.
- **Con:** doesn't actually unify anything; boundaries still type-
  juggle; the "same template" rule is aspirational and not enforced.

### Option D — Leave as is

The decentralised errors work; crate boundaries that need unification
fall back to `anyhow` where they already are.

- **Pro:** no work.
- **Con:** structure at the boundary stays lost; this is exactly what
  the sin register flagged.

## Recommendation

**Option A** (top-level `ZkError` wrapping downstream errors).
Accepting the reverse-dependency is the standard workspace pattern
for Rust projects that want one unified error at the public API
surface. The alternative (Option B, `Box<dyn>`) loses match
ergonomics, which matters for code that actually branches on error
kind — and that's the code we care about.

## First-draft scope for A

- Add `ZkError` enum in `zk-core/src/error.rs` with one variant per
  downstream crate whose errors bubble up to the protocol API.
- Each downstream crate implements `impl From<CrateError> for ZkError`.
- Replace the "protocol-specific errors are defined in the crates
  that use them" stub comment with a pointer to `ZkError`.
- Update `zk-sdk` and `zk-compliance` boundary functions to return
  `Result<T, ZkError>` instead of concrete downstream errors.

## Decision

Pending user approval. Change is contained to `rust-zk-protocol` and
its callers inside `rust-zk-compliance-api`.
