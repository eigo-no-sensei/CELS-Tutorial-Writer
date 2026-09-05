# Project governance

> Generated from `contracts/documentation_governance.json`. The JSON contract is authoritative.

## Documentation authority order

1. **Executable schema/contracts/tests** — Current executable contracts and tests are runtime authority. Lower-ranked documentation must not contradict them.
2. **Active component specs** — Describe current component responsibilities and boundaries; generated from component boundary contracts where possible.
3. **Master/cross-component specs** — Describe architecture, ownership and lifecycle across components without overriding higher-ranked authority.
4. **Operational docs** — Explain how to operate and validate the project; must follow current contracts/specs.
5. **ADRs/history** — Historical rationale only. Every ADR has explicit status and cannot override current contracts/specs.

## Active component specification contract

Every active component spec must contain all of these sections:

- Role
- Scope
- Authority
- Reads
- Writes
- Must not write
- State transitions
- Failure semantics
- Dependencies
- Tests

## Same-change rule

Any change to ownership, schema, state transitions, canonical field contracts, or externally visible behaviour must update the governing executable contract/spec/documentation in the same change.

## ADR policy

ADRs record historical decisions and rationale with explicit status. They are never current runtime authority; current behaviour is defined by higher-ranked executable contracts/tests and active specs. Superseded phase plans and acceptance narratives belong under docs/history/ or an external evidence store.

Allowed ADR statuses: `proposed`, `accepted_historical`, `superseded`, `rejected`.

## Generated-index rule

Documentation indexes and current-state status pages are generated where possible and must be current under check:governance. governance/current-state.json is a projection only and cannot override contracts, active component specs, or tests.

## State classification

- **source** — External or user/repository-authored canonical input.
- **decision** — Durable reviewed compatibility/dependency decision constraining later rebuilds.
- **derived** — Reproducible materialization from higher-authority inputs.
- **projection** — Denormalized/read/UI/status representation that must never become edit-back authority.
- **evidence** — Diagnostic, experimental, CI or acceptance material that cannot self-promote.

## AI-agent meta-governance

governance/agent-protocol defines AI-agent workflow, evidence and promotion semantics only. It is a reviewed meta-governance decision and is not GEL runtime/domain authority; the GEL project profile must bind to existing canonical contracts and may not override executable contracts/tests, active component specs, or state ownership.
