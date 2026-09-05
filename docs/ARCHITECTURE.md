# Architecture and component boundaries

> Generated from `contracts/component_boundaries.json` and `contracts/state_ownership.json`.

## Current architecture

```text
GEL server (authoritative live source)
  ├─ tutorial-list / summary / edit / print source representations
  │
  ├─> Rust GEL session (N1/N2b; login POST only) ──> ephemeral JSON/HTML snapshots
  │
  ├─> N2-PW1 Playwright evidence harness ──> gitignored privacy-safe evidence
  │      └─ manual login only; tutorial POST serialization observed then ABORTED
  │      ├─ New-form GET /add/{uid}/0/{type} ──> N2b NewTutorialForm parser
  │      │                                      └─> validated New source authority
  │                                             └─> Rust pure parsers
  │                                                  └─> reconciliation / semantic revision state
  │                                                       └─> offline POST mapper (NO NETWORK WRITE)
  │
  ├─> RustArchiver A2 ──> canonical schema-v2 SQLite archive
  │      └─> crate-private ArchiveSyncRepository ──> transactional materialization/reconciliation
  │
  ├─> Python v4.9 archiver oracle ──> historical/reference parity evidence only
  │
  └─> D1 archive-schema migrator ──> separate noncanonical v2 candidate DB

Canonical JSON contracts ──> generated Rust GEL compatibility projection
                         └─> generated governance/specification documentation
Private fixture capture ──> Git-ignored evidence ──> Rust comparator/release evidence

Dependency manifests ──> governed lock tooling ──> Cargo.lock + package-lock.json
                                             └─> dependency-lock manifest
Contracts/plan/locks ──> current-state projection (NON-AUTHORITATIVE)
Exact source+locks+toolchain ──> strict GRI evidence ──> no-rebuild package ──> verified archive receipt
Portable CI ──> evidence only; never strict acceptance
AI Governance Protocol v1.1 + GEL profile ──> agent workflow/evidence/promotion only (NON-RUNTIME AUTHORITY)
```

## Active components

| Component | Status | Role |
| --- | --- | --- |
| `gel_server` | `active_external` | Authoritative live tutorial service and source of canonical tutorial identities and source pages. |
| `canonical_contracts` | `active` | Highest-authority repository representation of known GEL field, applicability, anomaly, governance, ownership and release invariants. |
| `contract_tooling` | `active` | Generate and validate projections of canonical GEL contracts. |
| `governance_tooling` | `active` | Generate and validate component specs, architecture/ownership documents, documentation index, release-gate projections, and meta-governance protocol/profile conformance. |
| `python_archiver_oracle` | `historical_reference` | Historical Python v4.9 behavioural/parity oracle retained for A1/A2 regression evidence; no runtime canonical archive write ownership after A2. |
| `fixture_capture` | `active_development` | Capture private source evidence and normalized expectations for regression testing without becoming runtime authority. |
| `rust_summary_parser` | `active` | Pure parser from GEL summary HTML to derived summary entries. |
| `rust_edit_form_parser` | `active` | Pure parser from historical GEL edit HTML to raw/effective edit-form state. |
| `rust_edit_form_validator` | `active` | Contract-driven fail-closed boundary between raw parsed GEL edit forms and semantic tutorial state. |
| `rust_new_tutorial_form_parser` | `active_n2b` | Validate one acquired GEL New-tutorial form into immutable source authority without weakening the historical Revision edit-form validator. |
| `rust_print_parser` | `active_a1_pending_strict_acceptance` | Pure safe parser for GEL print HTML implementing the A1 Python-v4.9 print-fallback semantic shape for Rust archiver acquisition and parity evidence. |
| `rust_reconciliation` | `active_c3` | Pure association logic between canonical API identities and summary states, preserving collision evidence. |
| `rust_semantic_form` | `active_ui1c5` | Construct and validate editable semantic tutorial state from governed source authority, including UI1c5-integrated field applicability, structured edit validation, Initial course-type storage adaptation, and New-only same-role CEFR regression protection. |
| `rust_post_mapper` | `active_c2_c4_n2a` | Purely serialize governed semantic tutorial state through origin-specific New/Revision submission types to GEL form field/value pairs without network access. |
| `rust_fixture_tooling` | `active_c4` | Compare private source/archive evidence with derived parser, semantic, reconciliation and offline POST states through C4. |
| `archive_schema_migrator` | `active_d1` | Create fresh archive-schema-v2 databases and migrate an explicitly supplied legacy archive into a separate candidate destination without changing canonical writer ownership. |
| `rust_archive_repository` | `active_d2` | Public read-only typed repository over an existing archive-schema-v2 database for Writer/Viewer navigation and fail-closed historical revision loading. |
| `rust_archive_sync_repository` | `active_a2_canonical` | A2 production canonical local-archive implementation: RustArchiver acquires source data and delegates all SQLite mutation to the crate-private transactional ArchiveSyncRepository. |
| `rust_gel_session` | `active_n1_n2b_read_only` | Own authenticated GEL HTTP session state and expose a fixed read-only acquisition surface without leaking credentials/cookies or granting tutorial mutation authority. |
| `n2_playwright_evidence_harness` | `active_n2_pw1_core_complete_residual_deferred` | Zero-write evidence harness for current GEL New/Edit browser behaviour; core N2 evidence is complete and changed-teacher submit serialization remains a deferred non-blocking diagnostic capability. |
| `writer_tauri_app_service` | `active_w2_a2` | Own the Tutorial Writer runtime orchestration boundary: transient GEL read session use, read-only archive navigation, one explicit governed A2 archive-sync trigger, one ephemeral Rust-owned tutorial draft, typed semantic edits and safe frontend view models. |
| `writer_react_ui` | `active_ui1e` | Render the selected A+D hybrid browse/write layout from safe Rust view models, collect transient credentials/input and invoke only typed UI1 Tauri commands. |
| `dependency_lock_tooling` | `active_gri` | Own reproducible dependency-resolution decision state and its derived lock-identity projection. |
| `current_state_tooling` | `active_gri` | Generate one machine-readable current project status projection from higher-authority contracts, plan, lock identity and accepted evidence references. |
| `release_artifact_tooling` | `active_gri` | Run governed release checks, bind strict evidence to exact source/dependency/toolchain identity, package accepted source without rebuilding, and verify final archive bytes. |
| `continuous_enforcement` | `active_gri` | Continuously execute reproducible portable structural/build/behavioral checks without claiming target-host strict acceptance. |
| `writer_harper_service` | `active_ui1d` | Rust-owned British-English Harper checking service for bounded Writer text fields. |
| `harper_dictionary_repository` | `active_ui1d` | Sole writer of the local versioned Harper user dictionary. |
| `live_submission_transport` | `active_w2` | Submit governed tutorial POST payloads to the authoritative GEL server and discover canonical tutorial identity via post-submit readback. |

