#!/usr/bin/env python3
"""check:governance — validate ownership, component boundaries, docs and gate semantics."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
DOCS = ROOT / "docs"

FILES = {
    "documentation": "documentation_governance.json",
    "components": "component_boundaries.json",
    "ownership": "state_ownership.json",
    "gate": "release_gate.json",
}


class GovernanceError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GovernanceError(message)


def load(name: str) -> dict[str, Any]:
    path = CONTRACTS / FILES[name]
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GovernanceError(f"cannot parse {path.relative_to(ROOT)}: {exc}") from exc


def unique(values: list[str], label: str) -> None:
    dupes = sorted({v for v in values if values.count(v) > 1})
    require(not dupes, f"duplicate {label}: {dupes}")


def check_documentation_contract(docgov: dict[str, Any]) -> None:
    require(docgov.get("contract_id") == "documentation_governance", "bad documentation_governance contract_id")
    require(docgov.get("contract_version") == 3, "documentation_governance contract_version must be 3")
    ranks = sorted(docgov["authority_order"], key=lambda x: x["rank"])
    require([x["rank"] for x in ranks] == [1, 2, 3, 4, 5], "documentation authority ranks must be exactly 1..5")
    expected = [
        "executable_contracts_tests",
        "active_component_specs",
        "master_cross_component_specs",
        "operational_docs",
        "adrs_history",
    ]
    require([x["class"] for x in ranks] == expected, "documentation authority order drifted")
    required_sections = docgov["active_spec_required_sections"]
    require(required_sections == [
        "Role", "Scope", "Authority", "Reads", "Writes", "Must not write",
        "State transitions", "Failure semantics", "Dependencies", "Tests"
    ], "active component required section contract drifted")
    allowed = set(docgov["adr_statuses"])
    require(allowed == {"proposed", "accepted_historical", "superseded", "rejected"}, "ADR status taxonomy drifted")
    require(set(docgov.get("state_classification_taxonomy", {})) == {"source", "decision", "derived", "projection", "evidence"}, "five-way state classification taxonomy drifted")
    require("current-state.json" in docgov.get("index_rule", "") and "projection" in docgov.get("index_rule", "").lower(), "documentation governance must keep current-state generated/projection-only")
    meta_rule = docgov.get("meta_governance_protocol_rule", "").lower()
    require("meta-governance" in meta_rule and "not gel runtime/domain authority" in meta_rule, "documentation governance must keep generic agent protocol outside GEL runtime authority")


def check_components(components: dict[str, Any], ownership: dict[str, Any]) -> None:
    require(components.get("contract_id") == "component_boundaries", "bad component_boundaries contract_id")
    require(components.get("contract_version") == 30, "component_boundaries contract_version must be 30")
    items = components.get("components", [])
    require(items, "component_boundaries.components must not be empty")
    unique([c["id"] for c in items], "component id")
    component_ids = {c["id"] for c in items}
    state_ids = {s["id"] for s in ownership["state_classes"]}
    state_by_id = {s["id"]: s for s in ownership["state_classes"]}
    pseudo_writers = {"reviewed_repository_change"}
    pseudo_readers = {"developers", "future_viewer", "release_gate"}

    required = {
        "id", "name", "status", "role", "scope", "authority", "reads", "writes",
        "must_not_write", "state_transitions", "failure_semantics", "dependencies", "tests"
    }
    for c in items:
        missing = sorted(required - set(c))
        require(not missing, f"component {c.get('id')} missing keys {missing}")
        for key in ["scope", "authority", "must_not_write", "state_transitions", "failure_semantics", "dependencies", "tests"]:
            require(isinstance(c[key], list) and c[key], f"component {c['id']} {key} must be a non-empty list")
        require(isinstance(c["reads"], list), f"component {c['id']} reads must be a list")
        require(isinstance(c["writes"], list), f"component {c['id']} writes must be a list")
        if not c["writes"]:
            reference_only = (
                "historical" in c["status"].lower()
                or "reference" in c["status"].lower()
                or "read-only" in c["role"].lower()
                or any("no production" in x.lower() and "write authority" in x.lower() for x in c["authority"])
            )
            require(reference_only, f"component {c['id']} has no write state but is not explicitly read-only/reference-only")
        unknown = sorted((set(c["reads"]) | set(c["writes"]) | set(c["must_not_write"])) - state_ids)
        require(not unknown, f"component {c['id']} references unknown state(s): {unknown}")
        overlap = sorted(set(c["writes"]) & set(c["must_not_write"]))
        require(not overlap, f"component {c['id']} both writes and must-not-write: {overlap}")
        for state_id in c["reads"]:
            require(c["id"] in state_by_id[state_id]["readers"], f"component {c['id']} reads {state_id} but state ownership does not list it as a reader")

    planned = set(components.get("planned_not_active", []))
    require(not (planned & component_ids), "planned_not_active must not also be active component IDs")
    semantic_component = next(c for c in items if c["id"] == "rust_semantic_form")
    require(any("DraftOrigin" in x for x in semantic_component["scope"]), "semantic component scope must name DraftOrigin")
    require(any("provenance-only" in x.lower() for x in semantic_component["scope"]), "semantic component must declare raw source values provenance-only")
    post_component = next(c for c in items if c["id"] == "rust_post_mapper")
    require(any("HTML-escape" in x for x in post_component["scope"]), "POST mapper scope must require Aims HTML escaping")
    require(any("NewTutorialSubmission" in x and "RevisionTutorialSubmission" in x for x in post_component["scope"]), "N2a POST mapper must declare distinct New/Revision submission types")
    require(any("no authoritative created GEL identity" in x for x in semantic_component["scope"]), "N2a semantic scope must deny New authoritative identity before readback")
    require(any("teacher attribution" in x.lower() and "immutab" in x.lower() for x in semantic_component["scope"]), "N2a semantic scope must bind immutable teacher authority")
    fixture_component = next(c for c in items if c["id"] == "rust_fixture_tooling")
    require(
        any("independent expected successful-control payload" in x for x in fixture_component["scope"]),
        "C4 fixture tooling must independently reconstruct expected POST payloads",
    )
    require(
        "offline_post_round_trip_report" in fixture_component["writes"],
        "C4 fixture tooling must own the offline round-trip report",
    )
    reconciliation_component = next(c for c in items if c["id"] == "rust_reconciliation")
    require(
        any("group-owned" in x for x in reconciliation_component["scope"]),
        "C3 reconciliation component must keep collision source states group-owned",
    )
    require(
        any("divergent" in x.lower() and "fail" in x.lower() for x in reconciliation_component["failure_semantics"]),
        "C3 reconciliation failure semantics must fail closed for divergent collisions",
    )
    require(
        any("historical state authority" in x.lower() for x in semantic_component["scope"]),
        "C3 semantic component must require historical state authority",
    )
    schema_component = next(c for c in items if c["id"] == "archive_schema_migrator")
    require(
        schema_component["writes"] == ["archive_v2_candidate_database"],
        "D1 schema migrator may write only the noncanonical v2 candidate database",
    )
    require(
        "normalized_local_archive" in schema_component["must_not_write"],
        "D1 schema migrator must not mutate the canonical legacy archive",
    )
    require(
        any("separate" in x.lower() and "destination" in x.lower() for x in schema_component["scope"]),
        "D1 migration component must use a separate destination",
    )
    repository_component = next(c for c in items if c["id"] == "rust_archive_repository")
    require(repository_component["writes"] == ["archive_repository_read_models"], "D2 public repository may write only ephemeral read models")
    require("archive_v2_candidate_database" in repository_component["must_not_write"], "D2 public repository must not write archive v2")
    sync_repository = next(c for c in items if c["id"] == "rust_archive_sync_repository")
    require(set(sync_repository["writes"]) == {"normalized_local_archive", "archive_reconciliation_metadata", "archive_v2_candidate_database"}, "A2 Rust archive component write boundary drifted")
    require("normalized_local_archive" not in sync_repository["must_not_write"], "A2 Rust archive component must own canonical local archive")
    require(sync_repository["status"] == "active_a2_canonical", "A2 Rust archive component status drifted")
    require(any("crate-private" in x.lower() for x in sync_repository["authority"]), "D2 Rust sync repository authority must be crate-private")
    require("rust_sqlite_repository" not in planned, "obsolete planned rust_sqlite_repository placeholder must be removed when D2 activates")
    require("rust_archiver_runtime" not in planned, "A2 Rust archiver runtime must leave planned_not_active after cutover")
    print_component = next(c for c in items if c["id"] == "rust_print_parser")
    require(print_component["status"] == "active_a1_pending_strict_acceptance", "A1 Rust print parser lifecycle status drifted")
    require(any("Python-v4.9" in x for x in print_component["scope"] + print_component["authority"]), "A1 print parser must bind Python-v4.9 parity authority")
    session_component = next(c for c in items if c["id"] == "rust_gel_session")
    require(
        "authenticated_gel_session" in session_component["writes"],
        "N1 session must own authenticated session capability state",
    )
    require(
        all(state in session_component["must_not_write"] for state in ["normalized_local_archive", "tutorial_post_payload"]),
        "N1 session must not acquire archive or submission write authority",
    )
    require(
        any("two" in x.lower() and "login" in x.lower() and "post" in x.lower() for x in session_component["scope"]),
        "N1 session scope must explicitly constrain login POSTs",
    )
    require(
        any("generic request" in x.lower() for x in session_component["scope"]),
        "N1 session must explicitly reject a generic request surface",
    )
    require("rust_gel_session" not in planned, "rust_gel_session must leave planned_not_active when N1 activates")
    require("gel_new_form_html" in session_component["writes"], "N2b session must own ephemeral New-form HTML acquisition")
    require(any("zero locator" in x.lower() or "zero-locator" in x.lower() for x in session_component["scope"]), "N2b session scope must fix the New-form zero-locator GET")
    new_form_component = next(c for c in items if c["id"] == "rust_new_tutorial_form_parser")
    require(new_form_component["writes"] == ["validated_new_tutorial_form_state"], "N2b parser may write only validated New-form source state")
    require("live_gel_tutorials" in new_form_component["must_not_write"], "N2b parser must not write GEL tutorial state")
    require("tutorial_post_payload" in new_form_component["must_not_write"], "N2b parser must not own POST payload state")
    require(any("datetime" in x.lower() and "absent" in x.lower() for x in new_form_component["scope"]), "N2b parser must require New datetime absence")
    require(any("sole production" in x.lower() and "teacher" in x.lower() for x in new_form_component["scope"] + new_form_component["authority"]), "N2b parser must own sole production New teacher authority")
    pw_component = next(c for c in items if c["id"] == "n2_playwright_evidence_harness")
    require(pw_component["writes"] == ["n2_playwright_private_evidence"], "PW1 harness may write only private evidence")
    require("live_gel_tutorials" in pw_component["must_not_write"], "PW1 harness must not write GEL tutorial state")
    require("tutorial_post_payload" in pw_component["must_not_write"], "PW1 harness must not own production POST payload state")
    require(any("firewall" in x.lower() and "before" in x.lower() for x in pw_component["scope"]), "PW1 component scope must install firewall before navigation")
    require(any("redacted path" in x.lower() and "stderr" in x.lower() for x in pw_component["scope"]), "PW1 component scope must govern privacy-safe authentication diagnostics")
    require(any("server acceptance" in x.lower() or "server reassignment" in x.lower() for x in pw_component["authority"]), "PW1 authority must keep server reassignment unresolved")

    writer_service = next(c for c in items if c["id"] == "writer_tauri_app_service")
    require(writer_service["status"] == "active_w2_a2", "Writer Tauri service must be active at W2")
    require(set(writer_service["writes"]) == {"writer_active_draft", "writer_ui_view_models"}, "UI1 Tauri service writer boundary drifted")
    require(all(state in writer_service["must_not_write"] for state in ["live_gel_tutorials", "normalized_local_archive", "archive_v2_candidate_database", "tutorial_post_payload"]), "Writer Tauri service must retain no direct GEL/SQLite/POST write capability; archive sync is delegated to RustArchiver")
    require(any("RustArchiver::sync_full" in x for x in writer_service["authority"]), "Writer A2 archive sync must be explicitly delegated to RustArchiver")
    require(any("apply_tutorial_draft_edit" in x for x in writer_service["scope"]), "UI1 Tauri service must delegate semantic edits to rust_semantic_form")
    writer_react = next(c for c in items if c["id"] == "writer_react_ui")
    require(writer_react["status"] == "active_ui1e", "UI1 React presentation must be active for UI1e")
    semantic_component = next(c for c in items if c["id"] == "rust_semantic_form")
    require(semantic_component["status"] == "active_ui1c5", "rust_semantic_form must be active at UI1c5")
    require(any("field-disposition matrix" in x.lower() for x in semantic_component["scope"]), "UI1c0 semantic component must own field-disposition matrix")
    require(any("initialcoursetype" in x.lower() for x in semantic_component["scope"]), "UI1c0 semantic component must own InitialCourseType adapter")
    require(any("draftvalidationissue" in x.lower() for x in semantic_component["scope"]), "UI1c0 semantic component must own structured validation DTO")
    require(any("same-role" in x.lower() and "regression" in x.lower() for x in semantic_component["scope"]), "UI1c0 semantic component must own same-role regression protection")
    require(set(writer_react["writes"]) == {"writer_ui_presentation_state", "harper_disabled_rules", "harper_ignored_findings"}, "React may write only presentation state and session-only Harper suppression state")
    harper_component = next(c for c in items if c["id"] == "writer_harper_service")
    require(harper_component["writes"] == ["harper_check_result"], "Harper service must write only derived check results")
    require("harper_user_dictionary" in harper_component["reads"], "Harper service must read the governed user dictionary")
    dictionary_component = next(c for c in items if c["id"] == "harper_dictionary_repository")
    require(dictionary_component["writes"] == ["harper_user_dictionary"], "dictionary repository must be the sole dictionary writer")
    require("future schema" in " ".join(dictionary_component["failure_semantics"]).lower(), "dictionary repository must fail closed on future schemas")
    require(all(state in writer_react["must_not_write"] for state in ["semantic_form_state", "writer_active_draft", "authenticated_gel_session", "live_gel_tutorials", "normalized_local_archive", "tutorial_post_payload"]), "React must have complete semantic/session/GEL/archive no-write closure")
    require({"writer_harper_service", "harper_dictionary_repository"} <= component_ids, "UI1d Harper/dictionary components must be active")

    dependency_tooling = next(c for c in items if c["id"] == "dependency_lock_tooling")
    require(set(dependency_tooling["writes"]) == {"dependency_lock_state", "dependency_lock_manifest"}, "dependency lock tooling write boundary drifted")
    require("dependency_manifest_source" in dependency_tooling["reads"], "dependency lock tooling must read dependency manifests")
    require(any("LOCK_GENERATOR_UNAVAILABLE" in x for x in dependency_tooling["scope"]), "dependency lock tooling must own bounded tool-unavailable detection")
    dep_failure_text = " ".join(dependency_tooling["failure_semantics"]).lower()
    require("portable" in dep_failure_text and "skip" in dep_failure_text and "strict" in dep_failure_text and "fail" in dep_failure_text, "dependency lock tooling must encode portable SKIP / strict FAIL semantics")
    current_state_tooling = next(c for c in items if c["id"] == "current_state_tooling")
    require(current_state_tooling["writes"] == ["current_state_projection"], "current-state tooling may write only its projection")
    require(any("projection" in x.lower() and "cannot" in x.lower() for x in current_state_tooling["authority"]), "current-state tooling must deny runtime authority")
    release_tooling = next(c for c in items if c["id"] == "release_artifact_tooling")
    require(set(release_tooling["writes"]) == {"release_gate_evidence", "distribution_manifest", "release_artifact_receipt"}, "release artifact tooling write boundary drifted")
    require("dependency_lock_state" in release_tooling["must_not_write"], "release packaging must not rewrite dependency decisions")
    ci = next(c for c in items if c["id"] == "continuous_enforcement")
    require(ci["writes"] == ["ci_verification_evidence"], "CI may write only portable verification evidence")
    require(any("never automatically promote" in x.lower() for x in ci["scope"]), "CI must prohibit automatic promotion")

    governance_tooling = next(c for c in items if c["id"] == "governance_tooling")
    require(all(x in governance_tooling["reads"] for x in ["agent_governance_protocol_decision", "agent_governance_project_profile"]), "governance tooling must read agent protocol/profile decisions")
    require(all(x in governance_tooling["must_not_write"] for x in ["agent_governance_protocol_decision", "agent_governance_project_profile"]), "governance tooling must not write agent protocol/profile decisions")
    require(any("meta-governance" in x.lower() and "runtime/domain authority" in x.lower() for x in governance_tooling["authority"]), "governance tooling must explicitly deny agent protocol runtime authority")

    state_by_id = {s["id"]: s for s in ownership["state_classes"]}
    for c in items:
        for state_id in c["writes"]:
            permitted = set(state_by_id[state_id]["permitted_writers"])
            require(c["id"] in permitted, f"component {c['id']} writes {state_id} but state ownership does not permit it")
        for state_id in c["must_not_write"]:
            permitted = set(state_by_id[state_id]["permitted_writers"])
            require(c["id"] not in permitted, f"component {c['id']} must not write {state_id} but ownership permits it")

    all_writers = set().union(*(set(s["permitted_writers"]) for s in ownership["state_classes"]))
    unknown_writers = sorted(all_writers - component_ids - pseudo_writers)
    require(not unknown_writers, f"state ownership references unknown permitted writers: {unknown_writers}")
    all_readers = set().union(*(set(s["readers"]) for s in ownership["state_classes"]))
    unknown_readers = sorted(all_readers - component_ids - pseudo_readers)
    require(not unknown_readers, f"state ownership references unknown readers: {unknown_readers}")


def check_ownership(ownership: dict[str, Any]) -> None:
    require(ownership.get("contract_id") == "state_ownership", "bad state_ownership contract_id")
    require(ownership.get("contract_version") == 23, "state_ownership contract_version must be 23")
    states = ownership.get("state_classes", [])
    require(states, "state_ownership.state_classes must not be empty")
    unique([s["id"] for s in states], "state class id")
    required = {"id", "class", "source_or_derived", "state_kind", "canonical", "permitted_writers", "readers", "retention", "invalidation", "current_materialization"}
    for s in states:
        missing = sorted(required - set(s))
        require(not missing, f"state {s.get('id')} missing keys {missing}")
        require(isinstance(s["permitted_writers"], list) and s["permitted_writers"], f"state {s['id']} must have at least one writer")
        if s["canonical"]:
            require(len(s["permitted_writers"]) == 1, f"canonical state {s['id']} must have exactly one current permitted writer")
        require(s["retention"].strip(), f"state {s['id']} missing retention rule")
        require(s["invalidation"].strip(), f"state {s['id']} missing invalidation rule")
        require(s["state_kind"] in {"source", "decision", "derived", "projection", "evidence"}, f"state {s['id']} has invalid five-way state_kind")

    archive = next(s for s in states if s["id"] == "normalized_local_archive")
    require(archive["permitted_writers"] == ["rust_archive_sync_repository"], "A2 canonical local archive writer must be rust_archive_sync_repository")
    post = next(s for s in states if s["id"] == "tutorial_post_payload")
    require(post["canonical"] is False, "tutorial POST payload must remain derived/noncanonical")
    validated = next(s for s in states if s["id"] == "validated_edit_form_state")
    require(validated["permitted_writers"] == ["rust_edit_form_validator"], "validated edit-form state must have exactly the validator as writer")
    raw_edit = next(s for s in states if s["id"] == "parsed_edit_form_state")
    require("rust_semantic_form" not in raw_edit["readers"], "semantic form must not consume raw parsed edit state after C1")
    require("source_present" in ownership["archive_source_disappearance_policy"] and "last_seen" in ownership["archive_source_disappearance_policy"], "source-disappearance policy must name source_present/last_seen representation")
    policy = ownership["archive_source_disappearance_policy"].lower()
    require("failed syncs never invalidate" in policy, "source-disappearance policy must fail closed on failed sync")
    require("partial auxiliary" in policy and "preserve prior semantic source evidence" in policy, "A2 partial auxiliary acquisition must preserve prior semantic source evidence for still-observed tutorial keys")
    semantic = next(s for s in states if s["id"] == "semantic_form_state")
    require(semantic["permitted_writers"] == ["rust_semantic_form"], "semantic form state must have exactly the semantic component as current writer")
    require("DraftOrigin" in semantic["current_materialization"], "semantic state ownership must name explicit DraftOrigin materialization")
    require("no New authoritative created identity" in semantic["current_materialization"], "N2a semantic ownership must deny New identity before readback")
    require("authentication loss" in semantic["invalidation"].lower(), "N2a semantic invalidation must cover authentication loss")
    require("changed latest tutorial" in semantic["invalidation"].lower(), "N2a semantic invalidation must cover latest-source staleness")
    require("omit datetime" in post["retention"].lower(), "N2a payload ownership must require New datetime omission")
    require("exact source tutorial_ts" in post["retention"], "N2a payload ownership must require exact Revision timestamp")
    require("provenance" in semantic["retention"].lower(), "semantic state retention must distinguish editable values from provenance")
    require("authority" in semantic["retention"].lower(), "semantic state retention must require C3 historical state authority")
    archive_reconciliation = next(s for s in states if s["id"] == "archive_reconciliation_metadata")
    require(
        "position" in archive_reconciliation["retention"].lower()
        and "not authoritative" in archive_reconciliation["retention"].lower(),
        "archive reconciliation metadata must reject positional collision ownership",
    )
    derived_reconciliation = next(s for s in states if s["id"] == "derived_reconciliation_result")
    require(
        "group-owned" in derived_reconciliation["retention"].lower(),
        "derived reconciliation state must keep collision candidates group-owned",
    )
    round_trip_report = next(s for s in states if s["id"] == "offline_post_round_trip_report")
    require(
        round_trip_report["permitted_writers"] == ["rust_fixture_tooling"],
        "C4 offline round-trip report must have exactly rust_fixture_tooling as writer",
    )
    require(
        round_trip_report["canonical"] is False,
        "C4 offline round-trip report must remain derived/noncanonical",
    )
    candidate = next(s for s in states if s["id"] == "archive_v2_candidate_database")
    require(candidate["canonical"] is False, "A2 must retain archive_v2_candidate_database as noncanonical test/migration state")
    require(
        set(candidate["permitted_writers"]) == {"archive_schema_migrator", "rust_archive_sync_repository"},
        "D2 v2 candidate DB writers must be migrator + crate-private Rust sync repository",
    )
    read_models = next(s for s in states if s["id"] == "archive_repository_read_models")
    require(read_models["permitted_writers"] == ["rust_archive_repository"], "D2 read models must be owned only by rust_archive_repository")
    require(read_models["canonical"] is False, "D2 repository read models must remain derived/noncanonical")
    session = next(s for s in states if s["id"] == "authenticated_gel_session")
    require(session["permitted_writers"] == ["rust_gel_session"], "N1 authenticated session state must be owned only by rust_gel_session")
    require(session["canonical"] is False, "N1 authenticated session state must remain ephemeral/noncanonical")
    require("credentials are never retained" in session["retention"].lower(), "N1 credential retention must be explicitly zero")
    new_html = next(s for s in states if s["id"] == "gel_new_form_html")
    require(new_html["permitted_writers"] == ["rust_gel_session"], "N2b New-form HTML must be materialized only by rust_gel_session")
    require(new_html["canonical"] is False, "N2b New-form HTML must remain ephemeral/noncanonical")
    require("never persisted" in new_html["retention"].lower(), "N2b raw New-form HTML must not be persisted")
    validated_new = next(s for s in states if s["id"] == "validated_new_tutorial_form_state")
    require(validated_new["permitted_writers"] == ["rust_new_tutorial_form_parser"], "N2b validated New-form state must have exactly the parser as writer")
    require(validated_new["canonical"] is False, "N2b validated New-form state must remain noncanonical")
    require("authentication/session loss" in validated_new["invalidation"].lower(), "N2b validated source invalidation must cover authentication loss")
    require("no datetime" in validated_new["current_materialization"].lower(), "N2b validated source state must carry no datetime")
    pw_evidence = next(s for s in states if s["id"] == "n2_playwright_private_evidence")
    require(pw_evidence["permitted_writers"] == ["n2_playwright_evidence_harness"], "PW1 private evidence must have exactly the harness as writer")
    require(pw_evidence["canonical"] is False, "PW1 evidence must remain derived/noncanonical")
    require("credential" in pw_evidence["retention"].lower() and "never" in pw_evidence["retention"].lower(), "PW1 evidence retention must explicitly prohibit credentials")
    active_draft = next(s for s in states if s["id"] == "writer_active_draft")
    require(active_draft["permitted_writers"] == ["writer_tauri_app_service"], "UI1 active draft must have exactly the Tauri service as container writer")
    require(active_draft["canonical"] is False and "Process memory only" in active_draft["retention"], "UI1 active draft must remain ephemeral/noncanonical")
    writer_views = next(s for s in states if s["id"] == "writer_ui_view_models")
    require(writer_views["permitted_writers"] == ["writer_tauri_app_service"], "UI1 view models must be written only by the Tauri service")
    presentation = next(s for s in states if s["id"] == "writer_ui_presentation_state")
    require(presentation["permitted_writers"] == ["writer_react_ui"], "UI1 presentation state must be React-owned only")
    require("No localStorage/sessionStorage" in presentation["retention"], "UI1 React state must not persist in browser storage")
    require("writer_tauri_app_service" in semantic["readers"], "UI1 application service may read validated semantic state")
    require(semantic["permitted_writers"] == ["rust_semantic_form"], "UI1 must not weaken semantic_form_state sole-writer authority")
    require("LevelRegressionBaseline" in semantic["current_materialization"], "UI1c0 semantic state must document New regression baseline")
    require("InitialCourseType" in semantic["current_materialization"], "UI1c0 semantic state must document InitialCourseType adapter")
    api_json = next(s for s in states if s["id"] == "gel_api_json")
    require("rust_gel_session" in api_json["permitted_writers"], "N1 session must materialize ephemeral API JSON")
    require("email" in api_json["retention"].lower(), "N1 API JSON retention must declare email minimization")
    dictionary_state = next(s for s in states if s["id"] == "harper_user_dictionary")
    require(dictionary_state["canonical"] is True, "Harper user dictionary must be canonical local preference state")
    require(dictionary_state["permitted_writers"] == ["harper_dictionary_repository"], "Harper dictionary must have exactly one writer")
    require(dictionary_state["state_kind"] == "source", "Harper dictionary must be source state")
    check_result = next(s for s in states if s["id"] == "harper_check_result")
    require(check_result["canonical"] is False, "Harper check results must remain derived/noncanonical")
    require(check_result["permitted_writers"] == ["writer_harper_service"], "Harper check result must have the Harper service as sole writer")
    require("exact source snapshot" in check_result["retention"].lower(), "Harper check result retention must bind exact source snapshot")
    protocol_decision = next(s for s in states if s["id"] == "agent_governance_protocol_decision")
    profile_decision = next(s for s in states if s["id"] == "agent_governance_project_profile")
    for item in [protocol_decision, profile_decision]:
        require(item["canonical"] is True and item["state_kind"] == "decision", f"{item['id']} must be canonical decision state")
        require(item["permitted_writers"] == ["reviewed_repository_change"], f"{item['id']} must be changed only by reviewed repository change")
        require("runtime" in item["retention"].lower() and "authority" in item["retention"].lower(), f"{item['id']} must deny runtime authority")
    dependency_lock = next(s for s in states if s["id"] == "dependency_lock_state")
    require(dependency_lock["canonical"] is True and dependency_lock["state_kind"] == "decision", "dependency locks must be canonical decision state")
    require(dependency_lock["permitted_writers"] == ["dependency_lock_tooling"], "dependency locks must have one governed writer")
    require("LOCK_GENERATOR_UNAVAILABLE" in dependency_lock["retention"], "dependency lock ownership must classify tool-unavailable exception as non-lock evidence")
    require("portable" in dependency_lock["invalidation"].lower() and "strict" in dependency_lock["invalidation"].lower(), "dependency lock ownership must distinguish portable exception from strict requirement")
    current_projection = next(s for s in states if s["id"] == "current_state_projection")
    require(current_projection["canonical"] is False and current_projection["state_kind"] == "projection", "current-state must remain a noncanonical projection")
    release_evidence = next(s for s in states if s["id"] == "release_gate_evidence")
    require(release_evidence["state_kind"] == "evidence" and release_evidence["canonical"] is False, "strict release result must remain evidence state")
    ci_evidence = next(s for s in states if s["id"] == "ci_verification_evidence")
    require(ci_evidence["state_kind"] == "evidence" and ci_evidence["permitted_writers"] == ["continuous_enforcement"], "CI output must remain evidence-only")
    require("separate" in candidate["retention"].lower() or "source" in candidate["retention"].lower(), "D1 candidate retention must preserve legacy source archive")


def check_release_gate(gate: dict[str, Any]) -> None:
    require(gate.get("contract_id") == "release_gate", "bad release_gate contract_id")
    require(gate.get("contract_version") == 25, "release_gate contract_version must be 25")
    require(gate.get("current_release_scope") == "w2", "W2 must be the current release scope")
    require("ui1c5" in gate.get("scopes", {}), "UI1c5 release scope missing")
    require(gate["scopes"]["ui1c5"]["checks"][-2:] == ["ui1c5_integrated", "ui1c5_integrated_behavior"], "UI1c5 dedicated checks missing from release scope")
    profiles = gate.get("profiles", {})
    require(set(profiles) == {"portable", "strict"}, "release profiles must be exactly portable and strict")
    require(profiles["portable"]["missing_private_fixture_policy"] == "skip", "portable missing-private policy must be skip")
    require(profiles["strict"]["missing_private_fixture_policy"] == "fail", "strict missing-private policy must be fail")
    require(profiles["portable"].get("missing_dependency_lock_tool_policy") == "skip_when_corresponding_generator_unavailable", "portable lock-generator exception policy drifted")
    require(profiles["strict"].get("missing_dependency_lock_tool_policy") == "fail", "strict lock-generator exception must fail")
    require(set(gate["result_taxonomy"]) == {"PASS", "FAIL", "SKIP"}, "check result taxonomy must be PASS/FAIL/SKIP")
    require(set(gate.get("acceptance_status_taxonomy", {})) == {"STRUCTURAL_PASS", "STRUCTURAL_PASS_WITH_SKIPS", "TARGET_ACCEPTANCE_REQUIRED", "STRICT_ACCEPTED", "RELEASE_ARTIFACT_VERIFIED"}, "release acceptance taxonomy drifted")
    checks = gate.get("checks", [])
    unique([c["id"] for c in checks], "release check id")
    check_by_id = {c["id"]: c for c in checks}
    required = {
        "contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository", "gel_session",
        "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form", "n2c_prepopulation",
        "dependency_locks", "dependency_lock_exception_behavior", "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests",
        "private_fixture_parity", "private_collision_authority", "private_post_round_trip",
        "ui1_boundaries", "frontend_dependencies", "ui1_frontend_typecheck", "ui1_frontend_build",
        "ui1_hybrid_layout", "ui1c_forms_contract", "ui1c_semantic_validation", "ui1c_frontend_forms", "ui1c1_editor_framework", "ui1c2_4_semantic_forms",
        "current_state", "verification_semantics", "source_intake", "release_control", "release_control_behavior", "ci_contract",
        "a1_print_parity", "a1_print_behavior", "private_print_parity", "a2_archiver", "a2_archiver_behavior",
        "ui1c5_integrated", "ui1c5_integrated_behavior", "ui1d_harper", "ui1d_harper_behavior",
        "ui1e_safety", "ui1e_workflow_behavior", "w2_boundaries", "w2_submission_behavior"
    }
    require(set(check_by_id) == required, f"release gate check set drifted: missing={sorted(required-set(check_by_id))} extra={sorted(set(check_by_id)-required)}")
    allowed_classes = {"lint", "structural", "behavioral", "acceptance"}
    for check in checks:
        require(check.get("evidence_class") in allowed_classes, f"release check {check['id']} missing evidence class")
    require(check_by_id["contracts"].get("command") == ["python", "tools/check_contracts.py"], "release gate must include canonical check:contracts")
    require("Protocol v1.1" in check_by_id["governance"].get("purpose", "") and "runtime authority" in check_by_id["governance"].get("purpose", ""), "governance gate purpose must include agent protocol/profile non-authority validation")
    for cid, tool in [
        ("archive_schema_v2", "check_archive_schema.py"), ("archive_repository", "check_archive_repository.py"),
        ("gel_session", "check_gel_session.py"), ("n2_playwright_zero_write", "check_n2_playwright_zero_write.py"),
        ("n2a_semantic_post", "check_n2a_semantic_post.py"), ("n2b_new_form", "check_n2b_new_form.py"),
        ("n2c_prepopulation", "check_n2c_prepopulation.py"), ("ui1_boundaries", "check_ui1_boundaries.py"),
        ("ui1_hybrid_layout", "check_ui1_hybrid_layout.py"), ("ui1c_forms_contract", "check_ui1c_forms_contract.py"),
        ("ui1c_frontend_forms", "check_ui1c_frontend_forms.py"),
        ("ui1c1_editor_framework", "check_ui1c1_editor_framework.py"),
        ("ui1c2_4_semantic_forms", "check_ui1c2_4_semantic_forms.py"), ("dependency_locks", "check_dependency_lockfiles.py"),
        ("dependency_lock_exception_behavior", "check_dependency_lock_exception_behavior.py"),
        ("current_state", "check_current_state.py"), ("verification_semantics", "check_verification_semantics.py"),
        ("release_control", "check_release_control.py"), ("release_control_behavior", "check_release_control_behavior.py"),
        ("ci_contract", "check_ci_contract.py"),
        ("a1_print_parity", "check_a1_print_parity.py"),
        ("a2_archiver", "check_a2_archiver.py"),
        ("ui1c5_integrated", "check_ui1c5_integrated.py"),
        ("ui1d_harper", "check_ui1d_harper.py"),
        ("ui1e_safety", "check_ui1e_safety.py"),
        ("w2_boundaries", "check_w2_boundaries.py")
    ]:
        require(check_by_id[cid].get("command")[:3] == ["python", "-S", f"tools/{tool}"], f"{cid} must use dependency-minimal Python -S checker")
    require(check_by_id["source_intake"].get("command") == ["python", "-S", "tools/check_intake.py", "--mode", "source"], "source intake command drifted")
    require(check_by_id["dependency_locks"].get("kind") == "dependency_locks", "dependency lock release check must use profile-aware runner kind")
    require(check_by_id["dependency_locks"].get("portable_tool_unavailable_policy") == "skip" and check_by_id["dependency_locks"].get("strict_tool_unavailable_policy") == "fail", "dependency lock exception result semantics drifted")
    require(check_by_id["dependency_locks"].get("policy_contract") == "contracts/dependency_lock_policy.json", "dependency lock release check must bind policy contract")
    require(check_by_id["rust_workspace_fmt"].get("command") == ["cargo", "fmt", "--all", "--", "--check"], "workspace rustfmt command drifted")
    require(check_by_id["rust_workspace_clippy"].get("command") == ["cargo", "clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"], "workspace clippy must be --locked")
    require(check_by_id["rust_workspace_tests"].get("command") == ["cargo", "test", "--workspace", "--locked"], "workspace tests must be --locked")
    require(check_by_id["ui1c_semantic_validation"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1c_semantic_contract"], "UI1c focused semantic validation must be locked")
    require(check_by_id["a1_print_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "print_parity"], "A1 print behavior command drifted")
    require(check_by_id["a2_archiver_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "archiver::tests"], "A2 archiver behavior command drifted")
    require(check_by_id["ui1c5_integrated_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1c5_integrated"], "UI1c5 integrated behavior command drifted")
    require(check_by_id["ui1d_harper"].get("command") == ["python", "-S", "tools/check_ui1d_harper.py"], "UI1d structural check command drifted")
    require(check_by_id["ui1d_harper_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1d_harper"], "UI1d behavioral check command drifted")
    require(check_by_id["w2_submission_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "submission_transport"], "W2 behavioral check command drifted")
    require(check_by_id["ui1e_workflow_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1e_workflow"], "UI1e behavioral check command drifted")
    private_print = check_by_id["private_print_parity"]
    require(private_print.get("kind") == "private_print_parity" and private_print.get("private") is True, "A1 private print parity gate kind/private flag drifted")
    require(private_print.get("portable_missing_policy") == "skip" and private_print.get("strict_missing_policy") == "fail", "A1 private print parity portable/strict policy drifted")
    require(check_by_id["frontend_dependencies"].get("cwd") == "writer-ui" and check_by_id["frontend_dependencies"].get("command") == ["npm", "ci", "--no-audit", "--no-fund"], "frontend dependencies must use npm ci")
    require(check_by_id["ui1_frontend_typecheck"].get("cwd") == "writer-ui" and check_by_id["ui1_frontend_typecheck"].get("command") == ["npm", "run", "typecheck"], "UI1 frontend typecheck command drifted")
    require(check_by_id["ui1_frontend_build"].get("cwd") == "writer-ui" and check_by_id["ui1_frontend_build"].get("command") == ["npm", "run", "build"], "UI1 frontend build command drifted")
    for cid in ["rust_workspace_clippy", "rust_workspace_tests", "ui1c_semantic_validation", "ui1c5_integrated_behavior"]:
        require("--locked" in check_by_id[cid]["command"], f"{cid} must use Cargo --locked")
    require(not ({"rust_fmt", "rust_clippy", "rust_tests", "ui1_rust_fmt", "ui1_rust_clippy", "ui1_rust_tests"} & set(check_by_id)), "duplicated per-crate Rust release checks must be retired")
    scopes = gate.get("scopes", {})
    gri_required = required - {
        "ui1c5_integrated", "ui1c5_integrated_behavior",
        "ui1d_harper", "ui1d_harper_behavior",
        "ui1e_safety", "ui1e_workflow_behavior",
        "w2_boundaries", "w2_submission_behavior"
    }
    require("gri" in scopes and set(scopes["gri"]["checks"]) == gri_required and len(scopes["gri"]["checks"]) == 39, "GRI scope must remain the strictly accepted 39-check baseline")

    ui1c5_required = required - {
        "ui1d_harper", "ui1d_harper_behavior",
        "ui1e_safety", "ui1e_workflow_behavior",
        "w2_boundaries", "w2_submission_behavior"
    }
    require("ui1c5" in scopes and set(scopes["ui1c5"]["checks"]) == ui1c5_required and len(scopes["ui1c5"]["checks"]) == 41, "UI1c5 scope must remain the 41-check predecessor")
    require(scopes["ui1c5"]["checks"][:39] == scopes["gri"]["checks"], "UI1c5 scope must preserve GRI check ordering as an unchanged prefix")

    ui1d_required = required - {
        "ui1e_safety", "ui1e_workflow_behavior",
        "w2_boundaries", "w2_submission_behavior"
    }
    require("ui1d" in scopes and set(scopes["ui1d"]["checks"]) == ui1d_required and len(scopes["ui1d"]["checks"]) == 43, "UI1d scope must contain 43 checks")
    require(scopes["ui1d"]["checks"][:41] == scopes["ui1c5"]["checks"], "UI1d must preserve UI1c5 check ordering as prefix")
    require(scopes["ui1d"]["checks"][-2:] == ["ui1d_harper", "ui1d_harper_behavior"], "UI1d dedicated checks must be appended")

    ui1e_required = required - {"w2_boundaries", "w2_submission_behavior"}
    require("ui1e" in scopes and set(scopes["ui1e"]["checks"]) == ui1e_required and len(scopes["ui1e"]["checks"]) == 45, "UI1e scope must contain 45 checks")
    require(scopes["ui1e"]["checks"][:43] == scopes["ui1d"]["checks"], "UI1e must preserve UI1d check ordering as prefix")
    require(scopes["ui1e"]["checks"][-2:] == ["ui1e_safety", "ui1e_workflow_behavior"], "UI1e dedicated checks must be appended")

    require("w2" in scopes, "W2 scope missing from release_gate")
    w2_scope = scopes["w2"]["checks"]
    require(len(w2_scope) == 47, "W2 scope must contain 47 checks")
    require(w2_scope[:45] == scopes["ui1e"]["checks"], "W2 must preserve UI1e check ordering as prefix")
    require(w2_scope[-2:] == ["w2_boundaries", "w2_submission_behavior"], "W2 dedicated checks must be appended")
    require(gate["current_release_scope"] == "w2", "W2 must be the current release scope")

    require(gate.get("artifact_acceptance", {}).get("strict_scope") == "w2", "artifact acceptance must bind W2 scope")
    require(gate["artifact_acceptance"].get("rebuild_after_acceptance") is False and gate["artifact_acceptance"].get("automatic_promotion") is False, "artifact acceptance must forbid rebuild/automatic promotion")
    historical = gate.get("historical_acceptance_records", {})
    require(historical.get("ui1-hybrid") == "PASS=23 SKIP=0 FAIL=0", "historical accepted UI1 hybrid result must remain recorded")
    require(historical.get("ui1d", "").startswith("PASS=43 SKIP=0 FAIL=0"), "historical accepted UI1d result must remain recorded")
    require(historical.get("ui1e", "").startswith("PASS=45 SKIP=0 FAIL=0"), "historical accepted UI1e result must remain recorded")
    private = check_by_id["private_fixture_parity"]
    require(private.get("private") is True and private.get("portable_missing_policy") == "skip" and private.get("strict_missing_policy") == "fail", "private fixture portable/strict policy drifted")
    parity = gate["private_fixture_parity"]
    require((parity["required_fixture_count"], parity["required_field_count"], parity["required_ok"], parity["required_mismatch"], parity["required_unavailable"]) == (14, 275, 269, 6, 0), "private fixture strict baseline drifted")
    require(parity["allowed_mismatches"] == [{"field":"absent","archive_value":"0","edit_value":"true","count":6}], "private mismatch allowlist drifted")
    collision = gate["private_collision_authority"]
    require(collision.get("required_fixture_count") == 2 and set(collision.get("required_labels", [])) == {"duplicate_identical_state", "duplicate_different_state"}, "C3 collision evidence baseline drifted")
    round_trip = gate["private_post_round_trip"]
    require((round_trip.get("required_fixture_count"), round_trip.get("required_final_fixture_count"), round_trip.get("required_absent_source_discrepancy_count")) == (14, 5, 6), "C4 round-trip evidence counts drifted")
    live_rule = gate["live_write_rule"].lower()
    require("no automated release-gate command" in live_rule and "mutate a gel tutorial" in live_rule, "live-write prohibition must be explicit")

def check_component_specs(docgov: dict[str, Any], components: dict[str, Any]) -> None:
    required_sections = docgov["active_spec_required_sections"]
    for c in components["components"]:
        path = DOCS / "components" / f"{c['id']}.md"
        require(path.exists(), f"missing active component spec {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        for section in required_sections:
            require(f"## {section}" in text, f"component spec {path.relative_to(ROOT)} missing section {section!r}")


def check_adrs(docgov: dict[str, Any]) -> None:
    adr_dir = DOCS / "adrs"
    require((adr_dir / "README.md").exists(), "missing docs/adrs/README.md")
    allowed = set(docgov["adr_statuses"])
    status_re = re.compile(r"^\*\*Status:\*\*\s*`?([a-z_]+)`?\s*$", re.MULTILINE)
    for path in sorted(adr_dir.glob("ADR-*.md")):
        if path.name == "ADR_TEMPLATE.md":
            continue
        match = status_re.search(path.read_text(encoding="utf-8"))
        require(match is not None, f"ADR {path.relative_to(ROOT)} missing explicit Status")
        require(match.group(1) in allowed, f"ADR {path.relative_to(ROOT)} has invalid status {match.group(1)!r}")


def check_agent_protocol() -> None:
    proc = subprocess.run(
        [sys.executable, "-S", str(ROOT / "tools" / "check_ai_governance_protocol.py")],
        cwd=ROOT,
        text=True,
    )
    require(proc.returncode == 0, "AI Governance Protocol v1.1 / GEL profile validation failed")


def check_generated() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_governance_artifacts.py"), "--check"],
        cwd=ROOT,
        text=True,
    )
    require(proc.returncode == 0, "generated governance artifacts are stale; run python tools/generate_governance_artifacts.py")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_development_plan_doc.py"), "--check"],
        cwd=ROOT,
        text=True,
    )
    require(proc.returncode == 0, "generated development-plan document is stale")
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "generate_dependency_lock_manifest.py"), "--check"], cwd=ROOT, text=True)
    require(proc.returncode == 0, "generated dependency-lock manifest is stale")
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "generate_current_state.py"), "--check"], cwd=ROOT, text=True)
    require(proc.returncode == 0, "generated current-state projection is stale")


def main() -> int:
    try:
        docgov = load("documentation")
        components = load("components")
        ownership = load("ownership")
        gate = load("gate")
        check_documentation_contract(docgov)
        check_ownership(ownership)
        check_components(components, ownership)
        check_release_gate(gate)
        check_component_specs(docgov, components)
        check_adrs(docgov)
        check_agent_protocol()
        check_generated()
    except GovernanceError as exc:
        print(f"check:governance FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:governance PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
