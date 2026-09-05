# GEL Tutorial Writer development plan

> Generated from `development_plan.json`. Edit the JSON plan, then regenerate this document.

**Plan version:** 1.24.0  
**Date:** 2026-09-04  
**Evaluation:** approved w2 strictly accepted

Phase W2 production submission strictly accepted on 2026-09-04 with PASS=47 SKIP=0 FAIL=0 (evidence: w2-strict-evidence.json). Final release archive packaged without rebuild and verified (RELEASE_ARTIFACT_VERIFIED).

## Documentation authority

1. executable schema/contracts/tests
2. active component specs
3. master/cross-component specs
4. operational docs
5. ADRs/history

## Global invariants

- GEL is authoritative for live tutorials.
- tutorial_id from the tutorial-list API is canonical historical identity.
- student_uid+tutorial_ts+tutorial_type is a locator/reconciliation key, never a unique identity.
- The Writer must not directly create or mutate canonical tutorial rows in SQLite.
- The Archiver is the sole canonical local tutorial-history writer until an explicit cutover milestone changes ownership.
- The Viewer is read-only with respect to GEL and canonical SQLite.
- Live GEL submission remains disabled until W1 and W2 gates pass.
- Changes to ownership, schema, state transitions, or externally visible behaviour must update governing docs/contracts in the same change.
- Ambiguous collision candidate states must remain separate from canonical tutorial IDs; divergent or incomplete collision evidence can never produce a revision-by-ID draft.
- Archive schema v2 separates canonical tutorial identities, candidate source states, and governed associations; blocked authority statuses must not carry source_state_id.
- D2 exposes archive v2 publicly as read-only typed models; its Rust sync write capability is crate-private/candidate-only until A2 and cannot be reached by Writer/Viewer APIs.
- N1 Rust GEL networking is an authenticated read-only acquisition boundary: credentials/cookies remain session-private, exposed source operations are fixed GETs, and login handshake POSTs grant no tutorial mutation authority.
- New tutorial creation must never invent or send a datetime locator; GEL assigns the canonical tutorial timestamp/identity server-side and it is learned only by post-submit readback.
- Teacher reassignment is not an authorized Tutorial Writer capability: New uses the validated hidden tid supplied by the fetched New form; Revision preserves the validated historical tid. GEL may expose an editable source-form selector, but Writer UI/public APIs must not expose reassignment and changed-tid server semantics are deferred non-blocking.
- New-tutorial source forms and existing revision edit forms are distinct source states. Missing datetime is valid for New and must never relax C1 existing-edit validation.

## Phase map

| Phase | Name | Priority | Status | Depends on |
| --- | --- | --- | --- | --- |
| G0 | Evidence freeze | P0 | **complete** | — |
| G1 | Governance | P0 | **complete** | G0 |
| C1 | Parser validity | P0 | **complete** | G1 |
| C2 | Semantic model | P1 | **complete_strictly_accepted** | C1 |
| C3 | Collision authority | P0 | **complete_strictly_accepted** | G1, C2 |
| C4 | Offline POST round trip | P1 | **complete_strictly_accepted** | C2, C3 |
| D1 | Archive schema v2 | P1 | **complete_strictly_accepted** | C3, G1 |
| D2 | Rust repository | P2 | **complete_strictly_accepted** | D1 |
| N1 | Rust session and read-only GEL API | P2 | **complete_strictly_accepted_live_validated** | C1, G1 |
| N2 | New tutorial semantic authority, form acquisition and prepopulation integration | P1 | **complete_strictly_accepted** | N1, C2 |
| UI1 | Tauri Writer | P2 | **complete_strictly_accepted** | C2, D2, N2 |
| GRI | Governance and reproducible release identity | P1 | **complete_strictly_accepted** | G1 |
| AGP | AI Governance Protocol v1.1 + GEL project profile | P1 | **complete_strictly_accepted** | GRI |
| A1 | Rust print parity | P2 | **complete_strictly_accepted** | G1 |
| A2 | Rust archiver cutover | P2 | **complete_strictly_accepted** | A1, D2, N1 |
| W1 | Submission verification | gated | **complete_strictly_accepted** | C4, N2, UI1 |
| W2 | Production submission | gated | **complete_strictly_accepted** | W1, A2 |

## G0 — Evidence freeze

**Priority:** P0  
**Status:** complete  
**Depends on:** none

**Scope**

- Create canonical machine-readable GEL tutorial field contract.
- Create canonical tutorial-type contract.
- Create semantic applicability contract.
- Freeze known source anomalies and authority overrides.
- Freeze observed evidence and record projected evidence distinctly until a strict execution promotes it to observed.
- Generate Rust GEL constants and generated contract documentation from the canonical contracts.
- Establish check:contracts and enforce that generated artifacts and active Python/Rust projections do not drift.

**Artifacts**

- `contracts/gel_tutorial_fields.json`
- `contracts/tutorial_types.json`
- `contracts/tutorial_form_applicability.json`
- `contracts/known_source_anomalies.json`
- `contracts/evidence_baseline.json`
- `tools/generate_contract_artifacts.py`
- `tools/check_contracts.py`
- `gel-core/src/gel_fields.rs (generated)`
- `docs/generated/GEL_TUTORIAL_CONTRACTS.md`
- `docs/generated/CONTRACT_INDEX.md`

**Exit conditions**

- python tools/check_contracts.py returns PASS
- Generated artifacts are current
- Opaque GEL form IDs in Rust source are confined to the generated compatibility module
- Final Reading is contractually Standard+Final only
- Known absent/collision/Aims/blank anomalies are explicit authority rules

**Result:** Implemented in v5; the projected 275-field baseline was subsequently promoted to observed evidence after the C1 strict gate passed on 2026-08-24.

## G1 — Governance

**Priority:** P0  
**Status:** complete  
**Depends on:** G0

**Scope**

