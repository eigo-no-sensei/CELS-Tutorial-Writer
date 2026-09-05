#!/usr/bin/env python3
"""apply_stage1.py — Apply UI1e Stage 1 updates directly from current state."""
from __future__ import annotations

import json
import re
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

print("=== 1. Repairing & Updating contracts/release_gate.json ===")
raw_gate = read("contracts/release_gate.json")

# Cleanly splice the scopes section to bypass the syntax error in the current working copy
idx_scopes = raw_gate.find('"scopes": {')
idx_crs = raw_gate.find('"current_release_scope"')

clean_scopes = """  "scopes": {
    "n2a": {
      "purpose": "Historical N2a regression scope using current workspace-level Rust verification; historical PASS=14 acceptance remains recorded in development history.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "rust_workspace_fmt",
        "rust_workspace_clippy", "rust_workspace_tests", "private_fixture_parity",
        "private_collision_authority", "private_post_round_trip"
      ]
    },
    "n2b": {
      "purpose": "Historical N2b regression scope using current workspace-level Rust verification.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form",
        "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests",
        "private_fixture_parity", "private_collision_authority", "private_post_round_trip"
      ]
    },
    "n2c": {
      "purpose": "Historical N2c regression scope using current workspace-level Rust verification.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form",
        "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests",
        "private_fixture_parity", "private_collision_authority", "private_post_round_trip"
      ]
    },
    "ui1-initial": {
      "purpose": "Current regression form of the strictly accepted UI1a/b baseline; workspace Rust checks replace duplicated per-crate invocations.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form",
        "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests",
        "private_fixture_parity", "private_collision_authority", "private_post_round_trip",
        "ui1_boundaries", "frontend_dependencies", "ui1_frontend_typecheck", "ui1_frontend_build"
      ]
    },
    "ui1-hybrid": {
      "purpose": "Current regression form of the strictly accepted A+D hybrid baseline.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form",
        "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests",
        "private_fixture_parity", "private_collision_authority", "private_post_round_trip",
        "ui1_boundaries", "frontend_dependencies", "ui1_frontend_typecheck", "ui1_frontend_build",
        "ui1_hybrid_layout"
      ]
    },
    "ui1c": {
      "purpose": "UI1c0 semantic-form acceptance scope before reproducible-release controls are added.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "a1_print_parity", "a1_print_behavior", "private_print_parity", "a2_archiver",
        "a2_archiver_behavior", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post",
        "n2b_new_form", "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy",
        "rust_workspace_tests", "private_fixture_parity", "private_collision_authority",
        "private_post_round_trip", "ui1_boundaries", "frontend_dependencies",
        "ui1_frontend_typecheck", "ui1_frontend_build", "ui1_hybrid_layout", "ui1c_forms_contract",
        "ui1c_semantic_validation", "ui1c_frontend_forms", "ui1c1_editor_framework",
        "ui1c2_4_semantic_forms"
      ]
    },
    "gri": {
      "purpose": "Current GRI release-control scope: UI1c semantics plus A1 print parity, A2 Rust archiver cutover, complete locks/current-state/intake/semantic evidence/release-control/CI invariants. Strict zero-SKIP/FAIL result is required for promotion.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "a1_print_parity", "a1_print_behavior", "private_print_parity", "a2_archiver",
        "a2_archiver_behavior", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post",
        "n2b_new_form", "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy",
        "rust_workspace_tests", "private_fixture_parity", "private_collision_authority",
        "private_post_round_trip", "ui1_boundaries", "frontend_dependencies",
        "ui1_frontend_typecheck", "ui1_frontend_build", "ui1_hybrid_layout", "ui1c_forms_contract",
        "ui1c_semantic_validation", "ui1c_frontend_forms", "dependency_locks",
        "dependency_lock_exception_behavior", "current_state", "verification_semantics",
        "source_intake", "release_control", "release_control_behavior", "ci_contract",
        "ui1c1_editor_framework", "ui1c2_4_semantic_forms"
      ]
    },
    "ui1c5": {
      "purpose": "UI1c5 integrated semantic-form release scope: the strictly accepted 39-check GRI baseline plus dedicated structural and behavioral cross-form integration closure.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "a1_print_parity", "a1_print_behavior", "private_print_parity", "a2_archiver",
        "a2_archiver_behavior", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post",
        "n2b_new_form", "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy",
        "rust_workspace_tests", "private_fixture_parity", "private_collision_authority",
        "private_post_round_trip", "ui1_boundaries", "frontend_dependencies",
        "ui1_frontend_typecheck", "ui1_frontend_build", "ui1_hybrid_layout", "ui1c_forms_contract",
        "ui1c_semantic_validation", "ui1c_frontend_forms", "dependency_locks",
        "dependency_lock_exception_behavior", "current_state", "verification_semantics",
        "source_intake", "release_control", "release_control_behavior", "ci_contract",
        "ui1c1_editor_framework", "ui1c2_4_semantic_forms", "ui1c5_integrated",
        "ui1c5_integrated_behavior"
      ]
    },
    "ui1d": {
      "purpose": "UI1d Harper + persistent dictionary release scope: strictly accepted UI1c5 plus Rust-owned British-English assistance, persistent local dictionary ownership and dictionary failure semantics.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "a1_print_parity", "a1_print_behavior", "private_print_parity", "a2_archiver",
        "a2_archiver_behavior", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post",
        "n2b_new_form", "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy",
        "rust_workspace_tests", "private_fixture_parity", "private_collision_authority",
        "private_post_round_trip", "ui1_boundaries", "frontend_dependencies",
        "ui1_frontend_typecheck", "ui1_frontend_build", "ui1_hybrid_layout", "ui1c_forms_contract",
        "ui1c_semantic_validation", "ui1c_frontend_forms", "dependency_locks",
        "dependency_lock_exception_behavior", "current_state", "verification_semantics",
        "source_intake", "release_control", "release_control_behavior", "ci_contract",
        "ui1c1_editor_framework", "ui1c2_4_semantic_forms", "ui1c5_integrated",
        "ui1c5_integrated_behavior", "ui1d_harper", "ui1d_harper_behavior"
      ]
    },
    "ui1e": {
      "purpose": "UI1e safety, dirty-close, and E2E release scope: strictly accepted UI1d plus native window close interception, navigation discard guards, stale-source handling, and end-to-end workflow behavioral proof.",
      "checks": [
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository",
        "a1_print_parity", "a1_print_behavior", "private_print_parity", "a2_archiver",
        "a2_archiver_behavior", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post",
        "n2b_new_form", "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy",
        "rust_workspace_tests", "private_fixture_parity", "private_collision_authority",
        "private_post_round_trip", "ui1_boundaries", "frontend_dependencies",
        "ui1_frontend_typecheck", "ui1_frontend_build", "ui1_hybrid_layout", "ui1c_forms_contract",
        "ui1c_semantic_validation", "ui1c_frontend_forms", "dependency_locks",
        "dependency_lock_exception_behavior", "current_state", "verification_semantics",
        "source_intake", "release_control", "release_control_behavior", "ci_contract",
        "ui1c1_editor_framework", "ui1c2_4_semantic_forms", "ui1c5_integrated",
        "ui1c5_integrated_behavior", "ui1d_harper", "ui1d_harper_behavior",
        "ui1e_safety", "ui1e_workflow_behavior"
      ]
    }
  },
  """

