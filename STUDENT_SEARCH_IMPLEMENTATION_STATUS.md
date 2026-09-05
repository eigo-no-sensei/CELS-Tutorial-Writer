# STUDENT_SEARCH_PLAN Implementation Status & Remaining Work

## Executive Summary

**Implementation Progress: ~15% complete**

Only the core HTML parser (`live_student_search_parser.rs`) exists and compiles successfully. All critical backend integration, Tauri commands, TypeScript layer, React UI, contracts, tests, and governance tools remain unimplemented.

**Critical Path:** The parser cannot be used without `GelSession::search_live_students()` which walks pagination. This blocks all downstream components.

**Contract Compliance Risk:** HIGH - No contract amendments have been made. The plan requires changes to 4 contracts (gel_read_only_session.json, ui1_writer.json, state_ownership.json, archive_repository.json) but none have been updated. UI1f internal gate does not exist.

---

## Current State (as of 2026-09-05)

### ✅ Completed (1 component)

**live_student_search_parser.rs** - Core HTML parser for DataTables responses
- `LiveStudentSearchRow` struct with all required fields ✓
- `LiveStudentSearchInfoFooter` for pagination metadata ✓
- `parse_live_student_search_html()` function ✓
- `parse_data_tables_info_footer()` helper ✓
- Date filtering via `passes_date_filter()` method ✓
- Email stripping and privacy handling ✓
- Tutor cell parsing (three shapes: date+name, absent, never) ✓
- Spaced text content extraction to prevent glue bugs ✓
- Unit tests for footer parsing, tutor cells, email stripping ✓
- **Status:** Compiles with zero warnings ✓

### ❌ Missing Components (10 major areas, ~40 sub-tasks)

#### 1. GelSession Integration (§5.2) - BLOCKING
**File:** `gel-core/src/gel_session.rs`
- [ ] `search_live_students(&mut self, term: &str) -> Result<LiveStudentSearchResult>`
- [ ] `LiveStudentSearchResult` struct with fields: `rows`, `total_entries`, `info_footer_raw`, `pages_fetched`
- [ ] Pagination walker logic (POST with `length=100`, `start=<offset>`)
- [ ] MAX_PAGES safety cap (20 pages = 2000 rows)
- [ ] Privacy: call `strip_student_sensitive_fields` on each row
- [ ] Authentication check before search
- [ ] Login page detection
- [ ] Throttle between requests

**Dependencies:** Requires `live_student_search_parser` types (✓ exists)
**Blocks:** Tauri commands, all UI functionality

#### 2. gel-core Re-exports (§5.3)
**File:** `gel-core/src/lib.rs`
- [ ] Add `pub use live_student_search_parser::{parse_live_student_search_html, parse_data_tables_info_footer, LiveStudentSearchRow, LiveStudentSearchInfoFooter, LiveStudentSearchParseReport}`
- [ ] Export `LiveStudentSearchResult` from gel_session module

**Current state:** Module declared but not re-exported (line 12 shows `pub mod live_student_search_parser;` but no `pub use`)

#### 3. ArchiveRepository Method (§6.2 step 4a) - CRITICAL FOR V1.0.2
**File:** `gel-core/src/archive_repository.rs`
- [ ] `student_exists(&self, student_uid: i64) -> Result<bool>`
- [ ] SQL: `SELECT 1 FROM students WHERE uid = ?1`
- [ ] Used by `ui1_student_in_archive` to gate on-boarding decision

**Why critical:** Without this, cannot distinguish Case A (in-archive, zero tutorials) from Case B (never-synced). Would trigger wasteful sync loop on every click of tutorial-less student.

#### 4. Tauri Commands (§5.4)
**File:** `writer-ui/src-tauri/src/lib.rs`
- [ ] `LiveStudentSearchRowView` struct (camelCase for TypeScript)
- [ ] `LiveStudentSearchResponse` struct with `capture_rate` field
- [ ] `ui1_search_live_students()` command
  - Accepts: `term`, `course_start_before`, `course_end_after`
  - Applies date filter defaults (tomorrow, today)
  - Computes `capture_rate = rows.len() / total_entries`
  - Returns pre-filter row count for capture_rate calculation