## Planned but not active


Planned components have no current write authority. Their ownership must be added to the canonical contracts in the same change that activates them.

## Boundary rules

- Opaque GEL form IDs belong to the canonical field contract/generated compatibility layer, not SQL/domain/UI code.
- Parsers and reconciliation are pure derived-state components; they do not write GEL or canonical SQLite.
- The semantic model produces editable derived state; it does not mutate archive history.
- The POST mapper produces an ephemeral payload only and has no transport/network authority.
- The Rust GEL session owns cookies and authenticated read transport only: exactly two login-handshake POSTs are allowed, while all exposed acquisition operations are fixed GETs; it exposes no generic request or tutorial mutation API.
- N2b extends that fixed GET surface only with `/study/tutorials/add/{student_uid}/0/{ttype_raw}` and validates the returned New form separately from historical Revision edit forms.
- The N2b New-form parser is the sole production writer of validated New-form source state and opaque hidden-teacher authority; it forbids `datetime`, retains no raw HTML, and owns no POST/network capability.
- Credentials are transient inputs to the Rust GEL session and are not retained as project state; student email-like API fields are stripped before roster/profile JSON leaves the session boundary.
- N2-PW1 is evidence-only tooling: its browser firewall is installed before login, it never reads login bodies/password values, and every tutorial mutation attempt is aborted. It may record client-side changed-teacher serialization but cannot establish server reassignment authority.
- N2-PW1 treats latest tutorial as the established New prepopulation source and persists only field relationships/classifications, never raw tutorial values.
- A2 makes RustArchiver the production canonical local archive orchestrator and the crate-private ArchiveSyncRepository the sole SQLite write capability; Python v4.9 remains historical/reference parity authority only.
- D1 schema v2 is executable repository authority for the target archive shape, but its migration tool writes only separate noncanonical candidate databases; it does not cut over runtime ownership.
- Schema v2 separates API identities, candidate source states and governed associations; blocked authority statuses carry no source-state reference.
- The Viewer and future UI are not permitted to bypass the repository/source ownership contracts.
- Dependency lock state is a reviewed decision with one writer; release/build commands use the root Cargo workspace lock and `npm ci`.
- `governance/current-state.json` is generated projection state only. It summarizes higher-authority inputs and cannot override them.
- Strict release acceptance is immutable external evidence bound to the exact source fingerprint, dependency locks and toolchain identity; CI cannot self-promote it.
- Packaging occurs only after strict acceptance, revalidates the source fingerprint, performs no rebuild, and verifies the exact final archive bytes.
- The generic AI Governance Protocol and GEL project profile are reviewed meta-governance decisions. They bind agent workflow/claims to existing contracts and may not override GEL runtime/domain semantics.

## Source/decision/derived/projection/evidence rule

A parser/model output, projection or evidence artifact is never promoted to source/decision authority merely because it is convenient to consume. Five-way state kind, writers, retention and invalidation are enumerated in `contracts/state_ownership.json`.