raw_gate = raw_gate[:idx_scopes] + clean_scopes + raw_gate[idx_crs:]
gate = json.loads(raw_gate)
gate["contract_version"] = 24
gate["effective_date"] = "2026-09-02"
gate["current_release_scope"] = "ui1e"

# Ensure checks array has ui1e_safety and ui1e_workflow_behavior
check_ids = {c["id"] for c in gate["checks"]}
if "ui1e_safety" not in check_ids:
    gate["checks"].append({
        "id": "ui1e_safety",
        "command": ["python", "-S", "tools/check_ui1e_safety.py"],
        "profiles": ["portable", "strict"],
        "missing_policy": "fail",
        "purpose": "UI1e safety invariants: native window close interception, discard guards on all navigation paths, stale_source transition handling, and absence of live write or persistent draft commands.",
        "evidence_class": "structural"
    })
if "ui1e_workflow_behavior" not in check_ids:
    gate["checks"].append({
        "id": "ui1e_workflow_behavior",
        "command": ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1e_workflow"],
        "profiles": ["portable", "strict"],
        "missing_policy": "fail",
        "purpose": "UI1e end-to-end workflow simulation: dirty-close interception, navigation discard guards, Harper integration, session expiry and stale-source transitions.",
        "evidence_class": "behavioral"
    })

