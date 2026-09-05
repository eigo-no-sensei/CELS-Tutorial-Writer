# ADR-0001 — Keep the Python archiver as the transitional canonical archive writer

**Status:** accepted_historical

**Date:** 2026-08-23

## Context

The Rust archive schema/repository work was introduced before full acquisition/normalization parity with the established Python v4.9 archiver existed.

## Decision

Keep the Python v4.9 archiver as the sole canonical local archive writer until an explicit A2 cutover changes executable ownership. Rust D1/D2 may build/migrate candidate state but may not silently become the production writer.

## Consequences

Rust replacement can be validated against the existing behavior without risking an implicit production cutover. The Python implementation remains transitional debt until A1/A2 are completed.

## Current-authority note

This ADR records rationale only. `contracts/state_ownership.json`, active component specs, schema and tests define current writer authority.
