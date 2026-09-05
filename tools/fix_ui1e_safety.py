#!/usr/bin/env python3
"""fix_ui1e_safety.py — Cleanly overwrite tools/check_ui1e_safety.py."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Enforce no bytecode generation
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

code = '''#!/usr/bin/env python3
"""check:ui1e-safety — structural safety check for window close, discard guards, and staleness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CheckError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read(rel: str) -> str:
    path = ROOT / rel
    require(path.is_file(), f"missing {rel}")
    return path.read_text(encoding="utf-8")


def load(rel: str) -> dict:
    return json.loads(read(rel))


def main() -> int:
    try:
        contract = load("contracts/ui1_writer.json")
        gate = load("contracts/release_gate.json")
        identity = load("contracts/release_identity.json")
        ownership = load("contracts/state_ownership.json")

        require(contract["contract_version"] == 14, "UI1 Writer contract version must be 14")
        require(contract["status"] == "active_w2_pending_strict_acceptance", "UI1 Writer status must be active_w2_pending_strict_acceptance")
        require("draft_staleness" in contract["architecture"], "UI1 architecture must define draft_staleness")
        require("window_close_interception" in contract["architecture"], "UI1 architecture must define window_close_interception")

        require(gate["contract_version"] == 25, "release_gate contract_version must be 25")
        require(gate["current_release_scope"] == "w2", "current release scope must be w2")
        require(len(gate["scopes"]["ui1e"]["checks"]) == 45, "ui1e scope must contain exactly 45 checks")

        require(identity["contract_version"] == 6, "release_identity contract_version must be 6")
        require(identity["strict_acceptance"]["required_scope"] == "w2", "release_identity required_scope must be w2")
        require(identity["strict_acceptance"]["prerequisite_scope"] == "ui1e", "release_identity prerequisite_scope must be ui1e")

        for forbidden in ["post_tutorial", "create_tutorial", "revise_tutorial", "delete_tutorial"]:
            require(forbidden not in contract["initial_command_allowlist"], f"forbidden write command {forbidden} in allowlist")

        states = {s["id"]: s for s in ownership["state_classes"]}
        active_draft = states["writer_active_draft"]
        require("stale_source" in active_draft["invalidation"], "writer_active_draft invalidation must specify stale_source transition")
        require(active_draft["canonical"] is False, "writer_active_draft must not be canonical")

        # Stage 2 Backend Rust Staleness Guards verification
        rust_lib = read("writer-ui/src-tauri/src/lib.rs")
        require("stale: bool" in rust_lib, "LoadedTutorialDraft must contain stale boolean flag")
        require('"stale_source"' in rust_lib, "draft_view must derive stale_source status")
        require("if loaded.stale" in rust_lib and "Draft source authority is stale" in rust_lib, "ui1_apply_draft_edit must block edits when draft is stale")
        require("loaded.stale = true" in rust_lib, "Rust backend must transition draft to stale upon session loss or remote source drift")

        # Stage 3 Frontend Native Dirty-Close & Navigation Guards verification
        app_tsx = read("writer-ui/src/App.tsx")
        require("onCloseRequested" in app_tsx, "App.tsx must listen for onCloseRequested event")
        require("closing the application" in app_tsx, "App.tsx must trigger discard dialog for window close")
        require('guardDraft("opening a new tutorial"' in app_tsx, "doOpenNew must guard active dirty drafts")
        require("setDisabledHarperRules([])" in app_tsx, "doLogout must flush session-only Harper rules")

        foundation = read("writer-ui/src/components/DraftFoundationPanel.tsx")
        require("draft-stale-banner" in foundation, "DraftFoundationPanel must render stale source banner")
        require('draft.status === "stale_source"' in foundation, "DraftFoundationPanel must evaluate stale_source status")

    except (CheckError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"check:ui1e-safety FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:ui1e-safety PASS — window close interception + discard guards + backend staleness guards verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

target = ROOT / "tools" / "check_ui1e_safety.py"
target.write_text(code.strip() + "\n", encoding="utf-8")
target.chmod(0o755)
print("[✓] Overwritten tools/check_ui1e_safety.py with clean code")

# Purge any bytecode
for p in list(ROOT.rglob("__pycache__")):
    shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob("*.pyc")):
    p.unlink(missing_ok=True)
print("[✓] Bytecode purged")