- Define architecture and component boundaries.
- Define source-vs-derived state ownership and permitted writers.
- Define invalidation/last-seen policy.
- Publish active component specs covering role, scope, authority, reads, writes, must-not-write boundaries, state transitions, failure semantics, dependencies and tests.
- Add generated documentation index and release-gate specification.
- Treat ADRs as historical decisions with explicit status only.

**Artifacts**

- `contracts/documentation_governance.json`
- `contracts/component_boundaries.json`
- `contracts/state_ownership.json`
- `contracts/release_gate.json`
- `tools/generate_governance_artifacts.py`
- `tools/check_governance.py`
- `tools/release_gate.py`
- `tools/check_private_fixture_parity.py`
- `docs/GOVERNANCE.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_OWNERSHIP.md`
- `docs/RELEASE_GATE.md`
- `docs/components/*.md`
- `docs/generated/DOCUMENTATION_INDEX.md`
- `docs/adrs/README.md`

**Exit conditions**

- All active components have specs
- Ownership matrix has exactly one permitted canonical writer per state class
- Documentation index is generated/current
- Portable and strict gate semantics are documented

**Result:** implemented in v6 G1 governance revision

## C1 — Parser validity

**Priority:** P0  
**Status:** complete  
**Depends on:** G1

**Scope**

- Introduce raw-vs-validated edit-form state and explicit PresentValue/PresentUnset/Missing/Malformed classification.
- Generate edit-control validation metadata from the canonical GEL field contract.
- Fail closed when an applicable required GEL control is missing, wrong-kind, duplicate, structurally malformed or illegally unset.
- Model browser default-first-option select behaviour so an untouched placeholder remains PresentUnset rather than Missing.
- Validate type discriminator, positive metadata IDs/timestamps, historical teacher selection, GEL date format, CEFR select domains and complete Standard radio-group option sets.
- Reject known type-inapplicable tutorial controls as contract drift.
- Run validation before private fixture comparison and semantic revision construction.

**Artifacts**

- `gel-core/src/edit_form_validation.rs`
- `gel-core/tests/edit_form_validation.rs`
- `generated EditControlSpec metadata in gel-core/src/gel_fields.rs`
- `updated canonical field/governance/state-ownership contracts`

**Exit conditions**

- Missing applicable control is represented as Missing and validation fails.
- Wrong-kind/duplicate/impossible controls are represented as Malformed and validation fails.
- Intentional placeholders and blank radio groups are PresentUnset and validate where the contract allows unset.
- Semantic revision construction cannot consume unvalidated edit state.
- Private fixture comparator validates each raw edit form before field parity, so all 14 strict fixtures must satisfy C1 when locally available.

**Result:** Strict release gate passed locally on 2026-08-24: contracts, governance, Python compile, rustfmt, Clippy, Rust tests and exact private fixture parity all PASS; parity was 14 fixtures / 275 fields / 269 OK / 6 allowlisted absent mismatches / 0 unavailable.

## C2 — Semantic model

**Priority:** P1  
**Status:** complete_strictly_accepted  
**Depends on:** C1

**Scope**

- Make DraftOrigin explicit: New vs Revision.
- Separate editable semantic source-of-truth from raw/provenance values.
- Retain Final Reading and summary-authoritative historical absent.
- Enforce tutorial-type and origin invariants before POST mapping.
- HTML-escape Aims plain text before newline-to-<br> rich-text serialization.

**Artifacts**

- `contracts/tutorial_form_semantics.json`
- `gel-core/src/semantic.rs`
- `gel-core/src/post_mapper.rs`
- `gel-core/tests/semantic.rs`
- `gel-core/tests/post_mapper.rs`
- `updated semantic/component/state-ownership/generated documentation`

**Exit conditions**

- Revision state construction passes semantic and strict private-fixture tests.
- New and Revision cannot be confused by Option identity semantics.
- Overall level and Aims each have one editable semantic representation; source raw/HTML values are provenance-only.
- Type-inapplicable populated semantic fields fail validation.
- POST mapping validates semantic state and never uses provenance as semantic fallback.
- Aims text is HTML-escaped before line breaks are encoded as <br>.

**Result:** Completed and strictly accepted after v8.1. The strict release gate passed contracts, governance, Python compile, rustfmt, Clippy, all Rust tests, the exact 14/275/269/6/0 private parity baseline, and semantic Revision construction for all 14 fixtures.

## C3 — Collision authority

**Priority:** P0  
**Status:** complete_strictly_accepted  
**Depends on:** G1, C2

**Scope**

- Keep canonical tutorial-list API identities separate from captured summary source states and explicit association authority.
- Never positionally assign collision candidate states to tutorial IDs.
- Classify collisions as identical-state, divergent-state, or incomplete-evidence from governed summary state.
- Preserve every canonical ID in identical-state collisions while permitting revision only through a shared-identical state authority.
- Block revision-by-ID for divergent, incomplete, unmatched, or legacy ambiguous-unknown state authority.
- Treat timestamp-only print/edit route observations as collision-group evidence, never as an implicit per-ID discriminator.
- Require both synthetic and private real-collision regressions in the release gate.

**Artifacts**

- `contracts/reconciliation_authority.json`
- `gel-core/src/models.rs`
- `gel-core/src/reconciliation.rs`
- `gel-core/src/semantic.rs`
- `gel-core/src/fixture_support.rs`
- `gel-core/tests/reconciliation.rs`
- `gel-core/tests/semantic.rs`
- `gel-core/src/bin/check_reconciliation_fixtures.rs`
- `tools/check_private_collision_authority.py`
- `updated release/governance/state-ownership contracts and generated documentation`

**Exit conditions**

- Collision pairs never carry a positionally assigned summary state.
- Identical-state collisions preserve all IDs and resolve only a shared-equivalent historical state.
- Divergent and incomplete collisions cannot yield an authoritative per-ID revision state.
- Legacy collision_ambiguous archive rows fail closed for revision unless separately resolved from governed collision evidence.
- Synthetic Rust reconciliation/semantic tests pass.
- Both private reconciliation fixtures pass the strict C3 collision-authority gate.

