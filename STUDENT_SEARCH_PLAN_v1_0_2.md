# School-wide student search plan v1.0.2

**Plan ID:** LSS1 — UI1f internal gate
**Status:** Draft, pending strict acceptance
**Date:** 2026-09-05 (v1.0.2 — search-result selection now covers browse + amend, not just new)
**Brief:** School-wide / classless student search — new phase / feature extension over the accepted UI1e source identity.
**Source evidence:**
  - v1.0.0 baseline: `/home/z/my-project/upload/gel_search_report_anonymized.json` (captured 2026-09-04T16:39:10Z, 30-row anonymized response sample from `POST /administration/students` with `search=Rina`)
  - v1.0.1 update: `/home/z/my-project/upload/gel_search_report.json` (captured 2026-09-05T11:39:45Z by `gel_student_search_recon4.js`, 230 rows across 4 searches, `captureRate: 1.0` on every non-empty search — see §3.1.1, §5.2, §5.4)
  - v1.0.2 update: teacher directive — "The student may be enrolled but not currently showing in any class. This is not only for new tutorials but also for browsing historic tutorials and amending tutorials in the same way as for those in a class."
**Codebase baseline:** `gel-rust-bootstrap-v17.16-W2.zip` — UI1e strict acceptance PASS=45 SKIP=0 FAIL=0; RELEASE GATE: PASS.

**What changed in v1.0.1:**
  - §1 Out-of-scope: pagination moved from "open question" to in-scope.
  - §3.1.1 (new): jQuery DataTables rendering evidence — page-size `<select>`, info footer, two-button pager.
  - §3.2: third tutor-cell shape `never` (no tutorials yet) added.
  - §5.1: parser now extracts the DataTables info footer as `LiveStudentSearchInfoFooter { start, end, total, raw }`.
  - §5.2: session method walks the pager server-side via `length=100` + `start=<offset>` POSTs, returning `LiveStudentSearchResult { rows, total_entries, info_footer_raw, pages_fetched }`.
  - §5.4: Tauri command returns `LiveStudentSearchResponse { rows, total_entries, info_footer_raw, pages_fetched, capture_rate }`.
  - §5.5/§5.6: TS types and API wrapper updated for the new response shape.
  - §6.1: React pane adds a `captureRate` governance badge.
  - §9.1/§9.2/§9.3: fixtures and tests updated to cover the footer parser, multi-page walker, and `never` tutor cell.
  - §9.5: governance checker asserts the new `LiveStudentSearchResponse` struct and `captureRate` badge.
  - §9.7: strict exit asserts `capture_rate == 1.0 || capture_rate == None`.
  - §12 risk #1 (pagination) marked RESOLVED; §12 risk #10 (capture_rate as a hard release-gate signal) added.
  - §13 Summary updated.

**What changed in v1.0.2:**
  - §1 In-scope: search-result row click now covers all three teacher actions (New / browse historic / amend), not just New. The row click selects the student for `StudentOverview` exactly as a class-roster row click does today; the teacher then chooses the action from `StudentOverview`.
  - §1 In-scope (refined): archive-membership signal (`ui1_student_in_archive`) added as a required new command — the on-boarding trigger is gated on archive membership, NOT on the tutorial list being empty. Distinguishes Case A (in archive, zero tutorials — do NOT sync) from Case B (not in archive — DO sync).
  - §2 User story: rewritten to lead with "act on a tutorial" (any of three actions) instead of "write a tutorial". Adds an on-boarding precondition paragraph explaining how a never-synced search-selected student is brought into the archive.
  - §4.2: `initial_command_allowlist` now adds TWO commands (`ui1_search_live_students` + `ui1_student_in_archive`).
  - §5.6: API wrapper adds a `studentInArchive` wrapper.
  - §6.1 Props: `onOnboard` renamed to `onSelect` to reflect the new select-don't-act semantics. The pane no longer directly invokes `ui1_open_new_draft`.
  - §6.2 App.tsx: `handleOnboardFromSearch` renamed to `handleSelectFromSearch`. The handler sets `studentId`, calls `ui1_student_in_archive`, and on-boards the student into the archive only if the membership check returns `false` (Option A: `ui1_open_new_draft` + `ui1_discard_draft`; Option B deferred to LSS3). Step 4a adds the `ui1_student_in_archive` Tauri command spec and the `ArchiveRepository::student_exists` Rust method spec.
  - §8.7 (new): on-boarding precondition invariant — documents that the on-boarding step is gated on archive membership (not empty tutorial list), and is a read-only archive mutation delegated to `RustArchiver`, no new write authority.
  - §9.5: governance checker gains assertions 10–11 for `ArchiveRepository::student_exists` and `ui1_student_in_archive`.
  - §9.6: workflow test expanded from one scenario to FIVE (A: New with membership check, B: browse historic, C: amend, D: browse-only on-boarding for a never-synced student, E: in-archive student with genuinely zero tutorials — the critical regression test for the membership-gated design).
  - §9.4/§10/§12 risk #9: updated to reflect `onSelect` / `handleSelectFromSearch` naming and the separation of selection from action.
  - §12 risk #11 (new): LSS3 follow-up — dedicated `ui1_sync_targeted_student` command to replace the v1.0.2 Option A workaround.
  - §13 Summary updated.

---

## 1. Scope

### In scope

- Replace the existing live-filter `studentSearch` input (an AG Grid `quickFilterText` over an in-memory class roster) with a button-press **school-wide** search box that queries `POST /administration/students` on Learn2.
- Parse the returned HTML table into a typed Rust `LiveStudentSearchRow` and surface a typed DTO to React.
- Apply a Rust-side date filter (default: `course_start < tomorrow AND course_end > today`) and expose two ISO date pickers in React so the teacher can override the defaults.
- Render results in an AG Grid using the **full API column projection** (Code, Name, Created, Course start, Course end, Tutorial end, Tutor, Tutor date).
- On row click, **select the student for the `StudentOverview` pane** — exactly as clicking a row in the old class-roster pane did. The teacher can then take any of the three existing actions from `StudentOverview`:
  1. **Open a new tutorial** (Standard / Initial / Final) — the existing `ui1_open_new_draft` path, which already performs `sync_targeted_student` internally as its ~1.5 s on-boarding step. This handles the "student enrolled but not in any of the teacher's open classes" case.
  2. **Browse the student's historic tutorials** — the existing `ui1_list_tutorials` command (which already takes a `studentId` and reads from the local archive, independent of any class context). For an in-archive student with genuinely zero tutorials the pane surfaces "No tutorials yet" WITHOUT triggering a sync (Case A in §1). For a never-synced student the handler first runs `sync_targeted_student` (gated on `ui1_student_in_archive` returning `false` — see §1 "Archive-membership signal"), then re-queries; the pane surfaces "No tutorials yet" if the post-sync list is still empty.
  3. **Amend (revise) an existing tutorial** — the existing `ui1_open_revision_draft` path, gated on `ArchiveRevisionAvailability`. Same authority and same revision-eligibility rules as for a class-roster student.
- Three formal contract amendments: `gel_read_only_session.json`, `ui1_writer.json`, `state_ownership.json`.
- One new internal gate, **UI1f**, recorded in `ui1_writer.json::internal_gates`.
- One new governance checker, `tools/check_ui1f_live_search.py`, enforcing the contract surface and command allowlist.
- New Rust parser unit tests and an extended `ui1e_workflow_behavior` test that mocks the search → select → browse-historic → amend-revision flow (see §9.6).
- **Archive-membership signal for the on-boarding decision** (v1.0.2): a new `ui1_student_in_archive(studentId) -> bool` Tauri command (or an extended `ui1_list_tutorials` return shape — see §6.2 step 4 for the chosen approach) that unambiguously distinguishes:
  - **Case A: student IS in the archive** (a previous class-roster sync created the `students` row). `list_tutorials` may return `[]` (genuinely no tutorials) or a non-empty list. Either way, the archive is authoritative and NO `sync_targeted_student` call is triggered. The React pane surfaces "No tutorials yet" for the empty-list sub-case exactly as it does for a class-roster student with no tutorials.
  - **Case B: student is NOT in the archive** (the search-selected student has never been synced). The React handler triggers `sync_targeted_student` (via Option A: `ui1_open_new_draft` + `ui1_discard_draft`, or Option B in LSS3) to populate the archive, then re-queries `ui1_list_tutorials`.
  This signal is required because `ui1_list_tutorials` returning `[]` is ambiguous between "student in archive, no tutorials" and "student not in archive" — auto-syncing on every `[]` would re-fetch the same empty list every time the teacher clicks a genuinely-tutorial-less but in-archive student, which is wasteful and confusing. The archive-membership check is a cheap `SELECT 1 FROM students WHERE uid = ?1` query; see §6.2 step 4 and §8.7 for the contract details.

### Out of scope (non-goals for this phase)

- Persistent caching of search results (the new state class is explicitly **ephemeral**; see §4.3).
- Replacing `ui1_list_students` (the class-scoped archive command) — the Rust API and Tauri command remain available; only the React browse surface stops using them. Archive sync and tutorial history flows are untouched.
- Teacher reassignment, raw GEL field mutation, or any new tutorial write capability beyond what `ui1_submit_draft` already authorizes.
- Frontend semantic authority over search columns, row identity, or date semantics — all parsing and filtering authority stays in Rust.

**Note on pagination:** pagination of the `/administration/students` response was originally listed here as an open question. Live evidence captured on 2026-09-05 (see §3.1) confirms the server renders a **jQuery DataTables**-paginated HTML table with a configurable page-size `<select>` (10/25/50/100) and a two-button pager (`previous`/`next`). Pagination handling is therefore **in scope** for UI1f and is specified in §5.2 (session-level walker) and §5.4 (Tauri command surface). The original "out of scope" entry is retained above only as historical context.

---

## 2. Capability & user story

A teacher signs in to the Writer and needs to act on a tutorial for a student who is **currently enrolled** somewhere in the school but who has not yet been assigned to one of the teacher's open classes — or whose name the teacher only partially remembers. The action may be any of the three the Writer already supports for class-roster students: writing a **new** tutorial, **browsing** the student's historic tutorials, or **amending** (revising) an existing tutorial.

Today the teacher must first open the right class, scroll the class roster, and use a live filter box that only narrows the already-loaded class roster. This is insufficient for the school-wide case, and it incorrectly gates browsing and amending on class membership — a student may be enrolled in the school but not currently showing in any of the teacher's classes, yet still have a tutorial history the teacher needs to see and amend.

After UI1f, the teacher's browse surface is a single **Search students** workspace:

1. A search input plus a **Search** button (Enter key also triggers).
2. Two ISO date pickers:
   - **Course start before** (default: tomorrow — i.e. `course_start < tomorrow`, meaning any student whose course has already started).
   - **Course end after** (default: today — i.e. `course_end >= today`, meaning any student whose course has not yet finished).
   - An empty picker means "no upper / lower bound" on that side.
