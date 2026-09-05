#!/usr/bin/env python3
"""check:contracts — validate canonical GEL contracts and generated projections."""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
PY_ORACLE = ROOT / "python-oracle" / "tutorial_down4_resilient_v4_9_summary_blank_fidelity_no_email.py"
RUST_SRC = ROOT / "gel-core" / "src"

FILES = {
    "fields": "gel_tutorial_fields.json",
    "types": "tutorial_types.json",
    "app": "tutorial_form_applicability.json",
    "anomalies": "known_source_anomalies.json",
    "evidence": "evidence_baseline.json",
    "semantics": "tutorial_form_semantics.json",
    "reconciliation": "reconciliation_authority.json",
    "round_trip": "offline_post_round_trip.json",
    "archive_schema": "archive_schema_v2.json",
    "archive_repository": "archive_repository.json",
    "gel_session": "gel_read_only_session.json",
    "n2_pw": "n2_playwright_zero_write_evidence.json",
    "n2a": "n2a_semantic_post_authority.json",
    "new_form": "new_tutorial_form.json",
    "n2c": "new_tutorial_prepopulation.json",
    "ui1": "ui1_writer.json",
    "ui1_layout": "ui1_layout_hybrid.json",
    "ui1c": "ui1c_semantic_forms.json",
    "ui1c_aims": "ui1c_aims_assistance.json",
    "ui1d_harper": "ui1d_harper.json",
    "release_identity": "release_identity.json",
    "verification": "verification_semantics.json",
    "dependency_lock_policy": "dependency_lock_policy.json",
}

class ContractError(Exception):
    pass


def load(name: str) -> dict[str, Any]:
    path = CONTRACTS / FILES[name]
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContractError(f"cannot parse {path.relative_to(ROOT)}: {exc}") from exc


def require(cond: bool, message: str) -> None:
    if not cond:
        raise ContractError(message)


def unique(values: list[str], label: str) -> None:
    dupes = sorted({v for v in values if values.count(v) > 1})
    require(not dupes, f"duplicate {label}: {dupes}")


def literal_assignment(module: ast.Module, name: str):
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ContractError(f"Python oracle missing literal assignment {name}")


def check_python_oracle(types: dict[str, Any], fields: dict[str, Any]) -> None:
    require(PY_ORACLE.exists(), f"missing Python oracle {PY_ORACLE.relative_to(ROOT)}")
    module = ast.parse(PY_ORACLE.read_text(encoding="utf-8"), filename=str(PY_ORACLE))
    oracle_types = literal_assignment(module, "TTYPE_MAP")
    expected_types = {item["ttype"]: item["display"] for item in types["types"]}
    require(oracle_types == expected_types, f"Python TTYPE_MAP {oracle_types!r} != contract {expected_types!r}")

    summary_map = literal_assignment(module, "SUMMARY_ROW_MAP")
    observed_rows = set(fields["summary_rows_in_observed_order"])
    missing = sorted(set(summary_map.values()) - observed_rows)
    require(not missing, f"Python SUMMARY_ROW_MAP uses labels absent from canonical summary row contract: {missing}")


def check_rust_opaque_boundary() -> None:
    opaque = re.compile(r'(?:(?:dropdown|text)-\d+|trecs-79|(?:sl|sr|sw|ss|sv|sg|sp)-89)')
    violations = []
    for path in sorted(RUST_SRC.rglob("*.rs")):
        if path.name == "gel_fields.rs":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if opaque.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}")
    require(not violations, "opaque GEL IDs escaped generated compatibility module:\n  " + "\n  ".join(violations))


