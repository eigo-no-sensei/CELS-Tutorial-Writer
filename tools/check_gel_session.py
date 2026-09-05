#!/usr/bin/env python3
"""Dependency-minimal N1 Rust GEL read-only session boundary check."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "gel_read_only_session.json"
SOURCE = ROOT / "gel-core" / "src" / "gel_session.rs"
LIVE = ROOT / "gel-core" / "src" / "bin" / "check_gel_read_only_live.rs"
CARGO = ROOT / "gel-core" / "Cargo.toml"
LIB = ROOT / "gel-core" / "src" / "lib.rs"
COMPONENTS = ROOT / "contracts" / "component_boundaries.json"
OWNERSHIP = ROOT / "contracts" / "state_ownership.json"
GATE = ROOT / "contracts" / "release_gate.json"
PLAN = ROOT / "development_plan.json"


class CheckError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    try:
        for path in [CONTRACT, SOURCE, LIVE, CARGO, LIB, COMPONENTS, OWNERSHIP, GATE, PLAN]:
            require(path.exists(), f"missing N1 artifact {path.relative_to(ROOT)}")

        contract = load(CONTRACT)
        require(contract.get("contract_id") == "gel_read_only_session", "bad N1 contract_id")
        require(contract.get("contract_version") == 2, "N1/N2b session contract_version must be 2")
        require(contract.get("status") == "active", "N1 contract must be active")
        auth = contract["authentication"]
        require(auth["login_post_count"] == 2, "N1 must authorize exactly two login POSTs")
        require(auth["credential_retention"] == "none", "N1 credential retention must be none")
        require(contract["network_authority"]["generic_request_api"] is False, "N1 generic request API must be false")
        require(contract["network_authority"]["gel_tutorial_write_authority"] is False, "N1 tutorial write authority must be false")
        require(contract["live_acceptance"]["release_gate_network_access"] is False, "N1 release gate must remain offline")
        new_surface = next((x for x in contract["read_surface"] if x["id"] == "new_tutorial_form"), None)
        require(new_surface is not None, "N2b fixed New-form GET missing from session contract")
        require(new_surface["method"] == "GET", "N2b New-form acquisition must be GET")
        require(new_surface["path_template"] == "/study/tutorials/add/{student_uid}/0/{ttype_raw}", "N2b New-form route must use fixed zero locator")

        source = SOURCE.read_text(encoding="utf-8")
        production_source = source.split("#[cfg(test)]\nmod tests", 1)[0]
        require(f'const API_BASE: &str = "{contract["origins"]["api_base"]}";' in source, "Rust API origin drifted from N1 contract")
        require(f'const LEARN2_BASE: &str = "{contract["origins"]["learn2_base"]}";' in source, "Rust Learn2 origin drifted from N1 contract")
        require(f'const LOGIN_PATH: &str = "{auth["login_path"]}";' in source, "Rust login path drifted from N1 contract")
        require(production_source.count(".post(") == 2, "N1 production Rust source must contain exactly two POST calls")
        require(".put(" not in production_source and ".patch(" not in production_source and ".delete(" not in production_source, "N1 production Rust source contains a forbidden mutation HTTP method")
        require(not re.search(r"pub\s+fn\s+(?:request|post|put|patch|delete)\b", production_source), "N1 exposes a generic/mutation transport method")
        require(not re.search(r"pub\s+fn\s+(?:client|cookies?|cookie_store)\b", production_source), "N1 exposes private HTTP/cookie capability")
        require("cookie_store(true)" in production_source, "N1 Rust session must own a cookie store")
        require("pub struct GelSession" in production_source, "N1 GelSession type missing")
        require("get_new_tutorial_form_html" in production_source, "N2b fixed New-form GET method missing")
        require('"/study/tutorials/add/{student_uid}/0/{ttype_raw}"' in production_source, "N2b New-form GET path drifted")
        struct_match = re.search(r"pub struct GelSession\s*\{(?P<body>.*?)\n\}", production_source, re.S)
        require(struct_match is not None, "cannot inspect GelSession fields")
        struct_body = struct_match.group("body").lower()
        require("password" not in struct_body and "username" not in struct_body, "GelSession must not retain username/password fields")
        require("client: Client" in struct_match.group("body"), "GelSession must privately own the HTTP client")
        for method in [
            "login",
            "get_classes",
            "get_students",
            "get_student_profile",
            "get_tutorial_list_json",
            "get_tutorial_list",
            "get_tutorial_summary_html",
            "get_tutorial_print_html",
            "get_new_tutorial_form_html",
            "get_tutorial_edit_html",
        ]:
            require(re.search(rf"pub\s+fn\s+{re.escape(method)}\b", production_source) is not None, f"N1 public method missing: {method}")
        for field in contract["privacy"]["student_fields_removed_immediately"]:
            require(f'"{field}"' in source, f"N1 privacy filter missing {field!r}")
        require("GEL authentication rejected" in source, "N1 redacted authentication failure missing")
        require("response body" not in production_source.lower(), "N1 source unexpectedly references response-body diagnostics")
        for relative in [
            "src/archive_repository.rs",
            "src/edit_form_parser.rs",
            "src/edit_form_validation.rs",
            "src/print_parser.rs",
            "src/reconciliation.rs",
            "src/semantic.rs",
            "src/summary_parser.rs",
        ]:
            text = (ROOT / "gel-core" / relative).read_text(encoding="utf-8").lower()
            require("edit[pass]" not in text and "cookie_store" not in text, f"N1 credential/cookie implementation leaked into {relative}")

        cargo = CARGO.read_text(encoding="utf-8")
        require('reqwest = { version = "0.12"' in cargo, "N1 reqwest dependency missing")
        for feature in ["blocking", "cookies", "json", "rustls-tls"]:
            require(f'"{feature}"' in cargo, f"N1 reqwest feature missing: {feature}")
        require('rpassword = "7"' in cargo, "N1 live probe secure password-input dependency missing")

        lib = LIB.read_text(encoding="utf-8")
        require("pub mod gel_session;" in lib, "N1 module not public from gel-core")
        require("pub use gel_session::GelSession;" in lib, "N1 GelSession not re-exported")

        live = LIVE.read_text(encoding="utf-8")
        require("rpassword::prompt_password" in live, "N1 live probe must prompt password without echo")
        require("get_tutorial_list" in live and "get_tutorial_summary_html" in live and "get_tutorial_print_html" in live and "get_tutorial_edit_html" in live, "N1 live probe must exercise all tutorial read sources")
        require("validate_edit_form" in live, "N1 live probe must prove C1-valid historical edit retrieval")
        require(".post(" not in live and ".delete(" not in live and ".put(" not in live and ".patch(" not in live, "N1 live probe must not own HTTP mutation calls")
        require("GEL tutorial writes: 0" in live, "N1 live probe must explicitly report zero tutorial writes")

        components = load(COMPONENTS)
        component = next((item for item in components["components"] if item["id"] == "rust_gel_session"), None)
        require(component is not None, "rust_gel_session is not an active component")
        require("rust_gel_session" not in components.get("planned_not_active", []), "rust_gel_session still marked planned")
        require("normalized_local_archive" in component["must_not_write"], "N1 component must not write canonical archive")
        require("tutorial_post_payload" in component["must_not_write"], "N1 component must not write POST payload state")

        ownership = load(OWNERSHIP)
        states = {item["id"]: item for item in ownership["state_classes"]}
        require(states["authenticated_gel_session"]["permitted_writers"] == ["rust_gel_session"], "N1 authenticated session ownership drifted")
        require("rust_gel_session" in states["gel_api_json"]["permitted_writers"], "N1 API response materialization ownership missing")
        require(states["normalized_local_archive"]["permitted_writers"] == ["rust_archive_sync_repository"], "A2 archive ownership must remain Rust while N1 itself has no archive write capability")

        gate = load(GATE)
        checks = {item["id"]: item for item in gate["checks"]}
        require(checks["gel_session"]["command"] == ["python", "-S", "tools/check_gel_session.py"], "N1 release-gate command drifted")
        require(set(checks["gel_session"]["profiles"]) == {"portable", "strict"}, "N1 release-gate profiles drifted")

        plan = load(PLAN)
        phase = next(item for item in plan["phases"] if item["id"] == "N1")
        require(phase["status"] == "complete_strictly_accepted_live_validated", "N1 plan status must reflect strict+live acceptance")
        require(phase.get("evaluation", {}).get("status") == "approved_with_amendments", "N1 plan evaluation missing")
    except (CheckError, KeyError, StopIteration, json.JSONDecodeError) as exc:
        print(f"check:gel-session FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:gel-session PASS — fixed read-only transport + private session credentials/cookies + login-only POST authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