**Result:** Strict release gate passed on 2026-08-24 with PASS=8 SKIP=0 FAIL=0, including both private collision-authority fixtures and the existing 14/275/269/6/0 private parity contract.

## C4 — Offline POST round trip

**Priority:** P1  
**Status:** complete_strictly_accepted  
**Depends on:** C2, C3

**Scope**

- Run all 14 private edit fixtures through archive+validated edit -> Revision semantic form -> POST payload.
- Independently reconstruct the expected browser-successful POST map from validated source controls plus governed archive absent authority and require exact key/value equality.
- Require the confirmed 14/275/269/6/0 strict private-fixture parity baseline and the C3 collision-authority gate to remain green.
- Require all five Final fixtures to include Reading in the derived payload, including the unset placeholder case.
- Require exactly six historical edit-form absent discrepancies and prove POST uses archive/summary absent rather than the bad edit checkbox.
- Add mutation-isolation tests proving one editable semantic change affects only its declared GEL payload field and provenance-only changes affect none.
- Keep the entire phase offline with no HTTP client or GEL tutorial write authority.

**Artifacts**

- `contracts/offline_post_round_trip.json`
- `gel-core/src/bin/check_post_round_trip_fixtures.rs`
- `gel-core/tests/post_mutation_isolation.rs`
- `tools/check_private_post_round_trip.py`
- `contracts/release_gate.json private_post_round_trip check`

**Exit conditions**

- All 14 private revision fixtures produce exact independently verified POST payload maps
- All five Final fixture payloads contain Reading
- Exactly six historical absent source discrepancies are observed and archive/summary absent controls POST encoding
- Mutation-isolation tests pass for every editable semantic payload field and provenance-only mutations change no payload field
- Strict release gate passes with the new C4 private check
- No network write capability exists

**Result:** Strict acceptance observed: PASS=9 SKIP=0 FAIL=0, including exact private POST round-trip evidence.

## D1 — Archive schema v2

**Priority:** P1  
**Status:** complete_strictly_accepted  
**Depends on:** C3, G1

**Scope**

- Versioned schema migrations.
- Enable and test foreign keys.
- Replace INSERT OR REPLACE with safe UPSERTs.
- Replace students.class_id with membership relation.
- Model source_present/first_seen/last_seen invalidation semantics.
- Normalize collision identity/state/association storage.
- Decide raw_json retention/minimization policy.

**Phase evaluation**

Status: **approved with amendments**.

Implement schema v2 as executable target authority and a separate-destination migration path, but do not cut the active Python archive writer over during D1. Preserve legacy collision ambiguity fail-closed, keep canonical tutorial identity separate from candidate source state, require non-destructive source-presence semantics, and exclude raw_json/email from v2.

**Implementation notes**

- Executable schema authority is schema/archive_v2.sql with PRAGMA user_version=2.
- D1 defines and validates v2 without cutting the active Python v4.9 writer over to v2; D2 prepares the Rust repository without ownership transfer; A2 retains production cutover responsibility.
- Legacy migration is source-to-separate-destination and fails closed on invalid parent identity/collision evidence.
- v2 separates tutorial identities, candidate source states, collision groups, and governed state associations; blocked authority statuses carry no source_state_id.
- students.class_id is replaced by class_memberships in v2.
- source_present/first_seen/last_seen lifecycle columns and archive_sync_runs are executable schema invariants.
- v2 drops raw_json/email and preserves only minimal field-presence provenance.
- Transitional Python v4.9 class/student writes now use ON CONFLICT UPSERTs and enable SQLite foreign keys.
- D1 schema acceptance is dependency-minimal/offline: it AST-extracts the exact transitional oracle UPSERT SQL and tests it in isolated SQLite instead of importing the requests/bs4-dependent live oracle runtime.
- The release gate executes check:archive-schema with Python -S so accidental third-party/site-package dependencies are an executable failure, not merely a documentation rule.

**Artifacts**

- `schema/archive_v2.sql`
- `contracts/archive_schema_v2.json`
- `python-oracle/archive_schema_v2.py`
- `tools/check_archive_schema.py`
- `docs/components/archive_schema_migrator.md`

**Exit conditions**

- Fresh-schema and legacy-v1 migration checks pass under check:archive-schema
- Foreign keys are enabled and PRAGMA foreign_key_check is clean
- No canonical ambiguous state is falsely attributed
- students.class_id is absent from v2 and membership is relational
- Legacy raw_json/email is not retained in v2 migration output
- Portable/strict release gate includes the canonical archive schema check
- Full strict gate passes before D1 is marked complete

**Result:** Strict acceptance observed on 2026-08-26: PASS=10 SKIP=0 FAIL=0, including archive_schema_v2 and all C1-C4 private evidence gates.

## D2 — Rust repository

**Priority:** P2  
**Status:** complete_strictly_accepted  
**Depends on:** D1

**Scope**

- Implement public read-only Rust repository against schema v2 with typed Writer/Viewer navigation models and fail-closed revision loading.
- Implement a separate crate-private archive-sync write capability; do not expose canonical-history write methods to external Writer/Viewer consumers.
- Keep Python v4.9 as production canonical archive writer until A2; D2 Rust writes target only archive-v2 candidate/test databases.
- Materialize each sync transactionally; failed materialization rolls back and cannot invalidate prior source presence.
- Allow source-presence invalidation only for successful full syncs after the run is marked complete inside the transaction; targeted syncs never infer absence.
- Compute source-state SHA-256 fingerprints with exact D1 legacy-migrator semantic projection parity.
- Persist collision group membership and associations with typed authority checks; divergent/incomplete/unknown states remain blocked.
- Validate repository semantic invariants and foreign keys before commit.

**Phase evaluation**

Status: **approved with amendments**.

