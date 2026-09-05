#!/usr/bin/env python3
"""fix_w2_final_2.py — Resolve release_control and ui1e_safety scope/version assertions."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Enforce no bytecode generation
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel: str, content: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

print("=== 1. Updating tools/check_release_control.py ===")
rc = read("tools/check_release_control.py")
rc = rc.replace(
    'require(gate.get("current_release_scope") == "ui1e", "current release scope must be ui1e")',
    'require(gate.get("current_release_scope") == "w2", "current release scope must be w2")'
)
write("tools/check_release_control.py", rc)

print("=== 2. Updating tools/check_ui1e_safety.py ===")
safe = read("tools/check_ui1e_safety.py")
safe = safe.replace('require(contract["contract_version"] == 13, "UI1 Writer contract version must be 13")',
                    'require(contract["contract_version"] == 14, "UI1 Writer contract version must be 14")')
safe = safe.replace('require(contract["status"] == "active_ui1e_pending_strict_acceptance", "UI1 Writer status must be active_ui1e_pending_strict_acceptance")',
                    'require(contract["status"] == "active_w2_pending_strict_acceptance", "UI1 Writer status must be active_w2_pending_strict_acceptance")')
safe = safe.replace('require(gate["contract_version"] == 24, "release_gate contract_version must be 24")',
                    'require(gate["contract_version"] == 25, "release_gate contract_version must be 25")')
safe = safe.replace('require(gate["current_release_scope"] == "ui1e", "current release scope must be ui1e")',
                    'require(gate["current_release_scope"] == "w2", "current release scope must be w2")')
safe = safe.replace('require(identity["contract_version"] == 5, "release_identity contract_version must be 5")',
                    'require(identity["contract_version"] == 6, "release_identity contract_version must be 6")')
safe = safe.replace('require(identity["strict_acceptance"]["required_scope"] == "ui1e", "release_identity required_scope must be ui1e")',
                    'require(identity["strict_acceptance"]["required_scope"] == "w2", "release_identity required_scope must be w2")')
write("tools/check_ui1e_safety.py", safe)

print("=== 3. Purging Bytecode Files (*.pyc / __pycache__) ===")
for p in list(ROOT.rglob("__pycache__")):
    shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob("*.pyc")):
    p.unlink(missing_ok=True)
print("  [✓] Bytecode purged")

print("=== 4. Regenerating Documentation & Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

# Final cleanup of any bytecode
for p in list(ROOT.rglob("__pycache__")):
    shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob("*.pyc")):
    p.unlink(missing_ok=True)

print("=== Fix Complete! ===")