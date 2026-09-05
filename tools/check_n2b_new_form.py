#!/usr/bin/env python3
"""check:n2b-new-form — dependency-minimal N2b acquisition/parser authority check."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


class CheckError(Exception):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise CheckError(message)


def load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def main() -> int:
    try:
        new = load("new_tutorial_form.json")
        fields = load("gel_tutorial_fields.json")
        session = load("gel_read_only_session.json")
        n2a = load("n2a_semantic_post_authority.json")
        components = load("component_boundaries.json")
        ownership = load("state_ownership.json")
        gate = load("release_gate.json")
        plan = json.loads((ROOT / "development_plan.json").read_text(encoding="utf-8"))

        require(new.get("contract_id") == "new_tutorial_form", "bad N2b contract id")
        require(new.get("contract_version") == 1 and new.get("status") == "active", "N2b New-form contract must be active v1")
        require(new.get("network_write_authority") is False, "N2b must grant no network-write authority")
        acquisition = new["acquisition"]
        require(acquisition["method"] == "GET", "New-form acquisition must be GET")
        require(acquisition["path_template"] == "/study/tutorials/add/{student_uid}/0/{ttype_raw}", "New-form acquisition route must use fixed zero locator")
        require(acquisition["fixed_zero_locator_segment"] is True, "New-form route zero locator must be explicit authority")
        require(acquisition["generic_request_api"] is False, "N2b must not create generic transport")
        form = new["form_contract"]
        require(form["method"] == "POST" and form["action_path"] == "/study/tutorials/process", "New source-form structural method/action drifted")
        require(form["forbidden_fields"] == ["datetime"], "datetime must be the explicit forbidden New field")
        require(form["overrides"]["tid"]["control_kind"] == "hidden", "New tid must be hidden")
        require(form["overrides"]["tid"]["validation_rule"] == "positive_i64", "New hidden tid must be positive")
        require(new["teacher_authority"]["production_constructor"] == "new_tutorial_form_parser only", "New teacher production writer drifted")
        require(new["teacher_authority"]["public_mutation"] is False, "New teacher must not be publicly mutable")

        # Canonical source-role projection: all governed editable controls are New-source fields except datetime.
        by_name = {x["semantic_name"]: x for x in fields["fields"]}
        require(fields.get("contract_version") == 4, "N2b requires gel_tutorial_fields v4")
        for name, item in by_name.items():
            roles = set(item.get("source_roles", []))
            if name == "source_timestamp":
                require("new_form" not in roles, "source_timestamp/datetime must not become New source state")
            elif "edit_form" in roles or "edit_form_contenteditable" in roles:
                require("new_form" in roles, f"{name} missing New-form source role")
        require(by_name["teacher_id"].get("gel_name") == "tid", "canonical teacher field drifted")

        # N1 transport remains fixed/read-only and has only the added New GET.
        require(session.get("contract_version") == 2, "N2b requires read-only session contract v2")
        new_read = next((x for x in session["read_surface"] if x["id"] == "new_tutorial_form"), None)
        require(new_read is not None, "fixed New-form read missing")
        require(new_read["method"] == "GET" and new_read["path_template"] == acquisition["path_template"], "session New-form read drifted from N2b contract")
        require(session["network_authority"]["gel_tutorial_write_authority"] is False, "N2b must not grant GEL write transport")
        require(session["network_authority"]["generic_request_api"] is False, "N2b must not weaken N1 generic-request prohibition")

        src = (ROOT / "gel-core/src/new_form_parser.rs").read_text(encoding="utf-8")
        common = (ROOT / "gel-core/src/form_parser_common.rs").read_text(encoding="utf-8")
        edit = (ROOT / "gel-core/src/edit_form_parser.rs").read_text(encoding="utf-8")
        semantic = (ROOT / "gel-core/src/semantic.rs").read_text(encoding="utf-8")
        gel_session = (ROOT / "gel-core/src/gel_session.rs").read_text(encoding="utf-8")
        generated = (ROOT / "gel-core/src/gel_fields.rs").read_text(encoding="utf-8")
        lib = (ROOT / "gel-core/src/lib.rs").read_text(encoding="utf-8")
        tests = (ROOT / "gel-core/tests/new_form.rs").read_text(encoding="utf-8")

        require("pub struct ValidatedNewTutorialForm" in src, "ValidatedNewTutorialForm missing")
        require("pub fn parse_new_tutorial_form" in src, "New-form parser function missing")
        require("NEW_FORBIDDEN_FIELDS" in src and "NEW_CONTROL_SPECS" in src, "New parser must consume generated canonical metadata")
        require("from_validated_hidden_control" in src, "New parser must construct opaque teacher authority")
        require("tutorial_id" not in re.search(r"pub struct ValidatedNewTutorialForm\s*\{(?P<body>.*?)\n\}", src, re.S).group("body"), "Validated New source state must not contain tutorial_id")
        require("tutorial_ts" not in re.search(r"pub struct ValidatedNewTutorialForm\s*\{(?P<body>.*?)\n\}", src, re.S).group("body"), "Validated New source state must not contain tutorial timestamp")
        require("html:" not in re.search(r"pub struct ValidatedNewTutorialForm\s*\{(?P<body>.*?)\n\}", src, re.S).group("body"), "Validated New source state must not retain raw HTML")
        require("reqwest" not in src and "TcpStream" not in src and ".post(" not in src, "New parser must remain network/transport free")
        require("fn value_for_name" not in src and "fn raw_value_for_name" not in src, "N2b must not expose generic raw GEL-field accessors to UI/public callers")
        require("parse_form_controls" in common and "parse_form_controls" in edit and "parse_form_controls" in src, "New and Revision must share lexical parsing without sharing semantic validation")
        require("pub fn validate_edit_form" not in src, "New parser must not replace/relax historical Revision validator")

        require("pub struct ValidatedNewFormTeacher" in semantic, "opaque New teacher type missing")
        teacher_body = re.search(r"pub struct ValidatedNewFormTeacher\s*\{(?P<body>.*?)\n\}", semantic, re.S)
        require(teacher_body is not None, "cannot inspect opaque New teacher")
        require("teacher_id: i64" in teacher_body.group("body") and "pub teacher_id" not in teacher_body.group("body"), "New teacher raw ID must remain private")
        require("pub(crate) fn from_validated_hidden_control" in semantic, "New teacher production constructor must be crate-private")
        require("form_teacher: ValidatedNewFormTeacher" in semantic, "DraftOrigin::New must bind opaque New-form teacher")
        require("form_teacher_id" not in semantic, "legacy arbitrary New teacher integer authority remains")
        require(n2a.get("contract_version") == 3, "N2a authority must be v3 for W2")
        require(n2a["source_vs_derived"]["permitted_writers"]["new_form_source_state"] == "rust_new_tutorial_form_parser only", "N2a/N2b writer authority drifted")

        require("pub const NEW_CONTROL_SPECS" in generated, "generated New control specs missing")
        require("pub const NEW_FORBIDDEN_FIELDS" in generated and "SOURCE_TIMESTAMP" in generated, "generated datetime prohibition missing")
        require('pub const NEW_FORM_ACTION_PATH: &str = "/study/tutorials/process";' in generated, "generated New form action drifted")
        require('pub const NEW_FORM_METHOD: &str = "POST";' in generated, "generated New form method drifted")
        require("GelControlKind::Hidden" in generated, "generated New hidden-control metadata missing")

        require("pub fn get_new_tutorial_form_html" in gel_session, "fixed New-form GelSession read missing")
        require('"/study/tutorials/add/{student_uid}/0/{ttype_raw}"' in gel_session, "New-form route does not use fixed zero locator")
        production_session = gel_session.split("#[cfg(test)]\nmod tests", 1)[0]
        require(production_session.count(".post(") == 2, "N2b must not add a third production POST beyond login")
        require("pub mod new_form_parser;" in lib and "parse_new_tutorial_form" in lib, "N2b parser not exposed through gel-core boundary")

        fixture_dir = ROOT / "gel-core/fixtures/synthetic"
        for fixture in new["fixtures"]["public_sanitized"]:
            path = ROOT / fixture
            require(path.exists(), f"missing sanitized N2b fixture {fixture}")
            text = path.read_text(encoding="utf-8")
            low = text.lower()
            require("datetime" not in low, f"New fixture contains forbidden datetime: {fixture}")
            require("@" not in text and "password" not in low and "cookie" not in low and "token" not in low, f"New fixture contains privacy-sensitive material: {fixture}")
            require("synthetic comment" not in low and "synthetic aim" not in low, f"New fixture must not retain tutorial prose: {fixture}")

        for test_name in [
            "validates_sanitized_standard_initial_and_final_new_forms",
            "new_datetime_presence_is_contract_drift",
            "new_teacher_must_be_one_hidden_positive_control",
            "route_student_and_requested_type_must_match_form",
            "known_inapplicable_control_is_contract_drift",
            "unknown_cefr_option_fails_closed_even_when_not_selected",
            "invalid_customdate_fails_closed",
            "fingerprint_ignores_irrelevant_layout_but_changes_with_source_semantics",
            "validated_new_form_is_the_origin_teacher_authority",
            "first_ever_new_origin_needs_no_prepopulation_source",
        ]:
            require(f"fn {test_name}" in tests, f"missing N2b regression test {test_name}")

        component = next((x for x in components["components"] if x["id"] == "rust_new_tutorial_form_parser"), None)
        require(component is not None and component["status"] == "active_n2b", "N2b parser component spec missing/ inactive")
        require(component["writes"] == ["validated_new_tutorial_form_state"], "N2b parser writer boundary drifted")
        require("live_gel_tutorials" in component["must_not_write"] and "tutorial_post_payload" in component["must_not_write"], "N2b parser must not own GEL/payload writes")
        states = {x["id"]: x for x in ownership["state_classes"]}
        require(states["gel_new_form_html"]["permitted_writers"] == ["rust_gel_session"], "New-form HTML acquisition ownership drifted")
        require(states["validated_new_tutorial_form_state"]["permitted_writers"] == ["rust_new_tutorial_form_parser"], "validated New-form state ownership drifted")

        checks = {x["id"]: x for x in gate["checks"]}
        require(int(gate.get("contract_version", 0)) >= 13, "N2b checker requires release-gate contract v13 or later")
        require(checks["n2b_new_form"]["command"] == ["python", "-S", "tools/check_n2b_new_form.py"], "N2b gate command drifted")
        n2b_expected = {"contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form", "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests", "private_fixture_parity", "private_collision_authority", "private_post_round_trip"}
        require("n2b" in gate["scopes"] and set(gate["scopes"]["n2b"]["checks"]) == n2b_expected, "N2b release scope must preserve its strictly accepted 15-check baseline")
        require("n2b_new_form" not in gate["scopes"]["n2a"]["checks"], "strictly accepted N2a scope must not retroactively depend on N2b")

        phase = next(x for x in plan["phases"] if x["id"] == "N2")
        require(tuple(map(int, plan.get("plan_version", "0.0.0").split("."))) >= (1, 13, 0), "N2b checker requires plan v1.13.0 or later")
        require(phase["status"] in {"n2c_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "N2 phase must be at least N2c implementation state")
        require(phase["n2a"]["status"] == "complete_strictly_accepted", "N2a strict acceptance must be recorded before N2b")
        require(phase["n2a"]["strict_result"].startswith("PASS=14 SKIP=0 FAIL=0"), "N2a strict result not recorded")
        require(phase["n2b"]["status"] == "complete_strictly_accepted", "N2b strict acceptance must be recorded")
        require(phase["n2b"]["network_write_authority"] is False, "N2b plan must grant no network write")
        require(phase["n2b"]["strict_result"].startswith("PASS=15 SKIP=0 FAIL=0"), "N2b strict result must be recorded")

    except (CheckError, KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        print(f"check:n2b-new-form FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:n2b-new-form PASS — fixed GET acquisition + distinct fail-closed NewTutorialForm authority + opaque teacher + datetime prohibition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
