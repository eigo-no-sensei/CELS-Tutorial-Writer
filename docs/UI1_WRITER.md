# UI1 — Tutorial Writer

UI1 is an integration phase. The `ui1-initial` baseline is strictly accepted at `PASS=22 SKIP=0 FAIL=0`, and the selected A+D hybrid/history-focus baseline is strictly accepted at `PASS=23 SKIP=0 FAIL=0`. UI1c0 semantic authority is implemented. Before UI1c1 spreads further, the current candidate must satisfy **GRI — Governance and Reproducible Identity**.

## Authority

Executable contracts and tests remain authoritative. React is presentation-only. `writer_tauri_app_service` owns one ephemeral active draft container and safe UI projections, while semantic mutations, field applicability, option domains, Initial course-type storage semantics, structured validation and New level-regression policy belong to `rust_semantic_form`.

The Tauri command surface contains no tutorial POST/create/revise/delete command, no generic HTTP command, no teacher reassignment command and no raw GEL field/payload command. The sole governed local archive mutation trigger is `ui1_sync_archive`, which delegates to `RustArchiver`; React never receives raw SQLite/write capability.

GRI changes release control, not tutorial runtime authority. Dependency locks are governed decision state; `governance/current-state.json` is generated projection state only; strict/CI/package outputs are evidence state and cannot self-promote into runtime authority.

## Accepted A+D hybrid

Browse mode uses a focused 34/66 two-pane layout. The left student grid contains only **Student / Course / Attendance / Last tutorial**; the right pane contains selected-student context, explicit New Standard/Initial/Final actions and newest-first tutorial history. `School` and database/internal identifiers are not normal visible columns.

Write mode is editor-dominant with a compact, collapsible student-context pane. Tutorial history is **Date / Type / Level / Teacher**. Revision eligibility remains backend-enforced but is not a routine visible column; exceptional blocked Revision attempts produce contextual errors.

## UI1c0 semantic-form closure

UI1c0 establishes the executable boundary before complete Initial/Standard/Final form rendering spreads:

- `TutorialSemanticField` enumerates the canonical UI1c semantic field vocabulary.
- Every field is classified by tutorial type as `editable`, `read_only`, `hidden_preserved` or `inapplicable`.
- CEFR, assessment and Initial course-type options are Rust-owned and projected in `DraftFormContractView`; React owns no canonical option arrays.
- Initial course type is an explicit `InitialCourseType` semantic concept with exact `HSP`, `G21` and `G15` values. Storage remains GEL-compatible through Initial `teacher_comments`, but React never parses or composes that storage representation.
- Unknown nonblank historical Initial teacher-comment content is represented as `UnrecognizedPreserved` and survives unrelated edits until an explicit course-type replacement.
- Existing Initial exam fields remain `hidden_preserved` and have no UI1c typed edit target.
- `DraftValidationIssue` is the stable structured error DTO: code, semantic field, severity, message and optional prior/candidate values. React may display the message but must not parse text to infer field authority.
- Aims assistance is explicitly **absent** in UI1c0 because no curated/versioned preset source has been authorized. No preset/hotlist UI may be rendered yet.
- New drafts carry a Rust-owned `LevelRegressionBaseline` derived from N2c's latest authoritative source. Regression is checked only for the same canonical semantic field-role; Initial/current promotion, cross-skill comparison and Revision-vs-later-history comparison are forbidden.

UI1c0 adds no persistence and no GEL/archive write authority.

## GRI release-control boundary

The current release identity is governed by `contracts/release_identity.json`, `contracts/verification_semantics.json`, `contracts/release_gate.json` and state/component ownership.

- Rust release identity is one root workspace and one `Cargo.lock`; tests/clippy use `--locked`.
- Frontend dependency identity is `writer-ui/package-lock.json`; release/CI install with `npm ci`.
- `governance/dependency-lock-manifest.json` is a derived lock projection.
- `governance/current-state.json` and `docs/generated/CURRENT_STATE.md` are generated status projections, not runtime authority.
- High-value write/state/release invariants require behavioral/acceptance evidence, not text-presence checks alone.
- Portable CI may report structural results only; it never claims `STRICT_ACCEPTED` or `RELEASE_ARTIFACT_VERIFIED`.
- Strict GRI evidence must be written outside the source tree and binds exact source fingerprint, lock identity and toolchain identity.
- Release packaging accepts only matching `STRICT_ACCEPTED` evidence, performs no rebuild, embeds an exact checksum manifest and verifies the final archive bytes.