Proceed with D2 only as a split-capability repository: public read-only API plus crate-private sync writer. Keep production canonical ownership on Python v4.9 until A2, forbid implicit DB creation, make sync materialization transactional, restrict absence invalidation to completed full runs, and keep fingerprint/collision authority executable.

**Implementation notes**

- D2 is not the A2 production cutover: python_archiver_oracle remains sole writer of normalized_local_archive.
- ArchiveSyncRepository opens existing v2 databases read-write without CREATE and is crate-private.
- ArchiveRepository opens existing v2 databases with SQLITE_OPEN_READ_ONLY and PRAGMA query_only=ON.
- Whole repository materialization is transactional; the sync run row exists outside the transaction so failures remain observable.
- Full-run invalidation occurs only after status=complete inside the transaction, satisfying D1 presence guards; targeted runs do not invalidate unseen rows.
- Source-state fingerprints mirror python-oracle/archive_schema_v2.py legacy_state_fingerprint and exclude acquisition-route provenance URLs/methods.

**Artifacts**

- `contracts/archive_repository.json`
- `gel-core/src/archive_repository.rs`
- `gel-core/src/archive_sync_repository.rs`
- `gel-core/tests/archive_repository.rs`
- `tools/check_archive_repository.py`
- `check-archive-repository`
- `updated release/governance/state-ownership contracts and generated documentation`

**Exit conditions**

- python -S tools/check_archive_repository.py returns PASS
- Rust repository behavioural tests pass under cargo test
- Public ArchiveRepository opens only schema-v2 read-only/query-only and exposes no SQLite write handle
- archive_sync_repository remains crate-private and is not publicly re-exported
- Failed sync rollback and successful-full-only invalidation tests pass
- D1-compatible source-state fingerprint regression passes
- Collision association/read-back tests preserve C3 fail-closed authority
- Full strict release gate passes before D2 is marked complete

**Result:** Strict acceptance observed on 2026-08-26: PASS=11 SKIP=0 FAIL=0, including archive_repository and all prior private evidence gates.

## N1 — Rust session and read-only GEL API

**Priority:** P2  
**Status:** complete_strictly_accepted_live_validated  
**Depends on:** C1, G1

**Scope**

- Own Rust authentication/session state with a private cookie store and transient credentials.
- Implement the established two-step Learn2 login handshake and verify both api2 and learn2 sessions.
- Expose fixed GET-only methods for open classes, class students, student profile, tutorial list, summary, print and historical edit pages.
- Project tutorial-list responses to canonical tutorial_id/timestamp observations while leaving semantic parsing to existing parser components.
- Strip student email-like fields recursively at the acquisition boundary.
- Expose no generic request API and no GEL tutorial create/revise/delete endpoint; login POSTs are the only N1 POST authority.
- Keep live parity manual and credential-free from automated release gates.

**Phase evaluation**

Status: **approved with amendments**.

Proceed with N1 as a narrow acquisition component rather than a general HTTP client. Include the class/student/profile reads needed by later UI/A2 consumers, preserve GEL as source authority, strip student email fields immediately, allow POST only for the two established login handshake calls, and keep live credentialed parity outside automated release gates.

**Implementation notes**

- Rust parsers/repositories receive only returned source data, never credentials or cookies.
- The public session surface is endpoint-specific; arbitrary URL/method transport is private and unavailable to consumers.
- The release gate validates the N1 boundary offline; check_gel_read_only_live is a separate manual probe because credentials/network cannot be canonical release dependencies.
- N1 does not cut over the production archiver; Python v4.9 remains sole normalized_local_archive writer until A2.

**Artifacts**

- `contracts/gel_read_only_session.json`
- `gel-core/src/gel_session.rs`
- `gel-core/src/bin/check_gel_read_only_live.rs`
- `tools/check_gel_session.py`
- `check-gel-session`
- `updated release/governance/state-ownership contracts and generated documentation`

**Exit conditions**

- Offline N1 contract/boundary check passes in portable and strict release gates
- Rust unit tests prove login-only POST routing, GET read routes, expiry fail-closed behaviour, tutorial identity projection and student privacy filtering
- Manual live read-only probe confirms tutorial-list/summary/print/edit parity and C1-valid historical edit retrieval
- No password, cookie jar or serialized login body is exposed to parser/repository/frontend APIs or diagnostics
- No GEL tutorial write capability exists

**Result:** Strict acceptance observed on 2026-08-27: PASS=12 SKIP=0 FAIL=0. Credentialed manual read-only probe also passed with tutorial-list/summary/print/edit parity, C1-valid historical edit retrieval, 8 HTTP requests and 0 GEL tutorial writes.

## N2 — New tutorial semantic authority, form acquisition and prepopulation integration

**Priority:** P1  
**Status:** complete_strictly_accepted  
**Depends on:** N1, C2

**Scope**

- Treat latest tutorial as the established New prepopulation source when one exists; first-ever New may have no prepopulation source.
- Use canonical GEL field identity rather than equal-value inference: Initial 264/265/266/267; current 233/234/235/236; Reading 476; Final pairs initial/current fields and retains independently established Final Reading.
- Make New and Revision identity semantics structurally distinct. New has no authoritative created GEL identity and must omit datetime entirely; Revision is bound to its existing TutorialIdentity and exact source timestamp.
- Make teacher attribution immutable Writer authority: New uses the validated hidden teacher supplied by the fetched New form; Revision preserves the historical tutorial teacher. Writer exposes no teacher reassignment.
- Keep current-date customdate as a New-form default only; tutorial date remains editable semantic draft state.
- Define source-vs-derived ownership and invalidation: authentication loss invalidates New-form teacher authority, latest-source change makes a New draft stale, and Revision source change requires conflict/stale handling.
- Keep PW1 changed-teacher serialization/server acceptance as deferred non-blocking residual evidence because it has no supported Writer functionality impact.
- Require N2b as the production NewTutorialForm acquisition/parser path; do not weaken the existing historical edit parser to accept New forms.
- Freeze field-by-field New copy/reset/derive behaviour in N2c after canonical semantic field identity is in place.

