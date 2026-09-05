# Release gate

> Generated from `contracts/release_gate.json`. The JSON contract and executable gate are authoritative over this prose.

## Profiles

### `portable`

Reproducible repository validation. Private GEL evidence may be explicit SKIP where declared. A missing dependency lock may also be explicit SKIP only when its corresponding generator executable is objectively unavailable under contracts/dependency_lock_policy.json. Passing with skips is STRUCTURAL_PASS_WITH_SKIPS, not strict acceptance.

Missing private fixture policy: **SKIP**.
Missing dependency lock when corresponding generator is unavailable: **SKIP_WHEN_CORRESPONDING_GENERATOR_UNAVAILABLE**.

### `strict`

Target-host release acceptance requiring complete dependency locks, toolchains, private fixture evidence and all governed checks. Tool-unavailable lock exceptions never satisfy strict acceptance. Strict acceptance requires PASS for every check and binds evidence to the exact source fingerprint.

Missing private fixture policy: **FAIL**.
Missing dependency lock when corresponding generator is unavailable: **FAIL**.

Current release scope: **`w2`**.

## Check result taxonomy

| Result | Meaning |
| --- | --- |
| **PASS** | Check executed and satisfied its canonical invariant. |
| **FAIL** | Check executed and failed, or a required dependency/evidence source is missing. |
| **SKIP** | Permitted only by a profile/condition explicitly declared in this contract, including the portable lock-generator-unavailable exception; a skip is never reported as a pass. |

## Acceptance status taxonomy

| Status | Meaning |
| --- | --- |
| **STRUCTURAL_PASS** | Portable checks executed with no FAIL/SKIP; does not imply target acceptance. |
| **STRUCTURAL_PASS_WITH_SKIPS** | Portable checks have no FAIL but one or more explicitly permitted SKIPs; target acceptance remains required. |
| **TARGET_ACCEPTANCE_REQUIRED** | Candidate has not satisfied the current strict target-host gate for its exact source identity. |
| **STRICT_ACCEPTED** | Exact source/lock/toolchain identity passed the required strict scope with zero SKIP/FAIL; still not a verified release archive. |
| **RELEASE_ARTIFACT_VERIFIED** | Final archive bytes and embedded manifests were verified after strict acceptance without rebuilding. |

## Current checks

