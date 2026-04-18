# Proposal: Consolidate Merkle-tree implementations

**Date:** 2026-04-17
**Status:** DRAFT for approval (SIN #10 of the 2026-04-17 audit)

## Problem

Two runtime Merkle-tree implementations currently exist in the RUST-TRADING workspaces:

- `projects/RUST-TRADING/rust-zk-compliance-api/crates/sanctions-oracle/src/merkle_set.rs`
  (`SanctionsMerkleTree`) — sorted Poseidon tree over
  `UniversalAddress`, supports non-membership proofs.
- `projects/RUST-TRADING/rust-zk-compliance-api/crates/energy-oracle/src/merkle.rs`
  (`EnergyMerkleTree`) — wraps the same storage idea (`Vec<Fr>`, root,
  depth, label) over energy commitments.

`EnergyMerkleTree`'s module docstring claims to "wrap" the sanctions
tree, but in practice it re-declares the state fields rather than
delegating. The circuit gadget
(`rust-zk-protocol/crates/zk-circuits/src/gadgets/merkle.rs`,
`MerklePathVar`) is intentionally separate — it produces constraints,
not runtime data — and is out of scope.

## Options

### Option A — Energy delegates to Sanctions (minimum change)

Make `EnergyMerkleTree` own only energy-specific logic (commitment
schema, domain separation, leaf encoding) and hold a
`SanctionsMerkleTree` internally for tree storage + proof generation.
`EnergyMerkleTree` becomes a thin adapter (~50 LOC).

- **Pro:** smallest diff, no new crate, no cross-workspace changes.
- **Con:** `SanctionsMerkleTree` keeps its `sanctions-oracle` home,
  which is semantically wrong once another oracle depends on it.

### Option B — Extract `merkle-core` crate (clean)

Create `crates/merkle-core/` in `rust-zk-compliance-api`. Move the
sorted-Poseidon tree, proof generation, and verification there.
`sanctions-oracle` and `energy-oracle` both depend on it. Each oracle
keeps only its leaf-encoding / domain-tag logic.

- **Pro:** correct ownership; natural home for future oracles.
- **Con:** cross-crate refactor; API-break for in-workspace callers
  (mostly absorbed by the wrapping oracles); needs a migration sweep.

### Option C — Leave as is, accept the duplication

Document the overlap, commit to keeping both implementations in sync
by hand.

- **Pro:** zero change tonight.
- **Con:** drift risk compounds over time; every Merkle bugfix needs
  two patches. Worst option for long-term maintenance.

## Recommendation

**Option B.** It's the only choice that scales as more oracles land.
The work is a single-crate refactor inside one workspace, not a cross-
project change. Estimated scope: new crate + `Cargo.toml` wires in two
crates + ~3 files moved + 2 oracles now call the new crate + workspace
unit tests updated.

## Out of scope

- The circuit-side `MerklePathVar` gadget. Its split is correct (it
  emits constraints, not runtime state).
- Cross-workspace re-use. `rust-zk-protocol` and `rust-ta` do not
  currently need Merkle, and this proposal does not put the new crate
  in a location that forces dependency on them.

## Decision

Pending user approval. No code change until one of the three options
is selected.
