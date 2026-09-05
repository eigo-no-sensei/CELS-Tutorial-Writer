#!/usr/bin/env python3
"""apply_w2_preflight_in_place.py — Apply Phase W2 pre-flight contract and governance alignment."""
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

print("=== 1. Updating contracts/component_boundaries.json ===")
comp = json.loads(read("contracts/component_boundaries.json"))
comp["contract_version"] = 30
comp["effective_date"] = "2026-09-03"

# Remove live_submission_transport from planned_not_active
comp["planned_not_active"] = [x for x in comp.get("planned_not_active", []) if x != "live_submission_transport"]

# Add live_submission_transport to components if not present
existing_comp_ids = {c["id"] for c in comp["components"]}
if "live_submission_transport" not in existing_comp_ids:
    comp["components"].append({
        "id": "live_submission_transport",
        "name": "Live submission transport",
        "status": "active_w2",
        "role": "Submit governed tutorial POST payloads to the authoritative GEL server and discover canonical tutorial identity via post-submit readback.",
        "scope": [
            "Construct and dispatch authenticated POST /study/tutorials/process requests using the session client.",
            "Enforce New vs Revision submission rules: datetime omitted for New, exact source timestamp preserved for Revision; immutable origin teacher authority.",
            "On submission success, immediately perform fresh GET /staff/students/{uid}/tutorials readback to discover canonical server-assigned tutorial_id and timestamp.",
            "Trigger targeted RustArchiver sync to reconcile the server tutorial record into SQLite archive_v2.",
            "On submission failure (network, 401/403, 500, HTML redirect), leave active in-memory draft dirty and retryable; forbid blind local SQLite insertion."
        ],
        "authority": [
            "Production GEL tutorial network write transport authority.",
            "GEL server remains authoritative for live tutorial existence and canonical identity.",
            "Client-side prediction of server-assigned tutorial identity or timestamp is strictly forbidden."
        ],
        "reads": [
            "tutorial_post_payload",
            "authenticated_gel_session",
            "repository_contracts"
        ],
        "writes": [
            "live_submission_response"
        ],
        "must_not_write": [
            "live_gel_tutorials",
            "normalized_local_archive",
            "archive_v2_candidate_database",
            "archive_reconciliation_metadata",
            "repository_contracts",
            "private_fixtures",
            "semantic_form_state",
            "writer_active_draft"
        ],
        "state_transitions": [
            "Ephemeral payload -> HTTP POST -> HTTP 200 / redirect -> GET readback -> targeted sync -> clear in-memory draft.",
            "Ephemeral payload -> HTTP POST -> network failure / server error -> draft retained dirty and retryable."
        ],
        "failure_semantics": [
            "Transport or server failure preserves active draft dirty in process memory without silent discard.",
            "No canonical SQLite row is synthesized on failure.",
            "Network timeout triggers conflict check on retry before re-submission."
        ],
        "dependencies": [
            "rust_post_mapper",
            "rust_gel_session",
            "rust_archive_sync_repository"
        ],
        "tests": [
            "tools/check_w2_boundaries.py"
        ]
    })

for c in comp["components"]:
    if c["id"] == "writer_tauri_app_service":
        c["status"] = "active_w2_a2"
        if "live_submission_response" not in c["reads"]:
            c["reads"].append("live_submission_response")
        sc = "Coordinate production tutorial submission via live_submission_transport, triggering post-submit readback and targeted archive reconciliation."
        if sc not in c["scope"]:
            c["scope"].append(sc)
        if "tools/check_w2_boundaries.py" not in c["tests"]:
            c["tests"].append("tools/check_w2_boundaries.py")
write_json("contracts/component_boundaries.json", comp)

print("=== 2. Updating contracts/state_ownership.json ===")
ownership = json.loads(read("contracts/state_ownership.json"))
ownership["contract_version"] = 23
ownership["effective_date"] = "2026-09-03"

state_ids = {s["id"] for s in ownership["state_classes"]}
if "live_submission_response" not in state_ids:
    ownership["state_classes"].append({
        "id": "live_submission_response",
        "class": "ephemeral_runtime_response",
        "source_or_derived": "source",
        "canonical": False,
        "permitted_writers": [
            "live_submission_transport"
        ],
        "readers": [
            "writer_tauri_app_service",
            "developers"
        ],
        "retention": "Process memory only. Transient HTTP response status and redirect headers from tutorial process submission.",
        "invalidation": "Discarded immediately after readback discovery and targeted archive reconciliation.",
        "current_materialization": "Rust LiveSubmissionReceipt in process memory.",
        "state_kind": "source"
    })