| Check | Evidence class | Portable | Strict | Purpose |
| --- | --- | ---: | ---: | --- |
| `contracts` | `structural` | required | required | Canonical GEL contracts and projections are valid/current. |
| `governance` | `structural` | required | required | Validate ownership/component/documentation authority plus AI Governance Protocol v1.1 and the GEL meta-governance profile; fail any attempt to make the generic protocol runtime authority. |
| `python_compile` | `structural` | required | required | Active Python tooling/oracle parses successfully. |
| `archive_schema_v2` | `structural` | required | required | D1 executable archive schema v2: fresh schema, legacy migration, FK enforcement, relational membership, collision-safe associations, source-presence lifecycle, privacy minimization and safe UPSERTs. This offline check uses Python stdlib/SQLite and must not import the live-network archiver runtime. |
| `archive_repository` | `structural` | required | required | D2/A2 Rust repository boundary and D1 parity: public read-only API, public RustArchiver production orchestration, crate-private transactional writer, schema-v2/open-mode rules, rollback/invalidation semantics and Rust canonical-writer ownership. |
| `a1_print_parity` | `structural` | required | required | A1 public Python-v4.9 print fallback parity contract: exact result shape, 14 oracle-backed fixtures and structured-DOM prose-boundary protection. |
| `a1_print_behavior` | `behavioral` | required | required | A1 executable Rust exact print-parity fixture comparison and prose false-positive regression. |
| `private_print_parity` | `acceptance` | required | required | A1 strict exact comparison against the private historical print fixture set. |
| `a2_archiver` | `structural` | required | required | A2 canonical-writer cutover boundary: RustArchiver orchestration, atomic schema-v2 creation, acquire-before-transaction, collision-safe materialization and explicit Writer sync. |
| `a2_archiver_behavior` | `behavioral` | required | required | A2 Rust archiver fresh-DB, semantic precedence and transactional materialization regression tests. |
| `gel_session` | `structural` | required | required | N1 offline transport boundary: fixed read-only GEL acquisition surface, two login-only POSTs, private credentials/cookies, student-email stripping, no generic request or tutorial mutation API. Live parity is separate manual evidence. |
| `n2_playwright_zero_write` | `structural` | required | required | N2-PW1 offline safety/behaviour contract: firewall before login, no credential/session capture, expected tutorial probes always abort, private evidence is redacted, latest-tutorial prepopulation source is fixed, and changed-teacher submit/server semantics remain deferred non-blocking. |
| `n2a_semantic_post` | `structural` | required | required | N2a canonical field identity, New/Revision authority, datetime omission/preservation, immutable teacher ownership, first-ever New support and offline-only POST mapping. |
| `n2b_new_form` | `structural` | required | required | N2b fixed New-form GET and distinct fail-closed ValidatedNewTutorialForm parser: no datetime, hidden immutable teacher authority, canonical field applicability/fingerprint, no network write. |
| `n2c_prepopulation` | `structural` | required | required | N2c canonical field-by-field New prepopulation/default/reset projection from the latest tutorial plus validated New-form defaults; no cross-dimension inference or network write. |
| `dependency_locks` | `structural` | required | required | Require synchronized Rust/npm dependency identity; portable may explicitly SKIP a missing lock only when its corresponding generator executable is unavailable. Strict always requires complete locks. |
| `dependency_lock_exception_behavior` | `behavioral` | required | required | Prove LOCK_GENERATOR_UNAVAILABLE is automatic, per-lock, invalidated when the corresponding generator is available, and never substitutes for complete locks. |
| `rust_workspace_fmt` | `structural` | required | required | Format the complete Rust workspace under one release identity. |
| `rust_workspace_clippy` | `structural` | required | required | Static analysis for every Rust workspace target using the accepted Cargo.lock. |
| `rust_workspace_tests` | `behavioral` | required | required | Behavioral tests for the complete Rust workspace using the accepted Cargo.lock. |
| `private_fixture_parity` | `acceptance` | required | required | Validate every private historical edit form through C1 and C2 before enforcing the exact approved semantic/archive parity baseline. |
| `private_collision_authority` | `acceptance` | required | required | Validate C3 collision authority against the two private reconciliation fixtures: collision candidates remain group-owned, identical-state groups may resolve shared state, and divergent-state groups block revision-by-ID. |
| `private_post_round_trip` | `acceptance` | required | required | Validate C4 all-14 offline Revision semantic-to-POST exact round trips and authoritative absent handling without any GEL network write. |
| `ui1_boundaries` | `structural` | required | required | UI1/A2 static command/state boundary: explicit Tauri allowlist, read-only archive navigation, delegated RustArchiver sync, Rust-owned ephemeral draft, typed semantic edits, no GEL tutorial or raw SQLite mutation authority. |
| `frontend_dependencies` | `structural` | required | required | Install the exact writer-ui package-lock graph; release/build paths never use floating npm install. |
| `ui1_frontend_typecheck` | `structural` | required | required | UI1 React/TypeScript compile-time contract. |
| `ui1_frontend_build` | `structural` | required | required | UI1 production frontend bundle builds from the governed source. |
| `ui1_hybrid_layout` | `structural` | required | required | Selected A+D hybrid layout/read-model invariants: authoritative course/attendance/latest tutorial projection, no School/internal IDs, focused browse and editor-dominant write mode. |
| `ui1c_forms_contract` | `structural` | required | required | UI1c0 executable field-disposition/options/InitialCourseType/structured-validation/Aims-assistance/New-regression contract closure. |
| `ui1c_semantic_validation` | `behavioral` | required | required | Focused UI1c semantic behavior: field disposition, course-type losslessness, structured validation, candidate-before-commit and New-only same-role regression. |
| `ui1c_frontend_forms` | `structural` | required | required | UI1c0 frontend no-authority check: React consumes Rust field/options projections and does not duplicate CEFR/assessment/course-type/Aims domains or expose hidden exam edits. |
| `current_state` | `structural` | required | required | Generated current-state projection is current and remains explicitly non-authoritative. |
| `verification_semantics` | `structural` | required | required | Every release check is evidence-classified and high-value invariants have semantic behavioral/acceptance proof. |
| `source_intake` | `structural` | required | required | Distribution/source intake: generated state required; complete locks required unless a source-candidate missing lock is covered by automatic LOCK_GENERATOR_UNAVAILABLE; release-package intake never receives the exception; forbidden runtime/private/build artifacts absent. |
| `release_control` | `structural` | required | required | Release identity/package commands are fail-closed, locked, no-rebuild and exact-source-bound. |
| `release_control_behavior` | `behavioral` | required | required | Behavioral tamper test proves package intake accepts an exact manifest and rejects byte changes. |
| `ci_contract` | `structural` | required | required | CI continuously runs portable governance only and cannot claim strict acceptance or use private credentials. |
| `ui1c1_editor_framework` | `structural` | required | required | UI1c1 reusable editor framework consumes Rust field rules/options, preserves structured validation DTOs and does not expose UI1c2-c4 form sections early. |
| `ui1c2_4_semantic_forms` | `structural` | required | required | UI1c2-c4 complete Standard/Initial/Final presentation consumes Rust-projected applicability/domains, preserves hidden state, routes structured validation and adds no GEL/archive write capability. |
| `ui1c5_integrated` | `structural` | required | required | UI1c5 integrated release closure: accepted GRI baseline binding, cross-form reconstruction coverage, structured validation routing, immutable Revision authority, no new GEL/archive mutation surface and current UI1c5 lifecycle metadata. |
| `ui1c5_integrated_behavior` | `behavioral` | required | required | Executable UI1c5 cross-form behavior for New Standard/Initial/Final reconstruction, structured New regression failure/candidate immutability, and Revision identity/teacher immutability without New regression. |
| `ui1d_harper` | `structural` | required | required | UI1d structural Harper/dictionary ownership, DTO, Tauri command and React presentation boundary. |
| `ui1d_harper_behavior` | `behavioral` | required | required | UI1d behavioral British-English Harper, dictionary persistence/migration/failure and field-scope regressions. |
| `ui1e_safety` | `structural` | required | required | UI1e safety invariants: native window close interception, discard guards on all navigation paths, stale_source transition handling, and absence of live write or persistent draft commands. |
| `ui1e_workflow_behavior` | `behavioral` | required | required | UI1e end-to-end workflow simulation: dirty-close interception, navigation discard guards, Harper integration, session expiry and stale-source transitions. |
| `w2_boundaries` | `structural` | required | required | W2 live submission transport boundaries: governed POST transport, readback discovery, targeted archive sync, and dirty-on-failure recovery. |
| `w2_submission_behavior` | `behavioral` | required | required | W2 live submission transport behavioral tests: New datetime omission, Revision timestamp preservation, unauthenticated fail-closed, and zero blind inserts. |