- [ ] `ui1_student_in_archive(student_id: i64) -> Result<bool, String>` command
- [ ] Register both commands in `tauri::generate_handler![]`
- [ ] Helper: `parse_optional_iso_date()` for yyyy-MM-dd parsing
- [ ] Helper: `today_and_tomorrow_utc()` for defaults

**Dependencies:** Requires GelSession::search_live_students (❌), ArchiveRepository::student_exists (❌)
**Blocks:** TypeScript API, React UI

#### 5. TypeScript Types (§5.5)
**File:** `writer-ui/src/types.ts`
- [ ] `LiveStudentSearchRowView` interface
- [ ] `LiveStudentSearchResponse` interface with `captureRate`
- [ ] Proper camelCase field naming (`studentUid`, `courseStart`, etc.)

#### 6. TypeScript API Wrapper (§5.6)
**File:** `writer-ui/src/api.ts`
- [ ] `searchLiveStudents(term, courseStartBefore, courseEndAfter)`
- [ ] `studentInArchive(studentId: number)`
- [ ] Empty string normalization to null

**Dependencies:** Requires TypeScript types (❌)
**Blocks:** React UI

#### 7. React UI Components (§6)
**Files:** 
- `writer-ui/src/components/LiveStudentSearchPane.tsx` (NEW)
- `writer-ui/src/App.tsx` (MODIFY)
- `writer-ui/src/viewFormat.ts` (ADD helpers)
- `writer-ui/src/styles/app.css` (ADD styles)

**LiveStudentSearchPane requirements:**
- [ ] Search input + Search button (Enter key support)
- [ ] Two date pickers: "Course start before", "Course end after"
- [ ] Default values: tomorrow, today (computed client-side or passed from Rust)
- [ ] AG Grid with full column projection (8 columns):
  - Code, Name, Created, Course start, Course end, Tutorial end, Tutor, Tutor date, Absent
- [ ] Governance badge showing captureRate ("100% captured (N of N) in P page(s)")
- [ ] `onSelect` prop (NOT `onOnboard` - separation of selection from action per v1.0.2)
- [ ] Row click calls `onSelect(row)` without invoking draft operations
- [ ] Busy state during query
- [ ] Error display

**App.tsx changes:**
- [ ] Remove old `studentSearch` state and inline search input from workspace-toolbar
- [ ] Remove `setStudentSearch("")` from chooseClass and doLogout
- [ ] Replace `<StudentListPane … />` with `<LiveStudentSearchPane … />`
- [ ] Implement `handleSelectFromSearch(row)`:
  - Set `studentId = row.studentUid` for StudentOverview
  - Call `await studentInArchive(studentId)`
  - If false (Case B): trigger on-boarding via Option A (`openNewDraft("standard")` + `discardDraft()`)
  - If true (Case A): just call `listTutorials(studentId)` - NO sync
  - Set `busy=true` during membership check + on-boarding
  - Surface errors via existing `setError` channel
- [ ] Class selector remains but relabelled "Class (optional, tutorial history only)"

**View format helpers:**
- [ ] `formatIsoDate(iso: string | null): string`
- [ ] `formatTimestamp(rfc3339: string | null): string`

**Dependencies:** Requires TypeScript API (❌)
**Blocks:** User-facing functionality, workflow tests

#### 8. Contract Amendments (§4, §8) - GOVERNANCE REQUIREMENT
**Files:**
- [ ] `contracts/gel_read_only_session.json`
  - Add `live_student_search` to `read_surface` array
  - Method: POST, Path: `/administration/students`
  - Add "School-wide student read query" to `network_authority.allowed_post_purposes`
  - Bump `contract_version` from 2 to 3