3. An AG Grid showing **all** matching students across the school, with the full API column projection.
4. **Clicking a row selects the student for the `StudentOverview` pane** — exactly as clicking a row in the old class-roster pane did. The teacher can then take any of the three existing actions from `StudentOverview`:
   - **New Standard / Initial / Final** — the existing `ui1_open_new_draft` path, which already performs `sync_targeted_student` internally as its ~1.5 s on-boarding step. This handles the "student enrolled but not in any of the teacher's open classes" case.
   - **Recent tutorials list** — the existing `ui1_list_tutorials` path, which already takes a `studentId` and reads from the local archive, independent of any class context. For an in-archive student with genuinely zero tutorials the pane surfaces "No tutorials yet" WITHOUT triggering a sync. For a never-synced student the handler first runs `sync_targeted_student` (gated on `ui1_student_in_archive` returning `false`), then re-queries; the pane surfaces "No tutorials yet" if the post-sync list is still empty.
   - **Double-click a tutorial to revise** — the existing `ui1_open_revision_draft` path, gated on `ArchiveRevisionAvailability`. Same authority and same revision-eligibility rules as for a class-roster student.

The teacher's mental model is: *search → click → act*, where "act" is the same three actions they already know from the class-roster flow. The class selector remains only for scoping tutorial history when needed and is no longer the entry point for finding a student. Crucially, **a search-selected student is a first-class student** — every downstream action (browse, amend, new) works identically to the class-roster case, because the existing commands all take a `studentId` and do not require a class context.

**On-boarding precondition:** a search-selected student may not yet exist in the local archive (the recon4 evidence confirms some search-result UIDs are not in the archive until `sync_targeted_student` runs). `ui1_open_new_draft` handles this internally — its `sync_targeted_student` step both on-boards the live GEL student record AND populates the archive, so the subsequent `ui1_list_tutorials` and `ui1_open_revision_draft` calls find the student. For the browse-only path (teacher wants to see history without writing a new tutorial), the React handler first calls a new `ui1_student_in_archive(studentId) -> bool` Tauri command (v1.0.2: cheap `SELECT 1 FROM students WHERE uid = ?1`); if it returns `false`, the handler triggers `sync_targeted_student` via Option A (`ui1_open_new_draft` + `ui1_discard_draft`) in v1.0.2, or Option B (`ui1_sync_targeted_student`) in LSS3. **The on-boarding is gated on archive membership, NOT on the tutorial list being empty** — an in-archive student with genuinely zero tutorials (e.g. a new enrolment with no tutorials yet) must NOT trigger a sync, because that would re-fetch the same empty list every time the teacher clicks the row. See §8.7 for the full invariant.

---

## 3. API surface acquired from GEL

### 3.1 Endpoint

- **Method:** `POST`
- **URL:** `https://learn2.guidedelearning.net/administration/students`
- **Headers (recorded, anonymized):**
  - `content-type: application/x-www-form-urlencoded`
  - `origin: https://learn2.guidedelearning.net`
  - `referer: https://learn2.guidedelearning.net/administration/students/search`
  - `upgrade-insecure-requests: 1`
  - `user-agent: <existing GelSession user agent>`
- **Body:** a single form-encoded pair: `search=<term>`
- **Response:** `text/html; charset=utf-8` — a Drupal admin page containing one student results table.

#### 3.1.1 jQuery DataTables rendering (live evidence, 2026-09-05)

Live reconnaissance (`gel_student_search_recon4.js`, captured 2026-09-05T11:39:45Z, 230 rows across 4 searches, `captureRate: 1.0` for every non-empty search) confirms the response is rendered client-side by **jQuery DataTables**, not Drupal core pager. The relevant markup is:

```html
<!-- Page-size control: 10 / 25 / 50 / 100 entries per page -->
<div class="dataTables_length" id="student-management_length">
  <label>Show <select size="1" name="student-management_length"
    aria-controls="student-management">
    <option value="10"  selected="selected">10</option>
    <option value="25">25</option>
    <option value="50">50</option>
    <option value="100">100</option>
  </select> entries</label>
</div>

<!-- Info footer: authoritative total row count -->
<div class="dataTables_info" id="student-management_info"
     role="status" aria-live="polite">
  Showing 1 to 10 of 67 entries
</div>

<!-- Two-button pager -->
<div class="dataTables_paginate paging_two_button"
     id="student-management_paginate">
  <a class="paginate_disabled_previous" tabindex="-1" role="button"
     id="student-management_previous" aria-controls="student-management">Previous</a>
  <a class="paginate_enabled_next"      tabindex="0"  role="button"
     id="student-management_next"      aria-controls="student-management">Next</a>
</div>
```

Three rendering behaviours the Rust session layer (§5.2) must drive to capture all rows:

1. **Page-size `<select>`.** The default is 10 rows per page. Setting `select[name="student-management_length"]` to `100` collapses what would otherwise be 7 pages of 10 rows into 1 page of 67 (for the "Rina" search) or 2 pages of 100 + 54 (for the 154-row "Rin" search). The `<select>` is set via `POST` to `/administration/students` with the existing `search=<term>` field plus `length=100` (DataTables re-POSTs the full search form on length change). The Rust walker uses the largest available option (100).
2. **Info footer.** The text `"Showing X to Y of Z entries"` is the **authoritative total row count**. The Rust parser (§5.1) must extract `Z` and return it as `total_entries` alongside the row vector, so the Tauri command (§5.4) can compute and return `capture_rate = rows.len() / total_entries` for governance. The footer also handles the empty-state form `"Showing 0 to 0 of 0 entries"` and the filtered variant `"Showing X to Y of Z entries (filtered from N total entries)"`.
3. **Two-button pager.** "Next" is an `<a class="paginate_enabled_next">` with **no `href`** — the click is a JavaScript handler that re-POSTs the search form with an incremented `start` parameter. When there is no next page, DataTables toggles the class to `paginate_disabled_next` (the same `<a>` element, just a different class). The Rust walker detects end-of-results by either (a) `total_entries` reached, or (b) the `next` link's class containing `disabled`.

Because DataTables re-POSTs the search form on every page-size change and every pager click, the Rust session layer (§5.2) drives pagination by issuing **multiple `POST /administration/students` requests**, not by parsing one response and walking `<a href>` links. Each POST carries the same `search=<term>` field plus one of:

- `length=100` (set page size to 100) — issued first, to collapse the result set into as few pages as possible.
- `start=0` (first page, default if `start` omitted)
- `start=100` (second page, when `total_entries > 100`)
- `start=N` (page `N/100 + 1`)

The walker stops as soon as the cumulative row count reaches `total_entries` reported by the first response's footer.

### 3.2 Row schema (from `gel_search_report_anonymized.json`)

Each result row is a `<tr>` whose cells map 1:1 to the existing `resultRows[].cells` array captured by the existing Playwright capture pipeline. Indices:

| Index | Field | Source example | Typed Rust field |
|---|---|---|---|
| 0 | (row handle / empty) | `""` | ignored |
| 1 | Student code | `c80001907` | `code: String` |
| 2 | Name + email | `Student_8444da51 email@email.com` | `name: String` (email stripped before IPC — see §8) |
| 3 | Created date | `09-01-2018 11:46 pm` | `created_at: Option<DateTime>` (UTC, parsed from `dd-MM-yyyy hh:mm am/pm`) |
| 4 | Course start | `17-02-2018` | `course_start: Option<NaiveDate>` (`dd-MM-yyyy`) |
| 5 | Course end | `10-03-2018` | `course_end: Option<NaiveDate>` (`dd-MM-yyyy`) |
| 6 | Tutorial end | `10-06-2018` | `tutorial_end: Option<NaiveDate>` (`dd-MM-yyyy`) |
| 7 | Tutor + tutor date | `07-03-2018(Liam Wallington)` or `17-03-2020(Louisa Stodd) (absent)` or `never` | `tutor_date: Option<NaiveDate>`, `tutor_name: Option<String>`, `absent: bool` |

Each row also yields a stable **studentUid** from its link: `hrefPath = /administration/studentmanagement/report/<uid>`. The UID is the same identity surface used by the existing `ui1_open_new_draft` command, so no identity translation layer is required.

**Tutor-cell edge cases (live evidence, 2026-09-05):** the captured run included a row whose cell 7 was the literal string `never` (a student with no tutorials yet). The parser must accept this as `tutor_date: None, tutor_name: None, absent: false` and not count the row as malformed. The three observed shapes are therefore:

- `dd-MM-yyyy(Tutor Name)` — most common, parsed to `{ date, tutor_name, absent: false }`.
- `dd-MM-yyyy(Tutor Name) (absent)` — parsed to `{ date, tutor_name, absent: true }`.
- `never` — parsed to `{ date: None, tutor_name: None, absent: false }`.

Any other shape returns `{ date: None, tutor_name: None, absent: false }` and increments `skipped_malformed` for the tutor cell only (the row is still kept; only the tutor sub-record is dropped).

### 3.3 Relation to existing contract surface

`/administration/students` already appears in `gel_read_only_session.json` as `authentication.learn2_verification_path` — but only as a **GET** verification probe inside `GelSession::login` (gel_session.rs line 147). UI1f promotes a *POST* to that same path to a governed read-query, explicitly bounded:

- The POST body is one form field (`search`).
- The POST is only ever issued by `GelSession::search_live_students`, behind the `ui1_search_live_students` Tauri command, behind an authenticated session.
- No other POST handler is added. The existing `forbidden_command_capabilities` list (no "arbitrary or unvalidated tutorial POST", no "generic HTTP/request URL", no "POST payload construction/exposure") continues to hold; the search body is constructed in Rust.

---

## 4. Contract amendments (formal governance)

Three amendments, each with a version bump. All three amendments are mandatory pre-conditions for any code change in §5–§7. The codebase's existing governance tooling (`tools/check_contracts.py`, `tools/check_governance.py`, `tools/check_ui1_boundaries.py`) is updated in the same PR.

### 4.1 `contracts/gel_read_only_session.json`

**Version bump:** `contract_version: 2 → 3`
**`status:`** `active` (unchanged)
**`evaluation.summary`** updated to: *"N1 remains a narrow authenticated acquisition boundary. N2b extends the fixed GET surface with current New-tutorial form acquisition. UI1f adds a single governed POST read-query against /administration/students for school-wide student search; the POST body is a single `search` form field, the response is parsed in Rust, and student emails are stripped at acquisition. Login is no longer the only POST authority; the search POST is the sole additional POST and carries no write semantics."*

Concrete JSON deltas:

```jsonc
// read_surface — ADD one entry:
{
  "id": "live_student_search",
  "method": "POST",
  "path_template": "/administration/students",
  "request_body": { "search": "<term>" },
  "response": "html_table_privacy_filtered",
  "parser": "live_student_search_parser::parse_live_student_search_html"
}

// authentication — ADD one field alongside login_post_count:
"live_student_search_post_count": 0,   // runtime counter, incremented per issued POST

// network_authority — AMEND in place:
"allowed_post_purposes": [
  "Learn2 login handshake step 1",
  "Learn2 login handshake step 2",
  "School-wide student read query via /administration/students"
],
"forbidden_http_methods_after_authentication": [
  "POST — except (a) login handshake steps 1 and 2, (b) the governed live_student_search read query",
  "PUT",
  "PATCH",
  "DELETE"
],
"generic_request_api": false,            // unchanged
"gel_tutorial_write_authority": false,    // unchanged
"search_post_is_read_only": true,         // NEW assertion
"search_post_body_keys": ["search"],      // NEW assertion
```