**Phase evaluation**

Status: **approved with material amendments**.

N2a is approved and implemented first because New datetime/teacher/identity semantics are already established. N2b is required, not conditional. PW1 changed-tid serialization is deferred non-blocking. Canonical field identity replaces equal-value provenance inference.

**Evidence basis**

- Bundle: `GEL_tutorial_creation_teacher_evidence_v1.zip`
- Raw source archive SHA-256: `29497b61eb6bd3b41cf955d7c5a751fbc90e83b555c7939bd51a8419d1c24b2d`
- `NEW-1` (direct_high): New form/create POST omit datetime; server assigns identity.
- `NEW-2` (direct_high): Same-day timestamp construction is explanatory only.
- `NEW-3` (triangulated_high): Future-dated timestamp behaviour is explanatory only; never predict client-side.
- `TEACHER-1` (direct_high): New form-provided tid matched authenticated teacher in captured create flow.
- `TEACHER-2` (direct_high): Ordinary revision preserves stored historical tid even under a different authenticated teacher.
- `TEACHER-3` (direct_boundary): Deliberate teacher reassignment server acceptance/semantics are not established.
- `UPDATE-1` (direct_high): Revision form/POST preserve existing datetime.

**Implementation order**

- N2-PW1 — Core zero-write form evidence COMPLETE for functional requirements; changed-tid submission observation deferred non-blocking.
- N2a — Semantic/POST authority correction COMPLETE / STRICTLY ACCEPTED (PASS=14 SKIP=0 FAIL=0).
- N2b — Distinct authoritative NewTutorialForm fixed-GET acquisition/parser COMPLETE / STRICTLY ACCEPTED (PASS=15 SKIP=0 FAIL=0).
- N2c — Canonical field-by-field New prepopulation/default/reset contract COMPLETE / STRICTLY ACCEPTED (PASS=16 SKIP=0 FAIL=0).
- Core N2 completes after N2c strict acceptance; proceed to UI1.
- Residual teacher-reassignment serialization/server semantics may be investigated later only if a product requirement emerges.

**Non-goals**

- No GEL tutorial mutation in N2a.
- No teacher reassignment support or server experiment.
- No client-side prediction of server-assigned tutorial identity/timestamp.
- No weakening of the historical Revision edit-form validator to parse New forms.
- No freezing of detailed per-field New prepopulation rules until N2c.
- No full field-by-field prepopulation freeze in N2b; N2c owns copy/reset/derive semantics.

**Residual questions**

- For N2c, which same-semantic fields are copied/reset/transformed/session-derived/date-derived/unset for each New tutorial type?
- Changed-tid authentic serialization and GEL server reassignment semantics are deferred non-blocking residual evidence.

**Implementation notes**

- The browser context is ephemeral and created with service_workers=block so the route firewall remains authoritative.
- The context-wide route is installed before page.goto(LOGIN_URL). AUTHENTICATION forwards only the exact Learn2 login POST and never calls post_data/header inspection.
- Expected tutorial process POST bodies are read transiently only after authentication, reduced immediately to tid alias/type/customdate/datetime structural evidence and then aborted in a finally block.
- The harness never stores or prints raw teacher IDs, teacher names, student UID/name, comments, aims, level values, cookies, headers, form tokens or raw HTML.
- Teacher aliases T1/T2 are run-local relationships only. Student evidence uses S1 only; summary/state hashes exclude student UID.
- Client validation/no request is INCONCLUSIVE and is never bypassed by synthetic submission.
- PW1 is evidence-only tooling and is not imported into the production Rust GEL session or future Writer runtime.
- v13.5 diagnostic repair keeps the authentication allowlist unchanged. It exposes only a privacy-safe terminal diagnostic for blocked authentication mutations; the observed route must be reviewed before any future allowlist amendment.
- v13.6 replaces the ambiguous press-Enter authentication transition with explicit two-stage manual browser authentication and GET-only session verification. Both credential submissions remain entirely inside GEL pages; the harness reads no username/password values.
- v13.7 distinguishes mutation authority by origin after live evidence showed Google Analytics POST /j/collect during successful authentication. Third-party mutating telemetry is blocked for privacy but no longer classified as GEL contract drift; unexpected GEL-origin mutations remain fail-closed.
- The successful v13.6 authentication output proves login itself is working; v13.7 adds static stage markers because the remaining EvidenceContractError occurred after the authenticated GET and was otherwise opaque.
- v13.8 repairs a local privacy-projection contradiction exposed only after the live run reached final_verification: classify_prepopulation emitted student_uid/teacher_id as harmless semantic labels, while the global privacy guard correctly rejected identity-bearing keys. The repair keeps the privacy guard strict and moves identity semantics to non-identifying relationship rules instead of weakening the guard.
- v13.9 fixes the remaining local privacy-validation failure exposed after v13.8 reached privacy_validation. The strict validator was rejecting its own negative metadata keys raw_html_persisted/request_headers_persisted/teacher_names_persisted. The repair centralizes the persisted evidence preamble, renames those policy assertions to page_source_capture_enabled/submission_payload_capture_enabled/network_header_capture_enabled/staff_display_label_capture_enabled=false, and keeps the forbidden raw-data key guard unchanged.

**Artifacts**

