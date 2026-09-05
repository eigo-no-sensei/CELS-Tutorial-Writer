#!/usr/bin/env python3
"""Executable D1 archive-schema v2 creation and legacy-v1 migration support.

This module does not make Rust or the Writer a canonical archive writer. It creates
fresh v2 databases and migrates an explicitly supplied legacy archive into a
separate destination database. The Python v4.9 archiver remains the active
canonical archive writer until the later governed cutover.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "archive_v2.sql"
LATEST_SCHEMA_VERSION = 2

STATE_COLUMNS = [
    "tutorial_type",
    "ttype_raw",
    "teacher_id",
    "teacher_id_source",
    "teacher_name",
    "custom_date",
    "absent",
    "overall_level",
    "speaking",
    "use_of_english",
    "writing",
    "listening",
    "reading",
    "speaking_before",
    "uoe_before",
    "writing_before",
    "listening_before",
    "exam_want",
    "exam_which",
    "exam_when",
    "self_listening",
    "self_reading",
    "self_writing",
    "self_speaking",
    "self_vocabulary",
    "self_grammar",
    "self_pronunciation",
    "aims",
    "teacher_comments",
    "additional_comments",
    "source_method",
    "summary_url",
    "print_url",
    "edit_url",
    "summary_match_method",
]

SUMMARY_LABEL_TO_FIELD = {
    "Teacher": "teacher_name",
    "Tutorial Overall Level": "overall_level",
    "Initial Speaking": "initial_speaking",
    "Speaking": "speaking",
    "Initial Use of English": "initial_use_of_english",
    "Use of English": "use_of_english",
    "Initial Writing": "initial_writing",
    "Writing": "writing",
    "Initial Listening": "initial_listening",
    "Listening": "listening",
    "Reading": "reading",
    "Assessment": "self_assessment",
    "Aims": "aims",
    "Teacher's Comments": "teacher_comments",
    "Additional Comments/Accommodation (under 18s only)": "additional_comments",
    "Do you want to take an English proficiency exam?": "exam_intent",
    "If yes, which exam?": "exam_type",
    "If yes, when do you want to take the exam?": "exam_when",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        conn.close()
        raise RuntimeError("SQLite foreign_keys pragma could not be enabled")
    return conn


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def detect_schema_version(conn: sqlite3.Connection) -> int:
    names = table_names(conn)
    user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if "archive_schema_migrations" in names:
        if user_version != LATEST_SCHEMA_VERSION:
            raise RuntimeError(
                f"archive schema metadata exists but PRAGMA user_version={user_version}, expected {LATEST_SCHEMA_VERSION}"
            )
        return LATEST_SCHEMA_VERSION
    if {"classes", "students", "tutorials"} <= names:
        return 1
    if not names:
        return 0
    raise RuntimeError(f"unrecognized archive schema; tables={sorted(names)} user_version={user_version}")


def apply_fresh_schema(conn: sqlite3.Connection, *, applied_at: str | None = None) -> None:
    if table_names(conn):
        raise RuntimeError("fresh schema creation requires an empty database")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO archive_schema_migrations(version, name, source_version, applied_at) VALUES (?, ?, ?, ?)",
        (LATEST_SCHEMA_VERSION, "fresh_v2", 0, applied_at or utc_now()),
    )
    conn.commit()
    _assert_foreign_keys_clean(conn)


def create_fresh_database(path: Path | str, *, applied_at: str | None = None) -> Path:
    destination = Path(path)
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(destination)
    try:
        apply_fresh_schema(conn, applied_at=applied_at)
    except Exception:
        conn.close()
        destination.unlink(missing_ok=True)
        raise
    conn.close()
    return destination


def _value(row: sqlite3.Row, name: str, default: Any = None) -> Any:
    return row[name] if name in row.keys() else default


def _seen_at(row: sqlite3.Row, fallback: str) -> str:
    value = _value(row, "scraped_at")
    return str(value) if value else fallback


def _normalize_for_fingerprint(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return int(value)
    return value


def legacy_state_fingerprint(row: sqlite3.Row) -> str:
    payload = {
        "student_uid": _value(row, "student_uid"),
        "tutorial_ts": _value(row, "created_at", 0),
    }
    for name in STATE_COLUMNS:
        if name in {"summary_url", "print_url", "edit_url", "source_method", "summary_match_method"}:
            continue
        payload[name] = _normalize_for_fingerprint(_value(row, name))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _insert_field_evidence(
    conn: sqlite3.Connection, source_state_id: int, row: sqlite3.Row
) -> None:
    raw = _value(row, "raw_json")
    if not raw:
        return
    try:
        blob = json.loads(raw)
    except Exception:
        return
    summary = blob.get("summary") if isinstance(blob, dict) else None
    if not isinstance(summary, dict):
        return
    field_keys = summary.get("field_keys") or []
    fields = summary.get("fields") or {}
    if not isinstance(field_keys, list) or not isinstance(fields, dict):
        return
    for label in field_keys:
        field_name = SUMMARY_LABEL_TO_FIELD.get(str(label))
        if not field_name:
            continue
        raw_value = fields.get(label, "")
        presence = "present_blank" if str(raw_value or "").strip() == "" else "present"
        conn.execute(
            """
            INSERT INTO tutorial_source_field_evidence(source_state_id, field_name, source_kind, presence)
            VALUES (?, ?, 'summary', ?)
            ON CONFLICT(source_state_id, field_name, source_kind)
            DO UPDATE SET presence=excluded.presence
            """,
            (source_state_id, field_name, presence),
        )
    if _value(row, "teacher_id") is not None:
        conn.execute(
            """
            INSERT INTO tutorial_source_field_evidence(source_state_id, field_name, source_kind, presence)
            VALUES (?, 'teacher_id', 'edit', 'present')
            ON CONFLICT(source_state_id, field_name, source_kind)
            DO UPDATE SET presence=excluded.presence
            """,
            (source_state_id,),
        )


def _legacy_collision_keys(source: sqlite3.Connection) -> dict[tuple[int, int], set[int]]:
    groups: dict[tuple[int, int], set[int]] = {}
    names = table_names(source)
    if "reconciliation_collisions" in names:
        for row in source.execute("SELECT * FROM reconciliation_collisions"):
            student_uid = int(_value(row, "student_uid", 0) or 0)
            tutorial_ts = int(_value(row, "tutorial_ts", 0) or 0)
            ids: set[int] = set()
            raw_ids = _value(row, "api_tutorial_ids_json", "[]") or "[]"
            try:
                parsed = json.loads(raw_ids)
                ids = {int(value) for value in parsed}
            except Exception:
                ids = set()
            groups[(student_uid, tutorial_ts)] = ids

    duplicate_rows = source.execute(
        """
        SELECT student_uid, created_at, COUNT(*) AS cnt
        FROM tutorials
        WHERE student_uid IS NOT NULL AND created_at IS NOT NULL
        GROUP BY student_uid, created_at
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    for row in duplicate_rows:
        key = (int(row["student_uid"]), int(row["created_at"]))
        ids = {
            int(r["tutorial_id"])
            for r in source.execute(
                "SELECT tutorial_id FROM tutorials WHERE student_uid=? AND created_at=?",
                key,
            )
        }
        groups.setdefault(key, set()).update(ids)
    return groups


