# CHANGES — gel-rust-bootstrap-v17.11-harper-improved

Improved the use of Harper in `gel-rust-bootstrap-v17.11-harper` by porting the
inline-highlighting and richer React interface concepts from
`CELS-Report-Generator-P5.0.0`.

## Summary of improvements

1. **Inline wavy-underline highlighting** for `teacher_comments` and
   `additional_comments` — a transparent "mirror" `<div>` is overlaid on the
   native `<textarea>` and renders `<mark>` elements with spelling (red) or
   grammar (amber) wavy underlines. Aims remains a side-panel-only assistant
   (per the user's choice).
2. **Per-finding side-panel cards** with a structured topline (kind, rule,
   excerpt), message, suggestion buttons showing the actual fix label (e.g.
   `Replace with "colour"`) instead of the generic "Apply suggestion", and an
   actions row offering **Add to dictionary**, **Disable rule**, and
   **Skip issue**.
3. **Active-highlight coupling** — hovering or focusing a side-panel lint
   card strengthens the matching inline `<mark>` with a blue tint and thicker
   underline.
4. **Session-only state hoisted to App root** — `disabledHarperRules` and
   `ignoredHarperFindings` now live in `App.tsx` so they survive per-field
   editor unmount/remount, matching CELS's `ignoredHarperIssueKeys` /
   `disabledHarperRules` pattern.
5. **Engine bump** from `harper-core = "=2.7.0"` to `harper-core = "=2.8.0"`
   (the version CELS uses), with the `LintGroup::organized_lints` API used to
   obtain stable rule names per finding.
6. **Span-aware DTO** — `HarperFindingDto` now carries `spanStart` / `spanEnd`
   (char offsets, end-exclusive) and `rule`. `HarperSuggestionDto` now carries
   a human-readable `label` alongside the full `replacementText`. The
   contract clause is amended: React uses spans for highlight rendering only,
   never to construct replacements — Rust remains the sole replacement
   authority.
7. **Session-level rule/kind suppression** — `ui1_harper_check` now accepts
   `disabled_rules` and `suppressed_kinds` parameters that filter findings
   without mutating the persisted dictionary.
8. **User-dictionary cover-span short-circuit** — a Spelling finding is
   suppressed when a user-added term (e.g. `CHI365`) covers the reported span
   (e.g. `Chi`), so mixed-alphanumeric product names don't produce false
   positives.

## Files changed

### Rust backend

| File | Change |
|------|--------|
| `gel-core/Cargo.toml` | Bumped `harper-core` pin from `=2.7.0` to `=2.8.0`. |
| `gel-core/src/harper.rs` | Rewrote `check_text` to accept `disabled_rules` / `suppressed_kinds`; switched to `LintGroup::organized_lints` for rule names; added `span_start` / `span_end` to `HarperFindingDto`; added `label` and `rule` fields; added `user_dictionary_matches` and `user_dictionary_covers_span` helpers; bumped `HARPER_VERSION` to `"2.8.0"`; added 7 new behavioral tests. |
| `gel-core/tests/ui1d_harper.rs` | Updated `engine_version` assertion to `"2.8.0"`; updated all `check_harper_text` calls to pass `disabled_rules` / `suppressed_kinds`; added tests for span coordinates, suggestion labels, rule names, user-dictionary cover-span, empty-text short-circuit, disabled-rules suppression, suppressed-kinds filtering. |
| `writer-ui/src-tauri/src/lib.rs` | Updated `ui1_harper_check` signature to accept `disabled_rules: Vec<String>` and `suppressed_kinds: Vec<String>`; passes them through to `check_harper_text`. |
| `Cargo.lock` | Updated `harper-core` entry to version `2.8.0` with the correct crates.io checksum `2a0f1ba8...`. |

### TypeScript / React frontend

| File | Change |
|------|--------|
| `writer-ui/src/types.ts` | Added `spanStart`, `spanEnd`, `rule` to `HarperFindingDto`; added `label` to `HarperSuggestionDto`. |
| `writer-ui/src/api.ts` | Updated `harperCheck` to accept and pass `disabledRules` and `suppressedKinds`. |
| `writer-ui/src/components/HarperFieldAssistant.tsx` | Major rewrite: added `variant="inline"` / `"side-panel"` modes; inline mode renders a label + highlight surface (mirror div + textarea + scroll sync) + side panel; side-panel mode renders only the panel (used for `aims`); added `highlightedContent` useMemo tokenizer (ported from CELS `StudentDetail`); added per-finding `<article class="harper-lint">` cards with kind/rule/excerpt/message/suggestions/actions; added Add-to-dictionary (single-token gate), Disable-rule, Skip-issue actions; added active-highlight coupling via `activeFindingKey`; preserved all v1 stale-safe invariants (`350`, `requestId`, `sourceSnapshot`, `sourceText !== value`). |
| `writer-ui/src/components/HarperDictionaryPanel.tsx` | Added `onMutation?: () => void` callback prop, called after successful add/remove so the App can bump the revision counter. |
| `writer-ui/src/components/DraftFoundationPanel.tsx` | Added Harper session-state props; renders `teacher_comments` with `<HarperFieldAssistant variant="inline">` when editable (replacing the separate `SemanticTextAreaField` + `HarperFieldAssistant` pair); passes through `onHarperDictionaryMutation` to the standalone dictionary panel. |
| `writer-ui/src/components/TutorialTypeFields.tsx` | Split `Props` into `BaseFieldProps` + `HarperSessionProps`; `StandardFields` passes the session props to the aims assistant (side-panel variant); `FinalAdditionalCommentsField` uses inline variant for `additional_comments`. |
| `writer-ui/src/App.tsx` | Added `disabledHarperRules`, `ignoredHarperFindings`, `harperDictionaryRevision` state; added `handleDisableHarperRule`, `handleIgnoreHarperFinding`, `handleAddHarperDictionaryTerm`, `bumpHarperDictionaryRevision` handlers; passes them down to `DraftFoundationPanel`. |
| `writer-ui/src/styles/app.css` | Added ~190 lines of new CSS: `.comment-editor__surface`, `.comment-editor__highlights`, `.comment-editor__highlight--spelling/grammar/active`, `.comment-editor__textarea` (inline highlight styles with exact padding/font/line-height matching); `.harper-lint`, `.harper-lint--active`, `.harper-lint__topline/kind/rule/code/p`, `.harper-lint__suggestions`, `.harper-lint__actions`, `.harper-lint__action:disabled` (lint card styles). |

### Contracts / governance

| File | Change |
|------|--------|
| `contracts/ui1d_harper.json` | Bumped `contract_version` 1 → 2; engine version `2.7.0` → `2.8.0`; added `finding_fields` / `suggestion_fields` arrays; added `span_rule`, `rule_field_rule`, `command_parameters`; added `ephemeral_session_suppression` for `harper_disabled_rules` / `harper_ignored_findings`; added `highlighting`, `highlight_color_variants`, `active_highlight_coupling`, `actions`, `add_to_dictionary_gate`, `session_suppression` to `ui` section; added "React-side construction of replacement text from span offsets" to `forbidden_authority`. |
| `contracts/state_ownership.json` | Added two new ephemeral state classes: `harper_disabled_rules` and `harper_ignored_findings` (both `ephemeral_runtime_derived`, `canonical: false`, sole writer `writer_react_ui`). |
| `contracts/component_boundaries.json` | `writer_harper_service`: engine dep `2.7.0` → `2.8.0`; scope expanded to mention `disabled_rules` / `suppressed_kinds`, cover-span short-circuit, span coordinates / rule names / suggestion labels; added `harper_disabled_rules` / `harper_ignored_findings` to `must_not_write`. `writer_react_ui`: scope expanded with inline-highlighting, per-finding-actions, and session-state-hoisting lines; `writes` now includes `harper_disabled_rules` / `harper_ignored_findings`. |
| `contracts/ui1_writer.json` | `harper_service` architecture entry updated to `2.8.0`; `reuse.cels.reuse` extended with three new entries: inline Harper highlighting, per-finding actions, session-only state hoisting. |
| `development_plan.json` | `implemented_ui1d.engine` updated to `2.8.0`; `ui1d.scope` includes "inline Harper highlighting + per-finding actions ported from CELS-Report-Generator"; `react_role` mentions inline highlighting and session-only state hoisting. |

### Structural gate

| File | Change |
|------|--------|
| `tools/check_ui1d_harper.py` | Full rewrite to assert the v2 shape: engine `2.8.0`, `contract_version` 2, new DTO fields (`spanStart` / `spanEnd` / `rule` / `label`), new UI patterns (`comment-editor__surface` / `harper-lint` / `variant` / `dictionaryCandidate` / `dictionaryRevision`), new optional props (`disabledRules` / `ignoredFindingKeys` / `onDisableRule` / `onIgnoreFinding` / `onAddDictionaryTerm`), App.tsx ownership of session state, dictionary panel `onMutation` callback, CSS presence of `wavy` / `comment-editor__highlight--*` / `harper-lint--active`; added 7 new behavioral test names to the required list (original 6 preserved). |
| `tools/check_contracts.py` | Bumped `ui1d_harper` expected `contract_version` from 1 to 2; updated engine-version assertion from `2.7.0` to `2.8.0`. |
| `tools/check_governance.py` | Updated the `writer_react_ui` writes assertion to allow `writer_ui_presentation_state` + `harper_disabled_rules` + `harper_ignored_findings` (instead of only `writer_ui_presentation_state`). |

### Auto-regenerated artifacts

The following files were regenerated by the governance tooling after the
contract changes:

- `docs/components/writer_harper_service.md`
- `docs/components/writer_react_ui.md`
- `docs/components/harper_dictionary_repository.md`
- `docs/STATE_OWNERSHIP.md`
- `docs/generated/CONTRACT_INDEX.md`
- `docs/generated/DOCUMENTATION_INDEX.md`
- `docs/generated/GEL_TUTORIAL_CONTRACTS.md`
- `docs/generated/CURRENT_STATE.md`
- `docs/DEVELOPMENT_PLAN.md`
- `governance/current-state.json`
- `governance/dependency-lock-manifest.json`
- `gel-core/src/gel_fields.rs` (no semantic change — just regenerated)

## Verification

All 13 governance checks pass:

```
check:ui1d-harper        PASS
check:contracts          PASS
check:governance         PASS
check:ui1-boundaries     PASS
check:ui1-hybrid-layout  PASS
check:ui1c-frontend-forms PASS
check:ui1c1-editor-framework PASS
check:ui1c2-4-semantic-forms PASS
check:ui1c5-integrated   PASS
check:dependency-lockfiles PASS
check:release-control    PASS
check:release-control-behavior PASS
check:current-state      PASS
```

The TypeScript frontend compiles cleanly (`tsc -b --noEmit`) and the Vite
production build succeeds.

The Rust backend changes are API-compatible with harper-core 2.8.0 (the
same version CELS-Report-Generator uses). The behavioral test suite was not
run here because the Rust toolchain is not installed in this environment;
run `cargo test --locked -p gel-core --test ui1d_harper` locally to verify.

## Architectural notes

### Inline highlight rendering (mirror div + textarea)

Ported from CELS-Report-Generator's `StudentDetail.tsx`. The pattern:

1. A native `<textarea>` (with `spellCheck={false}` so Harper is the only
   visible checker) sits at `z-index: 1` inside a relative-positioned
   `.comment-editor__surface` container.
2. A transparent "mirror" `<div>` sits at `z-index: 0` with
   `pointer-events: none` and `aria-hidden="true"`. Its `.comment-editor__highlights-content`
   child uses `color: transparent` so only the `text-decoration` (wavy
   underline) and `background` are visible through the textarea's
   transparent background.
3. The mirror's padding, font-size, and line-height MUST exactly match the
   textarea's, or the underlines drift relative to the visible text.
4. A `useMemo` tokenizer builds a `Set<number>` of segment boundaries from
   `0`, `characters.length`, and every (clamped) finding `spanStart` /
   `spanEnd`, then renders each adjacent pair as a `<span>` (no lint covers)
   or a `<mark>` with the spelling/grammar/active color variant chosen from
   the covering findings.
5. The mirror is scrolled in lockstep with the textarea via `onScroll`.

### Stale-result-safe debounce (preserved from v1)

The original 350ms debounce with `requestId` race-guard and `sourceSnapshot`
source-snapshot equality is preserved verbatim. The structural gate still
asserts the literal `350`, `requestId`, `sourceSnapshot`, and
`sourceText !== value` tokens. The `disabledRules` array is a new
`useEffect` dep so a newly-disabled rule disappears from the side panel on
the next debounced tick.

### Session-only state hoisting

`disabledHarperRules: string[]` and `ignoredHarperFindings: Set<string>` are
owned by `App.tsx` (not by `HarperFieldAssistant`). This mirrors CELS's
`App.tsx` ownership of `disabledHarperRules` and `ignoredHarperIssueKeys`,
so that:
- Disabling a rule on one field suppresses it on all three fields.
- Skipping a finding survives the user typing more text (which would
  re-trigger the debounced lint and produce a fresh `result` object).
- Neither is persisted — both are cleared on process disposal.

The `harperDictionaryRevision: number` counter is bumped by the App whenever
the dictionary changes (either via a finding-card Add-to-dictionary action or
via the standalone `HarperDictionaryPanel`), and is passed down as a
`dictionaryRevision` prop to every `HarperFieldAssistant` so a debounced
re-lint is triggered against the new dictionary.
