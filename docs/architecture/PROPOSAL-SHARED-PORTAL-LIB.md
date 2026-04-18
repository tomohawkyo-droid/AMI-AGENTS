# Proposal: Shared library for AMI-PORTAL and ZK-PORTAL

**Date:** 2026-04-17
**Status:** DRAFT for approval (SIN #12 of the 2026-04-17 audit)

## Problem

AMI-PORTAL and ZK-PORTAL are two independent Next.js 16 applications
with diverging toolchains (prettier, eslint, Next.js minor), disjoint
auth stacks (next-auth vs `jose`), disjoint security-header policies,
and no code-sharing mechanism. AMI-PORTAL has started a `packages/*`
npm-workspace layout (`packages/highlight-core`, `packages/highlight-engine`)
that ZK-PORTAL cannot consume because the two repos are independent
git remotes.

Concretely, every shared concern (auth, header policy, code-editor UI,
document viewer primitives) has to be implemented twice and kept in
sync manually.

## Scope of the decision

This proposal is a **design sketch**. No code change happens under it.
Actually building the shared lib is multi-week work and out of scope
for tonight.

## Options

### Option A — Extract a dedicated `@ami/portal-lib` repo

Create a new repository `Independent-AI-Labs/AMI-PORTAL-LIB`
containing shared primitives (auth helpers, session types, security
headers config, common UI components). Both portals depend on it via
an npm-published package.

- **Pro:** clean separation; each portal imports by version; other
  future portals (admin console, docs site) can reuse.
- **Con:** npm publish pipeline required; version-bump ceremony for
  every change; cross-repo PR coordination.

### Option B — Add a git-submodule `shared/` inside each portal

Both portals include the same submodule pointing at
`AMI-PORTAL-LIB`. Simpler than npm publish but brings submodule
coordination costs.

- **Pro:** no publish; every portal sees the same HEAD.
- **Con:** submodule updates need discipline; Next.js build tooling
  sometimes has edge cases with submodule source-maps.

### Option C — Hoist to an AMI-AGENTS monorepo workspace

Move both portals into AMI-AGENTS as workspace members, share a single
`package.json` workspaces root. `packages/portal-core` lives at the
top level.

- **Pro:** one repo, single source of truth, no publishing.
- **Con:** AMI-AGENTS' gitignore currently excludes all of `projects/`;
  the portals are their own upstream repos with independent CI. Moving
  them would collapse two decoupled deploy pipelines into one.

### Option D — Do nothing (status quo)

Accept the duplication; keep the portals independent; migrate later
if the cost compounds.

## Recommendation

**Option A** (`@ami/portal-lib` as its own repo). The current pain
level (two maintainers of the same auth code, two security-header
policies) justifies a shared package. Option C is tempting but fights
the existing "projects/ is gitignored in AMI-AGENTS" arrangement,
which was chosen deliberately. Option B adds submodule overhead with
fewer of A's benefits.

## First-draft scope for A

- Create `Independent-AI-Labs/AMI-PORTAL-LIB` (empty Next.js-library
  scaffold, TypeScript, prettier config matches ZK-PORTAL's style).
- Move `lib/auth/*`, `lib/security/*`, shared session types from
  AMI-PORTAL into it.
- Publish as `@ami/portal-lib` (private npm registry or GitHub
  Packages).
- Add as dependency in both portals; remove the duplicated files.
- First migration wave: auth utilities + security headers only.
  Document remaining duplication as follow-up.

## Decision

Pending user approval. If approved, the actual implementation is a
separate follow-up task (weeks of work, not session-sized).
