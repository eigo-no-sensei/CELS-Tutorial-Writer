#!/usr/bin/env python3
"""check:n2c-prepopulation — dependency-minimal canonical New prepopulation check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CheckError(Exception):
    pass

def require(ok: bool, message: str) -> None:
    if not ok:
        raise CheckError(message)

def load(name: str) -> dict:
    return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))

def main() -> int:
    try:
        n2c = load("new_tutorial_prepopulation.json")
        n2a = load("n2a_semantic_post_authority.json")
        new_form = load("new_tutorial_form.json")
        gate = load("release_gate.json")
        components = load("component_boundaries.json")
        ownership = load("state_ownership.json")
        plan = json.loads((ROOT / "development_plan.json").read_text(encoding="utf-8"))

        require(n2c.get("contract_id") == "new_tutorial_prepopulation", "bad N2c contract id")
        require(n2c.get("contract_version") == 2 and n2c.get("status") == "active", "N2c contract must be active v2")
        require(n2c["evaluation"]["status"] == "approved_with_amendment", "N2c plan evaluation must be recorded before implementation")
        require(n2c["source_authority"]["prepopulation_source"] == "latest_tutorial_when_present", "latest tutorial source authority drifted")
        require("validated New-form defaults" in n2c["source_authority"]["first_ever"], "first-ever New must use validated form defaults")
        require(n2c["global_rules"]["source_timestamp"] == "absent for New", "New timestamp rule drifted")
        require(n2c["global_rules"]["teacher"] == "always use immutable validated New-form teacher", "New teacher authority drifted")
        require("same canonical Initial field" in n2c["level_projection"]["initial_target_role"], "Initial role projection must stay canonical-role-only")
        require("same canonical current field" in n2c["level_projection"]["current_target_role"], "current role projection must stay canonical-role-only")
        require("cross-role promotion" in n2c["level_projection"]["forbidden"], "Initial/current cross-role inference must be forbidden")
        require(n2c["canonical_level_fields"]["initial"] == {"264": "initial_speaking", "265": "initial_use_of_english", "266": "initial_writing", "267": "initial_listening"}, "Initial canonical field mapping drifted")
        require(n2c["canonical_level_fields"]["current"] == {"233": "speaking", "234": "use_of_english", "235": "writing", "236": "listening", "476": "reading"}, "current canonical field mapping drifted")
        require("changed-teacher" in " ".join(n2c["deferred_non_blocking"]), "teacher reassignment residual must remain deferred")

        require(n2a["origin_authority"]["new"]["datetime_post"] == "absent_key", "N2c must preserve N2a New datetime omission")
        require(new_form["teacher_authority"]["public_mutation"] is False, "N2c must preserve N2b teacher immutability")

        sem = (ROOT / "gel-core/src/semantic.rs").read_text(encoding="utf-8")
        parser = (ROOT / "gel-core/src/new_form_parser.rs").read_text(encoding="utf-8")
        tests = (ROOT / "gel-core/tests/new_prepopulation.rs").read_text(encoding="utf-8")
        require("pub fn build_new_form_state" in sem, "N2c New semantic builder missing")
        require("project_initial_scores" in sem and "project_current_scores" in sem, "N2c role projection helpers missing")
        require("TutorialType::Initial | TutorialType::Final" in sem, "Initial-role source applicability guard missing")
        require("TutorialType::Standard | TutorialType::Final" in sem, "current-role source applicability guard missing")
        require("source.current_scores.speaking" not in sem[sem.index("fn project_initial_scores"):sem.index("fn project_current_scores")], "Initial projection must not promote current role")
        current_projection = sem[sem.index("fn project_current_scores"):sem.index("fn new_form_raw")]
        require("source.initial_scores.speaking" not in current_projection, "current projection must not promote Initial role")
        require("latest.and_then(|source| source.reading).or(form_reading)" in sem, "Reading source/default rule missing")
        require("source.self_assessment.clone()" in sem, "Standard self-assessment copy rule missing")
        require("source.exam.clone()" in sem, "Initial exam copy rule missing")
        require("source.additional_comments.clone()" in sem, "Final additional-comments copy rule missing")
        require("source.aims.text.clone()" in sem, "Standard Aims copy rule missing")
        require("tutorial_date: form.default_date()" in sem, "New date must come from validated form default")
        require("form_teacher: form.teacher().clone()" in sem, "New teacher must come from validated form authority")
        require("prepopulation_source: latest.map" in sem, "New origin must retain optional latest source provenance")
        require("pub(crate) fn control_status" in parser, "N2c needs crate-private validated control access")
        require("pub fn control_status" not in parser, "validated raw control access must not become public")
        require("reqwest" not in sem and ".post(" not in sem, "N2c semantic code must remain network-write free")

        for name in [
            "initial_from_standard_keeps_new_form_defaults_for_unavailable_initial_role_fields",
            "standard_from_initial_keeps_new_form_defaults_for_unavailable_current_role_fields",
            "final_from_standard_copies_current_roles_and_keeps_initial_new_form_defaults",
            "final_from_initial_copies_initial_roles_and_keeps_current_new_form_defaults",
            "final_source_preserves_distinct_initial_and_current_roles_without_cross_role_inference",
            "standard_source_preserves_standard_only_assessment_aims_and_provenance",
            "common_fields_copy_latest_but_date_and_teacher_come_from_new_form",
            "first_ever_new_uses_validated_form_defaults_and_invents_no_source",
            "source_student_mismatch_fails_closed",
        ]:
            require(f"fn {name}" in tests, f"missing N2c regression test {name}")

        semantic_component = next(x for x in components["components"] if x["id"] == "rust_semantic_form")
        require(any("N2c" in item for item in semantic_component["scope"]), "semantic component must retain N2c authority in scope")
        require(semantic_component["writes"] == ["semantic_form_state"], "semantic component must remain sole semantic-state writer")
        semantic_state = next(x for x in ownership["state_classes"] if x["id"] == "semantic_form_state")
        require(semantic_state["permitted_writers"] == ["rust_semantic_form"], "N2c must not split semantic-state writer ownership")
        require("N2c" in semantic_state["retention"], "semantic ownership must record N2c projection")

        checks = {x["id"]: x for x in gate["checks"]}
        require(int(gate.get("contract_version", 0)) >= 13, "N2c requires release gate v13 or later")
        require(checks["n2c_prepopulation"]["command"] == ["python", "-S", "tools/check_n2c_prepopulation.py"], "N2c gate command drifted")
        n2c_expected = {"contracts", "governance", "python_compile", "archive_schema_v2", "archive_repository", "gel_session", "n2_playwright_zero_write", "n2a_semantic_post", "n2b_new_form", "n2c_prepopulation", "rust_workspace_fmt", "rust_workspace_clippy", "rust_workspace_tests", "private_fixture_parity", "private_collision_authority", "private_post_round_trip"}
        require("n2c" in gate["scopes"] and set(gate["scopes"]["n2c"]["checks"]) == n2c_expected, "N2c scope must preserve its strictly accepted 16-check baseline")
        require("n2c_prepopulation" not in gate["scopes"]["n2b"]["checks"], "strictly accepted N2b scope must not retroactively depend on N2c")

        phase = next(x for x in plan["phases"] if x["id"] == "N2")
        require(tuple(map(int, plan.get("plan_version", "0.0.0").split("."))) >= (1, 13, 0), "N2c checker requires plan v1.13.0 or later")
        require(phase["status"] in {"n2c_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "N2 phase must be at least N2c implementation state")
        require(phase["n2b"]["status"] == "complete_strictly_accepted", "N2b strict acceptance must be recorded")
        require(phase["n2b"]["strict_result"].startswith("PASS=15 SKIP=0 FAIL=0"), "N2b strict result missing")
        require(phase["n2c"]["status"] in {"implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "N2c subphase status drifted")
        require(phase["n2c"]["network_write_authority"] is False, "N2c must grant no network write")
        if phase["n2c"]["status"] == "complete_strictly_accepted":
            require(phase["n2c"].get("strict_result", "").startswith("PASS=16 SKIP=0 FAIL=0"), "N2c strict result missing")
    except (CheckError, KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"check:n2c-prepopulation FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:n2c-prepopulation PASS — latest-source field projection + validated New-form defaults + same-canonical-role-only mapping")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
