# UI1c — Complete semantic forms plan v1.0

**Evaluation:** APPROVED WITH AMENDMENTS, pending strict acceptance of the current `ui1-hybrid` baseline.

UI1c completes the Initial, Standard and Final editors without expanding GEL-write or archive-write authority. React remains presentation-only and all semantic mutations remain Rust-owned.

## Required amendments before implementation spreads

1. **Initial course type:** introduce an explicit Rust semantic `InitialCourseType` (`HSP`, `G21`, `G15`) and a lossless adapter to Initial teacher-comments storage. Unknown historical text must be preserved until explicitly replaced.
2. **Aims hotlist:** preset text is assistance content, not semantic authority. It must come from an explicitly curated/versioned bundled JSON source; otherwise only the direct Aims editor ships.
3. **Structured validation:** replace UI parsing of string failures with a Rust DTO carrying stable code, semantic field, severity, message and optional prior/candidate values.

## Internal gates

- **UI1c0 — Contract and option-domain closure.** Applicability matrix, Rust option projections, Initial course-type adapter, structured validation issues, Aims hotlist authority, New-only same-role regression rules.
- **UI1c1 — Common editor framework.** Type-aware common components and field-level validation presentation.
- **UI1c2 — Standard.** Absent; seven self-assessment groups; Aims; teacher comments.
- **UI1c3 — Initial.** Four Initial skill levels and HSP/G21/G15; existing GEL exam fields remain hidden but must be preserved unchanged unless separately authorized later.
- **UI1c4 — Final.** Paired Initial/current four-skill fields, optional Reading, teacher comments and additional comments.
- **UI1c5 — Integrated validation/release.** Same-role New regression protection plus complete UI1c acceptance.

## Regression rule

Regression protection applies to **New drafts only** and compares only the same canonical semantic field-role against the latest authoritative source. Initial/current roles are never compared to each other and one skill is never used as evidence for another. Revision editing is not compared against later tutorials.

## Release requirement

Implementation may begin only after `ui1-hybrid` passes strictly. UI1c final acceptance requires the entire accepted hybrid baseline plus dedicated UI1c contract, semantic-validation and frontend-form checks, all with `SKIP=0 FAIL=0`. The numerical check count is intentionally not frozen until UI1c0 establishes the executable check set.
