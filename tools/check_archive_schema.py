#!/usr/bin/env python3
"""D1 executable acceptance checks for archive schema v2."""
from __future__ import annotations

import ast
import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "schema" / "archive_v2.sql"
ARCHIVE_MODULE = ROOT / "python-oracle" / "archive_schema_v2.py"
ORACLE = ROOT / "python-oracle" / "tutorial_down4_resilient_v4_9_summary_blank_fidelity_no_email.py"
FIXED_NOW = "2026-08-25T12:00:00+00:00"


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CheckError("cannot load archive_schema_v2 module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_archive_module():
    return load_module(ARCHIVE_MODULE, "archive_schema_v2")


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def expect_integrity_error(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> None:
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError:
        conn.rollback()
        return
    raise CheckError(f"expected SQLite integrity failure for: {sql}")


def check_fresh_schema(mod) -> None:
    with tempfile.TemporaryDirectory(prefix="gel-d1-fresh-") as td:
        path = Path(td) / "fresh.db"
        mod.create_fresh_database(path, applied_at=FIXED_NOW)
        conn = mod.connect(path)
        try:
            require(mod.detect_schema_version(conn) == 2, "fresh schema version != 2")
            require(conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1, "foreign keys are not enabled")
            require(not conn.execute("PRAGMA foreign_key_check").fetchall(), "fresh schema foreign_key_check failed")
            expected_tables = {
                "archive_schema_migrations",
                "archive_sync_runs",
                "classes",
                "students",
                "class_memberships",
                "tutorial_identities",
                "tutorial_source_states",
                "tutorial_source_field_evidence",
                "tutorial_collision_groups",
                "tutorial_collision_identities",
                "tutorial_collision_states",
                "tutorial_state_associations",
                "scrape_log",
            }
            names = mod.table_names(conn)
            require(expected_tables <= names, f"fresh schema missing tables: {sorted(expected_tables - names)}")
            require("class_id" not in columns(conn, "students"), "v2 students must not contain class_id")
            require("raw_json" not in columns(conn, "tutorial_source_states"), "v2 source states must not store raw_json")
            for table in [
                "classes",
                "students",
                "class_memberships",
                "tutorial_identities",
                "tutorial_source_states",
                "tutorial_collision_groups",
            ]:
                cols = set(columns(conn, table))
                require(
                    {"source_present", "first_seen", "last_seen", "presence_checked_run_id"} <= cols,
                    f"{table} missing source-presence lifecycle/run-guard columns",
                )

            conn.execute(
                "INSERT INTO classes(class_id,name,source_present,first_seen,last_seen) VALUES (1,'A',1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            conn.execute(
                "INSERT INTO classes(class_id,name,source_present,first_seen,last_seen) VALUES (2,'B',1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            conn.execute(
                "INSERT INTO students(uid,name,source_present,first_seen,last_seen) VALUES (10,'Student',1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            conn.execute(
                "INSERT INTO class_memberships(class_id,student_uid,source_present,first_seen,last_seen) VALUES (1,10,1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            conn.execute(
                "INSERT INTO class_memberships(class_id,student_uid,source_present,first_seen,last_seen) VALUES (2,10,1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            require(
                conn.execute("SELECT COUNT(*) FROM class_memberships WHERE student_uid=10").fetchone()[0] == 2,
                "v2 membership relation does not support one student in multiple classes",
            )
            conn.commit()

            expect_integrity_error(
                conn,
                "INSERT INTO class_memberships(class_id,student_uid,source_present,first_seen,last_seen) VALUES (999,10,1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )

            conn.execute(
                "INSERT INTO tutorial_identities(tutorial_id,student_uid,tutorial_ts,source_present,first_seen,last_seen) VALUES (100,10,123,1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            conn.execute(
                "INSERT INTO tutorial_source_states(student_uid,tutorial_ts,state_fingerprint,tutorial_type,source_present,first_seen,last_seen) VALUES (10,123,'fp','Standard',1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            state_id = conn.execute("SELECT source_state_id FROM tutorial_source_states").fetchone()[0]
            conn.execute(
                "INSERT INTO students(uid,name,source_present,first_seen,last_seen) VALUES (11,'Other',1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            conn.execute(
                "INSERT INTO tutorial_source_states(student_uid,tutorial_ts,state_fingerprint,tutorial_type,source_present,first_seen,last_seen) VALUES (11,999,'other','Standard',1,?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            other_state = conn.execute("SELECT source_state_id FROM tutorial_source_states WHERE student_uid=11").fetchone()[0]
            expect_integrity_error(
                conn,
                """
                INSERT INTO tutorial_state_associations(
                    tutorial_id,authority_status,source_state_id,collision_group_id,proof_method,first_seen,last_seen
                ) VALUES (100,'proven_per_tutorial',?,NULL,'bad-cross-key',?,?)
                """,
                (other_state, FIXED_NOW, FIXED_NOW),
            )
            expect_integrity_error(
                conn,
                """
                INSERT INTO tutorial_state_associations(
                    tutorial_id,authority_status,source_state_id,collision_group_id,proof_method,first_seen,last_seen
                ) VALUES (100,'ambiguous_divergent_collision',?,NULL,'bad',?,?)
                """,
                (state_id, FIXED_NOW, FIXED_NOW),
            )
        finally:
            conn.close()


def create_legacy_v1(path: Path) -> str:
    secret = "private.person@example.invalid"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE classes (
            class_id INTEGER PRIMARY KEY, name TEXT, course_code TEXT, start_date TEXT,
            end_date TEXT, is_active INTEGER, scraped_at TEXT
        );
        CREATE TABLE students (
            uid INTEGER PRIMARY KEY, class_id INTEGER, name TEXT, email TEXT,
            cefr_level INTEGER, school_name TEXT, start_date TEXT, end_date TEXT,
            attendance INTEGER, tutorial_late INTEGER, last_tutorial_ts INTEGER,
            test_type TEXT, last_test_ts INTEGER, unmarked_exit_test INTEGER, scraped_at TEXT
        );
        CREATE TABLE tutorials (
            tutorial_id INTEGER PRIMARY KEY, student_uid INTEGER, teacher_id INTEGER,
            teacher_id_source TEXT, teacher_name TEXT, tutorial_type TEXT, ttype_raw TEXT,
            created_at INTEGER, created_date TEXT, absent INTEGER, custom_date TEXT,
            overall_level TEXT, speaking TEXT, use_of_english TEXT, writing TEXT,
            listening TEXT, reading TEXT, speaking_before TEXT, uoe_before TEXT,
            writing_before TEXT, listening_before TEXT, exam_want TEXT, exam_which TEXT,
            exam_when TEXT, self_listening TEXT, self_reading TEXT, self_writing TEXT,
            self_speaking TEXT, self_vocabulary TEXT, self_grammar TEXT,
            self_pronunciation TEXT, aims TEXT, teacher_comments TEXT,
            additional_comments TEXT, source_method TEXT, summary_url TEXT,
            print_url TEXT, edit_url TEXT, summary_match_method TEXT,
            reconciliation_status TEXT, reconciliation_key TEXT, raw_json TEXT, scraped_at TEXT
        );
        CREATE TABLE reconciliation_collisions (
            student_uid INTEGER NOT NULL, tutorial_ts INTEGER NOT NULL,
            api_count INTEGER NOT NULL, summary_count INTEGER NOT NULL,
            api_tutorial_ids_json TEXT NOT NULL, summary_entries_json TEXT NOT NULL,
            mapping_status TEXT NOT NULL, detected_at TEXT NOT NULL,
            PRIMARY KEY(student_uid,tutorial_ts)
        );
        CREATE TABLE scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, target TEXT,
            status TEXT, message TEXT, timestamp TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO classes VALUES (1,'Class A','G21',NULL,NULL,1,?)",
        (FIXED_NOW,),
    )
    conn.execute(
        "INSERT INTO students VALUES (10,1,'Student One',?,5,'School',NULL,NULL,90,0,999,'exit',888,0,?)",
        (secret, FIXED_NOW),
    )

    def tutorial_row(tutorial_id: int, ts: int, speaking: str, status: str, raw_json: str):
        data = {
            "tutorial_id": tutorial_id,
            "student_uid": 10,
            "teacher_id": 9,
            "teacher_id_source": "edit_form_inline_js",
            "teacher_name": "Teacher",
            "tutorial_type": "Standard",
            "ttype_raw": "0",
            "created_at": ts,
            "created_date": "2026-08-01",
            "absent": 0,
            "custom_date": "01-08-2026",
            "overall_level": "B1: intermediate",
            "speaking": speaking,
            "use_of_english": "B1",
            "writing": "B1",
            "listening": "B1",
            "reading": "",
            "speaking_before": None,
            "uoe_before": None,
            "writing_before": None,
            "listening_before": None,
            "exam_want": None,
            "exam_which": None,
            "exam_when": None,
            "self_listening": "OK for the current level",
            "self_reading": "OK for the current level",
            "self_writing": "OK for the current level",
            "self_speaking": "OK for the current level",
            "self_vocabulary": "OK for the current level",
            "self_grammar": "OK for the current level",
            "self_pronunciation": "OK for the current level",
            "aims": "Aim",
            "teacher_comments": "Comment",
            "additional_comments": None,
            "source_method": "summary+print",
            "summary_url": "/summary",
            "print_url": "/print",
            "edit_url": "/edit",
            "summary_match_method": "timestamp_exact",
            "reconciliation_status": status,
            "reconciliation_key": "10:2000" if "collision" in status else "",
            "raw_json": raw_json,
            "scraped_at": FIXED_NOW,
        }
        cols = list(data)
        conn.execute(
            f"INSERT INTO tutorials({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
            [data[c] for c in cols],
        )

    normal_raw = json.dumps(
        {
            "summary": {
                "field_keys": ["Speaking", "Reading", "Teacher's Comments"],
                "fields": {"Speaking": "B1", "Reading": "", "Teacher's Comments": secret},
            }
        }
    )
    tutorial_row(100, 1000, "B1", "matched", normal_raw)
    tutorial_row(200, 2000, "A2", "collision_ambiguous", json.dumps({"secret": secret}))
    tutorial_row(201, 2000, "B1", "collision_ambiguous", json.dumps({"secret": secret}))
    conn.execute(
        "INSERT INTO reconciliation_collisions VALUES (10,2000,2,2,?,?,?,?)",
        (json.dumps([200, 201]), json.dumps([{"state": "A"}, {"state": "B"}]), "ambiguous", FIXED_NOW),
    )
    conn.execute(
        "INSERT INTO scrape_log(action,target,status,message,timestamp) VALUES ('sync','10','ok','done',?)",
        (FIXED_NOW,),
    )
    conn.commit()
    conn.close()
    return secret


def check_legacy_migration(mod) -> None:
    with tempfile.TemporaryDirectory(prefix="gel-d1-migrate-") as td:
        source = Path(td) / "legacy.db"
        dest = Path(td) / "v2.db"
        secret = create_legacy_v1(source)
        mod.migrate_legacy_v1_to_v2(source, dest, applied_at=FIXED_NOW)
        require(source.exists(), "migration must not destructively replace the legacy source")
        conn = mod.connect(dest)
        try:
            require(mod.detect_schema_version(conn) == 2, "migrated schema version != 2")
            migration = conn.execute(
                "SELECT name,source_version FROM archive_schema_migrations WHERE version=2"
            ).fetchone()
            require(tuple(migration) == ("legacy_v1_to_v2", 1), "migration provenance is incorrect")
            require("class_id" not in columns(conn, "students"), "migrated v2 students still contain class_id")
            require(conn.execute("SELECT COUNT(*) FROM class_memberships WHERE class_id=1 AND student_uid=10").fetchone()[0] == 1, "legacy class membership was not migrated")
            require(conn.execute("SELECT COUNT(*) FROM tutorial_identities").fetchone()[0] == 3, "tutorial identities were lost")
            normal = conn.execute(
                "SELECT authority_status,source_state_id,collision_group_id FROM tutorial_state_associations WHERE tutorial_id=100"
            ).fetchone()
            require(normal[0] == "proven_per_tutorial" and normal[1] is not None and normal[2] is None, "unique matched tutorial did not migrate as proven")

            group = conn.execute(
                "SELECT collision_group_id,collision_kind FROM tutorial_collision_groups WHERE student_uid=10 AND tutorial_ts=2000"
            ).fetchone()
            require(group is not None and group[1] == "ambiguous_unknown", "legacy collision must migrate fail-closed as ambiguous_unknown")
            group_id = int(group[0])
            require(conn.execute("SELECT COUNT(*) FROM tutorial_collision_identities WHERE collision_group_id=?", (group_id,)).fetchone()[0] == 2, "collision identities not preserved")
            require(conn.execute("SELECT COUNT(*) FROM tutorial_collision_states WHERE collision_group_id=?", (group_id,)).fetchone()[0] == 2, "collision candidate states not preserved")
            blocked = conn.execute(
                "SELECT tutorial_id,authority_status,source_state_id FROM tutorial_state_associations WHERE tutorial_id IN (200,201) ORDER BY tutorial_id"
            ).fetchall()
            require(
                [(r[0], r[1], r[2]) for r in blocked]
                == [(200, "ambiguous_collision_unknown", None), (201, "ambiguous_collision_unknown", None)],
                "legacy collision falsely attributed candidate source state to an API identity",
            )
            view_rows = conn.execute(
                "SELECT tutorial_id,authority_status,speaking FROM tutorial_revision_state WHERE tutorial_id IN (200,201) ORDER BY tutorial_id"
            ).fetchall()
            require(
                [(r[0], r[1], r[2]) for r in view_rows]
                == [(200, "ambiguous_collision_unknown", None), (201, "ambiguous_collision_unknown", None)],
                "revision view leaks candidate collision state into blocked identities",
            )
            evidence = conn.execute(
                """
                SELECT field_name,presence FROM tutorial_source_field_evidence
                WHERE field_name='reading' AND source_kind='summary'
                """
            ).fetchone()
            require(tuple(evidence) == ("reading", "present_blank"), "explicit summary blank provenance was not minimized/preserved")
            require(not conn.execute("PRAGMA foreign_key_check").fetchall(), "migrated DB has foreign key violations")

            before = conn.execute("SELECT COUNT(*) FROM tutorial_identities").fetchone()[0]
            conn.execute(
                "INSERT INTO archive_sync_runs(source,scope,status,started_at,completed_at) VALUES ('gel','tutorials','failed',?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            failed_run = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            try:
                conn.execute(
                    "UPDATE tutorial_identities SET source_present=0,presence_checked_run_id=? WHERE tutorial_id=100",
                    (failed_run,),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
            else:
                raise CheckError("failed sync run was allowed to invalidate source_present")

            conn.execute(
                "INSERT INTO archive_sync_runs(source,scope,status,started_at,completed_at) VALUES ('gel','tutorials','complete',?,?)",
                (FIXED_NOW, FIXED_NOW),
            )
            complete_run = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "UPDATE tutorial_identities SET source_present=0,presence_checked_run_id=? WHERE tutorial_id=100",
                (complete_run,),
            )
            conn.commit()
            after = conn.execute("SELECT COUNT(*) FROM tutorial_identities").fetchone()[0]
            require(before == after == 3, "source disappearance deleted preserved tutorial identity")
        finally:
            conn.close()

        dest_bytes = dest.read_bytes()
        require(secret.encode("utf-8") not in dest_bytes, "v2 destination retained legacy email/raw_json PII")
        schema_text = "\n".join(
            row[0] or ""
            for row in sqlite3.connect(dest).execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            )
        )
        require("raw_json" not in schema_text, "v2 schema still contains raw_json")
        require(" email " not in f" {schema_text.lower()} ", "v2 schema still contains legacy email column")


def check_safe_upsert_policy() -> None:
    paths = [ORACLE, ARCHIVE_MODULE, SCHEMA_SQL]
    violations = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "INSERT OR REPLACE" in text.upper():
            violations.append(str(path.relative_to(ROOT)))
    require(not violations, f"INSERT OR REPLACE remains in active archive/schema code: {violations}")
    oracle_text = ORACLE.read_text(encoding="utf-8")
    require("PRAGMA foreign_keys = ON" in oracle_text, "transitional Python archive writer must enable foreign keys")
    require("ON CONFLICT(class_id) DO UPDATE" in oracle_text, "class upsert is not conflict-safe")
    require("ON CONFLICT(uid) DO UPDATE" in oracle_text, "student upsert is not conflict-safe")


def extract_oracle_upsert_sql(method_name: str, table: str) -> str:
    """Extract the exact SQLite UPSERT statement without importing the live oracle.

    The transitional v4.9 oracle has HTTP/parser dependencies (requests/bs4) that are
    irrelevant to the D1 archive-schema gate.  Importing that runtime here would make
    an offline storage contract depend on network-client packages.  Instead, parse the
    oracle source, locate the SQLite statement used by the named TutorialDatabase
    method, and execute that exact SQL against an isolated minimal schema.
    """
    source = ORACLE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ORACLE))
    wanted = f"INSERT INTO {table}"

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "TutorialDatabase":
            continue
        for member in node.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) or member.name != method_name:
                continue
            for call in ast.walk(member):
                if not isinstance(call, ast.Call) or not call.args:
                    continue
                func = call.func
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr == "execute"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "conn"
                    and isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "self"
                ):
                    continue
                sql_arg = call.args[0]
                if isinstance(sql_arg, ast.Constant) and isinstance(sql_arg.value, str):
                    sql = sql_arg.value
                    if wanted.upper() in sql.upper():
                        return sql
    raise CheckError(f"could not extract {table} UPSERT SQL from TutorialDatabase.{method_name}")