The `privacy.student_fields_removed_immediately` array already covers `email`, `mail`, `email_address`, `emailaddress`. The new parser **must** run `strip_student_sensitive_fields` on every parsed row before returning from `GelSession::search_live_students`, exactly as `get_students` and `get_student_profile` already do.

### 4.2 `contracts/ui1_writer.json`

**Version bump:** `contract_version: 14 → 15`
**`status:`** `complete_strictly_accepted` (UI1e baseline retained; UI1f added)
**`evaluation.summary`** updated to: *"...UI1f adds a button-triggered school-wide student search surface that replaces the class-roster live filter. React is still presentation-only; the search POST is issued by Rust; results are an ephemeral presentation state. UI1f exposes no GEL tutorial write capability."*

Concrete JSON deltas:

```jsonc
// initial_command_allowlist — ADD TWO entries (v1.0.2):
"ui1_search_live_students",
"ui1_student_in_archive"

// internal_gates — ADD a new gate after UI1e:
{
  "id": "UI1f",
  "name": "School-wide student search and on-boarding",
  "status": "implemented_pending_strict_acceptance",
  "scope": [
    "Replace live filter quickFilterText with button-press school-wide search",
    "POST /administration/students via GelSession::search_live_students",
    "Rust-side default date filter (course_start < tomorrow, course_end > today)",
    "Two ISO date pickers in React (yyyy-mm-dd; empty = no bound)",
    "AG Grid full API column projection",
    "Row click on-boards via ui1_open_new_draft (sync_targeted_student)",
    "Student emails stripped before IPC; cookies remain session-private",
    "No new GEL tutorial write, teacher reassignment, or archive mutation"
  ],
  "plan": "plans/LIVE_STUDENT_SEARCH_PLAN_v1_0_0.md",
  "implementation_authorization": "Requires UI1e strict acceptance baseline PASS=45 SKIP=0 FAIL=0 (recorded 2026-09-02)."
}

// forbidden_command_capabilities — UNCHANGED (no relaxation needed; search POST is governed in gel_read_only_session)

// layout — AMEND:
"browse_mode": "School-wide student search workspace (replaces class-roster + live filter)",
"school_visible": true,             // was false — UI1f is the explicit governance note that the school is now visible
"student_visible_projection": [
  "Code", "Name", "Created", "Course start", "Course end", "Tutorial end", "Tutor", "Tutor date"
]

// reproducible_release.current_release_scope — AMEND:
"ui1e" → "ui1f"
```

The `school_visible: false → true` change is the most material visible-authority change in this amendment and is called out explicitly so the next reviewer cannot miss it.

### 4.3 `contracts/state_ownership.json`

**Version bump:** `contract_version: 23 → 24`
**`status:`** `active` (unchanged)

Concrete JSON deltas:

```jsonc
// state_classes — ADD one entry:
{
  "id": "live_student_search_results",
  "class": "ephemeral_presentation",
  "source_or_derived": "derived",
  "canonical": false,
  "permitted_writers": [ "ui1_search_live_students" ],
  "readers": [ "writer_react_ui" ],
  "retention": "In-memory only; never persisted. Cleared on logout, on session expiry, and when a new search is issued. Not written to the archive.",
  "invalidation": "Any new search replaces the entire result set atomically. Session expiry (HTTP 401/403 or login redirect) clears the result set and surfaces a structured error.",
  "current_materialization": "ephemeral_react_state",
  "state_kind": "presentation"
}
```

The new class lives alongside `active_tutorial_draft_state` and `harper_session_disabled_rules` — it is the same kind of state (ephemeral, React-readable, Rust-owned writer).

---

## 5. Rust implementation surface

All Rust additions are made in the existing `gel-core` crate (parser + session) and `writer-ui/src-tauri` crate (Tauri command). No new crate is added. No new external dependency is required — `scraper`, `chrono`, `regex`, and `reqwest` are already in the workspace `Cargo.lock`.

### 5.1 New file `gel-core/src/live_student_search_parser.rs`

```rust
//! Parser for the HTML results page returned by
//! `POST /administration/students` (form: `search=<term>`,
//! optionally `length=100` and `start=<offset>` for pagination).
//!
//! Authority: contracts/gel_read_only_session.json::read_surface::live_student_search
//! Privacy:   every row is passed through `strip_student_sensitive_fields`
//!            before the typed row leaves this module.
//!
//! The page is rendered client-side by jQuery DataTables. The parser
//! extracts BOTH the result rows AND the DataTables info footer text
//! ("Showing X to Y of Z entries"), because Z is the authoritative
//! total row count that the session-level walker (§5.2) uses to
//! decide whether to issue follow-up `start=<offset>` POSTs.

use chrono::{DateTime, NaiveDate, Utc};
use scraper::{Html, Selector};
use serde::Serialize;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LiveStudentSearchRow {
    pub student_uid: i64,
    pub code: String,
    pub name: String,                       // email-stripped
    pub created_at: Option<DateTime<Utc>>,  // dd-MM-yyyy hh:mm am/pm
    pub course_start: Option<NaiveDate>,    // dd-MM-yyyy
    pub course_end: Option<NaiveDate>,      // dd-MM-yyyy
    pub tutorial_end: Option<NaiveDate>,    // dd-MM-yyyy
    pub tutor_date: Option<NaiveDate>,      // dd-MM-yyyy, from cell index 7 prefix
    pub tutor_name: Option<String>,         // text inside parens in cell 7
    pub absent: bool,                        // "(absent)" suffix in cell 7
}

/// DataTables info-footer projection. The footer text is of the form
/// `Showing 1 to 10 of 67 entries` (or `Showing 0 to 0 of 0 entries`
/// for an empty result, or `Showing X to Y of Z entries (filtered
/// from N total entries)` when a server-side filter is active).
/// `total` is the authoritative total row count for the search.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LiveStudentSearchInfoFooter {
    pub start: Option<u64>,
    pub end: Option<u64>,
    pub total: Option<u64>,
    pub raw: String,
}

pub struct LiveStudentSearchParseReport {
    pub rows: Vec<LiveStudentSearchRow>,
    pub skipped_malformed: usize,
    pub info_footer: Option<LiveStudentSearchInfoFooter>,
}

/// Parse one DataTables response page. The caller (GelSession::search_live_students,
/// §5.2) is responsible for walking pages and stitching rows from multiple
/// calls into one Vec, using `info_footer.total` to know when to stop.
pub fn parse_live_student_search_html(html: &str) -> LiveStudentSearchParseReport { /* … */ }

/// Parse the DataTables info-footer text alone. Extracted as a public
/// helper so the unit tests (§9.2) can exercise it without building
/// full HTML fixtures.
pub fn parse_data_tables_info_footer(text: &str) -> Option<LiveStudentSearchInfoFooter> { /* … */ }
```

Implementation notes:

- Use the existing `scraper` crate (already in `Cargo.lock`; same dependency used by the other HTML parsers in `gel-core`).
- Row identification: select `<tr>` elements inside the results table whose first `<a href>` matches `/administration/studentmanagement/report/<uid>`. The `uid` is parsed with `i64::from_str`; rows with a non-numeric uid are skipped and counted in `skipped_malformed`.
- Cell parsing: each row's `<td>` cells are extracted in order; rows with fewer than 8 cells are skipped.
- **Spaced cell extraction (defence against the recon3 glue bug):** cells are NOT extracted with `text_content()` directly. The parser walks each `<td>`'s child nodes and inserts a single ASCII space between any two adjacent element children that don't already have whitespace between them. This prevents `<td><a>FirstName Surname</a>email@x.com</td>` from producing the glued string `"FirstName Surnameemail@x.com"`, which would defeat the email-stripping regex (the surname would be consumed along with the email). The recon4 JavaScript walker (`cellTextSpaced`) is the reference implementation; the Rust port uses the same algorithm.
- Tutor cell (index 7): three observed shapes (see §3.2):
  - `dd-MM-yyyy(Tutor Name)` → `{ date, tutor_name, absent: false }`
  - `dd-MM-yyyy(Tutor Name) (absent)` → `{ date, tutor_name, absent: true }`
  - `never` → `{ date: None, tutor_name: None, absent: false }` (a student with no tutorials yet)
  - Anything else → `{ date: None, tutor_name: None, absent: false }` and increment `skipped_malformed` for the tutor sub-record only (the row is still kept). Regex for the first two shapes: `^(?P<date>\d{2}-\d{2}-\d{4})\((?P<name>[^)]+)\)(?:\s*\(absent\))?`.
- Date parsing: `NaiveDate::parse_from_str(s, "%d-%m-%Y")`. Created timestamp uses `DateTime::parse_from_str(s, "%d-%m-%Y %l:%M %P")` then `.with_timezone(&Utc)`. Unparseable dates become `None`; the row is kept (only `student_uid` and `code` are strictly required).
- **Info-footer parsing:** selector `.dataTables_info, [id$="_info"]`. The footer text is parsed with the regex `Showing\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+entries` (case-insensitive). The empty-state `No data available in table` and `Showing 0 to 0 of 0 entries` both produce `total: Some(0)`. Unparseable footers (e.g. legacy skins without an info element) produce `info_footer: None`; the session walker treats `None` as "unknown total — walk until the row count stops growing or the `next` link is disabled".
- Privacy: after building each `LiveStudentSearchRow`, call `strip_student_sensitive_fields` (existing helper) on a synthesized JSON view of the row before returning, mirroring how `get_students` already uses it. Practically, this strips any email-like substring from `name`.

### 5.2 New method on `GelSession` — `gel-core/src/gel_session.rs`

```rust
/// School-wide student read query. Walks the jQuery DataTables
/// pager server-side by issuing follow-up POSTs with `start=<offset>`.
///
/// Authority: contracts/gel_read_only_session.json::read_surface::live_student_search
/// POST /administration/students  form: search=<term>[&length=100][&start=<offset>]
///
/// Returns the full row vector across all pages plus the
/// DataTables-reported total_entries, so the Tauri command (§5.4)
/// can compute capture_rate = rows.len() / total_entries for governance.
pub fn search_live_students(
    &mut self,
    term: &str,
) -> Result<LiveStudentSearchResult> {
    if !self.authenticated {
        bail!("unauthenticated_read: search_live_students requires an authenticated GEL session");
    }
    if term.trim().is_empty() {
        return Ok(LiveStudentSearchResult {
            rows: Vec::new(),
            total_entries: Some(0),
            info_footer_raw: Some("Showing 0 to 0 of 0 entries".to_string()),
            pages_fetched: 0,
        });
    }

    let mut all_rows: Vec<LiveStudentSearchRow> = Vec::new();
    let mut total_entries: Option<u64> = None;
    let mut info_footer_raw: Option<String> = None;
    let mut pages_fetched: u32 = 0;
    let mut start: u64 = 0;
    const PAGE_SIZE: u64 = 100; // largest option in the captured <select>
    const MAX_PAGES: u32 = 20;  // safety cap; ~1000 rows at 100-per-page

    loop {
        self.throttle();
        let response = self
            .client
            .post(self.learn2_url("/administration/students"))
            .header(CONTENT_TYPE, "application/x-www-form-urlencoded")
            .header(REFERER, self.learn2_url("/administration/students/search"))
            .form(&[
                ("search", term.trim()),
                ("length", &PAGE_SIZE.to_string()),
                ("start", &start.to_string()),
            ])
            .send()
            .context("send GEL live student search POST")?;
        let status = response.status();
        let final_url = response.url().as_str().to_ascii_lowercase();
        let body = response.text().context("read GEL live student search response body")?;
        if !status.is_success() {
            bail!("GEL live student search failed with HTTP {}", status.as_u16());
        }
        if is_login_page(&final_url, &body) {
            self.authenticated = false;
            bail!("GEL live student search returned the login page; session marked unauthenticated");
        }

        let report = parse_live_student_search_html(&body);
        pages_fetched += 1;

        // Capture the footer from the first page only — it is constant
        // across pages (DataTables reports the total, not the slice).
        if total_entries.is_none() {
            total_entries = report.info_footer.as_ref().and_then(|f| f.total);
            info_footer_raw = report.info_footer.as_ref().map(|f| f.raw.clone());
        }

        // Defence-in-depth: strip emails on the typed rows.
        let mut rows = report.rows;
        for row in &mut rows {
            strip_student_sensitive_fields(&mut serde_json::to_value(&mut *row).unwrap());
        }
        all_rows.append(&mut rows);

        // Stop conditions:
        //   1. We have captured all rows the footer reported.
        //   2. The footer is absent and the last page returned no rows
        //      (defence against an empty result with no footer).
        //   3. We hit the safety cap.
        if let Some(total) = total_entries {
            if (all_rows.len() as u64) >= total {
                break;
            }
        } else if all_rows.is_empty() {
            break;
        }
        if pages_fetched >= MAX_PAGES {
            bail!("GEL live student search exceeded MAX_PAGES={MAX_PAGES} cap; \
                   captured {} of {} entries", all_rows.len(),
                   total_entries.map(|t| t.to_string()).unwrap_or_else(|| "unknown".to_string()));
        }

        start += PAGE_SIZE;
    }

    Ok(LiveStudentSearchResult {
        rows: all_rows,
        total_entries,
        info_footer_raw,
        pages_fetched,
    })
}