def _copy_classes_students_memberships(
    source: sqlite3.Connection, dest: sqlite3.Connection, now: str
) -> None:
    for row in source.execute("SELECT * FROM classes ORDER BY class_id"):
        seen = _seen_at(row, now)
        dest.execute(
            """
            INSERT INTO classes(
                class_id, name, course_code, start_date, end_date, is_active,
                source_present, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(class_id) DO UPDATE SET
                name=excluded.name,
                course_code=excluded.course_code,
                start_date=excluded.start_date,
                end_date=excluded.end_date,
                is_active=excluded.is_active,
                source_present=1,
                last_seen=excluded.last_seen
            """,
            (
                int(row["class_id"]),
                _value(row, "name"),
                _value(row, "course_code"),
                _value(row, "start_date"),
                _value(row, "end_date"),
                int(_value(row, "is_active", 1) or 0),
                seen,
                seen,
            ),
        )

    for row in source.execute("SELECT * FROM students ORDER BY uid"):
        seen = _seen_at(row, now)
        uid = int(row["uid"])
        dest.execute(
            """
            INSERT INTO students(
                uid, name, cefr_level, school_name, start_date, end_date,
                source_present, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                name=excluded.name,
                cefr_level=excluded.cefr_level,
                school_name=excluded.school_name,
                start_date=excluded.start_date,
                end_date=excluded.end_date,
                source_present=1,
                last_seen=excluded.last_seen
            """,
            (
                uid,
                _value(row, "name"),
                _value(row, "cefr_level"),
                _value(row, "school_name"),
                _value(row, "start_date"),
                _value(row, "end_date"),
                seen,
                seen,
            ),
        )
        class_id = _value(row, "class_id")
        if class_id is None:
            continue
        dest.execute(
            """
            INSERT INTO class_memberships(
                class_id, student_uid, attendance, tutorial_late, last_tutorial_ts,
                test_type, last_test_ts, unmarked_exit_test,
                source_present, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(class_id, student_uid) DO UPDATE SET
                attendance=excluded.attendance,
                tutorial_late=excluded.tutorial_late,
                last_tutorial_ts=excluded.last_tutorial_ts,
                test_type=excluded.test_type,
                last_test_ts=excluded.last_test_ts,
                unmarked_exit_test=excluded.unmarked_exit_test,
                source_present=1,
                last_seen=excluded.last_seen
            """,
            (
                int(class_id),
                uid,
                _value(row, "attendance"),
                _value(row, "tutorial_late"),
                _value(row, "last_tutorial_ts"),
                _value(row, "test_type"),
                _value(row, "last_test_ts"),
                _value(row, "unmarked_exit_test"),
                seen,
                seen,
            ),
        )


