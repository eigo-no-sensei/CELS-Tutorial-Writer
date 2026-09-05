#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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
        ui1c = load("contracts/ui1c_semantic_forms.json")
        ui1 = load("contracts/ui1_writer.json")
        gate = load("contracts/release_gate.json")
        plan = load("development_plan.json")

        require(ui1c.get("contract_version") == 4, "UI1c5 requires ui1c_semantic_forms v4")
        require(ui1c.get("status") == "active_ui1c5_pending_strict_acceptance", "UI1c5 contract status drifted")
        integrated = ui1c.get("ui1c5_integrated_acceptance", {})
        require(integrated.get("status") == "implemented_pending_strict_acceptance", "UI1c5 integrated status drifted")
        require(integrated.get("runtime_authority_change") is False, "UI1c5 must not change runtime authority")
        require(integrated.get("react_domain_authority") is False, "UI1c5 must keep React presentation-only")
        require(integrated.get("release_scope") == "ui1c5", "UI1c5 release scope drifted")
        require(integrated.get("baseline_accepted_result") == "PASS=39 SKIP=0 FAIL=0", "GRI strict baseline record drifted")
        require(integrated.get("gel_tutorial_write_authority") is False, "UI1c5 must not grant GEL tutorial write authority")
        require(integrated.get("archive_write_change") is False, "UI1c5 must not change archive writer authority")

        require(ui1.get("contract_version") == 14, "UI1 Writer must advance to v14 for W2")
        require(ui1.get("status") in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 Writer W2 status drifted")
        require(ui1.get("ui1c5", {}).get("status") == "complete_strictly_accepted", "UI1 Writer UI1c5 section must be strictly accepted before UI1d")
        require(ui1["architecture"]["react_role"] == "presentation_only", "React authority changed")
        require("ui1_submit_draft" in ui1["architecture"]["submission"] or ui1["architecture"]["submission"] == "absent from UI1 command surface", "UI1c5 submission authority drifted")

        require(gate.get("contract_version") == 25, "W2 requires release_gate v25")
        require(gate.get("current_release_scope") == "w2", "current release scope must be w2")
        require(gate.get("historical_acceptance_records", {}).get("gri") == "PASS=39 SKIP=0 FAIL=0; TARGET STATUS: STRICT_ACCEPTED; RELEASE GATE: PASS", "strict GRI acceptance record missing")
        require(gate.get("artifact_acceptance", {}).get("strict_scope") == "w2", "artifact acceptance must bind w2 strict evidence")
        checks = {item["id"]: item for item in gate.get("checks", [])}
        require(checks.get("ui1c5_integrated", {}).get("command") == ["python", "-S", "tools/check_ui1c5_integrated.py"], "UI1c5 structural check command drifted")
        require(checks.get("ui1c5_integrated_behavior", {}).get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "ui1c5_integrated"], "UI1c5 behavioral check command drifted")
        gri = gate.get("scopes", {}).get("gri", {}).get("checks", [])
        ui1c5_scope = gate.get("scopes", {}).get("ui1c5", {}).get("checks", [])
        require(len(gri) == 39, "accepted GRI baseline must remain 39 checks")
        require(len(ui1c5_scope) == 41, "UI1c5 strict scope must contain 41 checks")
        require(ui1c5_scope[: len(gri)] == gri, "UI1c5 must extend the accepted GRI scope without rewriting it")
        require(ui1c5_scope[-2:] == ["ui1c5_integrated", "ui1c5_integrated_behavior"], "UI1c5 dedicated checks must be appended to GRI baseline")

        ui1_phase = next((phase for phase in plan.get("phases", []) if phase.get("id") == "UI1"), None)
        require(ui1_phase is not None, "UI1 development phase missing")
        require(ui1_phase.get("status") in {"ui1e_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "development plan UI1e status drifted")
        require(ui1_phase.get("gri_strict_acceptance", {}).get("result", "").startswith("PASS=39 SKIP=0 FAIL=0"), "UI1c5 authorization must record strict GRI acceptance")
        require(ui1_phase.get("ui1c5", {}).get("release_scope") == "ui1c5", "development plan UI1c5 scope drifted")
        require(ui1_phase.get("ui1c5", {}).get("status") == "complete_strictly_accepted", "development plan UI1c5 must be strictly accepted before UI1d")
        require(ui1_phase.get("ui1d", {}).get("release_scope") == "ui1d", "development plan UI1d scope drifted")

        test = read("gel-core/tests/ui1c5_integrated.rs")
        required_tests = [
            "new_standard_reconstructs_standard_state_and_all_assessment_edits_are_typed",
            "new_initial_reconstructs_initial_state_and_preserves_hidden_storage",
            "new_final_keeps_initial_and_current_roles_independent",
            "rejected_new_regression_is_structured_and_leaves_prior_state_unchanged",
            "revision_reconstruction_keeps_source_identity_and_teacher_immutable_without_new_regression",
        ]
        for name in required_tests:
            require(re.search(rf"fn\s+{re.escape(name)}\s*\(", test) is not None, f"UI1c5 behavioral test missing {name}")
        for token in [
            "AssessmentSkill::Listening",
            "AssessmentSkill::Reading",
            "AssessmentSkill::Writing",
            "AssessmentSkill::Speaking",
            "AssessmentSkill::Vocabulary",
            "AssessmentSkill::Grammar",
            "AssessmentSkill::Pronunciation",
            "DraftValidationCode::LevelRegression",
            "TutorialSemanticField::InitialSpeaking",
            "InitialCourseTypeState::UnrecognizedPreserved",
            "DraftOrigin::Revision",
            "level_regression_baseline().is_none()",
        ]:
            require(token in test, f"UI1c5 integrated behavior missing {token}")

        app = read("writer-ui/src/App.tsx")
        api = read("writer-ui/src/api.ts").lower()
        require("DraftValidationIssue | null" in app and "validationIssue={draftIssue}" in app, "structured validation must remain routed to the editor")
        require("message.includes(" not in app and "message.split(" not in app, "React must not parse validation text for field authority")
        for forbidden in ["post_tutorial", "create_tutorial", "revise_tutorial", "delete_tutorial", "set_teacher", "raw_post"]:
            require(forbidden not in api, f"UI1c5 introduced forbidden frontend API capability {forbidden}")

    except (CheckError, OSError, json.JSONDecodeError, StopIteration) as exc:
        print(f"check:ui1c5-integrated FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:ui1c5-integrated PASS — strict UI1c5 predecessor bound + cross-form reconstruction/validation/Revision authority coverage + 41-check predecessor scope + no new write authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
