#!/usr/bin/env python3
"""Validate AI Governance Protocol v1.1 and the GEL project profile.

This checker is intentionally dependency-minimal. It validates the shipped protocol/profile
shape and, critically, their semantic binding to existing GEL contracts. The generic protocol
is meta-governance only and may not become GEL runtime/domain authority.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "governance" / "agent-protocol"
PROFILE = PROTO / "profiles" / "gel-tutorial-writer.profile.json"


class ProtocolError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProtocolError(f"cannot parse {path.relative_to(ROOT)}: {exc}") from exc
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    require(not dupes, f"duplicate {label}: {sorted(dupes)}")


def contract(path: str) -> dict[str, Any]:
    p = ROOT / path
    require(p.is_file(), f"profile references missing contract {path}")
    return load(p)


def check_protocol(protocol: dict[str, Any], protocol_schema: dict[str, Any], profile_schema: dict[str, Any], run_schema: dict[str, Any]) -> None:
    require(protocol.get("protocolId") == "ai-governance-protocol", "protocolId must be ai-governance-protocol")
    require(protocol.get("protocolVersion") == "1.1.0", "protocolVersion must be 1.1.0")
    require(protocol.get("status") == "active", "protocol v1.1 must be active")
    require(protocol.get("requiredRunResultSchema") == "agent-run-result.schema.json", "run-result schema binding drifted")
    require(protocol.get("requiredProjectProfileSchema") == "project-profile.schema.json", "project-profile schema binding drifted")

    # Schema-level strictness: all three root schemas must reject unknown root fields.
    for name, schema in [
        ("protocol", protocol_schema),
        ("project profile", profile_schema),
        ("run result", run_schema),
    ]:
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{name} schema must use Draft 2020-12")
        require(schema.get("type") == "object" and schema.get("additionalProperties") is False, f"{name} schema root must be closed")

    authority = sorted(protocol.get("authorityHierarchy", []), key=lambda item: item.get("rank", 999))
    require([item.get("rank") for item in authority] == [1, 2, 3, 4, 5], "protocol authority ranks must be exactly 1..5")
    require([item.get("kind") for item in authority] == [
        "executable",
        "active_component_contract",
        "cross_component_ownership_and_lifecycle",
        "operational_guidance",
        "adr_and_history",
    ], "protocol authority hierarchy drifted")
    require([item.get("currentRuntimeAuthority") for item in authority] == [True, True, True, False, False], "protocol runtime-authority flags drifted")

    state_classes = protocol.get("stateClasses", {})
    require(set(state_classes) == {"source", "decision", "derived", "projection", "evidence"}, "protocol must define exactly five state classes")
    require("repository-authored" in state_classes["source"].get("definition", ""), "source definition must include repository-authored canonical input")
    require("current-state" in state_classes["projection"].get("definition", ""), "projection definition must include current-state representation")
    for sid, item in state_classes.items():
        require(item.get("maySelfPromote") is False, f"state class {sid} must not self-promote")

    invariants = protocol.get("coreInvariants", [])
    ids = [item.get("id") for item in invariants]
    unique([str(x) for x in ids], "protocol invariant id")
    require(ids == [f"GOV-{n:02d}" for n in range(1, 17)], "protocol invariants must be GOV-01..GOV-16 in order")
    by_id = {item["id"]: item for item in invariants}
    require("projection" in by_id["GOV-01"]["rule"].lower() and "runtime authority" in by_id["GOV-01"]["rule"].lower(), "GOV-01 must keep current-state projection non-authoritative")
    require("exact subject identity" in by_id["GOV-10"]["rule"].lower() and "rebuild" in by_id["GOV-10"]["rule"].lower(), "GOV-10 must bind exact subject and no-rebuild semantics")
    require("side-effect" in by_id["GOV-15"]["rule"].lower(), "GOV-15 must govern gate side effects")
    require("scoped repair" in by_id["GOV-16"]["rule"].lower(), "GOV-16 must allow identity-establishing repair without promotion")

    ownership_fields = protocol.get("ownershipContractRequiredFields", [])
    require(set(ownership_fields) == {"stateId","stateClass","owner","permittedWriter","readers","sourceInputs","invalidationTriggers","failureBehavior","forbiddenWriters","mutationPolicy","approvalPolicy"}, "ownership required-field set drifted")
    component_fields = protocol.get("activeComponentContractRequiredFields", [])
    require(component_fields == ["role","scope","authority","reads","writes","mustNotWrite","stateTransitions","failureSemantics","dependencies","tests"], "active component required-field set drifted")

    subject = protocol.get("subjectIdentity", {})
    require(subject.get("artifactTypeAuthority") == "project_profile", "artifact type authority must belong to project profile")
    require(set(subject.get("requiredFields", [])) >= {"projectId","artifactType","sourceIdentity","dependencyIdentity","contractSetIdentity","schemaIdentities"}, "subject identity missing required release/governance identities")
    require("dependencyIdentity" in subject.get("nullableUntilPromotionFields", []), "dependency identity must be representable as unresolved before promotion")

    evidence = protocol.get("evidence", {})
    require(set(evidence.get("requiredFields", [])) == {"evidenceId","stage","proofClass","producer","subjectIdentityRef","observedAt","result","promotionAuthority"}, "protocol evidence required fields drifted")
    require(set(evidence.get("proofClasses", [])) == {"lint","structural","behavioral","acceptance"}, "protocol proof-class taxonomy drifted")
    require("fast_gate" in evidence.get("stages", []) and "strict_acceptance" in evidence.get("stages", []), "protocol evidence stages incomplete")

    steps = protocol.get("executionAlgorithm", [])
    require([step.get("step") for step in steps] == [f"A{i}" for i in range(8)], "execution algorithm must be A0..A7")
    require("load_project_profile" in steps[0].get("actions", []), "A0 must load project profile")
    require("regenerate_current_state_projection" in steps[-1].get("actions", []), "A7 must regenerate current-state projection rather than update it as authority")

    stop = {item.get("id"): item for item in protocol.get("stopConditions", [])}
    require(stop.get("STOP-04", {}).get("repairScopeExemption") is True, "STOP-04 must allow scoped reproducibility repair")
    require("promotion" in " ".join(stop.get("STOP-04", {}).get("blocks", [])).lower(), "STOP-04 must block promotion rather than all engineering work")

    mutation_profiles = protocol.get("mutationProfiles", {})
    require(mutation_profiles.get("authoritative_ephemeral_change", {}).get("requiresCandidateBeforeCommit") is True, "protocol must model candidate-before-commit authoritative ephemeral state")
    require(mutation_profiles.get("release_publication", {}).get("mustNotRebuildDuringVerification") is True, "release publication must forbid rebuild during verification")

    release = protocol.get("releaseSemantics", {})
    require("exact declared subject identity" in release.get("subjectAcceptanceRule", "").lower(), "release semantics must accept exact declared subject identity")
    require("BUILD creates a new subject identity" in release.get("verificationRule", ""), "verification/build identity rule drifted")

    profile_semantics = protocol.get("projectProfileSemantics", {})
    require(profile_semantics == {
        "role":"meta_governance_orchestration",
        "runtimeAuthorityDefault":False,
        "mustBindExistingAuthority":True,
        "mustDeclareGateProfiles":True,
        "mustDeclareSideEffectPolicy":True,
    }, "project profile semantics drifted")

    # The v1.0 defect must remain fixed: run-result evidence schema contains all protocol-required evidence fields.
    run_evidence = run_schema.get("$defs", {}).get("evidence", {})
    require(set(run_evidence.get("required", [])) == set(evidence["requiredFields"]), "run-result evidence required fields contradict protocol evidence policy")
    require(run_evidence.get("additionalProperties") is False, "run-result evidence object must be closed")

    # Lifecycle claim schema must contain conditional constraints for the strongest claims/statuses.
    conditional_text = json.dumps(run_schema.get("allOf", []), sort_keys=True)
    for token in ["FAST_VERIFIED", "CANDIDATE_QUALIFIED", "STRICT_ACCEPTED", "RELEASE_ARTIFACT_VERIFIED", '"const": "PASS"']:
        require(token in conditional_text, f"run-result schema missing lifecycle semantic condition {token}")


def check_profile(profile: dict[str, Any], protocol: dict[str, Any]) -> None:
    require(profile.get("profileId") == "gel-tutorial-writer", "unexpected GEL profileId")
    require(profile.get("profileVersion") == "1.1.0", "GEL profileVersion must be 1.1.0")
    require(profile.get("protocolId") == protocol.get("protocolId") and profile.get("protocolVersion") == protocol.get("protocolVersion"), "GEL profile must bind protocol v1.1 exactly")

    project = profile.get("project", {})
    require(project.get("projectId") == "gel-rust-bootstrap", "GEL profile projectId drifted")
    require(project.get("metaGovernanceOnly") is True and project.get("runtimeAuthority") is False, "generic protocol/profile must be meta-governance only")

    authority = profile.get("authorityBinding", {})
    require(authority.get("protocolRole") == "meta_governance_orchestration", "GEL profile protocol role drifted")
    require(authority.get("runtimeAuthority") is False, "GEL profile must never claim runtime authority")
    require(authority.get("currentStateSemantics") == "projection_only", "GEL current-state must remain projection-only")
    require(authority.get("authorityOrderContract") == "contracts/documentation_governance.json", "GEL profile must bind existing documentation authority contract")
    require(authority.get("runtimeAuthoritySources") and all(not x.startswith("governance/agent-protocol") for x in authority["runtimeAuthoritySources"]), "protocol files must not appear in runtimeAuthoritySources")
    require(authority.get("mustNotOverride"), "GEL profile must explicitly declare domain areas the protocol cannot override")

    docgov = contract(authority["authorityOrderContract"])
    ranked = sorted(docgov.get("authority_order", []), key=lambda x: x["rank"])
    kind_mapping = authority.get("kindMapping", {})
    proto_ranked = sorted(protocol["authorityHierarchy"], key=lambda x: x["rank"])
    expected_project_classes = [kind_mapping.get(item["kind"]) for item in proto_ranked]
    require(expected_project_classes == [item["class"] for item in ranked], "GEL profile authority kind mapping does not match documentation_governance authority order")

    bindings = profile.get("contractBindings", {})
    expected_contract_ids = {
        "documentationGovernance":"documentation_governance",
        "componentBoundaries":"component_boundaries",
        "stateOwnership":"state_ownership",
        "releaseGate":"release_gate",
        "releaseIdentity":"release_identity",
        "verificationSemantics":"verification_semantics",
        "uiWriter":"ui1_writer",
        "semanticForms":"ui1c_semantic_forms",
        "dependencyLockPolicy":"dependency_lock_policy",
    }
    for key, expected_id in expected_contract_ids.items():
        require(key in bindings, f"GEL profile missing contract binding {key}")
        obj = contract(bindings[key])
        require(obj.get("contract_id") == expected_id, f"GEL profile {key} binding points to wrong contract id")

    require(profile.get("stateTaxonomyMapping") == {k:k for k in ["source","decision","derived","projection","evidence"]}, "GEL profile state taxonomy mapping must be one-to-one")

    plan = load(ROOT / "development_plan.json")
    require(plan.get("artifact_type") in profile.get("artifactTypes", []), "current development-plan artifact type is not allowed by GEL profile")

    release_gate = contract(bindings["releaseGate"])
    gate_profiles = profile.get("gateProfiles", {})
    require(gate_profiles.get("portable", {}).get("releaseGateProfile") == "portable", "GEL profile portable gate binding drifted")
    require(gate_profiles.get("strict", {}).get("releaseGateProfile") == "strict", "GEL profile strict gate binding drifted")
    require(release_gate["profiles"]["portable"]["missing_private_fixture_policy"] == "skip", "project portable contract no longer matches profile")
    require(release_gate["profiles"]["strict"]["missing_private_fixture_policy"] == "fail", "project strict contract no longer matches profile")
    require(gate_profiles["portable"]["missingRequiredPrivateEvidence"] == "SKIP_EXPLICITLY", "portable private evidence must be explicit skip")
    require(gate_profiles["strict"]["missingRequiredPrivateEvidence"] == "FAIL", "strict private evidence must fail when required and absent")
    require(gate_profiles["portable"]["skipMayCountAsPass"] is False and gate_profiles["strict"]["skipMayCountAsPass"] is False, "SKIP must never count as PASS")
    require(gate_profiles["portable"]["promotionCeiling"] == "FAST_VERIFIED", "CI/portable promotion ceiling must remain FAST_VERIFIED")
    require(gate_profiles["strict"]["promotionCeiling"] == "STRICT_ACCEPTED", "strict promotion ceiling drifted")

    side_effect = profile.get("gateSideEffectPolicy", {})
    require(side_effect.get("automatedTutorialWrites") is False, "GEL profile must forbid automated tutorial writes")
    require(side_effect.get("automatedArchiveCanonicalWrites") is False, "GEL profile must forbid automated canonical archive writes")
    live_rule = release_gate.get("live_write_rule", "").lower()
    require("no automated release-gate command" in live_rule and "mutate a gel tutorial" in live_rule, "release gate live-write rule no longer supports profile side-effect policy")

    evidence_binding = profile.get("evidenceBinding", {})
    verification = contract(evidence_binding["proofClassContract"])
    require(set(verification.get("evidence_classes", [])) == set(protocol["evidence"]["proofClasses"]), "GEL verification proof classes must match protocol proof classes")
    require(evidence_binding.get("releaseGateContract") == bindings["releaseGate"], "profile evidence release-gate binding drifted")

    promotion = profile.get("promotionPolicy", {})
    missing_dep = promotion.get("missingDependencyIdentity", {})
    require(set(missing_dep.get("blocksStatuses", [])) == {"STRICT_ACCEPTED","RELEASE_ARTIFACT_VERIFIED"}, "missing dependency identity must block only strict/release promotions in GEL profile")
    require(missing_dep.get("repairScopeAllowed") is True, "GEL profile must permit a scoped dependency-identity repair")
    tool_exc = missing_dep.get("toolUnavailableException", {})
    require(tool_exc == {"automaticDetectionOnly":True,"manualOverrideAllowed":False,"portableResult":"SKIP","strictResult":"FAIL","promotionCeiling":"FAST_VERIFIED","invalidatedWhenToolAvailable":True}, "GEL lock-generator-unavailable exception binding drifted")
    lock_policy = contract(bindings["dependencyLockPolicy"])["tool_unavailable_exception"]
    require(lock_policy["id"] == "LOCK_GENERATOR_UNAVAILABLE" and lock_policy["portable_result"] == tool_exc["portableResult"] and lock_policy["strict_result"] == tool_exc["strictResult"], "GEL profile lock exception does not match project contract")
    require(lock_policy["manual_override_allowed"] is False and lock_policy["promotion_ceiling"] == tool_exc["promotionCeiling"], "GEL profile weakens lock exception authority")
    require(promotion.get("ciPromotionCeiling") == "FAST_VERIFIED", "CI must not claim strict acceptance")

    mutation = profile.get("mutationProfileBindings", {})
    require(mutation == {"writerDraftEdit":"authoritative_ephemeral_change","gelExternalMutation":"destructive_or_external_mutation","releasePublication":"release_publication"}, "GEL mutation-profile bindings drifted")

    components = contract(bindings["componentBoundaries"])
    ownership = contract(bindings["stateOwnership"])
    known_component_ids = {c["id"] for c in components.get("components", [])}
    known_state_ids = {s["id"] for s in ownership.get("state_classes", [])}
    known_gate_ids = {g["id"] for g in release_gate.get("checks", [])}
    validation = profile.get("validationBindings", {})
    unknown_components = set(validation.get("knownComponentIds", [])) - known_component_ids
    unknown_states = set(validation.get("knownStateIds", [])) - known_state_ids
    unknown_gates = set(validation.get("knownGateIds", [])) - known_gate_ids
    require(not unknown_components, f"GEL profile references unknown components: {sorted(unknown_components)}")
    require(not unknown_states, f"GEL profile references unknown state IDs: {sorted(unknown_states)}")
    require(not unknown_gates, f"GEL profile references unknown release gate IDs: {sorted(unknown_gates)}")
    for check_name in validation.get("requiredProjectChecks", []):
        executable = ROOT / check_name.replace(":", "-")
        require(executable.is_file(), f"GEL profile required project check missing: {check_name}")

    # Explicitly verify that current-state is project projection and the protocol cannot promote it.
    state_by_id = {s["id"]: s for s in ownership.get("state_classes", [])}
    current_state = state_by_id.get("current_state_projection", {})
    require(current_state.get("state_kind") == "projection" and current_state.get("canonical") is False, "current-state projection ownership drifted")
    require("runtime authority" in current_state.get("retention", "").lower(), "current-state projection must explicitly deny runtime authority")


def validate_run_result(result: dict[str, Any], profile: dict[str, Any]) -> None:
    """Semantic validation beyond what JSON Schema alone can reliably express."""
    require(result.get("protocolVersion") == "1.1.0", "run result protocolVersion drifted")
    pref = result.get("profileRef", {})
    require(pref.get("profileId") == profile.get("profileId") and pref.get("profileVersion") == profile.get("profileVersion"), "run result profileRef mismatch")
    before = result.get("subjectBefore")
    after = result.get("subjectAfter")
    require(isinstance(before, dict), "run result subjectBefore required")
    subjects = {before.get("identityRef"): before}
    if isinstance(after, dict):
        require(after.get("identityRef") != before.get("identityRef") or after == before, "subjectAfter may reuse identityRef only when identity is unchanged")
        subjects[after.get("identityRef")] = after
    for label, subject in subjects.items():
        require(label, "subject identityRef must be nonblank")
        require(subject.get("projectId") == profile["project"]["projectId"], "run result subject projectId mismatch")
        require(subject.get("artifactType") in profile["artifactTypes"], f"run result artifactType {subject.get('artifactType')!r} not allowed by profile")
        require(subject.get("sourceIdentity"), "run result sourceIdentity required")
        require(subject.get("contractSetIdentity"), "run result contractSetIdentity required")
        require(isinstance(subject.get("schemaIdentities"), dict) and subject["schemaIdentities"], "run result schemaIdentities required")

    verification = result.get("verification", {})
    for gate_name in ["fastGate","candidateGate","strictGate","artifactVerification"]:
        gate = verification.get(gate_name, {})
        require(gate.get("subjectIdentityRef") in subjects, f"{gate_name} references unknown subject identity")
        require(gate.get("result") != "PASS" or not gate.get("blockingReasons"), f"{gate_name} PASS cannot retain blocking reasons")
        require(not gate.get("sideEffectsObserved"), f"{gate_name} observed undeclared side effects: {gate.get('sideEffectsObserved')}")

    evidence_ids: list[str] = []
    for item in result.get("evidence", []):
        evidence_ids.append(item.get("evidenceId", ""))
        require(set(item) == {"evidenceId","stage","proofClass","producer","subjectIdentityRef","observedAt","result","promotionAuthority"}, "run evidence must carry the complete v1.1 evidence record")
        require(item.get("subjectIdentityRef") in subjects, f"evidence {item.get('evidenceId')} references unknown subject")
        require(item.get("result") != "PASS" or item.get("producer"), "PASS evidence requires a producer")
        require(item.get("promotionAuthority") is False, "evidence records cannot self-promote")
        require(re.match(r"^\d{4}-\d{2}-\d{2}T", str(item.get("observedAt", ""))) is not None, "evidence observedAt must be an ISO-like date-time")
    unique(evidence_ids, "run evidenceId")

    claims = result.get("claims", {})
    status = result.get("status")
    if claims.get("fastVerified"):
        require(claims.get("implemented") is True, "fastVerified implies implemented")
        require(verification["fastGate"].get("result") == "PASS", "fastVerified requires fastGate PASS")
    if claims.get("candidateQualified"):
        require(claims.get("implemented") is True, "candidateQualified implies implemented")
        require(verification["candidateGate"].get("result") == "PASS", "candidateQualified requires candidateGate PASS")
    if claims.get("strictlyAccepted"):
        require(claims.get("implemented") is True, "strictlyAccepted implies implemented")
        require(verification["strictGate"].get("result") == "PASS", "strictlyAccepted requires strictGate PASS")
        require(isinstance(after, dict), "strictlyAccepted requires subjectAfter")
        require(after.get("dependencyIdentity") is not None, "strictlyAccepted requires complete dependency identity")
        require(verification["strictGate"].get("profile") == "strict", "strictlyAccepted requires strict gate profile")
    if claims.get("releaseArtifactVerified"):
        require(claims.get("strictlyAccepted") is True, "releaseArtifactVerified implies strictlyAccepted")
        require(verification["artifactVerification"].get("result") == "PASS", "releaseArtifactVerified requires artifactVerification PASS")
        require(isinstance(after, dict) and after.get("artifactIdentity"), "releaseArtifactVerified requires artifact identity")

    status_requirements = {
        "FAST_VERIFIED": ("fastVerified", "fastGate"),
        "CANDIDATE_QUALIFIED": ("candidateQualified", "candidateGate"),
        "STRICT_ACCEPTED": ("strictlyAccepted", "strictGate"),
        "RELEASE_ARTIFACT_VERIFIED": ("releaseArtifactVerified", "artifactVerification"),
    }
    if status in status_requirements:
        claim_key, gate_key = status_requirements[status]
        require(claims.get(claim_key) is True, f"status {status} requires claim {claim_key}=true")
        require(verification[gate_key].get("result") == "PASS", f"status {status} requires {gate_key} PASS")


def self_test_semantics(example: dict[str, Any], profile: dict[str, Any]) -> None:
    validate_run_result(example, profile)

    # Reproduce the v1.0 contradiction/corruption case and prove it is rejected semantically.
    broken = json.loads(json.dumps(example))
    broken["status"] = "STRICT_ACCEPTED"
    broken["claims"]["strictlyAccepted"] = False
    broken["verification"]["strictGate"]["result"] = "NOT_RUN"
    try:
        validate_run_result(broken, profile)
    except ProtocolError:
        pass
    else:
        raise ProtocolError("semantic validator accepted contradictory STRICT_ACCEPTED result")

    skipped = json.loads(json.dumps(example))
    skipped["claims"]["fastVerified"] = True
    skipped["verification"]["fastGate"]["result"] = "SKIPPED"
    try:
        validate_run_result(skipped, profile)
    except ProtocolError:
        pass
    else:
        raise ProtocolError("semantic validator promoted SKIPPED fast gate to fastVerified")


def validate_or_raise() -> None:
    required = [
        PROTO / "ai-governance-protocol.schema.json",
        PROTO / "ai-governance-protocol.v1.1.json",
        PROTO / "project-profile.schema.json",
        PROTO / "agent-run-result.schema.json",
        PROTO / "agent-run-result.example.json",
        PROFILE,
    ]
    for path in required:
        require(path.is_file(), f"missing AI governance protocol file {path.relative_to(ROOT)}")
    protocol_schema = load(required[0])
    protocol = load(required[1])
    profile_schema = load(required[2])
    run_schema = load(required[3])
    example = load(required[4])
    profile = load(required[5])
    check_protocol(protocol, protocol_schema, profile_schema, run_schema)
    check_profile(profile, protocol)
    self_test_semantics(example, profile)


def main() -> int:
    try:
        validate_or_raise()
    except ProtocolError as exc:
        print(f"check:ai-governance-protocol FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:ai-governance-protocol PASS — protocol v1.1 + GEL profile are internally consistent and meta-governance-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
