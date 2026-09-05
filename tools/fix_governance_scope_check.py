#!/usr/bin/env python3
"""fix_governance_scope_check.py — Restore 2-element slice in tools/check_governance.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

cg_path = ROOT / "tools" / "check_governance.py"
cg = cg_path.read_text(encoding="utf-8")

# Restore the 2-element list in the ui1e_scope[-2:] assertion
cg = cg.replace(
    '["ui1e_safety", "ui1e_workflow_behavior", "w2_boundaries"], "UI1e dedicated checks must be appended"',
    '["ui1e_safety", "ui1e_workflow_behavior"], "UI1e dedicated checks must be appended"'
)

cg_path.write_text(cg, encoding="utf-8")
print("[✓] Restored ui1e_scope[-2:] assertion in tools/check_governance.py")

# Regenerate governance projections
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("[✓] Projections regenerated successfully")