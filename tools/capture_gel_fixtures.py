#!/usr/bin/env python3
"""Capture the GEL edit-form and reconciliation fixture bundle for Rust parity.

The capture set is intentionally PRIVATE. Raw Learn2 HTML may contain student,
teacher, tutorial, or comment data. The output directory contains a .gitignore
that ignores everything except the documentation marker.

Requirements:
  - tutorial_down4_resilient_v4_9_summary_blank_fidelity_no_email.py
  - the v4.9-refreshed SQLite database (e.g. gel-new.db)
  - BeautifulSoup (already required by the archiver)

Example:
  python tools/capture_gel_fixtures.py \
      --archiver tutorial_down4_resilient_v4_9_summary_blank_fidelity_no_email.py \
      --db gel-new.db \
      --out fixtures-private
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class EditFixtureSpec:
    label: str
    tutorial_id: int
    uid: int
    timestamp: int
    ttype: str
    purpose: str


EDIT_FIXTURES = [
    # Standard (ttype 0)
    EditFixtureSpec(
        "standard_full_mixed", 154306, 464954, 1781609897, "0",
        "Complete mixed Good/OK Standard assessment; historical teacher-id case.",
    ),
    EditFixtureSpec(
        "standard_missing_pronunciation", 151708, 464952, 1771317589, "0",
        "Six Standard assessment values populated; pronunciation genuinely blank.",
    ),
    EditFixtureSpec(
        "standard_assessment_blank", 151775, 464951, 1771504425, "0",
        "All seven Standard self-assessment values genuinely blank.",
    ),
    EditFixtureSpec(
        "standard_absent", 153538, 464951, 1778572680, "0",
        "Absent Standard tutorial while prior assessment state remains populated.",
    ),
    EditFixtureSpec(
        "standard_all_needs_more", 156707, 467678, 1785413990, "0",
        "All seven Standard assessment values are Needs more work.",
    ),
    EditFixtureSpec(
        "standard_full_good_ok", 156126, 464954, 1784560734, "0",
        "Complete Good/OK Standard assessment; proven inline historical tid mechanism.",
    ),

    # Initial (ttype 2)
    EditFixtureSpec(
        "initial_francesca_default", 151582, 464954, 1770716086, "2",
        "Initial form with source defaults and Francesca as historical teacher.",
    ),
    EditFixtureSpec(
        "initial_damian_default", 151705, 464954, 1771317408, "2",
        "Initial form with source defaults and Damian as historical teacher.",
    ),
    EditFixtureSpec(
        "initial_other_student", 152683, 464962, 1774946547, "2",
        "Initial form for another UID; guards against parser specialization to one student.",
    ),

    # Final (ttype 1). These are deliberately non-collision examples.
    EditFixtureSpec(
        "final_full_progress", 156904, 467678, 1785772326, "1",
        "Full Final with substantial initial-to-final score changes and long comment.",
    ),
    EditFixtureSpec(
        "final_absent_progress", 156928, 464952, 1785928657, "1",
        "Absent Final with substantial initial-to-final changes; Matt teacher-id case.",
    ),
    EditFixtureSpec(
        "final_full_progress_other", 156905, 464953, 1785772422, "1",
        "Non-absent Final with long comment and mixed level progression.",
    ),
    EditFixtureSpec(
        "final_regular_matt", 156930, 464955, 1785930857, "1",
        "Non-absent Final with Matt as historical teacher and lower-level progression.",
    ),
    EditFixtureSpec(
        "final_reading_none", 151950, 464953, 1771851958, "1",
        "Older Final where archived Reading is represented as none.",
    ),
]


COLLISION_SPECS = [
    {
        "label": "duplicate_identical_state",
        "uid": 464982,
        "timestamp": 1786523673,
        "ttype": "0",
        "api_ids": [157269, 157270, 157271],
        "expected_distinct_summary_states": 1,
        "purpose": "Three canonical API IDs share one timestamp and identical complete summary state.",
    },
    {
        "label": "duplicate_different_state",
        "uid": 464951,
        "timestamp": 1771504395,
        "ttype": "1",
        "api_ids": [151774, 156932],
        "expected_distinct_summary_states": 2,
        "purpose": "Two canonical IDs share one timestamp but summary states differ: present vs absent. Timestamp edit/print route resolves absent.",
    },
]


def load_archiver(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location("gel_archiver_v49", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load archiver module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def form_inventory(html: str) -> dict[str, Any]:
    """Capture raw control structure without pretending JS has already executed."""
    soup = BeautifulSoup(html, "html.parser")
    controls: list[dict[str, Any]] = []

    for node in soup.select("input[name], select[name], textarea[name], [contenteditable][name]"):
        item: dict[str, Any] = {
            "tag": node.name,
            "name": node.get("name"),
            "id": node.get("id"),
        }
        if node.name == "input":
            item.update({
                "type": node.get("type", "text"),
                "value": node.get("value", ""),
                "checked": node.has_attr("checked"),
            })
        elif node.name == "select":
            item["options"] = [
                {
                    "value": option.get("value", ""),
                    "text": normalize_ws(option.get_text(" ", strip=True)),
                    "selected": option.has_attr("selected"),
                }
                for option in node.find_all("option")
            ]
        elif node.name == "textarea":
            item["value"] = node.get_text("", strip=False)
        elif node.has_attr("contenteditable"):
            item["contenteditable"] = node.get("contenteditable", "")
            # Preserve the visible historical editor state independently from
            # any same-name hidden backing input (notably trecs-79/#tcinput).
            item["value"] = node.get_text("\n", strip=True)
            item["inner_html"] = node.decode_contents()
        controls.append(item)

    inline_scripts = [
        (script.string if script.string is not None else script.get_text("\n", strip=False)) or ""
        for script in soup.find_all("script")
        if not script.get("src")
    ]

    js_value_assignments = []
    value_re = re.compile(
        r'''(?:\$\s*|jQuery\s*)\(\s*["']#(?P<id>[^"']+)["']\s*\)\s*'''
        r'''\.val\s*\(\s*(?P<quote>["'])(?P<value>.*?)(?P=quote)\s*\)''',
        re.IGNORECASE,
    )
    for script_index, script_text in enumerate(inline_scripts):
        for m in value_re.finditer(script_text):
            js_value_assignments.append({
                "script_index": script_index,
                "id": m.group("id"),
                "value": m.group("value"),
                "expression": normalize_ws(m.group(0)),
            })

    return {
        "controls": controls,
        "inline_script_count": len(inline_scripts),
        "js_value_assignments": js_value_assignments,
    }


def db_row(conn: sqlite3.Connection, tutorial_id: int) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tutorials WHERE tutorial_id = ?", (tutorial_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"Tutorial {tutorial_id} is not present in the database")
    result = dict(row)
    raw = result.get("raw_json")
    if isinstance(raw, str) and raw:
        try:
            result["raw_json"] = json.loads(raw)
        except Exception:
            pass
    return result


def selected_normalized_fields(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "tutorial_id", "student_uid", "teacher_id", "teacher_id_source", "teacher_name",
        "tutorial_type", "ttype_raw", "created_at", "created_date", "absent", "custom_date",
        "overall_level", "speaking", "use_of_english", "writing", "listening", "reading",
        "speaking_before", "uoe_before", "writing_before", "listening_before",
        "exam_want", "exam_which", "exam_when",
        "self_listening", "self_reading", "self_writing", "self_speaking",
        "self_vocabulary", "self_grammar", "self_pronunciation",
        "aims", "teacher_comments", "additional_comments",
        "summary_match_method", "reconciliation_status", "reconciliation_key",
        "source_method", "summary_url", "print_url", "edit_url",
    ]
    return {k: row.get(k) for k in keys if k in row}


def parse_edit_route_state(archiver, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    teacher = archiver.parse_teacher_from_edit_html(html)
    absent = soup.select_one('input[name="absent"], input#absent')
    return {
        "absent_control_present": absent is not None,
        "absent_checked": bool(absent and absent.has_attr("checked")),
        "teacher": teacher,
    }


def parse_print_route_state(archiver, html: str) -> dict[str, Any]:
    parsed = archiver.parse_print_page_fallback(html)
    return {
        "absent": parsed.get("absent", ""),
        "teacher_name": parsed.get("teacher_name", ""),
        "custom_date": parsed.get("custom_date", ""),
        "tutorial_type": parsed.get("tutorial_type", ""),
    }


def capture_edit_fixtures(client, archiver, conn: sqlite3.Connection, out: Path) -> list[dict[str, Any]]:
    manifest = []
    raw_dir = out / "raw" / "edit_forms"
    expected_dir = out / "expected" / "edit_forms"
    raw_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    for i, spec in enumerate(EDIT_FIXTURES, start=1):
        print(f"[{i:02d}/{len(EDIT_FIXTURES)}] edit {spec.label}")
        row = db_row(conn, spec.tutorial_id)
        if int(row.get("student_uid") or 0) != spec.uid or int(row.get("created_at") or 0) != spec.timestamp:
            raise RuntimeError(
                f"Fixture {spec.label}: DB identity mismatch. "
                f"Expected uid/timestamp {spec.uid}/{spec.timestamp}; "
                f"got {row.get('student_uid')}/{row.get('created_at')}"
            )

        html = client.get_tutorial_edit_html(spec.uid, spec.timestamp, spec.ttype)
        raw_path = raw_dir / f"{spec.label}.html"
        raw_path.write_text(html, encoding="utf-8")

        inventory = form_inventory(html)
        teacher = archiver.parse_teacher_from_edit_html(html)
        expected = {
            "spec": asdict(spec),
            "normalized_db_reference": selected_normalized_fields(row),
            "teacher_from_edit_form": teacher,
            "route_state": parse_edit_route_state(archiver, html),
            "form_inventory": inventory,
        }
        expected_path = expected_dir / f"{spec.label}.json"
        json_dump(expected_path, expected)

        manifest.append({
            **asdict(spec),
            "raw_html": str(raw_path.relative_to(out)),
            "expected_json": str(expected_path.relative_to(out)),
        })

    return manifest



def capture_print_fixtures(client, archiver, out: Path) -> list[dict[str, Any]]:
    """Capture private A1 print fixtures from the same 14 historical tutorial identities.

    Raw HTML comes from GEL. Expected JSON is produced only by the retained
    Python-v4.9 oracle, so Rust never generates or blesses its own acceptance
    evidence.
    """
    manifest: list[dict[str, Any]] = []
    raw_dir = out / "raw" / "print"
    expected_dir = out / "expected" / "print"
    raw_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    for i, spec in enumerate(EDIT_FIXTURES, start=1):
        print(f"[{i:02d}/{len(EDIT_FIXTURES)}] print {spec.label}")
        html = client.get_tutorial_print_html(spec.uid, spec.timestamp)

        raw_path = raw_dir / f"{spec.label}.html"
        raw_path.write_text(html, encoding="utf-8")

        expected = archiver.parse_print_page_fallback(html)
        if not isinstance(expected, dict):
            raise RuntimeError(
                f"Fixture {spec.label}: Python-v4.9 print oracle returned "
                f"{type(expected).__name__}, expected dict"
            )
        expected_path = expected_dir / f"{spec.label}.json"
        json_dump(expected_path, expected)

        manifest.append({
            **asdict(spec),
            "raw_html": str(raw_path.relative_to(out)),
            "expected_json": str(expected_path.relative_to(out)),
            "oracle": "python-v4.9 parse_print_page_fallback",
        })

    return manifest

def capture_collision_fixture(client, archiver, conn: sqlite3.Connection, out: Path, spec: dict[str, Any]) -> dict[str, Any]:
    label = spec["label"]
    uid = int(spec["uid"])
    ts = int(spec["timestamp"])
    ttype = str(spec["ttype"])

    raw_dir = out / "raw" / "reconciliation" / label
    expected_dir = out / "expected" / "reconciliation"
    raw_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    conn.row_factory = sqlite3.Row
    collision = conn.execute(
        "SELECT * FROM reconciliation_collisions WHERE student_uid=? AND tutorial_ts=?",
        (uid, ts),
    ).fetchone()
    if collision is None:
        raise RuntimeError(f"Missing reconciliation collision {uid}:{ts}")
    collision_dict = dict(collision)
    for key in ("api_tutorial_ids_json", "summary_entries_json"):
        if collision_dict.get(key):
            collision_dict[key] = json.loads(collision_dict[key])

    tutorial_rows = [
        selected_normalized_fields(db_row(conn, int(tid)))
        for tid in spec["api_ids"]
    ]

    api_all = client.get_tutorial_list(uid)
    api_rows = [
        item for item in api_all
        if int(item.get("timestamp") or 0) == ts
    ]
    json_dump(raw_dir / "api_rows.json", api_rows)

    summary_html = client.get_tutorial_summary_html(uid)
    (raw_dir / "summary.html").write_text(summary_html, encoding="utf-8")
    summary_entries = archiver.parse_tutorial_summary(summary_html, uid)
    matching_summary_entries = [
        {
            "datetime_label": e.datetime_label,
            "tutorial_ts": e.tutorial_ts,
            "ttype_raw": e.ttype_raw,
            "ttype_label": e.ttype_label,
            "print_url": e.print_url,
            "edit_url": e.edit_url,
            "fields": e.fields,
        }
        for e in summary_entries
        if int(e.tutorial_ts or 0) == ts
    ]

    unique_states = {
        json.dumps(e["fields"], sort_keys=True, ensure_ascii=False)
        for e in matching_summary_entries
    }

    expected: dict[str, Any] = {
        "spec": spec,
        "collision_db_row": collision_dict,
        "tutorial_rows": tutorial_rows,
        "api_rows_at_timestamp": api_rows,
        "summary_entries_at_timestamp": matching_summary_entries,
        "observed_distinct_summary_states": len(unique_states),
    }

    # The divergent collision is additionally characterized by the timestamp-only
    # routes. Capture them here so the Rust model can keep route state separate
    # from canonical API-id ownership.
    if label == "duplicate_different_state":
        edit_html = client.get_tutorial_edit_html(uid, ts, ttype)
        print_html = client.get_tutorial_print_html(uid, ts)
        (raw_dir / "edit_route.html").write_text(edit_html, encoding="utf-8")
        (raw_dir / "print_route.html").write_text(print_html, encoding="utf-8")
        expected["timestamp_route_state"] = {
            "edit": parse_edit_route_state(archiver, edit_html),
            "print": parse_print_route_state(archiver, print_html),
        }

    if len(unique_states) != int(spec["expected_distinct_summary_states"]):
        raise RuntimeError(
            f"{label}: expected {spec['expected_distinct_summary_states']} distinct summary state(s), "
            f"observed {len(unique_states)}"
        )

    json_dump(expected_dir / f"{label}.json", expected)
    return {
        **spec,
        "raw_dir": str(raw_dir.relative_to(out)),
        "expected_json": str((expected_dir / f"{label}.json").relative_to(out)),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archiver", type=Path, required=True)
    p.add_argument("--db", type=Path)
    p.add_argument("--out", type=Path, default=Path("fixtures-private"))
    p.add_argument("--delay", type=float, default=None)
    p.add_argument(
        "--scope",
        choices=("all", "print"),
        default="all",
        help=(
            "all captures edit forms, private print pages, and reconciliation; "
            "print captures only the 14 private A1 print fixtures and does not require --db"
        ),
    )
    args = p.parse_args()

    if args.scope == "all" and args.db is None:
        p.error("--db is required when --scope=all")

    archiver = load_archiver(args.archiver.resolve())
    conn = sqlite3.connect(args.db.resolve()) if args.db is not None else None

    delay = args.delay if args.delay is not None else getattr(archiver, "DEFAULT_DELAY", 0.3)
    username, password = archiver.get_credentials()
    client = archiver.GELArchiverClient(delay=delay)

    print("Logging in...")
    if not client.login(username, password):
        raise SystemExit("Login failed")
    print("✓ Logged in")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / ".gitignore").write_text("*\n!.gitignore\n!README.md\n", encoding="utf-8")
    (out / "README.md").write_text(
        "# Private GEL fixtures\n\n"
        "Raw files in this directory may contain student, teacher, tutorial and comment data. "
        "Do not commit or redistribute them. The `.gitignore` intentionally ignores all captures.\n",
        encoding="utf-8",
    )

    print_manifest = capture_print_fixtures(client, archiver, out)

    if args.scope == "print":
        manifest = {
            "archiver_reference": args.archiver.name,
            "capture_scope": "print",
            "print_fixture_count": len(print_manifest),
            "print_fixtures": print_manifest,
        }
        json_dump(out / "print-manifest.json", manifest)
        print("\nPrivate print capture complete")
        print(f"  print pages:      {len(print_manifest)}")
        print(f"  output:           {out}")
        print("\nKeep this directory private; it is ignored by Git by design.")
        return 0

    assert conn is not None
    edit_manifest = capture_edit_fixtures(client, archiver, conn, out)
    collision_manifest = []
    for spec in COLLISION_SPECS:
        print(f"collision {spec['label']}")
        collision_manifest.append(capture_collision_fixture(client, archiver, conn, out, spec))

    manifest = {
        "archiver_reference": args.archiver.name,
        "database_reference": args.db.name,
        "capture_scope": "all",
        "edit_fixture_count": len(edit_manifest),
        "edit_fixtures": edit_manifest,
        "print_fixture_count": len(print_manifest),
        "print_fixtures": print_manifest,
        "reconciliation_fixture_count": len(collision_manifest),
        "reconciliation_fixtures": collision_manifest,
    }
    json_dump(out / "manifest.json", manifest)

    print("\nCapture complete")
    print(f"  edit forms:       {len(edit_manifest)}")
    print(f"  print pages:      {len(print_manifest)}")
    print(f"  reconciliation:   {len(collision_manifest)}")
    print(f"  output:           {out}")
    print("\nKeep this directory private; it is ignored by Git by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