def check_transitional_oracle_upsert_behavior() -> None:
    class_upsert_sql = extract_oracle_upsert_sql("upsert_class", "classes")
    student_upsert_sql = extract_oracle_upsert_sql("upsert_student", "students")

    with tempfile.TemporaryDirectory(prefix="gel-d1-oracle-upsert-") as td:
        path = Path(td) / "legacy.db"
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            require(
                conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
                "isolated transitional-UPSERT test connection did not enable foreign keys",
            )
            conn.executescript(
                """
                CREATE TABLE classes (
                    class_id INTEGER PRIMARY KEY, name TEXT, course_code TEXT,
                    start_date TEXT, end_date TEXT, is_active INTEGER, scraped_at TEXT
                );
                CREATE TABLE students (
                    uid INTEGER PRIMARY KEY, class_id INTEGER, name TEXT, cefr_level INTEGER,
                    school_name TEXT, start_date TEXT, end_date TEXT, attendance INTEGER,
                    tutorial_late INTEGER, last_tutorial_ts INTEGER, test_type TEXT,
                    last_test_ts INTEGER, unmarked_exit_test INTEGER, scraped_at TEXT,
                    FOREIGN KEY(class_id) REFERENCES classes(class_id)
                );
                CREATE TABLE tutorials (
                    tutorial_id INTEGER PRIMARY KEY, student_uid INTEGER NOT NULL,
                    FOREIGN KEY(student_uid) REFERENCES students(uid)
                );
                """
            )

            conn.execute(
                class_upsert_sql,
                (1, "Class A", None, None, None, FIXED_NOW),
            )
            conn.execute(
                student_upsert_sql,
                (10, 1, "Student", None, None, None, None, None, 0, None, None, None, 0, FIXED_NOW),
            )
            conn.execute("INSERT INTO tutorials(tutorial_id,student_uid) VALUES (100,10)")
            conn.commit()

            conn.execute(
                class_upsert_sql,
                (1, "Class A updated", None, None, None, FIXED_NOW),
            )
            conn.execute(
                student_upsert_sql,
                (10, 1, "Student updated", None, None, None, None, None, 0, None, None, None, 0, FIXED_NOW),
            )
            conn.commit()

            require(
                conn.execute("SELECT name FROM classes WHERE class_id=1").fetchone()[0]
                == "Class A updated",
                "class UPSERT did not update in place",
            )
            require(
                conn.execute("SELECT name FROM students WHERE uid=10").fetchone()[0]
                == "Student updated",
                "student UPSERT did not update in place",
            )
            require(
                conn.execute(
                    "SELECT COUNT(*) FROM tutorials WHERE tutorial_id=100 AND student_uid=10"
                ).fetchone()[0]
                == 1,
                "class/student UPSERT deleted dependent tutorial identity",
            )
            require(
                not conn.execute("PRAGMA foreign_key_check").fetchall(),
                "transitional oracle UPSERT left FK violations",
            )
        finally:
            conn.close()