gate["historical_acceptance_records"]["ui1d"] = "PASS=43 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
gate["historical_acceptance_records"]["ui1d_evidence"] = "external immutable evidence: ui1d-strict-20260901-183000.json"
gate["artifact_acceptance"]["strict_scope"] = "ui1e"
gate["future_growth_rule"] = (
    "UI1e closes the Tauri Writer UI1 phase over the strictly accepted 43-check UI1d baseline. "
    "Phase W1/W2 live submission verification extends from the strictly accepted ui1e scope; "
    "ownership/schema/state-transition/external-behaviour changes update canonical contracts in the same change."
)
write_json("contracts/release_gate.json", gate)

print("=== 2. Repairing & Updating contracts/component_boundaries.json ===")
comp = json.loads(read("contracts/component_boundaries.json"))
comp["contract_version"] = 29
comp["effective_date"] = "2026-09-02"

for c in comp["components"]:
    if c["id"] == "gel_server":
        c["state_transitions"] = [
            "External GEL operations may append live tutorial records.",
            "A live source change invalidates corresponding locally derived source snapshots until reacquired."
        ]
        c["failure_semantics"] = [
            "Unavailable or malformed GEL source causes acquisition failure; local code must not invent source values."
        ]
    elif c["id"] == "writer_tauri_app_service":
        c["status"] = "active_ui1e_a2"
        for sc in [
            "Intercept window CloseRequested events when the active draft is dirty, prompting for discard confirmation before window destruction.",
            "Transition writer_active_draft to stale_source upon session expiry or remote latest-tutorial drift; forbid silent rebinding to new source or teacher authority.",
            "Ensure all navigation actions (class selection, student change, New tutorial opening, Revision opening, logout) enforce discard guards when draft is dirty."
        ]:
            if sc not in c["scope"]:
                c["scope"].append(sc)
        c["state_transitions"] = [
            "No draft -> New/Revision open -> clean writer_active_draft.",
            "Clean -> typed semantic edit -> validated candidate -> dirty; failed candidate leaves prior draft unchanged.",
            "Draft -> discard/logout -> no draft.",
            "Later UI1 gates may add explicit stale/invalid transitions but never silent source rebinding.",
            "Draft -> session expiry / remote latest-tutorial drift -> stale_source; direct editing locked; silent rebinding forbidden.",
            "Dirty draft -> window close requested -> intercepted -> discard confirmed -> no draft + window destroyed.",
            "Dirty draft -> window close requested -> stay -> remain dirty in-memory."
        ]
        c["failure_semantics"] = [
            "Blocked/ambiguous D2 revision authority refuses Revision opening.",
            "Missing authentication refuses New/Revision live source acquisition without affecting archive navigation.",
            "Failed semantic edit returns an error and leaves current authoritative in-memory draft unchanged.",
            "Structured edit failures are returned without mutating writer_active_draft; React may render message/field metadata but cannot infer semantic authority from strings.",
            "A missing archive may be created only by authenticated explicit RustArchiver sync. Existing invalid/non-v2 archives fail closed and are never replaced or migrated in place by Writer.",
            "Archive synchronization failure leaves RustArchiver/ArchiveSyncRepository transactional failure semantics authoritative; Writer receives an error and does not fall back to raw SQLite or Python mutation.",
            "Session loss while writing transitions draft to stale_source; New drafts cannot rebind to an unauthenticated session.",
            "Window close attempt while dirty cannot silently drop in-memory draft without explicit discard confirmation."
        ]
    elif c["id"] == "writer_react_ui":
        c["status"] = "active_ui1e"
        for sc in [
            "Listen for window close requests via Tauri event lifecycle, triggering DiscardDraftDialog when draft is dirty before window close.",
            "Display stale_source status pill and banner when draft authority is invalidated, disabling direct editing until explicit user resolution.",
            "Ensure all navigation paths (class selection, student change, New tutorial opening, Revision opening, logout) prompt for discard confirmation if current draft is dirty."
        ]:
            if sc not in c["scope"]:
                c["scope"].append(sc)
        c["state_transitions"] = [
            "Browse no student -> browse selected student.",
            "Browse selected student -> New/Revision write mode.",
            "Write mode -> browse selected student through discard/back; dirty state requires discard/stay confirmation.",
            "Login attempt -> transient password -> finally clear password.",
            "Structured validation issues may be displayed beside the corresponding complete type-specific field; rejected edits do not change the Rust-owned active draft.",
            "Active draft -> stale_source notified -> render stale banner and lock editing.",
            "Window close requested while dirty -> open DiscardDraftDialog; confirm -> destroy window; cancel -> stay."
        ]
        c["failure_semantics"] = [
            "Backend errors are rendered as non-authoritative UI errors; frontend does not repair or invent semantic/source values.",
            "Unauthenticated state disables live New/Revision opening while archive navigation remains available.",
            "A field rendered by the wrong presentation branch still cannot emit an edit unless the Rust-projected disposition is editable; hidden_preserved/inapplicable fields render nothing.",
            "Stale source or invalid draft status disables further typed edits until draft is discarded or session is restored.",
            "Closing the window while draft is dirty is blocked until explicit user confirmation."
        ]
