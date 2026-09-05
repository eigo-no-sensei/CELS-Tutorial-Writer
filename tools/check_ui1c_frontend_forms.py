#!/usr/bin/env python3
"""UI1c0 frontend no-authority and safe form-contract projection check."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "writer-ui" / "src"
TYPES = SRC / "types.ts"
PANEL = SRC / "components" / "DraftFoundationPanel.tsx"
APP = SRC / "App.tsx"
TYPE_FIELDS = SRC / "components" / "TutorialTypeFields.tsx"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    try:
        text = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.ts*") if p.is_file())
        types = TYPES.read_text(encoding="utf-8")
        panel = PANEL.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        type_fields = TYPE_FIELDS.read_text(encoding="utf-8")

        require("DraftFormContractView" in types and "formContract: DraftFormContractView" in types, "React DraftView must consume Rust form contract")
        require("fields: DraftFieldRuleView[]" in types, "React DraftFormContractView must match Rust `fields` DTO member")
        require("formContract.fields.find" in panel and "formContract.fields.find" in type_fields, "semantic controls must consume the Rust `fields` disposition projection")
        require("formContract.fieldRules" not in text, "stale fieldRules DTO alias must not reappear")
        require('status: "unset" | "recognized" | "unrecognized_preserved"' in types, "InitialCourseTypeView status DTO shape drifted")
        require('courseType?.status === "unrecognized_preserved"' in type_fields, "Initial course-type preservation UI must consume status, not a stale state alias")
        require("initialCourseType.state" not in text, "stale InitialCourseTypeView state alias must not reappear")
        require('if (value !== null) onEdit({ kind: "set_initial_course_type", value });' in type_fields, "nullable select output must not be sent to the non-null Rust Initial course-type edit")
        require("DraftValidationIssue" in types and "priorValue" in types and "candidateValue" in types, "React structured validation DTO shape missing")
        require("set_initial_course_type" in types, "frontend typed edit shape must allow Rust InitialCourseType adapter")
        require("set_exam_field" not in types, "hidden Initial exam fields must not remain frontend-editable")
        require("draft.formContract.levelOptions" in panel, "CEFR options must be projected by Rust")
        require("draft.formContract.teacherCommentsMaxChars" in panel, "comment limit UX must use Rust-projected contract")
        require('isEditable(draft, "absent")' in panel and 'isEditable(draft, "teacher_comments")' in panel, "current foundation controls must respect Rust field disposition")
        require("\"message\" in error" in app, "structured backend issue message should be consumed without string parsing")

        for forbidden in ["HSP", "G21", "G15", "Needs work", "OK for the current level", "Good for this level", "dropdown-", "trecs-79"]:
            require(forbidden not in text, f"React must not own/hard-code canonical domain/source token: {forbidden}")
        require(re.search(r"const\s+\w*(LEVEL|ASSESSMENT|COURSE_TYPE|AIMS)\w*\s*=\s*\[", text, re.I) is None, "React must not introduce canonical option arrays")
        require("aims preset" not in text.lower() and "hotlist" not in text.lower(), "Aims preset UI must remain absent until curated")

        print("check:ui1c-frontend-forms PASS — React consumes Rust field/options contract, has no exam edit or duplicated CEFR/assessment/course-type/Aims domains")
        return 0
    except AssertionError as exc:
        print(f"check:ui1c-frontend-forms FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
