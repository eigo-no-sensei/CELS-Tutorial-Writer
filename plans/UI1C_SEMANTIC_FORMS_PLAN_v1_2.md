# UI1c Semantic Forms Plan v1.1

**Status:** UI1c0 implemented, pending strict acceptance.  
**Prerequisite:** `ui1-hybrid` strictly accepted at `PASS=23 SKIP=0 FAIL=0`.  
**Current acceptance target:** `ui1c` → `PASS=26 SKIP=0 FAIL=0`.

## GRI implementation dependency

UI1c0 semantic authority is implemented, but UI1c1 is now conditional on the GRI0–GRI5 reproducible-release boundary. The current release scope is `gri`. It requires one root Rust workspace lock, `writer-ui/package-lock.json` with `npm ci`, generated non-authoritative current-state/lock projections, semantic evidence classification, source/package intake, portable CI, immutable strict target-host evidence outside the source tree, and no-rebuild archive verification.

This development snapshot intentionally reports dependency-lock state as **INCOMPLETE** because this sandbox has no Cargo toolchain/network. No lockfile is fabricated. On the target development host, run `python tools/generate_dependency_lockfiles.py`, review/commit both locks, regenerate governance projections, then run the strict GRI gate with `--evidence-out` outside the repository. **UI1c1 must not begin before that strict GRI acceptance.**


## Authority

Executable contracts/tests remain authoritative over this plan. React is presentation-only; `rust_semantic_form` owns semantic field applicability, option domains, semantic validation, Initial course-type mapping and New level-regression rules. `writer_tauri_app_service` owns only the ephemeral draft container and safe DTO projection.

## UI1c0 — implemented contract/domain closure

UI1c0 establishes the contracts required before complete form rendering spreads:

- Every UI1c semantic field is classified for Standard, Initial and Final as `editable`, `read_only`, `hidden_preserved` or `inapplicable`.
- CEFR, assessment and Initial course-type option domains are Rust-owned and projected to React in `DraftFormContractView`.
- Initial course type is represented by `InitialCourseType` (`HSP`, `G21`, `G15`) and maps explicitly to Initial `teacher_comments`; unknown nonblank historical values are preserved losslessly until an explicit course-type replacement.
- Existing Initial exam fields remain hidden-preserved and have no UI1c typed edit variant.
- `DraftValidationIssue` supplies stable code, semantic field, severity, message and optional prior/candidate values; React must not infer field identity by parsing strings.
- Aims assistance is explicitly unavailable because no curated/versioned preset source has been authorized. Direct Aims editing remains planned for UI1c2.
- New drafts carry a Rust-owned `LevelRegressionBaseline` derived from the N2c latest authoritative source. Regression comparison is same-field/same-role only; it never compares Initial with current roles, one skill with another, or Revision against later tutorials.
- No GEL tutorial-write, archive-write or persistent tutorial-draft capability is introduced.

## UI1c internal sequence

1. **UI1c0 — Contract and option-domain closure:** implemented, strict acceptance pending.
2. **UI1c1 — Common type-aware editor framework:** planned, authorized only after the 26-check UI1c gate passes.
3. **UI1c2 — Standard form:** Absent, seven assessment groups, Aims, Teacher Comments.
4. **UI1c3 — Initial form:** four Initial skills and governed HSP/G21/G15 selector while preserving hidden exam state.
5. **UI1c4 — Final form:** paired Initial/current skills, optional Reading, Teacher Comments and Additional Comments.
6. **UI1c5 — Integrated validation and release:** complete semantic-form regression suite and strict acceptance.

## UI1c0 release gate

The `ui1c` scope freezes the accepted 23-check `ui1-hybrid` baseline and adds:

- `ui1c_forms_contract`
- `ui1c_semantic_validation`
- `ui1c_frontend_forms`

Strict target:

```text
PASS=26 SKIP=0 FAIL=0
RELEASE GATE: PASS
```

Portable skips are allowed only for checks explicitly classified as environment/platform dependent. Contract, semantic, deterministic unit and frontend no-authority failures remain failures.

## UI1c1 authorization condition

UI1c1 must not begin until the UI1c0 implementation is strictly accepted with `PASS=26 SKIP=0 FAIL=0`. The accepted contracts then become the implementation boundary for the full type-aware editor framework.