## D1 archive-schema invariant

`archive_schema_v2` runs in both portable and strict profiles. It validates fresh schema creation, legacy-v1 migration, foreign-key enforcement, relational class membership, collision-safe identity/state associations, source-presence lifecycle, privacy minimization, and the prohibition on `INSERT OR REPLACE`.

## D2 Rust repository invariant

`archive_repository` runs in both portable and strict profiles under `python -S`. It enforces the public read-only/query-only repository boundary, the crate-private candidate-only sync writer, exact D1 source-state fingerprint parity, transactional rollback/invalidation semantics, immutable canonical tutorial IDs, and the prohibition on D2 production-writer cutover.

## N1 Rust GEL session invariant

`gel_session` runs in both portable and strict profiles under `python -S`. It validates the fixed endpoint-specific read surface, exactly two login-handshake POST call sites, private cookie/credential ownership, fail-closed authentication semantics, student-email minimization, no generic transport API and no tutorial mutation authority. Credentialed live parity remains a separate manual probe and is never executed by the release gate.

## N2-PW1 zero-write browser invariant

`n2_playwright_zero_write` runs in both portable and strict profiles under `python -S` and remains offline. It statically/behaviourally validates the zero-write browser evidence boundary. Changed-teacher submit serialization is a deferred, non-blocking residual and is not an N2 functional gate.

## N2a semantic/POST authority invariant

