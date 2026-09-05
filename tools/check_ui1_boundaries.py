#!/usr/bin/env python3
"""UI1a/b static boundary check: no Writer-side GEL/archive writes and no frontend authority leaks."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "writer-ui"
RUST = UI / "src-tauri" / "src" / "lib.rs"
API = UI / "src" / "api.ts"
LOGIN = UI / "src" / "components" / "LoginPanel.tsx"
TYPES = UI / "src" / "types.ts"
CONTRACT = ROOT / "contracts" / "ui1_writer.json"
CARGO = UI / "src-tauri" / "Cargo.toml"
SEMANTIC = ROOT / "gel-core" / "src" / "semantic.rs"

EXPECTED_COMMANDS = {
    "ui1_session_status",
    "ui1_login",
    "ui1_logout",
    "ui1_archive_status",
    "ui1_sync_archive",
    "ui1_list_classes",
    "ui1_list_students",
    "ui1_list_tutorials",
    "ui1_open_new_draft",
    "ui1_open_revision_draft",
    "ui1_get_draft",
    "ui1_apply_draft_edit",
    "ui1_discard_draft",
    "ui1_submit_draft",
    "ui1_harper_check",
    "ui1_harper_dictionary_list",
    "ui1_harper_dictionary_add",
    "ui1_harper_dictionary_remove",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    try:
        for path in [RUST, API, LOGIN, TYPES, CONTRACT, CARGO, SEMANTIC]:
            require(path.exists(), f"missing UI1 artifact: {path.relative_to(ROOT)}")

        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        require(contract.get("contract_id") == "ui1_writer", "UI1 contract_id drifted")
        require(contract.get("contract_version") == 14, "UI1 W2 contract_version drifted")
        require(contract.get("status") in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "W2 status drifted")
        require(set(contract.get("initial_command_allowlist", [])) == EXPECTED_COMMANDS, "UI1 command allowlist drifted")
        require(contract["architecture"]["react_role"] == "presentation_only", "React must remain presentation-only")
        require("ui1_submit_draft" in contract["architecture"]["submission"] or contract["architecture"]["submission"] == "absent from UI1 command surface", "UI1 submission authority drifted")
        require(contract["architecture"]["draft_persistence"].startswith("none"), "UI1 tutorial drafts must remain ephemeral")
        require(contract["harper_future_state"]["persistent_dictionary"] is True, "UI1 plan must retain persistent Harper dictionary concept")
        require(contract["harper_future_state"]["persistent_tutorial_drafts"] is False, "Harper persistence must not imply persistent tutorial drafts")

        rust = RUST.read_text(encoding="utf-8")
        handler_match = re.search(r"tauri::generate_handler!\[(.*?)\]", rust, flags=re.S)
        require(handler_match is not None, "missing Tauri generate_handler allowlist")
        handler_commands = set(re.findall(r"\b(ui1_[a-z0-9_]+)\b", handler_match.group(1)))
        require(handler_commands == EXPECTED_COMMANDS, f"Tauri command surface drifted: {sorted(handler_commands)}")

        require("ui1_harper_check" in rust and "HarperDictionaryRepository" in rust, "UI1d Rust Harper command boundary missing")
        require("writer_operation" in rust, "UI1d dictionary mutation must use the existing writer operation lock")
        require("HARPER_DICTIONARY_ENV" in rust, "UI1d dictionary override must be environment-configurable")
        forbidden_rust = {
            "ArchiveSyncRepository": "UI1 must not expose the low-level archive sync writer",
            "build_tutorial_post_payload": "UI1 must not build GEL POST payloads",
            "build_new_tutorial_post_payload": "UI1 must not build New GEL POST payloads",
            "build_revision_tutorial_post_payload": "UI1 must not build Revision GEL POST payloads",
            ".post(": "UI1 Tauri service must not own direct HTTP POST transport",
            "reqwest::": "UI1 must use current GelSession rather than direct HTTP transport",
            "rusqlite::": "UI1 must use ArchiveRepository rather than direct SQLite",
        }
        for token, message in forbidden_rust.items():
            require(token not in rust, message)
        require("ArchiveRepository::open_read_only" in rust, "UI1 archive navigation must open D2 read-only repository")
        require("RustArchiver::sync_full" in rust, "UI1 A2 sync command must delegate to RustArchiver")
        require("get_new_tutorial_form_html" in rust and "build_new_form_state" in rust, "UI1 New draft must use N2b/N2c authority")
        require("get_tutorial_edit_html" in rust and "validate_edit_form" in rust and "build_revision_form_state" in rust, "UI1 Revision draft must use C1/C2 authority")
        require("apply_tutorial_draft_edit" in rust, "UI1 application service must delegate semantic edits to rust_semantic_form")
        require("GEL_ARCHIVE_DB" in rust, "UI1 archive override must remain available")
        require('DEFAULT_ARCHIVE_DB_NAME: &str = "gel-new-v2.db"' in rust, "UI1 default archive filename drifted")
        require('env!("CARGO_MANIFEST_DIR")' in rust and '.join("..")' in rust, "UI1 non-Windows/failure fallback must remain project-root based rather than process CWD")
        require("std::env::current_exe()" in rust and 'cfg!(target_os = "windows")' in rust, "UI1 Windows default must resolve from the running executable")
        require("executable_path.and_then(Path::parent)" in rust and "executable_dir.join(DEFAULT_ARCHIVE_DB_NAME)" in rust, "UI1 Windows default must be beside the executable")
        require("resolve_default_archive_path" in rust and "project_root.join(DEFAULT_ARCHIVE_DB_NAME)" in rust, "UI1 platform-default resolver/fallback missing")
        require("Connection::open" not in rust and "create_dir_all" not in rust, "Writer Tauri service must not create/open writable archive storage directly")

        semantic = SEMANTIC.read_text(encoding="utf-8")
        edit_match = re.search(r"pub enum TutorialDraftEdit\s*\{(.*?)\n\}", semantic, flags=re.S)
        require(edit_match is not None, "rust_semantic_form missing TutorialDraftEdit")
        edit_body = edit_match.group(1)
        for forbidden in ["Teacher", "Timestamp", "Datetime", "TutorialId", "StudentUid", "TutorialType", "GelField", "Post"]:
            require(
                re.search(rf"\bSet{forbidden}\b", edit_body) is None,
                f"typed edit surface must not expose Set{forbidden}",
            )
        require("apply_tutorial_draft_edit" in semantic, "candidate semantic edit function missing")
        require("SetInitialCourseType" in edit_body, "UI1c0 typed edit surface must include governed Initial course type")
        require("SetExamField" not in edit_body, "UI1c0 must not expose hidden Initial exam fields")
        require("DraftValidationIssue" in semantic, "UI1c0 structured semantic validation missing")
        require("TEACHER_COMMENTS_MAX_CHARS" in semantic, "970-character Rust authority missing")
        require("pub const fn all()" in semantic, "canonical CEFR option enumeration must remain Rust-owned")

        cargo = CARGO.read_text(encoding="utf-8")
        require('gel-core = { path = "../../gel-core" }' in cargo, "UI1 must depend on current local gel-core")
        require("reqwest" not in cargo and "rusqlite" not in cargo, "UI1 Tauri crate must not acquire direct transport/SQLite dependencies")

        api = API.read_text(encoding="utf-8")
        invoked = set(re.findall(r'invoke(?:<[^>]+>)?\("(ui1_[a-z0-9_]+)"', api))
        require(invoked == EXPECTED_COMMANDS, f"frontend invoke surface drifted: {sorted(invoked)}")
        for token in ["submit_tutorial", "post_tutorial", "update_tutorial", "delete_tutorial", "generic_http", "request_url", "set_teacher", "build_raw_post"]:
            require(token not in api.lower(), f"frontend API exposes forbidden capability {token}")

        login = LOGIN.read_text(encoding="utf-8")
        require("finally" in login and 'setPassword("")' in login, "password must clear in finally")
        frontend_text = "\n".join(path.read_text(encoding="utf-8") for path in (UI / "src").rglob("*.ts*") if path.is_file())
        require("localStorage" not in frontend_text and "sessionStorage" not in frontend_text, "UI1a/b must not persist frontend state")
        require("dropdown-" not in frontend_text and "trecs-79" not in frontend_text, "opaque GEL field IDs must not enter React")
        require("const LEVELS" not in frontend_text and "draft.formContract.levelOptions" in frontend_text, "React must receive CEFR options from Rust rather than define a canonical list")

        print("check:ui1-boundaries PASS — explicit Tauri allowlist + read-only navigation + delegated A2 RustArchiver sync + Rust-owned ephemeral draft + no GEL/raw-SQLite write authority")
        return 0
    except (AssertionError, json.JSONDecodeError) as exc:
        print(f"check:ui1-boundaries FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
