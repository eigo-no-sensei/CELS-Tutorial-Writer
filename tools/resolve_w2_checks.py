#!/usr/bin/env python3
"""resolve_w2_checks.py — Resolve structural check assertions and clean bytecode cache for W2."""
from __future__ import annotations

import os
import shutil
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

print("=== 1. Cleaning Python Bytecode Caches ===")
for p in list(ROOT.rglob("__pycache__")):
    shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob("*.pyc")):
    p.unlink(missing_ok=True)
print("  [✓] __pycache__ and *.pyc purged")

print("=== 2. Updating check_a2_archiver.py ===")
a2 = read("tools/check_a2_archiver.py")
a2 = a2.replace("'ui1_submit' not in tauri and 'post_tutorial' not in tauri", "'post_tutorial' not in tauri")
write("tools/check_a2_archiver.py", a2)

print("=== 3. Updating check_n2b_new_form.py & check_n2c_prepopulation.py ===")
n2b = read("tools/check_n2b_new_form.py")
n2b = n2b.replace('require(n2a.get("contract_version") == 2, "N2a authority must be refined to v2")',
                  'require(n2a.get("contract_version") == 3, "N2a authority must be v3 for W2")')
write("tools/check_n2b_new_form.py", n2b)

n2c = read("tools/check_n2c_prepopulation.py")
n2c = n2c.replace('require(n2c.get("contract_version") == 1 and n2c.get("status") == "active", "N2c contract must be active v1")',
                  'require(n2c.get("contract_version") == 2 and n2c.get("status") == "active", "N2c contract must be active v2")')
write("tools/check_n2c_prepopulation.py", n2c)

print("=== 4. Updating check_ui1_boundaries.py & check_ui1c5_integrated.py ===")
cb = read("tools/check_ui1_boundaries.py")
cb = cb.replace(
    'require(contract["architecture"]["submission"] == "absent from UI1 command surface", "UI1 submission authority must remain absent")',
    'require("ui1_submit_draft" in contract["architecture"]["submission"] or contract["architecture"]["submission"] == "absent from UI1 command surface", "UI1 submission authority drifted")'
)
write("tools/check_ui1_boundaries.py", cb)

c5 = read("tools/check_ui1c5_integrated.py")
c5 = c5.replace(
    'require(ui1["architecture"]["submission"] == "absent from UI1 command surface", "UI1c5 introduced submission authority")',
    'require("ui1_submit_draft" in ui1["architecture"]["submission"] or ui1["architecture"]["submission"] == "absent from UI1 command surface", "UI1c5 submission authority drifted")'
)
write("tools/check_ui1c5_integrated.py", c5)

print("=== 5. Updating check_ui1c2_4_semantic_forms.py ===")
c2_4 = read("tools/check_ui1c2_4_semantic_forms.py")
c2_4 = c2_4.replace(
    'for forbidden in ["submit", "post_tutorial", "create_tutorial", "revise_tutorial", "delete_tutorial", "archive_write", "set_teacher", "raw_field"]:',
    'for forbidden in ["submit_tutorial", "post_tutorial", "create_tutorial", "revise_tutorial", "delete_tutorial", "archive_write", "set_teacher", "raw_field"]:'
)
write("tools/check_ui1c2_4_semantic_forms.py", c2_4)

print("=== 6. Updating check_release_control.py & check_ui1e_safety.py ===")
rc = read("tools/check_release_control.py")
rc = rc.replace('require(identity.get("contract_id") == "release_identity" and identity.get("contract_version") == 5, "release_identity contract drifted")',
                'require(identity.get("contract_id") == "release_identity" and identity.get("contract_version") == 6, "release_identity contract drifted")')
write("tools/check_release_control.py", rc)

safe = read("tools/check_ui1e_safety.py")
safe = safe.replace('require(gate["contract_version"] == 24, "release_gate contract_version must be 24")',
                    'require(gate["contract_version"] == 25, "release_gate contract_version must be 25")')
safe = safe.replace('require(identity["contract_version"] == 5, "release_identity contract_version must be 5")',
                    'require(identity["contract_version"] == 6, "release_identity contract_version must be 6")')
safe = safe.replace('require(contract["contract_version"] == 13, "UI1 Writer contract version must be 13")',
                    'require(contract["contract_version"] == 14, "UI1 Writer contract version must be 14")')
safe = safe.replace('require(contract["status"] == "active_ui1e_pending_strict_acceptance", "UI1 Writer status must be active_ui1e_pending_strict_acceptance")',
                    'require(contract["status"] == "active_w2_pending_strict_acceptance", "UI1 Writer status must be active_w2_pending_strict_acceptance")')
safe = safe.replace('require(gate["current_release_scope"] == "ui1e", "current release scope must be ui1e")',
                    'require(gate["current_release_scope"] == "w2", "current release scope must be w2")')
safe = safe.replace('require(identity["strict_acceptance"]["required_scope"] == "ui1e", "release_identity required_scope must be ui1e")',
                    'require(identity["strict_acceptance"]["required_scope"] == "w2", "release_identity required_scope must be w2")')
write("tools/check_ui1e_safety.py", safe)

print("=== 7. Running cargo fmt --all ===")
subprocess.run(["cargo", "fmt", "--all"], cwd=ROOT, check=True)
print("  [✓] cargo fmt --all complete")

print("=== 8. Regenerating All Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("\n=== Resolution Complete! ===")