# ADR-0004 — Bind release identity to locks, strict evidence, and final archive bytes

**Status:** accepted_historical

**Date:** 2026-08-30

## Context

Runtime/state authority was already strong, but dependency resolution, duplicated per-crate release commands, absent CI and weak artifact identity left release reproducibility outside the same governance model.

## Decision

Use one Rust workspace lock, an npm lock with `npm ci`, generated non-authoritative current-state/lock projections, evidence-classified checks, target-host strict evidence bound to exact source/toolchain identity, and package only after acceptance without rebuilding. Verify final archive bytes separately.

## Consequences

Missing locks or target evidence block release rather than becoming portable skips. CI remains portable evidence and cannot claim strict acceptance. Packaging fails if accepted source identity changes.

## Current-authority note

`contracts/release_identity.json`, `contracts/release_gate.json`, `contracts/verification_semantics.json` and their executable tools define current release behavior. This ADR is rationale only.