- [ ] `contracts/ui1_writer.json`
  - Add `ui1_search_live_students` to `initial_command_allowlist`
  - Add `ui1_student_in_archive` to `initial_command_allowlist`
  - Add UI1f entry to `internal_gates` array
  - Verify `layout.school_visible == true`
  - Bump `contract_version` (current: 14 → 15)
- [ ] `contracts/state_ownership.json`
  - Add state class `live_student_search_results` (ephemeral, not persisted)
  - Bump `contract_version` (current: 23 → 24)
- [ ] `contracts/archive_repository.json`
  - Document `student_exists` read-only access pattern
  - Clarify no new write authority

**Why critical:** Contracts are the authoritative specification. Without amendments, the implementation violates the governance model. The check_ui1f_live_search.py tool will fail.

#### 9. Governance Checker (§9.5)
**File:** `tools/check_ui1f_live_search.py` (NEW)
- [ ] Assert gel_read_only_session.json has live_student_search read surface
- [ ] Assert ui1_writer.json has both commands in allowlist
- [ ] Assert UI1f internal gate exists
- [ ] Assert state_ownership.json has new state class
- [ ] Assert LiveStudentSearchResponse struct in Rust (parse source)
- [ ] Assert TypeScript types (parse source)
- [ ] Assert governance badge in LiveStudentSearchPane (parse source)
- [ ] Assert student_exists method in ArchiveRepository (parse source)
- [ ] Assert ui1_student_in_archive command (parse source)
- [ ] Exit 0 only if all assertions pass

**Dependencies:** Requires all implementation artifacts (❌)
**Purpose:** Automated gate enforcement before release

#### 10. Integration Tests (§9.3, §9.6)
**Files:**
- `gel-core/tests/gel_session_search.rs` (NEW)
- `gel-core/tests/ui1e_workflow_behavior.rs` (EXTEND with 5 scenarios)

**Test scenarios:**
- [ ] Multi-page walker test (154 rows = 2 POSTs with start=0, start=100)
- [ ] Empty result test (0 rows, 1 POST, footer "Showing 0 to 0 of 0")
- [ ] Unauthenticated error test (call before login)
- [ ] Login page detection test (mocked transport returns login HTML)
- [ ] Scenario A: New tutorial from search (in-archive student, no sync)
- [ ] Scenario B: Browse historic (in-archive student, no sync)
- [ ] Scenario C: Amend tutorial (in-archive student, no sync)
- [ ] Scenario D: Browse-only on-boarding (never-synced student, sync once)
- [ ] Scenario E: In-archive zero-tutorials regression (NO sync - critical!)
- [ ] capture_rate == 1.0 assertion for non-empty searches

**Dependencies:** Requires fixtures (❌), GelSession method (❌), Tauri commands (❌)
**Purpose:** Prove all five teacher workflows work correctly

#### 11. Fixtures (§9.1)
**Directory:** `gel-core/fixtures/live_student_search/`
- [ ] `raw/anonymized_report_sample.html` (30 rows, footer "Showing 1 to 10 of 30 entries")
- [ ] `raw/anonymized_report_sample_page2.html` (rows 11-30, footer "Showing 11 to 30 of 30")
- [ ] `raw/anonymized_report_sample_empty.html` (no rows, footer "Showing 0 to 0 of 0")
- [ ] `raw/anonymized_report_sample_never.html` (one row, cell 7 = "never")
- [ ] `expected/anonymized_report_sample.json` (typed projection)

**Must include DataTables chrome:**
- `<select name="student-management_length">` with 10/25/50/100 options
- `<div class="dataTables_info" id="student-management_info">`
- `<div class="dataTables_paginate paging_two_button">` with previous/next links

**Dependencies:** None - can be created immediately
**Blocks:** Parser unit tests, integration tests

---

## Implementation Priority Order (Critical Path)

### Phase 1: Backend Foundation (blocks everything else) - ESTIMATED 4-6 HOURS
1. Create HTML fixtures (can parallelize)
2. ArchiveRepository::student_exists() - simple SELECT 1 query
3. GelSession::search_live_students() - pagination walker
4. gel-core lib.rs re-exports

