# GEL Rust bootstrap v17.8 — bounded lock-generator exception

This revision keeps the UI1c0 semantic-form/runtime authority and GRI0–GRI5 release-control model, then adds **AI Governance Protocol v1.1 + a GEL project profile** as a meta-governance layer. The protocol governs agent workflow, evidence, lifecycle claims and promotion only; it does not replace or override GEL runtime/domain contracts.

The runtime boundaries are unchanged: React is presentation-only, Rust owns the ephemeral semantic draft, D2 archive access is read-only, N1/N2 expose fixed authenticated read acquisition, and UI1 still exposes no GEL tutorial mutation, archive mutation, teacher reassignment, persistent tutorial draft, generic HTTP or raw POST capability.

GRI adds a release-control layer:

- one root Cargo workspace for `gel-core` + `writer-ui/src-tauri` and one governed `Cargo.lock`;
- governed `writer-ui/package-lock.json` and release installs through `npm ci`;
- `governance/dependency-lock-manifest.json` as a derived lock identity/status projection;
- `governance/current-state.json` + `docs/generated/CURRENT_STATE.md` as generated **projection state only**, never runtime authority;
- five-way `source / decision / derived / projection / evidence` state classification;
- evidence-classified release checks and behavioural proof for high-value safety/release invariants;
- a source/package intake gate that rejects runtime databases, private evidence, secrets, caches and build trees;
- portable CI that cannot claim `STRICT_ACCEPTED` or `RELEASE_ARTIFACT_VERIFIED`;
- strict gate evidence bound to the exact source fingerprint, complete dependency locks and target toolchain identity;
- no-rebuild packaging from matching strict evidence, with exact internal checksums, final ZIP SHA-256 and independent archive verification;
- superseded UI1c plans under `docs/history/plans/`; ADRs remain rank-5 historical rationale.


## AI-agent governance

The generic protocol and project profile live under:

```text
governance/agent-protocol/ai-governance-protocol.v1.1.json
governance/agent-protocol/ai-governance-protocol.schema.json
governance/agent-protocol/project-profile.schema.json
governance/agent-protocol/agent-run-result.schema.json
governance/agent-protocol/profiles/gel-tutorial-writer.profile.json
```

The GEL profile explicitly sets `metaGovernanceOnly=true` and `runtimeAuthority=false`. It binds the generic protocol to the existing documentation hierarchy, state ownership, release gate, release identity, verification semantics and UI contracts instead of restating their domain rules.

Validation is part of the existing governance gate:

```fish
./check-ai-governance
./check-governance
```

`check:governance` fails if the profile claims runtime authority, weakens portable/strict evidence rules, allows automated tutorial/canonical-archive writes, or references unknown project gates/components/state classes.

## Important lock bootstrap

This source snapshot deliberately does **not** invent dependency locks. A missing lock now has one bounded portable exception: if the **corresponding generator executable itself is unavailable** (`cargo` for `Cargo.lock`, `npm` for `writer-ui/package-lock.json`), the dependency-lock release check reports an explicit `SKIP` under the portable profile. The exception is auto-detected only, cannot be manually asserted, does not cover network failure or a package-manager command failure, and disappears as soon as the generator becomes available. Dependency identity remains incomplete. Strict/release acceptance still requires both real locks.

On the target host, run once after unpacking (and again only when dependency manifests change):

```fish
cd ~/gel-rust-bootstrap
python tools/generate_dependency_lockfiles.py
```

This uses the package managers to create/update:

```text
Cargo.lock
writer-ui/package-lock.json
```

It then regenerates the lock/current-state projections and validates synchronization. Review and commit both lockfiles in the same change. Do not hand-create them.

## Development app

After the locks exist:

```fish
set -x GEL_ARCHIVE_DB /path/to/existing/archive-v2.db
cd writer-ui
npm ci
npm run tauri dev
```

`GEL_ARCHIVE_DB` must already exist and be schema v2. Tutorial Writer never creates or mutates it.

## Portable enforcement

```fish
./check-portable
```

Portable mode may explicitly skip missing private GEL fixtures and may explicitly skip a missing dependency lock **only** under `LOCK_GENERATOR_UNAVAILABLE` for that lock's absent package-manager executable. `SKIP` never means `PASS`; the result is `STRUCTURAL_PASS_WITH_SKIPS` and promotion is capped at `FAST_VERIFIED`. If the generator exists but lock generation fails (including network/registry failure), the exception does not apply. Rust/frontend toolchain or build failures remain failures.

## Strict GRI acceptance

Strict acceptance requires private fixtures and an evidence destination **outside** the repository source tree:

```fish
cd ~/gel-rust-bootstrap
set -x GEL_PRIVATE_FIXTURES_DIR /home/mashuu/GEL_tutorial_and_report_Writer/gel-rust-bootstrap/fixtures-private

./check-strict /evidence/gel/20260830T120000Z/strict-result.json
```

Acceptance requires every GRI check to pass with `SKIP=0` and `FAIL=0`, and the evidence record must report:

```text
TARGET STATUS: STRICT_ACCEPTED
```

UI1c1 is blocked until this succeeds.

## Exact release packaging

Packaging never rebuilds after strict acceptance. It first verifies that the current source fingerprint still matches the strict evidence:

```fish
python tools/package_release.py \
  --evidence /evidence/gel/20260830T120000Z/strict-result.json \
  --output /artifacts/gel-rust-bootstrap-v17.8.zip

python tools/verify_release_archive.py /artifacts/gel-rust-bootstrap-v17.8.zip
```

If source, locks or accepted identity changed, packaging fails and a new strict run is required.

## Current authority

Start with these files:

- `contracts/dependency_lock_policy.json`
- `contracts/release_identity.json`
- `contracts/verification_semantics.json`
- `contracts/release_gate.json`
- `contracts/state_ownership.json`
- `contracts/component_boundaries.json`
- `governance/agent-protocol/ai-governance-protocol.v1.1.json` — meta-governance decision only
- `governance/agent-protocol/profiles/gel-tutorial-writer.profile.json` — GEL binding; `runtimeAuthority=false`
- `governance/current-state.json` — generated status projection, not authority
- `plans/ui1c_semantic_forms_plan_v1_2.json`
- `docs/generated/DOCUMENTATION_INDEX.md`

## Archive database

Tutorial Writer archive resolution: a non-empty `GEL_ARCHIVE_DB` overrides the default. On Windows, when it is unset or blank, Writer uses `gel-new-v2.db` in the same directory as the running `.exe`. On non-Windows, the fallback remains project-root `gel-new-v2.db`. Existing archives must be schema v2 and are not migrated in place. Normal Writer navigation opens the archive read-only; the explicit `ui1_sync_archive` action may create a missing schema-v2 archive atomically or synchronize it only through `RustArchiver`.


## UI1c1 common editor framework

Implemented pending strict acceptance: reusable disposition-aware React controls now consume the existing Rust `DraftFormContractView`, preserve structured `DraftValidationIssue` objects, and render only the pre-existing foundation fields. UI1c2–UI1c4 provide the complete Standard/Initial/Final composition; UI1c5 now closes cross-form integration behavior. This change grants no GEL/archive mutation authority.


## UI1c2–c4 semantic forms

Standard, Initial and Final complete semantic form composition is implemented pending strict acceptance. React remains presentation-only: field applicability, CEFR/assessment/course-type domains, text limits, prepopulation/regression semantics and candidate validation remain Rust-owned. UI1c5 integrated acceptance is implemented pending strict `ui1c5` release acceptance; it adds no submission or archive/GEL write command.