`n2a_semantic_post` runs in both portable and strict profiles under `python -S`. It validates canonical GEL field identity, distinct New/Revision origins and submission types, complete New `datetime` omission, exact Revision source timestamp, immutable New/Revision teacher authority, first-ever New support, absence of fabricated New identity, and the offline-only POST mapper boundary.

## Named scopes

### `n2a`

Historical N2a regression scope using current workspace-level Rust verification; historical PASS=14 acceptance remains recorded in development history.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`.

### `n2b`

Historical N2b regression scope using current workspace-level Rust verification.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`.

### `n2c`

Historical N2c regression scope using current workspace-level Rust verification.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`.

### `ui1-initial`

Current regression form of the strictly accepted UI1a/b baseline; workspace Rust checks replace duplicated per-crate invocations.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`.

### `ui1-hybrid`

Current regression form of the strictly accepted A+D hybrid baseline.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`.

### `ui1c`

UI1c0 semantic-form acceptance scope before reproducible-release controls are added.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `a1_print_parity`, `a1_print_behavior`, `private_print_parity`, `a2_archiver`, `a2_archiver_behavior`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`, `ui1c_forms_contract`, `ui1c_semantic_validation`, `ui1c_frontend_forms`, `ui1c1_editor_framework`, `ui1c2_4_semantic_forms`.

### `gri`

Current GRI release-control scope: UI1c semantics plus A1 print parity, A2 Rust archiver cutover, complete locks/current-state/intake/semantic evidence/release-control/CI invariants. Strict zero-SKIP/FAIL result is required for promotion.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `a1_print_parity`, `a1_print_behavior`, `private_print_parity`, `a2_archiver`, `a2_archiver_behavior`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`, `ui1c_forms_contract`, `ui1c_semantic_validation`, `ui1c_frontend_forms`, `dependency_locks`, `dependency_lock_exception_behavior`, `current_state`, `verification_semantics`, `source_intake`, `release_control`, `release_control_behavior`, `ci_contract`, `ui1c1_editor_framework`, `ui1c2_4_semantic_forms`.

### `ui1c5`

UI1c5 integrated semantic-form release scope: the strictly accepted 39-check GRI baseline plus dedicated structural and behavioral cross-form integration closure.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `a1_print_parity`, `a1_print_behavior`, `private_print_parity`, `a2_archiver`, `a2_archiver_behavior`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`, `ui1c_forms_contract`, `ui1c_semantic_validation`, `ui1c_frontend_forms`, `dependency_locks`, `dependency_lock_exception_behavior`, `current_state`, `verification_semantics`, `source_intake`, `release_control`, `release_control_behavior`, `ci_contract`, `ui1c1_editor_framework`, `ui1c2_4_semantic_forms`, `ui1c5_integrated`, `ui1c5_integrated_behavior`.

### `ui1d`

UI1d Harper + persistent dictionary release scope: strictly accepted UI1c5 plus Rust-owned British-English assistance, persistent local dictionary ownership and dictionary failure semantics.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `a1_print_parity`, `a1_print_behavior`, `private_print_parity`, `a2_archiver`, `a2_archiver_behavior`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`, `ui1c_forms_contract`, `ui1c_semantic_validation`, `ui1c_frontend_forms`, `dependency_locks`, `dependency_lock_exception_behavior`, `current_state`, `verification_semantics`, `source_intake`, `release_control`, `release_control_behavior`, `ci_contract`, `ui1c1_editor_framework`, `ui1c2_4_semantic_forms`, `ui1c5_integrated`, `ui1c5_integrated_behavior`, `ui1d_harper`, `ui1d_harper_behavior`.

### `ui1e`

UI1e safety, dirty-close, and E2E release scope: strictly accepted UI1d plus native window close interception, navigation discard guards, stale-source handling, and end-to-end workflow behavioral proof.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `a1_print_parity`, `a1_print_behavior`, `private_print_parity`, `a2_archiver`, `a2_archiver_behavior`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`, `ui1c_forms_contract`, `ui1c_semantic_validation`, `ui1c_frontend_forms`, `dependency_locks`, `dependency_lock_exception_behavior`, `current_state`, `verification_semantics`, `source_intake`, `release_control`, `release_control_behavior`, `ci_contract`, `ui1c1_editor_framework`, `ui1c2_4_semantic_forms`, `ui1c5_integrated`, `ui1c5_integrated_behavior`, `ui1d_harper`, `ui1d_harper_behavior`, `ui1e_safety`, `ui1e_workflow_behavior`.