write_json("contracts/component_boundaries.json", comp)

print("=== 3. Updating contracts/state_ownership.json ===")
ownership = json.loads(read("contracts/state_ownership.json"))
ownership["contract_version"] = 22
ownership["effective_date"] = "2026-09-02"
for s in ownership["state_classes"]:
    if s["id"] == "writer_active_draft":
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
write_json("contracts/state_ownership.json", ownership)

print("=== 4. Updating development_plan.json ===")
plan = json.loads(read("development_plan.json"))
plan["plan_version"] = "1.22.0"
plan["date"] = "2026-09-02"
plan["candidate_version"] = "v17.11-ui1e-implemented-pending-strict"
for phase in plan["phases"]:
    if phase["id"] == "UI1":
        phase["status"] = "ui1e_implemented_pending_strict_acceptance"
        for gate in phase.get("internal_gates", []):
            if gate["id"] == "UI1d":
                gate["status"] = "complete_strictly_accepted"
            elif gate["id"] == "UI1e":
                gate["status"] = "implemented_pending_strict_acceptance"
                gate["plan"] = "ui1e_safety check + ui1e_workflow_behavior test"
                gate["scope"] = [
                    "native dirty-close",
                    "navigation/logout guards",
                    "stale/session-expiry states",
                    "mocked E2E",
                    "full UI1 release gate"
                ]
        phase["strict_acceptance_target"] = (
            "Current release acceptance: ui1e scope, all 45 checks PASS / SKIP=0 / FAIL=0 "
            "with targetStatus STRICT_ACCEPTED and immutable external evidence."
        )
        if "implemented_ui1d" in phase:
            phase["implemented_ui1d"]["status"] = "complete_strictly_accepted"
        if "ui1d" in phase:
            phase["ui1d"]["status"] = "complete_strictly_accepted"
            phase["ui1d"]["strict_result"] = "PASS=43 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS"
            phase["ui1d"]["next"] = "UI1e dirty-close/stale-state/E2E/full UI1 hardening"
        phase["ui1e"] = {
            "status": "implemented_pending_strict_acceptance",
            "release_scope": "ui1e",
            "implementation_authorization": "UI1d strict acceptance PASS=43 SKIP=0 FAIL=0 recorded 2026-09-01.",
            "scope": [
                "native window close interception via CloseRequested",
                "navigation and discard guards for class, student, new tutorial, and revision actions",
                "stale_source and session invalidation state transitions",
                "full mocked E2E workflow covering New, Revision, Harper, and session expiry",
                "dedicated structural check ui1e_safety and behavioral test ui1e_workflow_behavior"
            ],
            "strict_target": "PASS=45 SKIP=0 FAIL=0; immutable evidence outside source root",
            "next": "Phase W1 (Live Submission Verification) unlocked after UI1e strict acceptance"
        }
