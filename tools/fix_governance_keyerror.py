#!/usr/bin/env python3
"""fix_governance_keyerror.py — Repair accidental tuple key in tools/check_governance.py."""
from __future__ import annotations

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

print("=== 1. Fixing dictionary key in tools/check_governance.py ===")
cg = read("tools/check_governance.py")
cg = cg.replace(
    'check_by_id["ui1e_workflow_behavior", "w2_boundaries"]',
    'check_by_id["ui1e_workflow_behavior"]'
)
write("tools/check_governance.py", cg)

print("=== 2. Regenerating All Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== Fix Complete! ===")