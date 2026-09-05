
#!/usr/bin/env python3
"""
gel_tutorial_archiver_v4_9.py

Archive GEL tutorials to SQLite using the confirmed live sources:

1. API list endpoint:
   /staff/students/{uid}/tutorials
   -> canonical tutorial ids + timestamps

2. Learn2 summary page (PRIMARY normalized source):
   /study/tutorials/summary/{uid}
   -> server-rendered tutorial table containing type, teacher, absent status,
      levels, Standard assessment, aims/comments, exam rows, print/edit links
   NOTE: DataTables/FixedColumns are presentation only in the observed live
   response; the tutorial data is already present in the raw HTML.

3. Learn2 print page (fallback + cross-check):
   /study/tutorials/print/{uid}/{timestamp}
   -> read-only text with all tutorial field data

v4.5 fix: When the summary page returns only a JS shell (no fixedTable
structure), the script no longer skips the student. Instead it creates stub
entries from the API tutorial list and fetches print pages as the primary
data source. Previously the `continue` on line 1058 caused 100% tutorial loss.

v4.6 fix: The live summary response now exposes the complete server-rendered
`#Open_Text_General.table.FixedTables` table directly. The parser accepts this
raw structure as well as the older FixedColumns clone layout, extracts all
seven Standard self-assessment values, and upgrades existing print-only rows
when richer summary data becomes available.

v4.7 fix: Historical edit forms are fetched and used to recover the original
teacher id (`tid`). Live GEL does not mark the historical teacher option as
selected in raw HTML; instead it emits inline JavaScript such as
`$("#tid").val("326743")`. v4.7 parses that server-provided value without
executing JavaScript, validates it against the `<select name="tid">` option
list when available, stores the numeric teacher_id, and records its provenance.
A normal selected `<option>` remains supported as a fallback.

v4.8 fix: Summary/API reconciliation is now consumption-safe and collision-aware.
A summary column consumed by an exact timestamp match is also unavailable to
same-date fallback, preventing accidental reuse. Same-student/same-timestamp
collisions (multiple API tutorial ids and/or multiple summary columns) are
recorded explicitly; deterministic pairing may still be used to preserve all
rows, but the API-id ↔ summary-state correspondence is marked ambiguous rather
than treated as proven. All collision summary states are retained in the
`reconciliation_collisions` table for Rust parity/regression work.

v4.9 fix: The server-rendered summary is authoritative even when a field is
explicitly blank. Print fallback now fills only keys that are absent from the
summary; it never replaces a present-but-empty summary value (for example a
blank Teacher's Comments or Additional Comments field) with print-page
placeholders such as ``none``. Existing rows created by the older fallback
logic are repairable on re-run: explicit summary blanks are allowed to replace
legacy nonblank fallback values without being blocked by the normal richness
score/merge protection. Print fallback parsing is also DOM-structural: labels
are read from table row/cell boundaries so words such as ``Listening`` or
``Speaking`` inside teacher prose cannot be mistaken for field labels.

Privacy hardening: student email/mail fields are discarded immediately from
roster/profile API data and are never persisted. Existing legacy email values
are cleared automatically when the database is opened.
"""

import argparse
import base64
import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

API_BASE = "https://api2.guidedelearning.net"
LEARN2_BASE = "https://learn2.guidedelearning.net"
LOGIN_URL = f"{LEARN2_BASE}/user/login?destination=login_redirect"
LOGIN_FORM_URL = f"{LEARN2_BASE}/user/login"

DEFAULT_DB = "gel_tutorials_v4_1.db"
DEFAULT_DELAY = 0.3

