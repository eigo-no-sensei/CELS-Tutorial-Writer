#!/usr/bin/env python3
"""Offline governance/safety check for the N2-PW1 Playwright harness."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "n2_playwright_zero_write_evidence.json"
HARNESS = ROOT / "tools" / "playwright" / "n2_zero_write_evidence.py"
CORE = ROOT / "tools" / "playwright" / "n2_zero_write_evidence_core.py"
GITIGNORE = ROOT / ".gitignore"


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def function_source(module: ast.Module, source: str, name: str) -> str:
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise CheckError(f"missing function {name}")


def check_contract(data: dict) -> None:
    require(data.get("contract_id") == "n2_playwright_zero_write_evidence", "bad PW1 contract_id")
    require(data.get("contract_version") == 8, "PW1 contract_version must be 8")
    network = data["network_state_machine"]
    require(network.get("firewall_installed_before_first_navigation") is True, "PW1 firewall must predate navigation")
    require(network.get("service_workers_blocked") is True, "PW1 must block service workers")
    origin_policy = network["origin_policy"]
    require(origin_policy["gel_origin"]["unexpected_mutation"] == "abort_and_fail_closed", "PW1 unexpected GEL mutations must fail closed")
    require(origin_policy["gel_origin"]["body_may_be_inspected"] is False, "PW1 unexpected GEL mutation body must not be inspected")
    third_party = origin_policy["third_party_origins"]
    require(third_party["mutating_requests"] == "abort_nonfatal", "PW1 third-party mutations must abort without becoming GEL drift")
    require(third_party["body_may_be_inspected"] is False and third_party["headers_may_be_inspected"] is False, "PW1 third-party mutation body/headers must not be inspected")
    require(third_party["persisted_evidence"] == "aggregate_count_only", "PW1 may persist only an aggregate third-party block count")
    require(third_party["terminal_diagnostic_fields"] == ["phase", "method", "origin", "redacted_path"], "PW1 third-party diagnostic allowlist drifted")
    progress = network["progress_diagnostic"]
    require(progress["enabled"] is True, "PW1 progress diagnostic must be enabled")
    require(progress["destination"] == "stdout_only_not_persisted", "PW1 progress diagnostic must be terminal-only")
    require(progress["identities_or_form_values_may_be_printed"] is False, "PW1 progress diagnostic must not print identities/form values")
    require(progress["allowed_stages"] == ["authenticated", "baseline_summary", "latest_revision_snapshot", "new_form_standard", "new_form_initial", "new_form_final", "revision_probe", "final_verification", "evidence_evaluation", "privacy_validation", "evidence_written"], "PW1 progress stage allowlist drifted")
    auth = network["authentication"]
    require(auth["interactive_login_page"]["path"] == "/corelogin/", "PW1 interactive login page drifted")
    require(auth["interactive_login_page"]["method"] == "GET", "PW1 interactive login page must be GET")
    require(auth["allowed_mutation"]["path"] == "/user/login", "PW1 login mutation route drifted")
    require(auth["allowed_mutation"]["body_may_be_inspected"] is False, "PW1 must not inspect login body")
    require(auth["allowed_mutation"]["headers_may_be_inspected"] is False, "PW1 must not inspect login headers")
    diagnostic = auth["blocked_mutation_diagnostic"]
    require(diagnostic["enabled"] is True, "PW1 auth blocked-request diagnostic must be enabled")
    require(diagnostic["destination"] == "stderr_only_not_persisted", "PW1 auth diagnostic must be terminal-only")
    require(diagnostic["fields"] == ["phase", "method", "origin", "redacted_path"], "PW1 auth diagnostic field allowlist drifted")
    require(diagnostic["query_may_be_printed"] is False, "PW1 auth diagnostic must not print query parameters")
    require(diagnostic["body_may_be_inspected"] is False, "PW1 auth diagnostic must not inspect request body")
    require(diagnostic["headers_may_be_inspected"] is False, "PW1 auth diagnostic must not inspect request headers")
    two_stage = auth["two_stage_manual_login"]
    require(two_stage["stage_1"]["page"] == "/corelogin/", "PW1 stage-1 login page drifted")
    require(two_stage["stage_2_when_required"]["page"] == "/user/login", "PW1 stage-2 login page drifted")
    require(two_stage["verification_after_stage_1"]["method"] == "GET", "PW1 auth verification must be GET-only")
    require(two_stage["verification_after_stage_1"]["path"] == "/administration/students", "PW1 Learn2 auth verification path drifted")
    require(two_stage["evidence_phase_transition"].startswith("Only after a GET-only Learn2 session verification"), "PW1 must not enter evidence on Enter alone")
    session_diag = auth["session_verification_diagnostic"]
    require(session_diag["fields"] == ["login_posts_forwarded", "learn2_authenticated_get", "final_origin", "redacted_final_path", "password_control_present"], "PW1 session verification diagnostic allowlist drifted")
    require(session_diag["credential_values_may_be_read"] is False, "PW1 auth verification must not read credentials")
    expected = network["evidence"]["expected_tutorial_mutation"]
    require(expected["path"] == "/study/tutorials/process", "PW1 tutorial process path drifted")
    require(expected["network_action"] == "always_abort", "PW1 expected tutorial submission must always abort")
    require(network["evidence"]["forwarded_tutorial_mutations"] == 0, "PW1 may forward zero tutorial mutations")
    privacy = data["credential_privacy"]
    require(privacy["harness_credential_authority"] == "none", "PW1 harness must have no credential authority")
    require(privacy["raw_tutorial_post_body_persisted"] is False, "PW1 must not persist raw POST body")
    require(privacy["student_identity_persisted"] is False, "PW1 must not persist student identity")
    require(privacy["teacher_names_or_raw_ids_persisted"] is False, "PW1 must not persist teacher names/ids")
    teacher = data["teacher_semantics"]
    require(teacher["server_reassignment_acceptance"] == "unresolved", "PW1 must not claim server reassignment acceptance")
    require(teacher["server_reassignment_authorization"] == "unresolved", "PW1 must not claim reassignment authorization")
    pre = data["prepopulation"]
    require(pre["source"] == "latest_tutorial" and pre["source_status"] == "established_before_PW1", "PW1 must treat latest tutorial source as established")
    require(pre["persist_values"] is False, "PW1 prepopulation evidence must persist relationships, not values")
    require(pre.get("forbidden_inference", "").startswith("Cross-field provenance"), "PW1 must forbid equality-based cross-field provenance")
    require("copied_from_source_field" not in pre.get("classifications", []), "PW1 must retire copied_from_source_field classification")
    require("matches_multiple_source_fields" not in pre.get("classifications", []), "PW1 must retire matches_multiple_source_fields classification")
    residual = data.get("residual_status", {})
    require(residual.get("submit_serialization_observation") == "deferred_non_blocking", "PW1 submit serialization residual must be deferred")
    require(residual.get("n2_gate") is False, "PW1 submit serialization residual must not block N2")
    acceptance = data["acceptance"]
    require(acceptance["release_gate_network_access"] is False, "PW1 release gate must remain offline")


def check_harness_source() -> None:
    source = HARNESS.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(HARNESS))

    banned_strings = [
        "--username",
        "--password",
        "credentials.json",
        "GEL_PASSWORD",
        "GEL_USERNAME",
        "storage_state=",
        "record_har",
        "record_video",
        "tracing.start",
        ".screenshot(",
        "all_headers(",
        "headers_array(",
    ]
    for item in banned_strings:
        require(item not in source, f"PW1 harness contains forbidden credential/persistence API marker {item!r}")

    auth_handler = function_source(module, source, "_handle_authentication_mutation")
    for forbidden in ["post_data", "header_value", ".headers", "input_value"]:
        require(forbidden not in auth_handler, f"PW1 authentication mutation handler must not access {forbidden}")
    require("route.continue_()" in auth_handler, "PW1 login handler must explicitly forward canonical login POST")

    handle_source = function_source(module, source, "handle")
    require('network_origin_authority(request.url)' in handle_source, "PW1 must classify request authority before GEL mutation handling")
    require("self._abort_third_party" in handle_source, "PW1 must block third-party mutations separately")
    require("self._abort_unexpected_gel" in handle_source, "PW1 must retain fail-closed GEL mutation path")

    diagnostic_handler = function_source(module, source, "_emit_blocked_diagnostic")
    require("safe_network_diagnostic" in diagnostic_handler, "PW1 auth block diagnostic must use privacy-safe reducer")
    for forbidden in ["post_data", "header_value", ".headers", "input_value", "request.url}", "request.url,"]:
        require(forbidden not in diagnostic_handler, f"PW1 auth diagnostic must not access/print {forbidden}")
    for allowed in ["phase", "method", "origin", "redacted_path"]:
        require(allowed in diagnostic_handler, f"PW1 auth diagnostic must print {allowed}")

    third_party_handler = function_source(module, source, "_abort_third_party")
    require("route.abort" in third_party_handler, "PW1 third-party mutations must be blocked")
    require("self.failures" not in third_party_handler, "PW1 third-party telemetry must not become GEL contract drift")
    for forbidden in ["post_data", "header_value", ".headers", "input_value"]:
        require(forbidden not in third_party_handler, f"PW1 third-party handler must not inspect {forbidden}")
    for allowed in ["phase", "method", "origin", "redacted_path"]:
        require(allowed in third_party_handler, f"PW1 third-party diagnostic must expose only safe field {allowed}")

    abort_handler = function_source(module, source, "_abort_unexpected_gel")
    require("self.failures.append" in abort_handler, "PW1 unexpected GEL mutation must become contract failure")
    require("self.phase == Phase.AUTHENTICATION" in abort_handler, "PW1 must emit blocked GEL mutation diagnostics during authentication")
    require("self._emit_blocked_diagnostic" in abort_handler, "PW1 auth GEL block must emit immediate safe diagnostic")

    progress_handler = function_source(module, source, "announce_stage")
    require("allowed =" in progress_handler and "PW1 stage:" in progress_handler, "PW1 must use an allowlisted safe progress diagnostic")
    for forbidden in ["student_uid", "teacher", "request", "url", "post_data", "input_value"]:
        require(forbidden not in progress_handler, f"PW1 progress diagnostic must not access {forbidden}")

    submit_handler = function_source(module, source, "_handle_expected_tutorial_submission")
    require("request.post_data" in submit_handler, "PW1 expected tutorial handler must inspect transient body")
    require("route.abort" in submit_handler, "PW1 expected tutorial handler must abort request")
    require("route.continue_()" not in submit_handler, "PW1 expected tutorial handler must have no continue branch")

    run_source = function_source(module, source, "run")
    require("initial_evidence_document()" in run_source, "PW1 run must construct persisted evidence through the privacy-validated preamble helper")
    route_marker = 'context.route("**/*", firewall.handle)'
    nav_marker = "page.goto(LOGIN_PAGE_URL"
    require(route_marker in run_source and nav_marker in run_source, "PW1 run must install firewall and navigate to interactive login page")
    require('LOGIN_PAGE_URL = f"{LEARN2_ORIGIN}/corelogin/"' in source, "PW1 must open the real interactive /corelogin/ page")
    require('LOGIN_POST_PATH = "/user/login"' in source, "PW1 must keep the established login POST handshake endpoint distinct")
    require('LOGIN_FORM_PAGE_URL = f"{LEARN2_ORIGIN}/user/login"' in source, "PW1 must expose the historical second-stage manual login page")
    verification = function_source(module, source, "verify_learn2_session")
    require('/administration/students' in verification, "PW1 must verify Learn2 with the authenticated students GET")
    for forbidden in ["post_data", "header_value", ".headers", "input_value", "text_content", "inner_text"]:
        require(forbidden not in verification, f"PW1 auth verification must not access {forbidden}")
    require("context.new_page()" in verification, "PW1 auth verification must use a separate same-context page")
    require("probe.goto(" in verification, "PW1 auth verification must use browser GET navigation")
    require(run_source.index(route_marker) < run_source.index(nav_marker), "PW1 firewall must be installed before first navigation")
    require("verify_learn2_session(context)" in run_source, "PW1 must verify authentication before evidence")
    require('announce_stage("baseline_summary")' in run_source, "PW1 must identify baseline stage safely")
    require('announce_stage("revision_probe")' in run_source, "PW1 must identify revision stage safely")
    require('announce_stage("evidence_evaluation")' in run_source, "PW1 must identify local evidence evaluation stage safely")
    require('announce_stage("privacy_validation")' in run_source, "PW1 must identify privacy validation stage safely")
    require("page.goto(LOGIN_FORM_PAGE_URL" in run_source, "PW1 must support the historical second manual /user/login stage")
    phase_marker = "firewall.set_phase(Phase.EVIDENCE)"
    verify_marker = "second_auth = verify_learn2_session(context)"
    first_verify_marker = "first_auth = verify_learn2_session(context)"
    require(first_verify_marker in run_source and phase_marker in run_source, "PW1 authentication verification/phase transition missing")
    require(run_source.index(first_verify_marker) < run_source.index(phase_marker), "PW1 must verify stage 1 before evidence")
    require(run_source.index("page.goto(LOGIN_FORM_PAGE_URL") < run_source.index(phase_marker), "PW1 second-stage branch must occur before evidence transition")
    require('service_workers="block"' in run_source, "PW1 browser context must block service workers")
    require("browser.new_context" in run_source and "launch_persistent_context" not in run_source, "PW1 must use ephemeral browser context")
    require('evidence["network_firewall"]["unexpected_gel_mutations_aborted"]' in run_source, "PW1 live failure gate must use GEL-origin mutation count")
    require('evidence["network_firewall"]["third_party_mutations_aborted"] != 0' not in run_source, "PW1 third-party block count must not fail the run")

    trigger = function_source(module, source, "trigger_real_submit")
    require(".click(" in trigger, "PW1 must use a real visible submit control")
    require("form.submit" not in trigger and ".evaluate(\"form => form.submit" not in trigger, "PW1 must not synthesize form.submit()")

    main_source = function_source(module, source, "main")
    require("str(exc)" not in main_source and "{exc}" not in main_source, "PW1 must not print raw exception/browser data")


def check_core_source() -> None:
    source = CORE.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(CORE))
    reducer = function_source(module, source, "parse_urlencoded_submission_evidence")
    require("text-225" not in reducer and "trecs-79" not in reducer, "PW1 reducer must not special-case/persist private tutorial prose")
    require("parse_qs" in reducer, "PW1 reducer must parse only expected urlencoded body")
    require("allowlisted_fields_observed" in reducer, "PW1 reducer must emit allowlisted structural evidence only")
    require("latest_tutorial" in function_source(module, source, "classify_prepopulation"), "PW1 prepopulation must freeze latest tutorial as source")
    classifier = function_source(module, source, "classify_prepopulation")
    require('result["fields"][field_name] = "route_identity"' not in classifier, "PW1 must not persist student_uid in prepopulation field map")
    require('result["fields"][field_name] = "derived_from_authenticated_session"' not in classifier, "PW1 must not persist teacher_id in prepopulation field map")
    require('result["identity_rules"]["teacher"]' in classifier, "PW1 must reduce teacher prepopulation to a relationship-only identity rule")
    require("matching_source_fields" not in classifier and "copied_from_source_field" not in classifier, "PW1 classifier must not search unrelated equal-valued fields for provenance")
    origin_authority = function_source(module, source, "network_origin_authority")
    require('"learn2.guidedelearning.net"' in origin_authority, "PW1 origin authority helper must name the sole GEL host")
    require('"gel_invalid_transport"' in origin_authority and '"third_party"' in origin_authority, "PW1 origin authority taxonomy drifted")
    require("parsed.query" not in origin_authority, "PW1 origin authority must not inspect query data")
    diagnostic = function_source(module, source, "safe_network_diagnostic")
    require("urlparse" in diagnostic, "PW1 safe network diagnostic must parse URL structurally")
    require("parsed.query" not in diagnostic, "PW1 safe network diagnostic must not return parsed query data")
    require("redact_network_path" in diagnostic, "PW1 safe network diagnostic must redact path segments")
    initial = function_source(module, source, "initial_evidence_document")
    require("assert_privacy_safe_evidence(evidence)" in initial, "PW1 initial evidence document must self-validate against the strict privacy guard")
    for forbidden_key in ["raw_html_persisted", "request_headers_persisted", "teacher_names_persisted"]:
        require(forbidden_key not in initial, f"PW1 persisted privacy metadata must not reuse forbidden raw-data key {forbidden_key!r}")
    for safe_key in ["page_source_capture_enabled", "submission_payload_capture_enabled", "network_header_capture_enabled", "staff_display_label_capture_enabled"]:
        require(safe_key in initial, f"PW1 initial privacy metadata missing {safe_key}")


def check_gitignore() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    require("evidence-private/" in text, "PW1 private evidence directory must be gitignored")


def run_offline_tests() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "test_n2_playwright_zero_write.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        raise CheckError("PW1 offline behavioural tests failed:\n" + proc.stdout)


def main() -> int:
    try:
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        check_contract(data)
        check_harness_source()
        check_core_source()
        check_gitignore()
        run_offline_tests()
    except Exception as exc:
        print(f"check:n2-playwright-zero-write FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:n2-playwright-zero-write PASS — pre-login firewall + GEL-vs-third-party mutation authority + two-stage manual GEL login verification + no credential capture + always-abort tutorial probes + latest-source prepopulation audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
