# ADR-0003 — Use validated New form plus latest tutorial for New-draft authority

**Status:** accepted_historical

**Date:** 2026-08-28

## Context

Live evidence established that New tutorials do not carry authoritative `datetime`, use the authenticated New-form teacher, and prepopulate from the latest tutorial subject to canonical same-role field rules.

## Decision

Construct New drafts from the validated New form plus the latest authoritative tutorial when present. Copy only the same canonical semantic role; never infer provenance from equal values or promote Initial/current roles across one another.

## Consequences

New identity remains absent until successful server creation/readback; teacher authority is immutable; source changes make the draft stale rather than silently rebinding it.

## Current-authority note

This ADR does not override N2b/N2c executable contracts or tests.
