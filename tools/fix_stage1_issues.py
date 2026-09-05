#!/usr/bin/env python3
"""fix_stage1_issues.py — Deduplicate state_ownership.json, update check_ui1d_harper.py, and regenerate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

print("=== 1. Deduplicating writer_active_draft in contracts/state_ownership.json ===")
ownership_path = ROOT / "contracts/state_ownership.json"
ownership = json.loads(ownership_path.read_text(encoding="utf-8"))

deduped_classes = []
seen_ids = set()

for s in ownership["state_classes"]:
    sid = s["id"]
    if sid == "writer_active_draft":
        if sid in seen_ids:
            continue  # Drop duplicate
        s["invalidation"] = (
            "Discard/logout/confirmed window close/process exit removes the draft. "
            "Session expiry (HTTP 401/403 or login redirect) or latest tutorial remote drift transitions "
            "active draft to stale_source; invalid invariants transition to invalid. Direct editing is "
            "locked and silent rebinding to new source or teacher authority is strictly forbidden."
        )
        s["current_materialization"] = (
            "Rust LoadedTutorialDraft in writer-ui AppState; dirty status is derived from base != current; "
            "stale_source status is derived from session loss or source drift."
        )
        seen_ids.add(sid)
        deduped_classes.append(s)
    else:
        if sid not in seen_ids:
            seen_ids.add(sid)
            deduped_classes.append(s)

ownership["state_classes"] = deduped_classes
ownership["contract_version"] = 22
ownership_path.write_text(json.dumps(ownership, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"  [✓] state_ownership.json cleaned (total state classes: {len(deduped_classes)})")

print("=== 2. Updating tools/check_ui1d_harper.py to scope ui1e ===")
cdh_path = ROOT / "tools/check_ui1d_harper.py"
cdh = cdh_path.read_text(encoding="utf-8")
cdh = cdh.replace(
    'require(gate["current_release_scope"] == "ui1d", "UI1d must be the current release scope")',
    'require(gate["current_release_scope"] == "ui1e", "current release scope must be ui1e")'
)
cdh_path.write_text(cdh, encoding="utf-8")
print("  [✓] check_ui1d_harper.py updated")

print("=== 3. Regenerating documentation & projections ===")
generators = [
    "tools/generate_governance_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_current_state.py",
    "tools/generate_contract_artifacts.py",
]
for gen in generators:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== Fix Complete! ===")