/// Result of `search_live_students`. Mirrors the recon4 script's
/// `pagination` output block.
#[derive(Debug, Clone, Serialize)]
pub struct LiveStudentSearchResult {
    pub rows: Vec<LiveStudentSearchRow>,
    /// From the DataTables info footer: "Showing X to Y of Z entries" -> Z.
    /// `None` if the footer was absent (legacy skins).
    pub total_entries: Option<u64>,
    pub info_footer_raw: Option<String>,
    pub pages_fetched: u32,
}
```

The method follows the same posture as `get_students` / `get_student_profile`: throttle before every request, fail closed on login-page detection, strip emails before return. The walker uses the DataTables `length=100` + `start=<offset>` form fields (§3.1.1) to walk pages server-side; this is more reliable than parsing `<a>` click handlers in Rust, which has no DOM/JS engine. The `MAX_PAGES` cap (20) is the same safety cap the recon4 script uses; at 100-per-page it covers up to 2000 rows.

**Privacy note:** `pages_fetched` and `total_entries` are returned to the caller because they are governance signals, not PII. The `info_footer_raw` is also returned verbatim because the footer text is a DataTables-rendered string of the form `"Showing X to Y of Z entries"` — it contains only numeric counts, never student names or emails. The existing `error_redaction_rule` continues to apply to error paths.

### 5.3 Re-export in `gel-core/src/lib.rs`

Add `pub use live_student_search_parser::{parse_live_student_search_html, parse_data_tables_info_footer, LiveStudentSearchRow, LiveStudentSearchInfoFooter, LiveStudentSearchParseReport};` and `pub use gel_session::{GelSession, LiveStudentSearchResult};` (the existing `pub use gel_session::GelSession;` already exposes the impl; the new `LiveStudentSearchResult` struct is co-located with `GelSession` because it is the return type of `search_live_students`).

### 5.4 New Tauri command — `writer-ui/src-tauri/src/lib.rs`

```rust
#[derive(Serialize)]
pub struct LiveStudentSearchRowView {
    pub student_uid: i64,
    pub code: String,
    pub name: String,
    pub created_at: Option<String>,   // RFC 3339
    pub course_start: Option<String>,  // yyyy-MM-dd
    pub course_end: Option<String>,    // yyyy-MM-dd
    pub tutorial_end: Option<String>,  // yyyy-MM-dd
    pub tutor_date: Option<String>,    // yyyy-MM-dd
    pub tutor_name: Option<String>,
    pub absent: bool,
}

/// Governance wrapper around the filtered row vector. Mirrors the
/// recon4 script's `pagination` output block so the React pane and
/// the strict-release-gate checker (§9.5) can assert on capture_rate.
#[derive(Serialize)]
pub struct LiveStudentSearchResponse {
    pub rows: Vec<LiveStudentSearchRowView>,
    /// From the DataTables info footer: "Showing X to Y of Z entries" -> Z.
    /// None if the footer was absent (legacy skins).
    pub total_entries: Option<u64>,
    pub info_footer_raw: Option<String>,
    /// How many POST requests the session walker issued to /administration/students.
    pub pages_fetched: u32,
    /// rows.len() / total_entries, or None when total_entries is 0 or None.
    /// The strict release gate asserts capture_rate == 1.0 (or None for
    /// empty results) for every non-empty search — see §9.7.
    pub capture_rate: Option<f64>,
}

#[tauri::command]
async fn ui1_search_live_students(
    app: AppHandle,
    term: String,
    course_start_before: Option<String>,  // yyyy-MM-dd or None/""
    course_end_after: Option<String>,      // yyyy-MM-dd or None/""
) -> Result<LiveStudentSearchResponse, String> {
    let response = tauri::async_runtime::spawn_blocking(move || -> Result<_, String> {
        let state = app.state::<WriterAppState>();
        let _operation = state.writer_operation.lock().map_err(|_| "writer operation lock poisoned".to_string())?;
        let mut session = state.session.lock().map_err(|_| "session lock poisoned".to_string())?;
        let session = session.as_mut()
            .filter(|s| s.is_authenticated())
            .ok_or_else(|| "an authenticated GEL session is required to search live students".to_string())?;
        let result: LiveStudentSearchResult = session.search_live_students(&term)
            .map_err(|e| format!("GEL live student search failed: {e:#}"))?;
        let start_before = parse_optional_iso_date(course_start_before)?;
        let end_after = parse_optional_iso_date(course_end_after)?;
        let (today, tomorrow) = today_and_tomorrow_utc();
        let start_before = start_before.or(Some(tomorrow));    // default
        let end_after   = end_after.or(Some(today));            // default
        let filtered: Vec<LiveStudentSearchRowView> = result.rows.into_iter()
            .map(|row| {
                let passes = row.passes_date_filter(start_before, end_after);
                (row, passes)
            })
            .filter_map(|(row, passes)| if passes { Some(row.into()) } else { None })
            .collect();
        // capture_rate uses the PRE-filter row count vs total_entries,
        // because the filter is a local presentation concern — the
        // walker is responsible for capturing every row DataTables
        // reported, before any client-side filtering. A drop in rows
        // after filtering is expected and not a capture defect.
        let capture_rate = match result.total_entries {
            Some(total) if total > 0 => Some(result.rows.len() as f64 / total as f64),
            _ => None,
        };
        Ok(LiveStudentSearchResponse {
            rows: filtered,
            total_entries: result.total_entries,
            info_footer_raw: result.info_footer_raw,
            pages_fetched: result.pages_fetched,
            capture_rate,
        })
    })?;
    response
}
```

`parse_optional_iso_date` accepts `None`, `""`, or `Some("yyyy-MM-dd")` and returns `Result<Option<NaiveDate>, String>`. Invalid dates return a structured error such as `"invalid ISO date: '13-09-2026' (expected yyyy-MM-dd)"` — the raw input is echoed back only when it is not a recognizable PII pattern; this is consistent with the existing `error_redaction_rule`.

**capture_rate semantics:** `capture_rate = result.rows.len() / total_entries` uses the **unfiltered** row count returned by the session walker, not the post-date-filter count. The walker is responsible for capturing every row DataTables reported; the date filter (§7) is a local presentation concern applied after capture. A drop in `rows` after filtering is expected and is not a capture defect — the UI surfaces `resultRows.length` (post-filter) and `pagination.totalEntries` (pre-filter) separately so a human can see both.

Register the new command in the existing `tauri::generate_handler![…]` invocation alongside `ui1_submit_draft` and the other UI1e commands.

### 5.5 TypeScript types — `writer-ui/src/types.ts`

```ts
export interface LiveStudentSearchRowView {
  studentUid: number;
  code: string;
  name: string;
  createdAt: string | null;        // RFC 3339
  courseStart: string | null;      // yyyy-MM-dd
  courseEnd: string | null;        // yyyy-MM-dd
  tutorialEnd: string | null;       // yyyy-MM-dd
  tutorDate: string | null;         // yyyy-MM-dd
  tutorName: string | null;
  absent: boolean;
}

/**
 * Governance wrapper returned by ui1_search_live_students.
 * Mirrors the recon4 script's `pagination` output block so the UI
 * and the strict-release-gate checker can assert on captureRate.
 */
export interface LiveStudentSearchResponse {
  rows: LiveStudentSearchRowView[];
  /** From the DataTables info footer: "Showing X to Y of Z entries" -> Z.
   *  null if the footer was absent (legacy skins). */
  totalEntries: number | null;
  infoFooterRaw: string | null;
  /** How many POST requests the session walker issued to /administration/students. */
  pagesFetched: number;
  /** rows.length / totalEntries, or null when totalEntries is 0 or null.
   *  The strict release gate asserts captureRate === 1 (or null for
   *  empty results) for every non-empty search — see §9.7. */
  captureRate: number | null;
}
```

### 5.6 TypeScript API wrapper — `writer-ui/src/api.ts`

```ts
export const searchLiveStudents = (
  term: string,
  courseStartBefore: string,   // "" or yyyy-MM-dd
  courseEndAfter: string,      // "" or yyyy-MM-dd
) =>
  invoke<LiveStudentSearchResponse>("ui1_search_live_students", {
    term,
    courseStartBefore: courseStartBefore || null,
    courseEndAfter: courseEndAfter || null,
  });

/**
 * Read-only archive-membership check. Returns true iff a `students` row
 * exists for the given UID. Used by handleSelectFromSearch to decide
 * whether to trigger sync_targeted_student before calling
 * listTutorials — see §8.7. Distinguishes Case A (student in archive,
 * possibly zero tutorials — do NOT sync) from Case B (student not in
 * archive — DO sync).
 */
export const studentInArchive = (studentId: number) =>
  invoke<boolean>("ui1_student_in_archive", { studentId });