## Field-disposition highlights

Common Date and Overall Level are editable; Teacher is read-only. Standard owns Absent, current skill levels/Reading, seven assessments, Aims and Teacher Comments. Initial owns the four Initial skill levels plus `InitialCourseType`; its legacy teacher-comment storage and exam fields are hidden-preserved. Final owns paired Initial/current four-skill levels, Reading, Teacher Comments and Additional Comments.

The canonical complete matrix is `contracts/ui1c_semantic_forms.json`.

## Read-model authority

Course start/end and attendance are projected from existing D2 archive read models. Last-tutorial display is derived by the Rust application service from the first item in `ArchiveRepository::list_tutorials_for_student`, which is already newest-first. React only formats these safe DTO values; missing values remain unknown rather than inferred.

## Current UI1 flow

- Archive navigation opens an existing schema-v2 archive through `ArchiveRepository::open_read_only` using `GEL_ARCHIVE_DB`.
- GEL credentials are transient and the authenticated session remains Rust-owned by `GelSession`.
- New opening combines latest authoritative archive history, a live N2b validated New form, and N2c `build_new_form_state`.
- Revision opening requires D2 revision authority plus the live C1-validated historical edit form and C2 semantic construction.
- React receives safe semantic view models and sends only `TutorialDraftEdit` variants.
- Candidate edits are validated in `gel-core`; rejected edits do not alter the current draft.
- Tutorial drafts are process-memory only.

## Acceptance history and current gate

Historical accepted baselines:

```text
ui1-initial: PASS=22 SKIP=0 FAIL=0
ui1-hybrid:  PASS=23 SKIP=0 FAIL=0
```

The historical v17.5 UI1c0 gate contained 26 checks. GRI then established the reproducible workspace baseline and was strictly accepted at **PASS=39 / SKIP=0 / FAIL=0**. UI1c5 now extends that accepted baseline with two dedicated integration checks, so `ui1c5` is the current 41-check release-acceptance scope.

First materialize the real dependency locks on a target host:

```fish
python tools/generate_dependency_lockfiles.py
```

Then strict acceptance requires an external evidence path:

```fish
python tools/release_gate.py \
  --profile strict \
  --scope ui1c5 \
  --evidence-out /evidence/gel/<run-id>/ui1c5-strict-result.json
```

Target semantics are **all checks PASS, SKIP=0, FAIL=0, `TARGET STATUS: STRICT_ACCEPTED`**.

## Next UI1 stages

UI1c1–UI1c4 are implemented and their GRI prerequisite is satisfied. UI1c5 integrated cross-form validation/release is implemented and now awaits strict `ui1c5` acceptance for the changed source identity. UI1d remains Harper plus the separately governed persistent dictionary. UI1e remains native dirty-close, stale/session-expiry UX, mocked E2E and final UI1 release hardening.


## UI1c1 common editor framework

UI1c1 is implemented pending strict acceptance. React now uses reusable disposition-aware semantic controls for the existing foundation surface only: Date, Overall Level, read-only Teacher, Standard Absent, and applicable Teacher Comments. Option values and text limits remain Rust-projected. `DraftValidationIssue` remains a structured DTO and React does not parse its message to infer field authority. Complete Standard, Initial and Final sections remain UI1c2–UI1c4. No GEL tutorial or archive write authority is added.


## UI1c2–UI1c4 complete semantic forms

Implemented pending strict acceptance. Standard renders current Speaking/Use of English/Writing/Listening, Reading, seven Rust-projected assessments, direct Aims and applicable Teacher Comments. Initial renders the four Initial-role levels and the Rust-projected Initial course-type adapter; unknown historical course metadata remains preserved until explicit replacement and React never parses teacher-comment storage. Final renders paired Initial/current four-skill levels, Reading, Teacher Comments and Additional Comments. Every control still consumes Rust field dispositions/domains and emits only typed `TutorialDraftEdit`; hidden-preserved/inapplicable fields render nothing. No GEL/archive write capability is added. UI1c5 integrated semantic-form acceptance is implemented pending strict `ui1c5` acceptance.