- `contracts/n2a_semantic_post_authority.json`
- `contracts/tutorial_form_semantics.json v4`
- `contracts/tutorial_form_applicability.json v2`
- `contracts/offline_post_round_trip.json v2`
- `contracts/evidence_baseline.json v2`
- `contracts/n2_playwright_zero_write_evidence.json v8`
- `gel-core/src/semantic.rs`
- `gel-core/src/post_mapper.rs`
- `gel-core/src/gel_fields.rs generated projection`
- `gel-core/tests/semantic.rs`
- `gel-core/tests/post_mapper.rs`
- `tools/check_n2a_semantic_post.py`
- `check-n2a-semantic-post`
- `release gate scope n2a`
- `active component/state ownership specs and generated docs`
- `contracts/gel_tutorial_fields.json v4`
- `contracts/new_tutorial_form.json v1`
- `contracts/gel_read_only_session.json v2`
- `contracts/n2a_semantic_post_authority.json v2`
- `gel-core/src/form_parser_common.rs`
- `gel-core/src/new_form_parser.rs`
- `gel-core/fixtures/synthetic/new_standard.html`
- `gel-core/fixtures/synthetic/new_initial.html`
- `gel-core/fixtures/synthetic/new_final.html`
- `gel-core/tests/new_form.rs`
- `tools/check_n2b_new_form.py`
- `check-n2b-new-form`
- `release gate scope n2b`
- `contracts/new_tutorial_prepopulation.json`
- `gel-core/tests/new_prepopulation.rs`
- `tools/check_n2c_prepopulation.py`
- `check-n2c-prepopulation`
- `release gate scope n2c`

**Exit conditions**

- N2a canonical field IDs/roles are executable and equality-based cross-field provenance is forbidden.
- New/Revision submission types are distinct; New cannot serialize datetime and Revision emits exact source tutorial_ts.
- New teacher is immutable validated New-form authority; Revision teacher is immutable historical authority; no Writer/public teacher reassignment path exists.
- New has no authoritative GEL identity before a future successful create followed by fresh readback; first-ever New with no prepopulation source remains representable.
- Source-vs-derived state ownership and invalidation rules are documented and executable where applicable.
- N2a contracts/specs/generated docs are current and the named N2a release scope includes affected C1/C2/C4 plus existing governed regressions.
- N2b implements authoritative NewTutorialForm acquisition/validation.
- N2c freezes per-field New prepopulation behaviour using canonical same-semantic field mapping.
- Core N2 completes without changed-teacher serialization/server reassignment evidence; that residual remains non-blocking.

**Result:** Core N2 complete: N2a PASS=14, N2b PASS=15, N2c PASS=16, all SKIP=0 FAIL=0; no network-write or teacher-reassignment authority added.

## UI1 — Tauri Writer

**Priority:** P2  
**Status:** complete_strictly_accepted  
**Depends on:** C2, D2, N2

**Scope**

- UI1a: Tauri/React shell, transient authentication using current GelSession, and read-only D2 class/student/tutorial navigation using CELS-derived AG Grid patterns.
- UI1b: Rust-owned ephemeral tutorial draft authority, governed New/Revision constructors, typed semantic edits, candidate-before-commit validation, and no frontend mutation of teacher/origin/identity/raw GEL state.
- UI1c: complete Initial/Standard/Final semantic forms with Rust-owned CEFR/applicability/regression validation and authoritative New-type reconstruction.
- UI1d: CELS-derived British-English Harper service plus a separately governed persistent local user dictionary; persistent tutorial drafts remain out of scope.
- UI1e: dirty-close/navigation/logout protection, stale/session-expiry states, mocked E2E, static command boundary and full UI1 release gate.
- Reuse donor projects selectively: CELS for desktop presentation/AG Grid/Harper/dirty-close patterns; GEL Planner for Rust AppState/candidate-before-commit/typed edit/safety patterns; current N1/N2 remain runtime authority.
- Expose no GEL tutorial mutation, generic HTTP, archive write, teacher reassignment or raw POST capability.

**Phase evaluation**

Status: **approved with amendments**.

Use current N1/N2 contracts as authority; reuse CELS frontend/Harper concepts and GEL Planner Rust state/safety patterns selectively. React is presentation-only, Rust owns the semantic draft, persistent Harper dictionary is an explicit later local-state component, and UI1 exposes no GEL tutorial writes.

**Implementation order**

- UI1a — Shell, auth and read-only navigation: COMPLETE / STRICTLY ACCEPTED.
- UI1b — Rust-owned draft authority foundation: COMPLETE / STRICTLY ACCEPTED.
- UI1-LAYOUT-AD-HYBRID — COMPLETE / STRICTLY ACCEPTED (PASS=23 SKIP=0 FAIL=0).
- GRI0–GRI5 — COMPLETE / STRICTLY ACCEPTED (PASS=39 SKIP=0 FAIL=0).
- UI1c0–UI1c4 — IMPLEMENTED; GRI prerequisite satisfied.
- UI1c5 — COMPLETE / STRICTLY ACCEPTED (PASS=41 SKIP=0 FAIL=0).
- UI1d — Harper + persistent dictionary: COMPLETE / STRICTLY ACCEPTED (PASS=43 SKIP=0 FAIL=0).
- UI1e — dirty-close/stale-state/E2E/full release: IMPLEMENTED; strict ui1e PASS=45 target pending.

**Non-goals**

- No GEL tutorial submission/create/revision/delete command in UI1.
- No raw SQLite/archive writer capability in React or the normal draft-edit surface; the existing explicit ui1_sync_archive command may delegate only to RustArchiver under A2.
- No persistent tutorial drafts in UI1; only the later Harper dictionary may introduce governed local durable state.
- No reuse of legacy Planner GelClient/write/save transport.
- No frontend CEFR authority or raw GEL field IDs.
- No teacher reassignment support.

**Implementation notes**