```

Empty strings are normalized to `null` at the IPC boundary so Rust receives `None` for "no bound".

The `searchLiveStudents` return type changes from `LiveStudentSearchRowView[]` to `LiveStudentSearchResponse` so the caller receives `totalEntries`, `pagesFetched`, and `captureRate` alongside the row vector. The React pane (§6.1) uses `captureRate` as a governance indicator (a small badge in the search header showing `100% captured` when `captureRate === 1`, or `N of M captured` when `captureRate < 1`), and the strict-release-gate checker (§9.7) asserts `captureRate === 1 || captureRate === null` for every non-empty search in the workflow test.

The `studentInArchive` wrapper is the unambiguous archive-membership signal that drives the on-boarding decision in `handleSelectFromSearch` (§6.2 step 4). It is read-only, cheap (one indexed `SELECT 1` query), and adds no new write authority.

---

## 6. React UI surface

### 6.1 New component `writer-ui/src/components/LiveStudentSearchPane.tsx`

Props:

```ts
interface Props {
  busy: boolean;
  /** Fired when the teacher clicks a row. The parent (App.tsx) treats this
   *  exactly like a row click in the old StudentListPane: the selected
   *  student becomes the input to StudentOverview, which then exposes the
   *  three existing actions (New / browse history / amend). The pane does
   *  NOT directly invoke ui1_open_new_draft — that decision belongs to the
   *  teacher via the StudentOverview buttons, exactly as it does today. */
  onSelect: (row: LiveStudentSearchRowView) => Promise<void> | void;
}
```

Internal state:

- `term: string`
- `courseStartBefore: string` — initialized to tomorrow's ISO date
- `courseEndAfter: string` — initialized to today's ISO date
- `results: LiveStudentSearchRowView[]`
- `totalEntries: number | null` — from the DataTables footer, surfaced by `searchLiveStudents`
- `pagesFetched: number` — for the governance badge
- `captureRate: number | null` — for the governance badge
- `querying: boolean`
- `error: string | null`

Behaviour:

- A single `<input type="search">` for `term`, followed by a **Search** button. Both the button click and `Enter` inside the input call `runSearch()`.
- Two `<input type="date">` pickers labelled **Course start before** and **Course end after**. Clearing a picker leaves the field empty (which the wrapper converts to `null`).
- `runSearch()` sets `querying=true`, calls `searchLiveStudents(term, courseStartBefore, courseEndAfter)`, replaces `results` atomically with `response.rows`, stores `response.totalEntries`/`response.pagesFetched`/`response.captureRate`, sets `querying=false`. Empty `term` short-circuits and clears `results` to `[]` without an IPC call.
- AG Grid `themeQuartz` + `AllCommunityModule` (same registration pattern as `StudentListPane`).
- Column definitions (full API projection):

```ts
const columns: ColDef<LiveStudentSearchRowView>[] = [
  { field: "code",           headerName: "Code",          width: 120 },
  { field: "name",           headerName: "Name",         flex: 1.6, minWidth: 180 },
  { colId: "createdAt",      headerName: "Created",       width: 145,
    valueFormatter: ({ value }) => formatTimestamp(value) },
  { colId: "courseStart",    headerName: "Course start", width: 120,
    valueFormatter: ({ value }) => formatIsoDate(value) },
  { colId: "courseEnd",      headerName: "Course end",   width: 120,
    valueFormatter: ({ value }) => formatIsoDate(value) },
  { colId: "tutorialEnd",    headerName: "Tutorial end", width: 120,
    valueFormatter: ({ value }) => formatIsoDate(value) },
  { colId: "tutorName",      headerName: "Tutor",         flex: 1.1, minWidth: 130 },
  { colId: "tutorDate",      headerName: "Tutor date",    width: 120,
    valueFormatter: ({ value }) => formatIsoDate(value) },
  { colId: "absent",         headerName: "Absent",        width: 80,
    valueFormatter: ({ value }) => value ? "Yes" : "" },
];
```

- `defaultColDef`: `{ sortable: true, filter: true, resizable: true, editable: false, suppressMovable: true }` (same as `StudentListPane`).
- `getRowId={({ data }) => String(data.studentUid)}`.
- `onRowClicked` calls `onSelect(event.data)` when `!busy` and `event.data` is non-null. This mirrors the existing `StudentListPane` row-click contract exactly — the parent decides what to do with the selected student (typically: feed it to `StudentOverview`). The pane does NOT directly invoke `ui1_open_new_draft`; the New / browse / amend decisions are the teacher's, made via the `StudentOverview` buttons after the student is selected.
- Initial sort: by `courseStart` descending (newest first), which is the "by date and match" default requested in the brief.
- Header: `<h2>Search students</h2>` and a `<p className="subtle">{results.length} match{results.length === 1 ? "" : "es"}</p>`.
- **Governance badge** (new in v1.0.1, powered by the recon4 `captureRate` field): a small inline element next to the header that reads:
  - `"100% captured (N of N) in P page(s)"` when `captureRate === 1`,
  - `"N of M captured (incomplete)"` (with a warning colour) when `captureRate < 1`,
  - `"0 matches"` (neutral) when `totalEntries === 0`,
  - `"unknown total"` (neutral) when `totalEntries === null`.

  The badge is read-only and presentational; it is not a control. The strict-release-gate checker (§9.7) asserts `captureRate === 1 || captureRate === null` in the workflow test, so a teacher never sees the "incomplete" badge under normal operation — it is a fault indicator that surfaces a parser or pager-walk bug immediately.

### 6.2 `App.tsx` changes

1. **Remove** `const [studentSearch, setStudentSearch] = useState("");` and the `<input type="search" … onChange={(event) => setStudentSearch(event.target.value)} />` block inside the `workspace-toolbar` section.
2. **Remove** `setStudentSearch("")` from `chooseClass` and from `doLogout`.
3. **Replace** `<StudentListPane … />` with `<LiveStudentSearchPane busy={busy} onSelect={handleSelectFromSearch} />`. The pane's row-click is the entry point; the selected student becomes the input to `StudentOverview` exactly as a class-roster row click does today.
4. **Add** `handleSelectFromSearch(row: LiveStudentSearchRowView)` — this is the search-pane equivalent of `chooseStudent` in the existing class-roster flow. It must:
   - Set `studentId = row.studentUid` so `StudentOverview` receives the selected student (via the existing `selectedStudent` derivation).
   - **Call the new `ui1_student_in_archive(row.studentUid) -> bool` Tauri command** (v1.0.2: a new read-only command exposing `ArchiveRepository::student_exists(uid)` — see §6.2 step 4a below for the Rust-side spec). This is the unambiguous archive-membership signal that distinguishes Case A (student in archive, possibly zero tutorials) from Case B (student not in archive).
   - **If `ui1_student_in_archive` returns `true`:** call the existing `listTutorials(row.studentUid)` to populate the tutorial history. The existing `ui1_list_tutorials` Tauri command reads from the local archive; if the student genuinely has no tutorials this returns `[]` and the pane shows "No tutorials yet". **No `sync_targeted_student` call is triggered** — the archive is already authoritative for this student. This is the Case A path.
   - **If `ui1_student_in_archive` returns `false`:** the student has never been synced. The handler on-boards the student into the archive BEFORE calling `listTutorials`, so the subsequent `ui1_list_tutorials` and `ui1_open_revision_draft` calls find the student. Two on-boarding options:
     - **Option A (chosen for v1.0.2):** reuse `ui1_open_new_draft(row.studentUid, "standard")` and immediately discard the draft via `ui1_discard_draft`. This reuses the existing `sync_targeted_student` plumbing without adding a new Tauri command. Cost: one extra draft lifecycle in memory; no IPC payload cost because the draft is discarded before any field edits. After on-boarding, call `listTutorials(row.studentUid)` — it may still return `[]` (the student has no tutorials) but the student row now exists in the archive so subsequent amend attempts will resolve correctly.
     - **Option B (deferred to LSS3, §12 risk #11):** add a new `ui1_sync_targeted_student(studentId)` Tauri command that invokes `sync_targeted_student` directly without opening a draft. Cleaner than Option A; small contract amendment surface; thin wrapper around existing `RustArchiver` plumbing.
   - The handler should set `busy=true` for the duration of the `ui1_student_in_archive` check + any on-boarding step so the row click is locked against double-fire, and surface any error via the existing `setError` channel.

   **Step 4a — new Tauri command `ui1_student_in_archive` (v1.0.2):** add to `writer-ui/src-tauri/src/lib.rs`:

   ```rust
   /// Read-only archive-membership check. Returns true iff a `students`
   /// row exists for the given UID. Used by handleSelectFromSearch to
   /// decide whether to trigger sync_targeted_student before calling
   /// ui1_list_tutorials — see §8.7.
   ///
   /// Authority: contracts/archive_repository.json (read-only access via
   /// ArchiveRepository::student_exists, a new thin wrapper around
   /// `SELECT 1 FROM students WHERE uid = ?1`).
   #[tauri::command]
   fn ui1_student_in_archive(
       state: State<'_, WriterAppState>,
       student_id: i64,
   ) -> Result<bool, String> {
       let repository = state.open_archive()?;
       repository.student_exists(student_id)
           .map_err(|e| format!("archive membership check failed: {e}"))
   }
   ```

   Register `ui1_student_in_archive` in `tauri::generate_handler![…]` alongside `ui1_search_live_students` and the other UI1e commands. Add a new method `ArchiveRepository::student_exists(&self, uid: i64) -> Result<bool>` in `gel-core/src/archive_repository.rs`:

   ```rust
   /// Cheap existence check: SELECT 1 FROM students WHERE uid = ?1.
   /// Used by ui1_student_in_archive to gate the on-boarding decision
   /// (see plans/LIVE_STUDENT_SEARCH_PLAN_v1_0_2.md §8.7).
   pub fn student_exists(&self, student_uid: i64) -> Result<bool> {
       let exists: Option<i64> = self.connection
           .query_row(
               "SELECT 1 FROM students WHERE uid = ?1",
               [student_uid],
               |row| row.get(0),
           )
           .optional()?;
       Ok(exists.is_some())
   }
   ```

   This is a read-only query; no new write authority, no new state class, no contract amendment beyond adding the command to the `ui1_writer.json::initial_command_allowlist` (§4.2).
5. The class selector (`<select>`) remains available in the toolbar but is now labelled "Class (optional, tutorial history only)" and no longer gates the student browse — it only scopes `StudentOverview`'s tutorial history when a student is selected.
6. The `students` and `setStudents` state is removed entirely; `StudentOverview` continues to receive its `student` prop from the row clicked in the search pane (resolved by `studentUid`).
7. **Existing `doOpenNew(tutorialType)` and `doOpenRevision(tutorial)` handlers are unchanged** — they continue to be invoked from the `StudentOverview` buttons and the tutorial-history double-click, exactly as they are today for class-roster students. The search-selected student flows through the same `studentId` state, so no new handler is needed for New / amend; only the row-click handler (`handleSelectFromSearch`) is new.

### 6.3 `viewFormat.ts` additions

```ts
export const formatIsoDate = (iso: string | null): string =>
  iso ? iso : "—";

export const formatTimestamp = (rfc3339: string | null): string =>
  rfc3339 ? new Date(rfc3339).toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  }) : "—";
