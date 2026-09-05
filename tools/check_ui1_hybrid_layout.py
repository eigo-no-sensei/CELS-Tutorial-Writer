#!/usr/bin/env python3
"""Executable invariants for the selected A+D hybrid Writer layout/read model."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "writer-ui" / "src"
RUST = ROOT / "writer-ui" / "src-tauri" / "src" / "lib.rs"
LAYOUT = ROOT / "contracts" / "ui1_layout_hybrid.json"
APP = UI / "App.tsx"
STUDENT_LIST = UI / "components" / "StudentListPane.tsx"
OVERVIEW = UI / "components" / "StudentOverview.tsx"
CONTEXT = UI / "components" / "WriteContextPane.tsx"
TYPES = UI / "types.ts"
CSS = UI / "styles" / "app.css"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    try:
        for path in [RUST, LAYOUT, APP, STUDENT_LIST, OVERVIEW, CONTEXT, TYPES, CSS]:
            require(path.exists(), f"missing hybrid artifact: {path.relative_to(ROOT)}")
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        require(layout["layout_id"] == "UI1-LAYOUT-AD-HYBRID", "wrong selected hybrid layout")
        require(layout["student_read_model"]["visible_columns"] == ["Student", "Course", "Attendance", "Last tutorial"], "visible student projection drifted")

        rust = RUST.read_text(encoding="utf-8")
        student_struct = re.search(r"struct StudentView\s*\{(.*?)\n\}", rust, re.S)
        require(student_struct is not None, "StudentView DTO missing")
        body = student_struct.group(1)
        for field in ["student_id", "name", "course_start_date", "course_end_date", "attendance", "last_tutorial_date", "last_tutorial_type"]:
            require(re.search(rf"\b{field}\b", body) is not None, f"StudentView missing {field}")
        for forbidden in ["school_name", "tutorial_late", "last_tutorial_ts"]:
            require(re.search(rf"\b{forbidden}\b", body) is None, f"StudentView leaks retired presentation field {forbidden}")
        list_students = re.search(r"fn ui1_list_students\((.*?)\n\}\n\n#\[tauri::command\]", rust, re.S)
        require(list_students is not None, "ui1_list_students body missing")
        list_body = list_students.group(1)
        require("item.student.start_date" in list_body and "item.student.end_date" in list_body, "course dates must project from D2 student source fields")
        require("attendance: item.attendance" in list_body, "attendance must project from D2 membership source")
        require("list_tutorials_for_student(item.student.uid, false)" in list_body and ".into_iter()\n            .next()" in list_body, "last tutorial must derive from canonical newest-first D2 history")
        require("tutorial.custom_date.clone()" in list_body and "tutorial.tutorial_type" in list_body, "last tutorial display must use canonical history date/type")

        types = TYPES.read_text(encoding="utf-8")
        require("courseStartDate" in types and "courseEndDate" in types and "attendance" in types, "frontend safe StudentView projection incomplete")
        require("lastTutorialDate" in types and "lastTutorialType" in types, "frontend latest tutorial projection incomplete")
        require("schoolName" not in types and "tutorialLate" not in types and "lastTutorialTs" not in types, "retired student presentation fields remain in TypeScript DTO")

        list_text = STUDENT_LIST.read_text(encoding="utf-8")
        for header in ['headerName: "Student"', 'headerName: "Course"', 'headerName: "Attendance"', 'headerName: "Last tutorial"']:
            require(header in list_text, f"student grid missing {header}")
        require('headerName: "School"' not in list_text and 'field: "studentId"' not in list_text, "normal student grid must not show School/internal ID")

        overview = OVERVIEW.read_text(encoding="utf-8")
        for action in ["New Standard", "New Initial", "New Final"]:
            require(action in overview, f"selected-student command surface missing {action}")
        require("Recent tutorials" in overview, "selected-student history surface missing")
        for header in ['headerName: "Date"', 'headerName: "Type"', 'headerName: "Level"', 'headerName: "Teacher"']:
            require(header in overview, f"tutorial history missing {header}")
        require('headerName: "Revision"' not in overview and 'field: "revisionAvailable"' not in overview, "routine Revision eligibility column must be absent")
        require("if (event.data) onOpenRevision(event.data)" in overview, "tutorial row must still route Revision attempts through governed authority")

        app = APP.read_text(encoding="utf-8")
        require('className="browse-workspace"' in app and 'className={`write-workspace' in app, "A+D browse/write modes missing")
        require("contextCollapsed" in app and "WriteContextPane" in app, "editor-dominant collapsible student context missing")
        require("NavigationWorkspace" not in app, "legacy stacked navigation workspace must be retired")
        require("if (!tutorial.revisionAvailable)" in app and "Revision unavailable because archive authority is blocked" in app, "exceptional Revision blocks must remain fail-closed and contextual")

        css = CSS.read_text(encoding="utf-8")
        require("grid-template-columns: minmax(440px, 34%) minmax(0, 66%)" in css, "browse 34/66 layout invariant missing")
        require("grid-template-columns: 250px minmax(0, 1fr)" in css, "write editor-dominant layout invariant missing")
        require(".write-workspace.context-collapsed" in css, "write context collapse styling missing")

        all_frontend = "\n".join(path.read_text(encoding="utf-8") for path in UI.rglob("*.ts*") if path.is_file())
        require("schoolName" not in all_frontend and 'headerName: "School"' not in all_frontend, "School leaked into active React UI")
        require(layout.get("contract_version") == 3, "hybrid layout contract must be v3")
        level_rule = layout.get("presentation_rules", {}).get("cefr_level_display", {})
        require("compact canonical codes" in level_rule.get("rule", ""), "compact CEFR display rule missing")
        require("compact_level_display(item.overall_level)" in rust, "tutorial history overall level must be compacted in Rust view-model projection")
        require("CefrLevel::parse(trimmed)" in rust and "map(level_name)" in rust, "compact level projection must use gel-core CEFR authority")
        require("pre-intermediate" not in all_frontend and "upper-intermediate" not in all_frontend, "React must not own verbose GEL level labels")
        require("split(':')" not in all_frontend and 'split(":")' not in all_frontend, "React must not implement CEFR descriptor stripping")
        require("Save Draft" not in all_frontend and "Save &" not in all_frontend, "hybrid must not imply persistent/submission save capability")

        print("check:ui1-hybrid-layout PASS — authoritative Student/Course/Attendance/Last tutorial projection + focused browse + editor-dominant write mode")
        return 0
    except (AssertionError, json.JSONDecodeError) as exc:
        print(f"check:ui1-hybrid-layout FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
