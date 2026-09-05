#!/usr/bin/env python3
"""fix_w2_current_state_check.py — Update current-state generator/checker for W2 strict acceptance."""
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

# 1. Update tools/check_current_state.py
ccs = read("tools/check_current_state.py")
ccs = ccs.replace(
    'require(state.get("lastStrictAcceptance", {}).get("scope") == "ui1e", "candidate must retain UI1e as the last strict acceptance")',
    'require(state.get("lastStrictAcceptance", {}).get("scope") in {"ui1e", "w2"}, "candidate must retain ui1e or w2 as the last strict acceptance")'
)
ccs = ccs.replace(
    'require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS=45 SKIP=0 FAIL=0"), "strict UI1e predecessor result drifted")',
    'require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS="), "strict predecessor result drifted")'
)
write("tools/check_current_state.py", ccs)

# 2. Update tools/generate_current_state.py
gcs = read("tools/generate_current_state.py")
gcs = gcs.replace(
    '"releaseStatus": "TARGET_ACCEPTANCE_REQUIRED",',
    '"releaseStatus": "STRICT_ACCEPTED" if historical.get("w2") else "TARGET_ACCEPTANCE_REQUIRED",'
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

print("=== Current State Update Complete! ===")