#!/usr/bin/env python3
"""apply_w1_in_place.py — Record UI1e strict acceptance and W1 verification in place."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel: str, content: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

def write_json(rel: str, data: dict) -> None:
    write(rel, json.dumps(data, indent=2, ensure_ascii=False))

print("=== 1. Updating development_plan.json ===")
plan = json.loads(read("development_plan.json"))
plan["plan_version"] = "1.23.0"
plan["date"] = "2026-09-03"
plan["candidate_version"] = "v17.15-ui1e-accepted-w1-verified"
plan["evaluation"] = {
    "status": "approved_with_ui1e_accepted_and_w1_verified",
    "summary": "UI1e strict acceptance is recorded under ui1e-strict-evidence.json (PASS=45 SKIP=0 FAIL=0). Phase W1 manual controlled write verification is complete with zero blind inserts and failure recovery confirmed. The project is positioned at Phase W2 production submission pre-flight."
}

for phase in plan["phases"]:
    if phase["id"] == "UI1":
        phase["status"] = "complete_strictly_accepted"
        for gate in phase.get("internal_gates", []):
            if gate["id"] == "UI1e":
                gate["status"] = "complete_strictly_accepted"
                gate["strict_result"] = "PASS=45 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
                gate["evidence"] = "external immutable evidence: ui1e-strict-evidence.json"
        if "ui1e" in phase:
            phase["ui1e"]["status"] = "complete_strictly_accepted"
            phase["ui1e"]["strict_result"] = "PASS=45 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
            phase["ui1e"]["evidence"] = "external immutable evidence: ui1e-strict-evidence.json"
            phase["ui1e"]["next"] = "Phase W1 (Submission Verification) unblocked and verified"
    elif phase["id"] == "W1":
        phase["status"] = "complete_strictly_accepted"
        phase["evidence"] = "evidence-private/w1-verification/w1-controlled-write-evidence.json"
        phase["result"] = (
            "Manual controlled write validation passed on 2026-09-03: New (datetime omitted) and "
            "Revision (datetime preserved) POSTs verified against live GEL; server readback confirmed "
            "identity and timestamp discovery; targeted RustArchiver sync reconciled new record into "
            "archive_v2; zero blind local inserts; failures leave active draft dirty/retryable."
        )

write_json("development_plan.json", plan)

print("=== 2. Updating contracts/ui1_writer.json ===")
ui1 = json.loads(read("contracts/ui1_writer.json"))
for gate in ui1.get("internal_gates", []):
    if gate["id"] == "UI1e":
        gate["status"] = "complete_strictly_accepted"
        gate["implementation_authorization"] = "UI1e strict acceptance PASS=45 SKIP=0 FAIL=0 recorded 2026-09-02; W1 verified."
if "ui1e" in ui1:
    ui1["ui1e"]["status"] = "complete_strictly_accepted"
    ui1["ui1e"]["strict_result"] = "PASS=45 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
    ui1["ui1e"]["evidence"] = "external immutable evidence: ui1e-strict-evidence.json"
    ui1["ui1e"]["next_stage"] = "Phase W2 (Production Submission) pre-flight"
write_json("contracts/ui1_writer.json", ui1)

print("=== 3. Updating contracts/release_gate.json ===")
gate = json.loads(read("contracts/release_gate.json"))
hist = gate.setdefault("historical_acceptance_records", {})
hist["ui1e"] = "PASS=45 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
hist["ui1e_evidence"] = "external immutable evidence: ui1e-strict-evidence.json"
hist["w1"] = "MANUAL CONTROLLED WRITE VALIDATION: PASS; ZERO BLIND INSERTS: PASS; RETRYABLE DIRTY RECOVERY: PASS"
hist["w1_evidence"] = "evidence-private/w1-verification/w1-controlled-write-evidence.json"
write_json("contracts/release_gate.json", gate)

print("=== 4. Updating Governance Checkers and Current-State Tools ===")
# check_ui1d_harper.py
cdh = read("tools/check_ui1d_harper.py")
cdh = cdh.replace(
    'require(ui1_phase["status"] == "ui1e_implemented_pending_strict_acceptance", "development plan UI1e status drifted")',
    'require(ui1_phase["status"] in {"ui1e_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "development plan UI1e status drifted")'
)
write("tools/check_ui1d_harper.py", cdh)

# check_ui1c5_integrated.py
c5 = read("tools/check_ui1c5_integrated.py")
c5 = c5.replace(
    'require(ui1_phase.get("status") == "ui1e_implemented_pending_strict_acceptance", "development plan UI1d status drifted")',
    'require(ui1_phase.get("status") in {"ui1e_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "development plan UI1d status drifted")'
)
c5 = c5.replace(
    'require(ui1_phase.get("status") == "ui1e_implemented_pending_strict_acceptance", "development plan UI1e status drifted")',
    'require(ui1_phase.get("status") in {"ui1e_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "development plan UI1e status drifted")'
)
write("tools/check_ui1c5_integrated.py", c5)

# check_governance.py
cg = read("tools/check_governance.py")
if 'historical.get("ui1e")' not in cg:
    cg = cg.replace(
        'require(historical.get("ui1d", "").startswith("PASS=43 SKIP=0 FAIL=0"), "historical accepted UI1d result must remain recorded")',
        'require(historical.get("ui1d", "").startswith("PASS=43 SKIP=0 FAIL=0"), "historical accepted UI1d result must remain recorded")\n    require(historical.get("ui1e", "").startswith("PASS=45 SKIP=0 FAIL=0"), "historical accepted UI1e result must remain recorded")'
    )
write("tools/check_governance.py", cg)

# generate_current_state.py
gcs = read("tools/generate_current_state.py")
if 'historical.get("ui1e")' not in gcs:
    gcs = gcs.replace(
        'if historical.get("ui1d"):',
        'if historical.get("ui1e"):\n        last_acceptance = {\n            "scope": "ui1e",\n            "status": "STRICT_ACCEPTED",\n            "result": historical["ui1e"],\n            "artifactBinding": "external immutable strict evidence: ui1e-strict-evidence.json"\n        }\n    elif historical.get("ui1d"):'
    )
write("tools/generate_current_state.py", gcs)

# check_current_state.py
ccs = read("tools/check_current_state.py")
ccs = ccs.replace(
    'require(state.get("lastStrictAcceptance", {}).get("scope") == "ui1d", "UI1e candidate must retain UI1d as the last strict acceptance")',
    'require(state.get("lastStrictAcceptance", {}).get("scope") == "ui1e", "candidate must retain UI1e as the last strict acceptance")'
)
ccs = ccs.replace(
    'require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS=43 SKIP=0 FAIL=0"), "strict UI1d predecessor result drifted")',
    'require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS=45 SKIP=0 FAIL=0"), "strict UI1e predecessor result drifted")'
)
write("tools/check_current_state.py", ccs)

print("=== 5. Regenerating All Documentation and Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== In-Place Update Complete! ===")