### Phase 2: Tauri IPC Layer - ESTIMATED 2-3 HOURS
5. LiveStudentSearchRowView, LiveStudentSearchResponse structs
6. ui1_search_live_students command with date filtering
7. ui1_student_in_archive command
8. Register in generate_handler![]

### Phase 3: TypeScript Layer - ESTIMATED 1-2 HOURS
9. Type definitions in types.ts
10. API wrappers in api.ts

### Phase 4: React UI - ESTIMATED 3-4 HOURS
11. viewFormat.ts helpers
12. LiveStudentSearchPane.tsx component
13. App.tsx integration (handleSelectFromSearch with archive membership check)
14. CSS styles

### Phase 5: Contracts & Governance - ESTIMATED 1 HOUR
15. Amend 4 contract JSON files
16. Create check_ui1f_live_search.py

### Phase 6: Tests & Verification - ESTIMATED 3-4 HOURS
17. gel_session_search.rs integration tests
18. Extend ui1e_workflow_behavior.rs with 5 scenarios
19. Run all tests, fix failures
20. Run check_ui1f_live_search.py, fix failures

**TOTAL ESTIMATED EFFORT: 14-20 HOURS**

---

## Risk Assessment

| Risk | Severity | Probability | Mitigation | Owner |
|------|----------|-------------|------------|-------|
| Pagination walker misses rows (capture_rate < 1.0) | HIGH | Medium | capture_rate governance signal visible in UI, MAX_PAGES cap, multi-page test scenario | Backend |
| On-boarding triggers for in-archive zero-tutorial student (Case A) | MEDIUM | High without fix | student_exists check BEFORE listTutorials, Scenario E regression test | Full-stack |
| Date filter uses wrong defaults (today/tomorrow computation error) | MEDIUM | Low | Explicit UTC computation in Rust, unit test for defaults | Backend |
| Email leak in name field | HIGH | Low | Double defence: parser strip_student_sensitive_fields, unit test | Backend |
| capture_rate < 1.0 in production undetected | HIGH | Medium | Governance badge always visible, release gate assertion fails build | Governance |
| Double-click on-boarding race condition | LOW | Low | busy flag during student_exists + on-boarding, disable row clicks | Frontend |
| Contract amendments forgotten | HIGH | High without checklist | check_ui1f_live_search.py asserts all 4 contracts, fails if missing | Governance |
| TypeScript/Rust type drift | MEDIUM | Medium | tsc --noEmit after every Rust change, cargo test after every TS change | CI |
| Fixture HTML diverges from production | MEDIUM | Low over time | Capture fresh HTML after any GEL UI change, store in fixtures | Maintenance |

---

## Contract Compliance Evaluation

### Current Contract State vs Plan Requirements

| Contract | Current Version | Required Version | Changes Needed | Status |
|----------|----------------|------------------|----------------|--------|
| gel_read_only_session.json | 2 | 3 | Add live_student_search read surface, allowed_post_purposes | ❌ NOT STARTED |
| ui1_writer.json | 14 | 15 | Add 2 commands to allowlist, add UI1f gate | ❌ NOT STARTED |
| state_ownership.json | 23 | 24 | Add live_student_search_results state class | ❌ NOT STARTED |
| archive_repository.json | N/A | N/A | Document student_exists read access | ❌ NOT STARTED |

### Critical Contract Violations (if implemented without amendments)

1. **Network Authority Violation:** POST to `/administration/students` is not in `allowed_post_purposes`. Current contract only allows login POSTs.

2. **Command Allowlist Violation:** `ui1_search_live_students` and `ui1_student_in_archive` are not in `initial_command_allowlist`. The forbidden_command_capabilities would block these.

3. **State Class Violation:** `live_student_search_results` state class (ephemeral search results) is not defined in state_ownership.json.

4. **Internal Gate Missing:** UI1f gate is not recorded. Cannot mark UI1f as STRICT_ACCEPTED without the gate definition.

