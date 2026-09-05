#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def _resolve_root() -> Path:
    candidates: list[Path] = []
    env = os.environ.get("GEL_PROJECT_ROOT", "").strip()
    if env:
        candidates.append(Path(env).expanduser().resolve())
    candidates.append(Path.cwd().resolve())
    try:
        candidates.append(Path(__file__).resolve().parents[1])
    except IndexError:
        pass
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "contracts" / "ui1c_semantic_forms.json").is_file():
            return candidate
    raise RuntimeError(
        "GEL project root not found; run this checker from the project root "
        "or set GEL_PROJECT_ROOT=/path/to/gel-rust-bootstrap"
    )


ROOT = _resolve_root()

class CheckError(Exception):
    pass

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise CheckError(msg)

def read(rel: str) -> str:
    p = ROOT / rel
    require(p.is_file(), f"missing {rel}")
    return p.read_text(encoding="utf-8")

def main() -> int:
    try:
        contract = json.loads(read("contracts/ui1c_semantic_forms.json"))
        framework = contract.get("ui1c1_editor_framework", {})
        require(framework.get("status") == "implemented_prerequisite_satisfied_pending_ui1c5_strict_acceptance", "UI1c1 contract status drifted")
        require(framework.get("runtime_authority_change") is False, "UI1c1 must not change runtime authority")
        require(framework.get("react_domain_authority") is False, "React must not gain semantic/domain authority")
        require(framework.get("foundation_surface") == ["tutorial_date", "overall_level", "teacher_read_only", "absent", "teacher_comments"], "UI1c1 foundation surface drifted")
        require(set(framework.get("generic_controls", [])) == {"date", "select", "checkbox", "textarea", "read_only"}, "UI1c1 generic control set drifted")
        require(set(framework.get("deferred_to_later_stages", [])) >= {"initial_course_type", "initial_levels", "current_levels", "reading", "assessments", "aims", "additional_comments"}, "UI1c1 must defer type-complete sections")

        component = read("writer-ui/src/components/SemanticFieldControl.tsx")
        panel = read("writer-ui/src/components/DraftFoundationPanel.tsx")
        app = read("writer-ui/src/App.tsx")
        types = read("writer-ui/src/types.ts")

        for token in ["DraftFieldRuleView", "DraftOptionView", "DraftValidationIssue", "hidden_preserved", "inapplicable", "field-validation"]:
            require(token in component, f"SemanticFieldControl missing {token}")
        require("options.map((option)" in component and "option.value" in component and "option.label" in component, "select controls must consume projected options")
        require("A1" not in component and "B1" not in component and "HSP" not in component, "generic editor must not embed canonical domains")

        for token in ["SemanticDateField", "SemanticSelectField", "SemanticReadOnlyField", "SemanticCheckboxField", "SemanticTextAreaField", "draft.formContract.levelOptions", "draft.formContract.teacherCommentsMaxChars", 'ruleFor(draft, "absent")', 'ruleFor(draft, "teacher_comments")']:
            require(token in panel, f"DraftFoundationPanel missing UI1c1 framework usage: {token}")
        for forbidden in ["set_initial_level", "set_current_level", "set_reading", "set_assessment", "set_aims", "set_additional_comments", "set_initial_course_type"]:
            require(forbidden not in panel, f"UI1c1 must not render later-stage edit {forbidden}")
        require("970" not in panel, "teacher comment limit must remain Rust-projected")

        require("DraftValidationIssue" in types, "structured validation DTO missing from frontend types")
        require("DraftValidationIssue | null" in app, "App must retain structured validation issue state")
        require("asDraftValidationIssue" in app, "App must recognize structured validation DTO without message parsing")
        require("validationIssue={draftIssue}" in app, "App must pass structured issue to editor framework")
        require("message.includes(" not in app and "message.split(" not in app, "React must not parse validation messages for authority")
    except (CheckError, OSError, json.JSONDecodeError) as exc:
        print(f"check:ui1c1-editor-framework FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:ui1c1-editor-framework PASS — reusable disposition-aware controls + Rust-projected domains + structured issue routing; UI1c1 foundation remains intact")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
