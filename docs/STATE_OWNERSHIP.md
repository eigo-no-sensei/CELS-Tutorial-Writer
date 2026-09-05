# State ownership, writers and invalidation

> Generated from `contracts/state_ownership.json`. The JSON contract is authoritative.

## Global ownership rule

Every canonical state class has exactly one currently permitted writer. External GEL authority and reviewed repository source changes count as explicit writers. Derived state may also have exactly one producing component.

## Archive source-disappearance policy

Archive schema v2 represents current-source presence with source_present/first_seen/last_seen plus archive_sync_runs. A later omission may mark source_present false only after the relevant acquisition scope completes successfully. A2 full syncs with partial auxiliary summary/print/edit evidence preserve prior semantic source evidence for API tutorial keys still observed in the same completed run; failed syncs never invalidate prior presence, and preserved rows are never deleted merely because the source omitted them.

## State matrix

| State | Class | State kind | Legacy source/derived | Canonical | Permitted writer(s) | Current materialization |
| --- | --- | --- | --- | ---: | --- | --- |
| `live_gel_tutorials` | `canonical_external` | `source` | `source` | yes | `gel_server` | external |
| `canonical_tutorial_identity_state` | `canonical_external_observation` | `source` | `source` | yes | `gel_server` | tutorial-list API + normalized archive |
| `repository_contracts` | `canonical_repository` | `source` | `source` | yes | `canonical_contracts` | contracts/*.json + schema/archive_v2.sql |
| `writer_active_draft` | `ephemeral_application_owned_draft_container` | `source` | `derived` | no | `writer_tauri_app_service` | Rust LoadedTutorialDraft in writer-ui AppState; dirty status is derived from base != current; stale_source status is derived from session loss or source drift. |
| `development_plan_source` | `master_spec_source` | `source` | `source` | yes | `reviewed_repository_change` | development_plan.json |
| `generated_contract_projections` | `derived_repository` | `projection` | `derived` | no | `contract_tooling` | gel-core/src/gel_fields.rs + docs/generated contract docs |
| `generated_governance_docs` | `derived_repository` | `projection` | `derived` | no | `governance_tooling` | docs/generated + docs/components + architecture/ownership/release docs |
| `normalized_local_archive` | `canonical_local` | `source` | `derived_from_external_source` | yes | `rust_archive_sync_repository` | Schema-v2 SQLite gel-new-v2.db (GEL_ARCHIVE_DB override; Windows default beside executable, non-Windows project-root default). Missing DB may be atomically created by RustArchiver. |
| `archive_v2_candidate_database` | `derived_migration_candidate` | `derived` | `derived_from_canonical_local_archive_or_empty_schema` | no | `archive_schema_migrator`, `rust_archive_sync_repository` | Explicit test/migration destination created by archive schema tooling or test setup. |
| `archive_reconciliation_metadata` | `canonical_local_diagnostic` | `evidence` | `derived_from_external_source` | yes | `rust_archive_sync_repository` | Schema-v2 tutorial_collision_* and tutorial_state_associations tables. |
| `private_fixtures` | `private_test_evidence` | `evidence` | `captured_source` | no | `fixture_capture` | fixtures-private/ by default; an external private root may be supplied via GEL_PRIVATE_FIXTURES_DIR for release validation. |
| `authenticated_gel_session` | `ephemeral_runtime_capability` | `derived` | `derived_from_external_authentication` | no | `rust_gel_session` | Private reqwest client cookie store plus authenticated flag; no serialization/debug export. |
| `gel_api_json` | `ephemeral_source` | `source` | `source` | no | `gel_server`, `rust_gel_session` | In-memory serde_json::Value returned by fixed N1 GET methods. |
| `gel_summary_html` | `ephemeral_source` | `source` | `source` | no | `gel_server`, `fixture_capture`, `rust_gel_session` | HTTP response/private fixture |
| `gel_edit_html` | `ephemeral_source` | `source` | `source` | no | `gel_server`, `fixture_capture`, `rust_gel_session` | HTTP response/private fixture |
| `gel_new_form_html` | `ephemeral_external_source_snapshot` | `source` | `source_snapshot` | no | `rust_gel_session` | Authenticated GET response from /study/tutorials/add/{student_uid}/0/{ttype_raw}; no raw HTML persistence. |
| `gel_print_html` | `ephemeral_source` | `source` | `source` | no | `gel_server`, `fixture_capture`, `rust_gel_session` | HTTP response/private fixture |
| `parsed_summary_state` | `ephemeral_derived` | `derived` | `derived` | no | `rust_summary_parser` | Rust memory |
| `parsed_edit_form_state` | `ephemeral_derived` | `derived` | `derived` | no | `rust_edit_form_parser` | Rust memory |
| `validated_edit_form_state` | `ephemeral_validated_derived` | `derived` | `derived` | no | `rust_edit_form_validator` | Rust memory |
| `validated_new_tutorial_form_state` | `ephemeral_validated_source_derived` | `derived` | `derived_from_external_source` | no | `rust_new_tutorial_form_parser` | Rust ValidatedNewTutorialForm with opaque ValidatedNewFormTeacher; no tutorial_id/tutorial_ts and no datetime field. |
| `parsed_print_state` | `ephemeral_derived` | `derived` | `derived` | no | `rust_print_parser` | Rust memory |
| `derived_reconciliation_result` | `ephemeral_derived` | `derived` | `derived` | no | `rust_reconciliation` | Rust memory: canonical API identities + group-owned collision states + explicit HistoricalStateAuthority |
| `semantic_form_state` | `ephemeral_editable_derived_with_provenance` | `source` | `derived` | no | `rust_semantic_form` | Rust TutorialFormState + DraftOrigin with no New authoritative created identity before readback, plus UI1c0 field-disposition/structured-validation authority. DraftOrigin::New carries LevelRegressionBaseline; InitialCourseType is derived/mutated only through the Rust teacher_comments adapter. |
| `tutorial_post_payload` | `ephemeral_derived` | `derived` | `derived` | no | `rust_post_mapper` | Rust BTreeMap produced only by origin-specific NewTutorialSubmission/RevisionTutorialSubmission builders in rust_post_mapper; no network authority |
| `fixture_comparison_reports` | `derived_test_evidence` | `evidence` | `derived` | no | `rust_fixture_tooling` | stdout/optional JSON report |
| `offline_post_round_trip_report` | `ephemeral_test_evidence` | `evidence` | `derived` | no | `rust_fixture_tooling` | Rust checker stdout/process result; no persistent runtime state |
| `archive_repository_read_models` | `ephemeral_derived_read_model` | `projection` | `derived` | no | `rust_archive_repository` | Rust memory: ArchiveClass/ArchiveClassStudent/ArchiveTutorialListItem/ArchiveRevisionAvailability |
| `n2_playwright_private_evidence` | `private_derived_test_evidence` | `evidence` | `derived` | no | `n2_playwright_evidence_harness` | evidence-private/n2-playwright/*.json generated by the temporary N2-PW1 harness |
| `writer_ui_view_models` | `ephemeral_derived_presentation_model` | `projection` | `derived` | no | `writer_tauri_app_service` | Serde DTOs returned by ui1_* commands, including DraftView.formContract and structured DraftValidationIssue errors. Aims assistance projects unavailable until curated content is explicitly contracted. |
| `writer_ui_presentation_state` | `ephemeral_frontend_presentation_state` | `projection` | `derived` | no | `writer_react_ui` | React component state only; never canonical semantic/tutorial state. |
| `dependency_manifest_source` | `canonical_repository_build_input` | `source` | `source` | yes | `reviewed_repository_change` | Cargo.toml + gel-core/Cargo.toml + writer-ui/src-tauri/Cargo.toml + writer-ui/package.json |
| `dependency_lock_state` | `canonical_repository_dependency_decision` | `decision` | `source` | yes | `dependency_lock_tooling` | Cargo.lock + writer-ui/package-lock.json |
| `dependency_lock_manifest` | `derived_release_identity` | `derived` | `derived` | no | `dependency_lock_tooling` | governance/dependency-lock-manifest.json |
| `current_state_projection` | `governance_projection` | `projection` | `derived` | no | `current_state_tooling` | governance/current-state.json + docs/generated/CURRENT_STATE.md |
| `release_gate_evidence` | `release_acceptance_evidence` | `evidence` | `derived` | no | `release_artifact_tooling` | external evidence store/<run-id>/strict-result.json |
| `distribution_manifest` | `distribution_evidence` | `evidence` | `derived` | no | `release_artifact_tooling` | release-manifest.json + checksums.sha256 inside staged archive |
| `release_artifact_receipt` | `release_artifact_evidence` | `evidence` | `derived` | no | `release_artifact_tooling` | <release.zip>.receipt.json |
| `ci_verification_evidence` | `continuous_verification_evidence` | `evidence` | `derived` | no | `continuous_enforcement` | CI run result / PORTABLE_GOVERNANCE_PASS or STRUCTURAL_PASS_WITH_SKIPS |
| `agent_governance_protocol_decision` | `canonical_repository_meta_governance_decision` | `decision` | `source` | yes | `reviewed_repository_change` | governance/agent-protocol/ai-governance-protocol.v1.1.json plus its protocol/project/run-result schemas. |
| `agent_governance_project_profile` | `canonical_repository_project_meta_governance_decision` | `decision` | `source` | yes | `reviewed_repository_change` | governance/agent-protocol/profiles/gel-tutorial-writer.profile.json |
| `harper_user_dictionary` | `canonical_local_preference` | `source` | `source` | yes | `harper_dictionary_repository` | harper-dictionary.json beside resolved archive by default; GEL_HARPER_DICTIONARY override; schema_version=1. |
| `harper_check_result` | `ephemeral_runtime_derived` | `derived` | `derived` | no | `writer_harper_service` | HarperCheckDto returned through Tauri; never persisted. |
| `harper_disabled_rules` | `ephemeral_runtime_derived` | `derived` | `derived` | no | `writer_react_ui` | Set<string> in writer-ui/src/App.tsx; passed to ui1_harper_check through harperCheck(field, text, disabledRules, suppressedKinds). |
| `harper_ignored_findings` | `ephemeral_runtime_derived` | `derived` | `derived` | no | `writer_react_ui` | Set<string> in writer-ui/src/App.tsx; passed to HarperFieldAssistant as ignoredFindingKeys. |
| `live_submission_response` | `ephemeral_runtime_response` | `source` | `source` | no | `live_submission_transport` | Rust LiveSubmissionReceipt in process memory. |

## Retention and invalidation

### `live_gel_tutorials`

**Retention:** Owned externally by GEL. Created or updated on the server via live_submission_transport during Phase W2; local code never deletes live tutorial records.

**Invalidation:** Any GEL change makes corresponding local source snapshots potentially stale until reacquired.

### `canonical_tutorial_identity_state`

**Retention:** tutorial_id observations are preserved in archive history.

**Invalidation:** A fresh tutorial-list fetch supersedes previous current-source observation but does not delete archived historical identity.

### `repository_contracts`

**Retention:** Version-controlled indefinitely.

**Invalidation:** Contract edits immediately invalidate dependent generated artifacts and any contradictory lower-authority documentation.

### `writer_active_draft`

**Retention:** Process memory only. Holds immutable base semantic state plus current semantic state returned by rust_semantic_form; no persistent tutorial drafts in UI1.

**Invalidation:** Discard/logout/confirmed window close/process exit removes the draft. Successful submission transitions draft to cleared/unloaded upon post-submit readback and targeted archive sync. Failed submission retains draft as dirty and retryable. Session expiry (HTTP 401/403 or login redirect) or latest tutorial remote drift transitions active draft to stale_source.

### `development_plan_source`

**Retention:** Version-controlled; phase status updated in same change as phase completion.

**Invalidation:** Plan change invalidates generated docs/DEVELOPMENT_PLAN.md and documentation index.

### `generated_contract_projections`

**Retention:** Regenerable; checked into repository for review/build convenience.

**Invalidation:** Any input contract hash change makes projection stale and release gate fails until regenerated.

### `generated_governance_docs`

**Retention:** Regenerable; checked into repository.

**Invalidation:** Governance contract or development plan change makes docs stale and check:governance fails.

### `normalized_local_archive`

**Retention:** Append/preserve schema-v2 historical tutorials. RustArchiver is the A2 production orchestrator and ArchiveSyncRepository is the sole canonical local SQLite write capability. Preserved source-absent history is never deleted merely because GEL omits it.

**Invalidation:** Fresh authoritative GEL acquisition may upgrade/reconcile state. Fully evidenced successful Rust full syncs may mark unseen source rows source_present=false through a completed archive_sync_run. When auxiliary summary/print/edit acquisition is partial, A2 preserves prior semantic source evidence for still-observed API tutorial keys while invalidating truly disappeared identities; targeted/failed syncs never infer broader absence. Collision ambiguity remains fail-closed.

### `archive_v2_candidate_database`

**Retention:** Disposable non-canonical schema-v2 migration/test database. Legacy migration always writes a separate destination and preserves the source archive unchanged; A2 may also use candidate databases for isolated migration/repository/release testing.

**Invalidation:** Executable schema/repository contract change invalidates prior candidates. Candidate state never automatically replaces the canonical local archive.

### `archive_reconciliation_metadata`

**Retention:** Preserve collision groups, candidate source states and governed per-ID/group authority in schema v2. Positional API-ID↔state pairing is not authoritative and must never establish per-tutorial ownership.

**Invalidation:** Recomputed by successful Rust archive sync when external identity/state evidence changes; ambiguity cannot be silently promoted without governed proof.

### `private_fixtures`

**Retention:** Private/Git-ignored. Recapture replaces local evidence only; promotion to repository evidence is separate reviewed change.

**Invalidation:** Recapture invalidates old fixture comparison reports and requires strict parity rerun.

### `authenticated_gel_session`

**Retention:** Process memory only. Credentials are never retained as project state; cookies remain private inside the session client and disappear with the session.

**Invalidation:** Any 401/403, detected Learn2 login page/redirect, failed verification or process/session disposal invalidates authenticated capability.

### `gel_api_json`

**Retention:** Ephemeral runtime response only. Student roster/profile values are privacy-filtered before leaving rust_gel_session; raw email-like fields are not retained.

**Invalidation:** A new successful GET replaces the runtime snapshot; authentication/source failure yields no replacement state.

### `gel_summary_html`

**Retention:** Ephemeral at runtime; optionally preserved only in private fixtures.

**Invalidation:** New fetch replaces runtime snapshot.

### `gel_edit_html`

**Retention:** Ephemeral at runtime; optionally preserved only in private fixtures.

**Invalidation:** New fetch replaces runtime snapshot.

### `gel_new_form_html`

**Retention:** Process memory only. New-form HTML is transient acquisition input and is never persisted by the production Rust path.

**Invalidation:** Authentication/session loss, refetch, or source-form change invalidates the snapshot. It is never reused as authority after reauthentication.

### `gel_print_html`

**Retention:** Ephemeral at runtime; optionally preserved only in private fixtures.

**Invalidation:** New fetch replaces runtime snapshot.

### `parsed_summary_state`

**Retention:** Not canonical; regenerate from source.

**Invalidation:** Invalid immediately when source HTML or parsing contract changes.

### `parsed_edit_form_state`

**Retention:** Not canonical; regenerate from source.

**Invalidation:** Invalid immediately when source HTML or parsing contract changes; semantic code must not consume this raw state directly.

### `validated_edit_form_state`

**Retention:** Not canonical; regenerate from raw parsed form and current contracts.

**Invalidation:** Invalid immediately when source HTML, raw parser behaviour, or GEL field/applicability validation contract changes.

### `validated_new_tutorial_form_state`

**Retention:** Ephemeral immutable New-form source authority. Stores normalized validated control state, default date, opaque teacher authority and deterministic fingerprint; never raw HTML, teacher label or GEL created identity.

**Invalidation:** Authentication/session loss invalidates teacher/form authority; a refetched form fingerprint change replaces it. A changed latest tutorial separately stales any semantic draft prepopulation source.

### `parsed_print_state`

**Retention:** Not canonical; regenerate from source.

**Invalidation:** Invalid immediately when source HTML or parser changes.

### `derived_reconciliation_result`

**Retention:** Not canonical until a future repository explicitly persists governed identity/state/association data. Collision candidate states remain group-owned in memory.

**Invalidation:** Identity/source-state input or reconciliation-authority contract change invalidates result.

### `semantic_form_state`

**Retention:** Ephemeral. Editable semantic values are the sole writable draft representation; immutable source identity/teacher authority and source fidelity are provenance. New DraftOrigin also carries a non-writable same-role CEFR regression baseline derived from its N2c latest-source snapshot. Initial course type is a Rust semantic adapter over Initial teacher_comments storage; unknown legacy text is preserved losslessly.

**Invalidation:** Any semantic edit invalidates a derived POST payload. Revision source/archive/authority change requires reconstruction. For New, authentication loss invalidates fetched teacher authority and a changed latest tutorial invalidates both N2c prepopulation and its CEFR regression baseline; rebuild/reconcile rather than silently rebind.

### `tutorial_post_payload`

**Retention:** Ephemeral derived payload produced by rust_post_mapper, consumed by live_submission_transport for production GEL submission under Phase W2. New payloads structurally omit datetime; Revision payloads carry exact source tutorial_ts. Teacher attribution is inherited from immutable semantic origin authority. Payloads are never canonical evidence.

**Invalidation:** Any semantic edit, origin/source authority change, authentication invalidation of a New-form source, or semantic/round-trip contract change invalidates a built payload. New datetime presence, Revision datetime mismatch, teacher-authority mismatch, or C4 exact-map failure blocks later networking.

### `fixture_comparison_reports`

**Retention:** Regenerable test evidence.

**Invalidation:** Fixture/parser/comparator change invalidates report.

### `offline_post_round_trip_report`

**Retention:** Ephemeral C4 diagnostic evidence. Regenerate from private archive/edit fixtures and current contracts; do not promote payload data to canonical history.

**Invalidation:** Any private fixture, semantic constructor, POST mapper, GEL field contract, absent authority rule, or offline round-trip contract change invalidates the report.

### `archive_repository_read_models`

**Retention:** Ephemeral typed projections only; regenerate from archive v2. ArchivedTutorial is emitted only for governed source-present revision state.

**Invalidation:** Any source archive row, source-presence, authority association, schema or repository contract change invalidates previously loaded models.

### `n2_playwright_private_evidence`

**Retention:** Gitignored local evidence only. Persist aliases/booleans/counts/control topology/classifications/student-free hashes and sanitized failure categories; never credentials, cookies, storage state, raw HTML, raw POST bodies, student identity, teacher names or raw teacher IDs.

**Invalidation:** Any GEL form/client drift, PW1 contract change, field contract change or harness change invalidates prior PW1 evidence; rerun zero-write capture. Historical evidence is not silently superseded by a live contradiction.

### `writer_ui_view_models`

**Retention:** Ephemeral Tauri command results only. Safe semantic projections omit raw GEL field IDs, datetime/timestamps and teacher IDs from draft editing authority and include UI1c Rust-owned field rules/option domains plus InitialCourseType view state.

**Invalidation:** Any underlying archive/session/draft change invalidates the corresponding view model; frontend must request/refetch rather than treating it as authority.

### `writer_ui_presentation_state`

**Retention:** React process memory only; class/student selection, filters, busy/error state and transient password input. No localStorage/sessionStorage persistence.

**Invalidation:** Navigation, logout, app close or backend view refresh replaces presentation state. Password state is cleared after every login attempt.

### `dependency_manifest_source`

**Retention:** Version-controlled Cargo.toml workspace/crate manifests and writer-ui/package.json. Dependency edits are reviewed source changes.

**Invalidation:** Any dependency declaration or workspace membership change invalidates dependency locks, lock manifest, current-state projection and release identity.

### `dependency_lock_state`

**Retention:** Cargo.lock and writer-ui/package-lock.json are version-controlled decision state and changed only with explicit dependency/workspace changes. Missing locks remain missing rather than being fabricated; a portable LOCK_GENERATOR_UNAVAILABLE exception is evidence about host capability, not replacement decision state.

**Invalidation:** Any dependency-manifest change requires regeneration. Missing locks fail strict validation; portable validation may explicitly SKIP only when the corresponding generator executable is objectively unavailable under dependency_lock_policy.

### `dependency_lock_manifest`

**Retention:** Regenerable repository projection containing manifest/lock hashes and COMPLETE/INCOMPLETE status. Host tool availability is intentionally not persisted here; tool-unavailable exceptions are run evidence.

**Invalidation:** Any Cargo.toml, package.json, Cargo.lock or package-lock.json byte change invalidates the manifest.

### `current_state_projection`

**Retention:** Regenerable version-controlled snapshot of active phase/gate/lock/release status. It is never runtime authority.

**Invalidation:** Any referenced active contract, development-plan, release-gate, state-ownership or lock-manifest change invalidates the projection.

### `release_gate_evidence`

**Retention:** Immutable per-run JSON retained outside the governed source tree; a new run creates new evidence rather than overwriting accepted evidence.

**Invalidation:** Never edited in place. Source/lock/toolchain changes require a new strict run and new evidence identity.

### `distribution_manifest`

**Retention:** Embedded in each packaged candidate/release with exact distributed source-file hashes and bound acceptance identity.

**Invalidation:** Any distributed byte or accepted source/lock/evidence identity change requires a new manifest and package.

### `release_artifact_receipt`

**Retention:** Sidecar receipt for final archive bytes; immutable once RELEASE_ARTIFACT_VERIFIED.

**Invalidation:** Any archive-byte change creates a different artifact identity and requires a new receipt.

### `ci_verification_evidence`

**Retention:** CI-provider run logs/status retained according to repository/provider policy; never promoted automatically to strict acceptance.

**Invalidation:** Each source change produces new CI evidence. CI evidence cannot replace target-host/private strict evidence.

### `agent_governance_protocol_decision`

**Retention:** Version-controlled generic AI Governance Protocol v1.1 schemas/instance under governance/agent-protocol. It governs agent workflow/claims only and is never GEL runtime or domain authority.

**Invalidation:** A reviewed protocol-version or schema change invalidates the GEL profile validation, generated current-state protocol identity and governance evidence until revalidated.

### `agent_governance_project_profile`

**Retention:** Version-controlled GEL project profile binding the generic protocol to existing GEL contracts, gate profiles, subject identity and side-effect policies. runtimeAuthority=false and metaGovernanceOnly=true are mandatory.

**Invalidation:** Any referenced contract/gate/component/state ID or protocol-version change invalidates profile conformance until check:governance passes again.

### `harper_user_dictionary`

**Retention:** Writer-local durable preference only. Must not contain credentials, cookies/session state, student identifiers or tutorial text wholesale. Versioned JSON is recoverable and retained until explicit user removal.

**Invalidation:** Explicit add/remove replaces the current dictionary. Future schema versions fail closed. Failed atomic writes leave prior canonical bytes authoritative.

### `harper_check_result`

**Retention:** Process-memory assistance only. Each result carries the exact source snapshot and is discarded on text change or process disposal.

**Invalidation:** Any source-text change, dictionary mutation or request-id change invalidates prior findings; stale UI results are not applicable to newer text.

### `harper_disabled_rules`

**Retention:** Session-only rule suppression state hoisted to the App root. Never persisted; cleared on process disposal. Passed to ui1_harper_check as disabled_rules so a disabled rule does not run for any field until the session resets.

**Invalidation:** Session restart clears the set. Adding a rule removes its findings on the next debounced lint run.

### `harper_ignored_findings`

**Retention:** Session-only finding skip set hoisted to the App root. Never persisted; cleared on process disposal. Keyed by field + rule + span + kind + excerpt + message so a skipped finding disappears instantly from the visible findings without waiting for a re-lint.

**Invalidation:** Session restart clears the set. The visibleFindings useMemo recomputes instantly on skip.

### `live_submission_response`

**Retention:** Process memory only. Transient HTTP response status and redirect headers from tutorial process submission.

**Invalidation:** Discarded immediately after readback discovery and targeted archive reconciliation.