for s in ownership["state_classes"]:
    if s["id"] == "tutorial_post_payload":
        if "live_submission_transport" not in s["readers"]:
            s["readers"].append("live_submission_transport")
        s["retention"] = "Ephemeral derived payload produced by rust_post_mapper, consumed by live_submission_transport for production GEL submission."
    elif s["id"] == "authenticated_gel_session":
        if "live_submission_transport" not in s["readers"]:
            s["readers"].append("live_submission_transport")
    elif s["id"] == "repository_contracts":
        if "live_submission_transport" not in s["readers"]:
            s["readers"].append("live_submission_transport")
    elif s["id"] == "writer_active_draft":
        s["invalidation"] = (
            "Discard/logout/confirmed window close/process exit removes the draft. "
            "Successful submission transitions draft to cleared/unloaded upon post-submit readback and targeted archive sync. "
            "Failed submission retains draft as dirty and retryable. "
            "Session expiry (HTTP 401/403 or login redirect) or latest tutorial remote drift transitions active draft to stale_source."
        )
    elif s["id"] == "live_gel_tutorials":
        s["retention"] = "Owned externally by GEL. Created or updated on the server via live_submission_transport during Phase W2; local code never deletes live tutorial records."

write_json("contracts/state_ownership.json", ownership)

print("=== 3. Updating contracts/ui1_writer.json ===")
ui1 = json.loads(read("contracts/ui1_writer.json"))
ui1["contract_version"] = 14
ui1["effective_date"] = "2026-09-03"
ui1["status"] = "active_w2_pending_strict_acceptance"
ui1["architecture"]["submission"] = "production submission command ui1_submit_draft delegating to live_submission_transport"
if "ui1_submit_draft" not in ui1["initial_command_allowlist"]:
    ui1["initial_command_allowlist"].append("ui1_submit_draft")

ui1["forbidden_command_capabilities"] = [
    x if x != "tutorial POST/create/revise/delete" else "arbitrary or unvalidated tutorial POST outside ui1_submit_draft"
    for x in ui1["forbidden_command_capabilities"]
]
write_json("contracts/ui1_writer.json", ui1)

print("=== 4. Updating Semantic and Authority Contracts ===")
n2a = json.loads(read("contracts/n2a_semantic_post_authority.json"))
n2a["contract_version"] = 3
n2a["effective_date"] = "2026-09-03"
n2a["network_write_authority"] = True
n2a["resolved_preconditions"]["teacher_serialization_residual"] = (
    "Teacher reassignment is permanently unsupported in production Writer: "
    "Revisions strictly preserve historical teacher, and New tutorials strictly use authenticated teacher."
)
n2a["deferred_non_blocking"] = []
n2a["failure_semantics"] = [
    x if not x.startswith("No network write authority") else "Network write authority is granted exclusively through live_submission_transport under Phase W2."
    for x in n2a["failure_semantics"]
]
write_json("contracts/n2a_semantic_post_authority.json", n2a)

sem = json.loads(read("contracts/tutorial_form_semantics.json"))
sem["contract_version"] = 7
sem["effective_date"] = "2026-09-03"
sem["teacher_authority"]["reassignment_product_status"] = "unsupported_permanently_retired"
sem["failure_semantics"] = [
    x if not x.startswith("No network write authority") else "Network write authority is granted exclusively through live_submission_transport under Phase W2."
    for x in sem["failure_semantics"]
]
write_json("contracts/tutorial_form_semantics.json", sem)

n2c = json.loads(read("contracts/new_tutorial_prepopulation.json"))
n2c["contract_version"] = 2
n2c["effective_date"] = "2026-09-03"
n2c["deferred_non_blocking"] = []
write_json("contracts/new_tutorial_prepopulation.json", n2c)

print("=== 5. Updating contracts/release_identity.json and release_gate.json ===")
identity = json.loads(read("contracts/release_identity.json"))
identity["contract_version"] = 6
identity["effective_date"] = "2026-09-03"
identity["strict_acceptance"]["required_scope"] = "w2"
identity["strict_acceptance"]["prerequisite_scope"] = "ui1e"
write_json("contracts/release_identity.json", identity)

gate = json.loads(read("contracts/release_gate.json"))
gate["contract_version"] = 25
gate["effective_date"] = "2026-09-03"
gate["current_release_scope"] = "w2"

check_ids = {c["id"] for c in gate["checks"]}
if "w2_boundaries" not in check_ids:
    gate["checks"].append({
        "id": "w2_boundaries",
        "command": ["python", "-S", "tools/check_w2_boundaries.py"],
        "profiles": ["portable", "strict"],
        "missing_policy": "fail",
        "purpose": "W2 live submission transport boundaries: governed POST transport, readback discovery, targeted archive sync, and dirty-on-failure recovery.",
        "evidence_class": "structural"
    })

