# RUST-TRADING

Umbrella directory containing **four independent Rust Cargo workspaces**. They
are deliberately kept as separate workspaces rather than a single monorepo
workspace; the split is load-bearing, not an accident.

## Workspaces

| Workspace | Purpose | Notes |
|---|---|---|
| `rust-ta/` | Technical-analysis indicator crates (`ta-core`, `ta-indicators`, benchmarks). | Edition 2024, rust 1.85+. Consumed as published crates by downstream trading code. |
| `rust-zk-compliance-api/` | ZK energy-compliance API (sanctions oracle, energy oracle, circuits, REST API). | Edition 2021, rust 1.84 (Solana platform-tools constraint). |
| `rust-zk-protocol/` | Protocol primitives (`zk-core`, `zk-circuits`, `zk-sdk`, `zk-compliance`). | Edition 2021, rust 1.84 (Solana). |
| `rust-zk-provider/` | ZK proving-service runtime (GPU-accelerated prover, cluster orchestration). | Edition 2021, rust 1.84 (Solana). |

## Why four workspaces, not one

- **Toolchain divergence.** `rust-ta` uses Edition 2024 / rust 1.85+ to get the
  latest language features. The three ZK workspaces must stay on Edition 2021 /
  rust 1.84 because Solana's `cargo build-sbf` platform tooling only supports
  that rustc line. A single workspace would force the lowest common denominator
  on everyone.
- **Dependency cones don't overlap.** `rust-ta` pulls heavy numeric / TA crates;
  the ZK workspaces pull arkworks / poseidon / solana-sdk. Merging would produce
  a much larger resolver graph with no reuse benefit.
- **Independent release cadence.** TA crates and ZK crates are published on
  different schedules to different audiences. Separate `Cargo.lock` files keep
  each workspace's upgrades isolated.

## When a shared workspace would make sense

Only if *all* of the following become true:

1. Solana platform-tools ships a rustc that matches (or surpasses) whatever
   `rust-ta` is on, removing the toolchain split.
2. Concrete cross-workspace code sharing shows up (not just "we both use
   `thiserror`"). Until then, crates.io is the right sharing mechanism.
3. `cargo build` at the umbrella level demonstrably beats four separate builds
   in CI — today they run independently and in parallel.

## Not in any workspace

- `config/`, `docs/`, `scripts/`, `SUCK/` — monorepo support directories; their
  remote points at AMI-AGENTS, so they are in AMI-AGENTS' tree, not any of the
  Rust workspaces. The update tooling excludes them explicitly.

## Common tasks

```sh
# Build everything
for w in rust-ta rust-zk-compliance-api rust-zk-protocol rust-zk-provider; do
  (cd "$w" && cargo build --release) || exit 1
done

# Test everything
for w in rust-ta rust-zk-compliance-api rust-zk-protocol rust-zk-provider; do
  (cd "$w" && cargo test) || exit 1
done
```

Each workspace has its own README / docs with workspace-specific details.
