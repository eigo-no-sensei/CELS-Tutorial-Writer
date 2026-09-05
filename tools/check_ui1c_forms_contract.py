#!/usr/bin/env python3
"""UI1c0 executable semantic-form contract closure check."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "ui1c_semantic_forms.json"
AIMS = ROOT / "contracts" / "ui1c_aims_assistance.json"
SEMANTIC = ROOT / "gel-core" / "src" / "semantic.rs"
TAURI = ROOT / "writer-ui" / "src-tauri" / "src" / "lib.rs"

EXPECTED_FIELDS = {
    "tutorial_date", "overall_level", "teacher_read_only", "absent",
    "initial_speaking", "initial_use_of_english", "initial_writing", "initial_listening",
    "current_speaking", "current_use_of_english", "current_writing", "current_listening", "reading",
    "assessment_listening", "assessment_reading", "assessment_writing", "assessment_speaking",
    "assessment_vocabulary", "assessment_grammar", "assessment_pronunciation", "aims",
    "teacher_comments", "additional_comments", "initial_course_type", "exam_intent", "exam_type", "exam_when",
}
EXPECTED_CODES = {
    "INVALID_DATE", "INVALID_OPTION", "FIELD_NOT_APPLICABLE", "TEXT_TOO_LONG",
    "LEVEL_REGRESSION", "INVARIANT_VIOLATION", "NO_ACTIVE_DRAFT", "INTERNAL_STATE_ERROR",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def enum_variants(source: str, enum_name: str) -> list[str]:
    match = re.search(rf"pub enum {re.escape(enum_name)}\s*\{{(.*?)\n\}}", source, re.S)
    require(match is not None, f"missing Rust enum {enum_name}")
    body = match.group(1)
    return re.findall(r"^\s*(?:#\[[^\]]+\]\s*)*([A-Z][A-Za-z0-9_]*)\s*(?:\{{|,)", body, re.M)


def main() -> int:
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        aims = json.loads(AIMS.read_text(encoding="utf-8"))
        semantic = SEMANTIC.read_text(encoding="utf-8")
        tauri = TAURI.read_text(encoding="utf-8")

        require(contract["contract_id"] == "ui1c_semantic_forms", "UI1c contract id drifted")
        require(contract["contract_version"] == 4, "UI1c contract version drifted")
        require(contract["status"] == "active_ui1c5_pending_strict_acceptance", "UI1c status drifted")
        require(contract["prerequisite"]["accepted_result"] == "PASS=23 SKIP=0 FAIL=0", "UI1c0 prerequisite acceptance drifted")
        require(contract["ownership"]["semantic_writer"] == "rust_semantic_form", "semantic writer drifted")
        require(contract["ownership"]["react_role"] == "presentation_only", "React authority drifted")
        require(contract["ownership"]["gel_write_authority"] is False, "UI1c0 must not grant GEL write authority")

        dispositions = contract["field_dispositions"]
        require(set(dispositions["fields"]) == EXPECTED_FIELDS, "UI1c field set drifted")
        require(set(dispositions["values"]) == {"editable", "read_only", "hidden_preserved", "inapplicable"}, "field disposition domain drifted")
        for tutorial_type, matrix in dispositions["matrix"].items():
            flattened = matrix["editable"] + matrix["read_only"] + matrix["hidden_preserved"] + matrix["inapplicable"]
            require(len(flattened) == len(set(flattened)), f"{tutorial_type} matrix duplicates fields")
            require(set(flattened) == EXPECTED_FIELDS, f"{tutorial_type} matrix must classify every UI1c field exactly once")
        require("exam_intent" in dispositions["matrix"]["initial"]["hidden_preserved"], "Initial exam intent must be hidden-preserved")
        require("teacher_comments" in dispositions["matrix"]["initial"]["hidden_preserved"], "Initial teacher_comments storage must be hidden-preserved")
        require("initial_course_type" in dispositions["matrix"]["initial"]["editable"], "Initial course type must be editable")

        require(contract["option_domains"]["initial_course_type"]["options"] == ["HSP", "G21", "G15"], "Initial course-type domain drifted")
        assessment = contract["option_domains"]["assessment"]["options"]
        require([x["value"] for x in assessment] == ["needs_work", "ok", "good_for_this_level"], "assessment UI values drifted")
        require([x["label"] for x in assessment] == ["Needs work", "OK for the current level", "Good for this level"], "assessment labels drifted")
        require(contract["option_domains"]["exam"]["rendered_options"] is False, "UI1c0 must not render exam option domain")

        require(aims["contract_id"] == "ui1c_aims_assistance" and aims["contract_version"] == 1, "Aims assistance contract drifted")
        require(aims["status"] == "absent_not_curated" and aims["available"] is False and aims["items"] == [], "Aims presets must remain explicitly absent until curated")

        rust_fields = {camel_to_snake(v) for v in enum_variants(semantic, "TutorialSemanticField")}
        require(rust_fields == EXPECTED_FIELDS, f"Rust TutorialSemanticField differs from contract: {sorted(rust_fields ^ EXPECTED_FIELDS)}")
        require(set(camel_to_snake(v) for v in enum_variants(semantic, "FieldDisposition")) == {"editable", "read_only", "hidden_preserved", "inapplicable"}, "Rust FieldDisposition drifted")
        require(set(enum_variants(semantic, "DraftValidationCode")) == {"InvalidDate", "InvalidOption", "FieldNotApplicable", "TextTooLong", "LevelRegression", "InvariantViolation", "NoActiveDraft", "InternalStateError"}, "Rust DraftValidationCode drifted")
        require(set(contract["validation_issue"]["stable_codes"]) == EXPECTED_CODES, "structured validation code contract drifted")
        require('#[serde(rename_all = "camelCase")]\npub struct DraftValidationIssue' in semantic, "DraftValidationIssue must serialize stable camelCase fields")
        for field in ["code", "field", "severity", "message", "prior_value", "candidate_value"]:
            require(re.search(rf"pub {field}: ", semantic) is not None, f"DraftValidationIssue missing {field}")

        for token in ['#[serde(rename = "HSP")]', '#[serde(rename = "G21")]', '#[serde(rename = "G15")]', 'pub fn initial_course_type_state', 'UnrecognizedPreserved { raw: String }']:
            require(token in semantic, f"InitialCourseType adapter missing {token}")
        require("SetInitialCourseType" in semantic, "typed edit surface missing Initial course-type edit")
        edit_body = re.search(r"pub enum TutorialDraftEdit\s*\{(.*?)\n\}", semantic, re.S).group(1)
        require("SetExamField" not in edit_body, "hidden Initial exam fields must have no UI1c typed edit")
        require("level_regression_baseline: LevelRegressionBaseline" in semantic, "New origin regression baseline missing")
        require("DraftValidationCode::LevelRegression" in semantic, "structured LEVEL_REGRESSION implementation missing")
        require("source.identity.tutorial_type,\n        TutorialType::Initial | TutorialType::Final" in semantic, "initial-role baseline source rule missing")
        require("source.identity.tutorial_type,\n        TutorialType::Standard | TutorialType::Final" in semantic, "current-role baseline source rule missing")

        for token in ["DraftFormContractView", "initial_course_type_options", "assessment_options", "initial_course_type_state", "DraftValidationIssue"]:
            require(token in tauri, f"Tauri safe UI1c projection missing {token}")
        require("available: false" in tauri and "items: Vec::new()" in tauri, "Tauri must project Aims assistance as unavailable/empty")

        print("check:ui1c-forms-contract PASS — field matrix + Rust option domains + InitialCourseType lossless adapter + structured validation + absent Aims hotlist + same-role New regression")
        return 0
    except (AssertionError, json.JSONDecodeError, AttributeError) as exc:
        print(f"check:ui1c-forms-contract FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