def check_contracts(
    fields: dict[str, Any],
    types: dict[str, Any],
    app: dict[str, Any],
    anomalies: dict[str, Any],
    evidence: dict[str, Any],
    form_semantics: dict[str, Any],
    reconciliation: dict[str, Any],
    round_trip: dict[str, Any],
    archive_schema: dict[str, Any],
    archive_repository: dict[str, Any],
    gel_session: dict[str, Any],
    n2_pw: dict[str, Any],
    n2a: dict[str, Any],
    new_form: dict[str, Any],
    n2c: dict[str, Any],
    ui1: dict[str, Any],
    ui1_layout: dict[str, Any],
    ui1c: dict[str, Any],
    ui1c_aims: dict[str, Any],
    ui1d_harper: dict[str, Any],
    release_identity: dict[str, Any],
    verification: dict[str, Any],
    dependency_lock_policy: dict[str, Any],
) -> None:
    contract_versions = {
        "gel_tutorial_fields": 4,
        "tutorial_types": 1,
        "tutorial_form_applicability": 2,
        "known_source_anomalies": 1,
        "evidence_baseline": 2,
        "tutorial_form_semantics": 7,
        "reconciliation_authority": 1,
        "offline_post_round_trip": 2,
        "archive_schema_v2": 2,
        "archive_repository": 2,
        "gel_read_only_session": 2,
        "n2_playwright_zero_write_evidence": 8,
        "n2a_semantic_post_authority": 3,
        "new_tutorial_form": 1,
        "new_tutorial_prepopulation": 2,
        "ui1_writer": 14,
        "ui1_layout_hybrid": 3,
        "ui1c_semantic_forms": 4,
        "ui1c_aims_assistance": 1,
        "ui1d_harper": 2,
        "release_identity": 6,
        "verification_semantics": 1,
        "dependency_lock_policy": 1,
    }
    for obj, expected in [
        (fields, "gel_tutorial_fields"),
        (types, "tutorial_types"),
        (app, "tutorial_form_applicability"),
        (anomalies, "known_source_anomalies"),
        (evidence, "evidence_baseline"),
        (form_semantics, "tutorial_form_semantics"),
        (reconciliation, "reconciliation_authority"),
        (round_trip, "offline_post_round_trip"),
        (archive_schema, "archive_schema_v2"),
        (archive_repository, "archive_repository"),
        (gel_session, "gel_read_only_session"),
        (n2_pw, "n2_playwright_zero_write_evidence"),
        (n2a, "n2a_semantic_post_authority"),
        (new_form, "new_tutorial_form"),
        (n2c, "new_tutorial_prepopulation"),
        (ui1, "ui1_writer"),
        (ui1_layout, "ui1_layout_hybrid"),
        (ui1c, "ui1c_semantic_forms"),
        (ui1c_aims, "ui1c_aims_assistance"),
        (ui1d_harper, "ui1d_harper"),
        (release_identity, "release_identity"),
        (verification, "verification_semantics"),
        (dependency_lock_policy, "dependency_lock_policy"),
    ]:
        require(obj.get("contract_id") == expected, f"contract_id must be {expected!r}")
        require(
            obj.get("contract_version") == contract_versions[expected],
            f"{expected} contract_version must be {contract_versions[expected]}",
        )

    require(ui1.get("status") in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 active contract status drifted")
    require(ui1["architecture"]["react_role"] == "presentation_only", "UI1 React role must remain presentation-only")
    require(ui1["architecture"]["submission"] == "production submission command ui1_submit_draft delegating to live_submission_transport", "UI1 submission authority drifted for W2")
    require(ui1["architecture"]["draft_persistence"].startswith("none"), "UI1 tutorial drafts must remain ephemeral")
    expected_ui1_commands = {
        "ui1_session_status", "ui1_login", "ui1_logout", "ui1_archive_status",
        "ui1_sync_archive",
        "ui1_list_classes", "ui1_list_students", "ui1_list_tutorials",
        "ui1_open_new_draft", "ui1_open_revision_draft", "ui1_get_draft",
        "ui1_apply_draft_edit", "ui1_discard_draft",
        "ui1_submit_draft",
        "ui1_harper_check", "ui1_harper_dictionary_list", "ui1_harper_dictionary_add", "ui1_harper_dictionary_remove",
        "ui1_search_live_students", "ui1_student_in_archive",
    }
    require(set(ui1["initial_command_allowlist"]) == expected_ui1_commands, "UI1 initial command allowlist drifted")
    require(ui1["harper_future_state"]["persistent_dictionary"] is True, "UI1 must retain governed persistent Harper dictionary plan")
    require(ui1["harper_future_state"]["persistent_tutorial_drafts"] is False, "UI1 must not introduce persistent tutorial drafts")
    require(ui1d_harper.get("status") == "active_ui1d_pending_strict_acceptance", "UI1d Harper contract status drifted")
    require(ui1d_harper["engine"]["version"] == "2.8.0" and ui1d_harper["engine"]["dialect"] == "British", "UI1d Harper engine identity drifted")
    require(ui1d_harper["state"]["writer"] == "harper_dictionary_repository", "UI1d dictionary writer drifted")
    require(ui1d_harper["state"]["tutorial_authority"] is False, "UI1d dictionary must not be tutorial authority")
    require(set(ui1d_harper["tauri_commands"]) == {"ui1_harper_check", "ui1_harper_dictionary_list", "ui1_harper_dictionary_add", "ui1_harper_dictionary_remove"}, "UI1d Tauri command contract drifted")
    require(ui1d_harper["dictionary"]["schema_version"] == 1, "UI1d dictionary schema must be v1")
    require(ui1d_harper["dictionary"]["future_schema"].startswith("fail closed"), "UI1d future dictionary schemas must fail closed")
    require(ui1_layout.get("status") == "complete_strictly_accepted", "UI1 hybrid layout must remain strictly accepted")
    require(ui1_layout.get("layout_id") == "UI1-LAYOUT-AD-HYBRID", "selected UI1 layout must be A+D hybrid")
    require(ui1_layout["student_read_model"]["visible_columns"] == ["Student", "Course", "Attendance", "Last tutorial"], "hybrid student visible projection drifted")
    require("school_name" in ui1_layout["student_read_model"]["forbidden_visible_fields"], "School must remain forbidden in normal UI")
    require(ui1_layout["modes"]["browse"]["left"]["width"] == "34%" and ui1_layout["modes"]["browse"]["right"]["width"] == "66%", "hybrid browse proportions drifted")
    require(ui1_layout["modes"]["write"]["left"]["collapsible"] is True, "hybrid write context must be collapsible")
    require(ui1["layout"]["selected"] == ui1_layout["layout_id"], "UI1 master contract/layout contract mismatch")
    require(ui1c.get("status") == "active_ui1c5_pending_strict_acceptance", "UI1c0 semantic contract must be active pending strict acceptance")
    require(ui1c["prerequisite"]["accepted_result"] == "PASS=23 SKIP=0 FAIL=0", "UI1c0 prerequisite acceptance record drifted")
    require(ui1c["ownership"]["semantic_writer"] == "rust_semantic_form", "UI1c semantic writer drifted")
    require(ui1c["ownership"]["react_role"] == "presentation_only", "UI1c React authority drifted")
    require(ui1c["initial_course_type"]["semantic_enum"] == ["HSP", "G21", "G15"], "Initial course-type contract drifted")
    require(ui1c["option_domains"]["exam"]["rendered_options"] is False, "UI1c exam controls must remain hidden-preserved")
    require(ui1c["level_regression"]["applies_to"] == "New only", "UI1c level regression must be New-only")
    require("Revision against later tutorials" in ui1c["level_regression"]["forbidden_comparisons"], "UI1c must not regression-check Revision against later tutorials")
    require(ui1c.get("ui1c5_integrated_acceptance", {}).get("status") == "implemented_pending_strict_acceptance", "UI1c5 integrated acceptance contract missing")
    require(ui1c.get("ui1c5_integrated_acceptance", {}).get("release_scope") == "ui1c5", "UI1c5 release scope drifted")
    require(ui1c_aims.get("status") == "absent_not_curated" and ui1c_aims.get("available") is False and ui1c_aims.get("items") == [], "Aims assistance must remain explicitly absent until curated")
    require(form_semantics.get("ui1c0_semantic_editor", {}).get("contract_ref") == "ui1c_semantic_forms", "tutorial_form_semantics must reference UI1c0 authority")
    require(n2c.get("status") == "active", "N2c prepopulation contract must be active")
    require(n2c["source_authority"]["prepopulation_source"] == "latest_tutorial_when_present", "N2c latest-source authority drifted")
    require(n2c["global_rules"]["source_timestamp"] == "absent for New", "N2c must preserve New datetime absence")
    require("No cross-dimension fallback" in n2c["level_projection"]["forbidden"], "N2c must forbid cross-dimension provenance")
    require(new_form.get("status") == "active", "N2b New-form contract must be active")
    require(new_form.get("network_write_authority") is False, "N2b must grant no network-write authority")
    require(new_form["acquisition"]["method"] == "GET", "N2b New-form acquisition must be GET")
    require(new_form["acquisition"]["path_template"] == "/study/tutorials/add/{student_uid}/0/{ttype_raw}", "N2b New-form route must use fixed zero locator")
    require(new_form["acquisition"]["generic_request_api"] is False, "N2b must not introduce generic request transport")
    require(new_form["form_contract"]["forbidden_fields"] == ["datetime"], "N2b New form must forbid datetime")
    require(new_form["form_contract"]["overrides"]["tid"]["control_kind"] == "hidden", "N2b New tid must be hidden")
    require(new_form["teacher_authority"]["public_mutation"] is False, "N2b New teacher must be immutable")
    require(release_identity.get("status") == "active", "release identity contract must be active")
    require(release_identity["current_state_projection"]["classification"] == "projection", "current-state must remain projection state")
    require(release_identity["current_state_projection"]["must_not_be_runtime_authority"] is True, "current-state must not be runtime authority")
    require(release_identity["dependency_identity"]["single_rust_workspace_lock"] is True, "release identity must use one Rust workspace lock")
    require(release_identity["dependency_identity"]["release_commands_use_locked"] is True, "release Rust commands must use --locked")
    require(release_identity["dependency_identity"]["frontend_install_command"] == ["npm", "ci", "--no-audit", "--no-fund"], "release frontend install must use npm ci")
    require(release_identity["dependency_identity"].get("policy_contract") == "contracts/dependency_lock_policy.json", "release identity must bind dependency lock policy")
    exc = release_identity["dependency_identity"].get("portable_tool_unavailable_exception", {})
    require(exc == {"result":"SKIP","strict_result":"FAIL","automatic_detection_only":True,"manual_override_allowed":False,"promotion_ceiling":"FAST_VERIFIED"}, "release identity lock exception drifted")
    require(dependency_lock_policy.get("authority") and dependency_lock_policy["tool_unavailable_exception"]["id"] == "LOCK_GENERATOR_UNAVAILABLE", "dependency lock exception contract drifted")
    lock_exc = dependency_lock_policy["tool_unavailable_exception"]
    require(lock_exc["portable_result"] == "SKIP" and lock_exc["strict_result"] == "FAIL", "lock exception portable/strict semantics drifted")
    require(lock_exc["manual_override_allowed"] is False and lock_exc["network_unavailable_is_not_tool_unavailable"] is True and lock_exc["command_failure_is_not_tool_unavailable"] is True, "lock exception must be automatic executable-unavailability only")
    require(lock_exc["promotion_ceiling"] == "FAST_VERIFIED", "lock exception promotion ceiling drifted")
    require(release_identity["strict_acceptance"]["required_scope"] == "w2", "W2 must be current strict acceptance scope")
    require(release_identity["strict_acceptance"]["package_after_acceptance_may_not_rebuild"] is True, "packaging after acceptance must not rebuild")
    agent_gov = release_identity.get("agent_governance_identity", {})
    require(agent_gov.get("classification") == "decision" and agent_gov.get("runtime_authority") is False, "agent governance identity must remain non-runtime decision state")
    require(agent_gov.get("protocol") == "governance/agent-protocol/ai-governance-protocol.v1.1.json", "agent governance protocol release binding drifted")
    require(agent_gov.get("profile") == "governance/agent-protocol/profiles/gel-tutorial-writer.profile.json", "GEL agent governance profile release binding drifted")
    require(verification.get("automatic_promotion") is False, "verification evidence must not auto-promote")
    require(set(verification.get("evidence_classes", [])) == {"lint", "structural", "behavioral", "acceptance"}, "verification evidence taxonomy drifted")

    type_items = types.get("types", [])
    require(len(type_items) == 3, "tutorial_types must contain exactly Initial, Standard and Final")
    semantics = [x["semantic"] for x in type_items]
    ttypes = [x["ttype"] for x in type_items]
    displays = [x["display"] for x in type_items]
    unique(semantics, "tutorial type semantic")
    unique(ttypes, "ttype")
    require(set(semantics) == {"initial", "standard", "final"}, f"unexpected tutorial types: {semantics}")
    require(set(ttypes) == {"0", "1", "2"}, f"unexpected ttype codes: {ttypes}")
    require(set(displays) == {"Initial", "Standard", "Final"}, f"unexpected display types: {displays}")

    field_items = fields.get("fields", [])
    require(field_items, "gel_tutorial_fields.fields must not be empty")
    unique([x["semantic_name"] for x in field_items], "semantic field")
    unique([x["rust_const"] for x in field_items], "Rust constant")
    unique([x["gel_name"] for x in field_items], "GEL field")
    allowed_types = set(semantics)
    placeholders = set(fields.get("placeholders", {}))
    value_domains = fields.get("value_domains", {})
    require(set(value_domains) == {"skill_level", "overall_level"}, "C1 value domains must define skill_level and overall_level")
    for domain_name, values in value_domains.items():
        require(isinstance(values, list) and values, f"value domain {domain_name} must be a non-empty list")
        unique(values, f"{domain_name} value")

    edit_kinds = {"hidden", "text", "checkbox", "select", "textarea", "radio_group", "contenteditable_plus_hidden"}
    validation_rules = {"none", "positive_i64", "positive_i64_option", "tutorial_type_code", "gel_date", "checkbox_boolean"}
    for field in field_items:
        applies = set(field.get("applies_to", []))
        require(applies, f"{field['semantic_name']} has empty applies_to")
        require(applies <= allowed_types, f"{field['semantic_name']} has invalid applies_to {sorted(applies - allowed_types)}")
        if field.get("placeholder_ref"):
            require(field["placeholder_ref"] in placeholders, f"{field['semantic_name']} references unknown placeholder {field['placeholder_ref']}")
        if field.get("rust_max_const"):
            require(isinstance(field.get("max_chars"), int) and field["max_chars"] > 0, f"{field['semantic_name']} max_chars invalid")
        if field.get("value_domain_ref"):
            require(field["value_domain_ref"] in value_domains, f"{field['semantic_name']} references unknown value domain {field['value_domain_ref']}")
        roles = set(field.get("source_roles", []))
        is_edit_control = bool({"edit_form", "edit_form_contenteditable"} & roles)
        if is_edit_control:
            require(field.get("control_kind") in edit_kinds, f"{field['semantic_name']} has unsupported C1 edit control kind {field.get('control_kind')!r}")
            require(isinstance(field.get("allow_unset"), bool), f"{field['semantic_name']} must declare boolean allow_unset for C1")
            require(field.get("validation_rule") in validation_rules, f"{field['semantic_name']} has invalid C1 validation_rule {field.get('validation_rule')!r}")

    field_by_name = {x["semantic_name"]: x for x in field_items}
    for name, field in field_by_name.items():
        roles = set(field.get("source_roles", []))
        if name == "source_timestamp":
            require("new_form" not in roles, "datetime/source_timestamp must never be a New-form source field")
        elif "edit_form" in roles or "edit_form_contenteditable" in roles:
            require("new_form" in roles, f"governed editable form field {name} must declare New-form source role in N2b")
    app_fields = app["semantic_fields"]
    listed = set(app_fields["common"])
    for t in semantics:
        listed.update(app_fields[t])
    for excluded in app.get("excluded_infrastructure_fields", []):
        require(excluded in field_by_name, f"excluded infrastructure field {excluded} is unknown")
    unknown = sorted(listed - set(field_by_name))
    require(not unknown, f"applicability references unknown semantic fields: {unknown}")

    common = set(app_fields["common"])
    for t in semantics:
        expected = common | set(app_fields[t])
        actual = {name for name, field in field_by_name.items() if t in field["applies_to"] and name not in app.get("excluded_infrastructure_fields", [])}
        require(expected == actual, f"applicability drift for {t}: expected-only={sorted(expected-actual)}, field-contract-only={sorted(actual-expected)}")

    require(field_by_name["reading"]["applies_to"] == ["standard", "final"], "reading must apply to standard and final only")
    require("initial_reading" not in field_by_name, "there must be no initial_reading GEL field")
    require(field_by_name["additional_comments"]["applies_to"] == ["final"], "additional_comments must be Final-only")
    require(field_by_name["aims"]["applies_to"] == ["standard"], "aims must be Standard-only")
    require(field_by_name["teacher_comments"].get("max_chars") == 970, "teacher_comments GEL limit must be 970")
    require(field_by_name["additional_comments"].get("max_chars") == 600, "additional_comments GEL limit must be 600")
    require(field_by_name["student_uid"]["allow_unset"] is False, "student_uid must fail closed when unset")
    require(field_by_name["source_timestamp"]["allow_unset"] is False, "source_timestamp must fail closed when unset")
    require(field_by_name["tutorial_type"]["allow_unset"] is False, "tutorial_type must fail closed when unset")
    require(field_by_name["tutorial_date"]["validation_rule"] == "gel_date", "tutorial_date must use strict GEL date validation")
    require(field_by_name["reading"]["value_domain_ref"] == "skill_level", "Reading must use the canonical CEFR skill value domain")
    expected_level_fields = {
        "initial_speaking": (264, "speaking", "initial"),
        "initial_use_of_english": (265, "use_of_english", "initial"),
        "initial_writing": (266, "writing", "initial"),
        "initial_listening": (267, "listening", "initial"),
        "speaking": (233, "speaking", "current"),
        "use_of_english": (234, "use_of_english", "current"),
        "writing": (235, "writing", "current"),
        "listening": (236, "listening", "current"),
        "reading": (476, "reading", "current"),
    }
    for name, (field_id, dimension, phase) in expected_level_fields.items():
        item = field_by_name[name]
        require(item.get("gel_field_id") == field_id, f"{name} canonical GEL field ID drifted")
        require(item.get("semantic_level_role") == {"dimension": dimension, "phase": phase}, f"{name} semantic level role drifted")
        require(item.get("provenance_rule") == "field_identity_only_no_cross_field_value_inference", f"{name} must forbid equality-based cross-field provenance")
    require(field_by_name["source_timestamp"].get("new_post_rule") == "omit_key_entirely", "New datetime must be absent, not blank/zero")
    require(field_by_name["source_timestamp"].get("revision_post_rule") == "require_exact_source_timestamp", "Revision datetime rule drifted")
    require(field_by_name["teacher_id"].get("new_form_control_kind") == "hidden", "New teacher control must be recorded as hidden")
    require(field_by_name["teacher_id"].get("revision_form_control_kind") == "select", "Revision teacher control must be recorded as select")
    for name in ["assessment_listening", "assessment_reading", "assessment_writing", "assessment_speaking", "assessment_vocabulary", "assessment_grammar", "assessment_pronunciation"]:
        require(set(field_by_name[name].get("values", {})) == {"1", "2", "3"}, f"{name} radio domain must be exactly 1/2/3")
        require(field_by_name[name]["allow_unset"] is True, f"{name} must permit an intentionally blank radio group")

    anomaly_items = anomalies.get("anomalies", [])
    unique([x["id"] for x in anomaly_items], "anomaly ID")
    active = {x["id"]: x for x in anomaly_items if x.get("status") == "active"}
    for required in ["ANOM-ABSENT-001", "ANOM-COLLISION-001", "ANOM-COLLISION-002", "ANOM-AIMS-001", "ANOM-BLANK-001", "ANOM-LEVEL-001"]:
        require(required in active, f"missing active anomaly {required}")
    require(active["ANOM-ABSENT-001"]["authority_rule"].lower().startswith("for historical revision, summary/archive absent is authoritative"), "absent authority rule drifted")

    observed = {x["id"]: x for x in evidence.get("observations", [])}
    require(observed["EVID-FIXTURE-270"]["fixture_count"] == 14, "fixture evidence must record 14 fixtures")
    require((observed["EVID-FIXTURE-270"]["field_count"], observed["EVID-FIXTURE-270"]["ok"], observed["EVID-FIXTURE-270"]["mismatch"], observed["EVID-FIXTURE-270"]["unavailable"]) == (270,264,6,0), "observed pre-Final-Reading fixture evidence drifted")
    require(observed["EVID-FINAL-READING"]["fixture_count"] == 5, "Final Reading evidence must cover five Final fixtures")
    require(observed["EVID-COLLISIONS"]["collision_groups"] == 14 and observed["EVID-COLLISIONS"]["ambiguous_api_rows"] == 29, "collision evidence drifted")
    observed_275 = observed["EVID-FIXTURE-275"]
    require(observed_275["status"] == "observed", "275-field fixture baseline must be recorded as observed")
    require(
        (
            observed_275["fixture_count"],
            observed_275["field_count"],
            observed_275["ok"],
            observed_275["mismatch"],
            observed_275["unavailable"],
        ) == (14, 275, 269, 6, 0),
        "observed 275-field strict baseline drifted",
    )
    require(observed_275.get("release_gate_result") == "PASS", "C1 strict release gate must be recorded as PASS")
    next_base = evidence["expected_next_strict_fixture_baseline"]
    require(next_base["status"] == "confirmed_observed", "275-field strict baseline must remain confirmed observed")
    require(
        (
            next_base["fixture_count"],
            next_base["field_count"],
            next_base["expected_ok"],
            next_base["expected_mismatch"],
            next_base["expected_unavailable"],
        ) == (14, 275, 269, 6, 0),
        "expected 275-field baseline drifted",
    )

    origins = form_semantics.get("draft_origins", {})
    require(set(origins) == {"revision", "new"}, "semantic contract must define exactly revision and new draft origins")
    require(origins["revision"].get("required_source_identity") is True, "Revision origin must require source identity")
    require(origins["new"].get("prepopulation_source_optional") is True, "New origin must permit optional prepopulation source")
    require(
        origins["new"].get("post_source_timestamp_rule") == "omit_datetime_entirely",
        "New draft must omit datetime entirely",
    )
    require(
        origins["revision"].get("post_timestamp_rule") == "require_exact_source_timestamp",
        "Revision must require exact source timestamp",
    )
    require(
        origins["new"].get("teacher_authority") == "opaque ValidatedNewFormTeacher derived only from the validated N2b hidden tid source control",
        "New teacher authority must come from the validated New form",
    )
    require(
        origins["revision"].get("teacher_authority") == "historical_revision_teacher",
        "Revision teacher authority must remain historical",
    )
    truth = form_semantics.get("editable_source_of_truth", {})
    require(truth.get("overall_level") == "semantic_cefr_level_only", "overall level must have one semantic writable representation")
    require(truth.get("aims") == "plain_text_only", "Aims must have one plain-text editable representation")
    require(truth.get("absent_revision") == "summary_archive_authoritative", "revision absent authority drifted")
    provenance = form_semantics.get("provenance_only", {})
    require("overall_level_source_raw" in provenance, "overall raw value must be provenance-only")
    require("aims_source_html" in provenance, "Aims source HTML must be provenance-only")
    require(form_semantics["post_serialization"].get("aims_text_encoding") == "html_escape_then_newlines_to_br", "Aims POST escaping contract drifted")
    require(form_semantics["post_serialization"].get("provenance_must_not_drive_payload") is True, "POST payload must not read provenance as semantic fallback")
    require(form_semantics["post_serialization"].get("semantic_validation_required_before_mapping") is True, "POST mapper must validate semantic invariants")
    revision_authority = form_semantics.get("revision_state_authority", {})
    require(
        revision_authority.get("contract_ref") == "reconciliation_authority"
        and revision_authority.get("requires_permitted_historical_state_authority") is True,
        "semantic Revision construction must reference the C3 reconciliation authority contract",
    )

    require(
        reconciliation.get("identity_rule", "").startswith("tutorial_id from the tutorial-list API is canonical identity"),
        "C3 canonical identity rule drifted",
    )
    classes = reconciliation.get("collision_classes", {})
    require(
        set(classes) == {"identical_state", "divergent_state", "incomplete_evidence"},
        "C3 collision class taxonomy drifted",
    )
    require(
        classes["divergent_state"].get("revision_rule", "").startswith("Revision by tutorial_id is blocked"),
        "divergent collision must block revision-by-ID",
    )
    require(
        classes["identical_state"].get("per_id_association") == "ambiguous",
        "identical collision per-ID source association must remain ambiguous",
    )
    require(
        reconciliation.get("governed_summary_state", {}).get("equivalence_fields")
        == ["ttype_raw", "fields"],
        "governed collision state equivalence must use ttype_raw + fields",
    )
    statuses = set(reconciliation.get("revision_authority_statuses", []))
    require(
        statuses
        == {
            "proven_per_tutorial",
            "shared_identical_collision",
            "ambiguous_divergent_collision",
            "incomplete_collision_evidence",
            "ambiguous_collision_unknown",
            "unmatched_source_state",
        },
        "C3 revision authority status taxonomy drifted",
    )
    require(
        reconciliation.get("revision_allowed_statuses")
        == ["proven_per_tutorial", "shared_identical_collision"],
        "only proven and shared-identical authority may permit revision-by-ID",
    )

    require(
        gel_session.get("origins", {}).get("api_base") == "https://api2.guidedelearning.net"
        and gel_session.get("origins", {}).get("learn2_base") == "https://learn2.guidedelearning.net",
        "N1 canonical GEL origins drifted",
    )
    auth = gel_session.get("authentication", {})
    require(auth.get("login_post_count") == 2, "N1 login handshake must contain exactly two POSTs")
    require(auth.get("credential_retention") == "none", "N1 credentials must not be retained")
    require(auth.get("ajax_success_status") == "authNotNeeded", "N1 login success marker drifted")
    read_surface = gel_session.get("read_surface", [])
    require(len(read_surface) == 9, "N1/N2b read surface must contain exactly nine fixed operations (eight GET + one POST for search)")
    get_operations = [item for item in read_surface if item.get("method") == "GET"]
    post_operations = [item for item in read_surface if item.get("method") == "POST"]
    require(len(get_operations) == 8, "N1 exposed read surface must have eight GET operations")
    require(len(post_operations) == 1 and post_operations[0].get("id") == "school_wide_student_search", "N1 must have exactly one POST operation for school-wide student search")
    require(
        {item.get("id") for item in get_operations}
        == {"classes", "class_students", "student_profile", "tutorial_list", "tutorial_summary", "tutorial_print", "new_tutorial_form", "tutorial_edit"},
        "N1/N2b GET read surface operation set drifted",
    )
    network = gel_session.get("network_authority", {})
    require(network.get("generic_request_api") is False, "N1 must not expose a generic request API")
    require(network.get("gel_tutorial_write_authority") is False, "N1 must not acquire GEL tutorial write authority")
    require(
        set(network.get("forbidden_http_methods_after_authentication", [])) == {"POST", "PUT", "PATCH", "DELETE"},
        "N1 authenticated method prohibition drifted",
    )
    require(
        set(gel_session.get("privacy", {}).get("student_fields_removed_immediately", []))
        == {"email", "mail", "email_address", "emailaddress"},
        "N1 student privacy field minimization drifted",
    )
    live = gel_session.get("live_acceptance", {})
    require(live.get("release_gate_network_access") is False, "N1 release gate must remain offline")
    require(live.get("manual_probe_binary") == "check_gel_read_only_live", "N1 manual live probe name drifted")
    require(n2_pw.get("phase") == "N2-PW1", "PW1 phase identifier drifted")
    n2_network = n2_pw.get("network_state_machine", {})
    require(n2_network.get("firewall_installed_before_first_navigation") is True, "PW1 firewall must predate navigation")
    require(n2_network.get("service_workers_blocked") is True, "PW1 must block service workers")
    require(n2_network.get("authentication", {}).get("allowed_mutation", {}).get("body_may_be_inspected") is False, "PW1 must not inspect login body")
    require(n2_network.get("evidence", {}).get("expected_tutorial_mutation", {}).get("network_action") == "always_abort", "PW1 tutorial probes must always abort")
    require(n2_network.get("evidence", {}).get("forwarded_tutorial_mutations") == 0, "PW1 must forward zero tutorial mutations")
    n2_privacy = n2_pw.get("credential_privacy", {})
    require(n2_privacy.get("harness_credential_authority") == "none", "PW1 harness must have no credential authority")
    require(n2_privacy.get("raw_tutorial_post_body_persisted") is False, "PW1 must not persist raw tutorial POST bodies")
    require(n2_privacy.get("student_identity_persisted") is False, "PW1 must not persist student identity")
    n2_teacher = n2_pw.get("teacher_semantics", {})
    require(n2_teacher.get("server_reassignment_acceptance") == "unresolved", "PW1 must keep server teacher reassignment acceptance unresolved")
    require(n2_teacher.get("server_reassignment_authorization") == "unresolved", "PW1 must keep server teacher reassignment authorization unresolved")
    n2_pre = n2_pw.get("prepopulation", {})
    require(n2_pre.get("source") == "latest_tutorial" and n2_pre.get("source_status") == "established_before_PW1", "PW1 must treat latest tutorial as the established New prepopulation source")
    require(n2_pre.get("persist_values") is False, "PW1 prepopulation evidence must persist relationships only")

    pw1_live = observed.get("EVID-N2-PW1-LIVE", {})
    require(pw1_live.get("new_form_types_inspected") == 3, "N2 PW1 live evidence must cover three New types")
    require(pw1_live.get("new_datetime_absent_all_types") is True, "N2 PW1 must confirm New datetime absence")
    require(pw1_live.get("forwarded_tutorial_mutations") == 0, "N2 PW1 must preserve zero tutorial writes")
    require(pw1_live.get("changed_tid_serialization") == "deferred_non_blocking", "changed-tid serialization must be a non-blocking residual")
    field_identity = observed.get("EVID-N2-FIELD-IDENTITY", {})
    require(field_identity.get("initial", {}).get("267") == "initial_listening", "N2 field identity must map 267 to Initial Listening")
    require(field_identity.get("current", {}).get("233") == "speaking", "N2 field identity must map 233 to current Speaking")

    require(n2_pw.get("residual_status", {}).get("n2_gate") is False, "teacher serialization residual must not block N2")
    require(n2_pw.get("prepopulation", {}).get("forbidden_inference", "").startswith("Cross-field provenance"), "PW1 must forbid cross-field equality inference")
    require(n2a.get("phase") == "N2a", "N2a contract phase drifted")
    require(n2a.get("network_write_authority") is True, "N2a network_write_authority must be true under W2")
    require(n2a.get("type_safety", {}).get("generic_option_datetime_forbidden") is True, "N2a must forbid generic optional datetime submission semantics")
    require(n2a.get("origin_authority", {}).get("new", {}).get("datetime_post") == "absent_key", "N2a New datetime contract drifted")
    require(n2a.get("origin_authority", {}).get("revision", {}).get("datetime_post") == "exact source tutorial_ts", "N2a Revision datetime contract drifted")
    require(n2a.get("resolved_preconditions", {}).get("teacher_serialization_residual", "").startswith("Changed-teacher"), "N2a must record changed-teacher evidence as deferred")

    strict_collision = reconciliation.get("strict_private_fixtures", {})
    require(strict_collision.get("required_fixture_count") == 2, "C3 strict collision fixture count must be 2")
    require(
        set(strict_collision.get("required_labels", []))
        == {"duplicate_identical_state", "duplicate_different_state"},
        "C3 strict collision fixture labels drifted",
    )
    require(
        observed["EVID-COLLISIONS"]["identical_state_groups"] == 13
        and observed["EVID-COLLISIONS"]["divergent_state_groups"] == 1,
        "C3 collision evidence must retain 13 identical-state and 1 divergent-state groups",
    )
    c3_strict = observed.get("EVID-C3-STRICT", {})
    require(c3_strict.get("status") == "observed", "C3 strict acceptance evidence must be recorded")
    require(
        (
            c3_strict.get("private_collision_fixtures"),
            c3_strict.get("release_gate_pass"),
            c3_strict.get("release_gate_skip"),
            c3_strict.get("release_gate_fail"),
            c3_strict.get("release_gate_result"),
        )
        == (2, 8, 0, 0, "PASS"),
        "C3 strict acceptance evidence drifted",
    )

    require(
        round_trip.get("pipeline")
        == [
            "archive fixture -> ArchivedTutorial",
            "raw edit HTML -> EditFormState",
            "EditFormState -> ValidatedEditFormState",
            "archive + ValidatedEditFormState -> Revision TutorialFormState",
            "TutorialFormState -> TutorialPostPayload",
        ],
        "C4 offline POST round-trip pipeline drifted",
    )
    suite = round_trip.get("fixture_suite", {})
    require(
        (
            suite.get("required_fixture_count"),
            suite.get("required_final_fixture_count"),
            suite.get("required_absent_source_discrepancy_count"),
        )
        == (14, 5, 6),
        "C4 fixture evidence counts drifted",
    )
    require(
        round_trip.get("common_rules", {}).get("absent")
        == "summary/archive authority; true emits absent=on and false omits the key",
        "C4 absent POST authority rule drifted",
    )
    transformations = round_trip.get("transformations", {})
    require(
        transformations.get("final_reading", "").startswith("must always be present"),
        "C4 Final Reading POST invariant drifted",
    )
    mutation = round_trip.get("mutation_isolation", {})
    mapping = mutation.get("semantic_to_payload_field", {})
    expected_mutable_fields = {
        "absent",
        "overall_level",
        "tutorial_date",
        "teacher_comments",
        "initial_speaking",
        "initial_use_of_english",
        "initial_writing",
        "initial_listening",
        "speaking",
        "use_of_english",
        "writing",
        "listening",
        "reading",
        "assessment_listening",
        "assessment_reading",
        "assessment_writing",
        "assessment_speaking",
        "assessment_vocabulary",
        "assessment_grammar",
        "assessment_pronunciation",
        "aims",
        "additional_comments",
        "exam_intent",
        "exam_type",
        "exam_when",
    }
    require(
        set(mapping.values()) == expected_mutable_fields,
        "C4 mutation-isolation payload field set drifted",
    )
    require(
        set(mutation.get("provenance_only_paths", []))
        == {
            "provenance.overall_level_source_raw",
            "provenance.aims_source_html",
            "provenance.absent.edit_form_value",
            "provenance.absent.discrepancy",
        },
        "C4 provenance-only mutation set drifted",
    )
    require(
        set(mutation.get("revision_non_editable_paths", []))
        == {"origin", "student_uid", "tutorial_type", "teacher.teacher_id"},
        "C4 revision non-editable path set drifted",
    )
    field_names = {field["semantic_name"] for field in field_items}
    require(
        expected_mutable_fields <= field_names,
        "C4 mutation isolation references unknown GEL semantic fields",
    )
    require(
        "no HTTP client" in round_trip.get("network_rule", ""),
        "C4 must remain explicitly offline",
    )
    c4_strict = observed.get("EVID-C4-STRICT", {})
    require(c4_strict.get("status") == "observed", "C4 strict acceptance evidence must be recorded")
    require(
        (
            c4_strict.get("private_post_round_trip_fixtures"),
            c4_strict.get("final_reading_payloads"),
            c4_strict.get("archive_authoritative_absent_discrepancies"),
            c4_strict.get("release_gate_pass"),
            c4_strict.get("release_gate_skip"),
            c4_strict.get("release_gate_fail"),
            c4_strict.get("release_gate_result"),
        )
        == (14, 5, 6, 9, 0, 0, "PASS"),
        "C4 strict acceptance evidence drifted",
    )

    # D1 archive schema v2: executable storage authority and migration invariants.
    require(archive_schema.get("schema_version") == 2, "D1 archive schema version must be 2")
    require(archive_schema.get("current_runtime_cutover") == "a2_rust_archiver_active_pending_strict_acceptance", "A2 archive-schema runtime cutover status drifted")
    require("RustArchiver" in archive_schema.get("authority_rule", "") and "ArchiveSyncRepository" in archive_schema.get("authority_rule", ""), "archive-schema authority must reflect A2 Rust canonical-writer cutover")
    require("Failed or rolled-back" in archive_schema.get("source_presence", {}).get("failed_sync_rule", "") and "still observed" in archive_schema.get("source_presence", {}).get("failed_sync_rule", ""), "archive-schema source-presence rule must distinguish failed runs from A2 partial auxiliary evidence")
    require(archive_schema.get("executable_schema") == "schema/archive_v2.sql", "D1 executable schema path drifted")
    schema_path = ROOT / archive_schema["executable_schema"]
    require(schema_path.exists(), "D1 executable archive schema SQL is missing")
    schema_sql = schema_path.read_text(encoding="utf-8")
    require("PRAGMA user_version = 2" in schema_sql, "D1 executable schema must set PRAGMA user_version=2")
    require("CREATE TABLE class_memberships" in schema_sql, "D1 schema must replace students.class_id with class_memberships")
    student_block = re.search(r"CREATE TABLE students \((?P<body>.*?)\n\);", schema_sql, re.S)
    require(student_block is not None and "class_id" not in student_block.group("body"), "D1 v2 students table must not contain class_id")
    require("raw_json" not in schema_sql, "D1 v2 executable schema must not persist raw_json")
    require("INSERT OR REPLACE" not in schema_sql.upper(), "D1 executable schema must not use INSERT OR REPLACE")
    require(archive_schema.get("raw_json_policy", {}).get("stored_in_v2") is False, "D1 raw_json minimization policy drifted")
    require(archive_schema.get("membership_model", {}).get("student_class_foreign_key_removed") is True, "D1 membership contract must remove students.class_id")
    assoc = archive_schema.get("identity_state_association", {})
    require(assoc.get("canonical_identity") == "tutorial_id", "D1 archive canonical tutorial identity drifted")
    require(assoc.get("revision_allowed_statuses") == ["proven_per_tutorial", "shared_identical_collision"], "D1 archive revision authority statuses drifted")
    require("source_state_id as NULL" in assoc.get("blocked_association_rule", ""), "D1 blocked association rule must prevent false state attribution")
    presence = archive_schema.get("source_presence", {})
    require(set(presence.get("required_columns", [])) == {"source_present", "first_seen", "last_seen"}, "D1 source-presence columns drifted")
    require(presence.get("run_tracking_table") == "archive_sync_runs", "D1 source-presence run tracking table drifted")
    require(presence.get("run_guard_column") == "presence_checked_run_id", "D1 source-presence run guard column drifted")
    require("status=complete" in presence.get("invalidation_guard", ""), "D1 invalidation guard must require completed sync")
    require("same student_uid/tutorial_ts" in assoc.get("key_consistency_rule", ""), "D1 association key-consistency rule drifted")
    upsert = archive_schema.get("upsert_policy", {})
    require(upsert.get("insert_or_replace_forbidden") is True, "D1 must forbid INSERT OR REPLACE")
    require("ON CONFLICT" in upsert.get("required_pattern", ""), "D1 safe UPSERT policy must require ON CONFLICT")
    acceptance = archive_schema.get("acceptance", {})
    require(acceptance.get("check") == "python -S tools/check_archive_schema.py", "D1 archive-schema acceptance must run under python -S")
    require(acceptance.get("live_oracle_runtime_import_required") is False, "D1 archive-schema checker must not require live oracle runtime import")
    require("AST-extracting" in acceptance.get("offline_dependency_rule", ""), "D1 offline UPSERT verification rule drifted")
    legacy = archive_schema.get("legacy_v1_migration", {})
    require(legacy.get("mode") == "source_to_separate_destination", "D1 migration must not mutate legacy source in place")
    require(legacy.get("collision_rule", "").startswith("Any legacy duplicate"), "D1 legacy collision migration rule drifted")
    d1_strict = observed.get("EVID-D1-STRICT", {})
    require(d1_strict.get("status") == "observed", "D1 strict acceptance evidence must be recorded")
    require(
        (
            d1_strict.get("archive_schema_v2"),
            d1_strict.get("release_gate_pass"),
            d1_strict.get("release_gate_skip"),
            d1_strict.get("release_gate_fail"),
            d1_strict.get("release_gate_result"),
        ) == ("PASS", 10, 0, 0, "PASS"),
        "D1 strict acceptance evidence drifted",
    )

    # D2/A2 Rust repository: public reads + crate-private writes behind RustArchiver.
    require(archive_repository.get("schema_ref") == "archive_schema_v2", "D2 repository schema reference drifted")
    require(archive_repository.get("schema_version") == 2, "D2 repository must target archive schema v2")
    public = archive_repository.get("public_read_surface", {})
    require(public.get("module") == "gel-core/src/archive_repository.rs", "D2 public repository module path drifted")
    require(public.get("connection_exposure") is False and public.get("write_methods_allowed") is False, "D2 public repository must expose no write capability")
    require("SQLITE_OPEN_READ_ONLY" in public.get("open_mode", "") and "query_only" in public.get("open_mode", ""), "D2 public repository must be SQLite read-only/query-only")
    writer = archive_repository.get("archive_sync_write_surface", {})
    require(writer.get("module") == "gel-core/src/archive_sync_repository.rs", "D2 sync repository module path drifted")
    require(writer.get("visibility") == "crate_private", "D2 sync write capability must remain crate-private")
    require(writer.get("runtime_status") == "production_canonical_A2", "A2 sync writer runtime status drifted")
    require(writer.get("public_reexport_forbidden") is True and writer.get("database_create_forbidden") is True, "D2 writer must not be publicly re-exported or create databases")
    fingerprint = archive_repository.get("source_state_fingerprint", {})
    require(fingerprint.get("algorithm") == "sha256", "D2 source-state fingerprint must use SHA-256")
    require(fingerprint.get("parity_authority") == "python-oracle/archive_schema_v2.py#legacy_state_fingerprint", "D2 fingerprint parity authority drifted")
    require(set(fingerprint.get("include_identity_fields", [])) == {"student_uid", "tutorial_ts"}, "D2 fingerprint identity fields drifted")
    require(set(fingerprint.get("excluded_provenance_fields", [])) == {"source_method", "summary_url", "print_url", "edit_url", "summary_match_method"}, "D2 fingerprint provenance exclusions drifted")
    ownership = archive_repository.get("ownership", {})
    require(ownership.get("production_canonical_writer_after_A2") == "rust_archive_sync_repository", "A2 must transfer canonical archive writer to Rust")
    require(ownership.get("production_orchestrator") == "gel-core/src/archiver.rs#RustArchiver", "A2 RustArchiver orchestration boundary drifted")
    require(ownership.get("python_v49_status_after_A2") == "historical_reference", "A2 Python oracle status drifted")
    require(ownership.get("a2_cutover") is True, "A2 cutover flag must be true")
    require("partial_auxiliary" in archive_repository.get("scope_invalidation", {}), "A2 partial-evidence invalidation contract missing")
    acceptance2 = archive_repository.get("acceptance", {})
    require(acceptance2.get("contract_check") == "python -S tools/check_archive_repository.py && python -S tools/check_a2_archiver.py", "A2 repository contract check must include cutover checker")
    require(acceptance2.get("release_gate_check_id") == "archive_repository", "D2 release check id drifted")


def check_rust_semantic_contract() -> None:
    semantic_path = RUST_SRC / "semantic.rs"
    post_path = RUST_SRC / "post_mapper.rs"
    semantic = semantic_path.read_text(encoding="utf-8")
    post = post_path.read_text(encoding="utf-8")

    match = re.search(r"pub struct TutorialFormState \{(?P<body>.*?)\n\}", semantic, re.S)
    require(match is not None, "Rust semantic model missing TutorialFormState")
    body = match.group("body")
    require("pub origin: DraftOrigin" in body, "TutorialFormState must use explicit DraftOrigin")
    require("source_identity" not in body, "TutorialFormState must not use Option source_identity origin semantics")
    require("overall_level_raw" not in body, "overall_level_raw must not remain an editable TutorialFormState field")
    require("pub aims: String" in body, "TutorialFormState Aims must be one editable plain-text String")
    require("pub overall_level: Option<CefrLevel>" in body, "TutorialFormState must retain semantic overall CEFR level")

    archive_match = re.search(r"pub struct ArchivedTutorial \{(?P<body>.*?)\n\}", semantic, re.S)
    require(archive_match is not None, "Rust semantic model missing ArchivedTutorial")
    require(
        "pub state_authority: HistoricalStateAuthority" in archive_match.group("body"),
        "ArchivedTutorial must carry explicit C3 historical state authority",
    )
    require(
        "archive.state_authority.permits_revision_by_id()" in semantic,
        "revision construction must fail closed through C3 historical state authority",
    )

    reconciliation_path = RUST_SRC / "reconciliation.rs"
    models_path = RUST_SRC / "models.rs"
    reconciliation_src = reconciliation_path.read_text(encoding="utf-8")
    models_src = models_path.read_text(encoding="utf-8")
    require(
        "summary: None" in reconciliation_src and "MatchMethod::CollisionGroup" in reconciliation_src,
        "collision reconciliation must keep candidate summary states group-owned",
    )
    require(
        "RevisionBlockReason::DivergentCollision" in models_src,
        "C3 model must explicitly block divergent collision revision",
    )

    require("validate_semantic_form_state(state)?;" in post, "POST mapper must validate semantic invariants before mapping")
    require("provisional_source_timestamp_for_post" not in semantic and "provisional_source_timestamp_for_post" not in post, "N2a must retire provisional New timestamp encoding")
    require("pub struct NewTutorialSubmission" in post and "pub struct RevisionTutorialSubmission" in post, "N2a must expose distinct New/Revision submission types")
    new_builder = re.search(r"pub fn build_new_tutorial_post_payload(?P<body>.*?)(?=pub fn build_revision_tutorial_post_payload)", post, re.S)
    require(new_builder is not None and "SOURCE_TIMESTAMP" not in new_builder.group("body"), "New submission builder must have no datetime serialization path")
    revision_builder = re.search(r"pub fn build_revision_tutorial_post_payload(?P<body>.*?)(?=/// Compatibility entry point)", post, re.S)
    require(revision_builder is not None and "SOURCE_TIMESTAMP" in revision_builder.group("body") and "source.tutorial_ts" in revision_builder.group("body"), "Revision builder must serialize source tutorial_ts")
    require("source_teacher_id: i64" in semantic and "form_teacher: ValidatedNewFormTeacher" in semantic, "DraftOrigin must bind immutable Revision/New teacher authority")
    require("pub struct ValidatedNewFormTeacher" in semantic and "pub(crate) fn from_validated_hidden_control" in semantic, "N2b New teacher authority must be opaque and parser-constructed")
    require("pub teacher_id: i64" not in semantic, "ValidatedNewFormTeacher teacher ID must not have a public field constructor surface")
    require("revision teacher attribution is immutable" in semantic and "new tutorial teacher attribution is immutable" in semantic, "semantic validation must reject teacher reassignment")
    require("pub fn authoritative_identity" in semantic and "self.revision_source()" in semantic, "New drafts must expose no authoritative created identity")
    require("state.provenance" not in post, "POST mapper must not use provenance as payload input")
    require("overall_level_source_raw" not in post, "POST mapper must not use raw overall-level fallback")
    for escaped in ["&amp;", "&lt;", "&gt;", "&quot;", "&#39;"]:
        require(escaped in post, f"POST Aims escaping missing {escaped}")

    new_parser = (RUST_SRC / "new_form_parser.rs").read_text(encoding="utf-8")
    require("pub struct ValidatedNewTutorialForm" in new_parser, "N2b validated New-form source type missing")
    require("pub fn parse_new_tutorial_form" in new_parser, "N2b New-form parser missing")
    require("NEW_FORBIDDEN_FIELDS" in new_parser and "NEW_CONTROL_SPECS" in new_parser, "N2b parser must consume generated New-form contract projection")
    require("from_validated_hidden_control" in new_parser, "N2b parser must be the production teacher-authority constructor")
    require("reqwest" not in new_parser and "TcpStream" not in new_parser, "N2b parser must remain transport-free")
    generated = (RUST_SRC / "gel_fields.rs").read_text(encoding="utf-8")
    require("pub const NEW_CONTROL_SPECS" in generated and "pub const NEW_FORBIDDEN_FIELDS" in generated, "generated GEL projection missing N2b New-form metadata")
    require('pub const NEW_FORM_ACTION_PATH: &str = "/study/tutorials/process";' in generated, "generated New-form action drifted")
    round_trip_bin = RUST_SRC / "bin" / "check_post_round_trip_fixtures.rs"
    require(round_trip_bin.exists(), "C4 Rust private round-trip checker is missing")
    round_trip_src = round_trip_bin.read_text(encoding="utf-8")
    require(
        "actual != expected" in round_trip_src and "payload_diff" in round_trip_src,
        "C4 checker must enforce exact independent payload equality",
    )
    require(
        "archive.identity.tutorial_ts" in round_trip_src
        and "edit_timestamp != archive.identity.tutorial_ts" in round_trip_src,
        "C4 checker must prove edit source timestamp matches revision identity",
    )
    require(
        "archive.absent" in round_trip_src and "gel_fields::ABSENT" in round_trip_src,
        "C4 checker must reconstruct absent from archive authority",
    )
    mutation_tests = ROOT / "gel-core" / "tests" / "post_mutation_isolation.rs"
    require(mutation_tests.exists(), "C4 mutation-isolation test suite is missing")


def check_generated() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_contract_artifacts.py"), "--check"],
        cwd=ROOT,
        text=True,
    )
    require(proc.returncode == 0, "generated contract artifacts are stale; run python tools/generate_contract_artifacts.py")


