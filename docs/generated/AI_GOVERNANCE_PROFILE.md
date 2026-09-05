# AI-agent governance profile

> Generated from `governance/agent-protocol/ai-governance-protocol.v1.1.json` and the GEL project profile. This page is a projection and not runtime authority.

- Protocol: `ai-governance-protocol v1.1.0`
- Profile: `gel-tutorial-writer v1.1.0`
- Role: `meta_governance_orchestration`
- Runtime authority: `false`
- Current-state semantics: `projection_only`

## Runtime authority binding

The generic protocol does not define GEL field IDs, tutorial semantics, archive ownership, network endpoints, POST payloads, or UI edit authority. Those remain in the existing canonical GEL contracts/tests.

Bound contracts:

- `documentationGovernance` → `contracts/documentation_governance.json`
- `componentBoundaries` → `contracts/component_boundaries.json`
- `stateOwnership` → `contracts/state_ownership.json`
- `releaseGate` → `contracts/release_gate.json`
- `releaseIdentity` → `contracts/release_identity.json`
- `verificationSemantics` → `contracts/verification_semantics.json`
- `uiWriter` → `contracts/ui1_writer.json`
- `semanticForms` → `contracts/ui1c_semantic_forms.json`
- `dependencyLockPolicy` → `contracts/dependency_lock_policy.json`

## Gate profiles

| Profile | Missing required private evidence | SKIP counts as PASS | Promotion ceiling |
| --- | --- | ---: | --- |
| `portable` | `SKIP_EXPLICITLY` | no | `FAST_VERIFIED` |
| `strict` | `FAIL` | no | `STRICT_ACCEPTED` |

## Dependency-lock generator exception

- Exception: `SKIP` in portable only when auto-detected; strict result `FAIL`.
- Manual override allowed: `false`.
- Promotion ceiling while active: `FAST_VERIFIED`.
- Network failure or package-manager command failure is not equivalent to an unavailable generator executable.

## Side-effect policy

- Automated tutorial writes: `false`
- Automated canonical archive writes: `false`

## Validation

`check:governance` invokes `tools/check_ai_governance_protocol.py`, which validates protocol/profile consistency, references to existing GEL gates/components/state, lifecycle claim semantics, and the non-runtime-authority boundary.