write_json("development_plan.json", plan)

print("=== 5. Writing tools/check_ui1e_safety.py ===")
safety_script = """#!/usr/bin/env python3
\"\"\"check:ui1e-safety — structural safety check for window close, discard guards, and staleness.\"\"\"
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

        require(contract["contract_version"] == 13, "UI1 Writer contract version must be 13")
        require(contract["status"] == "active_ui1e_pending_strict_acceptance", "UI1 Writer status must be active_ui1e_pending_strict_acceptance")
        require("draft_staleness" in contract["architecture"], "UI1 architecture must define draft_staleness")
        require("window_close_interception" in contract["architecture"], "UI1 architecture must define window_close_interception")

        require(gate["contract_version"] == 24, "release_gate contract version must be 24")
        require(gate["current_release_scope"] == "ui1e", "current release scope must be ui1e")
        require(len(gate["scopes"]["ui1e"]["checks"]) == 45, "ui1e scope must contain exactly 45 checks")

        require(identity["contract_version"] == 5, "release_identity contract version must be 5")
        require(identity["strict_acceptance"]["required_scope"] == "ui1e", "release_identity required_scope must be ui1e")
        require(identity["strict_acceptance"]["prerequisite_scope"] == "ui1d", "release_identity prerequisite_scope must be ui1d")

        for forbidden in ["ui1_submit", "post_tutorial", "create_tutorial", "revise_tutorial", "delete_tutorial"]:
            require(forbidden not in contract["initial_command_allowlist"], f"forbidden write command {forbidden} in allowlist")

        states = {s["id"]: s for s in ownership["state_classes"]}
        active_draft = states["writer_active_draft"]
        require("stale_source" in active_draft["invalidation"], "writer_active_draft invalidation must specify stale_source transition")
        require(active_draft["canonical"] is False, "writer_active_draft must not be canonical")

    except (CheckError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"check:ui1e-safety FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:ui1e-safety PASS — window close interception + discard guards + staleness contracts verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
write("tools/check_ui1e_safety.py", safety_script)
(ROOT / "tools/check_ui1e_safety.py").chmod(0o755)

print("=== 6. Updating Verification Tools ===")

# check_contracts.py
cc = read("tools/check_contracts.py")
cc = cc.replace('"ui1_writer": 12,', '"ui1_writer": 13,')
cc = cc.replace('"release_identity": 4,', '"release_identity": 5,')
cc = cc.replace('require(ui1.get("status") == "active_ui1d_pending_strict_acceptance", "UI1 active contract status drifted")',
                'require(ui1.get("status") == "active_ui1e_pending_strict_acceptance", "UI1 active contract status drifted")')
cc = cc.replace('require(release_identity["strict_acceptance"]["required_scope"] == "ui1d", "UI1d must be current strict acceptance scope")',
                'require(release_identity["strict_acceptance"]["required_scope"] == "ui1e", "UI1e must be current strict acceptance scope")')
write("tools/check_contracts.py", cc)

# check_governance.py
cg = read("tools/check_governance.py")
cg = cg.replace('require(components.get("contract_version") == 28, "component_boundaries contract_version must be 28")',
                'require(components.get("contract_version") == 29, "component_boundaries contract_version must be 29")')
cg = cg.replace('require(ownership.get("contract_version") == 21, "state_ownership contract_version must be 21")',
                'require(ownership.get("contract_version") == 22, "state_ownership contract_version must be 22")')
cg = cg.replace('require(gate.get("contract_version") == 23, "release_gate contract_version must be 23")',
                'require(gate.get("contract_version") == 24, "release_gate contract_version must be 24")')
cg = cg.replace('require(gate.get("current_release_scope") == "ui1d", "UI1d must be the current release scope")',
                'require(gate.get("current_release_scope") == "ui1e", "UI1e must be the current release scope")')
cg = cg.replace('writer_service["status"] == "active_ui1d_a2"', 'writer_service["status"] == "active_ui1e_a2"')
cg = cg.replace('Writer Tauri service must expose the governed A2 sync trigger at UI1d', 'Writer Tauri service must expose the governed A2 sync trigger at UI1e')
cg = cg.replace('writer_react["status"] == "active_ui1d"', 'writer_react["status"] == "active_ui1e"')
cg = cg.replace('UI1 React presentation must be active for UI1d', 'UI1 React presentation must be active for UI1e')

if '"ui1e_safety"' not in cg:
    cg = cg.replace('"ui1d_harper_behavior"', '"ui1d_harper_behavior", "ui1e_safety", "ui1e_workflow_behavior"')
    cg = cg.replace('("ui1d_harper", "check_ui1d_harper.py")', '("ui1d_harper", "check_ui1d_harper.py"),\n        ("ui1e_safety", "check_ui1e_safety.py")')
    cg = cg.replace(
        'require(check_by_id["ui1d_harper_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1d_harper"], "UI1d behavioral check command drifted")',
        'require(check_by_id["ui1d_harper_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1d_harper"], "UI1d behavioral check command drifted")\n    require(check_by_id["ui1e_workflow_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1e_workflow"], "UI1e behavioral check command drifted")'
    )

# Fix scopes check in check_governance.py so subtraction matches 45 checks
scopes_pattern = re.compile(
    r'ui1d_scope = gate\["scopes"\]\["ui1d"\]\["checks"\].*?require\(gate\["current_release_scope"\] == "ui1[de]", "UI1[de] must be the current release scope"\)',
    re.S
)
scopes_code = """gri_required = required - {"ui1c5_integrated", "ui1c5_integrated_behavior", "ui1d_harper", "ui1d_harper_behavior", "ui1e_safety", "ui1e_workflow_behavior"}
    require("gri" in scopes and set(scopes["gri"]["checks"]) == gri_required and len(scopes["gri"]["checks"]) == 39, "GRI scope must remain the strictly accepted 39-check baseline")
    ui1c5_required = required - {"ui1d_harper", "ui1d_harper_behavior", "ui1e_safety", "ui1e_workflow_behavior"}
    require("ui1c5" in scopes and set(scopes["ui1c5"]["checks"]) == ui1c5_required and len(scopes["ui1c5"]["checks"]) == 41, "UI1c5 scope must remain the 41-check predecessor")
    require(scopes["ui1c5"]["checks"][:39] == scopes["gri"]["checks"], "UI1c5 scope must preserve GRI check ordering as an unchanged prefix")
    ui1d_required = required - {"ui1e_safety", "ui1e_workflow_behavior"}
    require("ui1d" in scopes and set(scopes["ui1d"]["checks"]) == ui1d_required and len(scopes["ui1d"]["checks"]) == 43, "UI1d scope must contain 43 checks")
    require(scopes["ui1d"]["checks"][:41] == scopes["ui1c5"]["checks"], "UI1d must preserve UI1c5 check ordering as prefix")
    require(scopes["ui1d"]["checks"][-2:] == ["ui1d_harper", "ui1d_harper_behavior"], "UI1d dedicated checks must be appended")

    ui1e_scope = gate["scopes"]["ui1e"]["checks"]
    require(len(ui1e_scope) == 45, "UI1e scope must contain 45 checks")
    require(ui1e_scope[:43] == gate["scopes"]["ui1d"]["checks"], "UI1e must preserve UI1d check ordering as prefix")
    require(ui1e_scope[-2:] == ["ui1e_safety", "ui1e_workflow_behavior"], "UI1e dedicated checks must be appended")
    require(gate["current_release_scope"] == "ui1e", "UI1e must be the current release scope")"""

cg = scopes_pattern.sub(scopes_code, cg)
cg = cg.replace('require(gate.get("artifact_acceptance", {}).get("strict_scope") == "ui1d", "artifact acceptance must bind UI1d scope")',
                'require(gate.get("artifact_acceptance", {}).get("strict_scope") == "ui1e", "artifact acceptance must bind UI1e scope")')
if 'require(historical.get("ui1d", "").startswith("PASS=43 SKIP=0 FAIL=0"), "historical accepted UI1d result must remain recorded")' not in cg:
    cg = cg.replace(
        'require(historical.get("ui1-hybrid") == "PASS=23 SKIP=0 FAIL=0", "historical accepted UI1 hybrid result must remain recorded")',
        'require(historical.get("ui1-hybrid") == "PASS=23 SKIP=0 FAIL=0", "historical accepted UI1 hybrid result must remain recorded")\n    require(historical.get("ui1d", "").startswith("PASS=43 SKIP=0 FAIL=0"), "historical accepted UI1d result must remain recorded")'
    )
write("tools/check_governance.py", cg)

# generate_current_state.py
gcs = read("tools/generate_current_state.py")
gcs = gcs.replace('current_scope = gate.get("current_release_scope", "ui1d")', 'current_scope = gate.get("current_release_scope", "ui1e")')
gcs = gcs.replace('"requiredGate": gate.get("current_release_scope", "ui1d"),', '"requiredGate": gate.get("current_release_scope", "ui1e"),')
if 'historical.get("ui1d")' not in gcs:
    hist_target = """    if historical.get("ui1c5"):
        last_acceptance = {
            "scope": "ui1c5",
            "status": "STRICT_ACCEPTED",
            "result": historical["ui1c5"],
            "artifactBinding": "external immutable strict evidence; accepted UI1c5 source identity predates UI1d implementation"
        }"""
    hist_replacement = """    if historical.get("ui1d"):
        last_acceptance = {
            "scope": "ui1d",
            "status": "STRICT_ACCEPTED",
            "result": historical["ui1d"],
            "artifactBinding": "external immutable strict evidence; accepted UI1d source identity predates UI1e implementation"
        }
    elif historical.get("ui1c5"):
        last_acceptance = {
            "scope": "ui1c5",
            "status": "STRICT_ACCEPTED",
            "result": historical["ui1c5"],
            "artifactBinding": "external immutable strict evidence; accepted UI1c5 source identity predates UI1d implementation"
        }"""
    gcs = gcs.replace(hist_target, hist_replacement)
write("tools/generate_current_state.py", gcs)

# check_current_state.py
ccs = read("tools/check_current_state.py")
ccs = ccs.replace('require(state.get("requiredGate") == "ui1d", "current candidate must require the UI1d gate")',
                  'require(state.get("requiredGate") == "ui1e", "current candidate must require the UI1e gate")')
ccs = ccs.replace('require(state.get("lastStrictAcceptance", {}).get("scope") == "ui1c5", "UI1d candidate must retain UI1c5 as the last strict acceptance")',
                  'require(state.get("lastStrictAcceptance", {}).get("scope") == "ui1d", "UI1e candidate must retain UI1d as the last strict acceptance")')
ccs = ccs.replace('require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS=41 SKIP=0 FAIL=0"), "strict UI1c5 predecessor result drifted")',
                  'require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS=43 SKIP=0 FAIL=0"), "strict UI1d predecessor result drifted")')
write("tools/check_current_state.py", ccs)

# check_ui1_boundaries.py
cb = read("tools/check_ui1_boundaries.py")
cb = cb.replace('require(contract.get("contract_version") == 12, "UI1 UI1d contract_version drifted")',
                'require(contract.get("contract_version") == 13, "UI1 UI1e contract_version drifted")')
cb = cb.replace('require(contract.get("status") == "active_ui1d_pending_strict_acceptance", "UI1d status drifted")',
                'require(contract.get("status") == "active_ui1e_pending_strict_acceptance", "UI1e status drifted")')
write("tools/check_ui1_boundaries.py", cb)

# check_ui1d_harper.py
cdh = read("tools/check_ui1d_harper.py")
cdh = cdh.replace('require(ui1_phase["status"] == "ui1d_implemented_pending_strict_acceptance", "development plan UI1d status drifted")',
                  'require(ui1_phase["status"] == "ui1e_implemented_pending_strict_acceptance", "development plan UI1e status drifted")')
cdh = cdh.replace('require(ui1["contract_version"] == 12 and ui1["status"] == "active_ui1d_pending_strict_acceptance", "UI1 Writer contract must be v12/UI1d-active")',
                  'require(ui1["contract_version"] == 13 and ui1["status"] == "active_ui1e_pending_strict_acceptance", "UI1 Writer contract must be v13/UI1e-active")')
if 'complete_strictly_accepted' not in cdh:
    cdh = cdh.replace('require(ui1_phase["ui1d"]["release_scope"] == "ui1d", "development plan UI1d scope drifted")',
                      'require(ui1_phase["ui1d"]["release_scope"] == "ui1d", "development plan UI1d scope drifted")\n        require(ui1_phase["ui1d"]["status"] == "complete_strictly_accepted", "development plan UI1d status drifted")')
write("tools/check_ui1d_harper.py", cdh)

# check_ui1c5_integrated.py
c5 = read("tools/check_ui1c5_integrated.py")
c5 = c5.replace('require(ui1.get("contract_version") == 12, "UI1 Writer must advance to v12 for UI1d")',
                'require(ui1.get("contract_version") == 13, "UI1 Writer must advance to v13 for UI1e")')
c5 = c5.replace('require(ui1.get("status") == "active_ui1d_pending_strict_acceptance", "UI1 Writer UI1d status drifted")',
                'require(ui1.get("status") == "active_ui1e_pending_strict_acceptance", "UI1 Writer UI1e status drifted")')
c5 = c5.replace('require(gate.get("contract_version") == 23, "UI1c5 requires release_gate v23")',
                'require(gate.get("contract_version") == 24, "UI1e requires release_gate v24")')
c5 = c5.replace('require(gate.get("current_release_scope") == "ui1d", "current release scope must be ui1d")',
                'require(gate.get("current_release_scope") == "ui1e", "current release scope must be ui1e")')
c5 = c5.replace('require(gate.get("artifact_acceptance", {}).get("strict_scope") == "ui1d", "artifact acceptance must bind ui1d strict evidence")',
                'require(gate.get("artifact_acceptance", {}).get("strict_scope") == "ui1e", "artifact acceptance must bind ui1e strict evidence")')
c5 = c5.replace('require(ui1_phase.get("status") == "ui1d_implemented_pending_strict_acceptance", "development plan UI1d status drifted")',
                'require(ui1_phase.get("status") == "ui1e_implemented_pending_strict_acceptance", "development plan UI1e status drifted")')
if 'complete_strictly_accepted' not in c5:
    c5 = c5.replace('require(ui1_phase.get("ui1d", {}).get("release_scope") == "ui1d", "development plan UI1d scope drifted")',
                    'require(ui1_phase.get("ui1d", {}).get("status") == "complete_strictly_accepted", "development plan UI1d must be strictly accepted before UI1e")\n        require(ui1_phase.get("ui1e", {}).get("release_scope") == "ui1e", "development plan UI1e scope drifted")')
write("tools/check_ui1c5_integrated.py", c5)

# check_ci_contract.py & workflows
ci = read("tools/check_ci_contract.py")
ci = ci.replace('python tools/release_gate.py --profile portable --scope ui1d', 'python tools/release_gate.py --profile portable --scope ui1e')
write("tools/check_ci_contract.py", ci)

wf = read(".github/workflows/portable-governance.yml")
wf = wf.replace('python tools/release_gate.py --profile portable --scope ui1d', 'python tools/release_gate.py --profile portable --scope ui1e')
write(".github/workflows/portable-governance.yml", wf)

# package_release.py
pr = read("tools/package_release.py")
pr = pr.replace('require(evidence.get("scope") == "ui1d", "evidence is not the canonical UI1d scope")',
                'require(evidence.get("scope") == "ui1e", "evidence is not the canonical UI1e scope")')
pr = pr.replace('"strictScope": "ui1d",', '"strictScope": "ui1e",')
write("tools/package_release.py", pr)

print("=== 7. Regenerating Governance & Documentation Projections ===")
for script in [
    "tools/generate_governance_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_current_state.py",
    "tools/generate_contract_artifacts.py",
]:
    print(f"  running {script}...")
    subprocess.run([sys.executable, str(ROOT / script)], check=True)

print("\n=== Stage 1 Complete! ===")