- React is presentation-only and receives safe DTO/view models.
- Rust WriterAppState owns session, one ephemeral active draft and a serialized writer-operation lock.
- New draft construction composes D2 latest authoritative source + N2b fetched validated New form + N2c build_new_form_state.
- Revision construction composes D2 revision authority + N1 historical form GET + C1 validation + C2 semantic construction.
- TutorialDraftEdit is a semantic allowlist; it has no SetTeacher, SetIdentity, SetTimestamp, SetTutorialType-on-Revision or raw GEL mutation variants.
- Each edit clones the current draft, mutates the candidate, validates semantic invariants, and replaces authoritative in-memory state only after success.
- Teacher comments are bounded at 970 Unicode scalar values in Rust; frontend maxLength is UX only.
- Frontend password state is cleared in a finally block after every login attempt and no localStorage/sessionStorage is used.
- Harper persistent dictionary is approved for UI1d but requires separate ownership/schema/version/privacy contracts before implementation.
- UI display projects recognized verbose GEL overall-level source labels (for example A2-: pre-intermediate) to compact canonical CEFR codes (A2-) in the Rust safe view model; source/archive values are not modified and React does not parse descriptors.
- Archive default is platform-aware: non-empty GEL_ARCHIVE_DB overrides; Windows defaults to gel-new-v2.db beside the running executable via current_exe parent; non-Windows falls back to project-root gel-new-v2.db. Existing archives must be schema v2 and are not migrated in place; the explicit ui1_sync_archive action delegates canonical creation/synchronization only to RustArchiver, while normal Writer navigation remains read-only.

**Artifacts**

- `contracts/ui1_writer.json`
- `writer-ui/`
- `tools/check_ui1_boundaries.py`
- `check-ui1-boundaries`
- `active UI1 component/state ownership specs and generated docs`
- `contracts/ui1_layout_hybrid.json`
- `tools/check_ui1_hybrid_layout.py`
- `release gate scopes ui1-initial + ui1-hybrid`
- `plans/ui1c_semantic_forms_plan_v1_2.json`
- `plans/UI1C_SEMANTIC_FORMS_PLAN_v1_2.md`
- `contracts/ui1c_semantic_forms.json`
- `contracts/ui1c_aims_assistance.json`
- `tools/check_ui1c_forms_contract.py`
- `tools/check_ui1c_frontend_forms.py`
- `gel-core/tests/ui1c_semantic_contract.rs`
- `release gate scopes ui1-initial + ui1-hybrid + ui1c + gri`
- `tools/check_ui1c1_editor_framework.py`
- `writer-ui/src/components/SemanticFieldControl.tsx`
- `writer-ui/src/components/TutorialTypeFields.tsx`
- `tools/check_ui1c2_4_semantic_forms.py`

**Exit conditions**

- All internal UI1a-e gates complete and strict UI1 release gate passes.
- React cannot mutate authoritative identity/teacher/raw GEL state and all semantic changes traverse Rust typed edits.
- Revision preserves historical teacher; New uses validated New-form teacher and N2c projection.
- Persistent Harper dictionary is governed separately from canonical archive and ephemeral tutorial drafts.
- No GEL tutorial mutation or archive mutation command exists anywhere in UI1.

## GRI — Governance and reproducible release identity

**Priority:** P1  
**Status:** complete_strictly_accepted  
**Depends on:** G1

**Scope**

- GRI0 generated current-state projection
- GRI1 one Rust workspace + Cargo/npm lock identity and --locked/npm ci release commands
- GRI2 source/package intake and exact checksum manifest
- GRI3 semantic evidence classification for high-value invariants
- GRI4 portable CI with no private/strict authority
- GRI5 ADR/history consolidation and generated indexes
- AI Governance Protocol v1.1 + GEL profile conformance through check:governance

**Phase evaluation**

Status: **approved with amendments**.

Preserve GEL runtime governance; add deterministic dependency identity, generated current-state projection, exact package intake, semantic evidence classification, portable CI and no-rebuild artifact verification. Current-state is projection only and CI cannot claim strict acceptance.

**Non-goals**

- No GEL runtime semantic changes
- No archive writer cutover
- No automatic candidate promotion
- No fabricated/placeholder locks and no manual lock-exception override; tool-unavailable evidence is not dependency decision state.

**Artifacts**

- `Cargo.toml workspace`
- `Cargo.lock (target-generated/required)`
- `writer-ui/package-lock.json (target-generated/required)`
- `contracts/release_identity.json`
- `contracts/verification_semantics.json`
- `governance/current-state.schema.json`
- `governance/current-state.json`
- `governance/dependency-lock-manifest.json`
- `tools/generate_dependency_lockfiles.py`
- `tools/check_dependency_lockfiles.py`
- `tools/check_intake.py`
- `tools/release_gate.py evidence output`
- `tools/package_release.py`
- `tools/verify_release_archive.py`
- `.github/workflows/portable-governance.yml`
- `governance/agent-protocol/ai-governance-protocol.v1.1.json`
- `governance/agent-protocol/project-profile.schema.json`
- `governance/agent-protocol/agent-run-result.schema.json`
- `governance/agent-protocol/profiles/gel-tutorial-writer.profile.json`
- `tools/check_ai_governance_protocol.py`
- `check-ai-governance`

**Exit conditions**

- Complete synchronized Cargo.lock and writer-ui/package-lock.json committed before STRICT_ACCEPTED; portable source validation may carry explicit LOCK_GENERATOR_UNAVAILABLE SKIP evidence while a corresponding generator is absent.
- check:contracts and check:governance current
- portable GRI gate has no public dependency/build FAIL and any private absence is explicit SKIP
- strict GRI target-host gate records all PASS / zero SKIP/FAIL to immutable external evidence
- package tool accepts only matching strict evidence and verifies final archive bytes without rebuilding

**Result:** Strict GRI accepted on 2026-08-31 with PASS=39 SKIP=0 FAIL=0; subsequent UI1c5 source changes require a new strict ui1c5 acceptance.

## AGP — AI Governance Protocol v1.1 + GEL project profile

**Priority:** P1  
**Status:** complete_strictly_accepted  
**Depends on:** GRI

**Scope**

- Protocol v1.1 schemas and canonical instance for authority discovery, state classes, evidence, lifecycle, mutation profiles and release claims.
- GEL profile binding the generic protocol to existing documentation/state/release/verification contracts.
- Portable vs strict promotion ceilings and explicit no-SKIP-as-PASS semantics.
- Gate side-effect policy forbidding automated GEL tutorial and canonical archive writes.
- Semantic run-result validation preventing contradictory lifecycle claims.
- check:governance integration and generated human profile/index projection.

