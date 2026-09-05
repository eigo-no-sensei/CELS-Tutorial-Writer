#!/usr/bin/env python3
"""Generate current-state.json as a projection of higher-authority inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from release_common import ROOT, sha256_file

TARGET = ROOT / "governance" / "current-state.json"
DOC_TARGET = ROOT / "docs" / "generated" / "CURRENT_STATE.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def active_development(plan: dict) -> list[str]:
    active: list[str] = []
    for phase in plan.get("phases", []):
        status = str(phase.get("status", ""))
        if "planned" not in status and not status.startswith("complete"):
            active.append(f"{phase['id']}:{status}")
    return active


def render() -> dict:
    plan_path = ROOT / "development_plan.json"
    gate_path = ROOT / "contracts" / "release_gate.json"
    components_path = ROOT / "contracts" / "component_boundaries.json"
    ownership_path = ROOT / "contracts" / "state_ownership.json"
    ui1_path = ROOT / "contracts" / "ui1_writer.json"
    locks_path = ROOT / "governance" / "dependency-lock-manifest.json"
    lock_policy_path = ROOT / "contracts" / "dependency_lock_policy.json"
    protocol_path = ROOT / "governance" / "agent-protocol" / "ai-governance-protocol.v1.1.json"
    profile_path = ROOT / "governance" / "agent-protocol" / "profiles" / "gel-tutorial-writer.profile.json"
    protocol_schema_path = ROOT / "governance" / "agent-protocol" / "ai-governance-protocol.schema.json"
    profile_schema_path = ROOT / "governance" / "agent-protocol" / "project-profile.schema.json"
    run_schema_path = ROOT / "governance" / "agent-protocol" / "agent-run-result.schema.json"
    plan = load(plan_path)
    gate = load(gate_path)
    ui1 = load(ui1_path)
    locks = load(locks_path)
    lock_policy = load(lock_policy_path)
    protocol = load(protocol_path)
    profile = load(profile_path)
    lock_status = locks.get("status", "INCOMPLETE")
    blockers = list(locks.get("blockers", []))
    current_scope = gate.get("current_release_scope", "w2")
    blockers.append(f"{current_scope} strict target-host acceptance has not yet been recorded for this candidate source fingerprint")
    last_acceptance = None
    historical = gate.get("historical_acceptance_records", {})
    if historical.get("w2"):
        last_acceptance = {
            "scope": "w2",
            "status": "STRICT_ACCEPTED",
            "result": historical["w2"],
            "artifactBinding": "external immutable strict evidence: w2-strict-evidence.json"
        }
    elif historical.get("ui1e"):
        last_acceptance = {
            "scope": "ui1e",
            "status": "STRICT_ACCEPTED",
            "result": historical["ui1e"],
            "artifactBinding": "external immutable strict evidence: ui1e-strict-evidence.json"
        }
    elif historical.get("ui1d"):
        last_acceptance = {
            "scope": "ui1d",
            "status": "STRICT_ACCEPTED",
            "result": historical["ui1d"],
            "artifactBinding": "external immutable strict evidence; accepted UI1d source identity predates UI1e implementation"
        }
    elif historical.get("ui1c5"):
        last_acceptance = {
            "scope": "ui1c5",
            "status": "STRICT_ACCEPTED",
            "result": historical["ui1c5"],
            "artifactBinding": "external immutable strict evidence; accepted UI1c5 source identity predates UI1d implementation"
        }
    elif historical.get("gri"):
        last_acceptance = {
            "scope": "gri",
            "status": "STRICT_ACCEPTED",
            "result": historical["gri"],
            "artifactBinding": "external immutable strict evidence; accepted source identity predates UI1c5 implementation"
        }
    else:
        ui1_phase = next((p for p in plan.get("phases", []) if p.get("id") == "UI1"), None)
        if ui1_phase and ui1_phase.get("ui1_hybrid_acceptance", {}).get("status") == "complete_strictly_accepted":
            last_acceptance = {
                "scope": "ui1-hybrid",
                "status": "STRICT_ACCEPTED",
                "result": ui1_phase["ui1_hybrid_acceptance"].get("result"),
                "artifactBinding": "not recorded for that historical acceptance"
            }
    return {
        "schemaVersion": 3,
        "project": "gel-rust-bootstrap",
        "artifactType": plan.get("artifact_type", "working-tree"),
        "candidateVersion": plan.get("candidate_version", "unversioned-working-tree"),
        "activeApplicationContract": {
            "id": ui1["contract_id"],
            "version": ui1["contract_version"],
            "status": ui1["status"],
        },
        "activeDevelopment": active_development(plan),
        "agentGovernance": {
            "protocolId": protocol["protocolId"],
            "protocolVersion": protocol["protocolVersion"],
            "profileId": profile["profileId"],
            "profileVersion": profile["profileVersion"],
            "runtimeAuthority": False,
        },
        "requiredGate": gate.get("current_release_scope", "w2"),
        "dependencyLockStatus": lock_status,
        "dependencyLockExceptionPolicy": {
            "id": lock_policy["tool_unavailable_exception"]["id"],
            "portableResult": lock_policy["tool_unavailable_exception"]["portable_result"],
            "strictResult": lock_policy["tool_unavailable_exception"]["strict_result"],
            "automaticDetectionOnly": not lock_policy["tool_unavailable_exception"]["manual_override_allowed"],
            "promotionCeiling": lock_policy["tool_unavailable_exception"]["promotion_ceiling"],
        },
        "lastStrictAcceptance": last_acceptance,
        "releaseStatus": "STRICT_ACCEPTED" if historical.get("w2") else "TARGET_ACCEPTANCE_REQUIRED",
        "unresolvedBlockers": blockers,
        "generatedFrom": {
            "developmentPlan": sha256_file(plan_path),
            "releaseGate": sha256_file(gate_path),
            "componentBoundaries": sha256_file(components_path),
            "stateOwnership": sha256_file(ownership_path),
            "dependencyLockPolicy": sha256_file(lock_policy_path),
            "dependencyLockManifest": sha256_file(locks_path),
            "agentGovernanceProtocol": sha256_file(protocol_path),
            "agentGovernanceProfile": sha256_file(profile_path),
            "agentGovernanceProtocolSchema": sha256_file(protocol_schema_path),
            "agentGovernanceProjectProfileSchema": sha256_file(profile_schema_path),
            "agentGovernanceRunResultSchema": sha256_file(run_schema_path),
        },
    }


def render_json() -> str:
    return json.dumps(render(), indent=2, sort_keys=False) + "\n"


def render_doc(state: dict) -> str:
    last = state["lastStrictAcceptance"]
    lines = [
        "# Current project state",
        "",
        "> Generated from higher-authority contracts/plan/lock identity. This page is a projection, not runtime authority.",
        "",
        f"- Artifact type: `{state['artifactType']}`",
        f"- Candidate version: `{state['candidateVersion']}`",
        f"- Active application contract: `{state['activeApplicationContract']['id']} v{state['activeApplicationContract']['version']}` (`{state['activeApplicationContract']['status']}`)",
        f"- Agent governance: `{state['agentGovernance']['protocolId']} v{state['agentGovernance']['protocolVersion']}` + profile `{state['agentGovernance']['profileId']} v{state['agentGovernance']['profileVersion']}` (meta-governance only)",
        f"- Required gate: `{state['requiredGate']}`",
        f"- Dependency lock status: `{state['dependencyLockStatus']}`",
        f"- Portable missing-lock exception: `{state['dependencyLockExceptionPolicy']['id']}` → `{state['dependencyLockExceptionPolicy']['portableResult']}` only; strict result `{state['dependencyLockExceptionPolicy']['strictResult']}`",
        f"- Release status: `{state['releaseStatus']}`",
        "",
        "## Active development",
        "",
    ]
    lines += [f"- `{x}`" for x in state["activeDevelopment"]] or ["- None."]
    lines += ["", "## Last strict acceptance", ""]
    if last:
        lines += [f"- Scope: `{last['scope']}`", f"- Status: `{last['status']}`", f"- Result: `{last['result']}`", f"- Artifact binding: {last['artifactBinding']}"]
    else:
        lines += ["- None recorded."]
    lines += ["", "## Unresolved blockers", ""]
    lines += [f"- {x}" for x in state["unresolvedBlockers"]] or ["- None."]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected_json = render_json()
    state = json.loads(expected_json)
    expected_doc = render_doc(state)
    if args.check:
        ok = True
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != expected_json:
            print("current-state projection: STALE")
            ok = False
        if not DOC_TARGET.is_file() or DOC_TARGET.read_text(encoding="utf-8") != expected_doc:
            print("current-state documentation: STALE")
            ok = False
        if ok:
            print("current-state projection: CURRENT")
        return 0 if ok else 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    DOC_TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected_json, encoding="utf-8")
    DOC_TARGET.write_text(expected_doc, encoding="utf-8")
    print(f"generated {TARGET.relative_to(ROOT)}")
    print(f"generated {DOC_TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