TTYPE_MAP = {"0": "Standard", "1": "Final", "2": "Initial"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS classes (
    class_id      INTEGER PRIMARY KEY,
    name          TEXT,
    course_code   TEXT,
    start_date    TEXT,
    end_date      TEXT,
    is_active     INTEGER DEFAULT 1,
    scraped_at    TEXT
);

CREATE TABLE IF NOT EXISTS students (
    uid                 INTEGER PRIMARY KEY,
    class_id            INTEGER,
    name                TEXT,
    cefr_level          INTEGER,
    school_name         TEXT,
    start_date          TEXT,
    end_date            TEXT,
    attendance          INTEGER,
    tutorial_late       INTEGER,
    last_tutorial_ts    INTEGER,
    test_type           TEXT,
    last_test_ts        INTEGER,
    unmarked_exit_test  INTEGER,
    scraped_at          TEXT,
    FOREIGN KEY (class_id) REFERENCES classes(class_id)
);

CREATE TABLE IF NOT EXISTS tutorials (
    tutorial_id         INTEGER PRIMARY KEY,
    student_uid         INTEGER,
    teacher_id          INTEGER,
    teacher_id_source   TEXT,
    teacher_name        TEXT,
    tutorial_type       TEXT,
    ttype_raw           TEXT,
    created_at          INTEGER,
    created_date        TEXT,
    absent              INTEGER DEFAULT 0,
    custom_date         TEXT,

    overall_level       TEXT,

    speaking            TEXT,
    use_of_english      TEXT,
    writing             TEXT,
    listening           TEXT,
    reading             TEXT,

    speaking_before     TEXT,
    uoe_before          TEXT,
    writing_before      TEXT,
    listening_before    TEXT,

    exam_want           TEXT,
    exam_which          TEXT,
    exam_when           TEXT,

    self_listening      TEXT,
    self_reading        TEXT,
    self_writing        TEXT,
    self_speaking       TEXT,
    self_vocabulary     TEXT,
    self_grammar        TEXT,
    self_pronunciation  TEXT,

    aims                TEXT,
    teacher_comments    TEXT,
    additional_comments TEXT,

    source_method       TEXT,
    summary_url         TEXT,
    print_url           TEXT,
    edit_url            TEXT,

    summary_match_method TEXT,
    reconciliation_status TEXT,
    reconciliation_key  TEXT,

    raw_json            TEXT,
    scraped_at          TEXT,
    FOREIGN KEY (student_uid) REFERENCES students(uid)
);

CREATE INDEX IF NOT EXISTS idx_students_class      ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_tutorials_student   ON tutorials(student_uid);
CREATE INDEX IF NOT EXISTS idx_tutorials_type      ON tutorials(tutorial_type);
CREATE INDEX IF NOT EXISTS idx_tutorials_date      ON tutorials(created_date);
CREATE INDEX IF NOT EXISTS idx_tutorials_teacher   ON tutorials(teacher_id);

CREATE TABLE IF NOT EXISTS reconciliation_collisions (
    student_uid            INTEGER NOT NULL,
    tutorial_ts            INTEGER NOT NULL,
    api_count              INTEGER NOT NULL,
    summary_count          INTEGER NOT NULL,
    api_tutorial_ids_json  TEXT NOT NULL,
    summary_entries_json   TEXT NOT NULL,
    mapping_status         TEXT NOT NULL DEFAULT 'ambiguous',
    detected_at            TEXT NOT NULL,
    PRIMARY KEY (student_uid, tutorial_ts)
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_collision_student
    ON reconciliation_collisions(student_uid);

CREATE TABLE IF NOT EXISTS scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT,
    target      TEXT,
    status      TEXT,
    message     TEXT,
    timestamp   TEXT
);
"""

MIGRATIONS = [
    ("students",  "cefr_level",         "INTEGER"),
    ("students",  "school_name",        "TEXT"),
    ("students",  "start_date",         "TEXT"),
    ("students",  "end_date",           "TEXT"),
    ("students",  "attendance",         "INTEGER"),
    ("students",  "tutorial_late",      "INTEGER"),
    ("students",  "last_tutorial_ts",   "INTEGER"),
    ("students",  "test_type",          "TEXT"),
    ("students",  "last_test_ts",       "INTEGER"),
    ("students",  "unmarked_exit_test", "INTEGER"),
    ("tutorials", "teacher_id",         "INTEGER"),
    ("tutorials", "teacher_id_source",  "TEXT"),
    ("tutorials", "teacher_name",       "TEXT"),
    ("tutorials", "speaking_before",    "TEXT"),
    ("tutorials", "uoe_before",         "TEXT"),
    ("tutorials", "writing_before",     "TEXT"),
    ("tutorials", "listening_before",   "TEXT"),
    ("tutorials", "source_method",      "TEXT"),
    ("tutorials", "summary_url",        "TEXT"),
    ("tutorials", "print_url",          "TEXT"),
    ("tutorials", "edit_url",           "TEXT"),
    ("tutorials", "summary_match_method", "TEXT"),
    ("tutorials", "reconciliation_status", "TEXT"),
    ("tutorials", "reconciliation_key",  "TEXT"),
]

SUMMARY_ROW_MAP = {
    "name": "Name",
    "id": "ID",
    "teacher": "Teacher",
    "type": "Type",
    "absent": "absent",
    "overall": "Tutorial Overall Level",
    "tutorial": "Tutorial",
    "initial_speaking": "Initial Speaking",
    "speaking": "Speaking",
    "initial_uoe": "Initial Use of English",
    "uoe": "Use of English",
    "initial_writing": "Initial Writing",
    "writing": "Writing",
    "initial_listening": "Initial Listening",
    "listening": "Listening",
    "reading": "Reading",
    "assessment": "Assessment",
    "aims": "Aims",
    "teacher_comments": "Teacher's Comments",
    "additional_comments": "Additional Comments/Accommodation (under 18s only)",
    "exam_want": "Do you want to take an English proficiency exam?",
    "exam_which": "If yes, which exam?",
    "exam_when": "If yes, when do you want to take the exam?",
    "actions": "Actions",
}

@dataclass
class SummaryEntry:
    datetime_label: str
    tutorial_ts: int
    ttype_raw: str
    ttype_label: str
    print_url: str
    edit_url: str
    fields: dict[str, str]


class GELArchiverClient:
    def __init__(self, delay: float = DEFAULT_DELAY):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GEL-Tutorial-Archiver/2.1",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://staff2.guidedelearning.net",
            "Referer": "https://staff2.guidedelearning.net/",
        })
        self.delay = delay
        self.authenticated = False
        self._request_count = 0
        self.last_learn2_fetch: dict[str, object] = {}

    def _throttle(self):
        if self.delay > 0:
            time.sleep(self.delay)
        self._request_count += 1

    def login(self, username: str, password: str) -> bool:
        payload = {
            "edit[name]": username,
            "edit[pass]": password,
            "edit[smsCode]": "",
            "edit[form_id]": "user_login",
            "edit[class_access_code]": "",
        }

        # Step 1: corelogin AJAX handshake used by the working writer client.
        self._throttle()
        r = self.session.post(
            LOGIN_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{LEARN2_BASE}/corelogin/",
            },
            allow_redirects=True,
            timeout=20,
        )
        try:
            result = r.json()
        except Exception:
            print(f"Login response not JSON: {r.text[:400]}")
            return False

        if result.get("status") not in ("authNotNeeded",):
            errs = result.get("errors", [])
            print(f"Login failed: {errs[0] if errs else r.text[:400]}")
            return False

        # Step 2: second POST completes the cookie/session handshake.
        self._throttle()
        self.session.post(
            LOGIN_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{LEARN2_BASE}/corelogin/",
            },
            allow_redirects=True,
            timeout=20,
        )

        # Step 3: verify api2 session.
        self._throttle()
        check = self.session.get(f"{API_BASE}/staff/classes?open=true", timeout=15)
        self.authenticated = check.status_code == 200
        if not self.authenticated:
            print("  ✗ api2 session not established after login")
            return False

        # Step 4: verify learn2 HTML session against a real authenticated page.
        self._throttle()
        learn2_check = self.session.get(
            f"{LEARN2_BASE}/administration/students",
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=15,
            allow_redirects=True,
        )
        sample = learn2_check.text[:5000].lower()
        final_url = learn2_check.url.lower()

        authenticated_markers = (
            "/administration/students" in final_url
            or "/administration/students/search" in final_url
            or 'id="student-management"' in sample
            or 'id="csvform"' in sample
            or 'id="studeamanagementform"' in sample
            or "download list" in sample
        )
        login_markers = (
            "/user/login" in final_url
            or "corelogin" in final_url
            or "user-login" in sample
            or 'name="form_build_id"' in sample
            or 'name="form_token"' in sample
            or 'name="edit[pass]"' in sample
            or 'name="edit[name]"' in sample
        )

        if login_markers:
            print("  ✗ learn2 session not established — HTML pages will not work")
            print(learn2_check.text[:1200])
            self.authenticated = False
            return False
        if not authenticated_markers:
            print(f"  ✗ learn2 HTML session check returned an unexpected page: {learn2_check.url}")
            print(learn2_check.text[:1200])
            self.authenticated = False
            return False

        print("  ✓ learn2 HTML session established")
        return True

    def _api_get(self, path: str, params: dict | None = None):
        self._throttle()
        r = self.session.get(f"{API_BASE}{path}", params=params, timeout=20)
        if r.status_code in (401, 403):
            self.authenticated = False
            raise ConnectionError("Session expired")
        if not r.ok:
            raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
        return r.json()

    def _learn2_get_text(self, path_or_url: str) -> str:
        url = path_or_url if path_or_url.startswith("http") else f"{LEARN2_BASE}{path_or_url}"
        self._throttle()
        r = self.session.get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{LEARN2_BASE}/administration/students",
            },
            timeout=20,
            allow_redirects=True,
        )
        self.last_learn2_fetch = {
            "requested_url": url,
            "final_url": r.url,
            "status": r.status_code,
            "head": r.text[:1200],
        }
        if r.status_code in (401, 403):
            self.authenticated = False
            raise ConnectionError("Session expired")
        if not r.ok:
            raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
        return r.text

    def get_classes(self) -> list:
        return self._api_get("/staff/classes", {"open": "true"})

    @staticmethod
    def _strip_student_sensitive_fields(value):
        """Discard student email fields immediately after API retrieval."""
        blocked = {"email", "mail", "email_address", "emailaddress"}
        if isinstance(value, dict):
            return {
                key: GELArchiverClient._strip_student_sensitive_fields(item)
                for key, item in value.items()
                if str(key).lower() not in blocked
            }
        if isinstance(value, list):
            return [GELArchiverClient._strip_student_sensitive_fields(item) for item in value]
        return value

    def get_students(self, class_id: int) -> list:
        data = self._api_get(f"/staff/classes/{class_id}/students")
        return self._strip_student_sensitive_fields(data)

    def get_student_profile(self, uid: int) -> dict:
        data = self._api_get(f"/staff/students/{uid}")
        return self._strip_student_sensitive_fields(data)

    def get_tutorial_list(self, uid: int) -> list:
        return self._api_get(f"/staff/students/{uid}/tutorials")

    def get_tutorial_summary_html(self, uid: int) -> str:
        return self._learn2_get_text(f"/study/tutorials/summary/{uid}")

    def get_tutorial_print_html(self, uid: int, tutorial_ts: int) -> str:
        return self._learn2_get_text(f"/study/tutorials/print/{uid}/{tutorial_ts}")

    def get_tutorial_edit_html(self, uid: int, tutorial_ts: int, ttype_raw: str) -> str:
        return self._learn2_get_text(f"/study/tutorials/add/{uid}/{tutorial_ts}/{ttype_raw}")


# GEL's historical edit form contains a normal <select id="tid" name="tid">,
# but the original teacher is selected by inline JavaScript rather than by an
# HTML `selected` attribute. Be tolerant of whitespace, quote style,
# `$` vs `jQuery`, and quoted vs bare numeric ids.
_TID_JS_PATTERNS = [
    re.compile(
        r"(?:\$\s*|jQuery\s*)\(\s*[\"']#tid[\"']\s*\)\s*"
        r"\.val\s*\(\s*[\"'](?P<tid>\d+)[\"']\s*\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\$\s*|jQuery\s*)\(\s*[\"']#tid[\"']\s*\)\s*"
        r"\.val\s*\(\s*(?P<tid>\d+)\s*\)",
        re.IGNORECASE,
    ),
]


def parse_teacher_from_edit_html(html: str) -> dict[str, Any]:
    """Recover the historical tutorial teacher from a raw GEL edit form."""
    soup = BeautifulSoup(html, "html.parser")
    tid_select = soup.select_one('select[name="tid"], select#tid')

    teacher_id: Optional[int] = None
    teacher_id_source = ""

    inline_script_text = "\n".join(
        (script.string if script.string is not None else script.get_text("\n", strip=False)) or ""
        for script in soup.find_all("script")
        if not script.get("src")
    )

    for pattern in _TID_JS_PATTERNS:
        match = pattern.search(inline_script_text)
        if match:
            value = int(match.group("tid"))
            if value != 0:
                teacher_id = value
                teacher_id_source = "edit_form_inline_js"
            break

    if teacher_id is None and tid_select is not None:
        selected = tid_select.find("option", selected=True)
        if selected is not None:
            raw_value = (selected.get("value") or "").strip()
            if raw_value.isdigit() and int(raw_value) != 0:
                teacher_id = int(raw_value)
                teacher_id_source = "edit_form_selected_option"

    teacher_name = ""
    teacher_option_found = False
    if teacher_id is not None and tid_select is not None:
        for option in tid_select.find_all("option"):
            raw_value = (option.get("value") or "").strip()
            if raw_value == str(teacher_id):
                teacher_option_found = True
                teacher_name = option.get_text(" ", strip=True)
                break

    return {
        "teacher_id": teacher_id,
        "teacher_name": teacher_name,
        "teacher_id_source": teacher_id_source,
        "tid_select_present": tid_select is not None,
        "teacher_option_found": teacher_option_found,
    }


def deep_find(data, key: str, default=None):
    if isinstance(data, dict):
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
        for v in data.values():
            result = deep_find(v, key)
            if result not in (None, "", [], {}):
                return result
    elif isinstance(data, list):
        for item in data:
            result = deep_find(item, key)
            if result not in (None, "", [], {}):
                return result
    return default


def safe_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "on" if value else ""
    return str(value).strip()


def normalize_type(value) -> str:
    if not value:
        return "Standard"
    s = str(value).strip()
    if s in TTYPE_MAP:
        return TTYPE_MAP[s]
    lowered = s.lower()
    for label in ("initial", "standard", "final"):
        if label in lowered:
            return label.capitalize()
    return "Standard"


def _ts_to_iso(ts) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts)).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _cell_text(td) -> str:
    hidden = td.select_one("span.hidden-text")
    if hidden:
        return hidden.get_text(" ", strip=True)
    clone = BeautifulSoup(str(td), "html.parser")
    for bad in clone.select(".show-more, span.hidden-text, script, style"):
        bad.decompose()
    return clone.get_text(" ", strip=True).replace(" read more", "").strip()


def _first_href(td, pattern: str) -> str:
    for a in td.select("a[href]"):
        href = a.get("href", "")
        if re.search(pattern, href):
            return href
    return ""


def _parse_ttype_from_edit_url(edit_url: str) -> str:
    m = re.search(r"/study/tutorials/add/\d+/\d+/(\d+)", edit_url)
    return m.group(1) if m else ""


def _parse_ts_from_url(url: str) -> int:
    m = re.search(r"/study/tutorials/(?:print|add)/\d+/(\d+)", url)
    return int(m.group(1)) if m else 0


def _summary_page_auth_guard(soup: BeautifulSoup) -> None:
    page_sample = soup.get_text(" ", strip=True)[:600].lower()
    if (
        soup.find("input", {"name": "edit[name]"})
        or soup.find("input", {"name": "name"})
        or soup.find("input", {"type": "password"})
        or soup.find("form", id=lambda x: x and "login" in x.lower())
    ):
        raise RuntimeError(
            "Summary page returned login form — session not authenticated for learn2"
        )
    if "corelogin" in page_sample or "log in" in page_sample or "login" in page_sample[:180]:
        raise RuntimeError(
            "Summary page looks like a login/holding page, not tutorial summary HTML"
        )


def _build_summary_entries(
    row_labels: list[str],
    head_dates: list[str],
    rows,
) -> list[SummaryEntry]:
    """Build per-tutorial columns from aligned row labels, dates and data rows."""
    columns: dict[int, dict[str, str]] = defaultdict(dict)
    meta: dict[int, dict[str, Any]] = defaultdict(dict)

    for row_idx, tr in enumerate(rows):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        label = row_labels[row_idx] if row_idx < len(row_labels) else f"row_{row_idx}"

        for col_idx, td in enumerate(tds):
            text = _cell_text(td)
            columns[col_idx][label] = text

            if label == "Actions":
                print_url = _first_href(td, r"/study/tutorials/print/")
                edit_url = _first_href(td, r"/study/tutorials/add/")
                meta[col_idx]["print_url"] = print_url
                meta[col_idx]["edit_url"] = edit_url
                meta[col_idx]["tutorial_ts"] = _parse_ts_from_url(print_url or edit_url)
                ttype_raw = _parse_ttype_from_edit_url(edit_url)
                meta[col_idx]["ttype_raw"] = ttype_raw
                meta[col_idx]["ttype_label"] = normalize_type(ttype_raw)

            if col_idx < len(head_dates):
                meta[col_idx]["datetime_label"] = head_dates[col_idx]

    entries: list[SummaryEntry] = []
    for col_idx in sorted(columns.keys()):
        md = meta.get(col_idx, {})
        if not md.get("edit_url") and not md.get("print_url"):
            continue
        entries.append(SummaryEntry(
            datetime_label=safe_str(md.get("datetime_label")),
            tutorial_ts=int(md.get("tutorial_ts") or 0),
            ttype_raw=safe_str(md.get("ttype_raw")),
            ttype_label=normalize_type(md.get("ttype_raw")),
            print_url=safe_str(md.get("print_url")),
            edit_url=safe_str(md.get("edit_url")),
            fields=columns[col_idx],
        ))

    for entry in entries:
        if not entry.tutorial_ts and entry.datetime_label:
            m = re.search(r"(\d{2}-\d{2}-\d{4})", entry.datetime_label)
            if m:
                try:
                    dt = datetime.strptime(m.group(1), "%d-%m-%Y")
                    entry.tutorial_ts = int(dt.timestamp())
                except ValueError:
                    pass
    return entries


def _parse_direct_summary_table(table) -> list[SummaryEntry]:
    """Parse the raw server-rendered FixedTables summary structure.

    Live GEL currently returns one table where the first column contains row
    labels and each subsequent column represents one tutorial.  This exists in
    the raw HTTP response before any DataTables/FixedColumns JavaScript runs.
    """
    header_row = table.select_one("thead tr")
    body_rows = table.select("tbody > tr")
    if header_row is None or not body_rows:
        return []

    headers = header_row.find_all(["th", "td"], recursive=False)
    if len(headers) < 2:
        return []

    first_header = _cell_text(headers[0]).lower()
    if "date" not in first_header and "time" not in first_header:
        return []

    head_dates = [_cell_text(cell) for cell in headers[1:]]
    row_labels: list[str] = []
    data_rows = []

    # Make lightweight cloned rows containing tutorial cells only so the same
    # aligned-column builder can be used for direct and legacy layouts.
    for tr in body_rows:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue
        label = _cell_text(tds[0])
        if not label:
            continue
        row_labels.append(label)

        clone_soup = BeautifulSoup("<tr></tr>", "html.parser")
        clone_tr = clone_soup.tr
        for td in tds[1:]:
            td_copy = BeautifulSoup(str(td), "html.parser").find("td")
            clone_tr.append(td_copy)
        data_rows.append(clone_tr)

    if "Actions" not in row_labels:
        return []
    return _build_summary_entries(row_labels, head_dates, data_rows)


def parse_tutorial_summary(html: str, student_uid: int) -> list[SummaryEntry]:
    soup = BeautifulSoup(html, "html.parser")
    _summary_page_auth_guard(soup)

    # v4.6: prefer the actual raw server-rendered table observed on live GEL.
    # ID first because it is the precise current structure; class is retained
    # as a resilient fallback if GEL changes the table id.
    direct_table = (
        soup.select_one("#Open_Text_General.FixedTables")
        or soup.select_one("#Open_Text_General")
        or soup.select_one("table.FixedTables")
    )
    if direct_table is not None:
        entries = _parse_direct_summary_table(direct_table)
        if entries:
            return entries

    # Legacy/alternate layout: JavaScript or older server variants may expose
    # separate fixed-left, fixed-head and data tables.
    fixed_left = (
        soup.select_one(".fixedColumn .fixedTable table")
        or soup.select_one("div.fixedArea div.fixedTable table")
        or soup.select_one("table.fixedColumn")
    )
    fixed_head = soup.select_one(".fixedContainer .fixedHead table")
    data_table = (
        soup.select_one(".fixedContainer .fixedTable table")
        or soup.select_one("div.fixedContainer div.fixedTable table")
    )

    if fixed_left and fixed_head and data_table:
        row_labels = [
            _cell_text(td) for td in fixed_left.select("tr > td") if _cell_text(td)
        ]
        head_dates = [_cell_text(td) for td in fixed_head.select("tr > td")]
        rows = data_table.select("tr")
        if rows:
            return _build_summary_entries(row_labels, head_dates, rows)

    raise RuntimeError("Summary page missing expected tutorial table structure")

def parse_print_page_fallback(html: str) -> dict[str, Any]:
    """Parse a single tutorial print page using DOM row/cell boundaries.

    Do not discover labels by scanning flattened prose: teacher comments can
    legitimately contain sentences such as ``Listening is ...`` and
    ``Speaking is ...``. The old flat-text parser split those sentences into
    fake fields.
    """
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    canonical = {label.lower(): label for label in PRINT_LABELS}
    best_fields: dict[str, str] = {}
    best_text = ""
    best_score = 0

    for table in soup.find_all("table"):
        fields: dict[str, str] = {}
        score = 0
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            if len(cells) < 2:
                continue
            raw_label = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip().rstrip(":").strip()
            label = canonical.get(raw_label.lower())
            if not label:
                continue
            value = " ".join(
                re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
                for cell in cells[1:]
                if cell.get_text(" ", strip=True)
            ).strip()
            fields[label] = safe_str(value)
            score += 1

        if score > best_score:
            best_score = score
            best_fields = fields
            best_text = table.get_text(" ", strip=True)

    result: dict[str, Any] = {}
    result.update(_extract_print_header(page_text))
    if best_text:
        result["print_text"] = best_text
    if best_fields:
        result["fields"] = dict(best_fields)
        result.update(best_fields)
        if "Tutorial Type" in best_fields and "Type" not in result:
            result["Type"] = best_fields["Tutorial Type"]
    return result


PRINT_LABELS = [
    "Tutorial Type",
    "absent",
    "Tutorial Overall Level",
    "Initial Speaking",
    "Initial Use of English",
    "Initial Writing",
    "Initial Listening",
    "Speaking",
    "Use of English",
    "Writing",
    "Listening",
    "Reading",
    "Assessment",
    "Aims",
    "Teacher's Comments",
    "Additional Comments/Accommodation (under 18s only)",
    "Do you want to take an English proficiency exam?",
    "If yes, which exam?",
    "If yes, when do you want to take the exam?",
]


def _extract_print_header(text: str) -> dict[str, str]:
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"Tutorial with (.+?) \(teacher\) and (.+?) \(student\) on (\d{2}-\d{2}-\d{4})", text)
    if not m:
        return {}
    return {
        "teacher_name": safe_str(m.group(1)),
        "student_name": safe_str(m.group(2)),
        "custom_date": safe_str(m.group(3)),
    }


def parse_print_record_text(text: str) -> dict[str, str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text or "Tutorial Type" not in text:
        return {}

    result = {}
    result.update(_extract_print_header(text))

    positions = []
    search_pos = 0
    # find labels in order of appearance; choose earliest valid next occurrence
    while True:
        found = []
        for label in PRINT_LABELS:
            idx = text.find(label, search_pos)
            if idx != -1:
                found.append((idx, label))
        if not found:
            break
        idx, label = min(found, key=lambda x: x[0])
        # skip duplicates at same position with shorter labels
        if positions and idx == positions[-1][0]:
            search_pos = idx + len(label)
            continue
        positions.append((idx, label))
        search_pos = idx + len(label)

    for i, (idx, label) in enumerate(positions):
        start = idx + len(label)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        value = text[start:end].strip(" :")
        result[label] = safe_str(value)

    # normalize some key aliases expected by build_record_from_summary
    if "Tutorial Type" in result and "Type" not in result:
        result["Type"] = result["Tutorial Type"]
    return result


def clean_summary_field(value: str) -> str:
    value = safe_str(value)
    value = re.sub(r"\s+", " ", value).strip()
    if value.lower() in {"choose...", "please choose:"}:
        return value
    return value


ASSESSMENT_FIELDS = {
    "listening": "self_listening",
    "reading": "self_reading",
    "writing": "self_writing",
    "speaking": "self_speaking",
    "vocabulary": "self_vocabulary",
    "grammar": "self_grammar",
    "pronunciation": "self_pronunciation",
}


def parse_self_assessment(value: str) -> dict[str, str]:
    """Decode the seven labelled values stored in the summary Assessment row."""
    result = {column: "" for column in ASSESSMENT_FIELDS.values()}
    text = re.sub(r"\s+", " ", safe_str(value)).strip()
    if not text:
        return result

    labels = "|".join(re.escape(label) for label in ASSESSMENT_FIELDS)
    matches = list(re.finditer(rf"(?i)\b({labels})\s*:\s*", text))
    for i, match in enumerate(matches):
        label = match.group(1).lower()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        assessment_value = text[match.end():end].strip(" ;,.-")
        result[ASSESSMENT_FIELDS[label]] = assessment_value
    return result


def build_record_from_summary(
    student_uid: int,
    tutorial_id: int,
    tutorial_ts: int,
    entry: SummaryEntry,
    print_fallback: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    summary_field_keys = set(entry.fields.keys())
    fields = {k: clean_summary_field(v) for k, v in entry.fields.items()}
    print_fallback = print_fallback or {}
    # v4.9: summary presence and summary content are separate facts. An
    # explicitly blank summary cell is authoritative and must remain blank.
    # Print is allowed to supplement only fields that the summary did not
    # expose at all.
    for k, v in (print_fallback.get("fields") or {}).items():
        if k not in fields:
            fields[k] = clean_summary_field(v)
    # print parser uses direct labels from the print text
    for k in ["Tutorial Overall Level", "Aims", "Teacher's Comments", "Additional Comments/Accommodation (under 18s only)",
              "Do you want to take an English proficiency exam?", "If yes, which exam?", "If yes, when do you want to take the exam?",
              "Initial Speaking", "Initial Use of English", "Initial Writing", "Initial Listening", "Speaking", "Use of English", "Writing", "Listening", "Reading", "Assessment", "Type", "absent"]:
        if k in print_fallback and k not in fields:
            fields[k] = clean_summary_field(print_fallback.get(k, ""))
    tutorial_type = normalize_type(entry.ttype_raw or fields.get("Type"))

    speaking = use_of_english = writing = listening = reading = ""
    speaking_before = uoe_before = writing_before = listening_before = ""

    if tutorial_type == "Initial":
        speaking       = fields.get("Initial Speaking", "")
        use_of_english = fields.get("Initial Use of English", "")
        writing        = fields.get("Initial Writing", "")
        listening      = fields.get("Initial Listening", "")
    elif tutorial_type == "Standard":
        speaking       = fields.get("Speaking", "")
        use_of_english = fields.get("Use of English", "")
        writing        = fields.get("Writing", "")
        listening      = fields.get("Listening", "")
        reading        = fields.get("Reading", "")
    elif tutorial_type == "Final":
        speaking        = fields.get("Speaking", "")
        use_of_english  = fields.get("Use of English", "")
        writing         = fields.get("Writing", "")
        listening       = fields.get("Listening", "")
        speaking_before = fields.get("Initial Speaking", "")
        uoe_before      = fields.get("Initial Use of English", "")
        writing_before  = fields.get("Initial Writing", "")
        listening_before= fields.get("Initial Listening", "")
        reading         = fields.get("Reading", "")

    date_label = entry.datetime_label.split()[0] if entry.datetime_label else ""
    if not date_label and print_fallback.get("custom_date"):
        date_label = print_fallback.get("custom_date", "")

    assessment_values = parse_self_assessment(fields.get("Assessment", ""))

    payload = {
        "source_method": "print_only" if not entry.fields else "summary+print",
        "student_uid": student_uid,
        "tutorial_id": tutorial_id,
        "teacher_id": None,
        "teacher_id_source": "",
        "teacher_name": fields.get("Teacher", "") or print_fallback.get("teacher_name", ""),
        "tutorial_type": tutorial_type,
        "ttype_raw": entry.ttype_raw,
        "created_at": int(tutorial_ts) if tutorial_ts else 0,
        "created_date": datetime.fromtimestamp(int(tutorial_ts)).isoformat() if tutorial_ts else "",
        "absent": 1 if fields.get("absent", "").strip().lower() in {"yes", "true", "1", "on"} else 0,
        "custom_date": date_label,
        "overall_level": fields.get("Tutorial Overall Level", ""),
        "speaking": speaking,
        "use_of_english": use_of_english,
        "writing": writing,
        "listening": listening,
        "reading": reading,
        "speaking_before": speaking_before,
        "uoe_before": uoe_before,
        "writing_before": writing_before,
        "listening_before": listening_before,
        "exam_want": fields.get("Do you want to take an English proficiency exam?", ""),
        "exam_which": fields.get("If yes, which exam?", ""),
        "exam_when": fields.get("If yes, when do you want to take the exam?", ""),
        "self_listening": assessment_values["self_listening"],
        "self_reading": assessment_values["self_reading"],
        "self_writing": assessment_values["self_writing"],
        "self_speaking": assessment_values["self_speaking"],
        "self_vocabulary": assessment_values["self_vocabulary"],
        "self_grammar": assessment_values["self_grammar"],
        "self_pronunciation": assessment_values["self_pronunciation"],
        "aims": fields.get("Aims", ""),
        "teacher_comments": fields.get("Teacher's Comments", ""),
        "additional_comments": fields.get("Additional Comments/Accommodation (under 18s only)", ""),
        "summary_url": f"/study/tutorials/summary/{student_uid}",
        "print_url": entry.print_url,
        "edit_url": entry.edit_url,
        "summary_match_method": "",
        "reconciliation_status": "",
        "reconciliation_key": "",
        "raw_json": "",
        "scraped_at": datetime.now().isoformat(),
    }

    # Self-assessment is decoded from the summary Assessment row above.
    if not payload["aims"] and print_fallback.get("print_text"):
        payload["aims"] = ""
    raw_blob = {
        "summary": {
            "datetime_label": entry.datetime_label,
            "tutorial_ts": tutorial_ts,
            "ttype_raw": entry.ttype_raw,
            "ttype_label": tutorial_type,
            # v4.9 provenance: distinguish a missing summary key from an
            # explicitly blank summary cell after print supplementation.
            "field_keys": sorted(summary_field_keys),
            "fields": fields,
        },
        "print_fallback": print_fallback,
    }
    payload["raw_json"] = json.dumps(raw_blob, ensure_ascii=False)

    return payload


class TutorialDatabase:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign_keys pragma could not be enabled")
        self.conn.executescript(SCHEMA_SQL)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        for table, column, definition in MIGRATIONS:
            existing = [row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")]
            if column not in existing:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        # Privacy migration: older databases may still have students.email.
        # Keep the legacy column structurally compatible but erase its values.
        student_columns = [
            row[1] for row in self.conn.execute("PRAGMA table_info(students)")
        ]
        if "email" in student_columns:
            self.conn.execute("UPDATE students SET email = NULL WHERE email IS NOT NULL")

    def log(self, action: str, target: str, status: str, message: str = ""):
        self.conn.execute(
            "INSERT INTO scrape_log (action, target, status, message, timestamp) VALUES (?, ?, ?, ?, ?)",
            (action, target, status, message, datetime.now().isoformat()),
        )

    def upsert_class(self, class_data: dict):
        self.conn.execute("""
            INSERT INTO classes
                (class_id, name, course_code, start_date, end_date, is_active, scraped_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(class_id) DO UPDATE SET
                name=excluded.name,
                course_code=excluded.course_code,
                start_date=excluded.start_date,
                end_date=excluded.end_date,
                is_active=1,
                scraped_at=excluded.scraped_at
        """, (
            class_data.get("id") or class_data.get("class_id"),
            class_data.get("name") or class_data.get("class_name"),
            class_data.get("courseCode") if class_data.get("courseCode") != "Array" else None,
            class_data.get("start_date") or _ts_to_iso(class_data.get("from")),
            class_data.get("end_date") or _ts_to_iso(class_data.get("to")),
            datetime.now().isoformat(),
        ))

    def upsert_student(self, uid: int, class_id: int, roster: dict, profile: Optional[dict] = None):
        p = profile or {}
        tut_block = roster.get("tutorial") or {}
        test_block = roster.get("test") or {}

        self.conn.execute("""
            INSERT INTO students (
                uid, class_id, name,
                cefr_level, school_name, start_date, end_date,
                attendance,
                tutorial_late, last_tutorial_ts,
                test_type, last_test_ts,
                unmarked_exit_test,
                scraped_at
            ) VALUES (
                ?, ?, ?,
                ?, ?, ?, ?,
                ?,
                ?, ?,
                ?, ?,
                ?,
                ?
            )
            ON CONFLICT(uid) DO UPDATE SET
                class_id=excluded.class_id,
                name=excluded.name,
                cefr_level=excluded.cefr_level,
                school_name=excluded.school_name,
                start_date=excluded.start_date,
                end_date=excluded.end_date,
                attendance=excluded.attendance,
                tutorial_late=excluded.tutorial_late,
                last_tutorial_ts=excluded.last_tutorial_ts,
                test_type=excluded.test_type,
                last_test_ts=excluded.last_test_ts,
                unmarked_exit_test=excluded.unmarked_exit_test,
                scraped_at=excluded.scraped_at
        """, (
            uid,
            class_id,
            roster.get("name") or p.get("name") or p.get("full_name"),
            p.get("level"),
            p.get("school", {}).get("name") if isinstance(p.get("school"), dict) else None,
            _ts_to_iso(p.get("startDate") or roster.get("start")),
            _ts_to_iso(p.get("endDate") or roster.get("end")),
            roster.get("attendance"),
            1 if tut_block.get("late") else 0,
            tut_block.get("timestamp"),
            test_block.get("type"),
            test_block.get("timestamp"),
            1 if roster.get("unmarkedExitTest") else 0,
            datetime.now().isoformat(),
        ))

    @staticmethod
    def _tutorial_quality(record: dict) -> tuple[int, int]:
        source_rank = {
            "": 0,
            "print_only": 1,
            "summary+print": 2,
        }.get(safe_str(record.get("source_method")), 0)
        meaningful = [
            "teacher_id", "teacher_name", "tutorial_type", "custom_date", "overall_level",
            "speaking", "use_of_english", "writing", "listening", "reading",
            "speaking_before", "uoe_before", "writing_before", "listening_before",
            "exam_want", "exam_which", "exam_when",
            "self_listening", "self_reading", "self_writing", "self_speaking",
            "self_vocabulary", "self_grammar", "self_pronunciation",
            "aims", "teacher_comments", "additional_comments",
            "print_url", "edit_url",
            "summary_match_method", "reconciliation_status", "reconciliation_key",
        ]
        populated = sum(1 for key in meaningful if record.get(key) not in (None, ""))
        return source_rank, populated

    @staticmethod
    def _authoritative_summary_blank_columns(record: dict) -> set[str]:
        """Return DB columns that the primary summary explicitly says are blank.

        v4.8's richness merge protected an older nonblank value even when the
        primary summary explicitly contained an empty cell. v4.9 records the
        original summary field-key set in raw_json and lets those authoritative
        blanks clear legacy print-fallback placeholders on re-run.
        """
        try:
            raw = json.loads(record.get("raw_json") or "{}")
        except Exception:
            return set()

        summary = raw.get("summary") or {}
        fields = summary.get("fields") or {}
        field_keys = set(summary.get("field_keys") or [])
        if not field_keys:
            # Old/raw records without v4.9 provenance are intentionally not
            # allowed to erase existing data.
            return set()

        tutorial_type = safe_str(record.get("tutorial_type"))
        label_to_column = {
            "Teacher": "teacher_name",
            "Tutorial Overall Level": "overall_level",
            "Reading": "reading",
            "Do you want to take an English proficiency exam?": "exam_want",
            "If yes, which exam?": "exam_which",
            "If yes, when do you want to take the exam?": "exam_when",
            "Aims": "aims",
            "Teacher's Comments": "teacher_comments",
            "Additional Comments/Accommodation (under 18s only)": "additional_comments",
        }

        if tutorial_type == "Initial":
            label_to_column.update({
                "Initial Speaking": "speaking",
                "Initial Use of English": "use_of_english",
                "Initial Writing": "writing",
                "Initial Listening": "listening",
            })
        elif tutorial_type == "Standard":
            label_to_column.update({
                "Speaking": "speaking",
                "Use of English": "use_of_english",
                "Writing": "writing",
                "Listening": "listening",
            })
        elif tutorial_type == "Final":
            label_to_column.update({
                "Initial Speaking": "speaking_before",
                "Initial Use of English": "uoe_before",
                "Initial Writing": "writing_before",
                "Initial Listening": "listening_before",
                "Speaking": "speaking",
                "Use of English": "use_of_english",
                "Writing": "writing",
                "Listening": "listening",
            })

        authoritative = set()
        for label, column in label_to_column.items():
            if label in field_keys and clean_summary_field(fields.get(label, "")) == "":
                authoritative.add(column)

        if "Assessment" in field_keys:
            assessment = parse_self_assessment(fields.get("Assessment", ""))
            for column, value in assessment.items():
                if value == "":
                    authoritative.add(column)

        return authoritative

    def store_tutorial(self, record: dict) -> str:
        """Insert a tutorial or upgrade an existing row with richer source data.

        Returns: inserted | updated | unchanged | invalid
        """
        if not record.get("tutorial_id"):
            return "invalid"

        existing_row = self.conn.execute(
            "SELECT * FROM tutorials WHERE tutorial_id = ?",
            (record["tutorial_id"],),
        ).fetchone()

        if existing_row is not None:
            existing = dict(existing_row)
            authoritative_blanks = self._authoritative_summary_blank_columns(record)
            has_authoritative_correction = any(
                column in record
                and record.get(column) in (None, "")
                and existing.get(column) not in (None, "")
                for column in authoritative_blanks
            )
            if (
                self._tutorial_quality(record) <= self._tutorial_quality(existing)
                and not has_authoritative_correction
            ):
                return "unchanged"

            merged = dict(record)
            # A richer source should not erase useful values merely because one
            # parser omitted an optional field. Zero/False values are meaningful.
            # Exception: an explicitly blank PRIMARY summary cell is an
            # authoritative value, not an omission, and may repair a legacy
            # print-fallback placeholder such as ``none``.
            for key, old_value in existing.items():
                if key in authoritative_blanks:
                    continue
                if key in merged and merged[key] in (None, "") and old_value not in (None, ""):
                    merged[key] = old_value

            assignments = [
                "student_uid=:student_uid", "teacher_id=:teacher_id",
                "teacher_id_source=:teacher_id_source", "teacher_name=:teacher_name",
                "tutorial_type=:tutorial_type", "ttype_raw=:ttype_raw", "created_at=:created_at",
                "created_date=:created_date", "absent=:absent", "custom_date=:custom_date",
                "overall_level=:overall_level", "speaking=:speaking", "use_of_english=:use_of_english",
                "writing=:writing", "listening=:listening", "reading=:reading",
                "speaking_before=:speaking_before", "uoe_before=:uoe_before",
                "writing_before=:writing_before", "listening_before=:listening_before",
                "exam_want=:exam_want", "exam_which=:exam_which", "exam_when=:exam_when",
                "self_listening=:self_listening", "self_reading=:self_reading",
                "self_writing=:self_writing", "self_speaking=:self_speaking",
                "self_vocabulary=:self_vocabulary", "self_grammar=:self_grammar",
                "self_pronunciation=:self_pronunciation", "aims=:aims",
                "teacher_comments=:teacher_comments", "additional_comments=:additional_comments",
                "source_method=:source_method", "summary_url=:summary_url",
                "print_url=:print_url", "edit_url=:edit_url",
                "summary_match_method=:summary_match_method",
                "reconciliation_status=:reconciliation_status",
                "reconciliation_key=:reconciliation_key",
                "raw_json=:raw_json", "scraped_at=:scraped_at",
            ]
            self.conn.execute(
                f"UPDATE tutorials SET {', '.join(assignments)} WHERE tutorial_id=:tutorial_id",
                merged,
            )
            return "updated"

        self.conn.execute("""
            INSERT INTO tutorials (
                tutorial_id, student_uid, teacher_id, teacher_id_source, teacher_name,
                tutorial_type, ttype_raw, created_at, created_date, absent, custom_date,
                overall_level,
                speaking, use_of_english, writing, listening, reading,
                speaking_before, uoe_before, writing_before, listening_before,
                exam_want, exam_which, exam_when,
                self_listening, self_reading, self_writing, self_speaking,
                self_vocabulary, self_grammar, self_pronunciation,
                aims, teacher_comments, additional_comments,
                source_method, summary_url, print_url, edit_url,
                summary_match_method, reconciliation_status, reconciliation_key,
                raw_json, scraped_at
            ) VALUES (
                :tutorial_id, :student_uid, :teacher_id, :teacher_id_source, :teacher_name,
                :tutorial_type, :ttype_raw, :created_at, :created_date, :absent, :custom_date,
                :overall_level,
                :speaking, :use_of_english, :writing, :listening, :reading,
                :speaking_before, :uoe_before, :writing_before, :listening_before,
                :exam_want, :exam_which, :exam_when,
                :self_listening, :self_reading, :self_writing, :self_speaking,
                :self_vocabulary, :self_grammar, :self_pronunciation,
                :aims, :teacher_comments, :additional_comments,
                :source_method, :summary_url, :print_url, :edit_url,
                :summary_match_method, :reconciliation_status, :reconciliation_key,
                :raw_json, :scraped_at
            )
        """, record)
        return "inserted"

    # Backward-compatible wrapper for callers outside archive_all().
    def insert_tutorial(self, record: dict) -> bool:
        return self.store_tutorial(record) == "inserted"

    def replace_reconciliation_collisions(self, student_uid: int, collisions: list[dict]):
        """Replace the current collision diagnostics for one student.

        This table is diagnostic/provenance data. It preserves every summary
        state involved in a same-timestamp collision without claiming that the
        deterministic list order proves which summary state belongs to which
        canonical API tutorial id.
        """
        self.conn.execute(
            "DELETE FROM reconciliation_collisions WHERE student_uid = ?",
            (int(student_uid),),
        )
        for collision in collisions:
            self.conn.execute(
                """
                INSERT INTO reconciliation_collisions (
                    student_uid, tutorial_ts, api_count, summary_count,
                    api_tutorial_ids_json, summary_entries_json,
                    mapping_status, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(student_uid),
                    int(collision.get("tutorial_ts") or 0),
                    int(collision.get("api_count") or 0),
                    int(collision.get("summary_count") or 0),
                    json.dumps(collision.get("api_tutorial_ids") or []),
                    json.dumps(collision.get("summary_entries") or [], ensure_ascii=False),
                    safe_str(collision.get("mapping_status") or "ambiguous"),
                    datetime.now().isoformat(),
                ),
            )

    def commit(self):
        self.conn.commit()

    def stats(self) -> dict:
        classes = self.conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        students = self.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        tutorials = self.conn.execute("SELECT COUNT(*) FROM tutorials").fetchone()[0]
        types = self.conn.execute("SELECT tutorial_type, COUNT(*) AS cnt FROM tutorials GROUP BY tutorial_type").fetchall()
        return {
            "classes": classes,
            "students": students,
            "tutorials": tutorials,
            "by_type": {r["tutorial_type"]: r["cnt"] for r in types},
        }

    def close(self):
        self.conn.close()


def _banner(verbose: bool, text: str):
    if verbose:
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}")