if "w2" not in gate["scopes"]:
    gate["scopes"]["w2"] = {
        "purpose": "Phase W2 production submission release scope: strictly accepted UI1e baseline plus dedicated W2 submission boundary checks.",
        "checks": gate["scopes"]["ui1e"]["checks"] + ["w2_boundaries"]
    }

gate["artifact_acceptance"]["strict_scope"] = "w2"
gate["future_growth_rule"] = "Phase W2 live submission verification extends from the strictly accepted ui1e/w1 baseline; production release requires w2 strict acceptance."
write_json("contracts/release_gate.json", gate)

print("=== 6. Writing tools/check_w2_boundaries.py ===")
w2_checker = """#!/usr/bin/env python3
\"\"\"check:w2-boundaries — structural boundary verification for Phase W2 live submission transport.\"\"\"
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
        comp = load("contracts/component_boundaries.json")
        own = load("contracts/state_ownership.json")
        ui1 = load("contracts/ui1_writer.json")
        n2a = load("contracts/n2a_semantic_post_authority.json")
        gate = load("contracts/release_gate.json")
        identity = load("contracts/release_identity.json")

        require(comp["contract_version"] == 30, "component_boundaries contract_version must be 30")
        require(len(comp.get("planned_not_active", [])) == 0, "planned_not_active must be empty after W2 activation")

        comps = {c["id"]: c for c in comp["components"]}
        require("live_submission_transport" in comps, "live_submission_transport component missing")
        lst = comps["live_submission_transport"]
        require(lst["status"] == "active_w2", "live_submission_transport status must be active_w2")
        require("normalized_local_archive" in lst["must_not_write"], "live_submission_transport must not write normalized_local_archive")
        require("live_submission_response" in lst["writes"], "live_submission_transport must write live_submission_response")

        states = {s["id"]: s for s in own["state_classes"]}
        require("live_submission_response" in states, "live_submission_response missing from state_ownership")
        require("live_submission_transport" in states["tutorial_post_payload"]["readers"], "tutorial_post_payload must be readable by live_submission_transport")

        require(ui1["contract_version"] == 14, "ui1_writer contract_version must be 14")
        require(ui1["status"] == "active_w2_pending_strict_acceptance", "ui1_writer status must be active_w2_pending_strict_acceptance")
        require("ui1_submit_draft" in ui1["initial_command_allowlist"], "ui1_submit_draft must be present in command allowlist")

        require(n2a["contract_version"] == 3, "n2a_semantic_post_authority contract_version must be 3")
        require(n2a["network_write_authority"] is True, "n2a network_write_authority must be true for W2")
        require(len(n2a.get("deferred_non_blocking", [])) == 0, "n2a deferred_non_blocking must be retired for W2")

        require(gate["contract_version"] == 25, "release_gate contract_version must be 25")
        require(gate["current_release_scope"] == "w2", "release_gate current_release_scope must be w2")
        require(len(gate["scopes"]["w2"]["checks"]) == 46, "w2 scope must contain 46 checks")

        require(identity["contract_version"] == 6, "release_identity contract_version must be 6")
        require(identity["strict_acceptance"]["required_scope"] == "w2", "release_identity required_scope must be w2")
        require(identity["strict_acceptance"]["prerequisite_scope"] == "ui1e", "release_identity prerequisite_scope must be ui1e")

    except (CheckError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"check:w2-boundaries FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:w2-boundaries PASS — live submission transport activated + command allowlist updated + W2 scope verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
write("tools/check_w2_boundaries.py", w2_checker)
(ROOT / "tools/check_w2_boundaries.py").chmod(0o755)

print("=== 7. Updating Governance & Contract Checkers ===")
# check_contracts.py
cc = read("tools/check_contracts.py")
cc = cc.replace('"ui1_writer": 13,', '"ui1_writer": 14,')
cc = cc.replace('"n2a_semantic_post_authority": 2,', '"n2a_semantic_post_authority": 3,')
cc = cc.replace('"tutorial_form_semantics": 6,', '"tutorial_form_semantics": 7,')
cc = cc.replace('"new_tutorial_prepopulation": 1,', '"new_tutorial_prepopulation": 2,')
cc = cc.replace('"release_identity": 5,', '"release_identity": 6,')
cc = cc.replace('require(ui1.get("status") == "active_ui1e_pending_strict_acceptance", "UI1 active contract status drifted")',
                'require(ui1.get("status") == "active_w2_pending_strict_acceptance", "UI1 active contract status drifted")')
cc = cc.replace('require(release_identity["strict_acceptance"]["required_scope"] == "ui1e", "UI1e must be current strict acceptance scope")',
                'require(release_identity["strict_acceptance"]["required_scope"] == "w2", "W2 must be current strict acceptance scope")')
cc = cc.replace('require(n2a.get("network_write_authority") is False, "N2a must grant no network write authority")',
                'require(n2a.get("network_write_authority") is True, "N2a network_write_authority must be true under W2")')
cc = cc.replace('require(n2a.get("contract_version") == 2, "N2a authority must be refined to v2")',
                'require(n2a.get("contract_version") == 3, "N2a authority must be v3 for W2")')
write("tools/check_contracts.py", cc)

# check_governance.py
cg = read("tools/check_governance.py")
cg = cg.replace('require(components.get("contract_version") == 29, "component_boundaries contract_version must be 29")',
                'require(components.get("contract_version") == 30, "component_boundaries contract_version must be 30")')
cg = cg.replace('require(ownership.get("contract_version") == 22, "state_ownership contract_version must be 22")',
                'require(ownership.get("contract_version") == 23, "state_ownership contract_version must be 23")')
cg = cg.replace('require(gate.get("contract_version") == 24, "release_gate contract_version must be 24")',
                'require(gate.get("contract_version") == 25, "release_gate contract_version must be 25")')
cg = cg.replace('require(gate.get("current_release_scope") == "ui1e", "UI1e must be the current release scope")',
                'require(gate.get("current_release_scope") == "w2", "W2 must be the current release scope")')
cg = cg.replace('writer_service["status"] == "active_ui1e_a2"', 'writer_service["status"] == "active_w2_a2"')
cg = cg.replace('Writer Tauri service must expose the governed A2 sync trigger at UI1e', 'Writer Tauri service must be active at W2')
cg = cg.replace('require(gate.get("artifact_acceptance", {}).get("strict_scope") == "ui1e", "artifact acceptance must bind UI1e scope")',
                'require(gate.get("artifact_acceptance", {}).get("strict_scope") == "w2", "artifact acceptance must bind W2 scope")')

# Update check_governance required check set to include w2_boundaries
if '"w2_boundaries"' not in cg:
    cg = cg.replace(
        '"ui1e_workflow_behavior"',
        '"ui1e_workflow_behavior", "w2_boundaries"'
    )
    cg = cg.replace(
        '("ui1e_safety", "check_ui1e_safety.py")',
        '("ui1e_safety", "check_ui1e_safety.py"),\n        ("w2_boundaries", "check_w2_boundaries.py")'
    )

# Update check_governance scopes assertion to handle w2 scope
w2_scopes_pattern = re.compile(
    r'ui1e_scope = gate\["scopes"\]\["ui1e"\]\["checks"\].*?require\(gate\["current_release_scope"\] == "ui1[de]", "UI1[de] must be the current release scope"\)',
    re.S
)
w2_scopes_code = """ui1e_scope = gate["scopes"]["ui1e"]["checks"]
    require(len(ui1e_scope) == 45, "UI1e scope must contain 45 checks")
    require(ui1e_scope[:43] == gate["scopes"]["ui1d"]["checks"], "UI1e must preserve UI1d check ordering as prefix")
    require(ui1e_scope[-2:] == ["ui1e_safety", "ui1e_workflow_behavior"], "UI1e dedicated checks must be appended")

    w2_scope = gate["scopes"]["w2"]["checks"]
    require(len(w2_scope) == 46, "W2 scope must contain 46 checks")
    require(w2_scope[:45] == ui1e_scope, "W2 must preserve UI1e check ordering as prefix")
    require(w2_scope[-1:] == ["w2_boundaries"], "W2 dedicated check must be appended")
    require(gate["current_release_scope"] == "w2", "W2 must be the current release scope")"""

cg = w2_scopes_pattern.sub(w2_scopes_code, cg)
write("tools/check_governance.py", cg)

# generate_current_state.py & check_current_state.py
gcs = read("tools/generate_current_state.py")
gcs = gcs.replace('current_scope = gate.get("current_release_scope", "ui1e")', 'current_scope = gate.get("current_release_scope", "w2")')
gcs = gcs.replace('"requiredGate": gate.get("current_release_scope", "ui1e"),', '"requiredGate": gate.get("current_release_scope", "w2"),')
write("tools/generate_current_state.py", gcs)

ccs = read("tools/check_current_state.py")
ccs = ccs.replace('require(state.get("requiredGate") == "ui1e", "current candidate must require the UI1e gate")',
                  'require(state.get("requiredGate") == "w2", "current candidate must require the W2 gate")')
write("tools/check_current_state.py", ccs)

# check_ui1e_safety.py
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

# check_ui1_boundaries.py
cb = read("tools/check_ui1_boundaries.py")
cb = cb.replace('require(contract.get("contract_version") == 13, "UI1 UI1e contract_version drifted")',
                'require(contract.get("contract_version") == 14, "UI1 W2 contract_version drifted")')
cb = cb.replace('require(contract.get("status") == "active_ui1e_pending_strict_acceptance", "UI1e status drifted")',
                'require(contract.get("status") == "active_w2_pending_strict_acceptance", "W2 status drifted")')
if '"ui1_submit_draft"' not in cb:
    cb = cb.replace('"ui1_discard_draft",', '"ui1_discard_draft",\n    "ui1_submit_draft",')
write("tools/check_ui1_boundaries.py", cb)

# check_ui1d_harper.py
cdh = read("tools/check_ui1d_harper.py")
cdh = cdh.replace('require(ui1["contract_version"] == 13 and ui1["status"] == "active_ui1e_pending_strict_acceptance", "UI1 Writer contract must be v13/UI1e-active")',
                  'require(ui1["contract_version"] == 14 and ui1["status"] == "active_w2_pending_strict_acceptance", "UI1 Writer contract must be v14/W2-active")')
cdh = cdh.replace('require(gate["current_release_scope"] == "ui1e", "current release scope must be ui1e")',
                  'require(gate["current_release_scope"] == "w2", "current release scope must be w2")')
write("tools/check_ui1d_harper.py", cdh)

# check_ui1c5_integrated.py
c5 = read("tools/check_ui1c5_integrated.py")
c5 = c5.replace('require(ui1.get("contract_version") == 13, "UI1 Writer must advance to v13 for UI1e")',
                'require(ui1.get("contract_version") == 14, "UI1 Writer must advance to v14 for W2")')
c5 = c5.replace('require(ui1.get("status") == "active_ui1e_pending_strict_acceptance", "UI1 Writer UI1e status drifted")',
                'require(ui1.get("status") == "active_w2_pending_strict_acceptance", "UI1 Writer W2 status drifted")')
c5 = c5.replace('require(gate.get("contract_version") == 24, "UI1e requires release_gate v24")',
                'require(gate.get("contract_version") == 25, "W2 requires release_gate v25")')
c5 = c5.replace('require(gate.get("current_release_scope") == "ui1e", "current release scope must be ui1e")',
                'require(gate.get("current_release_scope") == "w2", "current release scope must be w2")')
c5 = c5.replace('require(gate.get("artifact_acceptance", {}).get("strict_scope") == "ui1e", "artifact acceptance must bind ui1e strict evidence")',
                'require(gate.get("artifact_acceptance", {}).get("strict_scope") == "w2", "artifact acceptance must bind w2 strict evidence")')
write("tools/check_ui1c5_integrated.py", c5)

# check_n2a_semantic_post.py
cn2a = read("tools/check_n2a_semantic_post.py")
cn2a = cn2a.replace('require(n2a.get("contract_version") == 2, "N2a contract version must be 2 after N2b authority refinement")',
                    'require(n2a.get("contract_version") == 3, "N2a contract version must be 3 for W2")')
cn2a = cn2a.replace('require(n2a.get("network_write_authority") is False, "N2a must grant no network-write authority")',
                    'require(n2a.get("network_write_authority") is True, "N2a network_write_authority must be true under W2")')
write("tools/check_n2a_semantic_post.py", cn2a)

# check_ci_contract.py & workflows
ci = read("tools/check_ci_contract.py")
ci = ci.replace('python tools/release_gate.py --profile portable --scope ui1e', 'python tools/release_gate.py --profile portable --scope w2')
write("tools/check_ci_contract.py", ci)

wf = read(".github/workflows/portable-governance.yml")
wf = wf.replace('python tools/release_gate.py --profile portable --scope ui1e', 'python tools/release_gate.py --profile portable --scope w2')
write(".github/workflows/portable-governance.yml", wf)

# package_release.py
pr = read("tools/package_release.py")
pr = pr.replace('require(evidence.get("scope") == "ui1e", "evidence is not the canonical UI1e scope")',
                'require(evidence.get("scope") == "w2", "evidence is not the canonical W2 scope")')
pr = pr.replace('"strictScope": "ui1e",', '"strictScope": "w2",')
write("tools/package_release.py", pr)

print("=== 8. Regenerating Documentation and Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("\n=== Phase W2 Pre-flight Update Complete! ===")