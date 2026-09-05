#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CheckError(Exception):
    pass

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise CheckError(msg)

def read(rel: str) -> str:
    path = ROOT / rel
    require(path.is_file(), f"missing {rel}")
    return path.read_text(encoding="utf-8")

def main() -> int:
    try:
        contract = json.loads(read("contracts/ui1c_semantic_forms.json"))
        for stage in ["ui1c2_standard", "ui1c3_initial", "ui1c4_final"]:
            item = contract.get(stage, {})
            require(item.get("status") == "implemented_prerequisite_satisfied_pending_ui1c5_strict_acceptance", f"{stage} status drifted")
            require(item.get("runtime_authority_change") is False, f"{stage} must not change runtime authority")
            require(item.get("react_domain_authority") is False, f"{stage} must keep React presentation-only")

        types = read("writer-ui/src/types.ts")
        type_fields = read("writer-ui/src/components/TutorialTypeFields.tsx")
        panel = read("writer-ui/src/components/DraftFoundationPanel.tsx")
        # A+D hybrid New-type ownership: the semantic editor must not duplicate
        # New Standard / Initial / Final controls owned by selected-student browse context.
        for forbidden in ["newType", "onNewTypeChange", "onOpenNew", 'option value="standard"', 'option value="initial"', 'option value="final"']:
            require(forbidden not in panel, f"A+D hybrid New-type ownership regressed: {forbidden}")

        control = read("writer-ui/src/components/SemanticFieldControl.tsx")
        api = read("writer-ui/src/api.ts")

        expected_fields = {
            "tutorial_date", "overall_level", "teacher_read_only", "absent",
            "initial_speaking", "initial_use_of_english", "initial_writing", "initial_listening",
            "current_speaking", "current_use_of_english", "current_writing", "current_listening", "reading",
            "assessment_listening", "assessment_reading", "assessment_writing", "assessment_speaking",
            "assessment_vocabulary", "assessment_grammar", "assessment_pronunciation",
            "aims", "teacher_comments", "additional_comments", "initial_course_type",
            "exam_intent", "exam_type", "exam_when",
        }
        require("export type TutorialSemanticField" in types, "frontend semantic field type must be explicit")
        field_decl = re.search(r'export type TutorialSemanticField\s*=\s*(.*?);', types, re.S)
        require(field_decl is not None, "TutorialSemanticField declaration not found")
        declared = set(re.findall(r'"([a-z0-9_]+)"', field_decl.group(1)))
        require(declared == expected_fields, f"TutorialSemanticField drifted: missing={sorted(expected_fields-declared)} extra={sorted(declared-expected_fields)}")

        # UI1c2 Standard: current four + Reading + seven assessments + direct Aims.
        for token in [
            'data-tutorial-form="standard"', 'field="current_speaking"', 'field="current_use_of_english"',
            'field="current_writing"', 'field="current_listening"', 'field="reading"',
            'field="assessment_listening"', 'field="assessment_reading"', 'field="assessment_writing"',
            'field="assessment_speaking"', 'field="assessment_vocabulary"', 'field="assessment_grammar"',
            'field="assessment_pronunciation"', 'field="aims"', 'kind: "set_aims"',
            'draft.formContract.assessmentOptions', 'draft.formContract.levelOptions',
        ]:
            require(token in type_fields, f"Standard form missing {token}")
        require("aimsAssistance.items" not in type_fields, "UI1c2 must not invent/render Aims presets without a curated active source")

        # UI1c3 Initial: Initial four + explicit course type adapter only.
        for token in [
            'data-tutorial-form="initial"', 'field="initial_speaking"', 'field="initial_use_of_english"',
            'field="initial_writing"', 'field="initial_listening"', 'field="initial_course_type"',
            'draft.formContract.initialCourseTypeOptions', 'courseType?.value',
            'courseType?.status === "unrecognized_preserved"', 'kind: "set_initial_course_type"',
        ]:
            require(token in type_fields, f"Initial form missing {token}")
        require("initialCourseType.raw" not in type_fields, "React must not inspect raw Initial teacher-comment storage")

        # UI1c4 Final: paired Initial/current four + Reading + Additional Comments.
        for token in [
            'data-tutorial-form="final"', '<h4>Initial</h4>', '<h4>Final</h4>',
            'field="additional_comments"', 'draft.formContract.additionalCommentsMaxChars',
            'kind: "set_additional_comments"',
        ]:
            require(token in type_fields, f"Final form missing {token}")
        for field in ["initial_speaking", "initial_use_of_english", "initial_writing", "initial_listening", "current_speaking", "current_use_of_english", "current_writing", "current_listening"]:
            require(type_fields.count(f'field="{field}"') >= 1, f"Final paired field missing {field}")

        # Common framework remains disposition-aware and carries structured issues.
        require('rule.disposition === "inapplicable"' in control and 'rule.disposition === "hidden_preserved"' in control, "generic controls must hide non-renderable dispositions")
        require("maxLength?: number" in control and "maxLength == null" in control, "textarea framework must support unbounded Rust-governed fields such as Aims without inventing a limit")
        require("TutorialTypeFields" in panel and "FinalAdditionalCommentsField" in panel, "Draft panel must compose type-specific UI1c2-c4 controls")
        require("draft.formContract.teacherCommentsMaxChars" in panel, "teacher comment limit must remain Rust-projected")
        require("970" not in panel and "970" not in type_fields, "frontend must not hard-code governed comment limits")

        # Canonical option domains remain Rust-owned.
        for forbidden in ["A1", "A2", "B1", "B2", "C1", "C2", "needs_work", "good_for_this_level", "HSP", "G21", "G15"]:
            require(forbidden not in type_fields, f"frontend must not embed canonical domain literal {forbidden}")

        # No new network/write command surface.
        for forbidden in ["submit_tutorial", "post_tutorial", "create_tutorial", "revise_tutorial", "delete_tutorial", "archive_write", "set_teacher", "raw_field"]:
            require(forbidden not in api.lower(), f"UI1c2-c4 must not add forbidden API capability {forbidden}")
    except (CheckError, OSError, json.JSONDecodeError) as exc:
        print(f"check:ui1c2-4-semantic-forms FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:ui1c2-4-semantic-forms PASS — complete Standard/Initial/Final presentation over Rust-owned rules/domains; A+D New-type ownership preserved; no new write authority")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