def check_contract_shape() -> None:
    contract = json.loads((ROOT / "contracts" / "archive_schema_v2.json").read_text(encoding="utf-8"))
    require(contract["schema_version"] == 2, "archive schema contract version drifted")
    require(contract["raw_json_policy"]["stored_in_v2"] is False, "raw_json must be excluded from v2")
    require(contract["membership_model"]["student_class_foreign_key_removed"] is True, "student class_id replacement contract drifted")
    require(
        contract["identity_state_association"]["revision_allowed_statuses"]
        == ["proven_per_tutorial", "shared_identical_collision"],
        "C3 authority statuses drifted in archive schema contract",
    )


def main() -> int:
    try:
        require(SCHEMA_SQL.exists(), "missing schema/archive_v2.sql")
        require(ARCHIVE_MODULE.exists(), "missing python-oracle/archive_schema_v2.py")
        mod = load_archive_module()
        check_contract_shape()
        check_safe_upsert_policy()
        check_transitional_oracle_upsert_behavior()
        check_fresh_schema(mod)
        check_legacy_migration(mod)
    except (CheckError, RuntimeError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"check:archive-schema FAIL — {exc}")
        return 1
    print("check:archive-schema PASS — fresh v2 + legacy migration + FK + collision + privacy + upsert invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
