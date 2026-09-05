#!/usr/bin/env python3
"""closeout_w2.py — Record Phase W2 strict acceptance and release artifact verification."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def write_json(rel: str, data: dict) -> None:
    path = ROOT / rel
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

print("=== 1. Updating development_plan.json ===")
plan = json.loads(read("development_plan.json"))
plan["plan_version"] = "1.24.0"
plan["date"] = "2026-09-04"
plan["candidate_version"] = "v17.15-W2-release-verified"
plan["evaluation"] = {
    "status": "approved_w2_strictly_accepted",
    "summary": "Phase W2 production submission strictly accepted on 2026-09-04 with PASS=47 SKIP=0 FAIL=0 (evidence: w2-strict-evidence.json). Final release archive packaged without rebuild and verified (RELEASE_ARTIFACT_VERIFIED)."
}

for phase in plan["phases"]:
    if phase["id"] == "W2":
        phase["status"] = "complete_strictly_accepted"
        phase["evidence"] = "w2-strict-evidence.json"
        phase["result"] = (
            "Phase W2 production submission strictly accepted on 2026-09-04: "
            "all 47 checks PASS (0 SKIP, 0 FAIL); targeted single-student archive "
            "reconciliation, live submission transport, and resilient error recovery active; "
            "release artifact verified without rebuild (RELEASE_ARTIFACT_VERIFIED)."
        )

write_json("development_plan.json", plan)

print("=== 2. Updating contracts/ui1_writer.json ===")
ui1 = json.loads(read("contracts/ui1_writer.json"))
ui1["status"] = "complete_strictly_accepted"
write_json("contracts/ui1_writer.json", ui1)

print("=== 3. Updating contracts/release_gate.json ===")
gate = json.loads(read("contracts/release_gate.json"))
hist = gate.setdefault("historical_acceptance_records", {})
hist["w2"] = "PASS=47 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
hist["w2_evidence"] = "external immutable evidence: w2-strict-evidence.json"
write_json("contracts/release_gate.json", gate)

print("=== 4. Regenerating All Documentation & Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== Phase W2 Governance Closeout Complete! ===")