**GOVERNANCE RISK:** Implementing without contract amendments would create an undocumented capability that bypasses the governance model. The check_ui1f_live_search.py tool will fail immediately on contract version checks.

---

## Acceptance Criteria (UI1f Internal Gate)

### Must Pass Before UI1f Can Be Marked STRICT_ACCEPTED

1. ✅ Parser compiles and passes unit tests (cargo test --package gel-core live_student_search_parser)
2. ❌ search_live_students walker captures 100% of rows (capture_rate == 1.0 for all non-empty searches)
3. ❌ Both Tauri commands registered and callable from TypeScript (manual test + typecheck)
4. ❌ LiveStudentSearchPane renders with all 8 columns, sortable/filterable
5. ❌ Governance badge shows "100% captured (N of N) in P page(s)" for successful searches
6. ❌ handleSelectFromSearch correctly gates on-boarding on archive membership (Scenario E proves no sync for in-archive zero-tutorial student)
7. ❌ All five workflow scenarios pass (A: New, B: browse, C: amend, D: on-board never-synced, E: in-archive zero-tutorials regression)
8. ❌ check_ui1f_live_search.py exits 0 (all 11 assertions pass)
9. ❌ Contracts amended: gel_read_only_session v3, ui1_writer v15, state_ownership v24, archive_repository documented
10. ❌ STRICT_ACCEPTED status with UI1e baseline preserved (no regression in existing 45 tests)
11. ❌ tsc -p tsconfig.app.json --noEmit passes with zero errors
12. ❌ vite build succeeds
13. ❌ cargo test --package gel-core passes (all existing tests + new search tests)

---

## Recommended Next Steps (Immediate Action Items)

### Today (Priority 1 - Unblocks Everything)
1. **Create HTML fixtures** - Non-blocking, can be done in parallel
   - gel-core/fixtures/live_student_search/raw/*.html
   - Use plan §3.1.1 and §9.1 as templates

2. **Implement ArchiveRepository::student_exists()** - 30 minutes
   - Simple SELECT 1 query
   - Required for v1.0.2 archive-membership gating

3. **Implement GelSession::search_live_students()** - 2-3 hours
   - Pagination walker with length=100, start=<offset>
   - MAX_PAGES cap at 20
   - Call parser, apply privacy stripping
   - Return LiveStudentSearchResult

4. **Add gel-core re-exports** - 10 minutes
   - pub use statements in lib.rs

### Tomorrow (Priority 2 - IPC & Types)
5. **Tauri commands** - 2 hours
   - Both commands + helper functions
   - Register in generate_handler![]

6. **TypeScript layer** - 1 hour
   - Types + API wrappers

### Day 3 (Priority 3 - UI)
7. **React component** - 3 hours
   - LiveStudentSearchPane with all features
   - App.tsx integration with handleSelectFromSearch

### Day 4 (Priority 4 - Governance)
8. **Contract amendments** - 1 hour
   - All 4 JSON files
   - Update versions

9. **Governance checker** - 1 hour
   - check_ui1f_live_search.py

### Day 5 (Priority 5 - Verification)
10. **Integration tests** - 3 hours
    - gel_session_search.rs
    - Extend ui1e_workflow_behavior.rs
    - Run all tests, fix failures

---

## Conclusion

The STUDENT_SEARCH_PLAN implementation is approximately **15% complete**. The parser exists and compiles, but cannot be used without the session-layer walker. All downstream components (Tauri commands, TypeScript, React UI, contracts, tests, governance) remain unimplemented.

**Critical path:** Backend foundation (Phase 1) must be completed first. Nothing else can function without `GelSession::search_live_students()`.

**Highest risk:** Contract compliance. Implementing without amending the 4 contracts would violate the governance model and fail the check_ui1f_live_search.py gate.

**Recommended approach:** Follow the priority order strictly. Do not skip contract amendments. Write tests incrementally as each component is built. Run check_ui1f_live_search.py early and often to catch governance violations before they compound.

**Estimated completion:** 14-20 hours of focused work, assuming no major blockers or requirement changes.