def _summary_entry_snapshot(entry: SummaryEntry) -> dict[str, Any]:
    return {
        "datetime_label": entry.datetime_label,
        "tutorial_ts": int(entry.tutorial_ts or 0),
        "ttype_raw": safe_str(entry.ttype_raw),
        "ttype_label": safe_str(entry.ttype_label),
        "print_url": safe_str(entry.print_url),
        "edit_url": safe_str(entry.edit_url),
        "fields": deepcopy(entry.fields),
    }


def pair_tutorials_with_summary(
    tutorial_list: list[dict],
    summary_entries: list[SummaryEntry],
    student_uid: Optional[int] = None,
) -> tuple[
    list[tuple[dict, Optional[SummaryEntry], dict[str, Any]]],
    int,
    list[dict[str, Any]],
]:
    """Pair canonical API tutorial rows to summary columns exactly once.

    Exact timestamp matches are preferred. Once a summary entry is consumed it
    cannot later be reused by same-date fallback. Same-timestamp collision
    groups are detected before pairing. Within a collision group a stable list
    order is used only to retain data deterministically; every such mapping is
    explicitly marked `collision_ambiguous` because the sources do not expose a
    discriminator proving API-id ↔ summary-column correspondence.
    """
    indexed_entries = list(enumerate(summary_entries))
    unconsumed: set[int] = {idx for idx, _ in indexed_entries}

    by_ts: dict[int, list[int]] = defaultdict(list)
    by_date: dict[str, list[int]] = defaultdict(list)
    for idx, entry in indexed_entries:
        if entry.tutorial_ts:
            ts = int(entry.tutorial_ts)
            by_ts[ts].append(idx)
            by_date[_ts_to_date_key(ts)].append(idx)

    api_by_ts: dict[int, list[dict]] = defaultdict(list)
    for tut in tutorial_list:
        ts = int(tut.get("timestamp") or 0)
        if ts:
            api_by_ts[ts].append(tut)

    collision_ts: set[int] = set()
    collisions: list[dict[str, Any]] = []
    all_timestamps = set(api_by_ts) | set(by_ts)
    for ts in sorted(all_timestamps):
        api_group = api_by_ts.get(ts, [])
        summary_indices = by_ts.get(ts, [])
        if len(api_group) > 1 or len(summary_indices) > 1:
            collision_ts.add(ts)
            api_ids = []
            for tut in api_group:
                tut_id = tut.get("id") or tut.get("tutorial_id")
                if tut_id is not None:
                    try:
                        api_ids.append(int(tut_id))
                    except Exception:
                        api_ids.append(tut_id)
            collisions.append({
                "student_uid": student_uid,
                "tutorial_ts": ts,
                "api_count": len(api_group),
                "summary_count": len(summary_indices),
                "api_tutorial_ids": api_ids,
                "summary_entries": [
                    _summary_entry_snapshot(summary_entries[idx])
                    for idx in summary_indices
                ],
                "mapping_status": "ambiguous",
            })

    collision_lookup = {int(c["tutorial_ts"]): c for c in collisions}
    pairs: list[tuple[dict, Optional[SummaryEntry], dict[str, Any]]] = []
    unmatched = 0

    def consume(idx: int) -> SummaryEntry:
        # `unconsumed` is the single source of truth used by both exact and
        # date fallback paths. Removing here fixes the v4.7 double-use bug.
        unconsumed.discard(idx)
        return summary_entries[idx]

    for tut in tutorial_list:
        ts = int(tut.get("timestamp") or 0)
        entry: Optional[SummaryEntry] = None
        match_method = "unmatched"

        exact_candidates = [idx for idx in by_ts.get(ts, []) if idx in unconsumed]
        if exact_candidates:
            entry = consume(exact_candidates[0])
            match_method = "exact_timestamp"
        elif ts not in collision_ts:
            # Same-date fallback is deliberately disabled for an API row whose
            # timestamp belongs to a collision group. Otherwise a second API id
            # could steal an unrelated same-day summary after its collision's
            # exact summary candidates have been exhausted.
            day_key = _ts_to_date_key(ts)
            candidates = [
                idx
                for idx in by_date.get(day_key, [])
                if idx in unconsumed
                and int(summary_entries[idx].tutorial_ts or 0) not in collision_ts
            ]
            if candidates:
                chosen = min(
                    candidates,
                    key=lambda idx: abs((summary_entries[idx].tutorial_ts or ts) - ts),
                )
                entry = consume(chosen)
                match_method = "same_date_fallback"

        collision = collision_lookup.get(ts)
        if collision is not None:
            reconciliation_status = "collision_ambiguous"
            reconciliation_key = f"{student_uid}:{ts}" if student_uid is not None else str(ts)
        elif entry is not None:
            reconciliation_status = "matched"
            reconciliation_key = ""
        else:
            reconciliation_status = "unmatched_summary"
            reconciliation_key = ""
            unmatched += 1

        meta = {
            "match_method": match_method,
            "reconciliation_status": reconciliation_status,
            "reconciliation_key": reconciliation_key,
            "collision": deepcopy(collision) if collision is not None else None,
        }
        pairs.append((tut, entry, meta))

    return pairs, unmatched, collisions

