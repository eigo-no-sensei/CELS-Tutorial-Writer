#!/usr/bin/env python3
"""fix_w2_preflight.py — Repair state retention and contract checks for Phase W2."""
from __future__ import annotations

import json
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

print("=== 1. Restoring required retention invariants in contracts/state_ownership.json ===")
ownership = json.loads(read("contracts/state_ownership.json"))
for s in ownership["state_classes"]:
    if s["id"] == "tutorial_post_payload":
        s["retention"] = (
            "Ephemeral derived payload produced by rust_post_mapper, consumed by live_submission_transport "
            "for production GEL submission under Phase W2. New payloads structurally omit datetime; "
            "Revision payloads carry exact source tutorial_ts. Teacher attribution is inherited from "
            "immutable semantic origin authority. Payloads are never canonical evidence."
        )
write_json("contracts/state_ownership.json", ownership)

print("=== 2. Ensuring N2a teacher residual starts with 'Changed-teacher' ===")
n2a = json.loads(read("contracts/n2a_semantic_post_authority.json"))
n2a["resolved_preconditions"]["teacher_serialization_residual"] = (
    "Changed-teacher authentic serialization and server reassignment are permanently unsupported "
    "and non-blocking in production Writer: Revisions strictly preserve historical teacher, "
    "and New tutorials strictly use authenticated teacher."
)
write_json("contracts/n2a_semantic_post_authority.json", n2a)

print("=== 3. Updating tools/check_contracts.py for W2 submission authority ===")
cc = read("tools/check_contracts.py")

# Update contract version expectations in check_contracts.py
cc = cc.replace('"tutorial_form_semantics": 6,', '"tutorial_form_semantics": 7,')
cc = cc.replace('"new_tutorial_prepopulation": 1,', '"new_tutorial_prepopulation": 2,')

# Update submission assertion
cc = cc.replace(
    'require(ui1["architecture"]["submission"] == "absent from UI1 command surface", "UI1 must expose no submission authority")',
    'require(ui1["architecture"]["submission"] == "production submission command ui1_submit_draft delegating to live_submission_transport", "UI1 submission authority drifted for W2")'
)

# Update expected_ui1_commands to include ui1_submit_draft
if '"ui1_submit_draft"' not in cc:
    cc = cc.replace(
        '"ui1_discard_draft",',
        '"ui1_discard_draft",\n        "ui1_submit_draft",'
    )

write("tools/check_contracts.py", cc)

print("=== 4. Regenerating All Documentation & Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== Fix Complete! ===")