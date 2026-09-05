# GEL semantic tutorial form model

> **Authority note:** GEL field IDs, type codes, applicability, source anomalies, semantic draft rules, collision authority and offline POST round-trip behaviour are governed by `contracts/*.json`, especially `tutorial_form_semantics.json`, `reconciliation_authority.json` and `offline_post_round_trip.json`. This document is explanatory and must not override those executable contracts.

## Boundaries

Historical revision construction is intentionally staged:

```text
GEL tutorial-list API identities + summary source states
    ↓
Rust reconciliation
    ↓
HistoricalStateAuthority
    ↓
normalized ArchivedTutorial + validated edit form
    ↓
build_revision_form_state()
    ↓
TutorialFormState
    ↓
validate_semantic_form_state()
    ↓
build_tutorial_post_payload()   offline only
```

The edit-form side remains:

```text
raw GEL edit HTML
    ↓
EditFormState
    ↓
validate_edit_form()
    ↓
ValidatedEditFormState
```

Missing/malformed applicable controls fail at C1. Invalid semantic type/origin state fails at C2. Unproven historical state ownership fails at C3. C4 then requires the complete Revision state to serialize to an exact independently reconstructed GEL successful-control map. None of these layers has network write authority.

## Identity is separate from historical source state

`tutorial_id` from GEL's tutorial-list API is canonical historical identity. `(student_uid, tutorial_ts, tutorial_type)` is only a locator/reconciliation key.

A same-timestamp collision can therefore contain multiple canonical tutorial IDs and multiple captured summary source states. C3 does not create a fictitious ID↔state association by list order.

For collision timestamps:

```text
API tutorial identities       captured summary states
        │                              │
        └──────── collision group ─────┘
                       │
                       ├─ identical_state
                       ├─ divergent_state
                       └─ incomplete_evidence
```

Collision candidates stay owned by the group. `PairedTutorial.summary` is populated only for a proven non-collision association.

## Historical state authority

`ArchivedTutorial` now carries explicit `HistoricalStateAuthority`.

Revision-by-ID is permitted only for:

- `proven_per_tutorial`;
- `shared_identical_collision`.

It is blocked for:

- `ambiguous_divergent_collision`;
- `incomplete_collision_evidence`;
- `ambiguous_collision_unknown`;
- `unmatched_source_state`.

The `ambiguous_collision_unknown` state is important for the current legacy v4.9 SQLite shape. A row marked `collision_ambiguous` contains preserved data, but the row itself cannot prove whether its normalized summary values belong to that specific tutorial ID. Until D1 persists collision kind and source-state association explicitly, such a row fails closed for revision.

## Identical-state collisions

An identical-state collision has equal non-zero API and summary counts and all candidate states are equivalent under the governed state comparison:

```text
ttype_raw + normalized summary fields
```

Rendering labels and source URLs are excluded from this equality because they locate/describe source entries rather than distinguish normalized historical content.

All canonical tutorial IDs remain separate. Revision may use a representative shared state only because every candidate state is equivalent. The source-entry association itself remains ambiguous and must not be rewritten as proven ownership.

## Divergent-state collisions

When candidate source states differ, no per-ID state is authoritative. `revision_state_for(tutorial_id)` fails with `DivergentCollision`, and `build_revision_form_state()` also refuses an `ArchivedTutorial` carrying divergent/unknown blocked authority.

The observed divergent fixture has two IDs at one timestamp and two summary states differing in absence. The timestamp-only print/edit route resolves one state, but that route is keyed only by student+timestamp and therefore cannot discriminate which canonical tutorial ID owns that state. It remains group-level evidence.

## Explicit draft origin

`TutorialFormState` represents origin as:

```text
DraftOrigin::Revision { source, source_teacher_id }
DraftOrigin::New { prepopulation_source, form_teacher }
```

A Revision always identifies the historical tutorial being reconstructed and preserves its historical teacher. A New draft is structurally different: its optional prepopulation source is provenance only, its teacher authority comes from the validated New form, and it has no authoritative created GEL identity/timestamp before future server readback.

## One editable representation per semantic value

C2 remains unchanged:

- `overall_level: Option<CefrLevel>` is the sole editable overall level; raw GEL spelling is provenance only.
- `aims: String` is the sole editable Aims value; historical editor HTML is provenance only.
- POST serialization never uses provenance as a semantic fallback.
- historical `absent` remains summary/archive-authoritative for a revision, subject to C3 first establishing that the archived state is revision-authoritative for the selected ID.

## Applicability

| Semantic field | Initial | Standard | Final |
| --- | ---: | ---: | ---: |
| overall level | yes | yes | yes |
| initial Speaking/UoE/Writing/Listening | yes | no | yes |
| current Speaking/UoE/Writing/Listening | no | yes | yes |
| current Reading | no | yes | yes |
| seven self-assessments | no | yes | no |
| Aims | no | yes | no |
| exam intent/type/when | yes | no | no |
| teacher comments | yes | yes | yes |
| additional comments | no | no | yes |

Final Reading remains `dropdown-476`; there is no Initial Reading.

## Offline POST round-trip

C4 validates every one of the 14 private revision fixture pairs through the complete offline path. The POST mapper output is not compared with itself or with a hand-authored payload fixture: the checker independently reconstructs the expected successful-control map from the validated historical controls plus governed archive authority. Exact key/value equality is required.

The independent expectation has three deliberate non-literal rules: archive/summary controls historical `absent`; Standard Aims are rebuilt from visible normalized editor text using HTML escaping then `<br>` line breaks; and `lang=en` is a mapper constant. Unset assessments are omitted, while unset CEFR/exam selects retain their canonical GEL placeholders. All five Final fixtures must include Reading, including the unset placeholder case. The edit-form `datetime` value must equal the canonical revision source timestamp before the payload is accepted.

Mutation-isolation tests additionally prove that changing one editable semantic value changes only its declared GEL field, while changes to provenance-only raw overall-level/Aims/absent evidence change no POST field. Revision identity, student, tutorial type and historical teacher identity are not treated as C4 editable fields.

## Evidence and acceptance

C1–C4 are strictly accepted governed baseline phases. N2a is strictly accepted at `PASS=14 SKIP=0 FAIL=0`, and N2b is strictly accepted at `PASS=15 SKIP=0 FAIL=0`. N2c remains implemented pending its strict `n2c` release scope.

## N2c New-tutorial prepopulation authority

New draft construction is governed by `contracts/new_tutorial_prepopulation.json`.
When a prior tutorial exists, that exact latest tutorial is the prepopulation source;
a first-ever New has no source and uses the already-validated New-form defaults.

The Writer projects a level only from the same canonical semantic field/role.
Initial-role fields (`264`–`267`) copy only when the latest source type carries
those Initial fields (Initial or Final); otherwise their validated New-form defaults
remain. Current-role fields (`233`–`236`) copy only from Standard or Final sources;
otherwise their validated New-form defaults remain. Reading (`476`) copies only
from a Standard/Final source that carries Reading. There is no Initial Reading.
Equal values never authorize cross-skill or Initial/current cross-role provenance.

Common carried fields are `absent`, `overall_level`, and `teacher_comments`.
`tutorial_date`, teacher authority, and tutorial type come from the validated New
form/request rather than the historical source. Standard-only self-assessment/Aims,
Initial-only exam fields, and Final-only additional comments are copied only when
the latest source has the same applicable tutorial-type state; otherwise the
validated New-form default is retained. No New identity/timestamp is invented and
N2c grants no GEL write authority.
