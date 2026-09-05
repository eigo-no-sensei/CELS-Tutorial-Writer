#!/usr/bin/env python3
"""fix_governance_unpack.py — Fix 3-element tuple in tools/check_governance.py."""
from __future__ import annotations

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

print("=== 1. Restoring 2-tuple in tools/check_governance.py ===")
cg = read("tools/check_governance.py")

# Restore the 2-tuple in the Python -S tool list
cg = cg.replace(
    '("w2_boundaries", "w2_submission_behavior", "check_w2_boundaries.py")',
    '("w2_boundaries", "check_w2_boundaries.py")'
)

# Also handle without parenthesis whitespace if needed
cg = cg.replace(
    '("w2_boundaries",\n        "w2_submission_behavior", "check_w2_boundaries.py")',
    '("w2_boundaries", "check_w2_boundaries.py")'
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