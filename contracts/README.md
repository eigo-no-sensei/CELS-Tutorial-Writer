# Canonical executable contracts

These JSON contracts plus the executable schema files they govern are the highest current repository authority for GEL tutorial fields/evidence, semantic draft behaviour, archive storage and project governance.

## GEL/evidence/semantic contracts

- `gel_tutorial_fields.json`
- `tutorial_types.json`
- `tutorial_form_applicability.json`
- `tutorial_form_semantics.json`
- `reconciliation_authority.json`
- `offline_post_round_trip.json`
- `known_source_anomalies.json`
- `evidence_baseline.json`
- `archive_schema_v2.json` (governs executable `schema/archive_v2.sql`)
- `archive_repository.json`
- `gel_read_only_session.json`
- `n2_playwright_zero_write_evidence.json`
- `n2a_semantic_post_authority.json`

They generate the Rust GEL compatibility projection and contract documentation. After changing one, run:

```fish
python tools/generate_contract_artifacts.py
./check-contracts
```

The semantic contract defines explicit New-versus-Revision draft origin, the single writable representation of editable fields, provenance-only source fidelity, type invariants, and Aims POST escaping. The reconciliation-authority contract governs identity/state separation, collision classes, revision eligibility, and timestamp-route non-authority. The offline POST round-trip contract governs exact source-derived payload reconstruction, historical absent authority, Final Reading, mutation isolation, and the no-network C4 boundary. The archive-schema-v2 and archive-repository contracts govern executable SQLite storage plus the D2 split read-only/candidate-sync repository boundary. The N1 `gel_read_only_session.json` contract governs the two-login-POST authentication handshake, fixed GET acquisition surface, session-private credentials/cookies, privacy filtering, offline release checks and separate manual live parity. The N2-PW1 `n2_playwright_zero_write_evidence.json` contract governs the zero-write browser evidence boundary; changed-teacher submit/server semantics are explicitly deferred and non-blocking. The N2a `n2a_semantic_post_authority.json` contract governs canonical field identity, distinct New/Revision identity and teacher authority, New datetime omission, exact Revision timestamp, source-vs-derived ownership/invalidation and the offline-only submission mapper.

## Governance contracts

- `documentation_governance.json`
- `component_boundaries.json`
- `state_ownership.json`
- `release_gate.json`

They generate the active component specifications, architecture/ownership/release documentation, and documentation index. After changing one, run:

```fish
python tools/generate_governance_artifacts.py
./check-governance
```

The authority order is executable contracts/tests → active component specs → master/cross-component specs → operational docs → ADRs/history. ADRs are historical rationale only and must have explicit status.

The generic AI Governance Protocol is intentionally **not** another GEL runtime contract. `governance/agent-protocol/ai-governance-protocol.v1.1.json` and `governance/agent-protocol/profiles/gel-tutorial-writer.profile.json` are reviewed meta-governance decision state. The GEL profile binds agent workflow/evidence/promotion to these existing contracts and declares `runtimeAuthority=false`. `check:governance` validates that boundary.

The strict private-fixture baseline is now observed and confirmed: **14 fixtures / 275 fields / 269 OK / exactly 6 allowlisted historical `absent` mismatches / 0 unavailable**.

C3 private evidence is separately gated through the two reconciliation fixtures: identical-state collisions must preserve every API ID without positional state assignment, while divergent-state collisions must block revision-by-ID. C4 adds a third private gate over the same 14 edit/archive fixture pairs: every semantic Revision must serialize to an exact independently reconstructed POST map, all five Final payloads must carry Reading, and the six historical absent discrepancies must serialize from archive authority rather than the edit checkbox.

## D1 archive schema check

The executable D1 storage check is:

```fish
python tools/check_archive_schema.py
```

It is also a required portable/strict release-gate check. The v2 migration writes a separate candidate destination only; it does not change current canonical archive ownership.

