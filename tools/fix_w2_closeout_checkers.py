#!/usr/bin/env python3
"""fix_w2_closeout_checkers.py — Update checker assertions for complete_strictly_accepted."""
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
    p.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

# 1. check_contracts.py
cc = read("tools/check_contracts.py")
cc = cc.replace(
    'require(ui1.get("status") == "active_w2_pending_strict_acceptance", "UI1 active contract status drifted")',
    'require(ui1.get("status") in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 active contract status drifted")'
)
write("tools/check_contracts.py", cc)

# 2. check_ui1_boundaries.py
cb = read("tools/check_ui1_boundaries.py")
cb = cb.replace(
    'require(contract.get("status") == "active_w2_pending_strict_acceptance", "W2 status drifted")',
    'require(contract.get("status") in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "W2 status drifted")'
)
write("tools/check_ui1_boundaries.py", cb)

# 3. check_ui1c5_integrated.py
c5 = read("tools/check_ui1c5_integrated.py")
c5 = c5.replace(
    'require(ui1.get("status") == "active_w2_pending_strict_acceptance", "UI1 Writer W2 status drifted")',
    'require(ui1.get("status") in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 Writer W2 status drifted")'
)
write("tools/check_ui1c5_integrated.py", c5)

# 4. check_ui1d_harper.py
cdh = read("tools/check_ui1d_harper.py")
cdh = cdh.replace(
    'require(ui1["contract_version"] == 14 and ui1["status"] == "active_w2_pending_strict_acceptance", "UI1 Writer contract must be v14/W2-active")',
    'require(ui1["contract_version"] == 14 and ui1["status"] in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 Writer contract must be v14/W2-active")'
)
write("tools/check_ui1d_harper.py", cdh)

# 5. check_ui1e_safety.py
safe = read("tools/check_ui1e_safety.py")
safe = safe.replace(
    'require(contract["status"] == "active_w2_pending_strict_acceptance", "UI1 Writer status must be active_w2_pending_strict_acceptance")',
    'require(contract["status"] in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 Writer status must be active_w2_pending_strict_acceptance")'
)
write("tools/check_ui1e_safety.py", safe)

# 6. check_w2_boundaries.py
w2b = read("tools/check_w2_boundaries.py")
w2b = w2b.replace(
    'require(ui1["status"] == "active_w2_pending_strict_acceptance", "ui1_writer status must be active_w2_pending_strict_acceptance")',
    'require(ui1["status"] in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "ui1_writer status must be active_w2_pending_strict_acceptance")'
)
write("tools/check_w2_boundaries.py", w2b)

# 7. generate_current_state.py (bind W2 as last strict acceptance)
gcs = read("tools/generate_current_state.py")
if 'historical.get("w2")' not in gcs:
    gcs = gcs.replace(
        'if historical.get("ui1e"):',
        'if historical.get("w2"):\n        last_acceptance = {\n            "scope": "w2",\n            "status": "STRICT_ACCEPTED",\n            "result": historical["w2"],\n            "artifactBinding": "external immutable strict evidence: w2-strict-evidence.json"\n        }\n    elif historical.get("ui1e"):'
    )
write("tools/generate_current_state.py", gcs)

print("=== Regenerating Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== Checker Updates Complete! ===")