def _ensure_collision_group(
    dest: sqlite3.Connection,
    key: tuple[int, int],
    now: str,
) -> int:
    student_uid, tutorial_ts = key
    dest.execute(
        """
        INSERT INTO tutorial_collision_groups(
            student_uid, tutorial_ts, collision_kind,
            source_present, first_seen, last_seen
        ) VALUES (?, ?, 'ambiguous_unknown', 1, ?, ?)
        ON CONFLICT(student_uid, tutorial_ts) DO UPDATE SET
            collision_kind='ambiguous_unknown',
            source_present=1,
            last_seen=excluded.last_seen
        """,
        (student_uid, tutorial_ts, now, now),
    )
    row = dest.execute(
        "SELECT collision_group_id FROM tutorial_collision_groups WHERE student_uid=? AND tutorial_ts=?",
        key,
    ).fetchone()
    assert row is not None
    return int(row[0])


def _copy_tutorials(source: sqlite3.Connection, dest: sqlite3.Connection, now: str) -> None:
    collision_keys = _legacy_collision_keys(source)
    collision_ids: dict[tuple[int, int], set[int]] = {key: set(ids) for key, ids in collision_keys.items()}
    group_ids = {key: _ensure_collision_group(dest, key, now) for key in collision_keys}

    for row in source.execute("SELECT * FROM tutorials ORDER BY tutorial_id"):
        tutorial_id = int(row["tutorial_id"])
        student_uid = int(_value(row, "student_uid", 0) or 0)
        tutorial_ts = int(_value(row, "created_at", 0) or 0)
        seen = _seen_at(row, now)
        if student_uid <= 0:
            raise RuntimeError(f"legacy tutorial {tutorial_id} has invalid student_uid={student_uid}")
        if dest.execute("SELECT 1 FROM students WHERE uid=?", (student_uid,)).fetchone() is None:
            raise RuntimeError(
                f"legacy tutorial {tutorial_id} references missing student_uid={student_uid}; migration fails closed"
            )

        dest.execute(
            """
            INSERT INTO tutorial_identities(
                tutorial_id, student_uid, tutorial_ts,
                source_present, first_seen, last_seen
            ) VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(tutorial_id) DO UPDATE SET
                student_uid=excluded.student_uid,
                tutorial_ts=excluded.tutorial_ts,
                source_present=1,
                last_seen=excluded.last_seen
            """,
            (tutorial_id, student_uid, tutorial_ts, seen, seen),
        )

        fingerprint = legacy_state_fingerprint(row)
        values = [_value(row, name) for name in STATE_COLUMNS]
        placeholders = ", ".join("?" for _ in STATE_COLUMNS)
        columns = ", ".join(STATE_COLUMNS)
        updates = ", ".join(f"{name}=excluded.{name}" for name in STATE_COLUMNS)
        dest.execute(
            f"""
            INSERT INTO tutorial_source_states(
                student_uid, tutorial_ts, state_fingerprint, {columns},
                source_present, first_seen, last_seen
            ) VALUES (?, ?, ?, {placeholders}, 1, ?, ?)
            ON CONFLICT(student_uid, tutorial_ts, state_fingerprint) DO UPDATE SET
                {updates},
                source_present=1,
                last_seen=excluded.last_seen
            """,
            (student_uid, tutorial_ts, fingerprint, *values, seen, seen),
        )
        state_row = dest.execute(
            """
            SELECT source_state_id FROM tutorial_source_states
            WHERE student_uid=? AND tutorial_ts=? AND state_fingerprint=?
            """,
            (student_uid, tutorial_ts, fingerprint),
        ).fetchone()
        assert state_row is not None
        source_state_id = int(state_row[0])
        _insert_field_evidence(dest, source_state_id, row)

        key = (student_uid, tutorial_ts)
        reconciliation_status = str(_value(row, "reconciliation_status", "") or "").strip()
        group_id = group_ids.get(key)
        if group_id is not None:
            collision_ids.setdefault(key, set()).add(tutorial_id)
            dest.execute(
                """
                INSERT INTO tutorial_collision_identities(collision_group_id, tutorial_id)
                VALUES (?, ?)
                ON CONFLICT(collision_group_id, tutorial_id) DO NOTHING
                """,
                (group_id, tutorial_id),
            )
            dest.execute(
                """
                INSERT INTO tutorial_collision_states(collision_group_id, source_state_id)
                VALUES (?, ?)
                ON CONFLICT(collision_group_id, source_state_id) DO NOTHING
                """,
                (group_id, source_state_id),
            )
            authority = "ambiguous_collision_unknown"
            authority_state_id = None
            proof_method = "legacy_v1_collision_fail_closed"
        elif reconciliation_status == "matched":
            authority = "proven_per_tutorial"
            authority_state_id = source_state_id
            proof_method = "legacy_v1_unique_matched"
        else:
            authority = "unmatched_source_state"
            authority_state_id = None
            proof_method = "legacy_v1_unproven"

        dest.execute(
            """
            INSERT INTO tutorial_state_associations(
                tutorial_id, authority_status, source_state_id, collision_group_id,
                proof_method, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tutorial_id) DO UPDATE SET
                authority_status=excluded.authority_status,
                source_state_id=excluded.source_state_id,
                collision_group_id=excluded.collision_group_id,
                proof_method=excluded.proof_method,
                last_seen=excluded.last_seen
            """,
            (
                tutorial_id,
                authority,
                authority_state_id,
                group_id,
                proof_method,
                seen,
                seen,
            ),
        )

    # Some legacy collision diagnostics may name identities omitted from the
    # tutorial table. Do not invent them; fail closed because canonical API IDs
    # require a student identity row in v2.
    for key, ids in collision_ids.items():
        missing = [
            tutorial_id
            for tutorial_id in ids
            if dest.execute(
                "SELECT 1 FROM tutorial_identities WHERE tutorial_id=?", (tutorial_id,)
            ).fetchone()
            is None
        ]
        if missing:
            raise RuntimeError(
                f"legacy collision {key[0]}:{key[1]} names tutorial IDs absent from tutorials table: {sorted(missing)}"
            )