def main() -> int:
    try:
        fields = load("fields")
        types = load("types")
        app = load("app")
        anomalies = load("anomalies")
        evidence = load("evidence")
        semantics = load("semantics")
        reconciliation = load("reconciliation")
        round_trip = load("round_trip")
        archive_schema = load("archive_schema")
        archive_repository = load("archive_repository")
        gel_session = load("gel_session")
        n2_pw = load("n2_pw")
        n2a = load("n2a")
        new_form = load("new_form")
        n2c = load("n2c")
        ui1 = load("ui1")
        ui1_layout = load("ui1_layout")
        ui1c = load("ui1c")
        ui1c_aims = load("ui1c_aims")
        ui1d_harper = load("ui1d_harper")
        release_identity = load("release_identity")
        verification = load("verification")
        dependency_lock_policy = load("dependency_lock_policy")
        check_contracts(
            fields,
            types,
            app,
            anomalies,
            evidence,
            semantics,
            reconciliation,
            round_trip,
            archive_schema,
            archive_repository,
            gel_session,
            n2_pw,
            n2a,
            new_form,
            n2c,
            ui1,
            ui1_layout,
            ui1c,
            ui1c_aims,
            ui1d_harper,
            release_identity,
            verification,
            dependency_lock_policy,
        )
        check_python_oracle(types, fields)
        check_rust_opaque_boundary()
        check_rust_semantic_contract()
        check_generated()
    except ContractError as exc:
        print(f"check:contracts FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:contracts PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