def _ts_to_date_key(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def archive_all(
    client: GELArchiverClient,
    db: TutorialDatabase,
    verbose: bool = True,
    full_profile: bool = False,
    class_id_filter: Optional[int] = None,
):
    total_tutorials = 0
    new_tutorials = 0
    updated_tutorials = 0
    teacher_ids_recovered = 0
    teacher_id_failures = 0
    summary_failures = 0
    unmatched_summary = 0
    reconciliation_collisions = 0
    ambiguous_pairs = 0

    _banner(verbose, "PHASE 1: Fetching active classes...")

    try:
        classes = client.get_classes()
    except Exception as e:
        db.log("fetch_classes", "all", "error", str(e))
        raise RuntimeError(f"Failed to fetch classes: {e}")

    if not classes:
        print("  ⚠ No active classes found")
        return

    if class_id_filter:
        classes = [c for c in classes if (c.get("id") or c.get("class_id")) == class_id_filter]
        if not classes:
            print(f"  ⚠ Class {class_id_filter} not found in active classes")
            return

    if verbose:
        print(f"  Found {len(classes)} class(es)")

    for cls in classes:
        cid = cls.get("id") or cls.get("class_id")
        cname = cls.get("name") or cls.get("class_name") or f"Class {cid}"
        db.upsert_class(cls)
        db.log("fetch_classes", str(cid), "ok", cname)
        if verbose:
            print(f"    ✓ {cname} (ID: {cid})")
    db.commit()

    _banner(verbose, "PHASE 2: Fetching students per class...")
    all_students: list[dict] = []

    for cls in classes:
        cid = cls.get("id") or cls.get("class_id")
        cname = cls.get("name") or cls.get("class_name") or f"Class {cid}"

        try:
            roster = client.get_students(cid)
        except Exception as e:
            db.log("fetch_students", str(cid), "error", str(e))
            if verbose:
                print(f"    ✗ {cname}: {e}")
            continue

        if verbose:
            print(f"  {cname}: {len(roster)} students")

        for stu in roster:
            uid = stu.get("uid") or stu.get("id") or stu.get("user_id")
            if not uid:
                continue

            profile = None
            if full_profile:
                try:
                    profile = client.get_student_profile(uid)
                except Exception as e:
                    db.log("fetch_profile", str(uid), "warn", str(e))

            db.upsert_student(uid, cid, roster=stu, profile=profile)
            all_students.append({"uid": uid, "class": cname})
            db.log("fetch_students", str(uid), "ok", cname)

        db.commit()

    if verbose:
        print(f"\n  Total students queued: {len(all_students)}")

    _banner(verbose, "PHASE 3: Fetching tutorials via summary (print fallback/cross-check)...")

    for i, stu_info in enumerate(all_students, 1):
        uid = stu_info["uid"]
        cname = stu_info["class"]

        if verbose and i % 10 == 0:
            print(f"  [{i}/{len(all_students)}] {new_tutorials} new, {updated_tutorials} upgraded, {summary_failures} summary failures, {unmatched_summary} unmatched")

        try:
            tutorial_list = client.get_tutorial_list(uid)
        except ConnectionError:
            db.log("fetch_tutorials", str(uid), "error", "session_expired")
            if verbose:
                print(f"    ✗ Student {uid}: session expired — re-run to resume")
            raise
        except Exception as e:
            db.log("fetch_tutorials", str(uid), "error", str(e))
            continue

        total_tutorials += len(tutorial_list)

        # --- Fetch the server-rendered summary table (primary normalized source) ---
        summary_entries = []
        summary_ok = False
        try:
            summary_html = client.get_tutorial_summary_html(uid)
            summary_entries = parse_tutorial_summary(summary_html, uid)
            summary_ok = True
            db.log("fetch_summary", str(uid), "ok", f"{len(summary_entries)} entries")
        except Exception as e:
            summary_failures += 1
            db.log("fetch_summary", str(uid), "warn", f"fallback_to_print: {e}")
            if summary_failures <= 3:
                dbg = getattr(client, "last_learn2_fetch", None) or {}
                print(f"\n[debug] summary fetch failed for uid={uid}")
                print(f"[debug] error: {e}")
                print(f"[debug] requested: {dbg.get('requested_url')}")
                print(f"[debug] final:     {dbg.get('final_url')}")
                print(f"[debug] status:    {dbg.get('status')}")
                print(dbg.get("head", ""))
                print()
            # DON'T continue — fall through to print-only path

        # --- Build entry list ---
        if summary_ok and summary_entries:
            # Normal path: pair API tutorials with parsed summary columns
            pairs, missed, collisions = pair_tutorials_with_summary(
                tutorial_list, summary_entries, student_uid=uid
            )
            unmatched_summary += missed
            reconciliation_collisions += len(collisions)
            ambiguous_pairs += sum(
                1 for _, _, meta in pairs
                if meta.get("reconciliation_status") == "collision_ambiguous"
            )
            db.replace_reconciliation_collisions(uid, collisions)
            for collision in collisions:
                db.log(
                    "reconciliation_collision",
                    f"{uid}/{collision['tutorial_ts']}",
                    "warn",
                    (
                        f"ambiguous same-timestamp group: "
                        f"api_ids={collision['api_tutorial_ids']} "
                        f"summary_count={collision['summary_count']}"
                    ),
                )
            process_list = pairs  # list of (tut_dict, SummaryEntry|None, reconciliation_meta)
        else:
            # Summary unavailable/unparseable — create stub entries from the
            # canonical API tutorial list and rely on the print page fallback.
            process_list = []
            for tut in tutorial_list:
                tut_id = tut.get("id") or tut.get("tutorial_id")
                ts = int(tut.get("timestamp") or 0)
                entry = SummaryEntry(
                    datetime_label="",
                    tutorial_ts=ts,
                    ttype_raw="",
                    ttype_label="Unknown",
                    print_url=f"/study/tutorials/print/{uid}/{ts}",
                    edit_url="",
                    fields={},
                )
                process_list.append((tut, entry, {
                    "match_method": "summary_unavailable",
                    "reconciliation_status": "summary_unavailable",
                    "reconciliation_key": "",
                    "collision": None,
                }))

        for tut, entry, reconciliation_meta in process_list:
            tut_id = tut.get("id") or tut.get("tutorial_id")
            if not tut_id:
                continue

            if entry is None:
                db.log("pair_summary", f"{uid}/{tut_id}", "warn", f"no summary match for ts={tut.get('timestamp')}; using print fallback")
                entry = SummaryEntry(
                    datetime_label="",
                    tutorial_ts=int(tut.get("timestamp") or 0),
                    ttype_raw="",
                    ttype_label="Unknown",
                    print_url=f"/study/tutorials/print/{uid}/{int(tut.get('timestamp') or 0)}",
                    edit_url="",
                    fields={},
                )

            print_fallback = {}
            try:
                print_html = client.get_tutorial_print_html(uid, int(tut.get("timestamp") or entry.tutorial_ts))
                print_fallback = parse_print_page_fallback(print_html)
            except Exception as e:
                db.log("fetch_print", f"{uid}/{tut_id}", "warn", str(e))

            tutorial_ts = int(tut.get("timestamp") or entry.tutorial_ts or 0)
            record = build_record_from_summary(
                student_uid=uid,
                tutorial_id=int(tut_id),
                tutorial_ts=tutorial_ts,
                entry=entry,
                print_fallback=print_fallback,
            )

            record["summary_match_method"] = safe_str(
                reconciliation_meta.get("match_method")
            )
            record["reconciliation_status"] = safe_str(
                reconciliation_meta.get("reconciliation_status")
            )
            record["reconciliation_key"] = safe_str(
                reconciliation_meta.get("reconciliation_key")
            )
            try:
                raw_blob = json.loads(record.get("raw_json") or "{}")
            except Exception:
                raw_blob = {}
            raw_blob["reconciliation"] = {
                "match_method": record["summary_match_method"],
                "status": record["reconciliation_status"],
                "key": record["reconciliation_key"],
            }
            if reconciliation_meta.get("collision") is not None:
                # Collision table is canonical for the full group snapshot;
                # include the compact group facts here for per-row provenance.
                collision = reconciliation_meta["collision"]
                raw_blob["reconciliation"]["collision"] = {
                    "tutorial_ts": collision.get("tutorial_ts"),
                    "api_tutorial_ids": collision.get("api_tutorial_ids"),
                    "summary_count": collision.get("summary_count"),
                    "mapping_status": collision.get("mapping_status"),
                }
            record["raw_json"] = json.dumps(raw_blob, ensure_ascii=False)

            # v4.7: recover the original historical teacher id from the raw
            # edit form. Live GEL sets it with inline JavaScript such as
            # $("#tid").val("326743"); no JS execution is required.
            edit_ttype_raw = safe_str(entry.ttype_raw)
            if not edit_ttype_raw:
                edit_ttype_raw = {
                    "Standard": "0",
                    "Final": "1",
                    "Initial": "2",
                }.get(record.get("tutorial_type"), "")

            if edit_ttype_raw and tutorial_ts:
                if not record.get("edit_url"):
                    record["edit_url"] = f"/study/tutorials/add/{uid}/{tutorial_ts}/{edit_ttype_raw}"
                try:
                    edit_html = client.get_tutorial_edit_html(uid, tutorial_ts, edit_ttype_raw)
                    teacher_meta = parse_teacher_from_edit_html(edit_html)
                    teacher_id = teacher_meta.get("teacher_id")

                    if teacher_id is not None:
                        record["teacher_id"] = int(teacher_id)
                        record["teacher_id_source"] = safe_str(teacher_meta.get("teacher_id_source"))
                        teacher_ids_recovered += 1

                        edit_teacher_name = safe_str(teacher_meta.get("teacher_name"))
                        summary_teacher_name = safe_str(record.get("teacher_name"))

                        if edit_teacher_name and not summary_teacher_name:
                            record["teacher_name"] = edit_teacher_name
                        elif (
                            edit_teacher_name
                            and summary_teacher_name
                            and re.sub(r"\s+", " ", edit_teacher_name).casefold()
                            != re.sub(r"\s+", " ", summary_teacher_name).casefold()
                        ):
                            db.log(
                                "teacher_id",
                                f"{uid}/{tut_id}",
                                "warn",
                                f"tid={teacher_id} option_name={edit_teacher_name!r} summary_name={summary_teacher_name!r}",
                            )

                        if teacher_meta.get("tid_select_present") and not teacher_meta.get("teacher_option_found"):
                            db.log(
                                "teacher_id",
                                f"{uid}/{tut_id}",
                                "warn",
                                f"tid={teacher_id} recovered but matching option was not found",
                            )
                        else:
                            db.log(
                                "teacher_id",
                                f"{uid}/{tut_id}",
                                "ok",
                                f"tid={teacher_id} source={record['teacher_id_source']}",
                            )
                    else:
                        teacher_id_failures += 1
                        db.log(
                            "teacher_id",
                            f"{uid}/{tut_id}",
                            "warn",
                            "historical edit form contained no recoverable tid value",
                        )
                except Exception as e:
                    teacher_id_failures += 1
                    db.log("fetch_edit", f"{uid}/{tut_id}", "warn", str(e))
            else:
                teacher_id_failures += 1
                db.log(
                    "fetch_edit",
                    f"{uid}/{tut_id}",
                    "warn",
                    "could not determine ttype/timestamp for historical edit form",
                )

            store_result = db.store_tutorial(record)
            if store_result == "inserted":
                new_tutorials += 1
                db.log("store_tutorial", f"{uid}/{tut_id}", "ok", "inserted")
            elif store_result == "updated":
                updated_tutorials += 1
                db.log("store_tutorial", f"{uid}/{tut_id}", "ok", "upgraded with richer summary data")
            elif store_result == "unchanged":
                db.log("store_tutorial", f"{uid}/{tut_id}", "skip", "existing row is equal or richer")
            else:
                db.log("store_tutorial", f"{uid}/{tut_id}", "warn", "invalid tutorial record")

        if i % 20 == 0:
            db.commit()

    db.commit()

    stats = db.stats()
    print(f"\n{'='*60}")
    print("ARCHIVE COMPLETE")
    print(f"{'='*60}")
    print(f"  Classes:             {stats['classes']}")
    print(f"  Students:            {stats['students']}")
    print(f"  Tutorials:           {stats['tutorials']} total, {new_tutorials} new, {updated_tutorials} upgraded")
    print(f"  Summary failures:    {summary_failures}")
    print(f"  Unmatched summaries: {unmatched_summary}")
    print(f"  Collisions:          {reconciliation_collisions} groups, {ambiguous_pairs} ambiguous API rows")
    print(f"  Teacher IDs:         {teacher_ids_recovered} recovered, {teacher_id_failures} unavailable")
    print(f"  API/HTTP calls:      {client._request_count}")
    print(f"  By type:")
    for ttype, count in stats.get("by_type", {}).items():
        print(f"    {ttype}: {count}")
    print(f"{'='*60}\n")


_OBFUSCATION_KEY = "GELApp2024SecureKey"


def _xor_deobfuscate(encoded: str, key: str = _OBFUSCATION_KEY) -> str:
    try:
        data = base64.b64decode(encoded.encode()).decode("latin-1")
        return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))
    except Exception:
        return ""