### `w2`

Phase W2 production submission release scope: strictly accepted UI1e baseline plus dedicated W2 submission boundary checks.

Checks: `contracts`, `governance`, `python_compile`, `archive_schema_v2`, `archive_repository`, `a1_print_parity`, `a1_print_behavior`, `private_print_parity`, `a2_archiver`, `a2_archiver_behavior`, `gel_session`, `n2_playwright_zero_write`, `n2a_semantic_post`, `n2b_new_form`, `n2c_prepopulation`, `rust_workspace_fmt`, `rust_workspace_clippy`, `rust_workspace_tests`, `private_fixture_parity`, `private_collision_authority`, `private_post_round_trip`, `ui1_boundaries`, `frontend_dependencies`, `ui1_frontend_typecheck`, `ui1_frontend_build`, `ui1_hybrid_layout`, `ui1c_forms_contract`, `ui1c_semantic_validation`, `ui1c_frontend_forms`, `dependency_locks`, `dependency_lock_exception_behavior`, `current_state`, `verification_semantics`, `source_intake`, `release_control`, `release_control_behavior`, `ci_contract`, `ui1c1_editor_framework`, `ui1c2_4_semantic_forms`, `ui1c5_integrated`, `ui1c5_integrated_behavior`, `ui1d_harper`, `ui1d_harper_behavior`, `ui1e_safety`, `ui1e_workflow_behavior`, `w2_boundaries`, `w2_submission_behavior`.


## Private fixture parity invariant

Strict baseline: **14 fixtures / 275 fields / 269 OK / 6 known mismatches / 0 unavailable**.

Each raw edit form must pass C1 contract validation and construct a valid C2 Revision semantic state whose explicit source identity matches the archive fixture. Counts alone are insufficient: every parity mismatch must match the allowlist and no unavailable field is permitted.

Default private fixture root: `fixtures-private/`. Set `GEL_PRIVATE_FIXTURES_DIR` to validate a private fixture tree stored outside the repository checkout.

Allowed mismatch set:

- `6× absent` with archive `0` and edit `true`.

## Private C3 collision-authority invariant

Strict collision fixtures: **2** (`duplicate_different_state`, `duplicate_identical_state`).

The identical-state fixture must preserve every API tutorial ID while keeping candidate source entries group-owned; revision resolves only through shared-identical authority. The divergent-state fixture must keep all source states group-owned and block revision-by-ID.

The same `GEL_PRIVATE_FIXTURES_DIR` root override supplies these reconciliation fixtures from `expected/reconciliation` and `raw/reconciliation`.

## Private C4 offline POST round-trip invariant

Strict C4 fixtures: **14** edit/archive pairs, including **5** Final fixtures and **6** governed historical absent discrepancies.

Each fixture is parsed and validated, reconstructed as a Revision semantic state, serialized by the Rust POST mapper, and compared to an independently reconstructed expected successful-control map. Exact key/value equality is required; Final Reading must be present and archive absent remains authoritative.

The same `GEL_PRIVATE_FIXTURES_DIR` root override supplies these fixtures from `expected/edit_forms` and `raw/edit_forms`.

## Live-write prohibition

No automated release-gate command may create, revise, delete, or otherwise mutate a GEL tutorial. Login/session POSTs used by separate manual acquisition tooling are not invoked by the release gate.

## Gate growth

Phase W2 live submission verification extends from the strictly accepted ui1e/w1 baseline; production release requires w2 strict acceptance.

## Commands

```fish
# Portable CI/development evidence only
python tools/release_gate.py --profile portable --scope ui1d

# Target-host strict acceptance; evidence path must be outside source
python tools/release_gate.py --profile strict --scope ui1d --evidence-out /evidence/gel/<run-id>/strict-result.json

# Package exact accepted source without rebuilding
python tools/package_release.py --evidence /evidence/gel/<run-id>/strict-result.json --output /artifacts/gel-rust-bootstrap.zip
python tools/verify_release_archive.py /artifacts/gel-rust-bootstrap.zip
```
