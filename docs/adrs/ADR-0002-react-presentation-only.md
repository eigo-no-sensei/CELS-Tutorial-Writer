# ADR-0002 — Keep React presentation-only for tutorial semantic state

**Status:** accepted_historical

**Date:** 2026-08-28

## Context

Tutorial identity, teacher attribution, GEL field applicability and New/Revision semantics are safety-critical and already governed in Rust.

## Decision

React receives safe view models and submits typed semantic edit intents. Rust owns the active draft, canonical option domains, validation and candidate-before-commit mutation. React receives no raw GEL field-ID, generic HTTP, POST-payload or teacher-reassignment capability.

## Consequences

UI code remains replaceable presentation state and cannot become an accidental second semantic authority.

## Current-authority note

This ADR is historical rationale. `contracts/ui1_writer.json`, `contracts/ui1c_semantic_forms.json`, component/state ownership and behavioral tests define current behavior.