def get_credentials() -> tuple[str, str]:
    creds_path = Path("credentials.json")
    saved_user = saved_pass = ""

    if creds_path.exists():
        try:
            data = json.loads(creds_path.read_text(encoding="utf-8"))
            saved_user = data.get("username", "")
            raw_pass = data.get("password", "")
            if raw_pass:
                saved_pass = _xor_deobfuscate(raw_pass)
        except Exception:
            pass

    print("\nGEL Tutorial Archiver — Login")

    if saved_user:
        entered = input(f"Username [{saved_user}]: ").strip()
        username = entered or saved_user
    else:
        username = input("Username: ").strip()

    if saved_pass and username == saved_user:
        entered = input("Password [saved]: ").strip()
        password = entered or saved_pass
    else:
        import getpass
        password = getpass.getpass("Password: ")

    if not username or not password:
        print("Error: username and password are required")
        sys.exit(1)

    return username, password


def main():
    parser = argparse.ArgumentParser(
        description="Archive GEL tutorials to SQLite using summary/print pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tutorial_down4_resilient.py
  python tutorial_down4_resilient.py --class-id 2549
  python tutorial_down4_resilient.py --full-profile
  python tutorial_down4_resilient.py --stats-only
        """,
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"Database path (default: {DEFAULT_DB})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Seconds between calls (default: {DEFAULT_DELAY})")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument("--stats-only", action="store_true", help="Print DB stats and exit")
    parser.add_argument("--full-profile", action="store_true", help="Fetch /staff/students/{uid} profile for each student")
    parser.add_argument("--class-id", type=int, default=None, metavar="ID", help="Only process a single class")
    parser.add_argument("--probe-detail-endpoint", action="store_true",
                        help="Deprecated. Kept for compatibility; downloader no longer relies on /report?id=...")

    args = parser.parse_args()
    verbose = not args.quiet

    db = TutorialDatabase(args.db)

    if args.stats_only:
        print(json.dumps(db.stats(), indent=2))
        db.close()
        return

    username, password = get_credentials()
    client = GELArchiverClient(delay=args.delay)

    if verbose:
        print("\nLogging in…")

    if not client.login(username, password):
        print("Login failed!")
        db.log("login", username, "error", "authentication_failed")
        db.close()
        sys.exit(1)

    db.log("login", username, "ok")
    if verbose:
        print("  ✓ Logged in")

    if args.probe_detail_endpoint:
        print("\nNote: --probe-detail-endpoint is deprecated.")
        print("The downloader now uses /staff/students/{uid}/tutorials + /study/tutorials/summary/{uid}")
        print("and /study/tutorials/print/{uid}/{timestamp} instead of /report?id=...\n")

    try:
        archive_all(
            client,
            db,
            verbose=verbose,
            full_profile=args.full_profile,
            class_id_filter=args.class_id,
        )
    except ConnectionError:
        print("\n✗ Session expired mid-run. Re-run to resume (duplicates are skipped).")
        db.log("archive", "all", "error", "session_expired_mid_scrape")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        db.log("archive", "all", "error", str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