```

### 6.4 `styles/app.css` additions

A small block for `.live-search-pane`, `.live-search-controls`, `.live-search-picker-row`, and `.live-search-empty` — visually consistent with the existing `.student-list-pane` / `.student-grid` rules. No new design tokens; reuses existing palette.

---

## 7. Date filter contract (Rust-side)

The filter is enforced inside `ui1_search_live_students` after parsing, before IPC return. React never re-filters rows it has already received; changing a picker re-issues the search.

### 7.1 Inputs

| Field | Type | Meaning |
|---|---|---|
| `course_start_before` | `Option<NaiveDate>` | Row kept iff `row.course_start <= course_start_before` (or `row.course_start` is `None` AND we treat missing as "keep"; see §7.4) |
| `course_end_after` | `Option<NaiveDate>` | Row kept iff `row.course_end >= course_end_after` |

### 7.2 Defaults

When React sends `None` (or `""`, normalized to `None` by the wrapper):

- `course_start_before = tomorrow` (today + 1 day, in UTC)
- `course_end_after   = today` (UTC)

These two defaults together implement "currently enrolled" — any student whose course has already started (start ≤ tomorrow) and has not yet finished (end ≥ today).

### 7.3 Filter algorithm

```rust
fn passes_date_filter(
    row: &LiveStudentSearchRow,
    start_before: Option<NaiveDate>,
    end_after: Option<NaiveDate>,
) -> bool {
    let start_ok = match (row.course_start, start_before) {
        (Some(s), Some(ub)) => s <= ub,
        _ => true,   // missing row date OR no upper bound → keep
    };
    let end_ok = match (row.course_end, end_after) {
        (Some(e), Some(lb)) => e >= lb,
        _ => true,
    };
    start_ok && end_ok
}
```

### 7.4 Missing-date policy

Rows with `None` for `course_start` or `course_end` are **kept** (not excluded) under the filter, because the source table can omit a date for historical or transitional records. The anonymized capture shows all 30 rows have both dates, but the parser tolerates missing values. This policy is the most inclusive — the teacher can narrow further with the pickers, and the UI surfaces `—` for missing values so the teacher sees what was kept.

### 7.5 Invalid input handling

- React-side: an empty `<input type="date">` produces `""`, which the wrapper converts to `null` (so the Rust default applies).
- Rust-side: `parse_optional_iso_date` returns an `Err(String)` for a non-empty but unparseable string. The Tauri command surfaces the error directly; React displays it in the pane's `error` slot. The existing session remains valid and no POST is issued.

---

## 8. Privacy & security invariants

1. **POST body construction authority.** The `search=<term>` body is constructed by `reqwest::form(&[("search", term.trim())])` inside `GelSession::search_live_students`. React never builds a POST body; the existing `forbidden_command_capabilities` entry "POST payload construction/exposure" continues to hold because the new command does not expose that capability to the frontend.
2. **Email stripping.** Every parsed row passes through `strip_student_sensitive_fields` (existing helper, already invoked by `get_students` and `get_student_profile`) before leaving `GelSession::search_live_students`. The parser additionally strips emails at the `name` field granularity as defence-in-depth.
3. **Cookie ownership.** The cookie store remains inside the private `reqwest::Client` owned by `GelSession`. No cookie value crosses IPC. The existing `cookie_ownership` invariant is unchanged.
4. **Error redaction.** The existing `error_redaction_rule` ("Authentication errors must not include the supplied password, cookie values, serialized login form body or full response body") is extended by interpretation to cover the search POST: search-error diagnostics must not include the full response body. The HTTP status and a one-line reason are acceptable. The search *term* itself may be echoed in error messages because it is teacher-typed, not credential material — but only if it is short and not combined with other fields.
5. **Row identity immutability.** `student_uid` is added to `ui1_writer.json::draft_authority.immutable_from_frontend` (which already lists "student identity"). React treats `studentUid` as opaque and passes it unchanged to `ui1_open_new_draft`.
6. **No new write capability.** `ui1_search_live_students` is a read query. It is not a mutation, does not delegate to `live_submission_transport`, and does not touch the archive. The existing `forbidden_command_capabilities` list is unchanged in substance.
7. **Session expiry handling.** If `search_live_students` detects a login page (via the existing `is_login_page` helper), it sets `self.authenticated = false` and returns a structured error. The Tauri command surfaces this as a normal error; React treats it the same way it treats a 401 in `ui1_open_new_draft` (clears the search results and shows the login panel).
8. **NEW (v1.0.2): On-boarding precondition for browse and amend, gated on archive membership (NOT on empty tutorial list).** A search-selected student may not yet exist in the local archive (the recon4 evidence confirms some search-result UIDs are not in the archive until `sync_targeted_student` runs). The existing `ui1_list_tutorials` and `ui1_open_revision_draft` commands both read from the archive, so a never-synced student would show an empty tutorial list and would be unable to amend until the archive is populated. The React handler (`handleSelectFromSearch`, §6.2 step 4) on-boards the student into the archive **only when the new `ui1_student_in_archive(studentId: i64) -> bool` Tauri command returns `false`** — NOT on every empty tutorial list. This distinction is critical: an in-archive student with genuinely zero tutorials (Case A in §1) must NOT trigger a sync, because that would re-fetch the same empty list every time the teacher clicks the row. The archive-membership check is a cheap `SELECT 1 FROM students WHERE uid = ?1` query exposed via the new `ArchiveRepository::student_exists` method and the new `ui1_student_in_archive` Tauri command (chosen approach in v1.0.2 — see §6.2 step 4a for the Rust spec). The on-boarding itself uses Option A (`ui1_open_new_draft` + `ui1_discard_draft`) in v1.0.2 and migrates to Option B (a dedicated `ui1_sync_targeted_student` command) in LSS3. **This on-boarding step is a read-only archive mutation delegated to `RustArchiver`** — it is the same `sync_targeted_student` plumbing `ui1_open_new_draft` already uses, and is governed by the existing `archive_repository.json` contract. No new write authority is introduced.

---

## 9. Fixtures & test strategy

### 9.1 Fixture

- `gel-core/fixtures/live_student_search/raw/anonymized_report_sample.html` — a synthetic HTML fixture reconstructed from `gel_search_report_anonymized.json` (which is already anonymized — emails replaced with `email@email.com`, names with `Student_<hash>`). The fixture preserves the 8-cell row shape and the `/administration/studentmanagement/report/<uid>` link pattern. The fixture MUST also include the full jQuery DataTables chrome observed in production (§3.1.1):
  - `<select name="student-management_length">` with options `10/25/50/100` (default `10`)
  - `<div class="dataTables_info" id="student-management_info">` with text `Showing 1 to 10 of 30 entries`
  - `<div class="dataTables_paginate paging_two_button" id="student-management_paginate">` containing `<a class="paginate_disabled_previous" id="student-management_previous">` and `<a class="paginate_enabled_next" id="student-management_next">`
  This is required because the parser (§5.1) extracts `info_footer.total` from the `.dataTables_info` element, and the integration test (§9.3) drives the session walker which issues follow-up POSTs with `start=100` when `total_entries > 100`.
- `gel-core/fixtures/live_student_search/raw/anonymized_report_sample_page2.html` — a second-page fixture (rows 11–30) for the integration test, with the footer text `Showing 11 to 30 of 30 entries`.
- `gel-core/fixtures/live_student_search/raw/anonymized_report_sample_empty.html` — an empty-result fixture with footer text `Showing 0 to 0 of 0 entries`, no rows, and the `paginate_disabled_next` class on the `next` `<a>`. Used to test the empty-state path.
- `gel-core/fixtures/live_student_search/raw/anonymized_report_sample_never.html` — a one-row fixture where cell 7 is the literal string `never` (the no-tutorial edge case observed in the captured row 67). Used to test the tutor-cell fallback path.
- `gel-core/fixtures/live_student_search/expected/anonymized_report_sample.json` — the typed `LiveStudentSearchParseReport` projection expected from parsing the main fixture, including `info_footer: Some(LiveStudentSearchInfoFooter { start: 1, end: 10, total: 30, ... })`, `None` handling for any unparseable date, `absent: true` for the `(absent)` row, and `tutor_date: None, tutor_name: None, absent: false` for the `never` row.

### 9.2 Rust unit tests — `gel-core/tests/live_student_search.rs`

- `parses_all_30_rows_from_anonymized_fixture`
- `strips_email_from_name_cell` (asserts `name` field contains no `@` substring; uses the spaced cell walker so a cell like `<td><a>FirstName Surname</a>email@x.com</td>` produces `Student_<hash>` not `Student_<hash>email`)
- `parses_tutor_cell_with_absent_suffix` (the `17-03-2020(Louisa Stodd) (absent)` case → `{ date: Some(2020-03-17), tutor_name: Some(_), absent: true }`)
- `parses_tutor_cell_never` (the `never` case → `{ date: None, tutor_name: None, absent: false }`)
- `tolerates_missing_dates` (synthetic row with empty cells 4–7)
- `skips_row_with_non_numeric_uid_and_reports_malformed`
- `date_filter_keeps_currently_enrolled_by_default` (today/tomorrow)
- `date_filter_excludes_future_start`
- `date_filter_excludes_past_end`
- `date_filter_none_bounds_keep_all`
- `parses_info_footer_standard` (`Showing 1 to 10 of 67 entries` → `total: Some(67)`)
- `parses_info_footer_empty` (`Showing 0 to 0 of 0 entries` → `total: Some(0)`)
- `parses_info_footer_no_data_available` (`No data available in table` → `total: Some(0)`)
- `parses_info_footer_filtered_variant` (`Showing 1 to 10 of 67 entries (filtered from 200 total entries)` → `total: Some(67)`)
- `parses_info_footer_unparseable` (`Page 3 of 7` → `None`)
- `parses_info_footer_missing` (HTML with no `.dataTables_info` element → `report.info_footer: None`)
- `spaced_walker_separates_inline_anchor_and_text` (the recon3 glue bug regression test: `<td><a>Name</a>email</td>` produces `Name email`, not `Nameemail`)

### 9.3 Rust integration tests — `gel-core/tests/gel_session_search.rs`

- A mocked transport (or a fixture-only constructor on `GelSession` similar to the existing test seam used by `login_posts_only_to_login_then_read_surface_uses_get`) that returns the fixture HTML for `POST /administration/students`, and asserts:
  - `search_live_students("Rina")` (30-row fixture) issues exactly ONE POST (because `length=100` and `total_entries=30 ≤ 100`, the walker stops after page 1), returns `LiveStudentSearchResult { rows: 30, total_entries: Some(30), pages_fetched: 1 }`.
  - `search_live_students("Rin")` (154-row fixture spread across 2 pages of 100 + 54) issues TWO POSTs (first with `start=0`, second with `start=100`), returns `LiveStudentSearchResult { rows: 154, total_entries: Some(154), pages_fetched: 2 }`. The test verifies the second POST's form body contains `start=100`.
  - `search_live_students("Nonexistent")` (empty fixture, footer `Showing 0 to 0 of 0 entries`) issues ONE POST and returns `LiveStudentSearchResult { rows: 0, total_entries: Some(0), pages_fetched: 1 }`.
  - Calling `search_live_students` before `login` returns the `unauthenticated_read` error.
  - Calling `search_live_students` after the mocked transport returns a login page sets `authenticated = false`.
  - `capture_rate` (computed in the Tauri command, §5.4) equals `1.0` for the 30-row and 154-row cases, and `null` for the empty case. (This is asserted in the Tauri-command integration test, not here; included in §9.6.)

### 9.4 Frontend tests

- `writer-ui` typecheck (`tsc -p tsconfig.app.json --noEmit`) and `vite build` must succeed with the new component and types.
- A snapshot/behaviour test (optional, recommended): render `LiveStudentSearchPane` with a mocked `searchLiveStudents` and assert the AG Grid renders the expected columns and that clicking a row calls `onSelect` (not `onOnboard` — the pane selects, the parent acts).

### 9.5 Governance checker — `tools/check_ui1f_live_search.py`

A new Python checker (mirroring `tools/check_ui1e_safety.py`) that asserts:

1. `contracts/gel_read_only_session.json` contains `read_surface` entry with `id = live_student_search`, `method = POST`, `path_template = /administration/students`, and `network_authority.allowed_post_purposes` contains the new "School-wide student read query" string.
2. `contracts/ui1_writer.json` `contract_version == 15`, `initial_command_allowlist` contains BOTH `ui1_search_live_students` AND `ui1_student_in_archive`, `internal_gates` contains an entry with `id = UI1f`, and `layout.school_visible == true`.
3. `contracts/state_ownership.json` `contract_version == 24` and contains a state class with `id = live_student_search_results`.
4. `writer-ui/src-tauri/src/lib.rs` registers BOTH `ui1_search_live_students` AND `ui1_student_in_archive` in `tauri::generate_handler![…]` and exposes no other new command.
5. `writer-ui/src/api.ts` exposes BOTH `searchLiveStudents` AND `studentInArchive` wrappers and no other new `invoke` call.
6. The forbidden_command_capabilities list still contains "POST payload construction/exposure" and "generic HTTP/request URL".
7. **NEW (v1.0.1):** `writer-ui/src-tauri/src/lib.rs` defines `LiveStudentSearchResponse` with `rows`, `total_entries`, `info_footer_raw`, `pages_fetched`, and `capture_rate` fields (the governance wrapper, §5.4). The checker asserts the struct name and field names by parsing the Rust source; it does NOT execute Rust.
8. **NEW (v1.0.1):** `writer-ui/src/types.ts` exports `LiveStudentSearchResponse` with `rows`, `totalEntries`, `infoFooterRaw`, `pagesFetched`, and `captureRate` fields (§5.5). The checker asserts by parsing the TS source.
9. **NEW (v1.0.1):** `writer-ui/src/components/LiveStudentSearchPane.tsx` renders a governance badge element whose text content includes `captureRate` (§6.1). The checker asserts the component references `response.captureRate` (or destructured equivalent) somewhere in its render path.
10. **NEW (v1.0.2):** `gel-core/src/archive_repository.rs` defines a `pub fn student_exists(&self, student_uid: i64) -> Result<bool>` method. The checker asserts the method signature by parsing the Rust source.
11. **NEW (v1.0.2):** `writer-ui/src-tauri/src/lib.rs` defines `fn ui1_student_in_archive(state: State<'_, WriterAppState>, student_id: i64) -> Result<bool, String>`. The checker asserts the function signature by parsing the Rust source.

### 9.6 Extended workflow test — `gel-core/tests/ui1e_workflow_behavior.rs`

Add five mocked scenarios (or a sibling `ui1f_workflow_behavior` module) covering all three teacher actions from a search result, plus the two archive-membership edge cases:

**Scenario A — New tutorial from a search result (the v1.0.0/v1.0.1 case):**
- authenticate → `ui1_search_live_students("Rina", None, None)` returns a `LiveStudentSearchResponse` with `rows.len() == 30`, `total_entries == Some(30)`, `pages_fetched == 1`, and `capture_rate == Some(1.0)`. → select row → handler calls `ui1_student_in_archive(313350)` → returns `true` (UID 313350 is in the fixture archive) → `StudentOverview` renders → teacher clicks "New Standard" → `ui1_open_new_draft(313350, "standard")` returns a `DraftView` whose `student_uid` matches.
- Asserts `capture_rate == Some(1.0)` — the headline governance signal.
- Asserts `ui1_student_in_archive` was called once before `StudentOverview` rendered.
- Asserts NO `sync_targeted_student` on-boarding was triggered (the student is in the archive; Option A is not needed).

**Scenario B — Browse historic tutorials from a search result (the v1.0.2 case):**
- authenticate → `ui1_search_live_students("Rina", None, None)` returns the same response as Scenario A. → select row → handler calls `ui1_student_in_archive(313350)` → returns `true` → `StudentOverview` renders → `ui1_list_tutorials(313350)` returns the mocked tutorial history (e.g. 5 tutorials) → teacher scrolls the list without opening a draft.
- Asserts the tutorial list is non-empty for a previously-synced student (UID 313350 is in the fixture archive).
- Asserts NO draft is opened during this scenario (the browse-only path does not invoke `ui1_open_new_draft` for an in-archive student. If the student is NOT in the archive, it on-boards via `ui1_open_new_draft` + `ui1_discard_draft` — see Scenario D).
- Asserts `ui1_student_in_archive` was called once before `ui1_list_tutorials`.

**Scenario C — Amend an existing tutorial from a search result (the v1.0.2 case):**
- authenticate → `ui1_search_live_students("Rina", None, None)` returns the same response. → select row → handler calls `ui1_student_in_archive(313350)` → returns `true` → `StudentOverview` renders → `ui1_list_tutorials(313350)` returns 5 tutorials → teacher double-clicks tutorial #2 → `ui1_open_revision_draft(tutorial_id)` returns a `DraftView` with `origin: "revision"` whose `student_uid` matches.
- Asserts the revision path works identically for a search-selected student as for a class-roster student.
- Asserts the existing `pendingNavigation` discard guard intercepts the action if a draft is dirty (the guard is invoked because `ui1_open_revision_draft` discards the current draft — same as today).
- Asserts `ui1_student_in_archive` was called once before `ui1_list_tutorials`.

**Scenario D — Browse-only on-boarding for a never-synced student (the v1.0.2 edge case):**
- authenticate → `ui1_search_live_students("Rina", None, None)` returns the same response, including a row whose UID is NOT in the fixture archive (e.g. UID 470840, the captured row 67 with no tutorials). → select row → handler calls `ui1_student_in_archive(470840)` → returns `false` → `StudentOverview` renders in a "on-boarding…" state → handler invokes Option A: `ui1_open_new_draft(470840, "standard")` (which runs `sync_targeted_student` internally) followed by `ui1_discard_draft()` → handler calls `ui1_list_tutorials(470840)` → returns `[]` (the student now exists in the archive but has no tutorials) → `StudentOverview` shows "No tutorials yet".
- Asserts `ui1_student_in_archive` was called once before the on-boarding decision.
- Asserts the on-boarding step runs exactly once and the draft is discarded before any field edits.
- Asserts the `ui1_list_tutorials` call does NOT error (the student now exists in the archive even though they have no tutorials).
- Asserts the teacher can then click "New Standard" to write a tutorial for this never-previously-taught student, exactly as in Scenario A.

**Scenario E — In-archive student with genuinely zero tutorials (the v1.0.2 non-on-boarding case):**
- authenticate → `ui1_search_live_students("Rina", None, None)` returns the same response, including a row for an in-archive student with zero tutorials (e.g. UID 313351, a fixture-supplied student row with no `tutorial_identities` rows). → select row → handler calls `ui1_student_in_archive(313351)` → returns `true` → handler calls `ui1_list_tutorials(313351)` → returns `[]` → `StudentOverview` shows "No tutorials yet".
- Asserts `ui1_open_new_draft` was NOT called during this scenario (the student is in the archive; no on-boarding needed).
- Asserts `sync_targeted_student` was NOT called during this scenario (the archive is authoritative).
- Asserts the teacher can then click "New Standard" to write a tutorial for this in-archive-but-tutorial-less student, exactly as they would for a class-roster student with no tutorials.
- This scenario is the critical regression test for the v1.0.2 archive-membership-gated design: it proves the handler does NOT auto-sync on every empty `ui1_list_tutorials` result, which would re-fetch the same empty list every time the teacher clicks the row.

The `capture_rate == Some(1.0)` (or `capture_rate == None` for the empty-search variant) assertion is the single most important governance signal introduced by the recon4 evidence. A `capture_rate < 1.0` would indicate a parser or pager-walk defect and must fail the release gate.

These scenarios are added under the existing `ui1e_workflow_behavior` module (or a sibling `ui1f_workflow_behavior` module) so that the UI1e baseline is unchanged and UI1f carries the new evidence.

### 9.7 Strict exit target

- All existing UI1e checks still pass at PASS=45 SKIP=0 FAIL=0.
- New `ui1f_live_search` check (the Python governance checker above, §9.5) PASS — including the new assertions 7–9 for the `LiveStudentSearchResponse` struct and `captureRate` badge, AND the v1.0.2 assertions 10–11 for `ArchiveRepository::student_exists` and `ui1_student_in_archive`.
- New `live_student_search` and `gel_session_search` Rust test modules PASS — including the new footer-parser tests (§9.2) and the multi-page walker test (§9.3).
- New `ui1f_workflow_behavior` integration test PASS — all FIVE scenarios (A: New, B: browse, C: amend, D: browse-only on-boarding, E: in-archive zero-tutorials regression) including the `capture_rate == Some(1.0)` assertion and the `ui1_student_in_archive` membership-check assertions.
- `writer-ui` typecheck + `vite build` PASS.
- **TARGET STATUS: STRICT_ACCEPTED**
- Release gate remains PASS.

**The `capture_rate` assertion is the headline governance signal.** It is the field that turned the recon3 pagination miss (10 rows captured of 67 reported) from an invisible bug into a visible failure. Any future change that breaks the pager walker will fail this assertion and block the release.

**The `ui1_student_in_archive` membership check (v1.0.2) is the second headline governance signal.** Scenario E (in-archive student with genuinely zero tutorials) is the critical regression test: it asserts the handler does NOT auto-sync on every empty `ui1_list_tutorials` result, which would re-fetch the same empty list every time the teacher clicks the row. Any future change that breaks the membership-gated on-boarding decision will fail Scenario E and block the release.

---

## 10. Implementation sequence

The implementation is broken into ordered phases. Each phase is independently reviewable; later phases depend on earlier ones.

| # | Phase | Depends on | Deliverable |
|---|---|---|---|
| 1 | Contract amendments | — | Three JSON contracts amended, `contract_version` bumps, `governance/current-state.json` regenerated via `tools/generate_current_state.py`. |
| 2 | Parser + fixtures | 1 | `gel-core/src/live_student_search_parser.rs`, `gel-core/fixtures/live_student_search/{raw,expected}/anonymized_report_sample.{html,json}`, `gel-core/tests/live_student_search.rs` passing. |
| 3 | `GelSession::search_live_students` | 2 | New method on `GelSession`, `gel-core/tests/gel_session_search.rs` passing. |
| 4 | Tauri command `ui1_search_live_students` + `ui1_student_in_archive` | 3 | New commands in `writer-ui/src-tauri/src/lib.rs`, registered in `tauri::generate_handler![…]`, `LiveStudentSearchRowView` Serialize struct, `parse_optional_iso_date` helper, `ArchiveRepository::student_exists` method. |
| 5 | TS types + API wrapper | 4 | `writer-ui/src/types.ts` `LiveStudentSearchRowView` + `LiveStudentSearchResponse`; `writer-ui/src/api.ts` `searchLiveStudents` + `studentInArchive`. |
| 6 | React pane | 5 | `writer-ui/src/components/LiveStudentSearchPane.tsx`, `viewFormat.ts` helpers, `styles/app.css` additions. |
| 7 | `App.tsx` integration | 6 | Remove `studentSearch` state and the live-filter input; replace `StudentListPane` usage; add `handleSelectFromSearch` (selects the student for `StudentOverview`, on-boards via `ui1_open_new_draft` + `ui1_discard_draft` if an archive-membership check confirms the student is NOT in the archive). |
| 8 | Governance checker | 1, 4, 5 | `tools/check_ui1f_live_search.py`. |
| 9 | Workflow test extension | 7 | `gel-core/tests/ui1f_workflow_behavior.rs` (or extension of `ui1e_workflow_behavior.rs`). |
| 10 | Strict release gate | 1–9 | `tools/release_gate.py` PASS; immutable evidence written outside the source tree. |

---

## 11. Strict exit & release gate

UI1f strict acceptance is the gate. The target is:

- `ui1e_safety` PASS=45 SKIP=0 FAIL=0 (unchanged baseline).
- `ui1e_workflow_behavior` PASS (unchanged).
- `ui1f_live_search` (new governance checker) PASS.
- `live_student_search` parser unit tests PASS.
- `gel_session_search` integration tests PASS.
- `ui1f_workflow_behavior` PASS.
- `writer-ui` typecheck + `vite build` PASS.
- TARGET STATUS: `STRICT_ACCEPTED`.
- RELEASE GATE: `PASS`.
- Immutable evidence path: `ui1f-strict-evidence.json` (written outside the source tree, mirroring the `ui1e-strict-evidence.json` pattern recorded in `ui1_writer.json::ui1e.evidence`).

**Reproducible release impact:** `contracts/release_identity.json` is unchanged. No `Cargo.lock` or `package-lock.json` bumps are required (all dependencies — `scraper`, `chrono`, `regex`, `reqwest`, `ag-grid-community`, `ag-grid-react` — are already locked in the workspace). The release artifact identity (workspace + lockfiles) is preserved.

**AI governance protocol impact:** `governance/agent-protocol/ai-governance-protocol.v1.1.json` is unchanged. The new feature is a normal internal gate, not a new phase boundary. The agent-run-result schema remains valid.

---

## 12. Risks & open questions

1. **~~Pagination~~ RESOLVED (2026-09-05).** The original risk was: "the anonymized capture shows `resultCount: 30`; the live server may cap results at 30 (or 50) per page and require a `?page=N` query for additional rows." Live reconnaissance (`gel_student_search_recon4.js`, captured 2026-09-05T11:39:45Z, 230 rows across 4 searches) confirmed the server renders a **jQuery DataTables**-paginated HTML table with a configurable page-size `<select>` (10/25/50/100) and a two-button pager. The Rust session walker (§5.2) issues follow-up POSTs with `length=100` and `start=<offset>`, stopping when `total_entries` is reached. `capture_rate` (§5.4) is the governance signal that proves the walker captured every row DataTables reported. The recon4 script demonstrated `capture_rate == 1.0` on all four configured searches (67, 154, 9, and 0 rows respectively). This risk is now closed; the residual follow-up task (LSS2) is to expose `capture_rate` through the UI as a governance badge (§6.1).
2. **Tutor-cell regex edge cases.** The cell `17-03-2020(Louisa Stodd) (absent)` and the cell `07-03-2018(Liam Wallington)` are the two observed shapes. Other shapes (multiple tutor names, dates without parens, tutor names containing parens) are possible. **Mitigation:** the parser uses a permissive regex with named groups and falls back to `None` for any unparseable component rather than failing the whole row. The `skipped_malformed` counter surfaces drift. **UPDATE (2026-09-05):** the `never` shape (a student with no tutorials yet) was observed in the captured row 67 and is now a third recognised shape (§3.2, §5.1).
3. **Date format drift.** The source uses `dd-MM-yyyy`. If the GEL server ever switches to `yyyy-MM-dd` (unlikely — Drupal admin pages are locale-stable), the parser will return `None` for every date and the default filter will keep all rows (per §7.4). This is a safe degradation but will look like "no filtering". **Mitigation:** add a fixture that proves both formats are tolerated (parse both, prefer the locale format), or assert the locale in a regression test.
4. **Search term PII.** A teacher may type a student's full name as the search term. The term itself is not logged. Error messages may echo the term only as a short, isolated string (§8.4). **Mitigation:** the redaction rule is documented; the implementation must not log the term to any persistent channel.
5. **Rate limiting.** `GelSession::throttle()` already exists and is called before every request. The search uses the same throttle. A teacher mashing the Search button is throttled at the same rate as archive sync. **Mitigation:** the React pane also disables the Search button while `querying=true` (UI-level debounce), so the throttle is a backstop, not the primary control. **UPDATE (2026-09-05):** the walker now issues one POST per page (§5.2), so a 154-row search makes 2 POSTs (throttled between them). The recon4 script's 4-search run made 1+2+1+0 = 4 POSTs total and completed cleanly.
6. **School-visible scope change.** `ui1_layout_hybrid.json::school_visible` was `false` under UI1e; UI1f flips it to `true`. This is a deliberate visible-authority change. **Mitigation:** the change is called out explicitly in §4.2 and surfaced in the new governance checker (`school_visible == true`).
7. **Row identity conflict with archive.** A student found via school-wide search may already exist in the local archive (via a previous class roster sync). `ui1_open_new_draft` already handles this case — it reuses the archive's student row if present and otherwise calls `sync_targeted_student`. **Mitigation:** no change required; the existing path is the correct one. The new feature only changes *how* a student is selected, not how they are persisted.
8. **Empty results vs. error.** A successful search with zero matches returns `Ok(LiveStudentSearchResponse { rows: [], total_entries: Some(0), capture_rate: None, ... })`; the UI shows "0 matches" and the badge shows `0 matches`. A failed search (HTTP 5xx, login redirect, network error) returns `Err` and the UI shows the error in the pane's `error` slot. The two states are distinct and the UI must not conflate them. **Mitigation:** the pane's `error` state is separate from the `results.length === 0` state; the design uses two distinct visual treatments.
9. **Concurrent search + draft.** If a teacher starts a draft (dirty) and then issues a search, the search does not touch the draft (different state classes). Selecting a search result row selects the student for `StudentOverview` — this does NOT discard the current draft, because the draft is only discarded when the teacher explicitly clicks New or double-clicks a tutorial in `StudentOverview`. **Mitigation:** the existing `pendingNavigation` discard guard in `App.tsx` continues to intercept the New / amend actions exactly as it does today for class-roster students; `handleSelectFromSearch` does not route through the guard because it does not open a draft. This is a deliberate change from the v1.0.1 design, which auto-opened a draft on row click and therefore needed the guard; v1.0.2 separates selection from action, so the guard is only triggered when the teacher actually requests a draft-replacing action.
10. **NEW (2026-09-05): capture_rate as a hard release-gate signal.** The `capture_rate` field (§5.4) is the single most important governance signal introduced by this revision. The strict-release-gate checker (§9.7) asserts `capture_rate == 1.0 || capture_rate == None` in the workflow test. A `capture_rate < 1.0` would indicate either (a) a parser bug (some rows failed to parse and were silently dropped from the Vec without incrementing `skipped_malformed`), or (b) a pager-walk bug (the walker stopped before reaching `total_entries`). Both are release-blocking defects. **Mitigation:** the assertion is in §9.7; the badge in §6.1 surfaces a partial-capture failure to the teacher immediately, even before the release gate runs.
11. **NEW (v1.0.2): LSS3 follow-up — dedicated `ui1_sync_targeted_student` command.** v1.0.2 on-boards a never-synced search-selected student by reusing `ui1_open_new_draft` + `ui1_discard_draft` (Option A in §6.2 step 4). This works without a new Tauri command but is inelegant — it spins up a draft lifecycle only to throw it away. LSS3 should add a dedicated `ui1_sync_targeted_student(student_id: i64) -> Result<(), String>` Tauri command that invokes the existing `sync_targeted_student` plumbing directly, without opening a draft. This requires: (a) a new entry in `ui1_writer.json::initial_command_allowlist`, (b) a new entry in `contracts/state_ownership.json` if the on-boarding step produces new presentation state, (c) a new governance-checker assertion in §9.5. The contract amendment surface is small and the implementation is a thin wrapper around existing `RustArchiver` plumbing. **Mitigation:** Option A is acceptable for v1.0.2 because the draft is discarded before any field edits, so there is no IPC payload cost and no semantic drift; LSS3 is a cleanliness improvement, not a correctness fix.

---

## 13. Summary

UI1f adds a single governed POST read-query (`POST /administration/students` with `search=<term>`, optionally `length=100` and `start=<offset>` for jQuery DataTables pagination), parses the returned HTML page in Rust — extracting both the result rows and the DataTables info-footer total — walks the pager server-side when `total_entries > PAGE_SIZE`, applies a Rust-side default date filter ("currently enrolled"), and renders the typed rows in an AG Grid that replaces the class-roster live filter. **Selecting a search result row makes the student a first-class student in `StudentOverview`** — the teacher can then take any of the three existing actions (New / browse historic / amend) exactly as they would for a class-roster student, because the existing `ui1_open_new_draft`, `ui1_list_tutorials`, and `ui1_open_revision_draft` commands all take a `studentId` and do not require a class context. A never-synced search-selected student is on-boarded into the archive via the existing `sync_targeted_student` plumbing (Option A: `ui1_open_new_draft` + `ui1_discard_draft` in v1.0.2; LSS3 will add a dedicated `ui1_sync_targeted_student` command). Three contracts are amended (`gel_read_only_session` v3, `ui1_writer` v15 with `school_visible: true`, `state_ownership` v24 with `live_student_search_results`). No new write capability is introduced; React remains presentation-only; cookies and student emails remain private to Rust.

**The headline governance signal introduced in v1.0.1 is `capture_rate = rows.len() / total_entries`** (§5.4), surfaced through the Tauri command, the React pane badge (§6.1), the governance checker (§9.5), and the strict release gate (§9.7). Live evidence from `gel_student_search_recon4.js` (230 rows across 4 searches, `captureRate: 1.0` on every non-empty search) confirms the walker design captures every row DataTables reports. **The v1.0.2 design change is the separation of selection from action** — the pane selects, the teacher acts via `StudentOverview` — which makes a search-selected student indistinguishable from a class-roster student for all three downstream actions and removes the v1.0.1 need for the dirty-draft guard on row click. **The v1.0.2 archive-membership signal (`ui1_student_in_archive`) gates the on-boarding decision unambiguously**: an in-archive student with zero tutorials (Case A) does NOT trigger a sync, while a never-synced student (Case B) does — preventing the wasteful re-fetch loop that would otherwise occur every time the teacher clicks a genuinely-tutorial-less but in-archive student. The strict release gate is extended with one new governance checker and FIVE workflow-test scenarios (A: New, B: browse, C: amend, D: browse-only on-boarding, E: in-archive zero-tutorials regression), targeting `STRICT_ACCEPTED` with the UI1e baseline preserved.