def _copy_scrape_log(source: sqlite3.Connection, dest: sqlite3.Connection) -> None:
    if "scrape_log" not in table_names(source):
        return
    for row in source.execute("SELECT action, target, status, message, timestamp FROM scrape_log ORDER BY id"):
        dest.execute(
            "INSERT INTO scrape_log(action, target, status, message, timestamp) VALUES (?, ?, ?, ?, ?)",
            tuple(row),
        )


def _assert_foreign_keys_clean(conn: sqlite3.Connection) -> None:
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"foreign key violations after schema operation: {violations}")


def migrate_legacy_v1_to_v2(
    source_path: Path | str,
    destination_path: Path | str,
    *,
    applied_at: str | None = None,
) -> Path:
    source_path = Path(source_path)
    destination_path = Path(destination_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if destination_path.exists():
        raise FileExistsError(f"destination already exists: {destination_path}")

    source = sqlite3.connect(str(source_path))
    source.row_factory = sqlite3.Row
    try:
        version = detect_schema_version(source)
        if version != 1:
            raise RuntimeError(f"legacy migration requires schema version 1, found {version}")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        dest = connect(destination_path)
        try:
            apply_fresh_schema(dest, applied_at=applied_at)
            now = applied_at or utc_now()
            dest.execute("BEGIN IMMEDIATE")
            # Replace the fresh-schema migration marker with explicit migration provenance.
            dest.execute("DELETE FROM archive_schema_migrations WHERE version=?", (LATEST_SCHEMA_VERSION,))
            _copy_classes_students_memberships(source, dest, now)
            _copy_tutorials(source, dest, now)
            _copy_scrape_log(source, dest)
            dest.execute(
                "INSERT INTO archive_schema_migrations(version, name, source_version, applied_at) VALUES (?, ?, 1, ?)",
                (LATEST_SCHEMA_VERSION, "legacy_v1_to_v2", now),
            )
            _assert_foreign_keys_clean(dest)
            dest.commit()
        except Exception:
            dest.rollback()
            dest.close()
            destination_path.unlink(missing_ok=True)
            raise
        dest.close()
    finally:
        source.close()
    return destination_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or migrate GEL archive schema v2 databases")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="create a fresh v2 database")
    create.add_argument("destination")
    migrate = sub.add_parser("migrate", help="migrate legacy v1 into a separate v2 destination")
    migrate.add_argument("source")
    migrate.add_argument("destination")
    args = parser.parse_args()

    if args.command == "create":
        path = create_fresh_database(args.destination)
        print(f"created archive schema v2: {path}")
        return 0
    path = migrate_legacy_v1_to_v2(args.source, args.destination)
    print(f"migrated legacy archive to schema v2: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