**Phase evaluation**

Status: **approved with amendments**.

Adopt the generic protocol only as meta-governance orchestration. Repair the v1 evidence/run-result contradiction, enforce lifecycle semantics, split evidence stage/proof class, make current-state projection-only, model profile-sensitive reproducibility blocking, and bind a GEL profile to existing runtime contracts without duplicating their semantics.

**Non-goals**

- No GEL field/applicability/POST semantic authority is moved into the generic protocol.
- No archive writer, network endpoint, teacher/timestamp or UI semantic rule is duplicated as generic runtime authority.
- No automatic promotion from CI, diagnostics, candidates or evidence.
- No new GEL tutorial mutation capability.

**Artifacts**

- `governance/agent-protocol/ai-governance-protocol.schema.json`
- `governance/agent-protocol/ai-governance-protocol.v1.1.json`
- `governance/agent-protocol/project-profile.schema.json`
- `governance/agent-protocol/agent-run-result.schema.json`
- `governance/agent-protocol/agent-run-result.example.json`
- `governance/agent-protocol/profiles/gel-tutorial-writer.profile.json`
- `tools/check_ai_governance_protocol.py`
- `check-ai-governance`
- `docs/generated/AI_GOVERNANCE_PROFILE.md`

**Exit conditions**

- Protocol/profile schemas and example validate structurally.
- Semantic checker rejects contradictory STRICT_ACCEPTED and SKIPPED-as-PASS claims.
- GEL profile references only known project gates/components/state and binds the existing authority hierarchy.
- Profile runtimeAuthority=false/metaGovernanceOnly=true and automated tutorial/archive writes remain false.
- check:governance invokes protocol/profile validation and generated docs are current.
- Existing GRI strict acceptance remains the release prerequisite; the protocol itself does not self-promote the candidate.

**Result:** Implemented in v17.7 source candidate; direct protocol/profile check is green. Overall project remains TARGET_ACCEPTANCE_REQUIRED until existing GRI lock/strict blockers are resolved.

## A1 — Rust print parity

**Priority:** P2  
**Status:** complete_strictly_accepted  
**Depends on:** G1

**Scope**

- Reach Python v4.9 print-fallback semantic parity using structured DOM parsing.
- Return Python-compatible header fields, print_text, fields, direct-label projection and Tutorial Type -> Type alias.
- Bind Rust output to 14 oracle-generated public fixtures and a strict/private exact fixture comparator.

**Implementation notes**

- Rust PrintRecord now serializes the Python v4.9 result shape exactly rather than placing header metadata inside fields.
- Only direct row cells establish labels; flattened prose is used only for the fixed tutorial header.
- Fourteen public fixtures were generated by the retained Python v4.9 oracle and are compared as exact serde_json values.
- Private historical print parity passed within strict GRI acceptance: 14 exact Python-v4.9-compatible fixtures.

**Exit conditions**

- Private print fixture parity passes
- No prose-label false positives

## A2 — Rust archiver cutover

**Priority:** P2  
**Status:** complete_strictly_accepted  
**Depends on:** A1, D2, N1

**Scope**

- Replace Python runtime archiver with Rust implementation.
- Transfer canonical schema-v2 local archive writer ownership to the Rust archive component.
- Acquire GEL source data fully before opening the transactional materialization operation.
- Create a missing schema-v2 archive atomically; validate existing archives without in-place migration.
- Expose an explicit local archive sync action in Tutorial Writer without adding GEL tutorial write authority.

**Implementation notes**

- RustArchiver owns production acquisition/orchestration; ArchiveSyncRepository remains crate-private as the write capability.
- Fresh database creation stages a sibling .a2-incomplete file, validates schema v2/FKs, then atomically renames it.
- Summary remains primary and explicit summary blanks remain authoritative; print supplements missing keys only.
- Historical teacher identity is recovered from validated edit forms when available.
- Unique timestamp print-only records may establish proven_per_tutorial authority; same-timestamp collisions remain group-owned and fail closed.
- Python v4.9 is retained only as historical/reference parity oracle after cutover.
- A2 structural/behavioral/private acceptance passed within strict GRI acceptance; later source changes do not retroactively alter that baseline result.

**Exit conditions**

- Strict archive release gate passes
- Ownership docs updated in same change
- Python oracle status becomes historical/reference

## W1 — Submission verification

**Priority:** gated  
**Status:** complete_strictly_accepted  
**Depends on:** C4, N2, UI1

**Scope**

- Introduce separately gated POST transport.
- Submit only under explicit manual test flow.
- Re-fetch tutorial list after POST and identify newly created tutorial ID.
- Targeted archive sync verifies server result.

**Exit conditions**

- Manual controlled write validation passes
- No blind local canonical insert
- Failure leaves draft dirty/retryable

**Result:** Manual controlled write validation passed on 2026-09-03: New (datetime omitted) and Revision (datetime preserved) POSTs verified against live GEL; server readback confirmed identity and timestamp discovery; targeted RustArchiver sync reconciled new record into archive_v2; zero blind local inserts; failures leave active draft dirty/retryable.

## W2 — Production submission

**Priority:** gated  
**Status:** complete_strictly_accepted  
**Depends on:** W1, A2

**Scope**

- Enable production GEL writes behind final release gate.
- Document operational recovery and audit behaviour.

**Exit conditions**

- Strict release gate passes
- Write ownership and failure semantics are current
- No lifecycle deferrals remain

**Result:** Phase W2 production submission strictly accepted on 2026-09-04: all 47 checks PASS (0 SKIP, 0 FAIL); targeted single-student archive reconciliation, live submission transport, and resilient error recovery active; release artifact verified without rebuild (RELEASE_ARTIFACT_VERIFIED).

## Gate policy

Portable gate: Private/live evidence may be an explicit SKIP only where the gate declares it portable.

Strict gate: The same missing private/live dependency is a FAIL when required by the strict release profile.

Live write rule: Automated release gates never perform a GEL write.
